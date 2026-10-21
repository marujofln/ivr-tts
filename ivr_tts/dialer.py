import logging

# from multiprocessing.sharedctypes import Value
import gevent

# import greenswitch
import sys
from settings import config
from freeswitch import FSInboundConnection
from models import BigTableInput, Session
from sqlalchemy import select
import time

logging.basicConfig(
    format="%(asctime)s [DIALER] %(levelname)-8s %(message)s", level=logging.DEBUG
)


class DialerNothingToDial(Exception):
    pass


class DialerStopError(Exception):
    pass


class Dialer:
    def __init__(
        self,
        fs: FSInboundConnection,
        max_concurrent_calls: int = 2,
        logger: logging = logging,
        callerid_num: str = "0000",
        callerid_name: str = "IVR TTS Dialer",
    ):
        """Dialer object

        Args:
            fs_connection (greenswitch.InboundESL): connection InboundESL
            logger (logging): logging object
            callerid_num (str): CallerID number presented on originated calls
            callerid_name (str): CallerID name presented on originated calls
        """
        self.fs = fs
        self.logger = logger
        self.max_concurrent_calls = max_concurrent_calls
        self.callerid_num = callerid_num
        self.callerid_name = callerid_name
        self._running = False
        self._running_calls = []
        self._running_jobs = {}  # {job_uuid: {'call': call_uuid, 'row: row_id},}

    @property
    def running(self):
        return self._running

    @running.setter
    def running(self, value: bool):
        self._running = value

    def stop(self, timeout: float = 4.0):
        if not self.running:
            raise DialerStopError("Already stopped")
        self.logger.info("Stopping dialer...")
        self.running = False

        while len(self._running_jobs) > 0:
            self.logger.info(
                f"Waiting {timeout}s to finish {len(self._running_jobs)} running {'job' if len(self._running_jobs) < 2 else 'jobs'}"
            )
            gevent.sleep(timeout)

    def start(self, domain: str, context: str, dp_dst: str):
        #  self.logger.info(f"Starting dialer on {domain}")
        self.running = True
        while self.running and (len(self._running_calls) < self.max_concurrent_calls):
            self.fs.keep_connected()
            row = Session.execute(
                select(BigTableInput).where(
                    BigTableInput.job_uuid == None  # noqa: E711, W503
                )
            ).scalar()
            if row:
                self.logger.debug(f"Dialing to {row.customer_name} @{row.phone}")
                originated = self.fs.originate(
                    row.phone,
                    dp_dst,
                    row.id,
                    callerid_num=self.callerid_num,
                    callerid_name=self.callerid_name,
                    orig_domain=f"{domain}",
                    dest_context=context,
                    endpoint="loopback",
                    profile="external",
                )

                row.job_uuid = originated["job_uuid"].replace("\n", "")
                row.call_uuid = originated["call_uuid"]
                Session.commit()
                self._running_jobs[row.job_uuid] = {
                    "call": row.call_uuid,
                    "row": row.id,
                }
                self._running_calls.append(row.call_uuid)

            else:
                # raise DialerNothingToDial("Nothing to Dial")
                self.logger.info(
                    f"Nothing to dial. Waiting {config.dialer_job_wait_time}s for new jobs..."
                )
                time.sleep(config.dialer_job_wait_time)

    def on_job_finished(self, event):
        # self.logger.debug(f"Treating event: {event.headers['Event-Name']} 'Unique-ID:' {event.headers['Unique-ID']} Channel-Call-UUID: {event.headers['Channel-Call-UUID']}")

        # self.logger.debug(f"Treating event: {event.headers['Event-Name']}")
        job_return = event.headers["Content-Length"].split("\n")
        if "+OK" in job_return[2]:
            job_status = job_return[2].split(" ")[0]
        else:
            job_status = job_return[2]

        if event.headers["Job-UUID"] in self._running_jobs.keys():
            row = Session.execute(
                select(BigTableInput).where(
                    BigTableInput.id
                    == self._running_jobs[event.headers["Job-UUID"]]["row"]
                )
            ).scalar()
            row.job_status = job_status
            Session.commit()
            del self._running_jobs[event.headers["Job-UUID"]]

    def on_channel_hangup(self, event):
        if event.headers["Channel-Call-UUID"] in self._running_calls:
            row = Session.execute(
                select(BigTableInput).where(
                    BigTableInput.call_uuid == event.headers["Channel-Call-UUID"]
                )
            ).scalar()
            row.hangup_cause = event.headers["Hangup-Cause"]
            if "variable_sip_invite_failure_status" in event.headers.keys():
                row.sip_failure_status = int(
                    event.headers["variable_sip_invite_failure_status"]
                )
            if "variable_sip_invite_failure_phrase" in event.headers.keys():
                row.sip_failure_phrase = event.headers[
                    "variable_sip_invite_failure_phrase"
                ]
            Session.commit()

            self._running_calls.remove(event.headers["Channel-Call-UUID"])
            self.logger.debug(
                f"Removing {event.headers['Channel-Call-UUID']} from running calls"
            )


if __name__ == "__main__":
    fs = FSInboundConnection(
        config.freeswitch_host, config.freeswitch_port, config.freeswitch_password, logging
    )
    dialer = Dialer(
        fs,
        max_concurrent_calls=config.dialer_max_concurrent_calls,
        callerid_num=config.dialer_callerid_number,
        callerid_name=config.dialer_callerid_name,
    )
    dialer.fs.connector.register_handle("BACKGROUND_JOB", dialer.on_job_finished)
    # dialer.fs.connector.register_handle("*", dialer.on_event)
    dialer.fs.connector.register_handle("CHANNEL_HANGUP", dialer.on_channel_hangup)

    while True:
        try:
            fs.keep_connected(
                config.freeswitch_connection_wait_retry,
                config.freeswitch_connection_max_retry,
                config.freeswitch_keep_connected,
            )
            # start dialer
            dialer.start(
                config.dialer_domain,
                config.dialer_dialplan_context,
                config.dialer_dialplan_dst,
            )
            gevent.sleep(config.freeswitch_listen_loop)

        except KeyboardInterrupt:
            fs.connector.stop()
            logging.info("ESL Disconnected.")
            sys.exit(0)
            break

        except gevent.exceptions.LoopExit:
            logging.error("Event loop exit. Restarting Freeswitch connection object.")
            fs = FSInboundConnection(
                config.freeswitch_host,
                config.freeswitch_port,
                config.freeswitch_password,
                logging,
            )

            continue
        except ConnectionResetError:
            logging.error("ConectionResetError")
            continue

        except DialerNothingToDial:
            logging.info("Nothing to dial.")
            try:
                dialer.stop()
                break
            except DialerStopError as error:
                logging.error(f"Stop error: {error}. Stop forced.")
                sys.exit(255)
                break

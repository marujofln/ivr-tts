import logging
from datetime import datetime
import uuid
from gevent import sleep
from greenswitch import InboundESL


class OriginateError(Exception):
    """Error on Originate

    Args:
        Exception (_type_): Error from freeswitch
    """

    pass


class FSInboundConnection(object):
    """Wrapper to greenswitch Inbound Object"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8021,
        password: str = "ClueCon",
        logger: logging = logging,
    ):
        """Initialize object

        Args:
            host (str, optional): _description_. Defaults to "localhost".
            port (int, optional): _description_. Defaults to 8021.
            password (str, optional): _description_. Defaults to "ClueCon".
            logger (logging, optional): _description_. Defaults to logging.
        """
        self._host = host
        self._port = port
        self._last_check = datetime.now()
        self.logger = logger
        self.connector = InboundESL(
            host=host,
            port=port,
            password=password,
        )

    def originate(
        self,
        origin: str,
        destination: str,
        data_id: int,
        callerid_num: str = "0000",
        callerid_name: str = "IVR TTS Dialer",
        orig_domain: str = "localhost",
        dest_context: str = "default",
        endpoint: str = "sofia",  # ex: 'sofia', 'user'
        profile: str = "internal",
    ) -> dict:
        """Originate a background call on Freeswitch

        Args:
            origin (str): Origin (part before '@' url)
            destination (str): Destination
            data_id (int): Data id row on Input big table
            callerid_num (str, optional): CallerID Number. Defaults to "0000".
            callerid_name (str, optional): CallerId Name. Defaults to "IVR TTS Dialer".
            orig_domain (str, optional): Domain (part after '@' on url). Defaults to "localhost".
            dest_context (str, optional): Destination dialplan context. Defaults to "default".
            endpoint (str, optional): Endpoint, ex: 'sofia', 'user'. Defaults to "sofia".


        Raises:
            OriginateError: on -ERR, on any unexpected reply or when the ESL send fails.

        Returns:
            dict: {"job_uuid": ..., "call_uuid": ...} when freeswitch originate returns +OK.
        """

        orig_uuid = str(uuid.uuid4())
        # some possible opts: origination_caller_id_number=12345,ignore_early_media=true,call_timeout=60,hangup_after_bridge=true
        origin_opts = f"{{ignore_early_media=true}}[origination_uuid={orig_uuid},origination_caller_id_number={callerid_num},origination_caller_id_name='{callerid_name}',data_id={data_id}]"
        # dest_opts = ""

        if endpoint == "user":
            from_uri = f"user/{origin}@{orig_domain}"

        elif endpoint == "loopback":
            from_uri = f"{endpoint}/{origin}/{orig_domain}"

        else:
            from_uri = f"{endpoint}/{profile}/{origin}@{orig_domain}"

        # dest_uri = f"{conf.freeswitch.originate_channel}/{destination}@{dst_domain}"
        # originate [origination_uuid=34c48ce0-8142-4471-9509-cf017fb4ad95]user/1000@pbx.example.com &bridge(sofia/internal/1001@pbx.example.com)

        originate_cmd = (
            f"bgapi originate {origin_opts}{from_uri} {destination} XML {dest_context}"
        )
        # originate_cmd = (
        # f"bgapi originate {origin_opts}{from_uri} &socket(127.0.0.1:5000 sync full)"
        # )
        logging.debug(f"Sending ESL command: {originate_cmd}")

        try:
            r = self.connector.send(originate_cmd)
        except KeyError as e:
            self.logger.error(f"Originate: {e}")
            raise OriginateError(f"{e}")

        reply = (r.data or "").strip()
        r_data = reply.split()
        # expected reply: "+OK Job-UUID: <job uuid>"
        if len(r_data) == 3 and r_data[0] == "+OK":
            self.logger.debug(f"Originate returning: {r_data}")
            return {"job_uuid": r_data[2], "call_uuid": orig_uuid}

        if r_data[:1] == ["-ERR"]:
            error = " ".join(r_data[1:]) or "unknown error"
        else:
            error = f"unexpected reply: {reply!r}"
        self.logger.error(f"Originate: {error}")
        raise OriginateError(error)

    def keep_connected(
        self, time_btw_tries: int = 3, connection_tries: int = 5, check_interval: int = 10
    ):
        """Persists freeswitch connection

        Args:
            time_btw_tries (int): Time between tries. Time, in seconds, to wait before try to connect again. Defaults to 3.
            connection_tries (int): Connection tries. Try to connect N times before give up. Defaults to 5.
            check_interval (int, optional): Check interval. Defaults to 10.
        """
        time_diff = datetime.now() - self._last_check
        connection_try = 0
        if time_diff.seconds > check_interval:
            self.connector.send("api uptime")
            self._last_check = datetime.now()

        if not self.connector.connected:
            while connection_tries == 0 or connection_try < connection_tries:
                connection_try += 1
                self.logger.debug(
                    f"Trying to connect to freeswitch at {self._host}:{self._port}. Try: {connection_try}/{'infinity' if connection_tries==0 else connection_tries}"
                )
                try:
                    self.connector.connect()
                    self.logger.info("Successful connected to Freeswitch")
                    # todo: verify if must to register again.
                    # self.connector.register_handle("CHANNEL_EXECUTE_COMPLETE", on_event)
                    self.connector.send("EVENTS PLAIN ALL")
                    break

                except ConnectionRefusedError:
                    self.logger.error(
                        f"Error connecting to Freeswitch at {self._host}:{self._port}. Retry in {time_btw_tries}s"
                    )
                sleep(time_btw_tries)

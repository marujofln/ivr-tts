# -*- coding: utf-8 -*-
from gevent import sleep
import greenswitch
import logging
import sys
from settings import config
from pprint import pprint

""" FOR DEBUG PROPOSES """


EVENTS = [
    "BACKGROUND_JOB",
    "CHANNEL_BRIDGE",
    "CHANNEL_ANSWER",
    "CHANNEL_HANGUP",
    "CHANNEL_ORIGINATE",
    "CHANNEL_PROGRESS",
    "CALL_DETAIL",
    "CALL_SECURE",
    "CALL_SETUP_REQ",
    "CALL_UPDATE",
    "CDR",
]

logging.basicConfig(level=logging.DEBUG)


fs = greenswitch.InboundESL(
    host=config.freeswitch_host,
    port=config.freeswitch_port,
    password=config.freeswitch_password,
)


def on_event(event):
    print(f"========== NEW EVENT: {event.headers['Event-Name']} ==========")
    pprint(event.headers)


if __name__ == "__main__":
    logging.info("Starting listener ")

    try:
        fs.connect()
        logging.info("Successful connected to Freeswitch")
        for event in EVENTS:
            fs.register_handle(event, on_event)
        fs.send("EVENTS PLAIN ALL")
        logging.info(f"listen for {EVENTS}")
        while fs.connected:
            sleep(config.freeswitch_listen_loop)

    except KeyboardInterrupt:
        fs.stop()
        logging.info("ESL Disconnected.")
        sys.exit(0)
        # break

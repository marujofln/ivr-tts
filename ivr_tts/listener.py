# -*- coding: utf-8 -*-
from gevent import sleep
import greenswitch
import logging
import sys
from settings import config
from datetime import datetime


__version__ = '0.0.1'
EVENTS = ["callcenter::info"]

fs = greenswitch.InboundESL(
    host=config.freeswitch_host,
    port=config.freeswitch_port,
    password=config.freeswitch_password,
)


def connect_n_register(time_wait: int, tries: int):
    # by some reason we must to redefine fs object
    global fs
    fs = greenswitch.InboundESL(
        host=config.freeswitch_host,
        port=config.freeswitch_port,
        password=config.freeswitch_password,
    )
    connection_try = 0

    while tries == 0 or connection_try < tries:
        connection_try += 1
        logging.debug(
            f"Trying to connect to freeswitch at {config.freeswitch_host}:{config.freeswitch_port}. Try: {connection_try}/{'infinite' if tries==0 else tries}"
        )
        try:
            fs.connect()
            logging.info("Successful connected to Freeswitch")
            fs.register_handle("CHANNEL_EXECUTE_COMPLETE", on_event)
            fs.send("EVENTS PLAIN ALL")
            # for event in EVENTS:
            #     fs.send(f"filter Event-Subclass {event}")
            break
        except ConnectionRefusedError:
            logging.error(
                f"Error connecting to Freeswitch at {config.freeswitch_host}:{config.freeswitch_port}. Retry in {time_wait}s"
            )
            sleep(time_wait)


def check_connected():
    global last_check
    time_diff = datetime.now() - last_check
    if time_diff.seconds > config.freeswitch_keep_connected:
        fs.send("api uptime")
        last_check = datetime.now()


def on_event(event):
    # print(event.headers)
    pass


logging.basicConfig(level=logging.DEBUG)

logging.info(f"Starting listener version {__version__}")

last_check = datetime.now()

while True:
    try:
        while fs.connected:
            sleep(config.freeswitch_listen_loop)
            check_connected()

        connect_n_register(
            config.freeswitch_connection_wait_retry, config.freeswitch_connection_max_retry
        )

    except KeyboardInterrupt:
        fs.stop()
        logging.info("ESL Disconnected.")
        sys.exit(0)
        break

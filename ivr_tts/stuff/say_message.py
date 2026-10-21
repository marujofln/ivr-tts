# -*- coding: utf-8 -*-
import logging
import greenswitch
from ssml_builder.core import Speech
from models import BigTableInput
from settings import config


logging.basicConfig(
    format="%(asctime)s [IVR] %(levelname)-8s %(message)s", level=logging.DEBUG
)


class IVRMaxTries(Exception):
    """IVRMaxTries exception

    Args:
        Exception ([type]): Message from IVR
    """


class IVRNoData(Exception):
    pass


class IVRError(Exception):
    """IVRError exception

    Args:
        Exception (_type_): Error
    """

    pass


class SayMessage(object):
    """IVR TTS app

    Raises:
        IVRError: Raised on Error
        IVRMaxTries:Raised on max tries reached.

    Returns:
        Object: IVRTTS object
    """

    def __init__(self, session):
        self.session = session
        self.responses = {}
        self.init()

    def init(self, logger: logging = logging):
        self.logger = logger
        self.job_data = {}

    def on_hangup(self, event):
        if event.headers["Channel-Call-UUID"] == self.session.call_uuid:
            self.logger.info("Event hangup received")

    def speak(
        self,
        prompt: str,
        engine: str = "unimrcp:uni2",
        voice: int = "pt-BR-Wavenet-B",
    ):
        """Convert text to speech on freeswitch

        Args:
            prompt (str): Phrase
            engine (str, optional): Freeswitch engine. Defaults to "unimrcp:uni2".
            voice (int, optional): Voice on engine. Defaults to "pt-BR-Wavenet-B".
        """
        # self.session.call_command(f"set", "tts_engine={engine}")
        # self.session.call_command(f"set", "tts_voice={voice}")
        args = f"{engine}|{voice}|{prompt}"
        self.logger.debug(
            f"Speaking {prompt} with voice {voice} using engine {engine}."
        )
        self.session.call_command("speak", args)
        return

    def run(self):
        """Run"""
        try:
            self.safe_run()

        except greenswitch.esl.OutboundSessionHasGoneAway:
            self.logger.info("Session Finished")
            # self.database_write()

        except IVRNoData as error:
            self.logger.error(error)

        except Exception as error:
            self.logger.error(f"Exception {error }raised when handling call")
            self.session.stop()

    def safe_run(self):
        """
        Main function that is called when a call comes in.
        """

        ssml = Speech()
        self.session.linger()
        id = self.session.send(f"api uuid_getvar {self.session.call_uuid} data_id")
        if id.data == "_undef_":
            raise IVRNoData(
                f"Call variable 'data_id' not defined on call uuid: {self.session.call_uuid}"
            )
        elif id.data == "dev":
            self.job_data = {
                "phone": "11900000000",
                "customer_name": "Fulano de Tal",
                "condo": "Condomínio Exemplo",
                "unity": "unidade 101",
                "call_uuid": "00000000-0000-0000-0000-000000000000",
                "email": "fulano@example.com",
            }

        else:
            origin_data = BigTableInput.query.filter_by(id=id.data).first()

            if not origin_data:
                raise IVRNoData(
                    f"Cannot find call uuid: {self.session.call_uuid} data."
                )

            for key in origin_data.__dict__.keys():
                if key in [
                    "phone",
                    "customer_name",
                    "condo",
                    "unity",
                    "call_uuid",
                    "email",
                ]:
                    self.job_data[key] = origin_data.__dict__[key]

            # close session on sqlalquemy queue pool
            origin_data.query.session.close()

        # unregister greenswitch hardcoded event handler
        del self.session.event_handlers["CHANNEL_HANGUP"]
        self.session.register_handle("CHANNEL_HANGUP", self.on_hangup)

        # self.session.register_handle("callcenter::info", self.on_call_center)
        self.session.send("EVENTS PLAIN ALL")
        self.session.answer()
        ssml.pause(0.3)
        ssml.p(
            f"A {config.ivr_company_name} informa: a Unidade {self.job_data['unity']}, localizada no {self.job_data['condo']}, possui débitos em aberto. Para negociar agora, aguarde na linha ou entre em contato com a nossa central de atendimento no {config.ivr_contact_phone}."
        )
        self.speak(ssml.speak())
        self.session.hangup()
        # self.session.send


if __name__ == "__main__":
    server = greenswitch.OutboundESLServer(
        bind_address="0.0.0.0",
        bind_port=5000,
        application=SayMessage,
        max_connections=5,
    )
    server.listen()

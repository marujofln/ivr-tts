# -*- coding: utf-8 -*-
import logging
import re
from xml.sax.saxutils import escape

# import gevent
import greenswitch
from ssml_builder.core import Speech
import xmltodict
from xml.parsers.expat import ExpatError
from models import BigTableOutput, BigTableInput, Session
from settings import config


logging.basicConfig(
    format="%(asctime)s [IVR] %(levelname)-8s %(message)s", level=logging.DEBUG
)

# log = logging.getLogger(__name__)

#
#     Add a extension on your dialplan to bound the outbound socket on FS channel
#     as example below
#     <extension name="out socket">
#         <condition>
#             <action application="socket" data="<outbound socket server host>:<outbound socket server port> sync full"/>
#         </condition>
#     </extension>
#     Or see the complete doc on https://freeswitch.org/confluence/display/FREESWITCH/mod_event_socket
#

# TRUE_PHRASES = ["sim", "gostaria", "está", "sou eu", "tenho interesse"]
# FALSE_PHRASES = ["não"]


class IVRMaxTries(Exception):
    """IVRMaxTries exception

    Args:
        Exception ([type]): Message from IVR
    """


class IVRNoData(Exception):
    pass


class IVRForbiddenPeer(Exception):
    pass


class IVRError(Exception):
    """IVRError exception

    Args:
        Exception (_type_): Error
    """

    pass


class TTSVoiceMessage(object):
    """IVR TTS app

    Raises:
        IVRError: Raised on Error
        IVRMaxTries:Raised on max tries reached.

    Returns:
        Object: IVRTTS object
    """

    def __init__(self, session):
        self.session = session
        # self.responses = {}
        self.init()

    def init(self, logger: logging = logging):
        self.logger = logger
        self.job_data = {}

    def on_hangup(self, event):
        if event.headers["Channel-Call-UUID"] == self.session.call_uuid:
            self.logger.info("Event hangup received")
            self.database_write()

    # def on_call_center(self, event):
    #     if event.headers["Channel-Call-UUID"] == self.session.call_uuid:
    #         self.logger.info("Call {self.session.call_uuid} transfered to Call center.")
    #         self.database_write()

    def database_write(self):
        self.job_data.update({"responses": self.responses[self.session.call_uuid]})
        self.logger.debug(f"Adding to database {self.job_data}")
        Session.add(BigTableOutput(**self.job_data))
        Session.commit()

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
        # a line break would end the ESL sendmsg and let the rest run as a new command
        prompt = re.sub(r"[\x00-\x1f\x7f]+", " ", prompt)
        args = f"{engine}|{voice}|{prompt}"
        self.logger.debug(
            f"Speaking {prompt} with voice {voice} using engine {engine}."
        )
        self.session.call_command("speak", args)
        return

    # def sorry(self):
    #     """Say sorry message."""
    #     ssml = Speech()
    #     ssml.pause(0.3)
    #     ssml.add_text("Desculpe o incômodo.")
    #     self.speak(ssml.speak())
    #     self.session.hangup()

    # def call_later(self):
    #     """Say call_later message"""
    #     ssml = Speech()
    #     ssml.add_text("Talvez, você esteja sem tempo agora. Vou retornar mais tarde.")
    #     self.speak(ssml.speak())
    #     self.session.hangup()

    # def ivr_say_n_get_bool(
    #     self,
    #     prompt: str,
    #     error_phrase: str,
    #     engine: str = "unimrcp:uni2",
    #     start_input_timers: str = "false",
    #     no_input_timeout: int = 10000,
    #     response_timeout: int = 10000,
    #     asr_grammar: str = "speech/transcribe",
    #     asr_language: str = "pt-BR",
    #     tts_voice: str = "pt-BR-Wavenet-B",
    #     max_tries: int = 3,
    #     confidence_trashold: float = 0.83,
    # ) -> bool:
    #     """Say a prompt and get a voice True or False return.

    #     Args:
    #         prompt (str): Phrase
    #         error_phrase (str): Error Phrase
    #         engine (str, optional): freeswitch engine. Defaults to "unimrcp:uni2".
    #         start_input_timers (str, optional): engine param. Defaults to "false".
    #         no_input_timeout (int, optional): engine param. Defaults to 10000.
    #         response_timeout (int, optional): engine param. Defaults to 10000.
    #         asr_grammar (str, optional): engine speech to text grammar. Defaults to "speech/transcribe".
    #         asr_language (str, optional): engine speech to text language. Defaults to "pt-BR".
    #         tts_voice (str, optional): engine TTS voice. Defaults to "pt-BR-Wavenet-B".
    #         max_tries (int, optional): Max tries on getting response. Defaults to 3.
    #         confidence_trashold (float, optional): Confidence (assertiveness) on response [0.0-1.0]. Defaults to 0.83,

    #     Raises:
    #         IVRError: Error on IVR
    #         IVRMaxTries: Timeout

    #     Returns:
    #         bool: True or False intension
    #     """
    #     tries = 0
    #     self.session.call_command("set", f"tts_engine={engine}")
    #     self.session.call_command("set", f"tts_voice={tts_voice}")

    #     while tries < max_tries:
    #         tries += 1
    #         self.logger.debug(
    #             f"Speaking {prompt} with voice {tts_voice} using engine {engine}. Waiting return in {asr_language}"
    #         )
    #         ret = self.session.call_command(
    #             "play_and_detect_speech",
    #             f"say: {prompt} detect:{engine} {{start-input-timers={start_input_timers},no-input-timeout={no_input_timeout},recognition-timeout={response_timeout}}}builtin:{asr_grammar}?language={asr_language}",
    #         )

    #         if not ret.data == "+OK":
    #             self.logger.error(
    #                 "Error sending play_and_detect_speech command to Freeswitch."
    #             )
    #             raise IVRError("Error sending command to Freeswitch.")

    #         ret = self.session.send(
    #             f"api uuid_getvar {self.session.call_uuid} detect_speech_result"
    #         )
    #         # timeout
    #         if ret.data == "Completion-Cause: 002":
    #             self.logger.info("Timeout getting speech...")
    #             self.speak(error_phrase)
    #             continue

    #         try:
    #             speech_result = xmltodict.parse(ret.data)
    #         except ExpatError as error:
    #             self.logger.error(f'Error {error} parsing result from speech')
    #             self.speak(error_phrase)
    #             continue

    #         confidence = float(speech_result["result"]["interpretation"]["@confidence"])

    #         if confidence < confidence_trashold:
    #             self.logger.info(
    #                 f"Confidence {confidence} < {confidence_trashold}, restarting loop"
    #             )
    #             self.speak(error_phrase)
    #             continue

    #         instance = str(speech_result["result"]["interpretation"]["instance"])

    #         if any(match in instance.lower() for match in TRUE_PHRASES):
    #             self.logger.debug(
    #                 f"Returning True: Detected phrase: {instance} in {TRUE_PHRASES}"
    #             )
    #             return True
    #         elif any(match in instance.lower() for match in FALSE_PHRASES):
    #             self.logger.debug(
    #                 f"Returning False: Detected phrase: {instance} in {FALSE_PHRASES}"
    #             )
    #             return False
    #         else:
    #             self.logger.debug(
    #                 f"Detected phrase: {instance} not in {TRUE_PHRASES} or {FALSE_PHRASES}"
    #             )
    #             self.speak(error_phrase)
    #             continue

    #     if tries >= max_tries:
    #         self.logger.info(f"Max Tries: {tries} reached")
    #         raise IVRMaxTries("Max Tries reached")

    def run(self):
        """Run"""
        try:
            self.safe_run()

        except greenswitch.esl.OutboundSessionHasGoneAway:
            self.logger.info("Session Finished")
            # self.database_write()

        except IVRNoData as error:
            self.logger.error(error)

        except IVRForbiddenPeer as error:
            self.logger.warning(error)
            self.session.stop()

        except Exception as error:
            self.logger.error(f"Exception {error }raised when handling call")
            self.session.stop()

    def check_peer(self):
        """Only FreeSWITCH may drive this server: anyone else could read contacts by data_id."""
        allowed = [p.strip() for p in config.ivr_allowed_peers.split(",") if p.strip()]
        if "*" in allowed:
            return
        peer = self.session.sock.getpeername()[0]
        if peer not in allowed:
            raise IVRForbiddenPeer(f"Rejecting outbound session from {peer}")

    def safe_run(self):
        """
        Main function that is called when a call comes in.
        """
        self.check_peer()
        self.responses = {
            self.session.call_uuid: {
                "is_customer": True,
                "is_responsible": True,
                "negociate": True,
            }
        }

        ssml_intro = Speech()
        self.session.linger()
        id = self.session.send(f"api uuid_getvar {self.session.call_uuid} data_id")
        if id.data == "_undef_":
            raise IVRNoData(
                f"Call variable 'data_id' not defined on call uuid: {self.session.call_uuid}"
            )

        origin_data = BigTableInput.query.filter_by(id=id.data).first()
        # origin_data = db.session.execute(
        #     db.select(BigTableInput).where(BigTableInput.id == id.data)
        # ).scalar()
        if not origin_data:
            raise IVRNoData(f"Cannot find call uuid: {self.session.call_uuid} data.")

        for key in origin_data.__dict__.keys():
            if key in ["phone", "customer_name", "unity", "call_uuid", "email"]:
                self.job_data[key] = origin_data.__dict__[key]

        # unregister greenswitch hardcoded event handler
        del self.session.event_handlers["CHANNEL_HANGUP"]

        # close session on sqlalquemy queue pool
        origin_data.query.session.close()

        self.session.register_handle("CHANNEL_HANGUP", self.on_hangup)
        # self.session.register_handle("callcenter::info", self.on_call_center)
        self.session.send("EVENTS PLAIN ALL")
        self.session.answer()
        ssml_intro.pause(0.3)
        ssml_intro.add_text("Olá!")
        ssml_intro.pause(0.1)

        ssml_intro.pause(0.1)
        ssml_intro.emphasis(
            f"Esse é um lembrete importante da {config.ivr_company_name} sobre a dívida pendente do Condomínio:",
            "strong",
        )

        self.speak(ssml_intro.speak())
        ssml = Speech()
        condo, unity, name = (
            escape(str(v)) for v in (origin_data.condo, origin_data.unity, origin_data.customer_name)
        )
        ssml.add_text(f"{condo}, unidade: {unity}, para {name}")
        self.speak(ssml.speak())

        ssml = Speech()
        ssml.add_text(
            f"Para negociar ou obter mais informações, ligue para {config.ivr_contact_phone} ou envie uma mensagem pelo WhatsApp no mesmo número, {config.ivr_contact_phone}."
        )
        ssml.pause(0.1)
        ssml.add_text("Agradecemos pela sua atenção e cooperação.")
        self.speak(ssml.speak())
        self.session.hangup()


if __name__ == "__main__":
    server = greenswitch.OutboundESLServer(
        bind_address=config.ivr_bind_address,
        bind_port=config.ivr_bind_port,
        application=TTSVoiceMessage,
        max_connections=5,
    )
    server.listen()

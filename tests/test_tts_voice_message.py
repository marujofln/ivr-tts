from unittest.mock import MagicMock

import greenswitch
import pytest

from models import BigTableInput, BigTableOutput
from tts_voice_message import IVRForbiddenPeer, IVRNoData, TTSVoiceMessage


@pytest.fixture
def session():
    s = MagicMock()
    s.call_uuid = "call-1"
    s.event_handlers = {"CHANNEL_HANGUP": MagicMock()}
    s.sock.getpeername.return_value = ("127.0.0.1", 40000)
    return s


@pytest.fixture
def row(db):
    r = BigTableInput(
        customer_name="Fulano de Tal", condo="Condomínio Exemplo",
        unity="101", phone="11900000001", call_uuid="call-1",
    )
    db.add(r)
    db.commit()
    return r


def spoken(session):
    return " ".join(c.args[1] for c in session.call_command.call_args_list if c.args[0] == "speak")


def test_speak_args(session):
    TTSVoiceMessage(session).speak("Olá", engine="unimrcp:x", voice="v1")
    session.call_command.assert_called_once_with("speak", "unimrcp:x|v1|Olá")


def test_safe_run_plays_message_and_hangs_up(db, row, session):
    session.send.return_value = MagicMock(data=str(row.id))

    ivr = TTSVoiceMessage(session)
    ivr.safe_run()

    session.answer.assert_called_once()
    session.hangup.assert_called_once()
    session.register_handle.assert_called_once_with("CHANNEL_HANGUP", ivr.on_hangup)
    text = spoken(session)
    assert "Empresa Teste" in text
    assert "zero oitocentos teste" in text
    assert "Condomínio Exemplo, unidade: 101, para Fulano de Tal" in text
    assert ivr.job_data["phone"] == "11900000001"


def test_safe_run_without_data_id(session):
    session.send.return_value = MagicMock(data="_undef_")
    with pytest.raises(IVRNoData, match="not defined"):
        TTSVoiceMessage(session).safe_run()


def test_safe_run_unknown_row(db, session):
    session.send.return_value = MagicMock(data="999")
    with pytest.raises(IVRNoData, match="Cannot find"):
        TTSVoiceMessage(session).safe_run()


def test_hangup_writes_output(db, row, session):
    session.send.return_value = MagicMock(data=str(row.id))
    ivr = TTSVoiceMessage(session)
    ivr.safe_run()

    ivr.on_hangup(MagicMock(headers={"Channel-Call-UUID": "call-1"}))

    out = db.query(BigTableOutput).one()
    assert out.customer_name == "Fulano de Tal"
    assert out.call_uuid == "call-1"
    assert out.responses == {"is_customer": True, "is_responsible": True, "negociate": True}


def test_hangup_of_other_call_is_ignored(db, session):
    ivr = TTSVoiceMessage(session)
    ivr.on_hangup(MagicMock(headers={"Channel-Call-UUID": "other"}))
    assert db.query(BigTableOutput).count() == 0


def test_run_swallows_missing_data(session):
    session.send.return_value = MagicMock(data="_undef_")
    TTSVoiceMessage(session).run()
    session.stop.assert_not_called()


def test_run_handles_session_gone(session):
    session.send.side_effect = greenswitch.esl.OutboundSessionHasGoneAway
    TTSVoiceMessage(session).run()
    session.stop.assert_not_called()


def test_run_stops_session_on_unexpected_error(session):
    session.linger.side_effect = RuntimeError("boom")
    TTSVoiceMessage(session).run()
    session.stop.assert_called_once()


def test_speak_strips_line_breaks(session):
    TTSVoiceMessage(session).speak("a\n\napi system id\r\n", engine="e", voice="v")
    session.call_command.assert_called_once_with("speak", "e|v|a api system id ")


def test_safe_run_escapes_contact_fields(db, session):
    r = BigTableInput(
        customer_name='<audio src="http://attacker.example.com/x"/>',
        condo="A & B\n\napi system id", unity="1", phone="11900000001", call_uuid="call-1",
    )
    db.add(r)
    db.commit()
    session.send.return_value = MagicMock(data=str(r.id))

    TTSVoiceMessage(session).safe_run()

    text = spoken(session)
    assert "<audio" not in text
    assert "&lt;audio" in text
    assert "A &amp; B api system id" in text
    assert all("\n" not in c.args[1] for c in session.call_command.call_args_list if c.args[0] == "speak")


def test_safe_run_rejects_unknown_peer(db, row, session):
    session.sock.getpeername.return_value = ("203.0.113.5", 40000)
    with pytest.raises(IVRForbiddenPeer):
        TTSVoiceMessage(session).safe_run()
    session.send.assert_not_called()


def test_run_stops_session_from_unknown_peer(session):
    session.sock.getpeername.return_value = ("203.0.113.5", 40000)
    TTSVoiceMessage(session).run()
    session.stop.assert_called_once()
    session.answer.assert_not_called()


def test_allowed_peers_list_and_wildcard(db, row, session, monkeypatch):
    from settings import config

    session.sock.getpeername.return_value = ("172.17.0.1", 40000)
    session.send.return_value = MagicMock(data=str(row.id))

    monkeypatch.setattr(config, "ivr_allowed_peers", "10.0.0.1, 172.17.0.1")
    TTSVoiceMessage(session).safe_run()

    monkeypatch.setattr(config, "ivr_allowed_peers", "*")
    session.event_handlers = {"CHANNEL_HANGUP": MagicMock()}
    session.sock.getpeername.return_value = ("203.0.113.5", 40000)
    TTSVoiceMessage(session).safe_run()
    assert session.answer.call_count == 2

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import freeswitch
from freeswitch import FSInboundConnection, OriginateError


@pytest.fixture
def fs():
    with patch.object(freeswitch, "InboundESL") as esl:
        conn = FSInboundConnection("fs.example.com", 8021, "secret")
        conn.connector = esl.return_value
        yield conn


def reply(data):
    return MagicMock(data=data)


def test_originate_loopback(fs):
    fs.connector.send.return_value = reply("+OK Job-UUID: job-123")

    result = fs.originate(
        "11900000001", "99", 7, orig_domain="pbx.example.com",
        dest_context="pbx.example.com", endpoint="loopback",
    )

    cmd = fs.connector.send.call_args.args[0]
    assert cmd.startswith("bgapi originate {ignore_early_media=true}[origination_uuid=")
    assert "data_id=7" in cmd
    assert "origination_caller_id_name='IVR TTS Dialer'" in cmd
    assert cmd.endswith("loopback/11900000001/pbx.example.com 99 XML pbx.example.com")
    assert result["job_uuid"] == "job-123"
    assert f"origination_uuid={result['call_uuid']}," in cmd


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("user", "user/1000@pbx.example.com"),
        ("sofia", "sofia/internal/1000@pbx.example.com"),
    ],
)
def test_originate_uri_by_endpoint(fs, endpoint, expected):
    fs.connector.send.return_value = reply("+OK Job-UUID: job-1")
    fs.originate("1000", "99", 1, orig_domain="pbx.example.com", endpoint=endpoint)
    assert f"]{expected} 99 XML default" in fs.connector.send.call_args.args[0]


def test_originate_error(fs):
    fs.connector.send.return_value = reply("-ERR USER_NOT_REGISTERED now")
    with pytest.raises(OriginateError, match="USER_NOT_REGISTERED"):
        fs.originate("1000", "99", 1)


def test_keep_connected_reconnects(fs):
    fs.connector.connected = False
    fs.connector.connect.side_effect = [ConnectionRefusedError, None]

    with patch.object(freeswitch, "sleep") as sleep:
        fs.keep_connected(time_btw_tries=0, connection_tries=3)

    assert fs.connector.connect.call_count == 2
    fs.connector.send.assert_called_with("EVENTS PLAIN ALL")
    sleep.assert_called()


def test_keep_connected_gives_up_after_max_tries(fs):
    fs.connector.connected = False
    fs.connector.connect.side_effect = ConnectionRefusedError

    with patch.object(freeswitch, "sleep"):
        fs.keep_connected(time_btw_tries=0, connection_tries=2)

    assert fs.connector.connect.call_count == 2


def test_keep_connected_noop_when_connected(fs):
    fs.connector.connected = True
    fs.keep_connected(check_interval=60)
    fs.connector.connect.assert_not_called()
    fs.connector.send.assert_not_called()


def test_originate_key_error(fs):
    fs.connector.send.side_effect = KeyError("Reply-Text")
    with pytest.raises(OriginateError, match="Reply-Text"):
        fs.originate("1000", "99", 1)


def test_keep_connected_checks_uptime_after_interval(fs):
    fs.connector.connected = True
    fs._last_check = datetime.now() - timedelta(seconds=30)

    fs.keep_connected(check_interval=10)

    fs.connector.send.assert_called_once_with("api uptime")
    assert datetime.now() - fs._last_check < timedelta(seconds=5)

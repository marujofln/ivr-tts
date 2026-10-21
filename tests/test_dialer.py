from unittest.mock import MagicMock

import pytest

from dialer import Dialer, DialerStopError
from models import BigTableInput


def event(**headers):
    return MagicMock(headers=headers)


@pytest.fixture
def row(db):
    r = BigTableInput(
        customer_name="Fulano de Tal", condo="Condomínio Exemplo",
        unity="101", phone="11900000001",
    )
    db.add(r)
    db.commit()
    return r


@pytest.fixture
def dialer():
    fs = MagicMock()
    fs.originate.return_value = {"job_uuid": "job-1\n", "call_uuid": "call-1"}
    return Dialer(fs, max_concurrent_calls=1, callerid_num="1234", callerid_name="Teste")


def test_start_dials_pending_row(db, row, dialer):
    dialer.start("pbx.example.com", "ctx", "99")

    dialer.fs.keep_connected.assert_called()
    dialer.fs.originate.assert_called_once_with(
        "11900000001", "99", row.id,
        callerid_num="1234", callerid_name="Teste",
        orig_domain="pbx.example.com", dest_context="ctx",
        endpoint="loopback", profile="external",
    )
    db.refresh(row)
    assert row.job_uuid == "job-1"
    assert row.call_uuid == "call-1"
    assert dialer._running_jobs == {"job-1": {"call": "call-1", "row": row.id}}
    assert dialer._running_calls == ["call-1"]


def test_on_job_finished_stores_status(db, row, dialer):
    dialer.start("pbx.example.com", "ctx", "99")

    dialer.on_job_finished(
        event(**{"Job-UUID": "job-1", "Content-Length": "41\n\n+OK call-1\n"})
    )

    db.refresh(row)
    assert row.job_status == "+OK"
    assert dialer._running_jobs == {}


def test_on_job_finished_stores_error(db, row, dialer):
    dialer.start("pbx.example.com", "ctx", "99")

    dialer.on_job_finished(
        event(**{"Job-UUID": "job-1", "Content-Length": "30\n\n-ERR NO_ANSWER\n"})
    )

    db.refresh(row)
    assert row.job_status == "-ERR NO_ANSWER"


def test_on_job_finished_ignores_unknown_job(db, row, dialer):
    dialer.on_job_finished(
        event(**{"Job-UUID": "other", "Content-Length": "10\n\n+OK x\n"})
    )
    db.refresh(row)
    assert row.job_status is None


def test_on_channel_hangup_stores_cause(db, row, dialer):
    dialer.start("pbx.example.com", "ctx", "99")

    dialer.on_channel_hangup(
        event(**{
            "Channel-Call-UUID": "call-1",
            "Hangup-Cause": "USER_BUSY",
            "variable_sip_invite_failure_status": "486",
            "variable_sip_invite_failure_phrase": "Busy Here",
        })
    )

    db.refresh(row)
    assert row.hangup_cause == "USER_BUSY"
    assert row.sip_failure_status == 486
    assert row.sip_failure_phrase == "Busy Here"
    assert dialer._running_calls == []


def test_stop_when_not_running(dialer):
    with pytest.raises(DialerStopError):
        dialer.stop()

from unittest.mock import MagicMock, patch

import pytest

import dialer as dialer_module
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


def test_start_waits_when_nothing_to_dial(db, dialer):
    def stop_dialer(seconds):
        dialer.running = False

    with patch.object(dialer_module.time, "sleep", side_effect=stop_dialer) as sleep:
        dialer.start("pbx.example.com", "ctx", "99")

    sleep.assert_called_once_with(dialer_module.config.dialer_job_wait_time)
    dialer.fs.originate.assert_not_called()


def test_start_respects_max_concurrent_calls(db, dialer):
    for i in range(3):
        db.add(BigTableInput(customer_name=f"Contato {i}", phone=f"1190000000{i}"))
    db.commit()
    dialer.max_concurrent_calls = 2
    dialer.fs.originate.side_effect = [
        {"job_uuid": f"job-{i}", "call_uuid": f"call-{i}"} for i in range(3)
    ]

    dialer.start("pbx.example.com", "ctx", "99")

    assert dialer.fs.originate.call_count == 2
    assert db.query(BigTableInput).filter(BigTableInput.job_uuid.is_(None)).count() == 1


def test_stop_waits_running_jobs(dialer):
    dialer.running = True
    dialer._running_jobs = {"job-1": {"call": "call-1", "row": 1}}

    def finish_job(seconds):
        dialer._running_jobs.clear()

    with patch.object(dialer_module.gevent, "sleep", side_effect=finish_job) as sleep:
        dialer.stop(timeout=0.5)

    assert dialer.running is False
    sleep.assert_called_once_with(0.5)

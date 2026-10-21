import pytest
from pydantic import ValidationError

from settings import Settings

REQUIRED = {
    "fief_client_id": "id",
    "fief_client_secret": "secret",
    "dialer_domain": "pbx.example.com",
    "dialer_dialplan_context": "pbx.example.com",
    "dialer_dialplan_dst": "99",
}


@pytest.fixture
def clean_env(monkeypatch):
    for name in ["DATABASE_URL", *[k.upper() for k in REQUIRED]]:
        monkeypatch.delenv(name, raising=False)


def test_defaults(clean_env):
    s = Settings(_env_file=None, **REQUIRED)
    assert s.freeswitch_host == "localhost"
    assert s.freeswitch_port == 8021
    assert s.dialer_max_concurrent_calls == 10
    assert s.fief_base_url == "https://auth.example.com"


def test_database_url_built_from_postgres_settings(clean_env):
    s = Settings(
        _env_file=None,
        postgres_host="db",
        postgres_port=5433,
        postgres_user="u",
        postgres_password="p@ss:w/rd",
        postgres_database="calls",
        **REQUIRED,
    )
    # special characters on password must be escaped
    assert s.database_url == "postgresql+psycopg2://u:p%40ss%3Aw%2Frd@db:5433/calls"


def test_database_url_override(clean_env):
    s = Settings(_env_file=None, database_url="sqlite://", **REQUIRED)
    assert s.database_url == "sqlite://"


def test_missing_required_settings(clean_env):
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    missing = {e["loc"][0] for e in exc.value.errors()}
    assert missing == set(REQUIRED)


def test_reads_environment(clean_env, monkeypatch):
    monkeypatch.setenv("FREESWITCH_HOST", "fs.example.com")
    monkeypatch.setenv("DIALER_MAX_CONCURRENT_CALLS", "5")
    s = Settings(_env_file=None, **REQUIRED)
    assert s.freeswitch_host == "fs.example.com"
    assert s.dialer_max_concurrent_calls == 5

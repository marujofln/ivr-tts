import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules inside ivr_tts/ import each other as top-level modules (they run as scripts)
sys.path.insert(0, str(ROOT / "ivr_tts"))

# Required settings must exist before any module imports `settings.config`
os.environ.update(
    {
        "FIEF_CLIENT_ID": "test-client",
        "FIEF_CLIENT_SECRET": "test-secret",
        "DIALER_DOMAIN": "pbx.example.com",
        "DIALER_DIALPLAN_CONTEXT": "pbx.example.com",
        "DIALER_DIALPLAN_DST": "99",
        "DATABASE_URL": "sqlite://",
        "IVR_COMPANY_NAME": "Empresa Teste",
        "IVR_CONTACT_PHONE": "zero oitocentos teste",
    }
)

import pytest  # noqa: E402


@pytest.fixture
def db():
    """Fresh in-memory schema for each test."""
    from models import Base, Session, engine

    Base.metadata.create_all(engine)
    yield Session
    Session.remove()
    Base.metadata.drop_all(engine)

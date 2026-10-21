import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import app as app_module
from app import app, phone_parser
from models import Base

CSV = (
    "Fulano de Tal,Condomínio Exemplo,101,(11) 90000-0001\n"
    "Beltrana da Silva,Condomínio Exemplo,202,+55 21 90000-0002\n"
)


@pytest.fixture
def client(monkeypatch):
    # the endpoint runs in another thread: share a single in-memory connection
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(app_module, "create_engine", lambda url: engine)
    app.dependency_overrides[app_module.csv_writer] = lambda: {"id": "user"}
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def test_phone_parser_national_number():
    assert phone_parser("(11) 90000-0001") == 11900000001
    assert phone_parser("+55 21 90000-0002") == 21900000002


def test_phone_parser_invalid():
    with pytest.raises(HTTPException) as exc:
        phone_parser("not a phone")
    assert exc.value.status_code == 453


def test_upload_csv(client):
    c, engine = client
    r = c.post("/v1/upload_csv", files={"file": ("list.csv", CSV.encode(), "text/csv")})

    assert r.status_code == 200
    assert r.json() == {"loaded": "list.csv", "size": len(CSV.encode())}
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT customer_name, unity, phone FROM big_table_input ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [
        ("Fulano de Tal", "101", "11900000001"),
        ("Beltrana da Silva", "202", "21900000002"),
    ]


def test_upload_rejects_non_csv(client):
    c, _ = client
    r = c.post("/v1/upload_csv", files={"file": ("list.txt", b"x", "text/plain")})
    assert r.status_code == 415


def test_upload_rejects_invalid_phone(client):
    c, _ = client
    r = c.post(
        "/v1/upload_csv",
        files={"file": ("list.csv", b"Fulano,Condo,101,abc\n", "text/csv")},
    )
    assert r.status_code == 453


def test_upload_requires_token():
    r = TestClient(app).post(
        "/v1/upload_csv", files={"file": ("list.csv", CSV.encode(), "text/csv")}
    )
    assert r.status_code == 401


def test_upload_database_error(monkeypatch):
    # no schema on this database: to_sql into a missing column set must fail
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE big_table_input (id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(app_module, "create_engine", lambda url: engine)
    app.dependency_overrides[app_module.csv_writer] = lambda: {"id": "user"}
    try:
        r = TestClient(app).post(
            "/v1/upload_csv", files={"file": ("list.csv", CSV.encode(), "text/csv")}
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 452
    assert "Error while uploading CSV to database" in r.json()["detail"]


def test_me_returns_token_info():
    app.dependency_overrides[app_module.authenticated] = lambda: {"id": "user-1", "scope": ["openid"]}
    try:
        r = TestClient(app).get("/me")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"id": "user-1", "scope": ["openid"]}


def test_me_requires_token():
    assert TestClient(app).get("/me").status_code == 401

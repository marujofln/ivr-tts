from pathlib import Path

import pytest
from phonenumbers.phonenumberutil import NumberParseException
from sqlalchemy import create_engine, text

from csv_import import import_csv, phone_parser
from models import Base

EXAMPLE_CSV = Path(__file__).resolve().parent.parent / "csv" / "example.csv"


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def test_phone_parser():
    assert phone_parser("(11) 90000-0001") == 11900000001


def test_phone_parser_invalid():
    with pytest.raises(NumberParseException):
        phone_parser("abc")


def test_import_example_csv(engine):
    import_csv(str(EXAMPLE_CSV), engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT customer_name, condo, unity, phone, job_uuid FROM big_table_input ORDER BY id")
        ).all()
    assert [tuple(r) for r in rows] == [
        ("Fulano de Tal", "Condomínio Exemplo", "Bloco A 101", "11900000001", None),
        ("Beltrana da Silva", "Condomínio Exemplo", "Bloco B 202", "11900000002", None),
        ("Ciclano Souza", "Residencial Modelo", "Casa 3", "21900000003", None),
    ]


def test_import_appends(engine):
    import_csv(str(EXAMPLE_CSV), engine)
    import_csv(str(EXAMPLE_CSV), engine)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM big_table_input")).scalar() == 6

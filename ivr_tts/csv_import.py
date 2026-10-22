import re
import sys

import pandas as pd
from phonenumbers import parse
from sqlalchemy import create_engine
from settings import config

columns = [
    "customer_name",
    "condo",
    "unity",
    "phone",
    # "ivr_listen_time",
    # "ivr_played_full",
]


# Control characters (CR/LF included) would end the ESL command that speaks the field
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")
TEXT_COLUMNS = ("customer_name", "condo", "unity")


def clean_text(value: str):
    """Replace control characters with a space. Empty fields stay NULL."""
    return CONTROL_CHARS.sub(" ", value).strip() or None


def phone_parser(number: str):
    return parse(number, "BR").national_number


def import_csv(path: str, engine):
    """Load a headerless CSV (customer_name, condo, unity, phone) into big_table_input."""
    for df in pd.read_csv(
        path,
        names=columns,
        chunksize=1000,
        converters={"phone": phone_parser, **dict.fromkeys(TEXT_COLUMNS, clean_text)},
    ):
        df.to_sql(
            "big_table_input",
            engine,
            index=False,
            if_exists="append",  # if the table already exists, append this data
        )


if __name__ == "__main__":
    import_csv(
        sys.argv[1] if len(sys.argv) > 1 else "csv/example.csv",
        create_engine(config.database_url),
    )

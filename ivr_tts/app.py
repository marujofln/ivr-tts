# -*- coding: utf-8 -*-
import logging
from io import BytesIO

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from csv_import import TEXT_COLUMNS, clean_text
from fief_client import FiefAccessTokenInfo
from phonenumbers import parse
from phonenumbers.phonenumberutil import NumberParseException
from security import auth
from settings import config
from sqlalchemy import create_engine

logging.basicConfig(
    format="%(asctime)s [WEBSERVER] %(levelname)-8s %(message)s", level=logging.DEBUG
)


def phone_parser(number: str):
    try:
        return parse(number, "BR").national_number

    except NumberParseException as e:
        # TODO: Better error reporting. Should indicate the line on the CSV file.

        logging.error(f"{e}: {number}")
        raise HTTPException(
            status_code=453,
            detail=f"{e}: {number}",
        )


app = FastAPI(
    title="IVR TTS API",
    # version=__version__,
)
origins = ["http://localhost", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



authenticated = auth.authenticated()
csv_writer = auth.authenticated(permissions=['campaing:csv:write'])


@app.get("/me")
async def get_me(
    access_token_info: FiefAccessTokenInfo = Depends(authenticated),
):
    return access_token_info


@app.post("/v1/upload_csv")
async def upload_csv(
    file: UploadFile = File(...),
    access_token_info: FiefAccessTokenInfo = Depends(csv_writer),
):
    columns = [
        "customer_name",
        "condo",
        "unity",
        "phone",
    ]

    engine = create_engine(config.database_url)
    if file.content_type != "text/csv":
        raise HTTPException(
            status_code=415,
            detail=f"Invalid file type. Expected text/csv, got {file.content_type}",
        )

    # read one byte past the limit to tell a full-size file from a bigger one
    contents = file.file.read(config.restapi_max_upload_size + 1)
    if len(contents) > config.restapi_max_upload_size:
        file.file.close()
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {config.restapi_max_upload_size} bytes",
        )
    data = BytesIO(contents)

    try:

        for df in pd.read_csv(
            data,
            names=columns,
            chunksize=1000,
            converters={"phone": phone_parser, **dict.fromkeys(TEXT_COLUMNS, clean_text)},
        ):
            logging.debug(f"Importing {len(df)} rows from {file.filename}")
            try:
                df.to_sql(
                    "big_table_input",
                    engine,
                    index=False,
                    if_exists="append",  # if the table already exists, append this data
                )
            except Exception:
                # details stay in the log: they may expose schema or connection data
                logging.exception("Error while uploading CSV to database")
                data.close()
                file.file.close()
                raise HTTPException(
                    status_code=452,
                    detail="Error while uploading CSV to database",
                )

    except NumberParseException as e:
        logging.error(f"{e}")
        raise HTTPException(status_code=453, detail=f"{e}")

    data.close()
    file.file.close()

    return {"loaded": file.filename, "size": file.size}

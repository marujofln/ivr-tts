from greenlet import getcurrent
from sqlalchemy import JSON, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, mapped_column, scoped_session, sessionmaker
from settings import config

engine = create_engine(config.database_url, pool_pre_ping=True)

# One session per greenlet, as each ESL outbound call runs in its own greenlet
Session = scoped_session(sessionmaker(bind=engine), scopefunc=getcurrent)


class Base(DeclarativeBase):
    pass


Base.query = Session.query_property()


class BigTableOutput(Base):
    __tablename__ = "big_table_output"

    id = mapped_column(Integer, primary_key=True)
    customer_name = mapped_column(String(80), unique=False, nullable=False)
    condo = mapped_column(String(100))
    unity = mapped_column(String(100))
    phone = mapped_column(String(20))
    email = mapped_column(String(40))
    call_uuid = mapped_column(String(36))
    responses = mapped_column(JSON())


class BigTableInput(Base):
    __tablename__ = "big_table_input"

    id = mapped_column(Integer, primary_key=True)
    customer_name = mapped_column(String(80), unique=False, nullable=False)
    condo = mapped_column(String(100))
    unity = mapped_column(String(100))
    phone = mapped_column(String(20))
    email = mapped_column(String(40))
    job_uuid = mapped_column(String(36))
    job_status = mapped_column(String(40))
    call_uuid = mapped_column(String(36))
    hangup_cause = mapped_column(String(40))
    sip_failure_phrase = mapped_column(String(100))
    sip_failure_status = mapped_column(Integer())
    time_start = mapped_column(DateTime(timezone=True))


if __name__ == "__main__":
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

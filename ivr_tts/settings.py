from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='etc/.env',
        env_file_encoding='utf-8',
    )

    freeswitch_host: str = 'localhost'
    freeswitch_port: int = 8021
    freeswitch_password: str = 'ClueCon'
    freeswitch_recording_path: str = '/var/lib/freeswitch/recordings'
    freeswitch_listen_loop: float = 0.7
    freeswitch_keep_connected: int = 2
    freeswitch_connection_max_retry: int = 0
    freeswitch_connection_wait_retry: int = 3

    restapi_host: str = '0.0.0.0'
    restapi_port: int = 8000
    restapi_max_upload_size: int = 10 * 1024 * 1024  # bytes

    fief_base_url: str = 'https://auth.example.com'
    fief_authorize_path: str = '/authorize'
    fief_token_path: str = '/api/token'
    fief_client_id: str
    fief_client_secret: str

    dialer_domain: str
    dialer_dialplan_context: str
    dialer_dialplan_dst: str
    dialer_max_concurrent_calls: int = 10
    dialer_job_wait_time: int = 10
    dialer_callerid_number: str = '0000'
    dialer_callerid_name: str = 'IVR TTS Dialer'

    ivr_bind_address: str = '0.0.0.0'
    ivr_bind_port: int = 5000
    # Comma-separated IPs allowed to open an outbound ESL session; '*' allows any
    ivr_allowed_peers: str = '127.0.0.1'
    ivr_company_name: str = 'Example Company'
    # Contact phone as it must be spoken by the TTS engine
    ivr_contact_phone: str = 'zero oitocentos, zero zero zero, zero zero zero zero'

    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_user: str = 'ivr_tts'
    postgres_password: str = ''
    postgres_database: str = 'ivr_tts'
    # When set, overrides the postgres_* settings above
    database_url: str = ''

    @model_validator(mode='after')
    def build_database_url(self):
        if not self.database_url:
            self.database_url = URL.create(
                'postgresql+psycopg2',
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_database,
            ).render_as_string(hide_password=False)
        return self


config = Settings()

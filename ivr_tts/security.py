from fastapi.security import OAuth2AuthorizationCodeBearer
from fief_client import FiefAsync
from fief_client.integrations.fastapi import FiefAuth
from settings import config

fief = FiefAsync(config.fief_base_url, config.fief_client_id, config.fief_client_secret)

scheme = OAuth2AuthorizationCodeBearer(
    config.fief_base_url + config.fief_authorize_path,
    config.fief_base_url + config.fief_token_path,
    scopes={'openid': 'openid'},
)

auth = FiefAuth(fief, scheme)

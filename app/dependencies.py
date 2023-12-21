from functools import lru_cache

from app.utils.config import Settings
from app.utils.network import Network


@lru_cache
def get_settings():
    return Settings()


@lru_cache
def get_network():
    return Network()

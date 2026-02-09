import os
from typing import Optional


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


IG_USERNAME: Optional[str] = os.getenv("IG_USERNAME")
IG_PASSWORD: Optional[str] = os.getenv("IG_PASSWORD")

REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
REDIS_SENTINEL_HOSTS = os.getenv("REDIS_SENTINEL_HOSTS", "")
REDIS_SENTINEL_MASTER = os.getenv("REDIS_SENTINEL_MASTER", "mymaster")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

IG_SESSION_REFRESH_HOURS = _int_env("IG_SESSION_REFRESH_HOURS", 12)
IG_LOGIN_TIMEOUT_SEC = _int_env("IG_LOGIN_TIMEOUT_SEC", 30)

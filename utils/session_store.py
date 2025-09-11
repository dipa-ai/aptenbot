import json
from typing import Optional
from redis.asyncio.client import Redis
from utils.settings import IG_SESSION_REFRESH_HOURS

SESSION_KEY = "ig:session:{username}"
LOCK_KEY = "ig:session:lock"
TTL = IG_SESSION_REFRESH_HOURS * 3600 + 1800


class IgSessionStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_session(self, username: str) -> Optional[dict]:
        raw = await self.redis.get(SESSION_KEY.format(username=username))
        if raw is None:
            return None
        return json.loads(raw)

    async def save_session(self, username: str, data: dict) -> None:
        await self.redis.set(
            SESSION_KEY.format(username=username),
            json.dumps(data),
            ex=TTL,
        )

    async def touch(self, username: str) -> None:
        await self.redis.expire(SESSION_KEY.format(username=username), TTL)

    async def acquire_lock(self):
        lock = self.redis.lock(LOCK_KEY, timeout=300)
        await lock.acquire()
        return lock

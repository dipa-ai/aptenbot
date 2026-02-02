from redis.asyncio import Redis
from redis.asyncio.sentinel import Sentinel
from typing import List, Tuple, Optional
from utils.settings import (
    REDIS_URL,
    REDIS_SENTINEL_HOSTS,
    REDIS_SENTINEL_MASTER,
    REDIS_PASSWORD,
)


def _parse_hosts() -> List[Tuple[str, int]]:
    hosts = []
    for item in REDIS_SENTINEL_HOSTS.split(','):
        if not item:
            continue
        host, port = item.split(':')
        hosts.append((host, int(port)))
    return hosts


class RedisClient:
    def __init__(self) -> None:
        self._direct_client: Optional[Redis] = None
        self._sentinel: Optional[Sentinel] = None

        if REDIS_URL:
            # Direct connection mode (DragonflyDB, standalone Redis)
            self._direct_client = Redis.from_url(
                REDIS_URL,
                socket_timeout=5,
                decode_responses=False,
            )
        elif REDIS_SENTINEL_HOSTS:
            # Sentinel mode
            self._sentinel = Sentinel(
                _parse_hosts(),
                password=REDIS_PASSWORD,
                socket_timeout=5,
                sentinel_kwargs={"password": REDIS_PASSWORD},
            )
        else:
            raise ValueError("Either REDIS_URL or REDIS_SENTINEL_HOSTS must be set")

    def get_master(self) -> Redis:
        if self._direct_client:
            return self._direct_client
        return self._sentinel.master_for(
            REDIS_SENTINEL_MASTER,
            password=REDIS_PASSWORD,
            socket_timeout=5,
        )

    async def ping(self) -> bool:
        client = self.get_master()
        try:
            pong = await client.ping()
            return pong is True
        finally:
            # Only close if using Sentinel (connection per request)
            if self._sentinel:
                await client.close()

    async def close(self) -> None:
        """Graceful shutdown for direct connection mode."""
        if self._direct_client:
            await self._direct_client.close()

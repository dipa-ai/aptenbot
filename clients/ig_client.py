import asyncio
import httpx
import instaloader
from typing import Any, Dict

from utils.settings import IG_USERNAME, IG_PASSWORD, IG_LOGIN_TIMEOUT_SEC
from utils.session_store import IgSessionStore
from utils.logging_config import logger


class IgClient:
    GRAPHQL_URL = "https://www.instagram.com/graphql/query/"

    def __init__(self, store: IgSessionStore):
        self.store = store
        self.loader = instaloader.Instaloader(
            download_comments=False,
            download_geotags=False,
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False,
        )
        self.context = self.loader.context
        self._loaded = False

    async def ensure_session(self) -> None:
        if self._loaded:
            return
        data = await self.store.get_session(IG_USERNAME)
        if data:
            self.context.load_session_from_dict(IG_USERNAME, data["cookies"])
            await self.store.touch(IG_USERNAME)
            self._loaded = True
            return
        lock = await self.store.acquire_lock()
        try:
            data = await self.store.get_session(IG_USERNAME)
            if data:
                self.context.load_session_from_dict(IG_USERNAME, data["cookies"])
            else:
                await self.login()
        finally:
            await lock.release()
        self._loaded = True

    async def login(self) -> None:
        logger.info("Logging in to Instagram")

        def _login() -> Dict[str, Any]:
            self.loader.login(IG_USERNAME, IG_PASSWORD)
            return self.context.save_session()

        cookies = await asyncio.wait_for(
            asyncio.to_thread(_login), timeout=IG_LOGIN_TIMEOUT_SEC
        )

        session_data = {
            "sessionid": self.context._session.cookies.get("sessionid"),
            "csrftoken": self.context._session.cookies.get("csrftoken"),
            "ds_user_id": self.context._session.cookies.get("ds_user_id"),
            "cookies": cookies,
        }
        await self.store.save_session(IG_USERNAME, session_data)

    async def graphql(self, params: Dict[str, Any]) -> Dict[str, Any]:
        await self.ensure_session()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            client.cookies.update(self.context._session.cookies.get_dict())
            resp = await client.get(self.GRAPHQL_URL, params=params)
            if resp.status_code in (401, 403):
                logger.warning("Received %s from Instagram", resp.status_code)
                await self.store.redis.delete(
                    f"ig:session:{IG_USERNAME}"
                )
                self._loaded = False
                await self.ensure_session()
                resp = await client.get(self.GRAPHQL_URL, params=params)
            await self.store.touch(IG_USERNAME)
            resp.raise_for_status()
            return resp.json()

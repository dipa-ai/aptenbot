import os
import json
import re
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from utils.logging_config import logger
from utils.redis_client import RedisClient
import requests
import time
from urllib.parse import urlparse

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
CHALLENGE_CODE = os.getenv("IG_CHALLENGE_CODE")
IG_PROXY_URL = os.getenv("IG_PROXY_URL")  # Format: http://user:pass@host:port or socks5://host:port
REDIS_IG_SESSION_KEY = "instagrapi:session"

class InstagrapiClient:
    def __init__(self) -> None:
        self.client = Client()
        self._logged_in = False
        self.redis_client = RedisClient()

        # Set proxy if provided
        if IG_PROXY_URL:
            logger.info(f"Using Instagram proxy: {IG_PROXY_URL.split('@')[-1] if '@' in IG_PROXY_URL else IG_PROXY_URL}")
            self.client.set_proxy(IG_PROXY_URL)

        self._ensure_login()

    def _pick_best_video_url(self, video_versions: list[dict]) -> str | None:
        if not video_versions:
            return None
        try:
            # Prefer highest bandwidth
            best = max(video_versions, key=lambda v: v.get("bandwidth", 0))
            return best.get("url")
        except Exception:
            return video_versions[0].get("url")

    def _download_url_with_retries(
        self,
        url: str,
        folder: str = "/tmp",
        filename: str | None = None,
        max_attempts: int = 3,
        timeout_seconds: int = 30,
        backoff_seconds: float = 0.8,
    ) -> Path:
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)
        if filename:
            target = folder_path / filename
        else:
            parsed = urlparse(url)
            name = Path(parsed.path).name or f"ig_{int(time.time())}.mp4"
            if not name.endswith(".mp4"):
                name = f"{name}.mp4"
            target = folder_path / name

        last_err: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                with requests.get(url, stream=True, timeout=timeout_seconds) as r:
                    r.raise_for_status()
                    with open(target, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                return target
            except Exception as e:
                last_err = e
                if attempt < max_attempts:
                    sleep_time = backoff_seconds * (2 ** (attempt - 1))
                    logger.debug(f"Retrying CDN download in {sleep_time:.1f}s due to error: {e}")
                    time.sleep(sleep_time)
        # If all attempts failed, raise
        raise last_err if last_err else Exception("Unknown download error")

    def _download_video_via_private_api(self, media_pk: str, retry_login: bool = True) -> tuple[bool, str]:
        try:
            data = self.client.private_request(f"media/{media_pk}/info/")
            items = data.get("items") or []
            if not items:
                return False, "No media items found."
            item = items[0]

            media_type = item.get("media_type")
            if media_type == 2:  # Video/Reel
                video_url = self._pick_best_video_url(item.get("video_versions", []))
                if video_url:
                    # Try SDK downloader first, then resilient HTTP fallback
                    try:
                        path = self.client.video_download_by_url(video_url, folder="/tmp")
                        return True, str(path)
                    except Exception as _:
                        path = self._download_url_with_retries(
                            video_url,
                            folder="/tmp",
                            filename=f"ig_{media_pk}.mp4",
                        )
                        return True, str(path)
            elif media_type == 8:  # Carousel
                for res in item.get("carousel_media", []):
                    if res.get("media_type") == 2:
                        video_url = self._pick_best_video_url(res.get("video_versions", []))
                        if video_url:
                            try:
                                path = self.client.video_download_by_url(video_url, folder="/tmp")
                                return True, str(path)
                            except Exception as _:
                                path = self._download_url_with_retries(
                                    video_url,
                                    folder="/tmp",
                                    filename=f"ig_{media_pk}.mp4",
                                )
                                return True, str(path)
            return False, "No downloadable video found in media."
        except LoginRequired as login_err:
            if retry_login:
                logger.warning(f"Login required during private API call: {login_err}. Re-authenticating.")
                self._ensure_login(force_relogin=True)
                return self._download_video_via_private_api(media_pk, retry_login=False)
            return False, "Instagram session expired and re-login failed."
        except Exception as e:
            # Check if error message indicates login issue
            err_str = str(e).lower()
            if ("login" in err_str or "403" in err_str or "401" in err_str) and retry_login:
                logger.warning(f"Possible auth error in private API: {e}. Re-authenticating.")
                self._ensure_login(force_relogin=True)
                return self._download_video_via_private_api(media_pk, retry_login=False)
            return False, f"Private API fallback failed: {e}"

    def _challenge_code_handler(self, username: str, choice: str) -> str:
        if CHALLENGE_CODE:
            logger.info("Using IG_CHALLENGE_CODE from environment for challenge.")
            return CHALLENGE_CODE
        raise Exception(
            "Instagram requires a verification code (checkpoint). Set IG_CHALLENGE_CODE env var and retry."
        )

    async def _load_session_from_redis(self) -> bool:
        """Load Instagram session from Redis."""
        try:
            redis = self.redis_client.get_master()
            session_json = await redis.get(REDIS_IG_SESSION_KEY)
            await redis.close()
            
            if session_json:
                settings = json.loads(session_json)
                self.client.set_settings(settings)
                logger.info("Loaded Instagram session from Redis.")
                return True
            return False
        except Exception as e:
            logger.debug(f"Failed to load session from Redis: {e}")
            return False

    async def _save_session_to_redis(self) -> None:
        """Save Instagram session to Redis."""
        try:
            settings = self.client.get_settings()
            redis = self.redis_client.get_master()
            # Session lives for 7 days (Instagram sessions typically valid for ~90 days)
            await redis.setex(REDIS_IG_SESSION_KEY, 7 * 24 * 3600, json.dumps(settings))
            await redis.close()
            logger.info("Saved Instagram session to Redis.")
        except Exception as e:
            logger.warning(f"Failed to save session to Redis: {e}")

    def _ensure_login(self, force_relogin: bool = False) -> None:
        if self._logged_in and not force_relogin:
            return
        if not IG_USERNAME or not IG_PASSWORD:
            logger.warning("IG_USERNAME/IG_PASSWORD not provided; proceeding unauthenticated")
            return
        
        # Reset flag on forced relogin
        if force_relogin:
            self._logged_in = False
            logger.info("Forcing re-login due to expired session.")
        
        try:
            # Try loading session from Redis first
            if not force_relogin:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, create task
                    session_loaded = asyncio.run_coroutine_threadsafe(
                        self._load_session_from_redis(), loop
                    ).result(timeout=5)
                except RuntimeError:
                    # No running loop, create new one
                    session_loaded = asyncio.run(self._load_session_from_redis())
                
                if session_loaded:
                    try:
                        # Verify session works
                        self.client.account_info()
                        self._logged_in = True
                        logger.info("Instagram session restored from Redis and verified.")
                        return
                    except Exception as verify_err:
                        logger.warning(f"Redis session invalid: {verify_err}, performing fresh login.")
            
            # Fresh login
            logger.info("Performing fresh Instagram login.")
            self.client = Client()
            self.client.challenge_code_handler = self._challenge_code_handler
            
            # Set proxy if configured
            if IG_PROXY_URL:
                self.client.set_proxy(IG_PROXY_URL)
            
            self.client.login(IG_USERNAME, IG_PASSWORD)
            self._logged_in = True
            logger.info("Fresh Instagram login successful.")
            
            # Save to Redis
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    self._save_session_to_redis(), loop
                ).result(timeout=5)
            except RuntimeError:
                asyncio.run(self._save_session_to_redis())
            
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")

    def _try_public_download(self, url: str) -> tuple[bool, str]:
        """
        Try downloading video without authentication by parsing public HTML.
        Works for public posts only.
        """
        try:
            logger.info(f"Attempting public (no-auth) download for: {url}")
            
            # Resolve redirects first
            response = requests.get(url, allow_redirects=True, timeout=15)
            resolved_url = response.url
            html = response.text
            
            # Extract video URL from HTML using regex
            # Instagram embeds video URLs in <script> tags as JSON
            patterns = [
                r'"video_url":"([^"]+)"',
                r'"playback_url":"([^"]+)"',
                r'<meta property="og:video" content="([^"]+)"',
                r'"video_versions":\[{"url":"([^"]+)"',
            ]
            
            video_url = None
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    video_url = match.group(1)
                    # Unescape unicode
                    video_url = video_url.encode().decode('unicode_escape')
                    break
            
            if not video_url:
                logger.debug("Could not extract video URL from public HTML.")
                return False, "Public download failed: no video URL found"
            
            logger.info(f"Found public video URL, downloading...")
            
            # Download directly
            path = self._download_url_with_retries(
                video_url,
                folder="/tmp",
                filename=f"ig_public_{int(time.time())}.mp4",
            )
            return True, str(path)
            
        except Exception as e:
            logger.debug(f"Public download failed: {e}")
            return False, f"Public download failed: {e}"

    def download_video(self, url: str, retry_on_auth_fail: bool = True) -> tuple[bool, str]:
        # Try public download first (no auth required) - works for most public posts
        if not IG_PROXY_URL:
            logger.info("No proxy configured, trying public download first...")
            success, result = self._try_public_download(url)
            if success:
                logger.info("Public download successful!")
                return True, result
            logger.info(f"Public download failed, falling back to authenticated method: {result}")
        
        try:
            self._ensure_login()
            # Resolve Instagram share/redirect URLs to canonical media URL
            try:
                response = requests.get(url, allow_redirects=True, timeout=15)
                resolved_url = response.url
                if resolved_url != url:
                    logger.debug(f"Resolved Instagram URL: {url} -> {resolved_url}")
            except Exception as resolve_err:
                logger.debug(f"Failed to resolve URL redirects, proceeding with original URL: {resolve_err}")
                resolved_url = url

            # Obtain media PK from URL, then fetch media info
            media_pk = self.client.media_pk_from_url(resolved_url)
            try:
                media_info = self.client.media_info(media_pk)
            except LoginRequired as login_err:
                if retry_on_auth_fail:
                    logger.warning(f"Login required during media_info: {login_err}. Re-authenticating.")
                    self._ensure_login(force_relogin=True)
                    return self.download_video(url, retry_on_auth_fail=False)
                return False, "Instagram session expired and re-login failed."
            except Exception as parse_err:
                err_str = str(parse_err).lower()
                if ("login" in err_str or "403" in err_str or "401" in err_str) and retry_on_auth_fail:
                    logger.warning(f"Possible auth error in media_info: {parse_err}. Re-authenticating.")
                    self._ensure_login(force_relogin=True)
                    return self.download_video(url, retry_on_auth_fail=False)
                logger.warning(f"media_info parse failed, using private API fallback: {parse_err}")
                return self._download_video_via_private_api(media_pk)

            video_pk_to_download = None
            if media_info.media_type == 2:  # Video
                video_pk_to_download = media_info.pk
            elif media_info.media_type == 8:  # Carousel
                for resource in media_info.resources:
                    if resource.media_type == 2:
                        # Prefer direct download by URL for carousel resources
                        if getattr(resource, "video_url", None):
                            try:
                                path = self.client.video_download_by_url(resource.video_url, folder="/tmp")
                                return True, str(path)
                            except Exception:
                                path = self._download_url_with_retries(resource.video_url, folder="/tmp")
                                return True, str(path)
                        # Fallback: if resource PK works with video_download (depends on instagrapi version)
                        video_pk_to_download = getattr(resource, "pk", None)
                        break  # download first video in carousel

            if video_pk_to_download:
                try:
                    path = self.client.video_download(video_pk_to_download, folder="/tmp")
                    return True, str(path)
                except Exception:
                    # As a last resort, re-fetch via private API and download by URL
                    ok, p = self._download_video_via_private_api(str(video_pk_to_download))
                    if ok:
                        return True, p
                    else:
                        return False, p
            else:
                return False, "No video found in the post."

        except LoginRequired as login_err:
            if retry_on_auth_fail:
                logger.warning(f"Login required during download_video: {login_err}. Re-authenticating.")
                self._ensure_login(force_relogin=True)
                return self.download_video(url, retry_on_auth_fail=False)
            return False, "Instagram session expired and re-login failed."
        except Exception as e:
            err_str = str(e).lower()
            if ("login" in err_str or "403" in err_str or "401" in err_str) and retry_on_auth_fail:
                logger.warning(f"Possible auth error in download_video: {e}. Re-authenticating.")
                self._ensure_login(force_relogin=True)
                return self.download_video(url, retry_on_auth_fail=False)
            logger.error(f"Instagrapi video download failed: {e}")
            return False, str(e)

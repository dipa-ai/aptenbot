import os
import instaloader
from utils.logging_config import logger
from pathlib import Path

# Read credentials from environment to avoid import-time dependency on settings.py in Docker
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
SESSION_FILE_ENV = os.getenv("INSTALOADER_SESSION_FILE")
IG_SESSIONID = os.getenv("IG_SESSIONID")
IG_CSRFTOKEN = os.getenv("IG_CSRFTOKEN")
IG_DS_USER_ID = os.getenv("IG_DS_USER_ID")

# Optional Redis-backed session store
try:
    from utils.redis_client import RedisClient  # lazy optional import
    from utils.session_store import IgSessionStore
    _HAS_REDIS = True
except Exception:
    _HAS_REDIS = False

class InstaloaderClient:
    def __init__(self):
        self.loader = instaloader.Instaloader(
            download_comments=False,
            download_geotags=False,
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False
        )
        self._logged_in = False
        # Prefer user-provided session file if set, otherwise fallback to project-local
        if SESSION_FILE_ENV:
            self._session_file = SESSION_FILE_ENV
        else:
            self._session_file = f".instaloader_session_{IG_USERNAME}" if IG_USERNAME else None
        # Try to load cookies from Redis or environment (no interactive login required)
        self._try_load_redis_cookies()
        self._try_load_env_cookies()
        # Do NOT auto-login on startup; defer until needed to avoid crashing the bot

    def _apply_cookies_to_context(self, cookies: dict) -> None:
        try:
            jar = self.loader.context._session.cookies
            for name, value in cookies.items():
                if value is None:
                    continue
                jar.set(name, value, domain=".instagram.com", path="/")
            self._logged_in = True
        except Exception as e:
            logger.warning(f"Failed to apply cookies to Instaloader context: {e}")

    def _try_load_redis_cookies(self) -> None:
        if not _HAS_REDIS or not IG_USERNAME:
            return
        try:
            redis = RedisClient().get_master()
            store = IgSessionStore(redis)
            # IgSessionStore stores a dict with keys: sessionid, csrftoken, ds_user_id, cookies
            # We prefer explicit cookie values and fallback to cookies dict
            import asyncio
            async def _fetch():
                return await store.get_session(IG_USERNAME)
            data = asyncio.get_event_loop().run_until_complete(_fetch())
            if data and isinstance(data, dict):
                cookies = {
                    "sessionid": data.get("sessionid"),
                    "csrftoken": data.get("csrftoken"),
                    "ds_user_id": data.get("ds_user_id"),
                }
                # If full cookies dict is present, merge
                if isinstance(data.get("cookies"), dict):
                    cookies.update(data["cookies"])
                self._apply_cookies_to_context(cookies)
                if self._logged_in:
                    logger.info("Loaded Instagram cookies from Redis session store. Skipping login.")
        except Exception as e:
            logger.warning(f"Failed to load IG cookies from Redis: {e}")

    def _try_load_env_cookies(self) -> None:
        if IG_SESSIONID:
            try:
                cookies = {
                    "sessionid": IG_SESSIONID,
                    "csrftoken": IG_CSRFTOKEN,
                    "ds_user_id": IG_DS_USER_ID,
                }
                self._apply_cookies_to_context(cookies)
                if self._logged_in:
                    logger.info("Loaded Instagram cookies from environment. Skipping login.")
            except Exception as e:
                logger.warning(f"Failed to apply IG cookies from env: {e}")

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        if not IG_USERNAME or not IG_PASSWORD:
            logger.warning("IG credentials are not set (IG_USERNAME/IG_PASSWORD). Proceeding unauthenticated.")
            return
        # Try to load a persisted session first
        try:
            if self._session_file and Path(self._session_file).exists():
                logger.info(f"Loading Instagram session from file: {self._session_file}")
                self.loader.load_session_from_file(IG_USERNAME, filename=self._session_file)
                self._logged_in = True
                return
            else:
                # Try default session file path used by Instaloader CLI
                try:
                    logger.info("Trying to load default Instaloader session file")
                    self.loader.load_session_from_file(IG_USERNAME)
                    self._logged_in = True
                    return
                except Exception as e2:
                    logger.info(f"Default session load failed, will try fresh login: {e2}")
        except Exception as e:
            logger.warning(f"Failed to load saved IG session file, will try login: {e}")
        # Fallback to fresh login
        logger.info("Logging in to Instagram via Instaloader")
        self.loader.login(IG_USERNAME, IG_PASSWORD)
        # Persist session to file for reuse
        try:
            if self._session_file:
                self.loader.save_session_to_file(filename=self._session_file)
                logger.info(f"Saved Instagram session to file: {self._session_file}")
        except Exception as e:
            logger.warning(f"Failed to save IG session file: {e}")
        self._logged_in = True

    def download_video(self, url: str) -> tuple[bool, str]:
        if not url:
            return False, "Invalid URL provided"

        # Ensure we are authenticated before attempting to access post data
        try:
            self._ensure_login()
        except Exception as e:
            # If a checkpoint is required or any login-side error occurs, surface a friendly message
            msg = str(e)
            if "Checkpoint required" in msg:
                logger.error(f"Instagram checkpoint required: {msg}")
                import re
                match = re.search(r"https://www\.instagram\.com/challenge/\S+", msg)
                if match:
                    url_hint = f"Open this URL in a browser and retry: {match.group(0)}"
                else:
                    url_hint = "Open the challenge URL from logs in a browser and retry."
                return False, (
                    "Instagram requires verification (checkpoint). "
                    f"{url_hint}"
                )
            logger.warning(f"Proceeding without IG login due to error: {e}")

        def _do_download() -> tuple[bool, str]:
            shortcode = url.split('/')[-2]
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            if not post.is_video:
                return False, "This post does not contain a video"

            video_url = post.video_url
            extension = video_url.split('?')[0].split('.')[-1] if video_url else 'mp4'
            filename = f"{shortcode}/{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S')}_UTC.{extension}"

            logger.info(f"Downloading video to {filename}")
            self.loader.download_post(post, target=shortcode)

            if os.path.exists(filename):
                return True, filename
            else:
                return False, "no file exists"

        try:
            return _do_download()
        except Exception as e:
            msg = str(e)
            logger.warning(f"Download failed on first attempt: {msg}")
            if any(err in msg for err in ["401", "403", "Please wait a few minutes", "Checkpoint required"]):
                # Clear persisted session and re-login once
                try:
                    if self._session_file and Path(self._session_file).exists():
                        Path(self._session_file).unlink(missing_ok=True)
                        logger.info("Removed stale IG session file. Re-authenticating...")
                except Exception as del_err:
                    logger.warning(f"Failed to remove session file: {del_err}")
                self._logged_in = False
                try:
                    # Try Redis/env cookies again before login
                    self._try_load_redis_cookies()
                    self._try_load_env_cookies()
                    if not self._logged_in:
                        self._ensure_login()
                    return _do_download()
                except Exception as e2:
                    if "Checkpoint required" in str(e2):
                        return False, (
                            "Instagram requires verification (checkpoint). "
                            "Open the challenge URL from logs in a browser, complete the steps, and retry."
                        )
                    logger.error(f"Retry after re-login failed: {e2}")
                    return False, f"Failed to download video after re-login: {e2}"
            logger.error(f'Something went wrong while downloading video: {e}')
            return False, f"Failed to download video: {msg}"

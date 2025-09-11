import os
import asyncio
from pathlib import Path
import instaloader
from instaloader.exceptions import BadCredentialsException, CheckpointRequiredException, TwoFactorAuthRequiredException
from utils.logging_config import logger

# Read credentials from environment
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

class InstaloaderClient:
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.loader = instaloader.Instaloader(
            download_comments=False,
            download_geotags=False,
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False,
        )
        self._session_file = f"/tmp/instaloader_session_{IG_USERNAME}" if IG_USERNAME else None
        self._logged_in = False

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.login()
        return cls._instance

    async def login(self, force_relogin=False):
        if self._logged_in and not force_relogin:
            return

        if not IG_USERNAME or not IG_PASSWORD:
            logger.warning("Instagram credentials (IG_USERNAME, IG_PASSWORD) are not set. Proceeding unauthenticated.")
            return

        if force_relogin and self._session_file and Path(self._session_file).exists():
            logger.info(f"Forcing re-login. Removing existing session file: {self._session_file}")
            Path(self._session_file).unlink()

        try:
            if self._session_file and Path(self._session_file).exists():
                logger.info(f"Attempting to load Instagram session from file: {self._session_file}")
                await asyncio.to_thread(self.loader.load_session_from_file, IG_USERNAME, self._session_file)
                logger.info("Session loaded successfully.")
            else:
                raise FileNotFoundError("Session file not found.")
        except (FileNotFoundError, BadCredentialsException) as e:
            logger.info(f"Could not load session ({e}). Performing fresh login to Instagram.")
            try:
                await asyncio.to_thread(self.loader.login, IG_USERNAME, IG_PASSWORD)
                logger.info("Login successful.")
                if self._session_file:
                    logger.info(f"Saving new session to file: {self._session_file}")
                    await asyncio.to_thread(self.loader.save_session_to_file, self._session_file)
            except (BadCredentialsException, CheckpointRequiredException, TwoFactorAuthRequiredException) as auth_err:
                logger.error(f"Instagram login failed: {auth_err}")
                raise auth_err  # Re-raise to be caught by the caller

        self._logged_in = True

    async def download_video(self, url: str) -> tuple[bool, str]:
        if not url:
            return False, "Invalid URL provided"

        for attempt in range(2):
            try:
                # The first time, use the existing session. If it fails, force re-login on the second attempt.
                if attempt > 0:
                    logger.info("Download failed. Forcing re-login and retrying.")
                    await self.login(force_relogin=True)

                return await self._do_download(url)

            except (BadCredentialsException, CheckpointRequiredException) as auth_err:
                logger.warning(f"Authentication error on attempt {attempt + 1}: {auth_err}")
                if attempt == 1: # If it still fails after re-login
                    return False, f"Instagram authentication failed after retry: {auth_err}"
            except Exception as e:
                logger.error(f"An unexpected error occurred during download: {e}")
                return False, f"An unexpected error occurred: {e}"
        
        return False, "Failed to download video after multiple attempts."


    async def _do_download(self, url: str) -> tuple[bool, str]:
        def download_sync():
            shortcode = url.split('/')[-2]
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)

            if not post.is_video:
                return False, "This post does not contain a video."

            # Create a unique directory for the download
            target_dir = Path(f"/tmp/{shortcode}")
            target_dir.mkdir(exist_ok=True)

            # Download the post
            self.loader.download_post(post, target=target_dir)

            # Find the video file
            for file in target_dir.iterdir():
                if file.suffix in ['.mp4', '.mov', '.avi']:
                    return True, str(file)
            
            return False, "Downloaded post, but no video file was found."

        try:
            return await asyncio.to_thread(download_sync)
        except Exception as e:
            logger.error(f"Core download operation failed: {e}")
            # Propagate specific exceptions to be handled by the retry logic
            if "401" in str(e) or "403" in str(e) or "Bad credentials" in str(e):
                raise BadCredentialsException(str(e))
            if "checkpoint" in str(e).lower():
                raise CheckpointRequiredException(str(e))
            raise e

# Keep a single client instance to be used by the application
async def get_instaloader_client():
    return await InstaloaderClient.get_instance()
import os
import instaloader
from utils.logging_config import logger
from pathlib import Path
import asyncio

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

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
        self._session_file = f"/tmp/instaloader_session_{IG_USERNAME}" if IG_USERNAME else None

    def _ensure_login(self) -> None:
        if self._logged_in:
            return

        if not IG_USERNAME or not IG_PASSWORD:
            logger.warning("Instagram credentials not set. Proceeding without authentication.")
            return

        if self._session_file and Path(self._session_file).exists():
            try:
                logger.info(f"Loading Instagram session from {self._session_file}")
                self.loader.load_session_from_file(IG_USERNAME, self._session_file)
                self._logged_in = True
                logger.info("Instagram session loaded successfully.")
                return
            except Exception as e:
                logger.warning(f"Could not load session file: {e}. Creating a new one.")

        try:
            logger.info("Logging in to Instagram...")
            self.loader.login(IG_USERNAME, IG_PASSWORD)
            if self._session_file:
                self.loader.save_session_to_file(self._session_file)
                logger.info(f"Saved Instagram session to {self._session_file}")
            self._logged_in = True
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")
            # If login fails, we proceed without being logged in
            self._logged_in = False

    async def download_video(self, url: str) -> tuple[bool, str]:
        if not url:
            return False, "Invalid URL provided"

        await asyncio.to_thread(self._ensure_login)

        if not self._logged_in:
            return False, "Could not log in to Instagram. Please check credentials."

        def _do_download() -> tuple[bool, str]:
            try:
                shortcode = url.split('/')[-2]
                post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
                
                if not post.is_video:
                    return False, "This post does not contain a video."

                target_dir = Path(f"/tmp/{shortcode}")
                target_dir.mkdir(exist_ok=True)

                self.loader.download_post(post, target=target_dir)

                for file in target_dir.iterdir():
                    if file.suffix in ['.mp4', '.mov', '.avi']:
                        return True, str(file)
                
                return False, "Downloaded post, but no video file was found."
            except instaloader.exceptions.InstaloaderException as e:
                logger.error(f"Instaloader error: {e}")
                return False, f"Failed to download video: {e}"
            except Exception as e:
                logger.error(f"An unexpected error occurred during download: {e}")
                return False, f"An unexpected error occurred: {e}"

        return await asyncio.to_thread(_do_download)
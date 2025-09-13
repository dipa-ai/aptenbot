import os
from pathlib import Path
from instagrapi import Client
from utils.logging_config import logger
import requests

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
SESSION_FILE = os.getenv("INSTAGRAPI_SESSION_FILE", "/tmp/instagrapi_session.json")
CHALLENGE_CODE = os.getenv("IG_CHALLENGE_CODE")

class InstagrapiClient:
    def __init__(self) -> None:
        self.client = Client()
        self._logged_in = False
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

    def _download_video_via_private_api(self, media_pk: str) -> tuple[bool, str]:
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
                    path = self.client.video_download_by_url(video_url, folder="/tmp")
                    return True, str(path)
            elif media_type == 8:  # Carousel
                for res in item.get("carousel_media", []):
                    if res.get("media_type") == 2:
                        video_url = self._pick_best_video_url(res.get("video_versions", []))
                        if video_url:
                            path = self.client.video_download_by_url(video_url, folder="/tmp")
                            return True, str(path)
            return False, "No downloadable video found in media."
        except Exception as e:
            return False, f"Private API fallback failed: {e}"

    def _challenge_code_handler(self, username: str, choice: str) -> str:
        if CHALLENGE_CODE:
            logger.info("Using IG_CHALLENGE_CODE from environment for challenge.")
            return CHALLENGE_CODE
        raise Exception(
            "Instagram requires a verification code (checkpoint). Set IG_CHALLENGE_CODE env var and retry."
        )

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        if not IG_USERNAME or not IG_PASSWORD:
            logger.warning("IG_USERNAME/IG_PASSWORD not provided; proceeding unauthenticated")
            return
        try:
            session_path = Path(SESSION_FILE)
            if session_path.exists():
                logger.info(f"Loading Instagrapi session from {SESSION_FILE}")
                self.client.load_settings(session_path)
                self.client.login(IG_USERNAME, IG_PASSWORD)
                logger.info("Instagram login successful using session.")
            else:
                logger.info("Session file not found, performing fresh login.")
                self.client.challenge_code_handler = self._challenge_code_handler
                self.client.login(IG_USERNAME, IG_PASSWORD)
                session_path.parent.mkdir(parents=True, exist_ok=True)
                self.client.dump_settings(SESSION_FILE)
                logger.info("Fresh Instagram login successful and session saved.")
            self._logged_in = True
        except Exception as e:
            logger.warning(f"Instagram login with session failed: {e}. Attempting fresh login.")
            try:
                self.client = Client()
                self.client.challenge_code_handler = self._challenge_code_handler
                self.client.login(IG_USERNAME, IG_PASSWORD)
                session_path = Path(SESSION_FILE)
                session_path.parent.mkdir(parents=True, exist_ok=True)
                self.client.dump_settings(SESSION_FILE)
                self._logged_in = True
                logger.info("Fresh Instagram login successful after session failure.")
            except Exception as e2:
                logger.error(f"Instagram fresh login failed: {e2}")

    def download_video(self, url: str) -> tuple[bool, str]:
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
            except Exception as parse_err:
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
                            path = self.client.video_download_by_url(resource.video_url, folder="/tmp")
                            return True, str(path)
                        # Fallback: if resource PK works with video_download (depends on instagrapi version)
                        video_pk_to_download = getattr(resource, "pk", None)
                        break  # download first video in carousel

            if video_pk_to_download:
                path = self.client.video_download(video_pk_to_download, folder="/tmp")
                return True, str(path)
            else:
                return False, "No video found in the post."

        except Exception as e:
            logger.error(f"Instagrapi video download failed: {e}")
            return False, str(e)

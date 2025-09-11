from utils.logging_config import logger
from .instaloader import get_instaloader_client

class IgClient:
    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = await get_instaloader_client()
        return self._client

    async def download_video(self, url: str) -> tuple[bool, str]:
        """
        Downloads an Instagram video from the given URL.

        Args:
            url: The URL of the Instagram post.

        Returns:
            A tuple containing a boolean indicating success and a string with the file path or error message.
        """
        logger.info(f"Received request to download Instagram video: {url}")
        try:
            client = await self._get_client()
            success, result = await client.download_video(url)
            if success:
                logger.info(f"Successfully downloaded video to: {result}")
            else:
                logger.error(f"Failed to download video: {result}")
            return success, result
        except Exception as e:
            logger.critical(f"An unexpected error occurred in IgClient: {e}")
            return False, f"An unexpected critical error occurred: {e}"
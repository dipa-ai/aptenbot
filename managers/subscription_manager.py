from utils.logging_config import logger
from config import CHANNEL_IDS, CHANNEL_USER_ID

class SubscriptionManager:
    @staticmethod
    async def is_subscriber(user_id: int, bot) -> bool:
        logger.info(f"Checking subscription status for user: {user_id}")
        try:
            # Check if the user is posting on behalf of the channel
            if user_id == int(CHANNEL_USER_ID):
                logger.info("Message sent on behalf of a channel, considering as subscribed")
                return True

            # Check if user is a member of ANY of the configured channels
            for channel_id in CHANNEL_IDS:
                try:
                    member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                    logger.info(f"Member status in {channel_id}: {member.status}")
                    if member.status in ['member', 'administrator', 'creator']:
                        logger.info(f"User {user_id} is subscribed to {channel_id}")
                        return True
                except Exception as e:
                    logger.warning(f"Error checking subscription for channel {channel_id}: {e}")
                    continue
            
            logger.info(f"User {user_id} is not subscribed to any of the required channels")
            return False
        except Exception as e:
            logger.error(f"Error checking subscription status: {e}")
            return False

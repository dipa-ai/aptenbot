from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from utils.logging_config import logger
from config import CHANNEL_IDS

import asyncio # For Lock if needed, though simple flag used here
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, subscription_manager):
        self.subscription_manager = subscription_manager
        self.resolved_numeric_channel_ids = {}  # Maps channel_id_str -> resolved numeric ID
        self.resolving_started = False # Simple flag for one-time resolution attempt
        # For scenarios with many concurrent first messages, a Lock might be better:
        # self.resolve_lock = asyncio.Lock()
        super().__init__()

    async def _resolve_channel_ids(self, bot: Bot):
        """Helper to resolve all CHANNEL_IDS to their numeric forms."""
        for channel_id_str in CHANNEL_IDS:
            if channel_id_str in self.resolved_numeric_channel_ids:
                continue  # Already resolved
            
            try:
                # Try to convert to int directly first
                numeric_id = int(channel_id_str)
                self.resolved_numeric_channel_ids[channel_id_str] = numeric_id
                logger.info(f"CHANNEL_ID '{channel_id_str}' is already a numeric ID: {numeric_id}")
            except ValueError:
                # Not a numeric ID, assume it's a username like "@mychannel"
                logger.info(f"CHANNEL_ID '{channel_id_str}' is not numeric, attempting to resolve via bot.get_chat().")
                try:
                    chat_info = await bot.get_chat(chat_id=channel_id_str)
                    self.resolved_numeric_channel_ids[channel_id_str] = chat_info.id
                    logger.info(f"Successfully resolved CHANNEL_ID '{channel_id_str}' to numeric ID: {chat_info.id}")
                except TelegramAPIError as e:
                    logger.error(f"Failed to resolve CHANNEL_ID '{channel_id_str}' via bot.get_chat(): {e}. Bypass for channel messages will not work.")
                    self.resolved_numeric_channel_ids[channel_id_str] = -1  # Explicitly non-matchable
                except Exception as e:
                    logger.error(f"An unexpected error occurred while resolving CHANNEL_ID '{channel_id_str}': {e}. Bypass for channel messages will not work.")
                    self.resolved_numeric_channel_ids[channel_id_str] = -1  # Explicitly non-matchable

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        bot = data.get("bot")
        if bot and not self.resolving_started:
            self.resolving_started = True # Mark that resolution process has started
            # In a high concurrency scenario, self.resolve_lock might be used here
            # async with self.resolve_lock:
            #    if not self.resolving_started: # Double check after acquiring lock
            #        await self._resolve_channel_ids(bot)
            await self._resolve_channel_ids(bot)
            logger.info(f"CHANNEL_IDS resolution attempt finished. Resolved IDs: {self.resolved_numeric_channel_ids}")


        if isinstance(event, Message):
            # Case 1: Message sent by any of the configured CHANNELs (via sender_chat)
            if event.sender_chat:
                sender_chat_id = event.sender_chat.id
                # Check if sender_chat_id matches any resolved channel ID
                for channel_str, resolved_id in self.resolved_numeric_channel_ids.items():
                    if resolved_id is not None and resolved_id != -1 and sender_chat_id == resolved_id:
                        logger.info(f"Message from configured channel '{channel_str}' (ID: {resolved_id}), chat_id={event.chat.id}, sender_chat_id={sender_chat_id}. Bypassing user subscription check.")
                        return await handler(event, data)

            # Case 2: Message from a regular user
            if event.from_user:
                user_id = event.from_user.id
                # logger.info(f"Checking subscription for user_id {user_id} in chat_id {event.chat.id}.") # Can be noisy
                if not await self.subscription_manager.is_subscriber(user_id, data["bot"]):
                    logger.info(f"User {user_id} is not subscribed. Blocking message in chat {event.chat.id}.")
                    try:
                        # Build a user-friendly message with all required channels
                        if len(CHANNEL_IDS) == 1:
                            channel_msg = f"the {CHANNEL_IDS[0]} channel"
                        else:
                            channel_msg = f"one of these channels: {', '.join(CHANNEL_IDS)}"
                        await event.answer(f"To use this bot, you need to be a subscriber of {channel_msg}.")
                    except Exception as e:
                        logger.error(f"Error sending subscription denial message to {user_id}: {e}")
                    return # Block message
                else:
                    logger.debug(f"User {user_id} is subscribed. Allowing message.")
                    # Fall through to return await handler(event, data) at the end

            # Case 3: Other message types (e.g., not from user, not from sender_chat matching resolved channel)
            if not event.from_user and not event.sender_chat:
                logger.debug(f"Message event (type: {type(event)}, chat_id: {event.chat.id}) is not from a specific user or sender_chat. Allowing to pass.")
                # Fall through to return await handler(event, data) at the end

        # Default: Allow event to proceed if none of the above conditions resulted in a return
        return await handler(event, data)

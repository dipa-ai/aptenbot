from aiogram import Router, F
from aiogram.types import Message
from utils.logging_config import logger

router = Router()

@router.message(F.chat.type == "private", F.text)
async def handle_private_message(message: Message, session_manager, openai_client, claude_client, gemini_client, grok_client):
    user_id = message.from_user.id

    user_message = message.text
    logger.info(f"Received message from user: {user_message}")

    session = session_manager.get_or_create_session(user_id)
    model_provider = session_manager.get_model_provider(user_id)

    # Add logging for debugging
    logger.info(f"Using model provider: {model_provider}")

    if model_provider == "anthropic":
        logger.info("Using Anthropic (Claude) client for processing")
        reply = await claude_client.process_message(session, user_message)
    elif model_provider == "gemini":
        logger.info("Using Gemini client for processing")
        reply = await gemini_client.process_message(session, user_message)
    elif model_provider == "grok":
        logger.info("Using Grok client for processing")
        reply = await grok_client.process_message(session, user_message)
    else:
        logger.info("Using OpenAI client for processing")
        reply = await openai_client.process_message(session, user_message)

    await message.reply(reply)

@router.message((F.chat.type == "group") | (F.chat.type == "supergroup"), F.text)
async def handle_group_message(message: Message, session_manager, openai_client, claude_client, gemini_client, grok_client):
    bot_username = (await message.bot.me()).username
    bot_id = (await message.bot.me()).id
    message_text = message.text or "" # Ensure message_text is not None

    # Check if the message is a direct command /ask (processed separately)
    if message_text.startswith("/ask"):
        logger.debug("Ignoring message starting with /ask in group message handler as it's handled by command handler.")
        return

    # --- Check if the bot should process this message based on mention or reply ---
    bot_mentioned = False
    is_reply_to_bot = False

    # Check for @username mention in text
    if f"@{bot_username}" in message_text:
        bot_mentioned = True
        logger.debug(f"Bot mentioned by @{bot_username} in message text.")

    # Check for mention via entities (more reliable for usernames with special chars)
    if not bot_mentioned and message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mentioned_text = message_text[entity.offset : entity.offset + entity.length]
                if mentioned_text == f"@{bot_username}":
                    bot_mentioned = True
                    logger.debug(f"Bot mentioned by entity: {mentioned_text}")
                    break
            elif entity.type == "text_mention" and entity.user and entity.user.id == bot_id:
                # This case handles mentions where the user is explicitly linked without using @username
                # (e.g. user manually creates a text link to the bot)
                bot_mentioned = True
                logger.debug(f"Bot mentioned by text_mention entity for user ID: {bot_id}")
                break

    # Check if this is a reply to a bot message
    if message.reply_to_message and message.reply_to_message.from_user and \
       (message.reply_to_message.from_user.id == bot_id): # Simpler check using only bot_id
        is_reply_to_bot = True
        logger.debug(f"Message is a reply to the bot (bot ID: {bot_id}).")

    # If the bot is neither mentioned nor is the message a reply to the bot, ignore the message.
    if not bot_mentioned and not is_reply_to_bot:
        logger.debug("Ignoring group message: Not a mention and not a reply to the bot.")
        return
    # --- End Check ---

    # If we reach here, the bot should process the message.
    user_id = message.from_user.id # User who sent the message
    user_message = message_text # Start with the full text

    # If the bot was mentioned, remove the mention for cleaner processing
    if bot_mentioned:
        # Attempt to remove all occurrences of the bot's username mention
        user_message = user_message.replace(f"@{bot_username}", "").strip()
        # If after removing mention, the message is empty, we might ignore or handle differently.
        # For now, if it becomes empty, it will be caught by the `if not user_message:` check later.
        logger.debug(f"Removed mention, message to process: '{user_message}'")

    # If this is a reply to the bot, add context from the replied message
    if is_reply_to_bot and message.reply_to_message:
        replied_text = message.reply_to_message.text or "" # Ensure replied_text is not None

        if user_message: # If there's new text in the reply
            user_message = f"Context from my previous message: \"{replied_text}\"\n\nUser's question/reply: \"{user_message}\""
        elif replied_text: # If reply is empty but original message had text (e.g. user replies with sticker to bot text)
            # Frame it as a question about the context
            user_message = f"Context from my previous message: \"{replied_text}\"\n\nUser replied without additional text (e.g., with a sticker or just to get my attention). What should I say or do regarding my previous message?"
            logger.debug("Reply had no new text, created query based on bot's original message.")
        else: # Reply to a non-text message (e.g. photo) from bot, and reply itself is also non-text/empty
             logger.debug("Reply to a non-text message from bot, and reply itself is empty/non-text. Ignoring.")
             return


    # If, after processing mentions/replies, the user_message is empty, ignore.
    if not user_message.strip(): # Use strip() to catch messages that become whitespace
        logger.debug("After processing mentions/replies, message is empty or whitespace. Ignoring.")
        return

    logger.info(f"Processing group message (mention or reply): '{user_message}' from user {user_id}")

    session = session_manager.get_or_create_session(user_id)
    model_provider = session_manager.get_model_provider(user_id)
    logger.info(f"User {user_id} using model provider: {model_provider}")

    try:
        if model_provider == "anthropic":
            logger.info(f"Using Anthropic (Claude) client for user {user_id}")
            reply = await claude_client.process_message(session, user_message)
        elif model_provider == "gemini":
            logger.info(f"Using Gemini client for user {user_id}")
            reply = await gemini_client.process_message(session, user_message)
        elif model_provider == "grok":
            logger.info(f"Using Grok client for user {user_id}")
            reply = await grok_client.process_message(session, user_message)
        else:
            logger.info(f"Using OpenAI client for user {user_id}")
            reply = await openai_client.process_message(session, user_message)

        await message.reply(reply) # Use reply to keep context in group chat
        logger.info(f"Successfully processed and replied in group to user {user_id}.")
    except Exception as e:
        logger.error(f"Error processing group message for user {user_id} via AI client: {e}", exc_info=True)
        await message.reply("Sorry, I encountered an error trying to process that.")

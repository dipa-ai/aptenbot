from aiogram import Router, F
from aiogram.types import Message, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from aiogram.dispatcher.event.bases import SkipHandler
from config import OPENAI_MODEL, ANTHROPIC_MODEL, OPENAI_ALLOWED_MODELS, ANTHROPIC_ALLOWED_MODELS, GEMINI_MODEL, GEMINI_ALLOWED_MODELS, GROK_MODEL, GROK_ALLOWED_MODELS
import re
from utils.logging_config import logger

router = Router()

@router.message(Command("start"))
async def handle_start(message: Message, session_manager):
    user_id = message.from_user.id
    session_manager.get_or_create_session(user_id)

    welcome_message = (
        "👋 Hello! I'm a helpful bot with AI capabilities.\n\n"
        "In private chat, you can:\n"
        "• Just send me a message to chat\n"
        "• Send an image for analysis\n"
        "• Use /model to switch between AI models\n"
        "• Use /new to start a new conversation\n\n"
        "In group chats, you can:\n"
        "• Tag me in a message to get my attention\n"
        "• Start your message with /ask to ask me a question\n"
        "• Send images with the /ask command in the caption\n\n"
    )

    await message.answer(welcome_message)

@router.message(Command("help"))
async def handle_help(message: Message):
    help_message = (
        "📚 <b>Available Commands</b>\n\n"
        "/start - Introduction to the bot\n"
        "/new - Start a new conversation\n"
        "/provider - Select AI provider (OpenAI or Claude)\n"
        "/model - Select a specific model from the current provider\n"
        "/img - Generate images (OpenAI or Flux)\n"
        "/imgmodel - Select default image generation model\n"
        "/help - Show this help message\n\n"
        "<b>Using the bot:</b>\n"
        "• In <b>private chat</b>, just send messages directly\n"
        "• In <b>groups</b>, tag me or use /ask to get my attention\n"
        "• <b>Image generation</b>: use /img [openai|flux] your prompt\n"
        "• <b>Group chats</b>: Add /ask when posting images for analysis\n\n"
        "Each user has their own conversation history that persists until you start a new conversation with /new"
    )

    await message.answer(help_message, parse_mode="HTML")

@router.message(Command("new"))
async def handle_new(message: Message, session_manager):
    user_id = message.from_user.id
    session_manager.create_new_session(user_id)
    await message.answer("🔄 Starting a new conversation. Previous messages have been cleared.")

@router.message(Command("provider"))
async def handle_provider_command(message: Message, session_manager):
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type

    logger.info(f"Provider command from user {user_id} in chat {chat_id} (type: {chat_type})")

    # Create provider options
    current_provider = session_manager.get_model_provider(user_id)
    openai_current = "✓ " if current_provider == "openai" else ""
    claude_current = "✓ " if current_provider == "anthropic" else ""
    gemini_current = "✓ " if current_provider == "gemini" else ""
    grok_current = "✓ " if current_provider == "grok" else ""

    response = (
        "🤖 <b>Select an AI provider:</b>\n\n"
        f"1. {openai_current}OpenAI\n"
        f"2. {claude_current}Claude (Anthropic)\n"
        f"3. {gemini_current}Gemini (Google)\n"
        f"4. {grok_current}Grok\n\n"
        "To select a provider, reply with its number (e.g., '1')"
    )

    # Create or update model selection state
    session = session_manager.get_or_create_session(user_id)
    logger.info(f"Setting state 'selecting_provider' for user {user_id}")
    session.update_state("selecting_provider")

    await message.answer(response, parse_mode="HTML")
    logger.info("Provider options sent")

@router.message(Command("model"))
async def handle_model_command(message: Message, session_manager):
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type

    logger.info(f"Model command from user {user_id} in chat {chat_id} (type: {chat_type})")

    session = session_manager.get_or_create_session(user_id)
    provider = session.get_provider()

    # Get allowed models based on provider
    if provider == "openai":
        allowed_models = OPENAI_ALLOWED_MODELS
        default_model = OPENAI_MODEL
    elif provider == "anthropic":
        allowed_models = ANTHROPIC_ALLOWED_MODELS
        default_model = ANTHROPIC_MODEL
    elif provider == "gemini":
        allowed_models = GEMINI_ALLOWED_MODELS
        default_model = GEMINI_MODEL
    else:
        allowed_models = GROK_ALLOWED_MODELS
        default_model = GROK_MODEL

    # Use allowed models or fallback to default if empty
    if not allowed_models:
        model_options = f"Using default model: {default_model}"
        await message.answer(model_options)
        return

    # Get current model
    current_model = session.get_model()

    # Create model options
    model_options = ""
    for i, model_id in enumerate(allowed_models, start=1):
        current = "✓ " if model_id == current_model else ""
        model_options += f"{i}. {current}{model_id}\n"

    response = (
        f"🤖 <b>Select a {provider.capitalize()} model:</b>\n\n"
        f"{model_options}\n"
        "To select a model, reply with its number (e.g., '1')"
    )

    # Create or update model selection state
    session.update_state("selecting_specific_model")

    await message.answer(response, parse_mode="HTML")

@router.message(F.text.regexp(r"^[1-9]\d*$"))
async def handle_number_selection(message: Message, session_manager, openai_client, claude_client):
    user_id = message.from_user.id
    chat_type = message.chat.type
    logger.info(f"Handling number selection from user {user_id} in chat type: {chat_type}")

    session = session_manager.get_or_create_session(user_id)
    state = session.get_state()

    logger.info(f"Current user state: {state}")

    # If state is not set, let other handlers process numeric messages
    if not state:
        logger.info("No state set, skipping handler to allow normal processing")
        raise SkipHandler()

    # Provider selection handling
    if state == "selecting_provider":
        logger.info(f"Processing provider selection: {message.text}")
        try:
            selection = int(message.text)
            if selection == 1:
                provider = "openai"
            elif selection == 2:
                provider = "anthropic"
            elif selection == 3:
                provider = "gemini"
            elif selection == 4:
                provider = "grok"
            else:
                await message.answer("❌ Invalid selection. Please choose 1, 2, 3 or 4.")
                return

            session.update_model(provider)
            await message.answer(
                f"✅ Provider switched to <b>{provider.capitalize()}</b>.",
                parse_mode="HTML"
            )
        finally:
            logger.info("Clearing state after provider selection")
            session.clear_state()

    # Specific model selection handling
    elif state == "selecting_specific_model":
        try:
            provider = session.get_provider()
            if provider == "openai":
                allowed_models = OPENAI_ALLOWED_MODELS
            elif provider == "anthropic":
                allowed_models = ANTHROPIC_ALLOWED_MODELS
            elif provider == "gemini":
                allowed_models = GEMINI_ALLOWED_MODELS
            else:
                allowed_models = GROK_ALLOWED_MODELS

            selected_idx = int(message.text) - 1
            if 0 <= selected_idx < len(allowed_models):
                selected_model = allowed_models[selected_idx]
                session.update_specific_model(selected_model)

                await message.answer(
                    f"✅ Model switched to <b>{selected_model}</b>",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Invalid selection. Please choose a valid number from the list.")
        except ValueError:
            await message.answer("❌ Please enter a valid number.")
        finally:
            # Clear selection state
            session.clear_state()

    # Image model selection handling
    elif state == "selecting_img_model":
        try:
            selection = int(message.text)
            if selection == 1:
                provider = "openai"
            elif selection == 2:
                provider = "flux"
            else:
                await message.answer("❌ Invalid selection. Please choose 1 or 2.")
                return

            session.update_image_model(provider)
            await message.answer(
                f"✅ Default image model set to <b>{provider.upper()}</b>",
                parse_mode="HTML"
            )
        finally:
            # Clear selection state
            session.clear_state()

@router.message(Command("imgmodel"))
async def handle_imgmodel_command(message: Message, session_manager):
    user_id = message.from_user.id

    args = message.text.split()
    if len(args) > 1 and args[1] in ["openai", "flux"]:
        provider = args[1]
        session = session_manager.get_or_create_session(user_id)
        session.update_image_model(provider)
        await message.answer(f"✅ Default image model set to <b>{provider.upper()}</b>", parse_mode="HTML")
        return

    # Display options if no valid provider specified
    session = session_manager.get_or_create_session(user_id)
    current_img_provider = session.get_image_model() if hasattr(session, "get_image_model") else "openai"

    openai_current = "✓ " if current_img_provider == "openai" else ""
    flux_current = "✓ " if current_img_provider == "flux" else ""

    response = (
        "🖼️ <b>Select default image generation model:</b>\n\n"
        f"1. {openai_current}GPT-Image (OpenAI)\n"
        f"2. {flux_current}Flux\n\n"
        "Reply with a number or use /imgmodel openai or /imgmodel flux"
    )

    # Set selection state
    session.update_state("selecting_img_model")

    await message.answer(response, parse_mode="HTML")

@router.message(Command("img"))
async def handle_img_command(message: Message, openai_client, flux_client, session_manager):
    user_id = message.from_user.id
    args = message.text.split()

    # Get user's default provider or use openai as fallback
    session = session_manager.get_or_create_session(user_id)
    default_provider = session.get_image_model() if hasattr(session, "get_image_model") else "openai"

    # Check if a provider is specified
    if len(args) > 1 and args[1] in ["openai", "flux"]:
        provider = args[1]
        prompt = " ".join(args[2:])
    else:
        provider = default_provider
        prompt = " ".join(args[1:])

    if not prompt:
        await message.answer(f"Usage: /img [openai|flux] <prompt>\nCurrent default: {default_provider.upper()}")
        return

    await message.answer(f"Generating image using {provider.upper()}...")

    try:
        if provider == "openai":
            image_bytes = await openai_client.generate_image(prompt)
            await message.answer_photo(BufferedInputFile(image_bytes, filename="image.png"))
        else:  # flux
            image_url = await flux_client.generate_image(prompt)
            await message.answer_photo(image_url)
    except Exception as e:
        await message.answer(f"Error generating image: {str(e)}")

@router.message(Command("insta"))
async def cmd_insta(message: Message, instagram_client):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /insta <link to instagram video>")
        return
    user_message = args[1]
    url_pattern = r'https?://(?:www\.)?instagram\.com/[^\s]+'
    match = re.search(url_pattern, user_message)
    if not match:
        await message.answer("Please provide a valid Instagram URL")
        return
    instagram_url = match.group(0)
    ok, path = instagram_client.download_video(instagram_url)
    if not ok:
        await message.answer(f"Something went wrong: {path}")
        return

    # Use FSInputFile instead of directly opening the file
    video_file = FSInputFile(path)
    await message.answer_video(video_file)

    # Try deleting the original command message only when allowed (groups, bot has rights)
    if message.chat.type in ("group", "supergroup"):
        try:
            me = await message.bot.get_me()
            member = await message.bot.get_chat_member(message.chat.id, me.id)
            can_delete = bool(getattr(member, "can_delete_messages", False))
            if can_delete:
                await message.delete()
        except Exception as e:
            logger.debug(f"Skip deleting message (no rights or not allowed): {e}")

@router.message(Command("ask"), ~F.photo)
async def handle_ask_command(message: Message, session_manager, openai_client, claude_client, gemini_client, grok_client):
    user_id = message.from_user.id

    # Extract the actual question (remove the /ask part)
    question_source = message.text or message.caption or ""
    question = question_source.replace("/ask", "", 1).strip()

    # Check if this is a reply to another message
    if message.reply_to_message:
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""

        # Check if the replied message has a photo
        if message.reply_to_message.photo:
            # Handle photo from replied message
            if not question:
                question = "What is in this image?"
            elif replied_text:
                question = f"Context from caption: \"{replied_text}\"\n\nUser's question: \"{question}\""

            # Get photo URL
            file = await message.bot.get_file(message.reply_to_message.photo[-1].file_id)
            file_url = file.file_path

            session = session_manager.get_or_create_session(user_id)
            model_provider = session_manager.get_model_provider(user_id)

            # Process with image
            if model_provider == "anthropic":
                response = await claude_client.process_message_with_image(session, question, [file_url])
            elif model_provider == "gemini":
                response = await gemini_client.process_message_with_image(session, question, [file_url])
            elif model_provider == "grok":
                response = await grok_client.process_message_with_image(session, question, [file_url])
            else:
                response = await openai_client.process_message_with_image(session, question, [file_url])
            
            await message.reply(response)
            return

        # No photo, just text context
        if replied_text:
            # Add context from the replied message
            if question:
                question = f"Context from previous message: \"{replied_text}\"\n\nUser's question: \"{question}\""
            else:
                # If no question provided, just analyze the replied message
                question = f"Context from previous message: \"{replied_text}\"\n\nUser asked to analyze this."
        elif not question:
            await message.answer("Please provide a question after /ask")
            return
    elif not question:
        await message.answer("Please provide a question after /ask")
        return

    session = session_manager.get_or_create_session(user_id)
    provider = session.get_provider()

    # Process the question using the appropriate provider
    if provider == "anthropic":
        response = await session.process_claude_message(question, claude_client)
    elif provider == "gemini":
        response = await session.process_gemini_message(question, gemini_client)
    elif provider == "grok":
        response = await session.process_grok_message(question, grok_client)
    else:
        response = await session.process_openai_message(question, openai_client)

    await message.reply(response)

# Handler for numeric responses in the form of a reply to a bot message in group chats
@router.message(F.reply_to_message & F.text.regexp(r"^[1-9]\d*$"))
async def handle_reply_number_selection(message: Message, session_manager, openai_client, claude_client):
    # Check if the response is a reply to a bot message
    if not message.reply_to_message.from_user or message.reply_to_message.from_user.is_bot is False:
        return

    bot_username = (await message.bot.me()).username
    replied_username = message.reply_to_message.from_user.username

    if replied_username != bot_username:
        return

    user_id = message.from_user.id
    chat_type = message.chat.type

    # Get the session and check the state - this is the key check!
    session = session_manager.get_or_create_session(user_id)
    state = session.get_state()

    # If there's no selection state, this is a regular reply to a message,
    # not an option selection - skip to let the regular reply handler process it
    if not state or state not in ["selecting_provider", "selecting_specific_model", "selecting_img_model"]:
        logger.info(
            f"Reply with number but no selection state: {message.text} - skipping to regular handler"
        )
        raise SkipHandler()

    # From here down, we know this is a reply to handle selection state
    logger.info(f"Handling number reply selection from user {user_id} in chat type: {chat_type}")
    logger.info(f"Current user state (reply): {state}")

    # Provider selection handling
    if state == "selecting_provider":
        logger.info(f"Processing provider selection (reply): {message.text}")
        try:
            selection = int(message.text)
            if selection == 1:
                provider = "openai"
            elif selection == 2:
                provider = "anthropic"
            elif selection == 3:
                provider = "gemini"
            elif selection == 4:
                provider = "grok"
            else:
                await message.answer("❌ Invalid selection. Please choose 1, 2, 3 or 4.")
                return

            session.update_model(provider)
            await message.answer(
                f"✅ Provider switched to <b>{provider.capitalize()}</b>.",
                parse_mode="HTML"
            )
            # Mark message as handled to prevent other handlers from processing it
            return True
        finally:
            logger.info("Clearing state after provider selection (reply)")
            session.clear_state()

    # Specific model selection handling
    elif state == "selecting_specific_model":
        try:
            provider = session.get_provider()
            if provider == "openai":
                allowed_models = OPENAI_ALLOWED_MODELS
            elif provider == "anthropic":
                allowed_models = ANTHROPIC_ALLOWED_MODELS
            elif provider == "gemini":
                allowed_models = GEMINI_ALLOWED_MODELS
            else:
                allowed_models = GROK_ALLOWED_MODELS

            selected_idx = int(message.text) - 1
            if 0 <= selected_idx < len(allowed_models):
                selected_model = allowed_models[selected_idx]
                session.update_specific_model(selected_model)

                await message.answer(
                    f"✅ Model switched to <b>{selected_model}</b>",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Invalid selection. Please choose a valid number from the list.")
        except ValueError:
            await message.answer("❌ Please enter a valid number.")
        finally:
            # Clear selection state
            session.clear_state()

    # Image model selection handling
    elif state == "selecting_img_model":
        try:
            selection = int(message.text)
            if selection == 1:
                provider = "openai"
            elif selection == 2:
                provider = "flux"
            else:
                await message.answer("❌ Invalid selection. Please choose 1 or 2.")
                return

            session.update_image_model(provider)
            await message.answer(
                f"✅ Default image model set to <b>{provider.upper()}</b>",
                parse_mode="HTML"
            )
        finally:
            # Clear selection state
            session.clear_state()

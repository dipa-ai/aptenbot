# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot built with aiogram 3.x that integrates multiple AI providers (OpenAI, Claude, Gemini, Grok) for intelligent conversations, image processing, and media handling. The bot supports both private chats and group conversations with per-user session management.

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py

# Run tests
pytest tests/
```

### Required Environment Variables
```bash
# Core
export TG_BOT_TOKEN='your_telegram_bot_token'

# AI Providers (at least one required)
export OPENAI_API_KEY='your_key'
export ANTHROPIC_API_KEY='your_key'
export GEMINI_API_KEY='your_key'
export GROK_API_KEY='your_key'

# Optional
export BFL_API_KEY='your_key'  # For Flux image generation
export CHANNEL_ID='@channel1,@channel2'  # Comma-separated list for subscription checks
```

## Architecture

### Core Components

**Entry Point (`bot.py`)**
- Initializes Bot and Dispatcher with MemoryStorage for FSM
- Creates singleton instances of all managers and clients
- Registers dependencies via `dp["key"] = instance` pattern
- Sets up middleware chain: LoggingMiddleware → SubscriptionMiddleware → DependencyMiddleware
- Includes routers in order: commands → messages → media

**Dependency Injection Pattern**
All handlers receive dependencies through middleware injection, not direct imports:
```python
async def handler(message: Message, session_manager, openai_client, claude_client):
    # Dependencies automatically injected by DependencyMiddleware
```

The `DependencyMiddleware` (middlewares/dependencies.py) injects clients and managers into handler parameters. Never instantiate clients directly in handlers.

**Session Management (`managers/session_manager.py`)**
- `SessionManager`: Manages per-user conversation state with in-memory dict storage
- `Session`: Wrapper class for individual user sessions with methods like:
  - `process_openai_message()`, `process_claude_message()`, `process_gemini_message()`, `process_grok_message()`
  - `update_state()`, `get_state()`, `clear_state()` for FSM state tracking
  - `update_model()`, `get_model()` for model selection
- Sessions expire after 1 hour (SESSION_EXPIRY in config.py)
- Model preferences persist across sessions for the same user
- Messages stored with roles: "developer" (system), "user", "assistant"

**Client Architecture (`clients/`)**
Each AI client follows the same async context manager pattern:
```python
@asynccontextmanager
async def get_client(self):
    async with ClientLibrary(...) as client:
        yield client
```

Key methods:
- `process_message(session, text)`: Text-only conversations
- `process_message_with_image(session, text, image_urls)`: Multimodal requests
- `generate_image(prompt)`: Image generation (OpenAI, Flux only)

**OpenAI Client (`clients/openai_client.py`)**
- Uses OpenAI Responses API (NOT Chat Completions API)
- Supports reasoning models (o1, o3-mini, etc.) without fallback
- Image handling: converts Telegram file paths to full URLs

**Claude Client (`clients/claude_client.py`)**
- Uses Anthropic Messages API
- System prompt passed separately (not in messages array)
- Image format: `{"type": "image", "source": {"type": "url", "url": "..."}}`

**Other Clients**
- Gemini: Uses Google's generativeai library with sync wrapper
- Grok: OpenAI-compatible API via custom base URL
- Flux: Black Forest Labs API for image generation
- Instagrapi: Downloads Instagram videos with Redis session caching

**Router Structure (`routers/`)**
- `commands.py`: Handles all slash commands (/start, /help, /new, /provider, /model, /img, /insta, /ask)
- `messages.py`: Processes text messages in private and group chats
- `media.py`: Handles photo/video/document uploads with multimodal processing
- FSM states tracked in session for multi-step interactions (model selection, provider selection)

**Group Chat Handling**
Bot responds in groups when:
1. @username mentioned in message
2. Replying to bot's message
3. Message starts with /ask command

In group chats, numeric selections (for model/provider) must be replies to bot messages.

**Media Processing Flow**
1. User sends photo/document → media router handler
2. Handler gets file from Telegram API: `await message.bot.get_file(file_id)`
3. File path passed to appropriate client's `process_message_with_image()`
4. Client converts relative path to full URL: `https://api.telegram.org/file/bot{TOKEN}/{file_path}`
5. Response sent via multimodal API (OpenAI Responses API, Claude Messages API, etc.)

**Subscription Middleware (`middlewares/subscription.py`)**
- Checks if user is subscribed to configured channels (CHANNEL_IDS)
- Skips check for private chats
- Blocks non-subscribers in groups from using bot

**Configuration (`config.py`)**
- All settings via environment variables
- Model lists: OPENAI_MODELS, ANTHROPIC_MODELS, GEMINI_MODELS, GROK_MODELS
- Allowed models can be restricted via OPENAI_ALLOWED_MODELS env var (comma-separated)
- DEFAULT_MODEL_PROVIDER determines initial provider selection
- Special handling for reasoning models (OPENAI_MODELS_REASONING)

### Message Flow

**Private Chat:**
1. User sends message → LoggingMiddleware logs it
2. SubscriptionMiddleware checks subscription (skips private chats)
3. DependencyMiddleware injects session_manager and clients
4. messages.py router matches based on chat type
5. Handler gets/creates session, determines provider, processes message
6. Response sent back via `message.reply()`

**Group Chat:**
1. Bot checks if it should respond (mentioned, replied to, /ask command)
2. Same middleware chain as private
3. Group message handler processes if conditions met
4. For /ask command, commands.py handler processes it

**State-Based Selection (Provider/Model):**
1. User sends /provider or /model command
2. Handler displays options and sets session state (e.g., "selecting_provider")
3. User replies with number
4. Number handler checks session state, processes selection, clears state
5. In groups: must be reply to bot message to avoid conflicts

## Important Patterns

**Never Create Client Instances in Handlers**
Always use injected dependencies. Clients are singletons created in bot.py.

**Image URL Handling**
Telegram file paths are relative. Always convert:
```python
if not url.startswith(('http://', 'https://')):
    url = f"https://api.telegram.org/file/bot{self.telegram_bot_token}/{url}"
```

**Session State Management**
- Use `session.update_state()` before showing selection menus
- Always call `session.clear_state()` in finally blocks after processing
- Check state before processing numeric inputs to avoid conflicts

**OpenAI API Changes**
This bot uses OpenAI Responses API (not Chat Completions). Message format:
```python
input_items = [{"role": "system"|"user"|"assistant", "content": ...}]
response = await client.responses.create(model=model, input=input_items)
text = response.output_text
```

**Error Handling**
- Clients catch provider-specific errors (RateLimitError, OpenAIError, etc.)
- Return user-friendly error strings, not exceptions
- Log errors with logger.error() including exc_info=True for tracebacks

**FSM State in Sessions**
Don't use aiogram FSM states. Use session.data['state'] for state tracking:
- "selecting_provider"
- "selecting_specific_model"
- "selecting_img_model"

## Testing

Test structure mirrors source:
- `tests/routers/` for router tests
- `tests/middlewares/` for middleware tests
- Tests use module stubs (see test_telegram_utils.py) for external dependencies

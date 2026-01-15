# Project Overview

This project is a sophisticated Telegram bot built with `aiogram 3.x` that acts as a unified interface for multiple AI providers (OpenAI, Claude, Gemini, Grok). It supports intelligent text conversations, image processing (including generation via Flux), and media handling in both private and group chats. It features per-user session management, robust dependency injection for clients, and subscription-based access control.

## Repository Structure

- `.github/` - CI/CD workflows and GitHub templates.
- `clients/` - Async clients for AI providers (OpenAI, Claude, Gemini, Grok, Instagrapi) implementing a consistent interface.
- `deploy/` - Deployment configurations.
- `managers/` - Logic for session management (`SessionManager`) and state persistence.
- `middlewares/` - Aiogram middlewares for logging, subscription checks, and dependency injection.
- `models/` - Data models and Pydantic schemas.
- `routers/` - Request handlers organized by function: `commands.py`, `messages.py`, `media.py`.
- `states/` - FSM state definitions.
- `tests/` - Unit and integration tests mirroring the source structure.
- `utils/` - Helper functions and utilities.
- `bot.py` - Application entry point, dependency wiring, and startup logic.
- `config.py` - Configuration loading from environment variables.
- `CLAUDE.md` - Legacy context file (superseded by this file for agents).

## Build & Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot locally
python bot.py

# Run tests
pytest tests/

# Build Docker image
docker build -t tgbot .

# Run via Docker
docker run --env-file .env tgbot
```

## Code Style & Conventions

- **Python Version**: 3.12+
- **Asyncio**: Heavy reliance on `async`/`await`; direct blocking calls are prohibited in handlers.
- **Type Hinting**: Mandatory for all function signatures. Use `typing` and `pydantic`.
- **Formatting**: Adhere to standard Python PEP 8.
- **Imports**: Organize imports: standard lib -> third party -> local.
- **Logging**: Use `logging.getLogger(__name__)` not `print`.

## Architecture Notes

### Core Diagram
`bot.py` (Entry) -> `DependencyMiddleware` -> `Routers` (`commands`, `messages`) -> `Handlers` -> `SessionManager` / `AI Clients`

- **Dependency Injection**: `bot.py` initializes singletons (clients, managers). `DependencyMiddleware` injects them into handlers. **Never** instantiate clients inside handlers.
- **Session Management**: In-memory `SessionManager` handles conversation history and user preferences (model/provider selection). Sessions expire after 1 hour.
- **AI Clients**: Unified `process_message` interface. OpenAI client uses the "Responses API" (not Chat Completions).
- **Group chats**: Bot only responds to mentions, replies, or `/ask`.

## Testing Strategy

- **Tool**: `pytest`
- **Structure**: Tests are located in `tests/` and mirror the package structure (e.g., `tests/routers/test_commands.py`).
- **Mocking**: External APIs (Telegram, OpenAI, etc.) must be mocked. see `tests/test_telegram_utils.py` for stubs.

## Security & Compliance

- **Secrets**: ALL secrets must be loaded from environment variables via `config.py`. Never hardcode keys.
- **Env Vars**:
  - `TG_BOT_TOKEN`: Telegram Bot Token
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROK_API_KEY`: Provider keys
  - `CHANNEL_ID`: Comma-separated list for forced subscription checks.
- **Access Control**: `SubscriptionMiddleware` enforces channel membership before processing messages (except in private chats).

## Agent Guardrails

- **No Global State**: specific user state must be stored in `SessionManager`, not global variables.
- **Client Instantiation**: **FORBIDDEN** to create new client instances (`OpenAIClient`, etc.) inside route handlers. Use the injected arguments.
- **Blocking Code**: Do not use blocking I/O (like `requests` or `time.sleep`) in async handlers.

## Extensibility Hooks

- **New Providers**: Add a new client class in `clients/`, implement the standard interface, and register it in `bot.py` and `DependencyMiddleware`.
- **New Commands**: Register new command handlers in `routers/commands.py`.

## Further Reading

- [CLAUDE.md](file:///home/alex/git/tgbot/CLAUDE.md) - Previous context file containing specific API usage examples.
- [README.md](file:///home/alex/git/tgbot/README.md) - General user information.

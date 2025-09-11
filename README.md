# Telegram AI Bot

A Telegram bot that integrates with OpenAI, Claude, Google Gemini and Grok AI models to provide intelligent responses, supporting both text and image processing.

## Features

- Text conversations with OpenAI, Claude, Gemini and Grok models
- Image processing and analysis
- Media group handling
- Instagram video downloading
- Automatic Instagram login with shared Redis session
- Group chat support with mention handling
- Model switching between OpenAI, Claude, Gemini and Grok

## Structure

The project uses aiogram 3.x with a clean architecture:

```
project/
├── bot.py                   # Main entry point
├── config.py                # Configuration settings
├── clients/                 # API clients
│   ├── openai_client.py     # OpenAI API integration
│   ├── claude_client.py     # Claude API integration
│   ├── flux_client.py       # Image generation API
│   └── instagrapi_client.py # Instagram content downloader
├── redis_client.py          # Redis Sentinel connector
├── session_store.py         # Redis-based Instagram session cache
├── routers/                 # Message routers
│   ├── commands.py          # Command handlers
│   ├── messages.py          # Text message handlers
│   └── media.py             # Media file handlers
├── middlewares/             # Middleware components
│   ├── subscription.py      # Channel subscription checker
│   └── logging.py           # Message logging
├── states/                  # FSM states
│   └── conversation.py      # Conversation states
├── managers/                # Business logic managers
│   ├── session_manager.py   # User session management
│   └── subscription_manager.py # Subscription verification
└── utils/                   # Utility functions
    ├── logging_config.py    # Logging configuration
    └── telegram_utils.py    # Telegram-specific utilities
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tgbot.git
cd tgbot
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your environment variables:
```bash
# Set Telegram Bot token (required)
export TG_BOT_TOKEN='your_telegram_bot_token'

# Set API keys for AI providers
export OPENAI_API_KEY='your_openai_api_key'
export ANTHROPIC_API_KEY='your_anthropic_api_key'

# Optional: Set other configuration variables
export OPENAI_MODEL='gpt-4o-mini'
export ANTHROPIC_MODEL='claude-3-5-haiku-20241022'
export DEFAULT_MODEL_PROVIDER='openai'
export BFL_API_KEY='your_bfl_api_key'  # For image generation
export CHANNEL_ID='@korobo4ka_xoroni'
export LOG_LEVEL='INFO'
```

5. Run the bot:
```bash
python bot.py
```

## Required API Keys

- **Telegram Bot Token**: Obtain from [BotFather](https://t.me/botfather)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/account/api-keys)
- **Anthropic API Key**: Get from [Anthropic Console](https://console.anthropic.com/)
- **Black Forest Labs API Key** (optional): For image generation

## Environment Variables

All configuration is done through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_BOT_TOKEN` | Your Telegram bot token | *Required* |
| `OPENAI_API_KEY` | Your OpenAI API key | *Required for OpenAI* |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | *Required for Claude* |
| `GEMINI_API_KEY` | Your Google Gemini API key | *Required for Gemini* |
| `GROK_API_KEY` | Your Grok API key | *Required for Grok* |
| `OPENAI_MODEL` | OpenAI model to use | gpt-4o-mini |
| `ANTHROPIC_MODEL` | Claude model to use | claude-3-5-haiku-20241022 |
| `GEMINI_MODEL` | Gemini model to use | gemini-pro |
| `GROK_MODEL` | Grok model to use | grok-1 |
| `DEFAULT_MODEL_PROVIDER` | Default AI provider (openai, anthropic, gemini or grok) | openai |
| `BFL_API_KEY` | Black Forest Labs API key | *Optional* |
| `CHANNEL_ID` | Channel ID for subscription check | @korobo4ka_xoroni |
| `LOG_LEVEL` | Logging level | INFO |

## Commands

- `/start` - Start the bot and get help
- `/help` - Display available commands
- `/new` - Start a new conversation
 - `/provider` - Select AI provider (OpenAI, Claude, Gemini or Grok)
- `/model` - Choose a specific model from the current provider
- `/imgmodel` - Set the default image generation model
- `/img [openai|flux] <prompt>` - Generate an image from text
- `/insta <url>` - Download Instagram video
- `/ask <question>` - Ask a question in group chats

## License

[MIT License](LICENSE)

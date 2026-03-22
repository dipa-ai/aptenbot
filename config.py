import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.groq.com/openai/v1")
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "TschatWitscha_bot")

# Parse CHANNEL_ID as a list (comma-separated)
# Examples: "@channel1,@channel2" or "-1001234567890,@mychannel"
_channel_id_raw = os.getenv("CHANNEL_ID", "@korobo4ka_xoroni")
CHANNEL_IDS = [ch.strip() for ch in _channel_id_raw.split(",") if ch.strip()]
# Keep CHANNEL_ID for backward compatibility (first channel in the list)
CHANNEL_ID = CHANNEL_IDS[0] if CHANNEL_IDS else "@korobo4ka_xoroni"

CHANNEL_USER_ID = os.getenv("CHANNEL_USER_ID", "777000")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-1")
FLUX_MODEL = os.getenv("FLUX_MODEL", "flux-pro-1.1")
BFL_API_KEY = os.getenv("BFL_API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

MAX_RETRIES = 3
RETRY_DELAY = 1
SESSION_EXPIRY = 3600  # 1 hour
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")
_VALID_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}
_reasoning_raw = os.getenv("OPENAI_REASONING_EFFORT", "").strip().lower() or None
OPENAI_REASONING_EFFORT = _reasoning_raw if _reasoning_raw in _VALID_REASONING_EFFORTS else None
OPENAI_MODELS = ['gpt-5', 'gpt-5-mini', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'gpt-4o', 'gpt-4o-mini', 'o1', 'o3', 'o4-mini', 'o3-mini', 'o1-mini']
OPENAI_MODELS_REASONING = ['o1', 'o1-pro', 'o3-mini', 'o1-mini']
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_MODELS = ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022']
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
GEMINI_MODELS = ['gemini-pro', 'gemini-pro-vision']
DEFAULT_GEMINI_MODEL = 'gemini-pro'
GROK_MODELS = ['grok-1']
DEFAULT_GROK_MODEL = 'grok-1'

# Default model provider to use (openai, anthropic, gemini or grok)
DEFAULT_MODEL_PROVIDER = os.getenv("DEFAULT_MODEL_PROVIDER", "openai")

# Get allowed models from environment variables or default to all models
OPENAI_ALLOWED_MODELS = os.getenv("OPENAI_ALLOWED_MODELS", "").split(",") if os.getenv("OPENAI_ALLOWED_MODELS") else OPENAI_MODELS
ANTHROPIC_ALLOWED_MODELS = os.getenv("ANTHROPIC_ALLOWED_MODELS", "").split(",") if os.getenv("ANTHROPIC_ALLOWED_MODELS") else ANTHROPIC_MODELS
GEMINI_ALLOWED_MODELS = os.getenv("GEMINI_ALLOWED_MODELS", "").split(",") if os.getenv("GEMINI_ALLOWED_MODELS") else GEMINI_MODELS
GROK_ALLOWED_MODELS = os.getenv("GROK_ALLOWED_MODELS", "").split(",") if os.getenv("GROK_ALLOWED_MODELS") else GROK_MODELS

# Clean up empty strings if trailing comma in env var
OPENAI_ALLOWED_MODELS = [model.strip() for model in OPENAI_ALLOWED_MODELS if model.strip()]
ANTHROPIC_ALLOWED_MODELS = [model.strip() for model in ANTHROPIC_ALLOWED_MODELS if model.strip()]
GEMINI_ALLOWED_MODELS = [model.strip() for model in GEMINI_ALLOWED_MODELS if model.strip()]
GROK_ALLOWED_MODELS = [model.strip() for model in GROK_ALLOWED_MODELS if model.strip()]

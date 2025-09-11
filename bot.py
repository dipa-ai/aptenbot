import asyncio
import sys
from colorama import init, Fore, Style
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import TELEGRAM_BOT_TOKEN
from managers.session_manager import SessionManager
from managers.subscription_manager import SubscriptionManager
from clients.openai_client import OpenAIClient
from clients.claude_client import ClaudeClient
from clients.gemini_client import GeminiClient
from clients.grok_client import GrokClient
from clients.flux_client import FluxClient
from clients.instaloader import InstaloaderClient
from routers import commands_router, messages_router, media_router
from middlewares.subscription import SubscriptionMiddleware
from middlewares.logging import LoggingMiddleware
from middlewares.dependencies import DependencyMiddleware
from utils.logging_config import logger

# Initialize colorama for colored terminal output
init()

async def main():
    # Check if token is available
    if not TELEGRAM_BOT_TOKEN:
        print(f"\n{Fore.RED}ERROR: {Style.BRIGHT}Telegram Bot Token is missing!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please set the {Fore.GREEN}TG_BOT_TOKEN{Fore.YELLOW} environment variable.{Style.RESET_ALL}")
        print(f"\nExample: {Fore.CYAN}export TG_BOT_TOKEN='your_token_here'{Style.RESET_ALL}")
        print()
        sys.exit(1)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    session_manager = SessionManager()
    subscription_manager = SubscriptionManager()
    openai_client = OpenAIClient()
    claude_client = ClaudeClient()
    gemini_client = GeminiClient()
    grok_client = GrokClient()
    flux_client = FluxClient()
    instaloader_client = InstaloaderClient()

    # Register dependencies
    dp["session_manager"] = session_manager
    dp["subscription_manager"] = subscription_manager
    dp["openai_client"] = openai_client
    dp["claude_client"] = claude_client
    dp["gemini_client"] = gemini_client
    dp["grok_client"] = grok_client
    dp["flux_client"] = flux_client
    dp["instaloader_client"] = instaloader_client

    # Middlewares
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(SubscriptionMiddleware(subscription_manager))

    # DependencyMiddleware - register dependencies
    dependency_middleware = DependencyMiddleware(
        session_manager=session_manager,
        openai_client=openai_client,
        claude_client=claude_client,
        gemini_client=gemini_client,
        grok_client=grok_client,
        flux_client=flux_client,
        instaloader_client=instaloader_client
    )
    dp.message.middleware(dependency_middleware)

    # Routers
    dp.include_router(commands_router)
    dp.include_router(messages_router)
    dp.include_router(media_router)

    print(f"\n{Fore.GREEN}Starting the bot...{Style.RESET_ALL}")
    logger.info("Starting the bot application")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}ERROR: {e}{Style.RESET_ALL}")
        logger.error(f"Error in main application: {e}", exc_info=True)

import asyncio
from aiogram.exceptions import TelegramBadRequest
from telegram import Update
from telegram.error import TelegramError, BadRequest
from utils.logging_config import logger
from config import MAX_RETRIES, RETRY_DELAY
from pathlib import Path

TELEGRAM_MESSAGE_LIMIT = 4096


def split_message(text: str, max_length: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split a long message into chunks that fit within Telegram's message size limit.

    Tries to split at paragraph boundaries (double newlines), then single newlines,
    then spaces. Falls back to hard splitting if no natural boundary is found.
    """
    if not text:
        return [text]

    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to find a natural split point within the limit
        split_pos = None

        # 1. Try splitting at a double newline (paragraph boundary)
        pos = remaining.rfind("\n\n", 0, max_length)
        if pos > 0:
            split_pos = pos + 2  # Include the double newline in the first chunk

        # 2. Try splitting at a single newline
        if split_pos is None:
            pos = remaining.rfind("\n", 0, max_length)
            if pos > 0:
                split_pos = pos + 1  # Include the newline in the first chunk

        # 3. Try splitting at a space
        if split_pos is None:
            pos = remaining.rfind(" ", 0, max_length)
            if pos > 0:
                split_pos = pos + 1  # Include the space in the first chunk

        # 4. Hard split as last resort
        if split_pos is None:
            split_pos = max_length

        chunks.append(remaining[:split_pos])
        remaining = remaining[split_pos:]

    return chunks


async def send_long_message(message, text: str) -> None:
    """Send a reply that may exceed Telegram's message size limit.

    Escapes the text for MarkdownV2, splits into chunks, and sends each
    with MarkdownV2 parse mode. If Telegram rejects a formatted chunk,
    falls back to sending the original unescaped text for that chunk.
    """
    if not text:
        return
    chunks = split_message(text)
    for chunk in chunks:
        escaped_chunk = escape_markdown_v2(chunk)
        # Account for length increase after escaping: ensure each sent chunk
        # stays within Telegram's message size limit.
        if len(escaped_chunk) > TELEGRAM_MESSAGE_LIMIT:
            escaped_subchunks = split_message(escaped_chunk, TELEGRAM_MESSAGE_LIMIT)
        else:
            escaped_subchunks = [escaped_chunk]

        for subchunk in escaped_subchunks:
            try:
                await message.reply(subchunk, parse_mode="MarkdownV2")
            except TelegramBadRequest:
                logger.warning("MarkdownV2 parse failed, falling back to plain text")
                # Send original unescaped chunk to avoid visible backslashes
                await message.reply(chunk)


def escape_markdown_v2(text: str) -> str:
    # First handle triple backticks (code blocks)
    parts = text.split("```")

    for i in range(len(parts)):
        if i % 2 == 0:  # Regular text parts
            # Handle single backticks in regular text
            subparts = parts[i].split("`")
            for j in range(len(subparts)):
                if j % 2 == 0:  # Non-code text
                    # Escape backslashes first
                    subparts[j] = subparts[j].replace('\\', '\\\\')
                    # Escape special characters except markdown formatting
                    escape_chars = '[]()~`>#+=|{}.!-'
                    subparts[j] = ''.join(f'\\{char}' if char in escape_chars else char
                                        for char in subparts[j])
                else:  # Inline code
                    # For inline code, escape only minimal characters
                    subparts[j] = subparts[j].replace('\\', '\\\\')
                    subparts[j] = subparts[j].replace('`', '\\`')

            parts[i] = '`'.join(subparts)
        else:  # Code blocks
            # For code blocks, escape only minimal characters
            parts[i] = parts[i].replace('\\', '\\\\')
            parts[i] = parts[i].replace('`', '\\`')

    # Rejoin everything
    return '```'.join(parts)

async def send_message_with_retry(update: Update, text: str) -> None:
    escaped_text = escape_markdown_v2(text)
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_text(escaped_text, parse_mode='MarkdownV2')
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)

async def send_pic_with_retry(update: Update, pic: str) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_photo(pic)
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)

async def send_video_with_retry(update: Update, video: str) -> None:
    for attempt in range(MAX_RETRIES):
        try:
            path = Path(video)
            if not path.exists():
                logger.error(f"File not found: {video}")
                return
            await update.message.reply_video(path)
            return
        except TelegramError as e:
            if isinstance(e, BadRequest):
                logger.error(f"Bad request error: {e}")
                return
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts: {e}")
                raise
            await asyncio.sleep(RETRY_DELAY)

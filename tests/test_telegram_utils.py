import asyncio
import importlib
import sys
import types

# Stub out external dependencies required by utils.telegram_utils
telegram = types.ModuleType('telegram')
telegram.error = types.ModuleType('telegram.error')
class Update:  # minimal stub
    pass
class TelegramError(Exception):
    pass
class BadRequest(TelegramError):
    pass
telegram.Update = Update
telegram.error.TelegramError = TelegramError
telegram.error.BadRequest = BadRequest
sys.modules.setdefault('telegram', telegram)
sys.modules.setdefault('telegram.error', telegram.error)

# Use the real aiogram package (installed via requirements.txt)
from aiogram.exceptions import TelegramBadRequest as _AiogramTelegramBadRequest

try:
    # Prefer the real logging configuration module if it exists.
    import utils.logging_config as logging_config
except (ModuleNotFoundError, ImportError):
    # Fallback stub for environments where utils.logging_config is unavailable.
    logging_config = types.ModuleType('utils.logging_config')

    class DummyLogger:
        def __getattr__(self, name):
            # Return a no-op callable for any logging method (e.g., info, debug, error).
            def _noop(*args, **kwargs):
                pass
            return _noop

    logging_config.logger = DummyLogger()
    sys.modules.setdefault('utils.logging_config', logging_config)

telegram_utils = importlib.import_module('utils.telegram_utils')
escape_markdown_v2 = telegram_utils.escape_markdown_v2
split_message = telegram_utils.split_message
send_long_message = telegram_utils.send_long_message

def test_escape_special_characters():
    text = r"Escape []()~>#+=|{}.!- and \\backslashes"
    expected = r"Escape \[\]\(\)\~\>\#\+\=\|\{\}\.\!\- and \\\\backslashes"
    assert escape_markdown_v2(text) == expected

def test_inline_code_preserved():
    text = "Start `code [x](y) ~` end."
    expected = "Start `code [x](y) ~` end\\."
    assert escape_markdown_v2(text) == expected

def test_code_block_preserved():
    text = "Begin ```\nblock [x](y) -``` end."
    expected = "Begin ```\nblock [x](y) -``` end\\."
    assert escape_markdown_v2(text) == expected


# --- Tests for split_message ---

def test_split_message_short_text():
    """Short text should be returned as a single chunk."""
    text = "Hello, world!"
    result = split_message(text)
    assert result == ["Hello, world!"]

def test_split_message_empty_text():
    """Empty text should be returned as a single chunk."""
    result = split_message("")
    assert result == [""]

def test_split_message_exact_limit():
    """Text exactly at the limit should be returned as a single chunk."""
    text = "a" * 4096
    result = split_message(text)
    assert result == [text]

def test_split_message_over_limit_splits_at_paragraph():
    """Long text should split at paragraph boundaries (double newlines)."""
    part1 = "a" * 2000
    part2 = "b" * 3000
    text = part1 + "\n\n" + part2
    result = split_message(text)
    assert len(result) == 2
    assert result[0] == part1 + "\n\n"
    assert result[1] == part2

def test_split_message_over_limit_splits_at_newline():
    """Long text without paragraph breaks should split at single newlines."""
    part1 = "a" * 2000
    part2 = "b" * 3000
    text = part1 + "\n" + part2
    result = split_message(text)
    assert len(result) == 2
    assert result[0] == part1 + "\n"
    assert result[1] == part2

def test_split_message_over_limit_splits_at_space():
    """Long text without newlines should split at spaces."""
    part1 = "a" * 2000
    part2 = "b" * 3000
    text = part1 + " " + part2
    result = split_message(text)
    assert len(result) == 2
    assert result[0] == part1 + " "
    assert result[1] == part2

def test_split_message_hard_split():
    """Long text without any natural boundaries should be hard-split."""
    text = "a" * 5000
    result = split_message(text)
    assert len(result) == 2
    assert result[0] == "a" * 4096
    assert result[1] == "a" * 904

def test_split_message_multiple_chunks():
    """Very long text should produce multiple chunks."""
    text = "a" * 10000
    result = split_message(text)
    assert len(result) == 3
    assert all(len(chunk) <= 4096 for chunk in result)
    assert "".join(result) == text

def test_split_message_custom_max_length():
    """Custom max_length parameter should be respected."""
    text = "Hello World! This is a test."
    result = split_message(text, max_length=12)
    assert all(len(chunk) <= 12 for chunk in result)
    assert "".join(result) == text

def test_split_message_preserves_content():
    """All content should be preserved after splitting."""
    text = "Line 1\n\nLine 2\n\nLine 3\n\n" + "x" * 5000
    result = split_message(text)
    assert "".join(result) == text


# --- Tests for send_long_message ---

class FakeMessage:
    """Stub for aiogram Message that records reply calls."""
    def __init__(self, fail_markdown=False):
        self.replies = []
        self.fail_markdown = fail_markdown

    async def reply(self, text, parse_mode=None):
        if self.fail_markdown and parse_mode == "MarkdownV2":
            raise _AiogramTelegramBadRequest(method="sendMessage", message="Bad Request: can't parse entities")
        self.replies.append((text, parse_mode))


def test_send_long_message_uses_markdownv2():
    """send_long_message should escape text and send with MarkdownV2."""
    msg = FakeMessage()
    asyncio.run(send_long_message(msg, "Hello! World."))
    assert len(msg.replies) == 1
    text, mode = msg.replies[0]
    assert mode == "MarkdownV2"
    assert text == "Hello\\! World\\."


def test_send_long_message_falls_back_on_bad_request():
    """send_long_message should fall back to plain text when MarkdownV2 fails."""
    msg = FakeMessage(fail_markdown=True)
    asyncio.run(send_long_message(msg, "Hello! World."))
    assert len(msg.replies) == 1
    text, mode = msg.replies[0]
    assert mode is None
    # Fallback sends the original unescaped text
    assert text == "Hello! World."


def test_send_long_message_empty_text():
    """send_long_message should do nothing for empty text."""
    msg = FakeMessage()
    asyncio.run(send_long_message(msg, ""))
    assert len(msg.replies) == 0


def test_send_long_message_preserves_code_blocks():
    """send_long_message should preserve code block content."""
    text = "Result:\n```python\nprint('hello!')\n```\nDone."
    msg = FakeMessage()
    asyncio.run(send_long_message(msg, text))
    assert len(msg.replies) == 1
    sent_text, mode = msg.replies[0]
    assert mode == "MarkdownV2"
    # Code block content should not have ! escaped
    assert "print('hello!')" in sent_text
    # Text outside code block should have . escaped
    assert sent_text.endswith("Done\\.")

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

logging_config = types.ModuleType('utils.logging_config')
class DummyLogger:
    def error(self, *args, **kwargs):
        pass
logging_config.logger = DummyLogger()
sys.modules.setdefault('utils.logging_config', logging_config)

telegram_utils = importlib.import_module('utils.telegram_utils')
escape_markdown_v2 = telegram_utils.escape_markdown_v2
split_message = telegram_utils.split_message

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

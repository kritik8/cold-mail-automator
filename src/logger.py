"""Application logger setup with safe credential masking."""
import os
import re
import logging
from typing import Optional

_LOGGER: Optional[logging.Logger] = None

SENSITIVE_PATTERNS = [
    re.compile(r'(password[:=]\s*)([^\s&,]+)', re.IGNORECASE),
    re.compile(r'(api[_-]?key[:=]\s*)([^\s&,]+)', re.IGNORECASE),
    re.compile(r'(secret[:=]\s*)([^\s&,]+)', re.IGNORECASE),
    re.compile(r'(token[:=]\s*)([^\s&,]+)', re.IGNORECASE),
    re.compile(r'(SMTP_PASSWORD=)([^\s]+)', re.IGNORECASE),
    re.compile(r'(LITELLM_API_KEY=)([^\s]+)', re.IGNORECASE),
]


class RedactingFormatter(logging.Formatter):
    """Formatter that strips out API keys and passwords."""
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pattern in SENSITIVE_PATTERNS:
            msg = pattern.sub(r'\1[REDACTED]', msg)
        return msg


def setup_logger(log_dir: str = "logs", log_file: str = "app.log") -> logging.Logger:
    """Initialize and return a configured root logger."""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    logger = logging.getLogger("cold_mailer")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Prevent duplicate handlers
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = RedactingFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler (quieter, warnings & errors or general info)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = RedactingFormatter("[%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    _LOGGER = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the active application logger."""
    global _LOGGER
    if _LOGGER is None:
        return setup_logger()
    return _LOGGER

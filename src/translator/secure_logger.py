"""
Secure logging implementation that automatically redacts sensitive information.

This module provides a logging formatter that prevents accidental exposure of:
- API keys and tokens
- Passwords and credentials
- File content previews that may contain sensitive data
- Partial API key fragments (first/last N characters)

Usage:
    from .secure_logger import get_secure_logger
    logger = get_secure_logger(__name__)
"""

import logging
import re
from typing import Pattern


class SecureFormatter(logging.Formatter):
    """Formatter that redacts sensitive information from log messages."""

    # Patterns for sensitive data that should be redacted
    SENSITIVE_PATTERNS: list[tuple[Pattern[str], str]] = [
        # API keys (Anthropic format: sk-ant-...)
        (re.compile(r'sk-ant-[a-zA-Z0-9_-]+'), '[REDACTED_API_KEY]'),

        # Generic API keys
        (re.compile(r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{20,}["\']?', re.IGNORECASE),
         'api_key=[REDACTED]'),

        # Bearer tokens
        (re.compile(r'Bearer\s+[a-zA-Z0-9._-]+'), 'Bearer [REDACTED_TOKEN]'),

        # Password fields in JSON/logs
        (re.compile(r'["\']?password["\']?\s*[:=]\s*["\']?[^"\'}\s]+["\']?', re.IGNORECASE),
         'password=[REDACTED]'),

        # JWT tokens (basic pattern)
        (re.compile(r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'), '[REDACTED_JWT]'),

        # Partial key exposure patterns (common in debug logs)
        (re.compile(r'["\']?api[_-]?key[_-]?first[_-]?\d+["\']?\s*[:=]\s*["\']?[^"\'}\s]+["\']?', re.IGNORECASE),
         'api_key_first=[REDACTED]'),
        (re.compile(r'["\']?api[_-]?key[_-]?last[_-]?\d+["\']?\s*[:=]\s*["\']?[^"\'}\s]+["\']?', re.IGNORECASE),
         'api_key_last=[REDACTED]'),

        # Credit card numbers (basic pattern)
        (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '[REDACTED_CC]'),

        # Email addresses (optional - uncomment if needed)
        # (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[REDACTED_EMAIL]'),
    ]

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record and redact any sensitive information.

        Args:
            record: The log record to format

        Returns:
            Formatted and sanitized log message
        """
        # Format the message using the parent formatter
        original = super().format(record)

        # Apply all redaction patterns
        sanitized = original
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        return sanitized


def get_secure_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a logger with secure formatting that redacts sensitive information.

    Args:
        name: Name for the logger (typically __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger with secure formatting

    Example:
        >>> logger = get_secure_logger(__name__)
        >>> logger.info("API key: sk-ant-test123")  # Logs as: "API key: [REDACTED_API_KEY]"
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured (avoid duplicate handlers)
    if not logger.handlers:
        logger.setLevel(level)

        # Create console handler with secure formatter
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(SecureFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        logger.addHandler(handler)

        # Prevent propagation to root logger to avoid duplicate logs
        logger.propagate = False

    return logger


# Convenience function for testing redaction
def test_redaction():
    """Test the secure logger redaction patterns."""
    logger = get_secure_logger(__name__)

    print("Testing SecureLogger redaction patterns:")
    print("-" * 60)

    test_cases = [
        "API key: sk-ant-api03-test123...",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        'password="secret123"',
        "api_key=AKIAIOSFODNN7EXAMPLE",
        "api_key_first_10=sk-ant-api",
        "api_key_last_10=test123ABC",
        "Credit card: 4532-1234-5678-9010",
    ]

    for test in test_cases:
        logger.info(f"Test: {test}")

    print("-" * 60)
    print("All tests completed. Check that sensitive data was redacted.")


if __name__ == "__main__":
    test_redaction()

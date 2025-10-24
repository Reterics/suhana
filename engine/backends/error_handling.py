"""
Error handling utilities for LLM backends.

This module provides standardized error handling for LLM backend implementations,
ensuring consistent error messages and logging across different backends.
"""

import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

# Standard error messages
API_KEY_ERROR = "[❌ {provider} API key not set. Please define it in settings.json or as an env var.]"
CONNECTION_ERROR = "[{provider} connection error: {details}]"
RESPONSE_ERROR = "[Error in {provider} response: {details}]"
GENERAL_ERROR = "[{provider} error: {details}]"

def handle_backend_errors(provider_name: str) -> Callable:
    """
    Decorator for handling errors in backend query functions.

    Args:
        provider_name: Name of the LLM provider (e.g., "OpenAI", "Ollama")

    Returns:
        Decorator function that wraps backend query functions with error handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Check for API key if settings are provided
            settings = kwargs.get('settings', {})
            if not settings:
                # Try to get settings from positional args (usually the 4th argument)
                if len(args) >= 4:
                    settings = args[3]

            api_key_name = f"{provider_name.lower()}_api_key"
            if provider_name.lower() != "ollama" and settings and api_key_name in settings and not settings[api_key_name]:
                return API_KEY_ERROR.format(provider=provider_name)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"{provider_name} backend error: {error_msg}")

                if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    return CONNECTION_ERROR.format(provider=provider_name, details=error_msg)
                elif "response" in error_msg.lower():
                    return RESPONSE_ERROR.format(provider=provider_name, details=error_msg)
                else:
                    return GENERAL_ERROR.format(provider=provider_name, details=error_msg)

        return wrapper

    return decorator

def handle_streaming_errors(provider_name: str, stream_func: Callable) -> Callable:
    """
    Wraps a streaming generator function with error handling.

    Args:
        provider_name: Name of the LLM provider
        stream_func: Generator function that yields tokens

    Returns:
        Generator function with error handling
    """
    @wraps(stream_func)
    def wrapper(*args, **kwargs):
        try:
            yield from stream_func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"{provider_name} streaming error: {error_msg}")

            if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                yield CONNECTION_ERROR.format(provider=provider_name, details=error_msg)
            elif "response" in error_msg.lower():
                yield RESPONSE_ERROR.format(provider=provider_name, details=error_msg)
            else:
                yield GENERAL_ERROR.format(provider=provider_name, details=error_msg)

    return wrapper

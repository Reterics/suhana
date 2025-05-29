from enum import Enum
from typing import Optional, Dict, Any, Callable, Type, List
import logging
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Enum representing the severity of errors."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class SuhanaError(Exception):
    """Base exception class for all Suhana-specific errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize a new SuhanaError.

        Args:
            message: Human-readable error message
            severity: Error severity level
            details: Additional error details for debugging
            cause: Original exception that caused this error
        """
        self.message = message
        self.severity = severity
        self.details = details or {}
        self.cause = cause

        # Build the full message
        full_message = message
        if cause:
            full_message += f" | Caused by: {str(cause)}"

        super().__init__(full_message)

# Specific error types
class ConfigurationError(SuhanaError):
    """Error raised when there's an issue with configuration."""
    pass

class BackendError(SuhanaError):
    """Error raised when there's an issue with an LLM backend."""
    pass

class MemoryError(SuhanaError):
    """Error raised when there's an issue with memory operations."""
    pass

class VectorStoreError(SuhanaError):
    """Error raised when there's an issue with vectorstore operations."""
    pass

class ToolError(SuhanaError):
    """Error raised when there's an issue with a tool."""
    pass

class NetworkError(SuhanaError):
    """Error raised when there's a network-related issue."""
    pass

# Error handler registry
_error_handlers: Dict[Type[Exception], List[Callable[[Exception], None]]] = {}

def register_error_handler(
    exception_type: Type[Exception],
    handler: Callable[[Exception], None]
) -> None:
    """
    Register a handler for a specific exception type.

    Args:
        exception_type: The type of exception to handle
        handler: Function that will be called when the exception occurs
    """
    if exception_type not in _error_handlers:
        _error_handlers[exception_type] = []
    _error_handlers[exception_type].append(handler)

def handle_error(error: Exception) -> None:
    """
    Process an error through the appropriate handlers.

    Args:
        error: The exception to handle
    """
    # Log the error
    if isinstance(error, SuhanaError):
        log_level = {
            ErrorSeverity.DEBUG: logging.DEBUG,
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }[error.severity]

        logger.log(log_level, error.message, exc_info=error.cause)
    else:
        logger.error(f"Unhandled exception: {str(error)}", exc_info=error)

    # Find and execute handlers
    for exception_cls, handlers in _error_handlers.items():
        if isinstance(error, exception_cls):
            for handler in handlers:
                try:
                    handler(error)
                except Exception as e:
                    logger.error(f"Error in error handler: {str(e)}", exc_info=e)

def error_boundary(
    fallback_value: Any = None,
    reraise: bool = False,
    error_type: Type[SuhanaError] = SuhanaError,
    error_message: Optional[str] = None
) -> Callable:
    """
    Decorator that creates an error boundary around a function.

    Args:
        fallback_value: Value to return if an error occurs
        reraise: Whether to reraise the error after handling
        error_type: Type of SuhanaError to wrap the original exception in
        error_message: Custom error message (if None, uses the original exception message)

    Returns:
        Decorated function with error handling
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Create a SuhanaError from the original exception
                if not isinstance(e, SuhanaError):
                    message = error_message or f"Error in {func.__name__}: {str(e)}"
                    e = error_type(message, cause=e)

                # Handle the error
                handle_error(e)

                # Reraise or return fallback
                if reraise:
                    raise
                return fallback_value
        return wrapper
    return decorator

def format_error_for_user(error: Exception) -> str:
    """
    Format an error message for display to the user.

    Args:
        error: The exception to format

    Returns:
        User-friendly error message
    """
    if isinstance(error, SuhanaError):
        # For SuhanaError, use the human-readable message
        return f"❌ {error.message}"
    else:
        # For other exceptions, provide a generic message
        return f"❌ An error occurred: {str(error)}"

# Default error handlers
def default_error_handler(error: Exception) -> None:
    """Default handler for all errors."""
    if isinstance(error, SuhanaError) and error.severity.value >= ErrorSeverity.ERROR.value:
        # For severe errors, we might want to send notifications or take recovery actions
        pass

# Register the default handler
register_error_handler(Exception, default_error_handler)

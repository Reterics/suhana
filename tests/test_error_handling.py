import pytest
from unittest.mock import patch, MagicMock

from engine.error_handling import (
    SuhanaError,
    ErrorSeverity,
    BackendError,
    VectorStoreError,
    error_boundary,
    format_error_for_user,
    register_error_handler,
    handle_error
)

def test_suhana_error_basic():
    """Test basic SuhanaError creation and properties."""
    error = SuhanaError("Test error message")

    assert error.message == "Test error message"
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {}
    assert error.cause is None
    assert str(error) == "Test error message"

def test_suhana_error_with_details():
    """Test SuhanaError with details and cause."""
    cause = ValueError("Original error")
    details = {"param": "value", "code": 123}

    error = SuhanaError(
        "Error with details",
        severity=ErrorSeverity.WARNING,
        details=details,
        cause=cause
    )

    assert error.message == "Error with details"
    assert error.severity == ErrorSeverity.WARNING
    assert error.details == details
    assert error.cause is cause
    assert "Error with details" in str(error)
    assert "Original error" in str(error)

def test_specific_error_types():
    """Test that specific error types inherit correctly."""
    from engine.error_handling import (
        ConfigurationError,
        MemoryError,
        ToolError,
        NetworkError
    )

    backend_error = BackendError("Backend failed")
    vector_error = VectorStoreError("Vector store issue")
    config_error = ConfigurationError("Config issue")
    memory_error = MemoryError("Memory issue")
    tool_error = ToolError("Tool issue")
    network_error = NetworkError("Network issue")

    # Test that all error types inherit from SuhanaError
    assert isinstance(backend_error, SuhanaError)
    assert isinstance(vector_error, SuhanaError)
    assert isinstance(config_error, SuhanaError)
    assert isinstance(memory_error, SuhanaError)
    assert isinstance(tool_error, SuhanaError)
    assert isinstance(network_error, SuhanaError)

    # Test that error messages are set correctly
    assert backend_error.message == "Backend failed"
    assert vector_error.message == "Vector store issue"
    assert config_error.message == "Config issue"
    assert memory_error.message == "Memory issue"
    assert tool_error.message == "Tool issue"
    assert network_error.message == "Network issue"

@pytest.fixture
def mock_logger():
    """Mock the logger for testing."""
    with patch("engine.error_handling.logger") as mock:
        yield mock

def test_handle_error_suhana_error(mock_logger):
    """Test that handle_error logs SuhanaError correctly."""
    error = SuhanaError("Test error", severity=ErrorSeverity.ERROR)

    handle_error(error)

    # Verify logger was called with correct level
    mock_logger.log.assert_called_once()
    args, _ = mock_logger.log.call_args
    assert args[0] == 40  # ERROR level

def test_handle_error_standard_exception(mock_logger):
    """Test that handle_error logs standard exceptions correctly."""
    error = ValueError("Standard error")

    handle_error(error)

    # Verify logger.error was called for standard exceptions
    mock_logger.error.assert_called_once()
    args, _ = mock_logger.error.call_args
    assert "Unhandled exception" in args[0]
    assert "Standard error" in args[0]

def test_handle_error_with_handler():
    """Test that registered error handlers are called."""
    handler = MagicMock()
    register_error_handler(SuhanaError, handler)

    error = SuhanaError("Test error")
    handle_error(error)

    handler.assert_called_once_with(error)

def test_handle_error_with_multiple_handlers():
    """Test that multiple handlers for the same exception type are all called."""
    handler1 = MagicMock()
    handler2 = MagicMock()
    handler3 = MagicMock()

    # Register multiple handlers for the same exception type
    register_error_handler(ValueError, handler1)
    register_error_handler(ValueError, handler2)
    register_error_handler(ValueError, handler3)

    error = ValueError("Test multiple handlers")
    handle_error(error)

    # Verify all handlers were called with the error
    handler1.assert_called_once_with(error)
    handler2.assert_called_once_with(error)
    handler3.assert_called_once_with(error)

def test_handle_error_with_failing_handler(mock_logger):
    """Test that handle_error handles exceptions in error handlers."""
    # Create a handler that raises an exception
    handler = MagicMock(side_effect=Exception("Handler failed"))
    register_error_handler(SuhanaError, handler)

    error = SuhanaError("Test error")
    # This should not raise an exception
    handle_error(error)

    # Verify the handler was called
    handler.assert_called_once_with(error)
    # Verify the exception in the handler was logged
    # Note: We don't check the exact number of calls because other tests might affect this
    assert mock_logger.error.called

def test_error_boundary_decorator_no_error():
    """Test that error_boundary passes through when no error occurs."""
    @error_boundary()
    def no_error_func():
        return "success"

    result = no_error_func()
    assert result == "success"

def test_error_boundary_decorator_with_error():
    """Test that error_boundary handles errors and returns fallback."""
    @error_boundary(fallback_value="fallback")
    def error_func():
        raise ValueError("Test error")

    result = error_func()
    assert result == "fallback"

def test_error_boundary_decorator_reraise():
    """Test that error_boundary can reraise errors."""
    @error_boundary(reraise=True)
    def error_func():
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        error_func()

def test_error_boundary_decorator_custom_error_type():
    """Test that error_boundary wraps errors in the specified type."""
    @error_boundary(error_type=BackendError)
    def error_func():
        raise ValueError("Original error")

    # The function should return None (default fallback) and not raise
    result = error_func()
    assert result is None

def test_error_boundary_with_custom_message():
    """Test error_boundary with a custom error message."""
    @error_boundary(error_message="Custom error message")
    def error_func():
        raise ValueError("Original error")

    # Should not raise and return None (default fallback)
    result = error_func()
    assert result is None

def test_error_boundary_with_suhana_error():
    """Test error_boundary when the function raises a SuhanaError directly."""
    @error_boundary(fallback_value="fallback")
    def error_func():
        raise SuhanaError("Direct SuhanaError", severity=ErrorSeverity.WARNING)

    # Should not raise and return the fallback value
    result = error_func()
    assert result == "fallback"

def test_default_error_handler():
    """Test the default error handler."""
    from engine.error_handling import default_error_handler, ErrorSeverity

    # Create errors with different severity levels
    debug_error = SuhanaError("Debug error", severity=ErrorSeverity.DEBUG)
    error = SuhanaError("Error", severity=ErrorSeverity.ERROR)
    critical_error = SuhanaError("Critical error", severity=ErrorSeverity.CRITICAL)

    # These should not raise exceptions
    default_error_handler(debug_error)
    default_error_handler(error)
    default_error_handler(critical_error)

def test_format_error_for_user():
    """Test that format_error_for_user creates user-friendly messages."""
    # For SuhanaError
    error = SuhanaError("Database connection failed")
    message = format_error_for_user(error)
    assert "❌" in message
    assert "Database connection failed" in message

    # For standard exceptions
    std_error = ValueError("Invalid value")
    message = format_error_for_user(std_error)
    assert "❌" in message
    assert "An error occurred" in message
    assert "Invalid value" in message

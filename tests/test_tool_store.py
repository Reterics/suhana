import pytest
from unittest.mock import MagicMock


from engine.tool_store import load_tools, match_and_run_tools

@pytest.fixture
def mock_tool_modules():
    """Mock tool modules for testing."""
    # Create mock modules with different configurations
    mock_modules = {
        "tool1": MagicMock(
            name="weather",
            description="Get weather information",
            pattern=r"what is the weather in (?P<city>\w+)",
            action=lambda input_text, city: f"Weather in {city}: Sunny"
        ),
        "tool2": MagicMock(
            name="calculator",
            description="Calculate expressions",
            pattern=r"calculate (?P<expression>.+)",
            action=lambda input_text, expression: f"Result: {expression}"
        ),
        "tool3": MagicMock(
            # No name attribute, should use file stem
            description="Get current time",
            pattern=r"what time is it",
            action=lambda input_text: "Current time: 12:00 PM"
        ),
        "tool4": MagicMock(
            name="incomplete_tool",
            description="This tool is incomplete",
            pattern=r"incomplete"
            # No action attribute, should be skipped
        ),
        "_hidden": MagicMock(
            name="hidden",
            description="This tool should be hidden",
            pattern=r"hidden",
            action=lambda input_text: "Hidden tool"
        )
    }
    return mock_modules

@pytest.fixture
def mock_tool_files(mock_tool_modules):
    """Mock tool files for testing."""
    # Create mock Path objects for each tool
    mock_files = {
        "tool1.py": MagicMock(stem="tool1", name="tool1.py"),
        "tool2.py": MagicMock(stem="tool2", name="tool2.py"),
        "tool3.py": MagicMock(stem="tool3", name="tool3.py"),
        "tool4.py": MagicMock(stem="tool4", name="tool4.py"),
        "_hidden.py": MagicMock(stem="_hidden", name="_hidden.py")
    }

    # Make the name attribute start with "_" for the hidden tool
    mock_files["_hidden.py"].name = "_hidden.py"

    return mock_files

def test_load_tools():
    """Test loading tools from the tools directory."""
    # Test that load_tools returns a non-empty list of tools
    tools = load_tools()

    # Verify that tools were loaded
    assert len(tools) > 0

    # Verify that each tool has the required attributes
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "pattern" in tool
        assert "action" in tool
        assert callable(tool["action"])

def test_match_and_run_tools_with_mock_tools():
    """Test match_and_run_tools with mock tools."""
    # Create mock tools for testing
    mock_tools = [
        {
            "name": "weather",
            "description": "Get weather information",
            "pattern": r"what is the weather in (?P<city>\w+)",
            "action": lambda input_text, city: f"Weather in {city}: Sunny"
        },
        {
            "name": "calculator",
            "description": "Calculate expressions",
            "pattern": r"calculate (?P<expression>.+)",
            "action": lambda input_text, expression: f"Result: {expression}"
        },
        {
            "name": "time",
            "description": "Get current time",
            "pattern": r"what time is it",
            "action": lambda input_text: "Current time: 12:00 PM"
        }
    ]

    # Test that match_and_run_tools works with our mock tools
    result = match_and_run_tools("what is the weather in London", mock_tools)
    assert result == "Weather in London: Sunny"

    result = match_and_run_tools("calculate 2+2", mock_tools)
    assert result == "Result: 2+2"

    result = match_and_run_tools("what time is it", mock_tools)
    assert result == "Current time: 12:00 PM"

    # Test that no match returns None
    result = match_and_run_tools("this doesn't match any tool", mock_tools)
    assert result is None

def test_match_and_run_tools_match():
    """Test matching and running a tool."""
    # Create a simple tool list
    mock_action = MagicMock(return_value="Tool result")
    tools = [
        {
            "name": "test_tool",
            "description": "Test tool",
            "pattern": r"run test (?P<param>\w+)",
            "action": mock_action
        }
    ]

    # Call the function with matching input
    result = match_and_run_tools("run test parameter", tools)

    # Verify the tool action was called with the correct arguments
    mock_action.assert_called_once()
    args, kwargs = mock_action.call_args
    assert args[0] == "run test parameter"  # input_text
    assert kwargs["param"] == "parameter"  # captured group

    # Verify the result
    assert result == "Tool result"

def test_match_and_run_tools_no_match():
    """Test when no tool matches."""
    # Create a simple tool list
    mock_action = MagicMock(return_value="Tool result")
    tools = [
        {
            "name": "test_tool",
            "description": "Test tool",
            "pattern": r"run test (?P<param>\w+)",
            "action": mock_action
        }
    ]

    # Call the function with non-matching input
    result = match_and_run_tools("this doesn't match", tools)

    # Verify the tool action was not called
    mock_action.assert_not_called()

    # Verify the result is None
    assert result is None

def test_match_and_run_tools_multiple_matches():
    """Test with multiple matching tools (first match should be used)."""
    # Create a tool list with multiple tools that could match
    mock_action1 = MagicMock(return_value="Tool 1 result")
    mock_action2 = MagicMock(return_value="Tool 2 result")
    tools = [
        {
            "name": "tool1",
            "description": "First tool",
            "pattern": r"run (?P<param>\w+)",
            "action": mock_action1
        },
        {
            "name": "tool2",
            "description": "Second tool",
            "pattern": r"run \w+",
            "action": mock_action2
        }
    ]

    # Call the function with input that matches both tools
    result = match_and_run_tools("run parameter", tools)

    # Verify only the first tool action was called
    mock_action1.assert_called_once()
    mock_action2.assert_not_called()

    # Verify the result is from the first tool
    assert result == "Tool 1 result"

def test_match_and_run_tools_case_insensitive():
    """Test that pattern matching is case-insensitive."""
    # Create a tool with an uppercase pattern
    mock_action = MagicMock(return_value="Tool result")
    tools = [
        {
            "name": "test_tool",
            "description": "Test tool",
            "pattern": r"RUN TEST (?P<param>\w+)",
            "action": mock_action
        }
    ]

    # Call the function with lowercase input
    result = match_and_run_tools("run test parameter", tools)

    # Verify the tool action was called
    mock_action.assert_called_once()

    # Verify the result
    assert result == "Tool result"

import pytest
from unittest.mock import patch
from tools.web_search import action

@pytest.fixture
def mock_search_results():
    """Mock search results for different engines"""
    with patch('tools.web_search.duckduckgo') as mock_duckduckgo, \
         patch('tools.web_search.bing') as mock_bing, \
         patch('tools.web_search.brave') as mock_brave:

        # Configure mocks to return different results for each engine
        mock_duckduckgo.return_value = [
            "DuckDuckGo result 1",
            "DuckDuckGo result 2",
            "DuckDuckGo result 3"
        ]

        mock_bing.return_value = [
            "Bing result 1",
            "Bing result 2",
            "Bing result 3"
        ]

        mock_brave.return_value = [
            "Brave result 1",
            "Brave result 2",
            "Brave result 3"
        ]

        yield

@pytest.mark.expensive
def test_web_search_default_engine(mock_search_results):
    """Test web search with default engine (duckduckgo)"""
    result = action("search for python programming", "python programming")

    # Check that the result contains DuckDuckGo results
    assert "Here's what I found about 'python programming'" in result
    assert "DuckDuckGo result 1" in result
    assert "DuckDuckGo result 2" in result
    assert "DuckDuckGo result 3" in result

@pytest.mark.expensive
def test_web_search_duckduckgo_explicit(mock_search_results):
    """Test web search with explicitly specified duckduckgo engine"""
    result = action(
        "search with duckduckgo for python programming",
        "python programming",
        engine="duckduckgo"
    )

    # Check that the result contains DuckDuckGo results
    assert "Here's what I found about 'python programming'" in result
    assert "DuckDuckGo result 1" in result
    assert "DuckDuckGo result 2" in result
    assert "DuckDuckGo result 3" in result

@pytest.mark.expensive
def test_web_search_bing(mock_search_results):
    """Test web search with bing engine"""
    result = action(
        "search with bing for python programming",
        "python programming",
        engine="bing"
    )

    # Check that the result contains Bing results
    assert "Here's what I found about 'python programming'" in result
    assert "Bing result 1" in result
    assert "Bing result 2" in result
    assert "Bing result 3" in result

@pytest.mark.expensive
def test_web_search_brave(mock_search_results):
    """Test web search with brave engine"""
    result = action(
        "search with brave for python programming",
        "python programming",
        engine="brave"
    )

    # Check that the result contains Brave results
    assert "Here's what I found about 'python programming'" in result
    assert "Brave result 1" in result
    assert "Brave result 2" in result
    assert "Brave result 3" in result

@pytest.mark.expensive
def test_web_search_empty_query(mock_search_results):
    """Test web search with empty query"""
    result = action("search for ", "")
    assert "I need something to search for" in result

@pytest.mark.expensive
def test_web_search_no_results():
    """Test web search with no results"""
    with patch('tools.web_search.duckduckgo', return_value=[]):
        result = action("search for nonexistent", "nonexistent")
        assert "I searched, but couldn't find anything useful" in result

@pytest.mark.expensive
def test_web_search_error():
    """Test web search with error"""
    with patch('tools.web_search.duckduckgo', side_effect=Exception("Test error")):
        result = action("search for python", "python")
        assert "Web search failed: Test error" in result

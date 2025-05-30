import pytest
from unittest.mock import patch, MagicMock

from tools.web_search import action, duckduckgo, bing, brave

class MockResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")

@pytest.fixture
def mock_duckduckgo_html():
    return """
    <html>
        <div class="result__snippet">First result snippet</div>
        <div class="result__snippet">Second result snippet</div>
        <div class="result__snippet">Third result snippet</div>
        <div class="result__snippet">Fourth result snippet</div>
    </html>
    """

@pytest.fixture
def mock_bing_html():
    return """
    <html>
        <li class="b_algo">
            <h2>Title 1</h2>
            <p>First result snippet</p>
        </li>
        <li class="b_algo">
            <h2>Title 2</h2>
            <p>Second result snippet</p>
        </li>
        <li class="b_algo">
            <h2>Title 3</h2>
            <p>Third result snippet</p>
        </li>
    </html>
    """

@pytest.fixture
def mock_brave_html():
    return """
    <html>
        <div class="snippet-description">First result snippet</div>
        <div class="snippet-description">Second result snippet</div>
        <div class="snippet-description">Third result snippet</div>
    </html>
    """

@pytest.fixture
def mock_empty_html():
    return "<html></html>"

def test_duckduckgo_search(mock_duckduckgo_html):
    with patch('tools.web_search.get') as mock_get:
        mock_get.return_value = MockResponse(mock_duckduckgo_html)
        results = duckduckgo("test query")

        mock_get.assert_called_once()
        assert len(results) == 4
        assert results[0] == "First result snippet"
        assert results[1] == "Second result snippet"

def test_bing_search(mock_bing_html):
    with patch('tools.web_search.get') as mock_get:
        mock_get.return_value = MockResponse(mock_bing_html)
        results = bing("test query")

        mock_get.assert_called_once()
        assert len(results) == 3
        assert results[0] == "First result snippet"
        assert results[1] == "Second result snippet"

def test_brave_search(mock_brave_html):
    with patch('tools.web_search.get') as mock_get:
        mock_get.return_value = MockResponse(mock_brave_html)
        results = brave("test query")

        mock_get.assert_called_once()
        assert len(results) == 3
        assert results[0] == "First result snippet"
        assert results[1] == "Second result snippet"

def test_action_with_duckduckgo():
    with patch('tools.web_search.duckduckgo') as mock_duckduckgo:
        mock_duckduckgo.return_value = ["Result 1", "Result 2", "Result 3"]
        result = action("search for", "python programming", "duckduckgo")

        mock_duckduckgo.assert_called_once_with("python programming")
        assert "Here's what I found about 'python programming'" in result
        assert "- Result 1" in result
        assert "- Result 2" in result
        assert "- Result 3" in result

def test_action_with_bing():
    with patch('tools.web_search.bing') as mock_bing:
        mock_bing.return_value = ["Result 1", "Result 2"]
        result = action("search for", "python programming", "bing")

        mock_bing.assert_called_once_with("python programming")
        assert "Here's what I found about 'python programming'" in result
        assert "- Result 1" in result
        assert "- Result 2" in result

def test_action_with_brave():
    with patch('tools.web_search.brave') as mock_brave:
        mock_brave.return_value = ["Result 1", "Result 2", "Result 3", "Result 4"]
        result = action("search for", "python programming", "brave")

        mock_brave.assert_called_once_with("python programming")
        assert "Here's what I found about 'python programming'" in result
        # Should only include the first 3 results
        assert "- Result 1" in result
        assert "- Result 2" in result
        assert "- Result 3" in result
        assert "- Result 4" not in result

def test_action_with_default_engine():
    with patch('tools.web_search.duckduckgo') as mock_duckduckgo:
        mock_duckduckgo.return_value = ["Result 1", "Result 2"]
        # No engine specified, should default to duckduckgo
        result = action("search for", "python programming")

        mock_duckduckgo.assert_called_once_with("python programming")
        assert "Here's what I found about 'python programming'" in result

def test_action_with_unknown_engine():
    with patch('tools.web_search.duckduckgo') as mock_duckduckgo:
        mock_duckduckgo.return_value = ["Result 1", "Result 2"]
        # Unknown engine, should default to duckduckgo
        result = action("search for", "python programming", "unknown")

        mock_duckduckgo.assert_called_once_with("python programming")
        assert "Here's what I found about 'python programming'" in result

def test_action_with_empty_query():
    result = action("search for", "")
    assert "I need something to search for." in result

def test_action_with_no_results():
    with patch('tools.web_search.duckduckgo') as mock_duckduckgo:
        mock_duckduckgo.return_value = []
        result = action("search for", "python programming")

        mock_duckduckgo.assert_called_once_with("python programming")
        assert "I searched, but couldn't find anything useful" in result

def test_action_with_exception():
    with patch('tools.web_search.duckduckgo') as mock_duckduckgo:
        mock_duckduckgo.side_effect = Exception("Connection error")
        result = action("search for", "python programming")

        mock_duckduckgo.assert_called_once_with("python programming")
        assert "Web search failed: Connection error" in result

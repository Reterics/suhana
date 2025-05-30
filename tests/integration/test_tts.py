import sys
import pytest
from engine import voice

@pytest.mark.expensive
def test_speak_text():
    """Test the speak_text function with a simple text input."""
    print("Testing speak_text function...")
    try:
        voice.speak_text("Hello, this is a test of the text-to-speech functionality.")
        print("✅ Test passed! The text was successfully converted to speech.")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_speak_text()

import unittest
from engine.agent_core import handle_input
from engine.profile import load_profile
from engine.engine_config import load_settings

class TestAgentCore(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile()
        self.settings = load_settings()
        self.name = "Suhana"

    def test_handle_input_openai(self):
        if self.settings.get("openai_api_key"):
            reply = handle_input("What is Suhana?", "openai", self.profile, self.settings)
            self.assertIsInstance(reply, str)
            self.assertGreater(len(reply), 0)
        else:
            print("⚠️ Skipping OpenAI test — API key not set.")

    def test_handle_input_ollama(self):
        if self.settings.get("llm_model"):
            reply = handle_input("Who are you?", "ollama", self.profile, self.settings)
            self.assertIsInstance(reply, str)
            self.assertGreater(len(reply), 0)
        else:
            print("⚠️ Skipping Ollama test — model not set.")

if __name__ == '__main__':
    unittest.main()

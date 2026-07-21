import unittest
from unittest.mock import MagicMock, patch
import os

from src.policy.models import AccountPolicy
from src.llm.generator import GeminiKeyRotator, LLMGenerator
from google.api_core.exceptions import ResourceExhausted

class TestLLMGenerator(unittest.TestCase):
    def setUp(self):
        # Sample policy for testing
        self.policy = AccountPolicy(
            account_id="test_account",
            goal="Write simple test tips.",
            constraints=["Length must be under 200 characters.", "Exactly 1 hashtag."],
            examples=["This is a test post #test"],
            rubric=["Clear tip.", "Under 200 chars."],
            threshold=0.8,
            model_route="gemini-1.5-flash"
        )

    def test_rotator_initialization_default(self):
        # Clear env variables to ensure there are no keys
        if "GEMINI_API_KEYS" in os.environ:
            del os.environ["GEMINI_API_KEYS"]
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
            
        with patch("os.path.exists", return_value=False):
            rotator = GeminiKeyRotator()
            self.assertEqual(len(rotator.keys), 0)
            with self.assertRaises(ValueError):
                rotator.get_key()

    def test_rotator_initialization_env_keys(self):
        os.environ["GEMINI_API_KEYS"] = "key1,key2;key3"
        rotator = GeminiKeyRotator()
        self.assertEqual(len(rotator.keys), 3)
        self.assertIn("key1", rotator.keys)
        self.assertIn("key2", rotator.keys)
        self.assertIn("key3", rotator.keys)
        
        # Clean up
        del os.environ["GEMINI_API_KEYS"]

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_generate_draft_success(self, mock_configure, mock_model_class):
        mock_response = MagicMock()
        mock_response.text = "Hello world! #test"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 20
        
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        rotator = GeminiKeyRotator()
        # Mock keys to keep it simple
        rotator.keys = ["keyA"]
        rotator.current_idx = 0
        
        generator = LLMGenerator(rotator)
        content, usage = generator.generate_draft(self.policy)
        
        self.assertEqual(content, "Hello world! #test")
        self.assertEqual(usage["prompt_tokens"], 100)
        self.assertEqual(usage["completion_tokens"], 20)
        mock_configure.assert_called_with(api_key="keyA")

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_generate_draft_rotation_on_rate_limit(self, mock_configure, mock_model_class):
        # First key call raises ResourceExhausted, second key call succeeds
        mock_response = MagicMock()
        mock_response.text = "Success on rotated key! #test"
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 10

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = [ResourceExhausted("Rate limited"), mock_response]
        mock_model_class.return_value = mock_model

        rotator = GeminiKeyRotator()
        rotator.keys = ["key1", "key2"]
        rotator.current_idx = 0

        generator = LLMGenerator(rotator)
        content, usage = generator.generate_draft(self.policy)

        self.assertEqual(content, "Success on rotated key! #test")
        self.assertEqual(rotator.current_idx, 1) # Checked that it rotated
        mock_configure.assert_any_call(api_key="key1")
        mock_configure.assert_any_call(api_key="key2")

if __name__ == "__main__":
    unittest.main()

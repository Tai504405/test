import unittest
from unittest.mock import MagicMock, patch
import os

from src.policy.models import AccountPolicy
from src.llm.generator import (
    GeminiKeyRotator,
    GroqKeyRotator,
    AIResearchAgent,
    AICopywriterAgent,
    AILLMCriticAgent
)

class TestThreeAgentSystem(unittest.TestCase):
    def setUp(self):
        # Sample policy for testing
        self.policy = AccountPolicy(
            account_id="test_account",
            goal="Write simple test tips.",
            constraints=["Length must be under 200 characters.", "Exactly 1 hashtag."],
            examples=["This is a test post #test"],
            rubric=["Clear tip.", "Under 200 chars."],
            threshold=0.8,
            model_route="gemini-3.5-flash"
        )

    def test_gemini_rotator_init(self):
        # Clear env variables to ensure there are no keys
        if "GEMINI_API_KEYS" in os.environ:
            del os.environ["GEMINI_API_KEYS"]
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
            
        with patch("os.path.exists", return_value=False):
            rotator = GeminiKeyRotator()
            self.assertEqual(len(rotator.keys), 0)

    def test_groq_rotator_init(self):
        os.environ["GROQ_API_KEYS"] = "groq1,groq2"
        rotator = GroqKeyRotator()
        self.assertEqual(len(rotator.keys), 2)
        self.assertIn("groq1", rotator.keys)
        del os.environ["GROQ_API_KEYS"]

    @patch("src.llm.generator.call_gemini_api")
    def test_research_agent_success(self, mock_call_gemini):
        mock_call_gemini.return_value = ("Research Brief Content", {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.0001})
        
        rotator = MagicMock()
        agent = AIResearchAgent(rotator)
        brief, usage = agent.generate_brief("Test Topic", self.policy)
        
        self.assertEqual(brief, "Research Brief Content")
        self.assertEqual(usage["prompt_tokens"], 10)
        mock_call_gemini.assert_called_once()

    @patch("src.llm.generator.call_groq_api")
    def test_copywriter_groq_success(self, mock_call_groq):
        mock_call_groq.return_value = ("Groq Post Content", {"prompt_tokens": 15, "completion_tokens": 25, "cost": 0.0002})
        
        groq_rotator = MagicMock()
        groq_rotator.get_key.return_value = "groq_key"
        
        agent = AICopywriterAgent(groq_rotator=groq_rotator)
        content, usage = agent.write_post("Some Brief", self.policy)
        
        self.assertEqual(content, "Groq Post Content")
        mock_call_groq.assert_called_once()

    @patch("src.llm.generator.call_gemini_api")
    @patch("src.llm.generator.call_groq_api")
    def test_copywriter_fallback_to_gemini(self, mock_call_groq, mock_call_gemini):
        # Groq raises exception, Gemini succeeds
        mock_call_groq.side_effect = Exception("Groq failed")
        mock_call_gemini.return_value = ("Gemini Fallback Content", {"prompt_tokens": 20, "completion_tokens": 30, "cost": 0.0003})
        
        groq_rotator = MagicMock()
        groq_rotator.get_key.return_value = "groq_key"
        groq_rotator.keys = ["groq_key"]
        
        agent = AICopywriterAgent(groq_rotator=groq_rotator)
        content, usage = agent.write_post("Some Brief", self.policy)
        
        self.assertEqual(content, "Gemini Fallback Content")
        mock_call_groq.assert_called_once()
        mock_call_gemini.assert_called_once()

    @patch("src.llm.generator.call_github_models_api")
    def test_critic_github_success(self, mock_call_github):
        mock_call_github.return_value = ('{"score": 0.92, "criticism": "Good post!"}', {"prompt_tokens": 30, "completion_tokens": 40, "cost": 0.0004})
        
        agent = AILLMCriticAgent(github_token="github_token")
        score, criticism, usage = agent.critic_post("Draft Content", self.policy)
        
        self.assertEqual(score, 0.92)
        self.assertEqual(criticism, "Good post!")
        mock_call_github.assert_called_once()

    @patch("src.llm.generator.call_gemini_api")
    @patch("src.llm.generator.call_github_models_api")
    def test_critic_fallback_to_gemini(self, mock_call_github, mock_call_gemini):
        # GitHub raises exception, Gemini succeeds
        mock_call_github.side_effect = Exception("GitHub Models failed")
        mock_call_gemini.return_value = ('{"score": 0.82, "criticism": "Gemini review!"}', {"prompt_tokens": 35, "completion_tokens": 45, "cost": 0.0005})
        
        agent = AILLMCriticAgent(github_token="github_token")
        score, criticism, usage = agent.critic_post("Draft Content", self.policy)
        
        self.assertEqual(score, 0.82)
        self.assertEqual(criticism, "Gemini review!")
        mock_call_github.assert_called_once()
        mock_call_gemini.assert_called_once()

if __name__ == "__main__":
    unittest.main()

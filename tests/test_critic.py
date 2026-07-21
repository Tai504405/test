import unittest
from src.policy.parser import parse_policy_md
from src.critic.rule_critic import RuleCritic

class TestRuleCritic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load sample policies
        cls.threads_policy = parse_policy_md("accounts/threads_10xlab.md")
        cls.facebook_policy = parse_policy_md("accounts/facebook_tech.md")
        cls.x_policy = parse_policy_md("accounts/x_dev.md")

    def test_threads_valid_post(self):
        critic = RuleCritic(self.threads_policy)
        post = "Just spent 3 hours refactoring a Python script into a Go tool. Speedup is real, but was it worth the time? Definitely. #devlife"
        result = critic.check(post)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)

    def test_threads_too_short(self):
        critic = RuleCritic(self.threads_policy)
        post = "Short post."  # Length 11 < 100
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LENGTH_TOO_SHORT", result.violation_codes)
        self.assertTrue(any("quá ngắn" in v for v in result.violations))

    def test_threads_too_long(self):
        critic = RuleCritic(self.threads_policy)
        post = "A" * 501  # Length 501 > 500
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LENGTH_TOO_LONG", result.violation_codes)

    def test_threads_banned_words(self):
        critic = RuleCritic(self.threads_policy)
        # Check first banned word: "synergy"
        post = "We need to drive synergy across all dev teams in the organization. #productivity"
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("BANNED_WORD_PRESENT", result.violation_codes)
        self.assertTrue(any("synergy" in v for v in result.violations))

        # Check second banned word: "paradigm shift"
        post2 = "This new framework is a paradigm shift for web development. Let's build something today."
        result2 = critic.check(post2)
        self.assertFalse(result2.passed)
        self.assertIn("BANNED_WORD_PRESENT", result2.violation_codes)
        self.assertTrue(any("paradigm shift" in v for v in result2.violations))

    def test_threads_too_many_hashtags(self):
        critic = RuleCritic(self.threads_policy)
        post = "Refactoring Python code is fun. Let's make it clean and fast! We want to make sure it is super optimized and handles all edge cases perfectly. #python #clean #refactor" # 3 hashtags
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_MANY_HASHTAGS", result.violation_codes)

    def test_threads_disallow_links(self):
        critic = RuleCritic(self.threads_policy)
        post = "Check out our new tool to improve developer productivity at https://10xlab.ai. It is awesome and saves hours of manual work."
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LINKS_NOT_ALLOWED", result.violation_codes)

    def test_facebook_valid_post(self):
        critic = RuleCritic(self.facebook_policy)
        post = (
            "Have you ever wondered how databases handle concurrent writes without messing up your data? "
            "It comes down to ACID transactions. Specifically, Isolation levels like Read Committed or Serializable. "
            "Let's break them down today. Isolation levels control the visibility of changes made by one transaction to other concurrent transactions. "
            "Higher isolation levels reduce concurrency anomalies but increase contention and lock waits.\n"
            "What isolation level do you use in your production databases?"
        )
        result = critic.check(post)
        self.assertTrue(result.passed)

    def test_facebook_too_short(self):
        critic = RuleCritic(self.facebook_policy)
        post = "Short educational tip about databases." # length 37 < 300
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LENGTH_TOO_SHORT", result.violation_codes)

    def test_x_valid_post(self):
        critic = RuleCritic(self.x_policy)
        post = "Python tip: Use `zip(strict=True)` in Python 3.10+ to catch mismatched list lengths. #python 🚀"
        result = critic.check(post)
        self.assertTrue(result.passed)

    def test_x_too_many_emojis(self):
        critic = RuleCritic(self.x_policy)
        post = "Python tip: Use `zip(strict=True)`! #python 🚀🐍" # 2 emojis
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_MANY_EMOJIS", result.violation_codes)

    def test_x_no_hashtags(self):
        critic = RuleCritic(self.x_policy)
        post = "Python tip: Use `zip(strict=True)` in Python 3.10+ to catch mismatched list lengths."
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_FEW_HASHTAGS", result.violation_codes)

    def test_x_too_many_hashtags(self):
        critic = RuleCritic(self.x_policy)
        post = "Python tip: Use `zip(strict=True)` in Python 3.10+! #python #programming"
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_MANY_HASHTAGS", result.violation_codes)

    def test_vietnamese_characters_ignored_by_emoji_check(self):
        critic = RuleCritic(self.x_policy)
        # Vietnamese text with accents should NOT count as emojis
        post = "Mẹo Python: Sử dụng zip(strict=True) trong Python 3.10+ giúp bắt lỗi độ dài danh sách. #python"
        result = critic.check(post)
        # Verify no emoji count violations
        self.assertTrue(result.passed)

if __name__ == "__main__":
    unittest.main()

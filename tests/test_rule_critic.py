import unittest
from src.policy.parser import parse_policy_md
from src.critic.rule_critic import RuleCritic

class TestRuleCritic(unittest.TestCase):
    """Lớp kiểm thử cho bộ lọc luật cứng RuleCritic."""

    @classmethod
    def setUpClass(cls):
        # Tải các chính sách mẫu để chạy kiểm thử
        cls.threads_policy = parse_policy_md("accounts/threads_10xlab.md")
        cls.facebook_policy = parse_policy_md("accounts/facebook_tech.md")
        cls.x_policy = parse_policy_md("accounts/x_dev.md")

    def test_threads_valid_post(self):
        """Kiểm tra bài viết hợp lệ cho Threads (độ dài và hashtag đều đúng)."""
        critic = RuleCritic(self.threads_policy)
        post = "Just spent 3 hours refactoring a Python script into a Go tool. Speedup is real, but was it worth the time? Definitely. #devlife"
        result = critic.check(post)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)

    def test_threads_too_short(self):
        """Kiểm tra bài viết quá ngắn cho Threads (< 100 ký tự)."""
        critic = RuleCritic(self.threads_policy)
        post = "Short post."
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LENGTH_TOO_SHORT", result.violation_codes)

    def test_threads_too_long(self):
        """Kiểm tra bài viết quá dài cho Threads (> 500 ký tự)."""
        critic = RuleCritic(self.threads_policy)
        post = "A" * 501
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LENGTH_TOO_LONG", result.violation_codes)

    def test_threads_banned_words(self):
        """Kiểm tra phát hiện từ bị cấm (như 'synergy' và 'paradigm shift')."""
        critic = RuleCritic(self.threads_policy)
        
        # Test từ cấm 'synergy'
        post_synergy = "We need to drive synergy across all dev teams. #productivity"
        result_synergy = critic.check(post_synergy)
        self.assertFalse(result_synergy.passed)
        self.assertIn("BANNED_WORD_PRESENT", result_synergy.violation_codes)
        
        # Test từ cấm 'paradigm shift' dạng chữ thường/chữ hoa hỗn hợp
        post_shift = "This is a Paradigm Shift for our team."
        result_shift = critic.check(post_shift)
        self.assertFalse(result_shift.passed)
        self.assertIn("BANNED_WORD_PRESENT", result_shift.violation_codes)

    def test_threads_too_many_hashtags(self):
        """Kiểm tra Threads không được dùng quá 2 hashtags."""
        critic = RuleCritic(self.threads_policy)
        post = "Refactoring python is very fun. Let's make it fast! #python #clean #refactor" # 3 hashtags
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_MANY_HASHTAGS", result.violation_codes)

    def test_threads_links_not_allowed(self):
        """Kiểm tra Threads không được chứa liên kết."""
        critic = RuleCritic(self.threads_policy)
        post = "Check out our tool at https://10xlab.ai to improve productivity."
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("LINKS_NOT_ALLOWED", result.violation_codes)

    def test_x_too_many_emojis(self):
        """Kiểm tra kênh X/Twitter giới hạn tối đa 1 emoji."""
        critic = RuleCritic(self.x_policy)
        post = "Python tip: Use zip(strict=True)! #python 🚀🐍" # 2 emojis
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_MANY_EMOJIS", result.violation_codes)

    def test_x_no_hashtags(self):
        """Kiểm tra kênh X/Twitter yêu cầu chính xác 1 hashtag."""
        critic = RuleCritic(self.x_policy)
        post = "Python tip: Use zip(strict=True) to match list lengths." # 0 hashtags
        result = critic.check(post)
        self.assertFalse(result.passed)
        self.assertIn("TOO_FEW_HASHTAGS", result.violation_codes)

    def test_vietnamese_text_does_not_trigger_emoji_check(self):
        """Đảm bảo chữ tiếng Việt có dấu không bị nhận nhầm là emoji."""
        critic = RuleCritic(self.x_policy)
        post = "Mẹo lập trình Python cực kỳ hữu ích cho lập trình viên. #python"
        result = critic.check(post)
        self.assertTrue(result.passed)

if __name__ == "__main__":
    unittest.main()

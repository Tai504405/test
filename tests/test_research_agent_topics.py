import unittest
import json
from unittest.mock import MagicMock, patch
from src.policy.models import AccountPolicy
from src.llm.generator import AIResearchAgent

class TestAIResearchAgentModes(unittest.TestCase):
    """Bộ kiểm thử unit test cho AIResearchAgent với 2 chế độ xử lý đề tài (Topic)."""

    def setUp(self):
        self.policy = AccountPolicy(
            account_id="facebook_tech",
            goal="Chia sẻ kiến thức thiết kế hệ thống và lập trình Python",
            constraints=["Length must be between 300 and 1500 characters."],
            examples=["Example post 1"],
            rubric=["Educational depth"],
            threshold=0.75,
            model_route="gemini-3.1-flash-lite"
        )
        self.agent = AIResearchAgent()

    @patch("src.llm.generator.call_gemini_api")
    def test_mode1_auto_discover_topic(self, mock_gemini_call):
        """Kiểm thử Chế độ 1: Tự động tìm đề tài khi topic=None."""
        mock_json_response = json.dumps({
            "topic": "Thiết kế Cấu trúc Database cho Hệ thống E-commerce",
            "target_audience": "Lập trình viên Backend và System Architect",
            "main_points": [
                "Phân tách DB đọc và ghi (Read/Write Splitting)",
                "Chiến lược Caching với Redis để giảm tải Database",
                "Áp dụng Isolation Level trong giao dịch ACID"
            ],
            "angle": "Thực tiễn, chuyên sâu và súc tích"
        })
        mock_gemini_call.return_value = (mock_json_response, {"prompt_tokens": 100, "completion_tokens": 80, "cost": 0.0001})

        # Chạy Chế độ 1: topic=None
        content, usage = self.agent.generate_brief(topic=None, policy=self.policy)
        
        # Kiểm tra nội dung JSON nhận được
        data = json.loads(content)
        
        # Kiểm tra đầy đủ 4 trường thông tin bắt buộc
        self.assertIn("topic", data)
        self.assertIn("target_audience", data)
        self.assertIn("main_points", data)
        self.assertIn("angle", data)
        self.assertTrue(len(data["topic"]) > 0)
        self.assertTrue(len(data["main_points"]) >= 1)

    @patch("src.llm.generator.call_gemini_api")
    def test_mode2_manual_topic(self, mock_gemini_call):
        """Kiểm thử Chế độ 2: Truyền đề tài thủ công khi topic có giá trị."""
        manual_topic = "Tối ưu hóa Docker cho lập trình viên Python"
        mock_json_response = json.dumps({
            "topic": manual_topic,
            "target_audience": "Lập trình viên Python sử dụng Docker",
            "main_points": [
                "Sử dụng multi-stage builds để giảm kích thước image",
                "Tối ưu layer caching cho requirements.txt",
                "Tránh chạy container dưới quyền root"
            ],
            "angle": "Hướng dẫn thực hành từng bước"
        })
        mock_gemini_call.return_value = (mock_json_response, {"prompt_tokens": 120, "completion_tokens": 90, "cost": 0.00015})

        # Chạy Chế độ 2: Truyền đề tài thủ công
        content, usage = self.agent.generate_brief(topic=manual_topic, policy=self.policy)
        
        # Kiểm tra nội dung JSON nhận được
        data = json.loads(content)
        
        # Kiểm tra đề tài phải khớp đúng 100% với đề tài truyền vào
        self.assertEqual(data["topic"], manual_topic)
        self.assertIn("target_audience", data)
        self.assertIn("main_points", data)
        self.assertIn("angle", data)

if __name__ == "__main__":
    unittest.main()

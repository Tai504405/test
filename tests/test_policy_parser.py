import unittest
import tempfile
import os
from src.policy.parser import parse_policy_md
from src.policy.models import AccountPolicy, PolicyValidationError

class TestPolicyParser(unittest.TestCase):
    """Lớp kiểm thử cho bộ đọc chính sách (Policy Parser)."""

    def test_parse_valid_x_policy(self):
        """Kiểm tra việc parse một file cấu hình hợp lệ của kênh x_dev."""
        policy = parse_policy_md("accounts/x_dev.md")
        self.assertEqual(policy.account_id, "x_dev")
        self.assertEqual(policy.threshold, 0.85)
        self.assertEqual(policy.model_route, "gemini-3.5-flash")
        self.assertTrue(len(policy.constraints) > 0)
        self.assertTrue(len(policy.examples) > 0)
        self.assertTrue(len(policy.rubric) > 0)

    def test_parse_valid_facebook_policy(self):
        """Kiểm tra việc parse một file cấu hình hợp lệ của facebook_tech."""
        policy = parse_policy_md("accounts/facebook_tech.md")
        self.assertEqual(policy.account_id, "facebook_tech")
        self.assertEqual(policy.threshold, 0.75)
        self.assertEqual(policy.model_route, "gemini-3.5-flash")

    def test_missing_file_error(self):
        """Kiểm tra trường hợp file không tồn tại, phải ném ra lỗi PolicyValidationError."""
        with self.assertRaises(PolicyValidationError) as ctx:
            parse_policy_md("accounts/non_existent_file.md")
        self.assertIn("Policy file not found", str(ctx.exception))

    def test_empty_file_error(self):
        """Kiểm tra trường hợp file rỗng không có nội dung."""
        content = ""
        self._assert_validation_error(content, "The policy file is empty")

    def test_missing_main_header_error(self):
        """Kiểm tra trường hợp thiếu tiêu đề chính (# Policy: ...)"""
        content = """Threshold: 0.8
Model Route: gemini-1.5-flash

## Goal
Some goal description.

## Constraints
- Rule 1

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "Missing main account header")

    def test_missing_threshold_error(self):
        """Kiểm tra lỗi thiếu trường Threshold."""
        content = """# Policy: test_account
Model Route: gemini-1.5-flash

## Goal
Some goal description.

## Constraints
- Rule 1

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "Missing 'Threshold' metadata")

    def test_invalid_threshold_error(self):
        """Kiểm tra lỗi giá trị Threshold không hợp lệ."""
        content = """# Policy: test_account
Threshold: invalid_number
Model Route: gemini-1.5-flash

## Goal
Some goal description.

## Constraints
- Rule 1

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "Invalid 'Threshold' value")

    def test_missing_model_route_error(self):
        """Kiểm tra lỗi thiếu Model Route."""
        content = """# Policy: test_account
Threshold: 0.8

## Goal
Some goal description.

## Constraints
- Rule 1

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "Missing 'Model Route' metadata")

    def test_missing_goal_section_error(self):
        """Kiểm tra lỗi thiếu phần Goal."""
        content = """# Policy: test_account
Threshold: 0.8
Model Route: gemini-1.5-flash

## Constraints
- Rule 1

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "Missing required section '## Goal'")

    def test_empty_goal_section_error(self):
        """Kiểm tra lỗi phần Goal trống."""
        content = """# Policy: test_account
Threshold: 0.8
Model Route: gemini-1.5-flash

## Goal

## Constraints
- Rule 1

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "The '## Goal' section is empty")

    def test_empty_constraints_list_error(self):
        """Kiểm tra lỗi phần Constraints không có danh sách phần tử hợp lệ."""
        content = """# Policy: test_account
Threshold: 0.8
Model Route: gemini-1.5-flash

## Goal
Goal description.

## Constraints

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "The '## Constraints' section does not contain any valid list items")

    def _assert_validation_error(self, content: str, expected_message: str):
        """Hàm hỗ trợ ghi nội dung vào file tạm và kiểm tra lỗi kiểm chứng."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md", encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name
        try:
            with self.assertRaises(PolicyValidationError) as ctx:
                parse_policy_md(temp_path)
            self.assertIn(expected_message, str(ctx.exception))
        finally:
            os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()

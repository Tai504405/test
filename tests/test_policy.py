import unittest
import tempfile
import os
from src.policy.parser import parse_policy_md
from src.policy.models import AccountPolicy, PolicyValidationError

class TestPolicyParser(unittest.TestCase):
    def test_parse_valid_threads_policy(self):
        policy = parse_policy_md("accounts/threads_10xlab.md")
        self.assertEqual(policy.account_id, "threads_10xlab")
        self.assertEqual(policy.threshold, 0.8)
        self.assertEqual(policy.model_route, "gemini-1.5-flash")
        self.assertTrue(len(policy.constraints) > 0)
        self.assertTrue(len(policy.examples) > 0)
        self.assertTrue(len(policy.rubric) > 0)
        self.assertIn("productivity", policy.goal.lower())

    def test_parse_valid_facebook_policy(self):
        policy = parse_policy_md("accounts/facebook_tech.md")
        self.assertEqual(policy.account_id, "facebook_tech")
        self.assertEqual(policy.threshold, 0.75)
        self.assertEqual(policy.model_route, "gemini-1.5-pro")

    def test_parse_valid_x_policy(self):
        policy = parse_policy_md("accounts/x_dev.md")
        self.assertEqual(policy.account_id, "x_dev")
        self.assertEqual(policy.threshold, 0.85)
        self.assertEqual(policy.model_route, "gemini-1.5-flash")

    def test_missing_file(self):
        with self.assertRaises(PolicyValidationError) as ctx:
            parse_policy_md("accounts/non_existent_file.md")
        self.assertIn("Policy file not found", str(ctx.exception))

    def test_missing_main_header(self):
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

    def test_missing_threshold(self):
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

    def test_invalid_threshold(self):
        content = """# Policy: test_account
Threshold: not_a_number
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

    def test_missing_model_route(self):
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

    def test_missing_goal_section(self):
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

    def test_empty_goal_section(self):
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

    def test_empty_list_constraints(self):
        content = """# Policy: test_account
Threshold: 0.8
Model Route: gemini-1.5-flash

## Goal
Some goal description.

## Constraints

## Examples
- Ex 1

## Rubric
- Rubric 1
"""
        self._assert_validation_error(content, "The '## Constraints' section does not contain any valid list items")

    def test_different_bullet_styles(self):
        content = """# Policy: test_bullets
Threshold: 0.90
Model Route: gpt-4o

## Goal
This is a goal description.

## Constraints
* Constraint 1
+ Constraint 2
- Constraint 3

## Examples
- Example 1

## Rubric
- Rubric 1
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md", encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name
        try:
            policy = parse_policy_md(temp_path)
            self.assertEqual(policy.account_id, "test_bullets")
            self.assertEqual(policy.constraints, ["Constraint 1", "Constraint 2", "Constraint 3"])
        finally:
            os.remove(temp_path)

    def _assert_validation_error(self, content: str, expected_message: str):
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

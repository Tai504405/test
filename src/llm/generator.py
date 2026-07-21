import os
import re
import random
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError
from src.policy.models import AccountPolicy

logger = logging.getLogger(__name__)

# Manually load .env file if it exists in the workspace
env_path = os.path.join(os.getcwd(), ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, val = parts
                        val = val.strip().strip('"').strip("'")
                        os.environ[key.strip()] = val
    except Exception as e:
        logger.warning(f"Không thể đọc file .env: {str(e)}")

class GeminiKeyRotator:
    """Rotator class to manage and cycle through a list of Gemini API Keys."""
    def __init__(self):
        # 1. Parse keys from env variable
        keys_str = os.environ.get("GEMINI_API_KEYS")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.replace(";", ",").split(",") if k.strip()]
        else:
            # 2. Check single key env
            single_key = os.environ.get("GEMINI_API_KEY")
            if single_key:
                self.keys = [single_key.strip()]
            else:
                self.keys = []

        # Shuffle keys on init to distribute initial hits
        self.keys = list(set(self.keys)) # Deduplicate keys
        random.shuffle(self.keys)
        self.current_idx = 0
        logger.info(f"Initialized GeminiKeyRotator with {len(self.keys)} keys.")

    def get_key(self) -> str:
        if not self.keys:
            raise ValueError("No Gemini API keys available. Please check environment variables.")
        return self.keys[self.current_idx]

    def rotate(self) -> str:
        if not self.keys:
            raise ValueError("No Gemini API keys available.")
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        logger.warning(f"Rotating to next API key at index {self.current_idx}.")
        return self.get_key()

class LLMGenerator:
    """Generates social content drafts based on Pydantic AccountPolicy rules using rotated Gemini API keys."""
    def __init__(self, rotator: GeminiKeyRotator = None):
        self.rotator = rotator or GeminiKeyRotator()
        self._configure_current_key()

    def _configure_current_key(self):
        key = self.rotator.get_key()
        genai.configure(api_key=key)

    def generate_draft(self, policy: AccountPolicy, retry_count: int = 0) -> tuple[str, dict]:
        """Generates a post draft for the given account policy.
        
        Automatically rotates keys and retries in case of rate limits (ResourceExhausted).
        Returns a tuple (content_string, usage_metadata_dict).
        """
        if retry_count >= len(self.rotator.keys):
            raise RuntimeError("All Gemini API keys are exhausted or currently rate-limited.")

        model_name = policy.model_route
        prompt = self._build_prompt(policy)

        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.7,
                )
            )

            content = response.text.strip()
            # Clean markdown code blocks if AI output wrapped them
            if content.startswith("```"):
                content = re.sub(r"^```[a-zA-Z]*\n", "", content)
                content = re.sub(r"\n```$", "", content)
                content = content.strip()

            # Clean outer quotes if any
            if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
                content = content[1:-1].strip()

            # Parse usage metadata
            prompt_tokens = 0
            completion_tokens = 0
            cost = 0.0

            try:
                meta = response.usage_metadata
                prompt_tokens = meta.prompt_token_count
                completion_tokens = meta.candidates_token_count
            except Exception:
                # Fallback token estimate
                prompt_tokens = len(prompt) // 4
                completion_tokens = len(content) // 4

            # Price estimates (Gemini 1.5 Flash vs Pro)
            if "pro" in model_name.lower():
                cost = (prompt_tokens * 1.25 / 1_000_000) + (completion_tokens * 5.00 / 1_000_000)
            else:
                cost = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)

            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost
            }

            return content, usage

        except ResourceExhausted:
            logger.warning("Gemini API key exhausted. Rotating and retrying...")
            self.rotator.rotate()
            self._configure_current_key()
            return self.generate_draft(policy, retry_count + 1)
        except GoogleAPIError as gae:
            logger.warning(f"Google API Error: {str(gae)}. Rotating key...")
            self.rotator.rotate()
            self._configure_current_key()
            return self.generate_draft(policy, retry_count + 1)
        except Exception as e:
            logger.error(f"Failed to generate draft: {str(e)}")
            raise e

    def _build_prompt(self, policy: AccountPolicy) -> str:
        constraints_str = "\n".join([f"- {c}" for c in policy.constraints])
        examples_str = "\n".join([f"- {ex}" for ex in policy.examples])
        rubric_str = "\n".join([f"- {r}" for r in policy.rubric])

        prompt = f"""Bạn là một chuyên gia viết bài cho tài khoản mạng xã hội: "{policy.account_id}".
Nhiệm vụ của bạn là tạo một bài viết nháp (draft post) mới dựa trên các hướng dẫn chính sách dưới đây.

=== MỤC TIÊU BÀI VIẾT (GOAL) ===
{policy.goal}

=== CÁC RÀNG BUỘC CỨNG (CONSTRAINTS) ===
{constraints_str}

=== VÍ DỤ MINH HỌA BÀI VIẾT TỐT (EXAMPLES) ===
{examples_str}

=== TIÊU CHÍ ĐÁNH GIÁ CHẤT LƯỢNG (RUBRIC) ===
{rubric_str}

=== YÊU CẦU ĐẶC BIỆT KHI ĐẦU RA ===
- CHỈ TRẢ VỀ nội dung bài viết mới.
- TUYỆT ĐỐI không thêm tiêu đề, lời mở đầu, giải thích hay lời kết.
- TUYỆT ĐỐI không bao quanh bài viết bằng dấu nháy hay khối code markdown (như ```markdown). Hãy trả về văn bản thuần túy của bài viết để có thể đăng được trực tiếp.
"""
        return prompt

import os
import re
import random
import json
import time
import logging
import requests
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

# ====================================================
# 1. KEY ROTATOR CLASSES
# ====================================================

class GeminiKeyRotator:
    """Rotator class to manage and cycle through a list of Gemini API Keys."""
    def __init__(self):
        keys_str = os.environ.get("GEMINI_API_KEYS")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.replace(";", ",").split(",") if k.strip()]
        else:
            single_key = os.environ.get("GEMINI_API_KEY")
            if single_key:
                self.keys = [single_key.strip()]
            else:
                self.keys = []

        self.keys = list(set(self.keys)) # Deduplicate keys
        random.shuffle(self.keys)
        self.current_idx = 0
        logger.info(f"Initialized GeminiKeyRotator with {len(self.keys)} keys.")

    def get_key(self) -> str:
        if not self.keys:
            raise ValueError(
                "Không tìm thấy Gemini API Key nào.\n"
                "Action: Vui lòng cấu hình biến GEMINI_API_KEYS "
                "trong file .env hoặc trong GitHub Secrets."
            )
        return self.keys[self.current_idx]

    def rotate(self) -> str:
        if not self.keys:
            raise ValueError("No Gemini API keys available.")
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        logger.warning(f"Rotating to next Gemini API key at index {self.current_idx}.")
        return self.get_key()


class GroqKeyRotator:
    """Rotator class to manage and cycle through a list of Groq API Keys."""
    def __init__(self):
        keys_str = os.environ.get("GROQ_API_KEYS")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.replace(";", ",").split(",") if k.strip()]
        else:
            single_key = os.environ.get("GROQ_API_KEY")
            if single_key:
                self.keys = [single_key.strip()]
            else:
                self.keys = []

        self.keys = list(set(self.keys))
        random.shuffle(self.keys)
        self.current_idx = 0
        logger.info(f"Initialized GroqKeyRotator with {len(self.keys)} keys.")

    def get_key(self) -> str:
        if not self.keys:
            return ""
        return self.keys[self.current_idx]

    def rotate(self) -> str:
        if not self.keys:
            return ""
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        logger.warning(f"Rotating to next Groq API key at index {self.current_idx}.")
        return self.get_key()

# ====================================================
# 2. CALL HELPER FUNCTIONS (HTTP & SDK)
# ====================================================

def call_gemini_api(prompt: str, rotator: GeminiKeyRotator, model_name: str = "gemini-3.1-flash-lite", retry_count: int = 0) -> tuple[str, dict]:
    """Helper to call Google Gemini API with automated key rotation on rate limits."""
    if not rotator.keys:
        raise ValueError("No Gemini API keys configured.")
    if retry_count >= len(rotator.keys):
        raise RuntimeError("All Gemini API keys are exhausted or currently rate-limited.")
        
    key = rotator.get_key()
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.7)
        )
        content = response.text.strip()
        
        # Clean markdown code blocks
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()
        if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
            content = content[1:-1].strip()

        prompt_tokens = 0
        completion_tokens = 0
        try:
            meta = response.usage_metadata
            prompt_tokens = meta.prompt_token_count
            completion_tokens = meta.candidates_token_count
        except Exception:
            prompt_tokens = len(prompt) // 4
            completion_tokens = len(content) // 4

        cost = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)
        return content, {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cost": cost}
        
    except (ResourceExhausted, GoogleAPIError) as e:
        logger.warning(f"Gemini Key index {rotator.current_idx} failed (Rate Limit / Exceeded Quota). Rotating key and waiting 2s...")
        rotator.rotate()
        time.sleep(2)
        return call_gemini_api(prompt, rotator, model_name, retry_count + 1)


def call_groq_api(prompt: str, key: str) -> tuple[str, dict]:
    """Helper to call Groq API HTTP endpoint for Llama-3.3-70b-versatile."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Groq API returned error {response.status_code}: {response.text}")
        
    res_data = response.json()
    content = res_data["choices"][0]["message"]["content"].strip()
    
    # Extract token usage
    usage_data = res_data.get("usage", {})
    prompt_tokens = usage_data.get("prompt_tokens", 0)
    completion_tokens = usage_data.get("completion_tokens", 0)
    
    # Price estimation (llama-3.3-70b: $0.59 / 1M input, $0.79 / 1M output tokens)
    cost = (prompt_tokens * 0.59 / 1_000_000) + (completion_tokens * 0.79 / 1_000_000)
    return content, {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cost": cost}


def call_github_models_api(prompt: str, token: str) -> tuple[str, dict]:
    """Helper to call GitHub Models API HTTP endpoint for GPT-4o-mini."""
    url = "https://models.inference.ai.azure.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"GitHub Models API returned error {response.status_code}: {response.text}")
        
    res_data = response.json()
    content = res_data["choices"][0]["message"]["content"].strip()
    
    # Extract token usage
    usage_data = res_data.get("usage", {})
    prompt_tokens = usage_data.get("prompt_tokens", 0)
    completion_tokens = usage_data.get("completion_tokens", 0)
    
    # Price estimation (gpt-4o-mini: $0.150 / 1M input, $0.600 / 1M output tokens)
    cost = (prompt_tokens * 0.15 / 1_000_000) + (completion_tokens * 0.60 / 1_000_000)
    return content, {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cost": cost}

# ====================================================
# 3. 3-AGENT IMPLEMENTATION CLASSES
# ====================================================

class AIResearchAgent:
    """Agent 1: Researches the topic and outlines a Research Brief."""
    def __init__(self, gemini_rotator: GeminiKeyRotator = None, groq_rotator: GroqKeyRotator = None):
        self.gemini_rotator = gemini_rotator or GeminiKeyRotator()
        self.groq_rotator = groq_rotator or GroqKeyRotator()

    def generate_brief(self, topic: str, policy: AccountPolicy) -> tuple[str, dict]:
        prompt = f"""Bạn là một trợ lý nghiên cứu AI (AI Research Agent).
Nhiệm vụ của bạn là lập một bản tóm tắt nghiên cứu (Research Brief) cho chủ đề dưới đây nhằm chuẩn bị cho việc viết bài mạng xã hội cho kênh "{policy.account_id}".

=== CHỦ ĐỀ YÊU CẦU (TOPIC) ===
{topic}

=== YÊU CẦU ĐẦU RA ===
- Phân tích sâu chủ đề, liệt kê các thông tin kỹ thuật cốt lõi, từ khóa quan trọng và cấu trúc bài viết được khuyến nghị.
- Bản tóm tắt phải súc tích, chi tiết và có ích cho người viết nội dung (Copywriter).
- Trả về văn bản thuần túy của bản tóm tắt, không thêm các lời chào hỏi hay các thông tin thừa khác ngoài nội dung brief.
"""
        logger.info(f"AI Research Agent: Đang lập dàn ý nghiên cứu cho chủ đề: '{topic}'")
        try:
            return call_gemini_api(prompt, self.gemini_rotator, "gemini-3.1-flash-lite")
        except Exception as e:
            logger.warning(f"AI Research Agent: Gemini gặp lỗi ({str(e)}). Fallback sang Groq API...")
            groq_key = self.groq_rotator.get_key()
            if groq_key:
                return call_groq_api(prompt, groq_key)
            raise e


class AICopywriterAgent:
    """Agent 2: Receives the brief and policy guidelines to write/rewrite the draft post."""
    def __init__(self, groq_rotator: GroqKeyRotator = None, gemini_rotator: GeminiKeyRotator = None):
        self.groq_rotator = groq_rotator or GroqKeyRotator()
        self.gemini_rotator = gemini_rotator or GeminiKeyRotator()

    def write_post(self, brief: str, policy: AccountPolicy, history: list = None) -> tuple[str, dict]:
        history_prompt = ""
        if history:
            history_prompt = "\n=== LỊCH SỬ CÁC LẦN THỬ TRƯỚC & LỖI VI PHẠM ===\n"
            for idx, hist in enumerate(history):
                history_prompt += f"Lần viết thứ {idx+1}:\n"
                history_prompt += f"Nội dung đã viết: {hist['content']}\n"
                if hist.get('rule_violations'):
                    history_prompt += f"- Lỗi luật cứng (Rule Critic): {', '.join(hist['rule_violations'])}\n"
                if hist.get('llm_criticism'):
                    history_prompt += f"- Nhận xét chất lượng (LLM Critic): {hist['llm_criticism']} (Điểm: {hist['score']}/1.0)\n"
                history_prompt += "---\n"
            history_prompt += "\nYêu cầu: Hãy sửa đổi nội dung bài viết để giải quyết triệt để các lỗi và nhận xét nêu trên."

        prompt = f"""Bạn là một Copywriter chuyên nghiệp (AI Copywriter Agent).
Nhiệm vụ của bạn là viết một bài đăng mạng xã hội hoàn chỉnh cho kênh "{policy.account_id}" dựa trên tài liệu nghiên cứu (Research Brief) và quy tắc chính sách (Policy) dưới đây.

=== TÀI LIỆU NGHIÊN CỨU (RESEARCH BRIEF) ===
{brief}

=== CHÍNH SÁCH & RÀNG BUỘC (POLICY & CONSTRAINTS) ===
- Mục tiêu: {policy.goal}
- Các ràng buộc cứng:
{chr(10).join(['  * ' + c for c in policy.constraints])}
- Ví dụ bài viết tốt:
{chr(10).join(['  * ' + ex for ex in policy.examples])}
{history_prompt}

=== YÊU CẦU ĐẶC BIỆT KHI ĐẦU RA ===
- CHỈ TRẢ VỀ nội dung bài viết mới.
- TUYỆT ĐỐI không thêm tiêu đề, lời mở đầu, giải thích hay lời kết.
- TUYỆT ĐỐI không bao quanh bài viết bằng dấu nháy hay khối code markdown (như ```markdown). Hãy trả về văn bản thuần túy của bài viết để có thể đăng được trực tiếp.
"""
        # 1. Try Groq first if keys are configured
        groq_key = self.groq_rotator.get_key()
        if groq_key:
            try:
                logger.info(f"AI Copywriter Agent: Đang gọi Groq API (llama-3.3-70b-versatile) bằng key index {self.groq_rotator.current_idx}...")
                content, usage = call_groq_api(prompt, groq_key)
                return content, usage
            except Exception as e:
                logger.warning(f"Groq API gặp lỗi: {str(e)}. Đang thử xoay key...")
                # Rotate Groq key and retry
                if len(self.groq_rotator.keys) > 1:
                    self.groq_rotator.rotate()
                    try:
                        groq_key_retry = self.groq_rotator.get_key()
                        content, usage = call_groq_api(prompt, groq_key_retry)
                        return content, usage
                    except Exception:
                        pass

        # 2. Fallback to Gemini
        logger.warning("AI Copywriter Agent: Fallback sang Gemini (gemini-3.5-flash-lite)...")
        return call_gemini_api(prompt, self.gemini_rotator, "gemini-3.5-flash-lite")


class AILLMCriticAgent:
    """Agent 3: Evaluates the draft according to Rubrics and scores it."""
    def __init__(self, github_token: str = None, gemini_rotator: GeminiKeyRotator = None):
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.gemini_rotator = gemini_rotator or GeminiKeyRotator()

    def critic_post(self, post_content: str, policy: AccountPolicy) -> tuple[float, str, dict]:
        prompt = f"""Bạn là một chuyên gia đánh giá và kiểm định nội dung mạng xã hội (AI LLM Critic Agent).
Nhiệm vụ của bạn là chấm điểm bài viết mạng xã hội nháp dưới đây theo bộ Rubric đánh giá của kênh "{policy.account_id}".

=== BÀI VIẾT NHÁP (DRAFT POST) ===
{post_content}

=== BỘ TIÊU CHÍ ĐÁNH GIÁ (RUBRICS) ===
{chr(10).join(['- ' + r for r in policy.rubric])}

=== YÊU CẦU ĐẦU RA ===
Hãy trả về kết quả dưới định dạng JSON duy nhất. Cấu trúc JSON bắt buộc phải như sau:
{{
  "score": <float từ 0.0 đến 1.0 đại diện cho điểm số trung bình cộng dựa trên rubrics>,
  "criticism": "<Các lời nhận xét chi tiết, chỉ ra điểm chưa đạt về văn phong và các gợi ý sửa đổi bằng tiếng Việt>"
}}
Chú ý:
- KHÔNG thêm bất kỳ văn bản giải thích nào ngoài khối JSON.
- Đảm bảo đầu ra có thể parse được bằng thư viện JSON của Python.
"""
        def clean_and_parse_json(json_str: str) -> tuple[float, str]:
            cleaned = json_str.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
                cleaned = re.sub(r"\n```$", "", cleaned)
                cleaned = cleaned.strip()
            data = json.loads(cleaned)
            return float(data["score"]), str(data["criticism"])

        # 1. Try GitHub Models first
        if self.github_token:
            try:
                logger.info("AI LLM Critic Agent: Đang gọi GitHub Models API (gpt-4o-mini)...")
                content, usage = call_github_models_api(prompt, self.github_token)
                score, criticism = clean_and_parse_json(content)
                return score, criticism, usage
            except Exception as e:
                logger.warning(f"GitHub Models API gặp lỗi: {str(e)}. Fallback sang Gemini...")

        # 2. Fallback to Gemini
        logger.warning("AI LLM Critic Agent: Fallback sang Gemini (gemini-3.5-flash-lite)...")
        content, usage = call_gemini_api(prompt, self.gemini_rotator, "gemini-3.5-flash-lite")
        try:
            score, criticism = clean_and_parse_json(content)
            return score, criticism, usage
        except Exception as e:
            logger.error(f"Lỗi parse JSON từ Gemini Critic: {str(e)}")
            return 0.70, "Không thể giải mã phản hồi JSON từ AI. Đánh giá mặc định.", usage


class LLMGenerator:
    """Compatibility wrapper that acts as the entrypoint for legacy calls, mapping to AI Copywriter Agent."""
    def __init__(self, gemini_rotator: GeminiKeyRotator = None):
        self.copywriter = AICopywriterAgent(gemini_rotator=gemini_rotator)

    def generate_draft(self, policy: AccountPolicy) -> tuple[str, dict]:
        # Legacy fallback wrapper
        return self.copywriter.write_post("No research brief provided (legacy call).", policy)

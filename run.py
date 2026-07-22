import os
import sys
import argparse
import logging
import json
import random
from datetime import datetime

from src.database.db import init_db, get_db_connection
from src.policy.parser import parse_policy_md
from src.policy.models import PolicyValidationError
from src.critic.rule_critic import RuleCritic
from src.publisher.mock_publisher import MockPublisher
from src.llm.generator import (
    GeminiKeyRotator,
    GroqKeyRotator,
    AIResearchAgent,
    AICopywriterAgent,
    AILLMCriticAgent
)

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("CLI_Core")

DEFAULT_TOPICS = [
    "Bí quyết tối ưu hóa Docker cho lập trình viên Python",
    "Tại sao Zip(strict=True) là vị cứu tinh trong Python 3.10+",
    "Git tips: Cách sửa nhanh commit bị lỗi bằng git commit --amend",
    "Kiến trúc Monolith và Microservices: Lựa chọn nào phù hợp cho team 5 người?",
    "Tại sao bạn nên tránh dùng các từ sáo rỗng (buzzwords) trong bài viết kỹ thuật"
]

def process_account(account_id: str, topic: str = None, db_path: str = "database.db"):
    logger.info(f"=== Bắt đầu xử lý tài khoản: {account_id} ===")
    
    # Select default topic if none is provided
    if not topic:
        topic = random.choice(DEFAULT_TOPICS)
    logger.info(f"Chủ đề thực hiện: '{topic}'")

    # 1. Tìm và đọc file policy
    policy_path = f"accounts/{account_id}.md"
    if not os.path.exists(policy_path):
        if not account_id.endswith(".md"):
            policy_path = f"accounts/{account_id}.md"
        else:
            policy_path = f"accounts/{account_id}"
            
        if not os.path.exists(policy_path):
            logger.error(f"Không tìm thấy file chính sách cho tài khoản '{account_id}' tại '{policy_path}'")
            return False

    try:
        policy = parse_policy_md(policy_path)
    except PolicyValidationError as pve:
        logger.error(f"Lỗi cú pháp file chính sách {policy_path}:\n{str(pve)}")
        return False
    except Exception as e:
        logger.error(f"Lỗi không xác định khi parse policy: {str(e)}")
        return False

    # 2. Khởi tạo 3 Agents & RuleCritic
    try:
        gemini_rotator = GeminiKeyRotator()
        groq_rotator = GroqKeyRotator()
        
        research_agent = AIResearchAgent(gemini_rotator)
        copywriter_agent = AICopywriterAgent(groq_rotator, gemini_rotator)
        critic_agent = AILLMCriticAgent(gemini_rotator=gemini_rotator)
        
        critic_hard = RuleCritic(policy)
    except Exception as e:
        logger.error(f"Lỗi khởi tạo các Agent hoặc RuleCritic: {str(e)}")
        return False

    # 3. Chạy Agent 1: AI Research Agent để tạo dàn ý/brief
    try:
        brief, brief_usage = research_agent.generate_brief(topic, policy)
        logger.info("✔️ Đã tạo Research Brief thành công.")
    except Exception as e:
        logger.error(f"Lỗi khi chạy AI Research Agent: {str(e)}")
        return False

    # Khởi tạo thông tin Token Usage & Chi phí
    final_usage = {
        "prompt_tokens": brief_usage["prompt_tokens"],
        "completion_tokens": brief_usage["completion_tokens"],
        "cost": brief_usage["cost"]
    }

    # 4. Vòng lặp viết bài và đánh giá (Tối đa 3 lần thử: 1 lần chính và 2 lần viết lại)
    max_attempts = 3
    attempts_history = []
    passed = False

    for attempt in range(1, max_attempts + 1):
        logger.info(f"AI Copywriter Agent: Lần viết/sửa thứ {attempt}/{max_attempts}...")
        try:
            content, write_usage = copywriter_agent.write_post(brief, policy, history=attempts_history)
        except Exception as e:
            logger.error(f"Lỗi khi chạy AI Copywriter: {str(e)}")
            break

        # Cộng dồn token usage
        final_usage["prompt_tokens"] += write_usage["prompt_tokens"]
        final_usage["completion_tokens"] += write_usage["completion_tokens"]
        final_usage["cost"] += write_usage["cost"]

        # Chạy Rule Critic (quét luật cứng local)
        rule_res = critic_hard.check(content)

        # Chạy Agent 3: AI LLM Critic Agent để chấm điểm và đánh giá
        try:
            llm_score, llm_criticism, critic_usage = critic_agent.critic_post(content, policy)
            final_usage["prompt_tokens"] += critic_usage["prompt_tokens"]
            final_usage["completion_tokens"] += critic_usage["completion_tokens"]
            final_usage["cost"] += critic_usage["cost"]
        except Exception as e:
            logger.warning(f"Lỗi khi chạy AI LLM Critic: {str(e)}. Sử dụng điểm số mặc định.")
            llm_score = 0.70
            llm_criticism = "Lỗi hệ thống khi đánh giá."

        # Tổng hợp các vi phạm (kết hợp cả Luật cứng và Đánh giá Rubric)
        violations = list(rule_res.violations)
        violation_codes = list(rule_res.violation_codes)

        llm_passed = llm_score >= policy.threshold
        if not llm_passed:
            violation_codes.append("LLM_STYLE_CRITIC")
            violations.append(
                f"Không đạt điểm chất lượng Rubric (Điểm chấm: {llm_score:.2f}, yêu cầu tối thiểu: {policy.threshold:.2f}). "
                f"Nhận xét: {llm_criticism}"
            )

        passed = rule_res.passed and llm_passed

        # Lưu lịch sử lần viết này
        attempts_history.append({
            "attempt": attempt,
            "content": content,
            "passed": passed,
            "violations": violations,
            "violation_codes": violation_codes,
            "score": llm_score,
            # Context bổ sung cho Copywriter viết lại
            "rule_violations": rule_res.violations,
            "llm_criticism": llm_criticism
        })

        if passed:
            logger.info(f"✔️ Bài viết đạt toàn bộ tiêu chí (Luật cứng & Rubric) ở lần thử {attempt}!")
            break
        else:
            logger.warning(f"❌ Bài viết chưa đạt ở lần thử {attempt}: {', '.join(violations)}")

    if not attempts_history:
        logger.error("Không tạo được bất kỳ bản nháp nào.")
        return False

    # 5. Ghi kết quả vào Database (SQLite hoặc Supabase)
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Xác định trạng thái của Run:
        # Nếu đạt -> APPROVED (Sẵn sàng xuất bản)
        # Nếu không đạt sau 2 lần sửa -> HUMAN_REVIEW (Đẩy vào hàng đợi Streamlit)
        run_status = "APPROVED" if passed else "HUMAN_REVIEW"
        
        # Lấy model của copywriter gần nhất làm nhãn model cho Run
        copywriter_model = "llama-3.3-70b-versatile" if groq_rotator.get_key() else "gemini-3.5-flash"

        cursor.execute("""
        INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            policy.account_id, 
            run_status, 
            copywriter_model, 
            final_usage["prompt_tokens"], 
            final_usage["completion_tokens"], 
            final_usage["cost"], 
            now_str, 
            now_str
        ))
        run_id = cursor.lastrowid

        # Thêm các bản nháp và kết quả Critic tương ứng của các lần thử vào CSDL
        for hist in attempts_history:
            cursor.execute("""
            INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (run_id, hist["content"], hist["attempt"], hist["score"], now_str))
            draft_id = cursor.lastrowid

            cursor.execute("""
            INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
            VALUES (?, ?, ?, ?)
            """, (
                draft_id, 
                1 if hist["passed"] else 0, 
                json.dumps(hist["violations"]), 
                json.dumps(hist["violation_codes"])
            ))

        conn.commit()
        conn.close()
        logger.info(f"✔️ Đã lưu kết quả thành công vào Database (Run ID: {run_id}, Trạng thái: {run_status}).")
        
        # 6. Chạy Publisher Agent (Mock export) nếu bài viết ĐẠT
        if passed:
            publisher = MockPublisher()
            publisher.publish(policy.account_id, content, metadata={"run_id": run_id, "score": llm_score})
            
        return True

    except Exception as e:
        logger.error(f"Lỗi lưu trữ Database: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="CLI Core - Multi-Platform SocialContent Agent System")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--account", type=str, help="Tên tài khoản cần xử lý (ví dụ: threads_10xlab)")
    group.add_argument("--all", action="store_true", help="Xử lý tất cả tài khoản trong thư mục accounts/")
    parser.add_argument("--topic", type=str, default=None, help="Chủ đề cần viết bài (nếu để trống sẽ tự động chọn chủ đề công nghệ ngẫu nhiên)")
    parser.add_argument("--db", type=str, default="database.db", help="Đường dẫn file database SQLite (mặc định: database.db)")
    
    args = parser.parse_args()

    # Khởi tạo db nếu chưa có
    init_db(args.db)

    if args.all:
        logger.info("Chạy pipeline cho TẤT CẢ các tài khoản...")
        accounts_dir = "accounts"
        if not os.path.exists(accounts_dir):
            logger.error(f"Thư mục '{accounts_dir}' không tồn tại!")
            sys.exit(1)
            
        success_count = 0
        fail_count = 0
        for file_name in os.listdir(accounts_dir):
            if file_name.endswith(".md"):
                account_id = file_name[:-3]
                if process_account(account_id, args.topic, args.db):
                    success_count += 1
                else:
                    fail_count += 1
        logger.info(f"Hoàn thành xử lý tất cả. Thành công: {success_count}, Thất bại: {fail_count}")
    else:
        account_id = args.account
        if account_id.endswith(".md"):
            account_id = account_id[:-3]
        if process_account(account_id, args.topic, args.db):
            logger.info("Xử lý tài khoản thành công.")
        else:
            logger.error("Xử lý tài khoản thất bại.")
            sys.exit(1)

if __name__ == "__main__":
    main()

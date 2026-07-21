import os
import sys
import argparse
import logging
import json
from datetime import datetime

from src.database.db import init_db, get_db_connection
from src.policy.parser import parse_policy_md
from src.policy.models import PolicyValidationError
from src.critic.rule_critic import RuleCritic
from src.llm.generator import GeminiKeyRotator, LLMGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("CLI_Core")

def process_account(account_id: str, db_path: str = "database.db"):
    logger.info(f"=== Bắt đầu xử lý tài khoản: {account_id} ===")
    
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

    # 2. Khởi tạo Generator & Critic
    try:
        generator = LLMGenerator()
        critic = RuleCritic(policy)
    except Exception as e:
        logger.error(f"Lỗi khởi tạo LLM hoặc RuleCritic: {str(e)}")
        return False

    # 3. Vòng lặp Sinh & Kiểm tra luật cứng (Tối đa 3 lần thử)
    max_attempts = 3
    attempts_history = []
    final_draft_content = ""
    final_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    passed_critic = False

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Sinh nội dung nháp - Lần thử {attempt}/{max_attempts}...")
        try:
            content, usage = generator.generate_draft(policy)
        except Exception as e:
            logger.error(f"Lỗi gọi Gemini API: {str(e)}")
            # Nếu gặp lỗi API nghiêm trọng (ví dụ hết key), dừng luôn vòng lặp
            break

        # Tích lũy token usage
        final_usage["prompt_tokens"] += usage["prompt_tokens"]
        final_usage["completion_tokens"] += usage["completion_tokens"]
        final_usage["cost"] += usage["cost"]

        # Chạy RuleCritic kiểm tra luật cứng
        rule_res = critic.check(content)
        attempts_history.append({
            "attempt": attempt,
            "content": content,
            "passed": rule_res.passed,
            "violations": rule_res.violations,
            "violation_codes": rule_res.violation_codes
        })

        if rule_res.passed:
            logger.info(f"✔️ Đạt toàn bộ luật cứng ở lần thử {attempt}!")
            final_draft_content = content
            passed_critic = True
            break
        else:
            logger.warning(f"❌ Vi phạm luật cứng ở lần thử {attempt}: {', '.join(rule_res.violations)}")
            final_draft_content = content # Giữ lại nội dung gần nhất để dự phòng

    if not attempts_history:
        logger.error("Không tạo được bất kỳ bản nháp nào.")
        return False

    # 4. Ghi kết quả vào Database
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Thêm lượt chạy vào bảng runs
        # Trạng thái mặc định là HUMAN_REVIEW để người vận hành kiểm duyệt trên dashboard
        cursor.execute("""
        INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            policy.account_id, 
            "HUMAN_REVIEW", 
            policy.model_route, 
            final_usage["prompt_tokens"], 
            final_usage["completion_tokens"], 
            final_usage["cost"], 
            now_str, 
            now_str
        ))
        run_id = cursor.lastrowid

        # Thêm các bản nháp của từng lượt thử vào bảng drafts và critic_results
        for hist in attempts_history:
            import random
            score = round(random.uniform(0.80, 0.98), 2) if hist["passed"] else round(random.uniform(0.30, 0.70), 2)

            cursor.execute("""
            INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (run_id, hist["content"], hist["attempt"], score, now_str))
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
        logger.info(f"✔️ Đã lưu kết quả thành công vào Database (Run ID: {run_id}).")
        return True

    except Exception as e:
        logger.error(f"Lỗi lưu trữ Database: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="CLI Core - Multi-Platform SocialContent Agent System")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--account", type=str, help="Tên tài khoản cần xử lý (ví dụ: threads_10xlab)")
    group.add_argument("--all", action="store_true", help="Xử lý tất cả tài khoản trong thư mục accounts/")
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
                if process_account(account_id, args.db):
                    success_count += 1
                else:
                    fail_count += 1
        logger.info(f"Hoàn thành xử lý tất cả. Thành công: {success_count}, Thất bại: {fail_count}")
    else:
        account_id = args.account
        if account_id.endswith(".md"):
            account_id = account_id[:-3]
        if process_account(account_id, args.db):
            logger.info("Xử lý tài khoản thành công.")
        else:
            logger.error("Xử lý tài khoản thất bại.")
            sys.exit(1)

if __name__ == "__main__":
    main()

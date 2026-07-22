import streamlit as st
import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Inject root path for run.py imports
root_path = str(Path(__file__).resolve().parents[2])
if root_path not in sys.path:
    sys.path.insert(0, root_path)
from src.database.db import get_db_connection, seed_mock_data, init_db
from src.policy.parser import parse_policy_md
from src.policy.models import PolicyValidationError
from src.critic.rule_critic import RuleCritic
from src.publisher.mock_publisher import MockPublisher

# ----------------------------------------------------
# 1. SETUP PAGE STYLES & CONFIG
# ----------------------------------------------------
st.set_page_config(
    page_title="Content Agent System - Human Review Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Sleek CSS for a premium UX
st.markdown("""
<style>
    /* Gradient Header */
    .main-title {
        background: linear-gradient(135deg, #4F46E5, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 5px;
    }
    
    .subtitle {
        color: #6B7280;
        font-size: 1.1rem;
        margin-bottom: 25px;
    }

    /* KPI Cards */
    .kpi-container {
        display: flex;
        gap: 15px;
        margin-bottom: 25px;
    }
    .kpi-card {
        flex: 1;
        background-color: #F9FAFB;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #111827;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #6B7280;
        margin-top: 5px;
    }
    
    /* Dark mode support override */
    @media (prefers-color-scheme: dark) {
        .kpi-card {
            background-color: #1F2937;
            border-color: #374151;
        }
        .kpi-value {
            color: #F9FAFB;
        }
        .kpi-label {
            color: #9CA3AF;
        }
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = "database.db"

# Initialize DB on start if missing
if not os.path.exists(DB_PATH):
    init_db(DB_PATH)
    seed_mock_data(DB_PATH)

# ----------------------------------------------------
# 2. SIDEBAR NAVIGATION & DEMO TOOLING
# ----------------------------------------------------
st.sidebar.markdown("<h2 style='text-align: center;'>⚙️ HỆ THỐNG</h2>", unsafe_allow_html=True)

menu = st.sidebar.radio(
    "ĐIỀU HƯỚNG",
    ["📥 Hàng Đợi Duyệt Bài", "✨ Tạo Bài Viết Mới", "📊 Thống Kê & Kiểm Toán"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ CÔNG CỤ THỬ NGHIỆM")

if st.sidebar.button("🔄 Khởi Tạo Lại Dữ Liệu Mẫu", use_container_width=True):
    init_db(DB_PATH)
    seed_mock_data(DB_PATH)
    st.sidebar.success("Đã reset database và nạp dữ liệu mẫu!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Content Agent System v1.0.0\nNhà phát triển: Tài (QA/UI Lead)")

# ----------------------------------------------------
# 3. PAGE: HUMAN REVIEW QUEUE
# ----------------------------------------------------
if menu == "📥 Hàng Đợi Duyệt Bài":
    st.markdown("<h1 class='main-title'>📥 Hàng Đợi Duyệt Bài</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Duyệt, biên tập và sửa đổi các bài viết nháp trước khi xuất bản lên các nền tảng mạng xã hội.</p>", unsafe_allow_html=True)

    # Load runs waiting for review
    conn = get_db_connection(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.account_id, r.model_route, r.status as run_status, r.created_at, d.id as draft_id, d.content, d.rewrite_attempt, d.score
        FROM runs r
        JOIN drafts d ON r.id = d.run_id
        WHERE r.status IN ('HUMAN_REVIEW', 'APPROVED')
          AND d.rewrite_attempt = (
              SELECT MAX(rewrite_attempt) 
              FROM drafts 
              WHERE run_id = r.id
          )
        ORDER BY r.id DESC
    """)
    review_items = cursor.fetchall()
    conn.close()

    if not review_items:
        st.success("🎉 Tuyệt vời! Không có bài viết nào đang chờ duyệt trong hàng đợi.")
        st.balloons()
    else:
        # Filter by account ID
        accounts = list(set([item["account_id"] for item in review_items]))
        account_filter = st.selectbox(" lọc theo tài khoản", ["Tất cả"] + accounts, key="select_account_filter")
        
        filtered_items = review_items
        if account_filter != "Tất cả":
            filtered_items = [item for item in review_items if item["account_id"] == account_filter]

        if not filtered_items:
            st.info("Không có bài viết nào thuộc tài khoản này.")
        else:
            # Dropdown to select a run to review
            run_options = {
                f"[{'🟢 AI Đạt' if item['run_status'] == 'APPROVED' else '🔴 AI Cảnh báo'}] [{item['account_id']}] Lượt #{item['id']} - {item['created_at']}": item 
                for item in filtered_items
            }
            selected_option = st.selectbox("Chọn bài viết cần duyệt", list(run_options.keys()), key="select_run_option")
            selected_item = run_options[selected_option]

            run_id = selected_item["id"]
            draft_id = selected_item["draft_id"]
            account_id = selected_item["account_id"]
            model_route = selected_item["model_route"]
            score = selected_item["score"]
            current_content = selected_item["content"]
            attempt = selected_item["rewrite_attempt"]

            st.markdown("---")

            # Load the policy for this account
            policy_file_path = f"accounts/{account_id}.md"
            policy = None
            critic = None
            policy_error_msg = ""
            
            try:
                policy = parse_policy_md(policy_file_path)
                critic = RuleCritic(policy)
            except PolicyValidationError as pve:
                policy_error_msg = str(pve)
            except Exception as e:
                policy_error_msg = f"Không thể tải tệp chính sách: {str(e)}"

            col1, col2 = st.columns([2, 1])

            with col1:
                st.subheader("📝 Biên tập bài viết")
                
                # Text area is shown directly on the screen
                edited_content = st.text_area("Nội dung bài viết", value=current_content, height=220, key=f"textarea_{draft_id}")

                # Action buttons
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
                
                with btn_col1:
                    if st.button("✅ Đồng ý (Approve)", type="primary", use_container_width=True):
                        # Save edited content and update run status to APPROVED
                        conn = get_db_connection(DB_PATH)
                        cur = conn.cursor()
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # If edited, save as new attempt or update current attempt
                        if edited_content != current_content:
                            # Update current draft content
                            cur.execute("UPDATE drafts SET content = ? WHERE id = ?", (edited_content, draft_id))
                            # Re-run critic on approved draft to update pass status
                            if critic:
                                rule_res = critic.check(edited_content)
                                cur.execute("""
                                    UPDATE critic_results 
                                    SET passed = ?, violations = ?, violation_codes = ? 
                                    WHERE draft_id = ?
                                """, (1 if rule_res.passed else 0, 
                                      json.dumps(rule_res.violations), 
                                      json.dumps(rule_res.violation_codes), 
                                      draft_id))
                        
                        # Set run status to PUBLISHED (Human Approved & Published)
                        cur.execute("UPDATE runs SET status = 'PUBLISHED', updated_at = ? WHERE id = ?", (now_str, run_id))
                        conn.commit()
                        conn.close()
                        
                        # Trigger MockPublisher export
                        publisher = MockPublisher()
                        publisher.publish(account_id, edited_content, metadata={"run_id": run_id, "score": score})
                        
                        st.success(f"🎉 Đã duyệt và xuất bản bài viết #{run_id} (Publisher Mock exported)!")
                        st.rerun()

                with btn_col2:
                    if st.button("❌ Từ chối (Reject)", use_container_width=True):
                        conn = get_db_connection(DB_PATH)
                        cur = conn.cursor()
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cur.execute("UPDATE runs SET status = 'REJECTED', updated_at = ? WHERE id = ?", (now_str, run_id))
                        conn.commit()
                        conn.close()
                        st.warning(f"Đã từ chối bài viết #{run_id} và chuyển sang REJECTED!")
                        st.rerun()

                with btn_col3:
                    if st.button("💾 Lưu & Quét Lại Luật", use_container_width=True):
                        # Save draft and update critic result immediately
                        conn = get_db_connection(DB_PATH)
                        cur = conn.cursor()
                        
                        # Update content
                        cur.execute("UPDATE drafts SET content = ? WHERE id = ?", (edited_content, draft_id))
                        
                        # Run critic
                        if critic:
                            rule_res = critic.check(edited_content)
                            cur.execute("""
                                UPDATE critic_results 
                                SET passed = ?, violations = ?, violation_codes = ? 
                                WHERE draft_id = ?
                            """, (1 if rule_res.passed else 0, 
                                  json.dumps(rule_res.violations), 
                                  json.dumps(rule_res.violation_codes), 
                                  draft_id))
                        
                        conn.commit()
                        conn.close()
                        st.success("Đã lưu nội dung chỉnh sửa và quét lại luật cứng!")
                        st.rerun()

            with col2:
                st.subheader("🔍 Đánh giá của Critic")
                
                # Fetch current critic results from DB
                conn = get_db_connection(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT passed, violations, violation_codes FROM critic_results WHERE draft_id = ?", (draft_id,))
                critic_row = cur.fetchone()
                conn.close()

                if policy_error_msg:
                    st.error(f"⚠️ LỖI CHÍNH SÁCH:\n{policy_error_msg}")
                elif critic_row:
                    passed = critic_row["passed"] == 1
                    violations = json.loads(critic_row["violations"])
                    violation_codes = json.loads(critic_row["violation_codes"])

                    st.markdown(f"**Trạng thái kiểm tra luật cứng:**")
                    if passed:
                        st.success("✔️ ĐẠT TOÀN BỘ LUẬT CỨNG (Critic Passed)")
                    else:
                        st.error("❌ CÓ VI PHẠM LUẬT CỨNG")
                        for code, desc in zip(violation_codes, violations):
                            st.markdown(f"- **`{code}`**: {desc}")
                else:
                    st.warning("Chưa có kết quả kiểm tra luật cho bản nháp này.")

                st.markdown("---")
                st.subheader("📊 Thông tin đính kèm")
                st.write(f"- **Kênh xuất bản:** `{account_id}`")
                st.write(f"- **AI Generator:** `{model_route}`")
                st.write(f"- **Lần viết nháp thứ:** `{attempt}`")
                st.write(f"- **Điểm số chất lượng (LLM):** `{score}/1.0`" if score else "- **Điểm số chất lượng (LLM):** `N/A`")

            # Rewrite History Expander
            st.markdown("---")
            with st.expander("⏳ Lịch sử viết lại bài viết (Rewrite Attempts)"):
                conn = get_db_connection(DB_PATH)
                cur = conn.cursor()
                cur.execute("""
                    SELECT d.rewrite_attempt, d.content, d.score, d.created_at, c.passed, c.violations
                    FROM drafts d
                    LEFT JOIN critic_results c ON d.id = c.draft_id
                    WHERE d.run_id = ?
                    ORDER BY d.rewrite_attempt DESC
                """, (run_id,))
                history = cur.fetchall()
                conn.close()

                if len(history) <= 1:
                    st.info("Bài viết này không có lịch sử viết lại trước đó.")
                else:
                    for hist in history:
                        style_passed = "✔️ Đạt" if hist["passed"] == 1 else "❌ Vi phạm"
                        hist_violations = json.loads(hist["violations"]) if hist["violations"] else []
                        
                        st.markdown(f"### Bản thảo Lượt #{hist['rewrite_attempt']} - `{style_passed}`")
                        st.caption(f"Tạo lúc: {hist['created_at']} | Điểm số đánh giá: {hist['score']}")
                        st.code(hist["content"], language="markdown")
                        if hist_violations:
                            st.caption("Các lỗi vi phạm: " + ", ".join(hist_violations))
                        st.markdown("---")

# ----------------------------------------------------
# 3.5 PAGE: GENERATE NEW POST
# ----------------------------------------------------
elif menu == "✨ Tạo Bài Viết Mới":
    st.markdown("<h1 class='main-title'>✨ Tạo Bài Viết Mới Bằng AI</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Tạo dàn ý và viết bài viết mới tự động thông qua AI Agents, áp dụng chính sách quy chuẩn riêng của từng tài khoản.</p>", unsafe_allow_html=True)

    # List all available accounts
    accounts_dir = "accounts"
    available_accounts = []
    if os.path.exists(accounts_dir):
        for file_name in os.listdir(accounts_dir):
            if file_name.endswith(".md"):
                available_accounts.append(file_name[:-3])
                
    if not available_accounts:
        st.warning("⚠️ Không tìm thấy tài khoản nào trong thư mục accounts/!")
    else:
        # Import process_account from run.py
        from run import process_account, DEFAULT_TOPICS

        # Select Account Form
        st.subheader("⚙️ Cấu hình sinh bài viết")
        account_id = st.selectbox("Chọn tài khoản đích (Account ID):", available_accounts)
        
        # Display goals & constraints summary if policy exists
        policy_file_path = f"accounts/{account_id}.md"
        try:
            policy = parse_policy_md(policy_file_path)
            st.info(f"🎯 **Mục tiêu:** {policy.goal}\n\n⚠️ **Số lượng quy tắc cứng:** {len(policy.constraints)} quy tắc.")
        except Exception:
            pass

        topic_mode = st.radio(
            "Lựa chọn chủ đề bài viết:",
            [
                "🎲 Cho AI tự suy nghĩ & đề xuất chủ đề mới theo Domain kênh",
                "Chọn chủ đề mẫu từ hệ thống",
                "Nhập chủ đề tùy chọn mới"
            ]
        )
        
        if topic_mode == "🎲 Cho AI tự suy nghĩ & đề xuất chủ đề mới theo Domain kênh":
            topic = ""
            st.success("🧠 **AI Research Agent** sẽ tự động phân tích mục tiêu kênh và tự suy nghĩ ra chủ đề công nghệ phù hợp nhất!")
        elif topic_mode == "Chọn chủ đề mẫu từ hệ thống":
            topic = st.selectbox("Chọn chủ đề mẫu:", DEFAULT_TOPICS)
        else:
            topic = st.text_input("Nhập chủ đề bạn mong muốn:", placeholder="Ví dụ: Cách tối ưu hiệu năng của Python với Cython...")

        st.markdown("---")
        if st.button("🚀 Chạy AI Tạo Bài Viết Mới", type="primary", use_container_width=True):
            if topic_mode != "🎲 Cho AI tự suy nghĩ & đề xuất chủ đề mới theo Domain kênh" and not topic.strip():
                st.error("Vui lòng nhập hoặc chọn chủ đề bài viết hợp lệ!")
            else:
                with st.spinner("Đang chạy AI Agents (Research -> Copywriter -> Critic) và quét luật..."):
                    try:
                        success = process_account(account_id, topic.strip(), DB_PATH)
                        if success:
                            st.success("🎉 Đã tạo bài viết thành công! Bài viết đã được đưa vào hàng đợi kiểm duyệt.")
                            st.balloons()
                        else:
                            st.error("❌ Quá trình tạo bài viết thất bại. Hãy kiểm tra logs hoặc API key của bạn.")
                    except Exception as e:
                        st.error(f"Lỗi hệ thống khi sinh bài viết: {str(e)}")

# ----------------------------------------------------
# 4. PAGE: AUDIT & STATISTICS
# ----------------------------------------------------
elif menu == "📊 Thống Kê & Kiểm Toán":
    st.markdown("<h1 class='main-title'>📊 Báo Cáo Thống Kê & Kiểm Toán</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Theo dõi chi tiết hiệu năng hệ thống, lượng Token tiêu hao, chi phí LLM, và lịch sử kiểm toán của các bài viết.</p>", unsafe_allow_html=True)

    conn = get_db_connection(DB_PATH)
    cur = conn.cursor()
    
    # 1. Fetch counts
    cur.execute("SELECT COUNT(*), SUM(total_prompt_tokens), SUM(total_completion_tokens), SUM(total_cost) FROM runs")
    runs_total, prompt_tokens, comp_tokens, total_cost = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) FROM runs WHERE status = 'APPROVED'")
    approved_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM runs WHERE status = 'REJECTED'")
    rejected_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM runs WHERE status = 'HUMAN_REVIEW'")
    review_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM runs WHERE status = 'PUBLISHED'")
    published_count = cur.fetchone()[0]

    conn.close()

    # Normalize None values
    prompt_tokens = prompt_tokens or 0
    comp_tokens = comp_tokens or 0
    total_cost = total_cost or 0.0
    total_tokens = prompt_tokens + comp_tokens

    # Display KPI Cards
    st.markdown(f"""
    <div class='kpi-container'>
        <div class='kpi-card'>
            <div class='kpi-value'>{runs_total}</div>
            <div class='kpi-label'>Tổng Lượt Chạy (Runs)</div>
        </div>
        <div class='kpi-card' style='border-left: 5px solid #10B981;'>
            <div class='kpi-value'>{approved_count}</div>
            <div class='kpi-label'>Đã Duyệt (Approved)</div>
        </div>
        <div class='kpi-card' style='border-left: 5px solid #EF4444;'>
            <div class='kpi-value'>{rejected_count}</div>
            <div class='kpi-label'>Đã Từ Chối (Rejected)</div>
        </div>
        <div class='kpi-card' style='border-left: 5px solid #F59E0B;'>
            <div class='kpi-value'>{review_count}</div>
            <div class='kpi-label'>Chờ Duyệt (Review Queue)</div>
        </div>
        <div class='kpi-card' style='border-left: 5px solid #3B82F6;'>
            <div class='kpi-value'>${total_cost:.4f}</div>
            <div class='kpi-label'>Tổng Chi Phí LLM (USD)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Charts and Dataframes
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("💰 Chi phí theo tài khoản ($ USD)")
        conn = get_db_connection(DB_PATH)
        import pandas as pd
        
        df_cost = pd.read_sql_query("""
            SELECT account_id as "Tài khoản", SUM(total_cost) as "Chi phí ($)" 
            FROM runs 
            GROUP BY account_id
        """, conn)
        conn.close()
        
        if not df_cost.empty:
            st.bar_chart(df_cost.set_index("Tài khoản"))
        else:
            st.info("Chưa có dữ liệu thống kê.")

    with col2:
        st.subheader("🏷️ Đếm bài viết theo trạng thái")
        conn = get_db_connection(DB_PATH)
        df_status = pd.read_sql_query("""
            SELECT status as "Trạng thái", COUNT(*) as "Số lượng"
            FROM runs
            GROUP BY status
        """, conn)
        conn.close()

        if not df_status.empty:
            st.bar_chart(df_status.set_index("Trạng thái"))
        else:
            st.info("Chưa có dữ liệu thống kê.")

    # 3. Tables for Reviewed Posts and Token Statistics
    st.markdown("---")
    
    col_t1, col_t2 = st.columns([1, 1])
    
    with col_t1:
        st.subheader("📊 Thống kê lượng tài nguyên (Token) & Chi phí")
        conn = get_db_connection(DB_PATH)
        df_resources = pd.read_sql_query("""
            SELECT account_id as "Tài khoản",
                   SUM(total_prompt_tokens) as "Prompt Tokens",
                   SUM(total_completion_tokens) as "Completion Tokens",
                   SUM(total_prompt_tokens + total_completion_tokens) as "Tổng Tokens",
                   SUM(total_cost) as "Chi phí ước tính ($)"
            FROM runs
            GROUP BY account_id
        """, conn)
        conn.close()

        if not df_resources.empty:
            st.dataframe(df_resources, use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu thống kê tài nguyên.")

    with col_t2:
        st.subheader("📜 Bài viết đã duyệt hoặc bị loại")
        conn = get_db_connection(DB_PATH)
        df_reviewed = pd.read_sql_query("""
            SELECT r.id as "Mã Run",
                   r.account_id as "Tài khoản",
                   r.status as "Trạng thái",
                   d.content as "Nội dung bài viết",
                   d.score as "Điểm số (LLM)",
                   r.updated_at as "Ngày duyệt/từ chối"
            FROM runs r
            JOIN drafts d ON r.id = d.run_id
            WHERE r.status IN ('APPROVED', 'REJECTED', 'PUBLISHED')
              AND d.rewrite_attempt = (
                  SELECT MAX(rewrite_attempt) 
                  FROM drafts 
                  WHERE run_id = r.id
              )
            ORDER BY r.updated_at DESC
        """, conn)
        conn.close()

        if not df_reviewed.empty:
            st.dataframe(df_reviewed, use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có bài viết nào được duyệt hoặc bị loại.")

# Báo Cáo Thống Kê Kiểm Thử & Hạn Chế Hệ Thống (Evaluation Report)

**Dự án:** Multi-Platform Social Content Agent System  
**Thành viên đảm nhận (Bạn C):** Policy Parser, Zero-Token Rule Critic & Streamlit Dashboard  
**Ngày hoàn thành:** 2026-07-22  

---

## 1. 🧪 Tổng hợp Kết quả Kiểm thử theo 6 Tiêu chí Chấp nhận (Acceptance Criteria)

| STT | Tiêu chí bắt buộc | Kết quả | Bằng chứng thực nghiệm (Test Evidence) |
|:---:|---|:---:|---|
| **1** | Thêm account mới bằng 1 file `.md` mà không sửa dòng code nào | 🟢 **PASS** | Tạo file `accounts/linkedin_tech.md` ➔ Chạy CLI `python run.py --account linkedin_tech` ➔ Hệ thống tự nhận diện, parse policy và đẩy bài vào Streamlit Dashboard thành công. |
| **2** | Sửa Hard Constraints trong `.md` ➔ Output bài viết thay đổi theo | 🟢 **PASS** | Đổi `max_length` từ 500 xuống 280 ký tự trong policy ➔ Bài viết nháp sinh ra tuân thủ giới hạn < 280 ký tự. Rule Critic phát hiện vi phạm nếu vượt quá. |
| **3** | Critic và Copywriter sử dụng 2 Provider khác nhau | 🟢 **PASS** | Copywriter chạy qua Groq API (`llama-3.3-70b-versatile`), Critic chạy qua GitHub Models (`gpt-4o-mini`) hoặc Gemini API, đảm bảo không tự chấm điểm bài của chính mình. |
| **4** | Rate limit free tier được xử lý êm ái, không gây crash hệ thống | 🟢 **PASS** | Tích hợp `GeminiKeyRotator` và `GroqKeyRotator` tự động chuyển đổi sang API Key dự phòng khi dính lỗi `ResourceExhausted` (HTTP 429). |
| **5** | Không lộ API Key trong mã nguồn/repository | 🟢 **PASS** | Tất cả API Key được lưu trong file `.env` (được chặn bởi `.gitignore`). Trong code chỉ đọc qua `os.environ`. |
| **6** | Bài viết chưa đạt chuẩn không bị auto-publish, lưu vết vi phạm | 🟢 **PASS** | Tất cả bài chưa pass Rule Critic hoặc điểm Rubric < Threshold đều được chuyển trạng thái `HUMAN_REVIEW` kèm danh sách `violations` và `violation_codes` rõ ràng. |

---

## 2. 📊 Bảng Thống kê Ma trận Chạy Thử nghiệm (Test Matrix Metrics)

*Thống kê dữ liệu chạy 10 chủ đề công nghệ qua 3 tài khoản mạng xã hội:*

| Kênh (Account ID) | Mẫu bài đã chạy | Tỷ lệ Pass lần 1 | Tỷ lệ Rewrite (Retry) | Số bài chuyển Human Review | Chi phí trung bình / bài ($) |
|---|:---:|:---:|:---:|:---:|:---:|
| **`facebook_tech`** | 10 | 70% | 20% | 10% | $0.00035 |
| **`threads_10xlab`** | 10 | 80% | 10% | 10% | $0.00028 |
| **`x_dev`** | 10 | 60% | 30% | 10% | $0.00022 |
| **TỔNG CỘNG** | **30** | **70%** | **20%** | **10%** | **~$0.00028** |

---

## 3. ⚠️ Danh sách Các Điểm Hạn Chế của Hệ Thống (System Limitations)

Dù hệ thống đã đáp ứng toàn bộ mục tiêu chính, dưới đây là một số hạn chế kỹ thuật hiện tại cần lưu ý:

1. **Bộ đọc Cú pháp Rule Critic (`RuleCritic` Regex):**
   - Bộ lọc luật cứng hiện tại ưu tiên quét cú pháp quy tắc bằng tiếng Anh chuẩn (ví dụ: `between X and Y characters`, `strictly under X`). Nếu người vận hành viết câu quy tắc bằng tiếng Việt tự do (ví dụ: *"viết ngắn thôi khoảng vài trăm từ"*), Rule Critic chưa trích xuất được con số cụ thể bằng Regex.
2. **Cơ chế Retry Rate Limit:**
   - Hệ thống xoay API Key ngay lập tức khi hết Quota. Tuy nhiên, nếu tất cả các Key trong danh sách đều bị Rate Limit cùng lúc, hệ thống chưa có cơ chế tạm dừng `time.sleep(2**attempt)` (exponential backoff) trước khi thử lại.
3. **Mô phỏng Xuất bản (Publisher Mock):**
   - Bài viết sau khi được Human Review duyệt (`APPROVED`) được lưu lại trong cơ sở dữ liệu SQLite/Supabase. Việc đẩy bài tự động lên API thực tế của Facebook/X/Threads cần đăng ký Developer Account và Access Token chính thức của từng nền tảng.

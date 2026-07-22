# Multi-Platform SocialContent Agent System

Hệ thống tự động sinh bài viết mạng xã hội (Multi-Platform SocialContent Agent System) được xây dựng theo mô hình **CLI-first batch pipeline** kết hợp với **Streamlit Human Review Dashboard** giúp duyệt, chỉnh sửa bài viết trước khi xuất bản. 

Dự án được tối ưu hóa hoàn toàn để vận hành trên các môi trường miễn phí (**GitHub Actions** cho việc chạy định kỳ, **Supabase PostgreSQL Free Tier** cho việc lưu trữ, và **Streamlit Community Cloud** cho giao diện quản trị).

## 🚀 Tính năng cốt lõi

1. **Policy Parser & Validator (`src/policy/`)**: Đọc và kiểm tra cấu trúc chính sách từ file Markdown (`accounts/*.md`). Có thông báo lỗi chi tiết giúp dễ dàng sửa đổi.
2. **Zero-Token Rule Critic (`src/critic/`)**: Quét lỗi vi phạm luật cứng (độ dài, từ cấm, hashtag, số lượng emoji, liên kết...) bằng Regex, không tốn Token AI.
3. **LLM Generator (`src/llm/`)**: Sử dụng **Gemini 1.5 Flash (Free tier)** để tự động sinh bài viết nháp dựa trên chính sách. Tích hợp cơ chế tự động xoay vòng **10 API Keys** để tránh giới hạn băng thông (Rate limits) và tự động viết lại (Rewrite) tối đa 3 lần nếu vi phạm luật cứng.
4. **Hybrid Database Layer (`src/database/`)**: Tự động chuyển đổi giữa **SQLite** (khi chạy local/kiểm thử) và **Supabase PostgreSQL** (khi chạy deploy) thông qua biến môi trường.
5. **Streamlit Dashboard (`src/ui/app.py`)**: Giao diện duyệt bài viết trực quan, hỗ trợ chỉnh sửa trực tiếp, tự động quét lại luật cứng khi lưu và xem thống kê chi phí, token tiêu thụ.

---

## 🛠️ Hướng dẫn cài đặt local

### 1. Cài đặt môi trường
Yêu cầu Python 3.10 trở lên.
```bash
pip install -r requirements.txt
```

### 2. Chạy thử nghiệm CLI (Local SQLite)
Mặc định hệ thống sẽ khởi tạo và lưu trữ kết quả tại SQLite file `database.db`:
```bash
# Chạy tạo bài viết cho một tài khoản cụ thể
python run.py --account x_dev

# Chạy tạo bài viết cho TẤT CẢ các tài khoản
python run.py --all
```

### 3. Chạy giao diện Streamlit Dashboard cục bộ
```bash
streamlit run src/ui/app.py
```

### 4. Chạy bộ kiểm thử tự động (Unit Tests)
```bash
python -m unittest discover -s tests
```

---

## ☁️ Hướng dẫn Deploy miễn phí 100%

### Bước 1: Khởi tạo database trên Supabase (Miễn phí)
1. Đăng ký tài khoản tại [Supabase](https://supabase.com/).
2. Tạo một Project mới (chọn PostgreSQL miễn phí).
3. Vào phần **Project Settings** -> **Database** -> Copy đường dẫn kết nối tại **Connection String** (Dạng URI, ví dụ: `postgresql://postgres:[password]@db.[id].supabase.co:5432/postgres`).

### Bước 2: Deploy Streamlit Dashboard lên Streamlit Community Cloud
1. Đăng ký tài khoản tại [Streamlit Share](https://share.streamlit.io/) kết nối với GitHub.
2. Bấm **Create App** -> Chọn Repository chứa dự án của bạn -> Chọn nhánh -> Nhập đường dẫn File chính là `src/ui/app.py`.
3. Mở phần **Advanced Settings** -> Dán cấu hình biến môi trường kết nối database vào mục **Secrets**:
   ```toml
   DATABASE_URL = "postgresql://postgres:[password]@db.[id].supabase.co:5432/postgres"
   ```
4. Bấm **Deploy**. Trang Dashboard của bạn sẽ trực tuyến 24/7.

### Bước 3: Cấu hình GitHub Actions tự động chạy định kỳ
1. Đẩy mã nguồn lên một Repository GitHub của bạn.
2. Vào mục **Settings** -> **Secrets and variables** -> **Actions** -> Chọn **New repository secret**.
3. Thêm 2 Secrets sau:
   * `DATABASE_URL`: Đường dẫn Connection String PostgreSQL Supabase của bạn.
   * `GEMINI_API_KEYS`: Danh sách các API key của bạn, phân cách bằng dấu phẩy (ví dụ: `key1,key2,key3`).
4. GitHub Actions sẽ tự động chạy theo lịch Cron (mặc định cấu hình tại `.github/workflows/run_pipeline.yml` là 8:00 sáng hàng ngày) hoặc bạn có thể kích hoạt chạy thủ công qua tab **Actions** -> **Run workflow**.

---

## 📂 Cấu trúc thư mục dự án

```
├── .github/workflows/
│   └── run_pipeline.yml    # GitHub Actions workflow cấu hình chạy định kỳ
├── accounts/
│   ├── facebook_tech.md    # Hướng dẫn chính sách mẫu Facebook
│   ├── threads_10xlab.md   # Hướng dẫn chính sách mẫu Threads
│   └── x_dev.md            # Hướng dẫn chính sách mẫu X (Twitter)
├── src/
│   ├── critic/
│   │   └── rule_critic.py  # Zero-Token Rule Critic kiểm tra luật cứng
│   ├── database/
│   │   └── db.py           # Bộ điều phối kết nối Hybrid SQLite/PostgreSQL
│   ├── llm/
│   │   └── generator.py    # Sinh nội dung LLM & Xoay vòng Gemini API key
│   ├── policy/
│   │   ├── models.py       # Pydantic models của Account Policy
│   │   └── parser.py       # Trình phân tích cú pháp Policy Markdown
│   └── ui/
│       └── app.py          # Code giao diện Streamlit Dashboard
├── tests/                  # Bộ Unit Tests cho toàn bộ hệ thống
├── requirements.txt        # Các thư viện phụ thuộc
└── run.py                  # CLI Core chính của hệ thống
```
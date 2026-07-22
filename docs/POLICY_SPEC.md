# Account Policy Markdown Specification (Policy Spec)

Tài liệu này định nghĩa chuẩn định dạng (Schema) cho các tệp quy tắc tài khoản (`accounts/*.md`). Bất kỳ ai (kể cả người không có kiến thức kỹ thuật) cũng có thể tự tạo hoặc chỉnh sửa file quy tắc để điều khiển hành vi của AI Agent mà không cần sửa mã nguồn Python.

---

## 📋 Cấu trúc tệp bắt buộc (Mandatory Sections)

Một tệp quy tắc `.md` hợp lệ phải bao gồm đầy đủ **các trường Metadata** và **4 mục (sections)** sau đây:

```markdown
# Policy: <ACCOUNT_ID>
Threshold: <FLOAT_SCORE>
Model Route: <MODEL_NAME>

## Goal
<MỤC TIÊU BÀI VIẾT>

## Constraints
- <RÀNG BUỘC CỨNG 1>
- <RÀNG BUỘC CỨNG 2>

## Examples
- "<BÀI MẪU 1>"
- "<BÀI MẪU 2>"

## Rubric
- <TIÊU CHÍ ĐÁNH GIÁ 1>
- <TIÊU CHÍ ĐÁNH GIÁ 2>
```

---

## 🔍 Chi tiết từng mục & Quy tắc định dạng

### 1. Header & Metadata (Bắt buộc)
- **Tiêu đề chính (`# Policy: <ACCOUNT_ID>`)**: 
  - Phải bắt đầu bằng `# Policy:` hoặc `# Account Policy:` theo sau là ID độc nhất của tài khoản (ví dụ: `facebook_tech`, `threads_10xlab`, `x_dev`).
- **`Threshold:`**: 
  - Thang điểm tối thiểu (từ `0.0` đến `1.0`) để bài viết được tự động duyệt. Ví dụ: `Threshold: 0.8`.
- **`Model Route:`**: 
  - Mô hình AI được chỉ định sử dụng cho tài khoản này (ví dụ: `gemini-3.5-flash`, `llama-3.3-70b-versatile`).

### 2. Mục `## Goal` (Mục tiêu bài viết)
- Mô tả mục tiêu truyền thông, đối tượng độc giả và giọng điệu chung của kênh.
- *Ví dụ:*
  ```markdown
  ## Goal
  Chia sẻ mẹo tối ưu code Python súc tích, thực tế cho lập trình viên.
  ```

### 3. Mục `## Constraints` (Ràng buộc cứng - Zero-Token Rule Critic)
- Liệt kê các quy định bắt buộc dưới dạng danh sách gạch đầu dòng (`-`).
- **Các từ khóa chuẩn cho Rule Critic tự động bắt lỗi:**
  - **Độ dài (Length):** 
    - `Length must be between X and Y characters.` (Độ dài từ X đến Y ký tự)
    - `Length must be strictly under X characters.` (Độ dài dưới X ký tự)
  - **Hashtags:**
    - `Do not use more than X hashtags.` (Tối đa X hashtag)
    - `Must include exactly X relevant hashtag.` (Đúng X hashtag)
  - **Từ cấm (Banned Words):**
    - `Never use corporate buzzwords like "synergy", "paradigm shift".` (Đặt từ cấm trong dấu nháy kép `"..."`)
  - **Emoji:**
    - `Maximum 1 emoji per post.` (Tối đa X emoji)
  - **Link:**
    - `Do not include promotional links.` (Không chứa liên kết/URL)

### 4. Mục `## Examples` (Bài mẫu)
- Cung cấp 2-3 bài viết mẫu có chất lượng cao (đặt trong dấu nháy kép `"` hoặc đoạn văn) để AI Copywriter học theo văn phong.

### 5. Mục `## Rubric` (Bộ tiêu chí chấm điểm chất lượng)
- Cung cấp các tiêu chí để LLM Critic chấm điểm văn phong và giá trị bài viết.
- *Ví dụ:*
  ```markdown
  ## Rubric
  - Technical Value: Cung cấp mẹo lập trình hữu ích, có giá trị thực tế.
  - Tone: Thân thiện, không mang tính quảng cáo.
  ```

---

## ❌ Các lỗi thường gặp khiến Hệ thống Báo Lỗi (`PolicyValidationError`)

Hệ thống sẽ ngay lập tức dừng chạy và thông báo lỗi rõ ràng nếu bạn mắc các lỗi sau:
1. **Thiếu Tiêu đề chính:** Quên dòng `# Policy: <name>` ở đầu file.
2. **Thiếu Metadata:** Không có dòng `Threshold:` hoặc `Model Route:`.
3. **Giá trị Threshold sai:** Nhập chữ thay vì số (ví dụ: `Threshold: High`).
4. **Thiếu section bắt buộc:** Quên một trong 4 phần (`## Goal`, `## Constraints`, `## Examples`, `## Rubric`).
5. **Section rỗng:** Khai báo tiêu đề `## Constraints` nhưng không ghi dấu gạch đầu dòng `-` nào bên dưới.

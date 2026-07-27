# Self-review checklist cho system prompt (6 items)

Theo *System Prompt Testing Checklist*. Tick từng mục dựa trên kết quả
`python run_tests.py` và `python demo_errors.py`.

- [x] **Happy path** — câu hỏi trong scope trả lời đúng format?
  → Test 1 & 2: gọi đúng tool, trả JSON `{intent, action, reply}`. ✅
- [x] **Edge case** — câu hỏi mơ hồ/thiếu thông tin → hỏi lại chứ không đoán bừa?
  → Test 4 ("Cho tôi xem thời tiết đi" — thiếu thành phố) → hỏi lại, không gọi tool. ✅
- [x] **Out of scope** — câu hỏi ngoài phạm vi → từ chối đúng cách?
  → Test 5 (giá bitcoin) → từ chối, dẫn chiếu Constraints. ✅
- [x] **Adversarial** — prompt injection / ép "best guess" → có bị bypass?
  → Demo lỗi 1: `BROKEN_SYSTEM_PROMPT` bị bịa; `SYSTEM_PROMPT` có Constraints thì
    không. ✅ (bài học: policy layer phải rõ boundary)
- [x] **Tool decision** — khi nào gọi tool vs khi nào trả lời trực tiếp?
  → 2/5 câu gọi tool (đủ dữ liệu), 3/5 trả lời trực tiếp (chào hỏi / thiếu thông
    tin / ngoài phạm vi). ✅
- [x] **Format consistency** — nhiều câu khác nhau → output format nhất quán?
  → Cả 5 câu đều trả JSON đúng 3 field `{intent, action, reply}`. ✅

## Nếu chuyển sang model thật (Google Gemini)
Chạy lại `run_tests.py` với `LAB_MODEL=gemini` 10–20 lần và đo
**consistency**: nếu < 90% pass thì cần iterate prompt/schema (slide *Prompt
Evaluation Framework*). MockModel tất định nên luôn 100% — dùng để dạy cơ chế,
không thay thế việc đo độ ổn định trên model thật.

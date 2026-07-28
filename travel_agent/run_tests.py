"""
run_tests.py — Bộ test chứng minh KHI NÀO agent trả lời trực tiếp, KHI NÀO gọi tool.

Bám sát "System Prompt Testing Checklist":
  - Happy path (gọi đúng tool)
  - Tool decision (khi nào tool vs khi nào direct)
  - Edge case (thiếu thông tin bắt buộc -> hỏi lại, không tool)
  - Out of scope (từ chối đúng cách, không tool)

Mỗi câu có `expect_tool` (kỳ vọng) để tự động kiểm tra hành vi tool-decision.
"""

from __future__ import annotations

from agent import run_agent
from llm import get_model

# (câu hỏi, tool kỳ vọng hoặc None nếu kỳ vọng trả lời trực tiếp, ghi chú)
TEST_CASES = [
    ("Tôi muốn đi chơi ở Hà Nội",
     "search_places",
     "Happy path — data query: có thành phố -> GỌI TOOL search_places."),

    ("Ở Đà Nẵng có quán ăn ngon nào không?",
     "search_places",
     "Happy path — data query có category (ẩm thực) -> GỌI TOOL search_places."),

    ("Nên đi Sa Pa vào mùa nào?",
     "get_travel_info",
     "Happy path — API wrapper: hỏi thời điểm -> GỌI TOOL get_travel_info."),

    ("Xin chào, bạn là ai?",
     None,
     "Conditional/direct: chào hỏi -> TRẢ LỜI TRỰC TIẾP, không tool."),

    ("Tôi muốn đi chơi",
     None,
     "Edge case: muốn đi chơi nhưng THIẾU thành phố -> hỏi lại, KHÔNG tool."),

    ("Giúp tôi đặt vé máy bay đi Đà Nẵng",
     None,
     "Out of scope: đặt vé -> TỪ CHỐI/escalate trực tiếp, không tool."),
]


def main() -> None:
    model = get_model()  # mặc định MockModel
    passed = 0
    summary = []

    for i, (question, expected_tool, note) in enumerate(TEST_CASES, 1):
        print(f"\n########## TEST {i}: {note}")
        trace = run_agent(question, model=model)

        actual_tool = trace.tool_calls[0] if trace.called_tool else None
        ok = actual_tool == expected_tool
        passed += ok

        exp = expected_tool or "DIRECT (không tool)"
        act = actual_tool or "DIRECT (không tool)"
        print(f"{'-'*70}")
        print(f"  Kỳ vọng: {exp:32}  Thực tế: {act:32}  {'✅ PASS' if ok else '❌ FAIL'}")
        summary.append((i, exp, act, ok))

    print(f"\n{'='*70}")
    print(f"KẾT QUẢ: {passed}/{len(TEST_CASES)} test PASS")
    print(f"{'='*70}")
    print(f"{'#':<3}{'Kỳ vọng':<34}{'Thực tế':<34}{'':<6}")
    for i, exp, act, ok in summary:
        print(f"{i:<3}{exp:<34}{act:<34}{'PASS' if ok else 'FAIL'}")
    print("\nGhi chú: 3 câu GỌI TOOL (mỗi tool ít nhất 1 câu), 3 câu TRẢ LỜI TRỰC TIẾP")
    print("(chào hỏi / thiếu thông tin / ngoài phạm vi). Đúng như thiết kế policy.")


if __name__ == "__main__":
    main()

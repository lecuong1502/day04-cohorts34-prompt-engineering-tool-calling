"""
agent.py — Chatbot du lịch: nối tools vào agent loop.

Cài đặt đúng "Tool Calling Flow":
    LLM decides -> tool_call JSON -> App executes tool -> tool result -> LLM final.

Và "3 Tool Use Patterns":
    1. Conditional: agent tự quyết định gọi tool hay trả lời trực tiếp.
    2. Chaining/loop: lặp cho tới khi model không còn muốn gọi tool.
    3. Refusal: từ chối trực tiếp khi câu hỏi ngoài phạm vi (đặt vé, thanh toán...).

Điểm quan trọng:
    - Model KHÔNG tự chạy tool. Application nhận tool_call -> execute -> trả kết quả lại.
    - Phải có giới hạn vòng lặp (max_steps) để tránh loop vô hạn.
    - Phải feed tool result trở lại model, nếu quên -> LỖI CONTROL FLOW.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from llm import MockModel
from system_prompt import SYSTEM_PROMPT
from tools import execute_tool, tool_schemas


@dataclass
class Trace:
    """Nhật ký một lượt chạy agent — để chứng minh khi nào direct, khi nào tool."""
    user_msg: str
    steps: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    final_reply: str = ""

    def log(self, msg: str) -> None:
        self.steps.append(msg)

    @property
    def called_tool(self) -> bool:
        return len(self.tool_calls) > 0


def run_agent(user_msg: str, model=None, system_prompt: str = SYSTEM_PROMPT,
              max_steps: int = 3, verbose: bool = True) -> Trace:
    """Chạy một lượt hội thoại qua agent loop. Trả về Trace để quan sát/đánh giá."""
    model = model or MockModel()
    trace = Trace(user_msg=user_msg)
    schemas = tool_schemas()
    tool_names = [t["function"]["name"] for t in schemas]

    # --- Bước 1: LLM decides (conditional tool use) ---
    resp = model.decide(system_prompt, user_msg, tool_names, schemas)

    step = 0
    while resp.wants_tool and step < max_steps:
        step += 1
        for call in resp.tool_calls:
            trace.log(f"[decide] model muốn gọi tool: {call.name}({call.arguments})")
            trace.tool_calls.append(call.name)

            # --- Bước 2+3: App executes tool -> tool result ---
            result = execute_tool(call.name, call.arguments)
            trace.log(f"[execute] {call.name} -> {json.dumps(result, ensure_ascii=False)}")

            # --- Bước 4: feed tool result trở lại model -> final response ---
            resp = model.summarize_tool_result(call.name, result, user_msg)

    if not trace.called_tool:
        trace.log("[decide] model trả lời TRỰC TIẾP (không gọi tool)")
    trace.final_reply = resp.text or ""

    if verbose:
        _print_trace(trace)
    return trace


def _print_trace(trace: Trace) -> None:
    print(f"\n{'='*70}")
    print(f"USER: {trace.user_msg}")
    print(f"{'-'*70}")
    for s in trace.steps:
        print("  " + s)
    tag = "TOOL" if trace.called_tool else "DIRECT"
    print(f"{'-'*70}")
    print(f"[{tag}] FINAL: {trace.final_reply}")


def _chat_loop() -> None:
    print("\nGõ câu hỏi (vd: 'Tôi muốn đi chơi ở Hà Nội'), Ctrl+D hoặc 'exit' để thoát.")
    while True:
        try:
            msg = input("\n> ").strip()
        except EOFError:
            break
        if not msg or msg.lower() in ("exit", "quit"):
            break
        run_agent(msg)


if __name__ == "__main__":
    prompt = input()
    run_agent(prompt)
    # run_agent("Ở Đà Nẵng có quán ăn ngon nào không?")
    # run_agent("Nên đi Sa Pa vào mùa nào?")
    # run_agent("Xin chào, bạn là ai?")
    # run_agent("Tôi muốn đi chơi")
    # run_agent("Giúp tôi đặt vé máy bay đi Đà Nẵng")
    _chat_loop()

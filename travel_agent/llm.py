"""
llm.py — Lớp model pluggable cho chatbot du lịch.

Slide "Tool Calling Flow": LLM decides -> tool_call JSON -> App executes -> tool
result -> LLM final response. File này lo phần "LLM decides" và "LLM final".

Mặc định dùng MockModel: một model GIẢ LẬP có luật quyết định (rule-based
router) để chatbot CHẠY ĐƯỢC ngay, offline, kết quả tất định. Đây KHÔNG phải
LLM thật — nó minh hoạ đúng 3 pattern (conditional / direct / refusal) bằng
cách route theo từ khoá + policy trong system prompt, y hệt cách model thật sẽ
"quyết định" dựa trên system prompt + tool schema.

Muốn dùng model thật (Gemini/Anthropic), xem adapter `_GeminiModel` /
`_AnthropicModel` ở `../llm.py` (thư mục gốc của lab) — chỉ cần đổi
tool_schemas() sang bộ 2 tool của module này, vòng lặp agent không đổi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict
    id: str = "call_1"


@dataclass
class ModelResponse:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tool(self) -> bool:
        return len(self.tool_calls) > 0


# ---------------------------------------------------------------------------
# MOCK MODEL — router tất định, minh hoạ "khi nào gọi tool, khi nào direct".
# ---------------------------------------------------------------------------
class MockModel:
    """Mô phỏng model quyết định: gọi search_places / get_travel_info / trả lời
    trực tiếp / từ chối (out of scope), dựa trên từ khoá trong câu hỏi.
    """

    _BOOKING_KW = (
        "đặt vé", "đặt phòng", "đặt khách sạn", "mua vé", "thanh toán",
        "chuyển tiền", "booking", "book vé", "book phòng",
    )
    _SEASON_KW = (
        "mùa nào", "tháng nào", "thời điểm nào", "khi nào nên đi",
        "nên đi vào", "thời tiết du lịch", "mùa đẹp",
    )
    _PLACE_KW = (
        "đi chơi", "du lịch", "tham quan", "đi đâu", "chơi gì", "ăn gì",
        "quán ăn", "ẩm thực", "địa điểm", "điểm đến", "có gì hay",
        "có gì thú vị", "vui chơi", "khám phá",
    )
    _GREET_KW = ("xin chào", "chào", "bạn là ai", "hello", "hi ")

    _CITIES = {
        "hà nội": "Hà Nội", "ha noi": "Hà Nội", "hanoi": "Hà Nội",
        "đà nẵng": "Đà Nẵng", "da nang": "Đà Nẵng", "danang": "Đà Nẵng",
        "hồ chí minh": "Hồ Chí Minh", "sài gòn": "Hồ Chí Minh",
        "saigon": "Hồ Chí Minh", "hcm": "Hồ Chí Minh", "tphcm": "Hồ Chí Minh",
        "huế": "Huế", "hue": "Huế",
        "hội an": "Hội An", "hoi an": "Hội An",
        "sa pa": "Sa Pa", "sapa": "Sa Pa",
    }
    _CATEGORIES = {
        "ẩm thực": "ẩm thực", "ăn gì": "ẩm thực", "món ăn": "ẩm thực", "quán ăn": "ẩm thực",
        "thiên nhiên": "thiên nhiên", "biển": "thiên nhiên", "núi": "thiên nhiên", "cảnh": "thiên nhiên",
        "vui chơi": "giải trí", "giải trí": "giải trí", "chơi gì": "giải trí",
        "văn hóa": "văn hóa", "di tích": "văn hóa", "lịch sử": "văn hóa",
    }

    def decide(self, system_prompt: str, user_msg: str, tool_names: list[str],
               tools_full: list[dict] | None = None) -> ModelResponse:
        text = user_msg.lower()

        # (1) Ngoài phạm vi: đặt vé/đặt phòng/thanh toán -> từ chối, escalate.
        if any(k in text for k in self._BOOKING_KW):
            return self._direct(
                intent="yêu cầu đặt vé/đặt phòng/thanh toán (ngoài phạm vi)",
                reply=("Xin lỗi, mình chỉ hỗ trợ tra cứu địa điểm và thông tin du lịch, "
                       "không thể đặt vé/đặt phòng hay thanh toán. Bạn vui lòng liên hệ "
                       "đại lý du lịch hoặc bộ phận đặt dịch vụ nhé."),
            )

        # (2) Hỏi thời điểm/mùa nên đi -> get_travel_info.
        if any(k in text for k in self._SEASON_KW) and "get_travel_info" in tool_names:
            city = self._extract_city(text)
            if city is None:
                return self._direct(
                    intent="hỏi thời điểm du lịch nhưng thiếu thành phố",
                    reply="Bạn muốn hỏi thời điểm du lịch của thành phố nào ạ?",
                )
            return ModelResponse(tool_calls=[ToolCall("get_travel_info", {"city": city})])

        # (3) Ý định tìm địa điểm/ăn uống/vui chơi -> search_places.
        if any(k in text for k in self._PLACE_KW) and "search_places" in tool_names:
            city = self._extract_city(text)
            if city is None:
                return self._direct(
                    intent="muốn đi chơi/du lịch nhưng thiếu thành phố",
                    reply="Bạn muốn đi chơi ở thành phố nào ạ?",
                )
            category = self._extract_category(text)
            args = {"city": city}
            if category:
                args["category"] = category
            return ModelResponse(tool_calls=[ToolCall("search_places", args)])

        # (4) Chào hỏi / hỏi bạn là ai -> trả lời trực tiếp, không tool.
        if any(k in text for k in self._GREET_KW):
            return self._direct(
                intent="chào hỏi / hỏi danh tính",
                reply="Chào bạn! Mình là trợ lý du lịch, giúp bạn tìm địa điểm tham "
                      "quan, ăn uống và thời điểm nên đi ở các thành phố Việt Nam.",
            )

        # (5) Không khớp intent nào -> trả lời trực tiếp (không bịa, không gọi tool).
        return self._direct(
            intent="không xác định",
            reply="Mình chưa rõ yêu cầu. Bạn có thể hỏi mình nên đi chơi/ăn gì ở "
                  "một thành phố, hoặc nên đi vào mùa nào.",
        )

    def summarize_tool_result(self, tool_name: str, tool_result: dict, user_msg: str) -> ModelResponse:
        """Lượt 2 của model: biến tool result thành câu trả lời cuối (JSON contract)."""
        if tool_result.get("status") == "error":
            reply = f"Không lấy được dữ liệu: {tool_result.get('message')}."
        elif tool_name == "search_places":
            d = tool_result["data"]
            items = "; ".join(
                f"{r['name']} ({r['category']}, {r['rating']}⭐) - {r['description']}"
                for r in d["results"]
            )
            reply = f"Ở {d['city']} bạn có thể ghé: {items}."
        elif tool_name == "get_travel_info":
            d = tool_result["data"]
            reply = (f"Nên đi {d['city']} vào {d['best_season']}, nhiệt độ trung bình "
                     f"{d['avg_temp_c']}°C. Lưu ý: {d['tip']}")
        else:
            reply = "Đã có kết quả."
        return ModelResponse(text=json.dumps({
            "intent": user_msg, "action": tool_name, "reply": reply,
        }, ensure_ascii=False))

    def _direct(self, intent: str, reply: str) -> ModelResponse:
        return ModelResponse(text=json.dumps({
            "intent": intent, "action": "direct", "reply": reply,
        }, ensure_ascii=False))

    def _extract_city(self, text: str) -> str | None:
        for key in sorted(self._CITIES, key=len, reverse=True):
            if key in text:
                return self._CITIES[key]
        return None

    def _extract_category(self, text: str) -> str | None:
        for key in sorted(self._CATEGORIES, key=len, reverse=True):
            if key in text:
                return self._CATEGORIES[key]
        return None


def get_model(name: str | None = None):
    """Chọn model. Hiện chỉ hỗ trợ 'mock' (offline, tất định)."""
    import os
    name = name or os.environ.get("LAB_MODEL", "mock")
    if name == "mock":
        return MockModel()
    raise ValueError(
        f"Model '{name}' chưa được cài trong travel_agent/llm.py. "
        "Xem _GeminiModel / _AnthropicModel ở llm.py (thư mục gốc) để tham khảo cách nối model thật."
    )

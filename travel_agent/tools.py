"""
tools.py — Hai custom tools cho chatbot du lịch.

  Tool 1 (data query):  search_places(city, category, top_k) -> tìm địa điểm
                          tham quan/ẩm thực/vui chơi tại một thành phố, từ dữ
                          liệu nội bộ data/attractions.csv.
  Tool 2 (API wrapper):  get_travel_info(city)               -> bọc một "API
                          tư vấn du lịch" bên ngoài (giả lập), trả mùa đẹp,
                          nhiệt độ trung bình, lưu ý khi đi.

Bám sát "Tool Schema Anatomy" và "Tool Return Format Best Practices":
  - description = tài liệu cho model: (1) chức năng, (2) KHI NÀO dùng, (3) khi nào KHÔNG dùng.
  - parameters mô tả bằng JSON Schema, có `required`, dùng `enum` để giảm lỗi arguments.
  - Mọi tool TRẢ VỀ JSON có cấu trúc:
        success -> {"status": "success", "data": {...}, "source": "..."}
        error   -> {"status": "error", "message": "...", "code": "..."}

Nguyên tắc thiết kế tool: Single Responsibility, Idempotency, Granularity hợp lý,
Test độc lập. Mỗi tool ở đây làm ĐÚNG một việc nghiệp vụ và test được mà không cần agent.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

_VALID_CATEGORIES = {"văn hóa", "ẩm thực", "thiên nhiên", "giải trí"}


def _normalize_city(city: str) -> str:
    """Chuẩn hoá tên thành phố: bỏ dấu cách thừa, lowercase, gộp vài alias."""
    c = " ".join(city.strip().lower().split())
    aliases = {
        "ha noi": "hà nội", "hà nội": "hà nội", "hanoi": "hà nội",
        "da nang": "đà nẵng", "đà nẵng": "đà nẵng", "danang": "đà nẵng",
        "sài gòn": "hồ chí minh", "saigon": "hồ chí minh", "tphcm": "hồ chí minh",
        "hcm": "hồ chí minh", "hồ chí minh": "hồ chí minh",
        "hue": "huế", "huế": "huế",
        "hoi an": "hội an", "hội an": "hội an",
        "sa pa": "sa pa", "sapa": "sa pa",
    }
    return aliases.get(c, c)


def _load_rows() -> list[dict]:
    with open(DATA_DIR / "attractions.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# TOOL 1 — DATA QUERY: search_places(city, category, top_k)
# ---------------------------------------------------------------------------
def search_places(city: str, category: str | None = None, top_k: int = 3) -> dict:
    """Tìm địa điểm tham quan/ẩm thực/vui chơi tại một thành phố, xếp theo rating."""
    if not city or not city.strip():
        return {
            "status": "error",
            "message": "Thiếu tham số 'city'.",
            "code": "MISSING_ARGUMENT",
        }
    if category is not None and category not in _VALID_CATEGORIES:
        return {
            "status": "error",
            "message": f"category không hợp lệ. Chọn một trong {sorted(_VALID_CATEGORIES)}.",
            "code": "INVALID_ARGUMENT",
        }

    key = _normalize_city(city)
    rows = _load_rows()
    matched = [
        r for r in rows
        if _normalize_city(r["city"]) == key
        and (category is None or r["category"] == category)
    ]
    matched.sort(key=lambda r: float(r["rating"]), reverse=True)
    matched = matched[: max(1, top_k)]

    if not matched:
        return {
            "status": "error",
            "message": f"Không có dữ liệu địa điểm cho '{city}'"
                       + (f" (loại '{category}')" if category else "") + ".",
            "code": "NO_DATA",
        }

    return {
        "status": "success",
        "data": {
            "city": matched[0]["city"],
            "category": category or "tất cả",
            "results": [
                {
                    "name": r["name"],
                    "category": r["category"],
                    "description": r["description"],
                    "rating": float(r["rating"]),
                }
                for r in matched
            ],
        },
        "source": "data/attractions.csv",
    }


SEARCH_PLACES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_places",
        "description": (
            "Tìm địa điểm du lịch (danh lam thắng cảnh, quán ăn, hoạt động vui "
            "chơi) tại MỘT thành phố cụ thể, có thể lọc theo loại hình. Dùng KHI "
            "người dùng hỏi nên đi đâu / ăn gì / chơi gì tại một thành phố. KHÔNG "
            "dùng khi người dùng chưa nói rõ thành phố nào, hoặc hỏi về thời "
            "điểm/mùa nên đi (dùng get_travel_info)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Tên thành phố, ví dụ: 'Hà Nội', 'Hội An'.",
                },
                "category": {
                    "type": "string",
                    "description": "Lọc theo loại địa điểm (tuỳ chọn).",
                    "enum": sorted(_VALID_CATEGORIES),
                },
                "top_k": {
                    "type": "integer",
                    "description": "Số lượng kết quả tối đa muốn trả về (tuỳ chọn, mặc định 3).",
                },
            },
            "required": ["city"],
        },
    },
}


# ---------------------------------------------------------------------------
# TOOL 2 — API WRAPPER: get_travel_info(city)
# ---------------------------------------------------------------------------
# Mô phỏng một "API tư vấn du lịch" bên ngoài: mùa đẹp, nhiệt độ trung bình,
# lưu ý khi đi. Chạy OFFLINE bằng backend giả lập để lab luôn chạy được.
_TRAVEL_INFO_BACKEND = {
    "hà nội": {
        "best_season": "Mùa thu, tháng 9-11",
        "avg_temp_c": "18-28",
        "tip": "Mang áo khoác nhẹ buổi tối, tránh mùa hè nóng ẩm tháng 6-8.",
    },
    "đà nẵng": {
        "best_season": "Tháng 2-5 (mùa khô, ít mưa)",
        "avg_temp_c": "22-30",
        "tip": "Tránh mùa mưa bão tháng 9-11.",
    },
    "hồ chí minh": {
        "best_season": "Tháng 12-4 (mùa khô)",
        "avg_temp_c": "25-33",
        "tip": "Mang ô vì mưa bất chợt vào mùa mưa (tháng 5-11).",
    },
    "huế": {
        "best_season": "Tháng 1-4 (khô ráo, mát mẻ)",
        "avg_temp_c": "20-29",
        "tip": "Tránh mùa mưa lũ tháng 9-11.",
    },
    "hội an": {
        "best_season": "Tháng 2-4",
        "avg_temp_c": "22-30",
        "tip": "Ghé vào ngày 14 âm lịch để xem lễ hội đèn lồng phố cổ.",
    },
    "sa pa": {
        "best_season": "Tháng 9-11 hoặc tháng 3-5",
        "avg_temp_c": "12-20",
        "tip": "Mang áo ấm, nhiệt độ ban đêm có thể xuống dưới 10°C.",
    },
}


def get_travel_info(city: str) -> dict:
    """Trả về thông tin thời điểm lý tưởng du lịch của một thành phố."""
    if not city or not city.strip():
        return {
            "status": "error",
            "message": "Thiếu tham số 'city'.",
            "code": "MISSING_ARGUMENT",
        }

    key = _normalize_city(city)
    if key not in _TRAVEL_INFO_BACKEND:
        return {
            "status": "error",
            "message": f"Không có dữ liệu tư vấn du lịch cho '{city}'.",
            "code": "CITY_NOT_FOUND",
        }
    info = _TRAVEL_INFO_BACKEND[key]
    return {
        "status": "success",
        "data": {"city": key.title(), **info},
        "source": "fake-travel-advisory-api (offline)",
    }


GET_TRAVEL_INFO_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_travel_info",
        "description": (
            "Lấy thông tin thời điểm lý tưởng để du lịch (mùa đẹp, nhiệt độ "
            "trung bình, lưu ý) của MỘT thành phố. Dùng KHI người dùng hỏi nên "
            "đi vào mùa/tháng nào, hoặc thời tiết du lịch nói chung. KHÔNG dùng "
            "khi người dùng hỏi địa điểm/quán ăn cụ thể (dùng search_places), "
            "hoặc hỏi thời tiết CHÍNH XÁC hôm nay (ngoài phạm vi tool này)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Tên thành phố, ví dụ: 'Sa Pa', 'Đà Nẵng'.",
                }
            },
            "required": ["city"],
        },
    },
}


# ---------------------------------------------------------------------------
# TOOL REGISTRY — nối tên tool -> (schema, hàm thực thi)
# ---------------------------------------------------------------------------
TOOLS = {
    "search_places": {"schema": SEARCH_PLACES_SCHEMA, "fn": search_places},
    "get_travel_info": {"schema": GET_TRAVEL_INFO_SCHEMA, "fn": get_travel_info},
}


def tool_schemas() -> list[dict]:
    """Danh sách schema để truyền cho model qua tham số `tools`."""
    return [t["schema"] for t in TOOLS.values()]


def execute_tool(name: str, arguments: dict) -> dict:
    """Application thực thi tool call và trả về JSON kết quả."""
    if name not in TOOLS:
        return {"status": "error", "message": f"Tool '{name}' không tồn tại.", "code": "TOOL_NOT_FOUND"}
    try:
        return TOOLS[name]["fn"](**arguments)
    except TypeError as e:
        return {"status": "error", "message": f"Arguments không hợp lệ: {e}", "code": "BAD_ARGUMENTS"}


if __name__ == "__main__":
    # Test độc lập từng tool TRƯỚC khi gắn vào agent (nguyên tắc 'Test độc lập').
    print("search_places('Hà Nội') ->",
          json.dumps(search_places("Hà Nội"), ensure_ascii=False))
    print("search_places('Đà Nẵng', 'ẩm thực') ->",
          json.dumps(search_places("Đà Nẵng", "ẩm thực"), ensure_ascii=False))
    print("search_places('Paris') ->",
          json.dumps(search_places("Paris"), ensure_ascii=False))
    print("get_travel_info('Sa Pa') ->",
          json.dumps(get_travel_info("Sa Pa"), ensure_ascii=False))
    print("get_travel_info('Mars') ->",
          json.dumps(get_travel_info("Mars"), ensure_ascii=False))

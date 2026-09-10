"""Decode answer text without treating reasoning blocks as the final answer."""
import json
import re
from typing import Any


def answer_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, str) or (
                isinstance(block, dict) and block.get("type") in ("text", "output_text")
            )
        )
    if not isinstance(content, str):
        raise ValueError("模型没有返回文本答案")
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def parse_json_answer(response: Any, expected_type: type = dict) -> Any:
    text = answer_text(response)
    decoder = json.JSONDecoder()
    # raw_decode respects nested arrays and braces inside strings.
    for match in re.finditer(r"[\[{]", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, expected_type):
            return value
    raise ValueError("模型答案中没有有效的 JSON")

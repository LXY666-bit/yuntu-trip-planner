"""知名地标列表 — 从 JSON 文件加载"""

import json as _json
from pathlib import Path

_LANDMARKS_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "known_landmarks.json"

with open(_LANDMARKS_PATH, "r", encoding="utf-8") as _f:
    KNOWN_LANDMARKS: list = _json.load(_f)

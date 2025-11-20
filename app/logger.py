# app/logger.py
from __future__ import annotations

import json
import os
from typing import Any, Dict


class TransitionLogger:
    """
    Simple synchronous JSONL logger.
    Writes on every move.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    def log(self, record: Dict[str, Any]):
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

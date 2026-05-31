from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".cassettify"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    client_id: str
    client_secret: str
    output_dir: str

    @classmethod
    def load(cls) -> Optional["Config"]:
        if not CONFIG_FILE.exists():
            return None
        data = json.loads(CONFIG_FILE.read_text())
        return cls(**data)

    def save(self) -> None:
        CONFIG_DIR.mkdir(exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))

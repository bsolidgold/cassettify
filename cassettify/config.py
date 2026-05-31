from __future__ import annotations
import json
import os
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
        CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)
        CONFIG_DIR.chmod(0o700)  # re-apply in case dir already existed
        fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(asdict(self), f, indent=2)

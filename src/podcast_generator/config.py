from pathlib import Path
from pydantic import BaseModel
import yaml

class AppConfig(BaseModel):
    paths: dict
    llm: dict | None = None
    selection: dict | None = None
    appraisal: dict | None = None

def load_yaml(path: str | Path) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(**raw)
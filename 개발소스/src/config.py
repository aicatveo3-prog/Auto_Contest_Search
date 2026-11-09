from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "settings.yaml"


def load_settings(path=None):
    settings_path = Path(path) if path else DEFAULT_SETTINGS
    with open(settings_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    config["_settings_path"] = str(settings_path)
    return config


def resolve(path):
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate

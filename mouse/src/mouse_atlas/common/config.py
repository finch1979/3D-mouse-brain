"""Small YAML config loader for per-mouse-age settings in mouse/configs/."""

import yaml

from mouse_atlas.common.paths import CONFIGS_DIR


def load_config(name):
    path = CONFIGS_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

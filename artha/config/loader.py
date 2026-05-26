import yaml
import os
from typing import Any, Dict

def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f)

# Global config instance (optional, but convenient)
config = load_config()

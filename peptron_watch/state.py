import json
import os

_HEALTH_DEFAULT = {"consecutive_failures": 0, "alerted": False}


def _path(state_dir, name):
    return os.path.join(state_dir, name)


def load_snapshot(state_dir, target_key):
    p = _path(state_dir, f"{target_key}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(state_dir, target_key, items):
    os.makedirs(state_dir, exist_ok=True)
    p = _path(state_dir, f"{target_key}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def load_heartbeat(state_dir):
    p = _path(state_dir, "heartbeat.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_heartbeat(state_dir, timestamp_iso):
    os.makedirs(state_dir, exist_ok=True)
    with open(_path(state_dir, "heartbeat.json"), "w", encoding="utf-8") as f:
        json.dump({"last_run": timestamp_iso}, f, ensure_ascii=False, indent=2)


def load_health(state_dir):
    p = _path(state_dir, "health.json")
    if not os.path.exists(p):
        return dict(_HEALTH_DEFAULT)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_health(state_dir, health):
    os.makedirs(state_dir, exist_ok=True)
    with open(_path(state_dir, "health.json"), "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)

import json
import os
from dataclasses import dataclass, asdict
from datetime import date as date_cls, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

LOG_FILE = os.getenv("LOG_FILE", "logs.json")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")


@dataclass
class DailyLog:
    date: str
    weight_kg: Optional[float] = None
    exercise_kcal: float = 0.0
    exercise_note: str = ""
    food_kcal: float = 0.0
    food_protein_g: float = 0.0


def _load_all() -> dict[str, DailyLog]:
    if not os.path.exists(LOG_FILE):
        return {}
    with open(LOG_FILE, "r") as f:
        raw = json.load(f)
    return {d: DailyLog(**entry) for d, entry in raw.items()}


def _save_all(logs: dict[str, DailyLog]) -> None:
    with open(LOG_FILE, "w") as f:
        json.dump({d: asdict(log) for d, log in logs.items()}, f, indent=2)


def today_str() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).date().isoformat()


def get_log(d: Optional[str] = None) -> DailyLog:
    d = d or today_str()
    return _load_all().get(d, DailyLog(date=d))


def log_weight(weight_kg: float, d: Optional[str] = None) -> DailyLog:
    d = d or today_str()
    logs = _load_all()
    entry = logs.get(d, DailyLog(date=d))
    entry.weight_kg = weight_kg
    logs[d] = entry
    _save_all(logs)
    return entry


def log_exercise(kcal: float, note: str = "", d: Optional[str] = None) -> DailyLog:
    d = d or today_str()
    logs = _load_all()
    entry = logs.get(d, DailyLog(date=d))
    entry.exercise_kcal += kcal
    if note:
        entry.exercise_note = "; ".join(filter(None, [entry.exercise_note, note]))
    logs[d] = entry
    _save_all(logs)
    return entry


def log_food(kcal: float, protein_g: float = 0.0, d: Optional[str] = None) -> DailyLog:
    d = d or today_str()
    logs = _load_all()
    entry = logs.get(d, DailyLog(date=d))
    entry.food_kcal += kcal
    entry.food_protein_g += protein_g
    logs[d] = entry
    _save_all(logs)
    return entry


def get_range(days: int, end_date: Optional[str] = None) -> list[DailyLog]:
    end = date_cls.fromisoformat(end_date) if end_date else date_cls.fromisoformat(today_str())
    logs = _load_all()
    return [
        logs.get((end - timedelta(days=i)).isoformat(), DailyLog(date=(end - timedelta(days=i)).isoformat()))
        for i in range(days - 1, -1, -1)
    ]

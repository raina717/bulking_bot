import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

PROFILE_FILE = os.getenv("PROFILE_FILE", "profile.json")

VALID_ACTIVITY_LEVELS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


@dataclass
class Profile:
    weight_kg: float
    height_cm: float
    age: int
    gender: str
    activity_level: str
    target_gain_kg: float
    target_weeks: float
    updated_at: str = ""

    def to_dict(self):
        return asdict(self)


def load_profile() -> Optional[Profile]:
    if not os.path.exists(PROFILE_FILE):
        return None
    with open(PROFILE_FILE, "r") as f:
        data = json.load(f)
    return Profile(**data)


def save_profile(profile: Profile) -> None:
    profile.updated_at = datetime.utcnow().isoformat()
    with open(PROFILE_FILE, "w") as f:
        json.dump(profile.to_dict(), f, indent=2)

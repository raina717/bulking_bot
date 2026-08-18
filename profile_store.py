"""
Penyimpanan profil user secara sederhana pakai file JSON.
Karena bot ini cuma dipakai 1 orang (owner), gak perlu database.
"""
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

PROFILE_FILE = os.getenv("PROFILE_FILE", "profile.json")

VALID_ACTIVITY_LEVELS = {
    "sedentary": 1.2,       # kerja duduk, jarang olahraga
    "light": 1.375,         # olahraga ringan 1-3x/minggu
    "moderate": 1.55,       # olahraga sedang 3-5x/minggu
    "active": 1.725,        # olahraga berat 6-7x/minggu
    "very_active": 1.9,     # olahraga berat + kerja fisik / 2x sehari
}


@dataclass
class Profile:
    weight_kg: float
    height_cm: float
    age: int
    gender: str  # "male" atau "female"
    activity_level: str  # salah satu dari VALID_ACTIVITY_LEVELS
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

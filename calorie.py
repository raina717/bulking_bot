from dataclasses import dataclass
from profile_store import Profile, VALID_ACTIVITY_LEVELS

KCAL_PER_KG_GAIN = 7700
SAFE_MAX_DAILY_SURPLUS = 700
SAFE_MIN_DAILY_SURPLUS = 200


@dataclass
class BulkingPlan:
    bmr: float
    tdee: float
    daily_surplus: float
    target_calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    warning: str = ""


def calculate_bmr(profile: Profile) -> float:
    base = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age
    if profile.gender.lower().startswith("m"):
        return base + 5
    return base - 161


def calculate_tdee(profile: Profile) -> float:
    multiplier = VALID_ACTIVITY_LEVELS.get(profile.activity_level, 1.55)
    return calculate_bmr(profile) * multiplier


def calculate_bulking_plan(profile: Profile) -> BulkingPlan:
    bmr = calculate_bmr(profile)
    tdee = calculate_tdee(profile)

    total_days = max(profile.target_weeks * 7, 1)
    total_kcal_needed = profile.target_gain_kg * KCAL_PER_KG_GAIN
    daily_surplus = total_kcal_needed / total_days

    warning = ""
    if daily_surplus > SAFE_MAX_DAILY_SURPLUS:
        warning = (
            f"Your target requires a surplus of ~{daily_surplus:.0f} kcal/day, which is quite "
            f"aggressive (usually above {SAFE_MAX_DAILY_SURPLUS} kcal/day leads to more fat gain "
            f"than muscle). Consider a longer time frame for leaner gains."
        )
    elif daily_surplus < SAFE_MIN_DAILY_SURPLUS:
        warning = (
            f"Your surplus is only ~{daily_surplus:.0f} kcal/day, so progress will be slow. "
            f"This is fine if lean bulking is your priority, but you may want to increase it "
            f"slightly to reach your time target."
        )

    target_calories = tdee + daily_surplus

    protein_g = profile.weight_kg * 2.0
    fat_g = (target_calories * 0.25) / 9
    protein_kcal = protein_g * 4
    fat_kcal = fat_g * 9
    carbs_g = max((target_calories - protein_kcal - fat_kcal) / 4, 0)

    return BulkingPlan(
        bmr=round(bmr),
        tdee=round(tdee),
        daily_surplus=round(daily_surplus),
        target_calories=round(target_calories),
        protein_g=round(protein_g),
        fat_g=round(fat_g),
        carbs_g=round(carbs_g),
        warning=warning,
    )


def format_plan_message(profile: Profile, plan: BulkingPlan) -> str:
    lines = [
        f"📊 *Your Daily Requirements Summary*",
        f"BMR: {plan.bmr} kcal",
        f"TDEE (maintenance): {plan.tdee} kcal",
        f"Target surplus: +{plan.daily_surplus} kcal/day",
        f"🎯 *Daily Calorie Target: {plan.target_calories} kcal*",
        "",
        f"🥩 Protein: {plan.protein_g} g/day",
        f"🥑 Fat: {plan.fat_g} g/day",
        f"🍚 Carbs: {plan.carbs_g} g/day",
        "",
        f"(Target: gain {profile.target_gain_kg} kg in {profile.target_weeks:.0f} weeks)",
    ]
    if plan.warning:
        lines.append("")
        lines.append(f"⚠️ {plan.warning}")
    return "\n".join(lines)

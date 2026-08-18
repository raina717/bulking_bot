"""
Kalkulasi kebutuhan kalori & protein harian buat bulking.

Rumus:
- BMR: Mifflin-St Jeor (paling akurat & paling umum dipakai sekarang)
- TDEE: BMR x activity multiplier
- Surplus kalori: dihitung dari target kenaikan berat badan dibagi
  jumlah hari, pakai estimasi ~7700 kkal per 1 kg kenaikan berat
  (ini estimasi kasar campuran otot+lemak, prakteknya bisa beda-beda
  tergantung training & genetik).
- Protein: 2 g per kg berat badan (di rentang aman/optimal buat bulking,
  yaitu 1.6-2.2 g/kg menurut riset ISSN).
- Fat: ~25% dari total kalori.
- Carbs: sisanya.
"""
from dataclasses import dataclass
from profile_store import Profile, VALID_ACTIVITY_LEVELS

KCAL_PER_KG_GAIN = 7700  # estimasi energi buat naik 1 kg berat badan
SAFE_MAX_DAILY_SURPLUS = 700  # di atas ini, gain kemungkinan besar didominasi lemak
SAFE_MIN_DAILY_SURPLUS = 200  # di bawah ini, progres bulking bakal kerasa lambat


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
            f"Target kamu butuh surplus ~{daily_surplus:.0f} kkal/hari, itu cukup "
            f"agresif (biasanya di atas {SAFE_MAX_DAILY_SURPLUS} kkal/hari bikin gain "
            f"lebih banyak ke lemak daripada otot). Pertimbangkan target waktu lebih "
            f"panjang biar gain-nya lebih lean."
        )
    elif daily_surplus < SAFE_MIN_DAILY_SURPLUS:
        warning = (
            f"Surplus kamu cuma ~{daily_surplus:.0f} kkal/hari, progresnya bakal pelan. "
            f"Gapapa kalau memang prioritas lean bulk, tapi kalau mau ngejar target "
            f"waktu, boleh dinaikin dikit."
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
        f"📊 *Ringkasan kebutuhan harian kamu*",
        f"BMR: {plan.bmr} kkal",
        f"TDEE (maintenance): {plan.tdee} kkal",
        f"Target surplus: +{plan.daily_surplus} kkal/hari",
        f"🎯 *Target kalori harian: {plan.target_calories} kkal*",
        "",
        f"🥩 Protein: {plan.protein_g} g/hari",
        f"🥑 Fat: {plan.fat_g} g/hari",
        f"🍚 Carbs: {plan.carbs_g} g/hari",
        "",
        f"(Target: naik {profile.target_gain_kg} kg dalam {profile.target_weeks:.0f} minggu)",
    ]
    if plan.warning:
        lines.append("")
        lines.append(f"⚠️ {plan.warning}")
    return "\n".join(lines)

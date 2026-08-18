"""
Analisis progress mingguan: bandingin rata-rata berat badan & asupan aktual
vs target dari profile, kasih saran adjust surplus kalau perlu.

Prinsip (sesuai riset umum soal bulking): pakai rata-rata mingguan buat
banding berat badan, bukan angka harian, karena fluktuasi harian sering
cuma air/glycogen bukan gain otot/lemak beneran.

Catatan: kalori exercise (dari Huawei Health) TIDAK ditambahin balik ke
budget makan harian, karena TDEE di calorie.py sudah mengasumsikan level
aktivitas (activity_level) yang mencakup olahraga rutin. Data exercise di
sini cuma buat referensi/cross-check, biar activity_level di profil tetap
representatif sama aktivitas asli.
"""
from dataclasses import dataclass
from datetime import date as date_cls, timedelta
from statistics import mean
from typing import Optional

from calorie import calculate_tdee
from log_store import DailyLog, get_range
from profile_store import Profile


@dataclass
class WeeklyReview:
    days_logged: int
    avg_weight_this_week: Optional[float]
    avg_weight_prev_week: Optional[float]
    actual_weekly_rate_kg: Optional[float]
    target_weekly_rate_kg: float
    avg_food_kcal: Optional[float]
    avg_food_protein_g: Optional[float]
    avg_exercise_kcal: Optional[float]
    tdee: float
    suggestion: str


def _avg_weight(logs: list[DailyLog]) -> Optional[float]:
    weights = [l.weight_kg for l in logs if l.weight_kg is not None]
    return mean(weights) if weights else None


def _build_suggestion(
    days_logged: int,
    actual_rate: Optional[float],
    target_rate: float,
) -> str:
    if days_logged < 4:
        return (
            "Data minggu ini masih kurang (idealnya timbang & catat makan tiap hari "
            "pakai /berat dan /makan). Lanjutin logging-nya biar rekomendasi ini akurat."
        )
    if actual_rate is None:
        return "Belum bisa dibandingin ke minggu lalu (butuh data berat badan minimal 2 minggu)."

    if actual_rate < target_rate * 0.5:
        return (
            f"Kenaikan BB minggu ini (~{actual_rate:+.2f} kg) di bawah target "
            f"(~{target_rate:.2f} kg/minggu). Kalau ini kejadian 2-3 minggu berturut-turut, "
            f"tambah asupan ~100-150 kkal/hari."
        )
    if actual_rate > target_rate * 1.5:
        return (
            f"Kenaikan BB minggu ini (~{actual_rate:+.2f} kg) lebih cepat dari target "
            f"(~{target_rate:.2f} kg/minggu) — kemungkinan gain-nya lebih banyak ke lemak. "
            f"Pertimbangkan kurangin asupan ~100-150 kkal/hari."
        )
    return f"Progres BB minggu ini (~{actual_rate:+.2f} kg) udah sesuai target. Pertahanin polanya."


def build_weekly_review(profile: Profile) -> WeeklyReview:
    this_week = get_range(7)
    prev_end = (date_cls.fromisoformat(this_week[0].date) - timedelta(days=1)).isoformat()
    prev_week = get_range(7, end_date=prev_end)

    days_logged = sum(1 for l in this_week if l.weight_kg is not None or l.food_kcal > 0)

    avg_w_this = _avg_weight(this_week)
    avg_w_prev = _avg_weight(prev_week)
    actual_rate = (
        avg_w_this - avg_w_prev if avg_w_this is not None and avg_w_prev is not None else None
    )
    target_rate = profile.target_gain_kg / max(profile.target_weeks, 1)

    food_kcals = [l.food_kcal for l in this_week if l.food_kcal > 0]
    food_proteins = [l.food_protein_g for l in this_week if l.food_kcal > 0]
    exercise_kcals = [l.exercise_kcal for l in this_week if l.exercise_kcal > 0]

    return WeeklyReview(
        days_logged=days_logged,
        avg_weight_this_week=avg_w_this,
        avg_weight_prev_week=avg_w_prev,
        actual_weekly_rate_kg=actual_rate,
        target_weekly_rate_kg=target_rate,
        avg_food_kcal=mean(food_kcals) if food_kcals else None,
        avg_food_protein_g=mean(food_proteins) if food_proteins else None,
        avg_exercise_kcal=mean(exercise_kcals) if exercise_kcals else None,
        tdee=calculate_tdee(profile),
        suggestion=_build_suggestion(days_logged, actual_rate, target_rate),
    )


def format_weekly_message(review: WeeklyReview) -> str:
    lines = ["📅 *Ringkasan progress minggu ini*", f"Hari ke-log: {review.days_logged}/7"]
    if review.avg_weight_this_week is not None:
        lines.append(f"Rata-rata BB minggu ini: {review.avg_weight_this_week:.1f} kg")
    if review.avg_weight_prev_week is not None:
        lines.append(f"Rata-rata BB minggu lalu: {review.avg_weight_prev_week:.1f} kg")
    if review.actual_weekly_rate_kg is not None:
        lines.append(
            f"Perubahan: {review.actual_weekly_rate_kg:+.2f} kg "
            f"(target: {review.target_weekly_rate_kg:+.2f} kg/minggu)"
        )
    if review.avg_food_kcal is not None:
        lines.append(f"Rata-rata asupan: {review.avg_food_kcal:.0f} kkal/hari (TDEE: {review.tdee:.0f} kkal)")
    if review.avg_food_protein_g is not None:
        lines.append(f"Rata-rata protein: {review.avg_food_protein_g:.0f} g/hari")
    if review.avg_exercise_kcal is not None:
        lines.append(
            f"Rata-rata kalori olahraga (Huawei Health): {review.avg_exercise_kcal:.0f} kkal/hari "
            f"(referensi, sudah termasuk asumsi di TDEE)"
        )
    lines.append("")
    lines.append(f"💡 {review.suggestion}")
    return "\n".join(lines)

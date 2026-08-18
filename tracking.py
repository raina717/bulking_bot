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
            "Insufficient data this week (ideally, weigh yourself and log meals daily "
            "using /weight and /eat). Keep logging for more accurate recommendations."
        )
    if actual_rate is None:
        return "Cannot compare to last week yet (requires at least 2 weeks of weight data)."

    if actual_rate < target_rate * 0.5:
        return (
            f"Weight gain this week (~{actual_rate:+.2f} kg) is below the target "
            f"(~{target_rate:.2f} kg/week). If this happens for 2-3 consecutive weeks, "
            f"increase your intake by ~100-150 kcal/day."
        )
    if actual_rate > target_rate * 1.5:
        return (
            f"Weight gain this week (~{actual_rate:+.2f} kg) is faster than the target "
            f"(~{target_rate:.2f} kg/week) — this gain might be mostly fat. "
            f"Consider reducing your intake by ~100-150 kcal/day."
        )
    return f"Your weight progress this week (~{actual_rate:+.2f} kg) is right on target. Keep it up."


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
    lines = ["📅 *Weekly Progress Summary*", f"Days logged: {review.days_logged}/7"]
    if review.avg_weight_this_week is not None:
        lines.append(f"Average weight this week: {review.avg_weight_this_week:.1f} kg")
    if review.avg_weight_prev_week is not None:
        lines.append(f"Average weight last week: {review.avg_weight_prev_week:.1f} kg")
    if review.actual_weekly_rate_kg is not None:
        lines.append(
            f"Change: {review.actual_weekly_rate_kg:+.2f} kg "
            f"(target: {review.target_weekly_rate_kg:+.2f} kg/week)"
        )
    if review.avg_food_kcal is not None:
        lines.append(f"Average intake: {review.avg_food_kcal:.0f} kcal/day (TDEE: {review.tdee:.0f} kcal)")
    if review.avg_food_protein_g is not None:
        lines.append(f"Average protein: {review.avg_food_protein_g:.0f} g/day")
    if review.avg_exercise_kcal is not None:
        lines.append(
            f"Average exercise calories (Huawei Health): {review.avg_exercise_kcal:.0f} kcal/day "
            f"(reference only, already assumed in TDEE)"
        )
    lines.append("")
    lines.append(f"💡 {review.suggestion}")
    return "\n".join(lines)

"""
Bot Telegram personal buat bantu tracking bulking:
- Simpen profil (berat, tinggi, umur, gender, level aktivitas, target)
- Hitung BMR/TDEE/target kalori/protein harian
- Kasih saran menu tinggi protein (pakai Claude, fallback Hermes)
- Chat bebas seputar nutrisi/bulking, tetap dipersonalisasi pakai profil kamu

Cuma merespon ke 1 user (TELEGRAM_OWNER_ID) biar aman & hemat API cost.
"""
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from profile_store import Profile, load_profile, save_profile, VALID_ACTIVITY_LEVELS
from calorie import calculate_bulking_plan, format_plan_message
from agents import ask_agent
from log_store import get_log, log_weight, log_exercise, log_food, today_str
from tracking import build_weekly_review, format_weekly_message

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0"))

# States buat ConversationHandler /profile
WEIGHT, HEIGHT, AGE, GENDER, ACTIVITY, TARGET_GAIN, TARGET_WEEKS = range(7)

ACTIVITY_HELP = (
    "Pilih level aktivitas kamu (ketik salah satu):\n"
    "- sedentary: kerja duduk, jarang olahraga\n"
    "- light: olahraga ringan 1-3x/minggu\n"
    "- moderate: olahraga sedang 3-5x/minggu\n"
    "- active: olahraga berat 6-7x/minggu\n"
    "- very_active: olahraga berat + kerja fisik"
)


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_user.id != TELEGRAM_OWNER_ID:
            logger.info("Ignored message from non-owner user %s", update.effective_user)
            return
        return await func(update, context)

    return wrapper


@owner_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Gua bot bulking asisten kamu 💪\n\n"
        "Command yang tersedia:\n"
        "/profile - isi/update data badan & target bulking\n"
        "/kalori - lihat kebutuhan kalori & protein harian\n"
        "/saran - saran menu tinggi protein (nyesuaiin sisa budget hari ini)\n\n"
        "Logging harian (catat manual dari Huawei Health / makanan kamu):\n"
        "/berat <kg> - catat berat badan hari ini\n"
        "/olahraga <kkal> [catatan] - catat kalori terbakar dari Huawei Health\n"
        "/makan <kkal> [protein_g] - catat kalori (& protein) yang udah dimakan\n"
        "/sisa - lihat sisa budget kalori & protein hari ini\n"
        "/minggu - ringkasan progress & saran adjust minggu ini\n\n"
        "Atau langsung chat aja bebas soal nutrisi/bulking, gua jawab pakai AI."
    )


# ---------- /profile conversation ----------

@owner_only
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Berat badan kamu sekarang berapa kg?")
    return WEIGHT


async def profile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["weight_kg"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Masukin angka aja ya, misal: 65")
        return WEIGHT
    await update.message.reply_text("Tinggi badan kamu berapa cm?")
    return HEIGHT


async def profile_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["height_cm"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Masukin angka aja ya, misal: 170")
        return HEIGHT
    await update.message.reply_text("Umur kamu berapa tahun?")
    return AGE


async def profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["age"] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Masukin angka aja ya, misal: 25")
        return AGE
    await update.message.reply_text("Gender kamu? (male/female)")
    return GENDER


async def profile_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in ("male", "female"):
        await update.message.reply_text("Ketik 'male' atau 'female' ya.")
        return GENDER
    context.user_data["gender"] = text
    await update.message.reply_text(ACTIVITY_HELP)
    return ACTIVITY


async def profile_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in VALID_ACTIVITY_LEVELS:
        await update.message.reply_text(
            "Pilihan gak valid. " + ACTIVITY_HELP
        )
        return ACTIVITY
    context.user_data["activity_level"] = text
    await update.message.reply_text(
        "Target naik berat badan berapa kg? (misal: 5)"
    )
    return TARGET_GAIN


async def profile_target_gain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_gain_kg"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Masukin angka aja ya, misal: 5")
        return TARGET_GAIN
    await update.message.reply_text("Target itu mau dicapai dalam berapa minggu? (misal: 8 buat 2 bulan)")
    return TARGET_WEEKS


async def profile_target_weeks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_weeks"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Masukin angka aja ya, misal: 8")
        return TARGET_WEEKS

    profile = Profile(
        weight_kg=context.user_data["weight_kg"],
        height_cm=context.user_data["height_cm"],
        age=context.user_data["age"],
        gender=context.user_data["gender"],
        activity_level=context.user_data["activity_level"],
        target_gain_kg=context.user_data["target_gain_kg"],
        target_weeks=context.user_data["target_weeks"],
    )
    save_profile(profile)

    plan = calculate_bulking_plan(profile)
    await update.message.reply_text("Profil tersimpan! Ini hasil kalkulasinya:")
    await update.message.reply_text(format_plan_message(profile, plan), parse_mode="Markdown")
    return ConversationHandler.END


async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Oke, dibatalin.")
    return ConversationHandler.END


# ---------- /kalori ----------

@owner_only
async def kalori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil kamu belum ada. Isi dulu pakai /profile ya.")
        return
    plan = calculate_bulking_plan(profile)
    await update.message.reply_text(format_plan_message(profile, plan), parse_mode="Markdown")


# ---------- /saran ----------

@owner_only
async def saran(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil kamu belum ada. Isi dulu pakai /profile ya.")
        return

    plan = calculate_bulking_plan(profile)
    today_log = get_log()
    remaining_kcal = max(plan.target_calories - today_log.food_kcal, 0)
    remaining_protein = max(plan.protein_g - today_log.food_protein_g, 0)
    await update.message.reply_text("Bentar, lagi nyusun saran menu...")

    system_prompt = (
        "Kamu adalah asisten nutrisi personal buat orang yang lagi program bulking "
        "(nambah massa otot). Jawab dalam Bahasa Indonesia santai tapi jelas, "
        "pakai poin-poin singkat, dan fokus ke makanan yang gampang ditemukan di Indonesia."
    )
    if today_log.food_kcal > 0 and remaining_kcal <= 50:
        user_message = (
            f"Data aku: berat {profile.weight_kg} kg, target kalori harian "
            f"{plan.target_calories} kkal. Aku udah makan {today_log.food_kcal:.0f} kkal "
            f"hari ini, jadi budget hari ini udah hampir/kelar habis. Kasih 1-2 saran "
            f"snack ringan rendah kalori kalau masih laper, atau bilang aja kalau memang "
            f"udah cukup buat hari ini."
        )
    else:
        user_message = (
            f"Data aku: berat {profile.weight_kg} kg, sisa budget hari ini "
            f"{remaining_kcal:.0f} kkal dan {remaining_protein:.0f} g protein (dari target "
            f"harian {plan.target_calories} kkal / {plan.protein_g} g protein, udah makan "
            f"{today_log.food_kcal:.0f} kkal / {today_log.food_protein_g:.0f} g protein). "
            f"Tolong kasih beberapa contoh menu makanan tinggi protein (sesuai jam makan yang "
            f"masih relevan hari ini) yang mudah didapat di Indonesia, muat di sisa budget "
            f"kalori itu, beserta estimasi kandungan protein & kalori tiap menu."
        )
    answer, agent_used = await ask_agent(system_prompt, user_message)
    await update.message.reply_text(f"{answer}\n\n_(dijawab oleh: {agent_used})_", parse_mode="Markdown")


# ---------- Logging harian (patokan dari Huawei Health / makanan) ----------

def _parse_float(text: str) -> float:
    return float(text.replace(",", "."))


@owner_only
async def berat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /berat <kg>, misal: /berat 65.5")
        return
    try:
        weight = _parse_float(context.args[0])
    except ValueError:
        await update.message.reply_text("Masukin angka aja ya, misal: /berat 65.5")
        return
    log_weight(weight)
    await update.message.reply_text(f"Oke, BB hari ini ({today_str()}) dicatat: {weight} kg.")


@owner_only
async def olahraga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Format: /olahraga <kkal_terbakar> [catatan], misal:\n"
            "/olahraga 350 lari 5k dari Huawei Health"
        )
        return
    try:
        kcal = _parse_float(context.args[0])
    except ValueError:
        await update.message.reply_text("Kkal-nya harus angka ya, misal: /olahraga 350 lari 5k")
        return
    note = " ".join(context.args[1:])
    entry = log_exercise(kcal, note)
    await update.message.reply_text(
        f"Dicatat: +{kcal:.0f} kkal olahraga hari ini (total: {entry.exercise_kcal:.0f} kkal).\n"
        f"Catatan: ini cuma buat referensi/cross-check, gak ditambahin ke budget makan, "
        f"soalnya TDEE kamu udah mengasumsikan level aktivitas kamu."
    )


@owner_only
async def makan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /makan <kkal> [protein_g], misal: /makan 450 35")
        return
    try:
        kcal = _parse_float(context.args[0])
        protein = _parse_float(context.args[1]) if len(context.args) > 1 else 0.0
    except ValueError:
        await update.message.reply_text("Angkanya gak valid ya, misal: /makan 450 35")
        return
    entry = log_food(kcal, protein)
    await update.message.reply_text(
        f"Dicatat: +{kcal:.0f} kkal / +{protein:.0f} g protein.\n"
        f"Total hari ini: {entry.food_kcal:.0f} kkal, {entry.food_protein_g:.0f} g protein.\n"
        f"Cek sisa budget hari ini pakai /sisa."
    )


@owner_only
async def sisa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil kamu belum ada. Isi dulu pakai /profile ya.")
        return
    plan = calculate_bulking_plan(profile)
    today_log = get_log()
    remaining_kcal = plan.target_calories - today_log.food_kcal
    remaining_protein = plan.protein_g - today_log.food_protein_g

    lines = [
        f"📆 *Status hari ini ({today_str()})*",
        f"Target: {plan.target_calories} kkal / {plan.protein_g} g protein",
        f"Udah makan: {today_log.food_kcal:.0f} kkal / {today_log.food_protein_g:.0f} g protein",
        f"Sisa: {remaining_kcal:.0f} kkal / {remaining_protein:.0f} g protein",
    ]
    if today_log.exercise_kcal > 0:
        lines.append(f"Olahraga hari ini (Huawei Health): {today_log.exercise_kcal:.0f} kkal")
    if remaining_kcal < 0:
        lines.append("")
        lines.append("⚠️ Udah lewat target kalori hari ini.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@owner_only
async def minggu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil kamu belum ada. Isi dulu pakai /profile ya.")
        return
    review = build_weekly_review(profile)
    await update.message.reply_text(format_weekly_message(review), parse_mode="Markdown")


# ---------- Chat bebas ----------

@owner_only
async def free_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile:
        plan = calculate_bulking_plan(profile)
        context_str = (
            f"Profil user: berat {profile.weight_kg} kg, tinggi {profile.height_cm} cm, "
            f"umur {profile.age}, target naik {profile.target_gain_kg} kg dalam "
            f"{profile.target_weeks} minggu. Target kalori harian: {plan.target_calories} kkal, "
            f"protein {plan.protein_g} g/hari."
        )
    else:
        context_str = "User belum isi profil, kalau relevan sarankan dia isi /profile dulu."

    system_prompt = (
        "Kamu adalah asisten personal bulking/nutrisi berbahasa Indonesia yang santai "
        "dan suportif. " + context_str
    )
    answer, agent_used = await ask_agent(system_prompt, update.message.text)
    await update.message.reply_text(f"{answer}\n\n_(dijawab oleh: {agent_used})_", parse_mode="Markdown")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN belum diisi di .env")
    if not TELEGRAM_OWNER_ID:
        raise SystemExit("TELEGRAM_OWNER_ID belum diisi di .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_weight)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_height)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_gender)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_activity)],
            TARGET_GAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_target_gain)],
            TARGET_WEEKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_target_weeks)],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(CommandHandler("kalori", kalori))
    app.add_handler(CommandHandler("saran", saran))
    app.add_handler(CommandHandler("berat", berat))
    app.add_handler(CommandHandler("olahraga", olahraga))
    app.add_handler(CommandHandler("makan", makan))
    app.add_handler(CommandHandler("sisa", sisa))
    app.add_handler(CommandHandler("minggu", minggu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_chat))

    logger.info("Bot jalan (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()

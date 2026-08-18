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
from agents import ask_agent, estimate_food_from_text, estimate_food_from_image
from log_store import get_log, log_weight, log_exercise, log_food, today_str
from tracking import build_weekly_review, format_weekly_message

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0"))

WEIGHT, HEIGHT, AGE, GENDER, ACTIVITY, TARGET_GAIN, TARGET_WEEKS = range(7)

ACTIVITY_HELP = (
    "Pilih tingkat aktivitas fisik kamu:\n"
    "- sedentary: kerja kantoran, jarang olahraga\n"
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
        "Halo! Gua bot asisten bulking personal lu 💪\n\n"
        "Command yang tersedia:\n"
        "/profil - isi/update data badan & target bulking\n"
        "/kalori - lihat kebutuhan kalori & protein harian\n"
        "/saran - saran menu tinggi protein (sesuai sisa jatah kalori hari ini)\n\n"
        "Pencatatan Harian:\n"
        "/berat <kg> - catat berat badan hari ini\n"
        "/olahraga <kkal> [catatan] - catat kalori terbakar dari aktivitas\n"
        "/makan <kkal> [protein_g] - catat kalori & protein yang dimakan\n"
        "/makan <deskripsi> - deskripsikan makanan, AI akan estimasi otomatis\n"
        "atau kirim foto makanan - AI akan estimasi kalori dari foto\n"
        "/sisa - cek sisa jatah kalori & protein hari ini\n"
        "/minggu - ringkasan progres mingguan & saran penyesuaian\n\n"
        "Atau chat bebas aja seputar nutrisi/bulking, gua bakal jawab pakai AI."
    )


@owner_only
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Berapa berat badan kamu sekarang (kg)?")
    return WEIGHT


async def profile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["weight_kg"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Tolong masukkan angka, contoh: 65")
        return WEIGHT
    await update.message.reply_text("Berapa tinggi badan kamu (cm)?")
    return HEIGHT


async def profile_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["height_cm"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Tolong masukkan angka, contoh: 170")
        return HEIGHT
    await update.message.reply_text("Berapa umur kamu?")
    return AGE


async def profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["age"] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Tolong masukkan angka bulat, contoh: 25")
        return AGE
    await update.message.reply_text("Apa jenis kelamin kamu? (Ketik: male / female)")
    return GENDER


async def profile_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in ("male", "female"):
        await update.message.reply_text("Tolong ketik 'male' atau 'female'.")
        return GENDER
    context.user_data["gender"] = text
    await update.message.reply_text(ACTIVITY_HELP)
    return ACTIVITY


async def profile_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in VALID_ACTIVITY_LEVELS:
        await update.message.reply_text("Pilihan tidak valid. " + ACTIVITY_HELP)
        return ACTIVITY
    context.user_data["activity_level"] = text
    await update.message.reply_text("Berapa target kenaikan berat badan kamu (kg)? (contoh: 5)")
    return TARGET_GAIN


async def profile_target_gain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_gain_kg"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Tolong masukkan angka, contoh: 5")
        return TARGET_GAIN
    await update.message.reply_text("Dalam berapa minggu kamu ingin mencapai target ini? (contoh: 8)")
    return TARGET_WEEKS


async def profile_target_weeks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_weeks"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Tolong masukkan angka, contoh: 8")
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
    await update.message.reply_text("Profil berhasil disimpan! Berikut rencana kalori harianmu:")
    await update.message.reply_text(format_plan_message(profile, plan), parse_mode="Markdown")
    return ConversationHandler.END


async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses pembuatan profil dibatalkan.")
    return ConversationHandler.END


@owner_only
async def calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil lu belum ada. Tolong buat dulu pakai /profil.")
        return
    plan = calculate_bulking_plan(profile)
    await update.message.reply_text(format_plan_message(profile, plan), parse_mode="Markdown")


@owner_only
async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil lu belum ada. Tolong buat dulu pakai /profil.")
        return

    plan = calculate_bulking_plan(profile)
    today_log = get_log()
    remaining_kcal = max(plan.target_calories - today_log.food_kcal, 0)
    remaining_protein = max(plan.protein_g - today_log.food_protein_g, 0)
    await update.message.reply_text("Tunggu sebentar, sedang menyusun saran makanan...")

    system_prompt = (
        "You are a personal nutrition assistant for someone currently on a bulking program "
        "(gaining muscle mass). Answer in casual Indonesian (pakai lu/gua atau bahasa santai). "
        "Use short bullet points, and focus on foods that are easily available in Indonesia."
    )
    if today_log.food_kcal > 0 and remaining_kcal <= 50:
        user_message = (
            f"My data: weight {profile.weight_kg} kg, daily calorie target "
            f"{plan.target_calories} kcal. I have eaten {today_log.food_kcal:.0f} kcal "
            f"today, so my budget for today is almost/completely exhausted. Please give 1-2 suggestions "
            f"for light, low-calorie snacks if I'm still hungry, or just tell me if I've "
            f"had enough for today."
        )
    else:
        user_message = (
            f"My data: weight {profile.weight_kg} kg, remaining budget for today is "
            f"{remaining_kcal:.0f} kcal and {remaining_protein:.0f} g protein (out of the daily target "
            f"of {plan.target_calories} kcal / {plan.protein_g} g protein, having already eaten "
            f"{today_log.food_kcal:.0f} kcal / {today_log.food_protein_g:.0f} g protein). "
            f"Please give some examples of high-protein meals (suitable for the time of day) "
            f"that are easily available in Indonesia, fit into the remaining calorie budget, along with "
            f"estimated protein & calorie content for each meal."
        )
    answer, agent_used = await ask_agent(system_prompt, user_message)
    await update.message.reply_text(f"{answer}\n\n_(dijawab oleh: {agent_used})_", parse_mode="Markdown")


def _parse_float(text: str) -> float:
    return float(text.replace(",", "."))


@owner_only
async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /berat <kg>, contoh: /berat 65.5")
        return
    try:
        weight_val = _parse_float(context.args[0])
    except ValueError:
        await update.message.reply_text("Tolong masukkan angka, contoh: /berat 65.5")
        return
    log_weight(weight_val)
    await update.message.reply_text(f"Mantap, berat badan hari ini ({today_str()}) dicatat: {weight_val} kg.")


@owner_only
async def exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Format: /olahraga <kkal> [catatan], contoh:\n"
            "/olahraga 350 lari 5km"
        )
        return
    try:
        kcal = _parse_float(context.args[0])
    except ValueError:
        await update.message.reply_text("Kalori harus angka, contoh: /olahraga 350 lari")
        return
    note = " ".join(context.args[1:])
    entry = log_exercise(kcal, note)
    await update.message.reply_text(
        f"Dicatat: olahraga hari ini membakar +{kcal:.0f} kkal (total: {entry.exercise_kcal:.0f} kkal).\n"
        f"Catatan: Ini cuma buat referensi dan nggak nambah jatah makan ya, karena TDEE kamu udah "
        f"mencakup level aktivitas kamu."
    )


def _format_food_logged(entry, kcal: float, protein: float, header: str) -> str:
    return (
        f"{header}\n"
        f"Dicatat: masuk +{kcal:.0f} kkal / +{protein:.0f} g protein.\n"
        f"Total hari ini: {entry.food_kcal:.0f} kkal, {entry.food_protein_g:.0f} g protein.\n"
        f"Cek sisa jatah kalori kamu hari ini pakai /sisa."
    )


@owner_only
async def eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Format:\n"
            "/makan <kkal> [protein_g] - contoh: /makan 450 35\n"
            "/makan <deskripsi> - contoh: /makan 1 porsi nasi goreng ayam "
            "(AI otomatis estimasi kalori & protein)\n"
            "Atau cukup kirim foto makanan aja."
        )
        return

    # Coba format manual dulu
    try:
        kcal = _parse_float(context.args[0])
        protein = _parse_float(context.args[1]) if len(context.args) > 1 else 0.0
        entry = log_food(kcal, protein)
        await update.message.reply_text(_format_food_logged(entry, kcal, protein, "Input manual."))
        return
    except ValueError:
        pass

    # Bukan angka -> deskripsi teks
    description = " ".join(context.args)
    await update.message.reply_text("Tunggu sebentar, AI lagi ngitung estimasi kalori & protein...")
    estimate = await estimate_food_from_text(description)
    if estimate is None:
        await update.message.reply_text(
            "Gagal melakukan estimasi (API Gemini mungkin error/belum disetup). "
            "Tolong catat manual, contoh: /makan 450 35"
        )
        return
    kcal, protein = float(estimate["kcal"]), float(estimate["protein_g"])
    entry = log_food(kcal, protein)
    header = f"🍽️ {estimate['food_name']} (estimasi, akurasi: {estimate['confidence']})"
    await update.message.reply_text(_format_food_logged(entry, kcal, protein, header))


@owner_only
async def food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tunggu sebentar, menganalisis foto makanan...")
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    caption = update.message.caption or ""

    estimate = await estimate_food_from_image(image_bytes, "image/jpeg", caption)
    if estimate is None:
        await update.message.reply_text(
            "Gagal menganalisis foto (API Gemini mungkin error/belum disetup). "
            "Tolong catat manual, contoh: /makan 450 35"
        )
        return
    kcal, protein = float(estimate["kcal"]), float(estimate["protein_g"])
    entry = log_food(kcal, protein)
    header = f"🍽️ {estimate['food_name']} (dari foto, akurasi: {estimate['confidence']})"
    await update.message.reply_text(_format_food_logged(entry, kcal, protein, header))


@owner_only
async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil lu belum ada. Tolong buat dulu pakai /profil.")
        return
    plan = calculate_bulking_plan(profile)
    today_log = get_log()
    remaining_kcal = plan.target_calories - today_log.food_kcal
    remaining_protein = plan.protein_g - today_log.food_protein_g

    lines = [
        f"📆 *Status Hari Ini ({today_str()})*",
        f"Target: {plan.target_calories} kkal / {plan.protein_g} g protein",
        f"Udah masuk: {today_log.food_kcal:.0f} kkal / {today_log.food_protein_g:.0f} g protein",
        f"Sisa jatah: {remaining_kcal:.0f} kkal / {remaining_protein:.0f} g protein",
    ]
    if today_log.exercise_kcal > 0:
        lines.append(f"Olahraga hari ini (Health App): {today_log.exercise_kcal:.0f} kkal")
    if remaining_kcal < 0:
        lines.append("")
        lines.append("⚠️ Awas, asupan kalori kamu hari ini udah melebihi target surplus.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@owner_only
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Profil lu belum ada. Tolong buat dulu pakai /profil.")
        return
    review = build_weekly_review(profile)
    await update.message.reply_text(format_weekly_message(review), parse_mode="Markdown")


@owner_only
async def free_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile:
        plan = calculate_bulking_plan(profile)
        context_str = (
            f"User profile: weight {profile.weight_kg} kg, height {profile.height_cm} cm, "
            f"age {profile.age}, target to gain {profile.target_gain_kg} kg in "
            f"{profile.target_weeks} weeks. Daily calorie target: {plan.target_calories} kcal, "
            f"protein {plan.protein_g} g/day."
        )
    else:
        context_str = "User has not filled out their profile yet, suggest they use /profil if relevant."

    system_prompt = (
        "You are a personal bulking/nutrition assistant. Be casual and supportive. Answer in casual Indonesian language (use lu/gua or santai). " + context_str
    )
    answer, agent_used = await ask_agent(system_prompt, update.message.text)
    await update.message.reply_text(f"{answer}\n\n_(dijawab oleh: {agent_used})_", parse_mode="Markdown")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")
    if not TELEGRAM_OWNER_ID:
        raise SystemExit("TELEGRAM_OWNER_ID is not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profil", profile_start)],
        states={
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_weight)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_height)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_gender)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_activity)],
            TARGET_GAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_target_gain)],
            TARGET_WEEKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_target_weeks)],
        },
        fallbacks=[CommandHandler("batal", profile_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(CommandHandler("kalori", calories))
    app.add_handler(CommandHandler("saran", suggest))
    app.add_handler(CommandHandler("berat", weight))
    app.add_handler(CommandHandler("olahraga", exercise))
    app.add_handler(CommandHandler("makan", eat))
    app.add_handler(CommandHandler("sisa", remaining))
    app.add_handler(CommandHandler("minggu", week))
    app.add_handler(MessageHandler(filters.PHOTO, food_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_chat))

    logger.info("Bot is running (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()

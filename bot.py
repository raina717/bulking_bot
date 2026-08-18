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
    "Choose your activity level (type one of the following):\n"
    "- sedentary: office job, rarely exercises\n"
    "- light: light exercise 1-3x/week\n"
    "- moderate: moderate exercise 3-5x/week\n"
    "- active: heavy exercise 6-7x/week\n"
    "- very_active: heavy exercise + physical job"
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
        "Hello! I'm your personal bulking assistant bot 💪\n\n"
        "Available commands:\n"
        "/profile - fill/update body metrics & bulking target\n"
        "/calories - view daily calorie & protein requirements\n"
        "/suggest - high-protein meal suggestions (adjusted to today's remaining budget)\n\n"
        "Daily logging (record manually from Huawei Health / your meals):\n"
        "/weight <kg> - log today's body weight\n"
        "/exercise <kcal> [note] - log calories burned from Huawei Health\n"
        "/eat <kcal> [protein_g] - log calories (& protein) you have eaten\n"
        "/eat <description> - or just describe your meal, AI will estimate it\n"
        "or send a food photo - AI will estimate calories/protein from it\n"
        "/remaining - check remaining calorie & protein budget for today\n"
        "/week - weekly progress summary & adjustment suggestions\n\n"
        "Or just chat freely about nutrition/bulking, and I'll answer using AI."
    )


@owner_only
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What is your current body weight in kg?")
    return WEIGHT


async def profile_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["weight_kg"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g.: 65")
        return WEIGHT
    await update.message.reply_text("What is your height in cm?")
    return HEIGHT


async def profile_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["height_cm"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g.: 170")
        return HEIGHT
    await update.message.reply_text("What is your age in years?")
    return AGE


async def profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["age"] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g.: 25")
        return AGE
    await update.message.reply_text("What is your gender? (male/female)")
    return GENDER


async def profile_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in ("male", "female"):
        await update.message.reply_text("Please type 'male' or 'female'.")
        return GENDER
    context.user_data["gender"] = text
    await update.message.reply_text(ACTIVITY_HELP)
    return ACTIVITY


async def profile_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in VALID_ACTIVITY_LEVELS:
        await update.message.reply_text("Invalid choice. " + ACTIVITY_HELP)
        return ACTIVITY
    context.user_data["activity_level"] = text
    await update.message.reply_text("What is your target weight gain in kg? (e.g.: 5)")
    return TARGET_GAIN


async def profile_target_gain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_gain_kg"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g.: 5")
        return TARGET_GAIN
    await update.message.reply_text("In how many weeks do you want to achieve this target? (e.g.: 8 for 2 months)")
    return TARGET_WEEKS


async def profile_target_weeks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_weeks"] = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g.: 8")
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
    await update.message.reply_text("Profile saved! Here is your calculated plan:")
    await update.message.reply_text(format_plan_message(profile, plan), parse_mode="Markdown")
    return ConversationHandler.END


async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alright, cancelled.")
    return ConversationHandler.END


@owner_only
async def calories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Your profile does not exist yet. Please fill it out using /profile.")
        return
    plan = calculate_bulking_plan(profile)
    await update.message.reply_text(format_plan_message(profile, plan), parse_mode="Markdown")


@owner_only
async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Your profile does not exist yet. Please fill it out using /profile.")
        return

    plan = calculate_bulking_plan(profile)
    today_log = get_log()
    remaining_kcal = max(plan.target_calories - today_log.food_kcal, 0)
    remaining_protein = max(plan.protein_g - today_log.food_protein_g, 0)
    await update.message.reply_text("Hold on, compiling meal suggestions...")

    system_prompt = (
        "You are a personal nutrition assistant for someone currently on a bulking program "
        "(gaining muscle mass). Answer in casual but clear English, "
        "use short bullet points, and focus on foods that are easily available."
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
            f"that are easily available, fit into the remaining calorie budget, along with "
            f"estimated protein & calorie content for each meal."
        )
    answer, agent_used = await ask_agent(system_prompt, user_message)
    await update.message.reply_text(f"{answer}\n\n_(answered by: {agent_used})_", parse_mode="Markdown")


def _parse_float(text: str) -> float:
    return float(text.replace(",", "."))


@owner_only
async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /weight <kg>, e.g.: /weight 65.5")
        return
    try:
        weight_val = _parse_float(context.args[0])
    except ValueError:
        await update.message.reply_text("Please enter a number only, e.g.: /weight 65.5")
        return
    log_weight(weight_val)
    await update.message.reply_text(f"Alright, today's body weight ({today_str()}) logged: {weight_val} kg.")


@owner_only
async def exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Format: /exercise <kcal_burned> [note], e.g.:\n"
            "/exercise 350 5k run from Huawei Health"
        )
        return
    try:
        kcal = _parse_float(context.args[0])
    except ValueError:
        await update.message.reply_text("Kcal must be a number, e.g.: /exercise 350 5k run")
        return
    note = " ".join(context.args[1:])
    entry = log_exercise(kcal, note)
    await update.message.reply_text(
        f"Logged: +{kcal:.0f} kcal of exercise today (total: {entry.exercise_kcal:.0f} kcal).\n"
        f"Note: This is just for reference/cross-checking, it is not added to your food budget, "
        f"because your TDEE already assumes your activity level."
    )


def _format_food_logged(entry, kcal: float, protein: float, header: str) -> str:
    return (
        f"{header}\n"
        f"Logged: +{kcal:.0f} kcal / +{protein:.0f} g protein.\n"
        f"Total today: {entry.food_kcal:.0f} kcal, {entry.food_protein_g:.0f} g protein.\n"
        f"Check your remaining budget for today using /remaining."
    )


@owner_only
async def eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Format:\n"
            "/eat <kcal> [protein_g] - e.g.: /eat 450 35\n"
            "/eat <food description> - e.g.: /eat 1 plate fried rice with chicken "
            "(AI will estimate the kcal & protein for you)\n"
            "Or just send a photo of your meal."
        )
        return

    # Coba format manual dulu: /eat <kcal> [protein_g]
    try:
        kcal = _parse_float(context.args[0])
        protein = _parse_float(context.args[1]) if len(context.args) > 1 else 0.0
        entry = log_food(kcal, protein)
        await update.message.reply_text(_format_food_logged(entry, kcal, protein, "Manually logged."))
        return
    except ValueError:
        pass

    # Bukan angka -> anggap deskripsi makanan, minta Claude estimasi.
    description = " ".join(context.args)
    await update.message.reply_text("Hold on, estimating calories & protein...")
    estimate = await estimate_food_from_text(description)
    if estimate is None:
        await update.message.reply_text(
            "Couldn't estimate that automatically (Gemini API might be down/misconfigured). "
            "Please log manually instead, e.g.: /eat 450 35"
        )
        return
    kcal, protein = float(estimate["kcal"]), float(estimate["protein_g"])
    entry = log_food(kcal, protein)
    header = f"🍽️ {estimate['food_name']} (estimated, confidence: {estimate['confidence']})"
    await update.message.reply_text(_format_food_logged(entry, kcal, protein, header))


@owner_only
async def food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hold on, analyzing the photo...")
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    caption = update.message.caption or ""

    estimate = await estimate_food_from_image(image_bytes, "image/jpeg", caption)
    if estimate is None:
        await update.message.reply_text(
            "Couldn't analyze that photo (Gemini API might be down/misconfigured). "
            "Please log manually instead, e.g.: /eat 450 35"
        )
        return
    kcal, protein = float(estimate["kcal"]), float(estimate["protein_g"])
    entry = log_food(kcal, protein)
    header = f"🍽️ {estimate['food_name']} (estimated from photo, confidence: {estimate['confidence']})"
    await update.message.reply_text(_format_food_logged(entry, kcal, protein, header))


@owner_only
async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Your profile does not exist yet. Please fill it out using /profile.")
        return
    plan = calculate_bulking_plan(profile)
    today_log = get_log()
    remaining_kcal = plan.target_calories - today_log.food_kcal
    remaining_protein = plan.protein_g - today_log.food_protein_g

    lines = [
        f"📆 *Today's Status ({today_str()})*",
        f"Target: {plan.target_calories} kcal / {plan.protein_g} g protein",
        f"Eaten: {today_log.food_kcal:.0f} kcal / {today_log.food_protein_g:.0f} g protein",
        f"Remaining: {remaining_kcal:.0f} kcal / {remaining_protein:.0f} g protein",
    ]
    if today_log.exercise_kcal > 0:
        lines.append(f"Exercise today (Huawei Health): {today_log.exercise_kcal:.0f} kcal")
    if remaining_kcal < 0:
        lines.append("")
        lines.append("⚠️ You have exceeded today's calorie target.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@owner_only
async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_profile()
    if profile is None:
        await update.message.reply_text("Your profile does not exist yet. Please fill it out using /profile.")
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
        context_str = "User has not filled out their profile yet, suggest they use /profile if relevant."

    system_prompt = (
        "You are a personal bulking/nutrition assistant. Be casual and supportive. " + context_str
    )
    answer, agent_used = await ask_agent(system_prompt, update.message.text)
    await update.message.reply_text(f"{answer}\n\n_(answered by: {agent_used})_", parse_mode="Markdown")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")
    if not TELEGRAM_OWNER_ID:
        raise SystemExit("TELEGRAM_OWNER_ID is not set in .env")

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
    app.add_handler(CommandHandler("calories", calories))
    app.add_handler(CommandHandler("suggest", suggest))
    app.add_handler(CommandHandler("weight", weight))
    app.add_handler(CommandHandler("exercise", exercise))
    app.add_handler(CommandHandler("eat", eat))
    app.add_handler(CommandHandler("remaining", remaining))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(MessageHandler(filters.PHOTO, food_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_chat))

    logger.info("Bot is running (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()

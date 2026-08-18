# Telegram Bulking Bot (Claude + Hermes)

A personalized Telegram bot designed to assist you during your bulking journey. 

## Features

- `/profile` — Set or update your weight, height, age, gender, activity level, weight gain target, and duration.
- `/kalori` — View your BMR, TDEE, daily calorie target, and macronutrient breakdown (protein, fat, carbs).
- `/saran` — Request high-protein meal suggestions that automatically fit into your remaining daily calorie budget.
- `/berat`, `/olahraga`, `/makan` — Manually log your daily progress (body weight, calories burned from Huawei Health or other fitness trackers, and calories/protein consumed).
- `/sisa` — Check your remaining calorie and protein budget for the day.
- `/minggu` — Get a weekly progress summary (average weight and intake vs target) along with suggestions to adjust your caloric surplus.
- **Free Chat** — Ask any nutrition or bulking-related questions, and the bot will answer using your profile's context.

## Daily Logging & Progress Tracking

Currently, this bot **does not automatically connect** to the Huawei Health API (as Huawei does not provide an easily accessible personal API without an official app review). Instead, use manual logging. Open your fitness tracker app, check your burned calories and steps, and log them into the bot:

```text
/berat 65.5
/olahraga 350 5k run
/makan 450 35        (Calories and protein from a single meal, can be called multiple times a day)
/sisa                (Check remaining calorie/protein budget for today)
/minggu              (Check weekly progress and surplus adjustment advice)
```

> **Note:** Calories burned from exercises are **not** added back to your daily food budget. The calorie target from `/kalori` is calculated based on a TDEE that already accounts for your `activity_level` (which should include your workout routine). Exercise data is logged purely for reference and cross-checking, not to be "eaten back".

The `/minggu` command compares your average body weight this week vs last week against your target (`target_gain_kg` / `target_weeks` from your profile). It will suggest increasing or decreasing your surplus by ~100-150 kcal/day if your progress is consistently too slow or too fast for 2-3 consecutive weeks.

## Agent Architecture

- **Primary Engine (Claude)**: Acts as the main brain, providing highly accurate nutritional calculations and advice.
- **Fallback Engine (Hermes by NousResearch)**: Automatically triggered if the Claude API experiences errors, timeouts, or hits rate limits. Hermes runs locally (self-hosted) on your VPS via Ollama.

The bot is strictly locked to 1 user (you) via `TELEGRAM_OWNER_ID`, making it safe to use without requiring a complex login or database system.

---

## Setup & Installation

### 1. Create a Telegram Bot

1. Chat with `@BotFather` on Telegram → Send `/newbot` → Follow the instructions to get your **Bot Token**.
2. Chat with `@userinfobot` to get your own Telegram **User ID**.

### 2. VPS Setup (e.g., Ubuntu/Debian)

Assuming you have SSH access to your VPS:

```bash
# Update and install basic dependencies
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git curl

# Clone or upload this project to your VPS (e.g., /home/USERNAME/bulking-bot)
cd ~/bulking-bot

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Install Ollama + Hermes Model (Optional Fallback)

This is only used as a **fallback** if the Claude API fails or limits are reached. The bot will run perfectly fine without this as long as your `ANTHROPIC_API_KEY` is valid. You can skip this step and set it up later. If skipped, the bot service will not throw errors.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama

# Pull the Hermes model (choose a variant suitable for your VPS RAM)
ollama pull hermes3          # Requires decent RAM (8B variants and above)
# For lower-spec VPS, find lighter variants at ollama.com/library
```

> **Tip:** Check the exact model name using `ollama list` and match it with `HERMES_MODEL` in your `.env` file. If your VPS has < 8GB RAM, 7-8B models might be slow—consider a VPS upgrade or a smaller model variant.

#### Environment Configuration

```bash
cp .env.example .env
nano .env
```

Fill in `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`, `ANTHROPIC_API_KEY`, and `HERMES_MODEL` with your credentials. For `CLAUDE_MODEL`, check the [latest available models](https://docs.claude.com/en/docs/about-claude/models) before deploying.

#### Manual Testing

```bash
source venv/bin/activate
python bot.py
```

If you see the "Bot is running (polling)..." log, open Telegram, chat with your bot, and try `/start`.

### 3. Keep the Bot Running 24/7 (systemd)

```bash
sudo cp telegram-bulking-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/telegram-bulking-bot.service
# Replace all instances of "YOUR_VPS_USERNAME" with your actual SSH username

sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bulking-bot
sudo systemctl status telegram-bulking-bot
```

To view real-time logs:

```bash
journalctl -u telegram-bulking-bot -f
```

## How to Use

1. `/start` — View the main menu.
2. `/profile` — Fill in your body metrics and target (e.g., gain 5 kg in 8 weeks).
3. `/kalori` — View your daily calorie and protein targets.
4. **Daily:** Open your fitness tracker and log `/berat`, `/olahraga`, and `/makan` after every meal.
5. `/sisa` — Check your remaining calorie/protein budget for the day.
6. `/saran` — Ask for high-protein meal recommendations that fit your remaining budget.
7. `/minggu` — At the end of the week, check your progress and see if surplus adjustments are needed.
8. **Chat anytime:** Ask any nutrition-related questions, and the bot will answer contextually based on your profile.

## Note on Calculation Accuracy

- **BMR** is calculated using the Mifflin-St Jeor equation (currently the most research-backed method).
- The estimation of **1 kg weight gain ≈ 7700 kcal** is a rough mixed-tissue estimate (muscle and fat). Pure muscle gain actually requires less energy, but since 100% muscle gain is unrealistic, 7700 kcal/kg serves as a standard conservative estimate.
- The bot will automatically warn you if your daily calorie surplus is too aggressive (>700 kcal/day), which usually indicates predominantly fat gain rather than muscle.
- The **protein target (2g/kg body weight)** falls within the optimal range (1.6–2.2 g/kg) recommended by the ISSN for individuals undergoing bulking or strength training.
- *Disclaimer: These calculations are estimates and are not a substitute for professional medical or nutritional advice.*

## Troubleshooting

- **Bot is unresponsive:** Ensure `TELEGRAM_OWNER_ID` matches your Telegram ID correctly. Check errors via `journalctl -u telegram-bulking-bot -f`.
- **Always answers with "(answered by: hermes)":** The Claude API is failing. Check if your `ANTHROPIC_API_KEY` is valid and has sufficient quota.
- **Always answers with "(answered by: none)":** Both agents failed. Verify your `ANTHROPIC_API_KEY` and ensure the Ollama service is running (`sudo systemctl status ollama`).

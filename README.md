# Telegram Bulking Bot

A personalized Telegram bot designed to assist you during your bulking journey by tracking calories, protein, weight, and providing AI-powered meal suggestions.

## Features

- **Profile Tracking:** Set your body metrics and weight gain target (`/profil`).
- **Daily Targets:** View your calculated BMR, TDEE, and daily calorie/protein goals (`/kalori`).
- **Progress Logging:** Log your body weight (`/berat`), calories burned from workouts (`/olahraga`), and meals eaten (`/makan`) — either with exact numbers, a free-text description, or a photo of your meal (AI estimates the calories/protein for you).
- **Budget Tracking:** Check your remaining calorie and protein budget for the day (`/sisa`).
- **Smart Suggestions:** Get high-protein meal ideas that perfectly fit your remaining daily budget (`/saran`).
- **Weekly Review:** Compare weekly progress and get advice on adjusting your caloric surplus (`/minggu`).
- **Free Chat:** Ask any nutrition-related questions, and the AI will answer using your personal profile's context.

## Setup & Installation (Docker)

The easiest and recommended way to deploy the bot is using **Docker Compose**.

### 1. Get your Telegram Credentials
1. Chat with `@BotFather` on Telegram → Send `/newbot` → Follow the instructions to get your **Bot Token**.
2. Chat with `@userinfobot` to get your own Telegram **User ID**.

### 2. Deploy with Docker
1. **Install Docker & Docker Compose** on your server.
2. **Clone this repository:**
   ```bash
   git clone https://github.com/raina717/bulking_bot.git
   cd bulking_bot
   ```
3. **Configure your environment variables:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Fill in your `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`, `GROQ_API_KEY`, and `GEMINI_API_KEY`.
4. **Start the bot:**
   ```bash
   docker compose up -d
   ```
5. **View logs (optional):**
   ```bash
   docker compose logs -f
   ```

*Note: The bot stores your profile and logs inside the `./data` directory. Since this folder is mounted as a volume, your data will persist even if the container restarts.*

## How to Use

1. Send `/start` to view the main menu.
2. Send `/profil` to initialize your body metrics and goals.
3. Check your daily targets using `/kalori`.
4. After every meal or workout, log your progress using `/makan` and `/olahraga`. For `/makan` you can either:
   - type exact numbers: `/makan 450 35` (kcal, protein_g)
   - describe the meal: `/makan 1 plate fried rice with chicken` (AI estimates it)
   - or just send a photo of your meal (AI estimates it from the photo)

   Note: AI-based food estimates (text/photo) use Google Gemini and require a working `GEMINI_API_KEY`.
5. Check `/sisa` at the end of the day to see if you have room for a snack, and use `/saran` if you need ideas.
6. Check `/minggu` at the end of the week for progress analysis.

## Troubleshooting

- **Bot is unresponsive:** Ensure `TELEGRAM_OWNER_ID` in your `.env` file matches your actual Telegram User ID perfectly.
- **Bot responds with "API Groq sedang bermasalah...":** Your `GROQ_API_KEY` is likely invalid or missing. Check your Groq Console.
- **Bot responds with "Gagal melakukan estimasi..." on images:** Your `GEMINI_API_KEY` is invalid or missing. Check Google AI Studio.
- **View Errors:** Run `docker compose logs -f` to see what is causing the issue.

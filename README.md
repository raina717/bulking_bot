# Telegram Bulking Bot

A personalized Telegram bot designed to assist you during your bulking journey by tracking calories, protein, weight, and providing AI-powered meal suggestions.

## Features

- **Profile Tracking:** Set your body metrics and weight gain target (`/profile`).
- **Daily Targets:** View your calculated BMR, TDEE, and daily calorie/protein goals (`/calories`).
- **Progress Logging:** Manually log your body weight (`/weight`), calories burned from workouts (`/exercise`), and meals eaten (`/eat`).
- **Budget Tracking:** Check your remaining calorie and protein budget for the day (`/remaining`).
- **Smart Suggestions:** Get high-protein meal ideas that perfectly fit your remaining daily budget (`/suggest`).
- **Weekly Review:** Compare weekly progress and get advice on adjusting your caloric surplus (`/week`).
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
   Fill in your `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`, and `ANTHROPIC_API_KEY`.
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
2. Send `/profile` to initialize your body metrics and goals.
3. Check your daily targets using `/calories`.
4. After every meal or workout, log your progress using `/eat` and `/exercise`.
5. Check `/remaining` at the end of the day to see if you have room for a snack, and use `/suggest` if you need ideas.
6. Check `/week` at the end of the week for progress analysis.

## Troubleshooting

- **Bot is unresponsive:** Ensure `TELEGRAM_OWNER_ID` in your `.env` file matches your actual Telegram User ID perfectly.
- **Bot responds with "Both Claude and Hermes are unreachable":** Your `ANTHROPIC_API_KEY` is likely invalid or out of credits. Check your Claude API dashboard.
- **View Errors:** Run `docker compose logs -f` to see what is causing the issue.

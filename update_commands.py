import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot, BotCommand

async def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    bot = Bot(token)
    commands = [
        BotCommand("profil", "Isi/update data badan & target"),
        BotCommand("kalori", "Lihat kebutuhan kalori & protein harian"),
        BotCommand("saran", "Saran menu tinggi protein dari AI"),
        BotCommand("berat", "Catat berat badan hari ini"),
        BotCommand("olahraga", "Catat kalori olahraga"),
        BotCommand("makan", "Catat kalori makanan / kirim deskripsi"),
        BotCommand("sisa", "Cek sisa jatah kalori hari ini"),
        BotCommand("minggu", "Ringkasan progres mingguan"),
        BotCommand("batal", "Batalkan pengisian profil"),
    ]
    await bot.set_my_commands(commands)
    print("Berhasil mengupdate menu command di Telegram!")

if __name__ == "__main__":
    asyncio.run(main())

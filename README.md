# Bot Bulking Telegram (Claude + Hermes)

Bot Telegram personal buat kamu yang lagi bulking. Fitur:

- `/profile` — isi/update berat, tinggi, umur, gender, level aktivitas, target kenaikan berat & jangka waktu.
- `/kalori` — lihat BMR, TDEE, target kalori harian, dan target protein/fat/carbs.
- `/saran` — minta saran menu tinggi protein, otomatis nyesuaiin sisa budget kalori hari ini.
- `/berat`, `/olahraga`, `/makan` — logging harian manual (berat badan, kalori terbakar dari
  Huawei Health, kalori/protein makanan) buat kontrol progres vs target.
- `/sisa` — lihat sisa budget kalori & protein hari ini.
- `/minggu` — ringkasan progres mingguan (rata-rata BB & asupan vs target) + saran adjust surplus.
- Chat bebas — tanya apa aja soal nutrisi/bulking, dijawab dengan konteks profil kamu.

## Logging harian & kontrol progres (Huawei Health)

Bot ini **belum konek otomatis** ke API Huawei Health (Huawei nggak nyediain API personal yang
gampang dipakai dari skrip pribadi — butuh HMS Core Health Kit + app review kalau mau resmi).
Jadi sementara pakai logging manual: buka Huawei Health di HP, lihat kalori kebakar & langkah,
terus catat ke bot:

```
/berat 65.5
/olahraga 350 lari 5k dari Huawei Health
/makan 450 35        (kalori & protein dari 1x makan, bisa dipanggil berkali-kali per hari)
/sisa                 (cek sisa budget kalori/protein hari ini)
/minggu               (cek progres mingguan & apakah perlu adjust surplus)
```

Kalori olahraga yang dicatat **tidak** ditambahin balik ke budget makan harian — itu karena
target kalori dari `/kalori` udah dihitung dari TDEE yang sudah mengasumsikan `activity_level`
kamu (yang harusnya udah mencakup rutinitas olahraga kamu). Data olahraga di sini murni buat
referensi & cross-check, bukan buat "dimakan balik".

`/minggu` bandingin rata-rata berat badan minggu ini vs minggu lalu terhadap target
(`target_gain_kg` / `target_weeks` dari profil), dan kasih saran naik/turunin surplus ~100-150
kkal/hari kalau progresnya kelewat lambat atau kelewat cepat 2-3 minggu berturut-turut.

Arsitektur agent: **Claude jadi otak utama** (lebih akurat buat kalkulasi & saran nutrisi),
dan **Hermes (NousResearch) jadi fallback** — dipanggil otomatis kalau Claude API lagi
error/timeout/limit, dengan Hermes yang jalan sendiri (self-hosted) di VPS kamu lewat Ollama.

Bot ini di-lock cuma buat 1 user (kamu sendiri) lewat `TELEGRAM_OWNER_ID`, jadi aman dipakai
tanpa perlu sistem login/database.

---

## 1. Bikin Bot Telegram

1. Chat `@BotFather` di Telegram → `/newbot` → ikutin instruksinya → dapet **bot token**.
2. Chat `@userinfobot` buat tau **user ID** Telegram kamu sendiri.

## 2. Setup di Rumahweb VPS

Asumsi VPS-nya Ubuntu/Debian, akses via SSH.

```bash
# update & install dependency dasar
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git curl

# clone / upload project ini ke VPS, misal ke /home/USERNAME/bulking-bot
cd ~/bulking-bot

# bikin virtual env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Install Ollama + model Hermes (opsional, boleh dilewatin/nyusul)

Ini cuma buat **fallback** kalau Claude API gagal/limit — bot tetap jalan normal tanpa ini
selama `ANTHROPIC_API_KEY` valid. Bisa di-skip dulu sekarang dan di-setup belakangan kapan aja
(tinggal isi `OLLAMA_HOST`/`HERMES_MODEL` di `.env` lalu `sudo systemctl restart telegram-bulking-bot`,
gak perlu ubah kode). Kalau di-skip, `After=ollama.service` di file `.service` juga gak akan
bikin error meskipun `ollama.service` belum ada di VPS.

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama

# pull model Hermes (pilih salah satu varian sesuai kapasitas VPS kamu)
ollama pull hermes3          # butuh RAM lumayan besar (varian 8B ke atas)
# atau kalau VPS spek kecil, cari varian Hermes yang lebih ringan di ollama.com/library
```

> Cek nama model persis pakai `ollama list`, terus samain sama `HERMES_MODEL` di `.env`.
> Kalau VPS kamu speknya kecil (RAM < 8GB), model 7-8B bisa berat/lambat — pertimbangkan
> pakai VPS dengan RAM lebih besar, atau ganti model Hermes ke varian yang lebih kecil.

### Konfigurasi .env

```bash
cp .env.example .env
nano .env
```

Isi `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`, `ANTHROPIC_API_KEY`, dan `HERMES_MODEL`
sesuai punya kamu. Untuk `CLAUDE_MODEL`, cek daftar model id terbaru di
https://docs.claude.com/en/docs/about-claude/models sebelum deploy, karena nama model
bisa berubah/nambah dari waktu ke waktu.

### Test jalan manual dulu

```bash
source venv/bin/activate
python bot.py
```

Kalau muncul log "Bot jalan (polling)...", buka Telegram, chat bot kamu, coba `/start`.

## 3. Bikin bot jalan terus 24/7 (systemd)

```bash
sudo cp telegram-bulking-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/telegram-bulking-bot.service
# ganti semua "YOUR_VPS_USERNAME" sesuai username SSH kamu di VPS

sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bulking-bot
sudo systemctl status telegram-bulking-bot
```

Cek log realtime:

```bash
journalctl -u telegram-bulking-bot -f
```

## 4. Cara pakai di Telegram

1. `/start` — lihat menu.
2. `/profile` — isi data badan & target (misal: naik 5 kg dalam 8 minggu / 2 bulan).
3. `/kalori` — lihat target kalori & protein harian kamu.
4. Tiap hari: buka Huawei Health, catat `/berat`, `/olahraga`, dan `/makan` tiap kali makan.
5. `/sisa` — cek sisa budget kalori/protein hari ini biar makan gak kelebihan/kekurangan.
6. `/saran` — minta rekomendasi menu tinggi protein yang muat di sisa budget hari ini.
7. `/minggu` — tiap akhir minggu, cek progres & apakah surplus perlu di-adjust.
8. Bebas chat kapan aja soal nutrisi, bot bakal jawab pakai konteks profil kamu.

## Catatan soal akurasi kalkulasi

- BMR pakai rumus Mifflin-St Jeor (paling direkomendasikan riset terkini dibanding Harris-Benedict).
- Estimasi 1 kg kenaikan berat badan ≈ 7700 kkal itu angka kasar (campuran otot+lemak).
  Kenaikan otot murni sebenarnya butuh energi lebih sedikit dari itu, tapi karena gak mungkin
  100% gain-nya otot (tergantung training, tidur, genetik, status latihan), 7700 kkal/kg
  dipakai sebagai estimasi konservatif yang umum dipakai.
- Bot bakal kasih warning otomatis kalau surplus kalori harian kamu kelewat agresif
  (>700 kkal/hari) — itu tandanya gain kamu kemungkinan besar didominasi lemak, bukan otot.
- Protein target 2 g/kg berat badan — ada di rentang optimal (1.6–2.2 g/kg) menurut riset ISSN
  (International Society of Sports Nutrition) buat orang yang lagi bulking/strength training.
- Ini kalkulasi estimasi, bukan pengganti konsultasi ahli gizi/dokter kalau kamu punya kondisi
  kesehatan khusus.

## Troubleshooting

- **Bot gak respon sama sekali** → cek `TELEGRAM_OWNER_ID` udah bener sesuai user ID kamu,
  dan cek `journalctl -u telegram-bulking-bot -f` buat lihat error.
- **Selalu jawab "(dijawab oleh: hermes)"** → berarti Claude API gagal terus, cek
  `ANTHROPIC_API_KEY` valid & masih ada kuota.
- **Selalu jawab "(dijawab oleh: none)"** → dua-duanya gagal, cek `ANTHROPIC_API_KEY` dan
  service Ollama (`sudo systemctl status ollama`) di VPS.
# bulking_bot

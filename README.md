# 🤖 Telegram Video Bot

Bot Telegram yang otomatis mengirim video MP4 ke channel setiap jam,
dengan link deep link yang mengarahkan ke chat bot untuk memutar video langsung.

---

## 📁 Struktur File

```
telegram-bot/
├── bot.py            # Main bot
├── video_manager.py  # Manajemen penyimpanan video (JSON)
├── videos.json       # Database video (auto-dibuat)
├── requirements.txt
├── Procfile          # Untuk Railway/Render
└── .env.example      # Contoh konfigurasi
```

---

## ⚙️ Setup Awal

### 1. Buat Bot di @BotFather
```
/newbot → ikuti langkah → salin BOT_TOKEN
```

### 2. Jadikan Bot sebagai Admin Channel
- Buka channel kamu → Settings → Administrators
- Tambahkan bot sebagai admin
- Aktifkan izin: **Post Messages**

### 3. Dapatkan ADMIN_ID kamu
- Kirim pesan ke **@userinfobot**
- Salin angka "Id" yang muncul

### 4. Dapatkan CHANNEL_ID (untuk channel privat)
- Forward pesan dari channel ke **@userinfobot**
- Akan muncul "Forwarded from chat #-100xxxxxxxxxx"
- Gunakan angka itu (dengan tanda minus) sebagai CHANNEL_ID

---

## 🚀 Deploy ke Railway

1. Push semua file ke GitHub repository

2. Buka [railway.app](https://railway.app) → New Project → Deploy from GitHub

3. Pilih repo kamu

4. Masuk ke tab **Variables**, tambahkan:
   ```
   BOT_TOKEN      = token_dari_botfather
   CHANNEL_ID     = @username_channel atau -100xxxxxxxxxx
   CHANNEL_LINK   = https://t.me/username_channel
   BOT_USERNAME   = username_bot_tanpa_@
   ADMIN_ID       = user_id_kamu
   ```

5. Klik **Deploy** — selesai! ✅

---

## 🚀 Deploy ke Render

1. Push ke GitHub

2. Buka [render.com](https://render.com) → New → Background Worker

3. Pilih repo → Runtime: **Python 3**

4. Build Command: `pip install -r requirements.txt`

5. Start Command: `python bot.py`

6. Tambahkan Environment Variables yang sama seperti di Railway

---

## 🎬 Cara Tambah Video

### Metode 1 — Via File Telegram (Recommended)
Ini metode terbaik karena video disimpan di server Telegram, tidak ada biaya hosting.

**Langkah:**
1. Kirim/upload video MP4 ke bot kamu (chat pribadi dengan bot)
2. Bot akan balas dengan file_id otomatis
3. Atau: reply ke video tersebut dengan perintah:
   ```
   /add Judul Video Kamu
   ```

### Metode 2 — Via URL Langsung
```
/add Judul Video | https://contoh.com/video.mp4
```
URL harus bisa diakses publik dan berformat MP4.

### Sumber URL MP4 Gratis:
| Platform | Cara Dapat URL |
|----------|----------------|
| **Catbox.moe** | Upload → klik kanan → Copy link |
| **Streamable** | Upload → share → link direct |
| **GitHub Releases** | Upload lewat release → copy raw link |
| **Cloudinary** (free tier) | Upload → transformation URL |

---

## 📋 Perintah Bot

### Untuk Semua User:
| Perintah | Fungsi |
|----------|--------|
| `/start` | Sambutan + video terbaru |
| `/video` | Tampilkan video terbaru |
| `/list`  | Daftar semua video (dengan tombol putar) |
| `/info`  | Statistik bot |

### Khusus Admin:
| Perintah | Fungsi |
|----------|--------|
| `/add <judul>` | Tambah video (reply ke video) |
| `/add <judul> \| <url>` | Tambah video via URL |
| `/listall` | Lihat semua video + ID |
| `/delete <id>` | Hapus video by ID |
| `/broadcast` | Paksa broadcast sekarang |

---

## 🔄 Alur Sistem

```
[Admin upload video via /add]
        ↓
[Video tersimpan di videos.json]
        ↓
[Scheduler jalan setiap 1 jam]
        ↓
[Bot posting ke Channel]
[Isi: judul + tombol "▶️ Tonton Sekarang"]
        ↓
[User klik tombol → diarahkan ke Chat Bot]
[URL: t.me/botname?start=video_<id>]
        ↓
[Bot langsung kirim video MP4]
[Video bisa diputar langsung di Telegram]
```

---

## ⚠️ Catatan Penting

- **Railway Free Tier**: Service tidur setelah tidak aktif. Upgrade ke Hobby ($5/bulan) agar scheduler berjalan 24/7.
- **Render Free Tier**: Service spin down setelah 15 menit idle. Gunakan paid plan untuk bot 24/7.
- **Alternatif gratis**: Gunakan **Railway Starter** (free $5 credit) atau **Fly.io** (free tier lebih stabil).
- `videos.json` akan hilang setiap redeploy di Railway/Render (ephemeral storage). Untuk produksi jangka panjang, gunakan Railway PostgreSQL atau MongoDB Atlas (gratis).

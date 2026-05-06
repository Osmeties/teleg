import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from video_manager import VideoManager

# ─────────────────────────────────────────────
# KONFIGURASI — isi di file .env atau Railway Variables
# ─────────────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN", "8652023085:AAH2b5Xca52J3-vQSXpgxuVSu0zSIkcUzak")
CHANNEL_ID       = os.getenv("CHANNEL_ID", "@mediaWJR")   # e.g. @mychannel
CHANNEL_LINK     = os.getenv("CHANNEL_LINK", "https://t.me/mediaWJR")
BOT_USERNAME     = os.getenv("BOT_USERNAME", "MediaWJR_bot")       # tanpa @
ADMIN_ID         = int(os.getenv("ADMIN_ID", "0"))                  # Telegram user ID admin

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

video_manager = VideoManager()


# ══════════════════════════════════════════════
#  COMMAND HANDLERS
# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start — sambut user dan kirim video terbaru."""
    user = update.effective_user
    
    welcome_text = (
        f"👋 Halo, <b>{user.first_name}</b>!\n\n"
        f"🎬 Selamat datang di <b>Video Bot</b>!\n"
        f"Setiap jam kami mengirimkan video baru untukmu.\n\n"
        f"📌 <b>Perintah tersedia:</b>\n"
        f"• /video — Lihat video terbaru\n"
        f"• /list  — Daftar semua video\n"
        f"• /info  — Info bot\n\n"
        f"⬇️ Berikut video terbaru untuk kamu:"
    )
    
    await update.message.reply_text(welcome_text, parse_mode="HTML")
    await send_latest_video(update, context)


async def send_latest_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim video terbaru ke user."""
    video = video_manager.get_latest_video()
    
    if not video:
        await update.message.reply_text(
            "😔 Belum ada video tersedia saat ini.\n"
            "Coba lagi beberapa saat ya!"
        )
        return
    
    await deliver_video(update.effective_chat.id, video, context)


async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan daftar video yang tersedia."""
    videos = video_manager.get_all_videos()
    
    if not videos:
        await update.message.reply_text("📭 Belum ada video tersedia.")
        return
    
    keyboard = []
    for i, v in enumerate(videos[-10:], 1):  # max 10 terakhir
        label = f"🎬 {v['title']} — {v['uploaded_at']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"play_{v['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📋 <b>Daftar Video Tersedia ({len(videos)} total):</b>\n"
        f"Pilih video yang ingin kamu tonton:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Info bot."""
    total = video_manager.count_videos()
    latest = video_manager.get_latest_video()
    last_time = latest['uploaded_at'] if latest else "belum ada"
    
    text = (
        f"ℹ️ <b>Info Video Bot</b>\n\n"
        f"📦 Total video: <b>{total}</b>\n"
        f"🕐 Video terakhir: <b>{last_time}</b>\n"
        f"⏰ Update otomatis: <b>setiap 1 jam</b>\n\n"
        f"📢 Channel kami: {CHANNEL_LINK}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ══════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin: tambah video baru via file_id atau URL.
    
    Cara pakai:
      1. Forward video ke bot lalu ketik /add <judul>
      2. Atau: /add <judul> | <url_mp4>
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Kamu bukan admin!")
        return
    
    args = " ".join(context.args) if context.args else ""
    
    # Cek apakah ada video yang di-forward/reply
    if update.message.reply_to_message and update.message.reply_to_message.video:
        video_msg = update.message.reply_to_message
        file_id   = video_msg.video.file_id
        title     = args if args else f"Video {datetime.now().strftime('%d/%m %H:%M')}"
        
        video_manager.add_video(title=title, file_id=file_id)
        await update.message.reply_text(f"✅ Video '<b>{title}</b>' berhasil ditambahkan!\nFile ID: <code>{file_id}</code>", parse_mode="HTML")
    
    # Atau via URL
    elif "|" in args:
        parts = args.split("|", 1)
        title = parts[0].strip()
        url   = parts[1].strip()
        
        video_manager.add_video(title=title, url=url)
        await update.message.reply_text(f"✅ Video '<b>{title}</b>' berhasil ditambahkan!\nURL: <code>{url}</code>", parse_mode="HTML")
    
    else:
        await update.message.reply_text(
            "📖 <b>Cara tambah video:</b>\n\n"
            "<b>Metode 1 — Reply ke video:</b>\n"
            "Reply video dengan perintah:\n"
            "<code>/add Judul Video Kamu</code>\n\n"
            "<b>Metode 2 — Via URL:</b>\n"
            "<code>/add Judul Video | https://url-video.mp4</code>",
            parse_mode="HTML"
        )


async def broadcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: paksa broadcast sekarang tanpa tunggu jadwal."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Kamu bukan admin!")
        return
    
    await update.message.reply_text("📤 Memulai broadcast manual...")
    await scheduled_broadcast(context.application)
    await update.message.reply_text("✅ Broadcast selesai!")


async def list_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: lihat semua video + ID."""
    if update.effective_user.id != ADMIN_ID:
        return
    
    videos = video_manager.get_all_videos()
    if not videos:
        await update.message.reply_text("📭 Belum ada video.")
        return
    
    text = "📋 <b>Semua Video:</b>\n\n"
    for v in videos:
        source = f"file_id: <code>{v['file_id'][:20]}...</code>" if v.get('file_id') else f"url: {v.get('url','?')[:40]}"
        text += f"<b>ID {v['id']}:</b> {v['title']}\n{source}\n📅 {v['uploaded_at']}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML")


async def delete_video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: hapus video by ID. Usage: /delete <id>"""
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    
    vid_id = int(context.args[0])
    success = video_manager.delete_video(vid_id)
    if success:
        await update.message.reply_text(f"🗑️ Video ID {vid_id} dihapus.")
    else:
        await update.message.reply_text(f"❌ Video ID {vid_id} tidak ditemukan.")


# ══════════════════════════════════════════════
#  CALLBACK QUERY (tombol inline)
# ══════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tombol inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("play_"):
        vid_id = int(query.data.replace("play_", ""))
        video  = video_manager.get_video_by_id(vid_id)
        
        if video:
            await deliver_video(query.message.chat_id, video, context)
        else:
            await query.message.reply_text("❌ Video tidak ditemukan.")


# ══════════════════════════════════════════════
#  HELPER: kirim video ke chat
# ══════════════════════════════════════════════

async def deliver_video(chat_id: int, video: dict, context: ContextTypes.DEFAULT_TYPE):
    """Kirim video ke chat berdasarkan file_id atau URL."""
    caption = (
        f"🎬 <b>{video['title']}</b>\n"
        f"📅 {video['uploaded_at']}\n\n"
        f"📢 Channel: {CHANNEL_LINK}"
    )
    
    keyboard = [[InlineKeyboardButton("📢 Kunjungi Channel", url=CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if video.get("file_id"):
            await context.bot.send_video(
                chat_id=chat_id,
                video=video["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                supports_streaming=True
            )
        elif video.get("url"):
            await context.bot.send_video(
                chat_id=chat_id,
                video=video["url"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                supports_streaming=True
            )
    except Exception as e:
        logger.error(f"Gagal kirim video: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Gagal memutar video.\nError: {e}"
        )


# ══════════════════════════════════════════════
#  SCHEDULED BROADCAST — setiap 1 jam
# ══════════════════════════════════════════════

async def scheduled_broadcast(app: Application):
    """
    Kirim link ke channel setiap jam.
    Channel akan berisi tombol yang mengarah ke chat bot.
    """
    video = video_manager.get_next_scheduled_video()
    
    if not video:
        logger.warning("Tidak ada video untuk di-broadcast.")
        return
    
    bot_link = f"https://t.me/{BOT_USERNAME}?start=video_{video['id']}"
    
    channel_text = (
        f"🎬 <b>Video Terbaru Tersedia!</b>\n\n"
        f"📌 <b>{video['title']}</b>\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')} WIB\n\n"
        f"▶️ Klik tombol di bawah untuk tonton langsung!"
    )
    
    keyboard = [[InlineKeyboardButton("▶️ Tonton Sekarang", url=bot_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await app.bot.send_message(
            chat_id=CHANNEL_ID,
            text=channel_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        logger.info(f"✅ Broadcast berhasil: {video['title']}")
        video_manager.mark_as_broadcasted(video['id'])
    except Exception as e:
        logger.error(f"❌ Gagal broadcast: {e}")


# ══════════════════════════════════════════════
#  DEEP LINK handler (/start video_<id>)
# ══════════════════════════════════════════════

async def deep_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deep link dari channel, e.g. /start video_5"""
    if context.args and context.args[0].startswith("video_"):
        vid_id = int(context.args[0].replace("video_", ""))
        video  = video_manager.get_video_by_id(vid_id)
        
        if video:
            await update.message.reply_text(
                f"🎬 Memutar video: <b>{video['title']}</b>",
                parse_mode="HTML"
            )
            await deliver_video(update.effective_chat.id, video, context)
        else:
            await start(update, context)
    else:
        await start(update, context)


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handler umum
    app.add_handler(CommandHandler("start",     deep_link_handler))
    app.add_handler(CommandHandler("video",     send_latest_video))
    app.add_handler(CommandHandler("list",      list_videos))
    app.add_handler(CommandHandler("info",      info))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Handler admin
    app.add_handler(CommandHandler("add",       add_video))
    app.add_handler(CommandHandler("broadcast", broadcast_now))
    app.add_handler(CommandHandler("listall",   list_admin))
    app.add_handler(CommandHandler("delete",    delete_video_cmd))
    
    # Scheduler — broadcast ke channel setiap jam
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_broadcast,
        trigger="interval",
        hours=1,
        args=[app],
        id="hourly_broadcast"
    )
    scheduler.start()
    logger.info("⏰ Scheduler aktif — broadcast setiap 1 jam")
    
    logger.info("🤖 Bot berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

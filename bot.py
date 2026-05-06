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

BOT_TOKEN    = os.getenv("BOT_TOKEN", "ISI_BOT_TOKEN_DI_SINI")
CHANNEL_ID   = os.getenv("CHANNEL_ID", "@nama_channel_kamu")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/nama_channel_kamu")
BOT_USERNAME = os.getenv("BOT_USERNAME", "nama_bot_kamu")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

video_manager = VideoManager()


# ══════════════════════════════════════════════
#  USER COMMANDS
# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    video = video_manager.get_latest_video()
    if not video:
        await update.message.reply_text("😔 Belum ada video tersedia saat ini.\nCoba lagi beberapa saat ya!")
        return
    await deliver_video(update.effective_chat.id, video, context)


async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id == ADMIN_ID
    all_videos = video_manager.get_all_videos()
    videos = all_videos if is_admin else [v for v in all_videos if v.get("broadcasted")]

    if not videos:
        await update.message.reply_text("📭 Belum ada video tersedia.\nTunggu broadcast berikutnya ya! 🕐")
        return

    keyboard = []
    for v in videos[-10:]:
        label = f"🎬 {v['title']} — {v['uploaded_at']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"play_{v['id']}")])

    if is_admin:
        broadcasted = [v for v in all_videos if v.get("broadcasted")]
        pending = [v for v in all_videos if not v.get("broadcasted")]
        info_text = (
            f"📋 <b>[ADMIN] Semua Video:</b>\n"
            f"✅ Sudah broadcast: <b>{len(broadcasted)}</b>\n"
            f"⏳ Antrian: <b>{len(pending)}</b>\n\n"
            f"Pilih video untuk diputar:"
        )
    else:
        info_text = (
            f"📋 <b>Daftar Video ({len(videos)} tersedia):</b>\n"
            f"Pilih video yang ingin kamu tonton:"
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(info_text, reply_markup=reply_markup, parse_mode="HTML")


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Kamu bukan admin!")
        return

    args = " ".join(context.args) if context.args else ""

    if update.message.reply_to_message and update.message.reply_to_message.video:
        file_id = update.message.reply_to_message.video.file_id
        title   = args if args else f"Video {datetime.now().strftime('%d/%m %H:%M')}"
        video   = video_manager.add_video(title=title, file_id=file_id)
        await update.message.reply_text(
            f"✅ Video '<b>{title}</b>' berhasil ditambahkan!\n"
            f"ID: <b>{video['id']}</b>\n"
            f"File ID: <code>{file_id[:30]}...</code>\n\n"
            f"💡 Tambahkan thumbnail:\n<code>/thumb {video['id']}</code> (reply ke foto)",
            parse_mode="HTML"
        )
    elif "|" in args:
        parts = args.split("|", 1)
        title = parts[0].strip()
        url   = parts[1].strip()
        video = video_manager.add_video(title=title, url=url)
        await update.message.reply_text(
            f"✅ Video '<b>{title}</b>' berhasil ditambahkan!\n"
            f"ID: <b>{video['id']}</b>\n\n"
            f"💡 Tambahkan thumbnail:\n<code>/thumb {video['id']}</code> (reply ke foto)",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "📖 <b>Cara tambah video:</b>\n\n"
            "<b>Metode 1 — Reply ke video:</b>\n"
            "<code>/add Judul Video Kamu</code>\n\n"
            "<b>Metode 2 — Via URL:</b>\n"
            "<code>/add Judul Video | https://url-video.mp4</code>",
            parse_mode="HTML"
        )


async def set_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin: set thumbnail untuk video.
    Cara: reply ke foto dengan /thumb <id_video>
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Kamu bukan admin!")
        return

    if not context.args:
        await update.message.reply_text(
            "📖 <b>Cara set thumbnail:</b>\n\n"
            "1. Kirim foto ke bot\n"
            "2. Reply foto itu dengan:\n"
            "<code>/thumb ID_VIDEO</code>\n\n"
            "Contoh: <code>/thumb 3</code>\n\n"
            "Cek ID video dengan /listall",
            parse_mode="HTML"
        )
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text(
            "⚠️ Kamu harus <b>reply ke foto</b> dengan perintah ini!\n\n"
            "Langkah:\n"
            "1. Kirim foto thumbnail ke bot\n"
            "2. Reply foto itu dengan <code>/thumb ID_VIDEO</code>",
            parse_mode="HTML"
        )
        return

    video_id = int(context.args[0])
    # Ambil foto resolusi tertinggi
    photo    = update.message.reply_to_message.photo[-1]
    thumb_id = photo.file_id

    success = video_manager.set_thumbnail(video_id, thumb_id)
    if success:
        video = video_manager.get_video_by_id(video_id)
        await update.message.reply_text(
            f"✅ Thumbnail untuk video '<b>{video['title']}</b>' berhasil disimpan!\n"
            f"Akan tampil saat broadcast berikutnya. 🎉",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"❌ Video ID {video_id} tidak ditemukan. Cek /listall")


async def broadcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Kamu bukan admin!")
        return
    await update.message.reply_text("📤 Memulai broadcast manual...")
    await scheduled_broadcast(context.application)
    await update.message.reply_text("✅ Broadcast selesai!")


async def list_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    videos = video_manager.get_all_videos()
    if not videos:
        await update.message.reply_text("📭 Belum ada video.")
        return
    text = "📋 <b>Semua Video:</b>\n\n"
    for v in videos:
        thumb = "🖼️ Ada" if v.get("thumbnail_id") else "❌ Belum"
        status = "✅ Broadcast" if v.get("broadcasted") else "⏳ Antrian"
        text += f"<b>ID {v['id']}:</b> {v['title']}\n{status} | Thumbnail: {thumb}\n📅 {v['uploaded_at']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def delete_video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    vid_id  = int(context.args[0])
    success = video_manager.delete_video(vid_id)
    if success:
        await update.message.reply_text(f"🗑️ Video ID {vid_id} dihapus.")
    else:
        await update.message.reply_text(f"❌ Video ID {vid_id} tidak ditemukan.")


# ══════════════════════════════════════════════
#  CALLBACK QUERY
# ══════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
#  HELPER: kirim video ke user
# ══════════════════════════════════════════════

async def deliver_video(chat_id: int, video: dict, context: ContextTypes.DEFAULT_TYPE):
    caption = (
        f"🎬 <b>{video['title']}</b>\n"
        f"📅 {video['uploaded_at']}\n\n"
        f"📢 Channel: {CHANNEL_LINK}"
    )
    keyboard     = [[InlineKeyboardButton("📢 Kunjungi Channel", url=CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if video.get("file_id"):
            await context.bot.send_video(
                chat_id=chat_id,
                video=video["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                supports_streaming=True,
                thumbnail=video.get("thumbnail_id") or None
            )
        elif video.get("url"):
            await context.bot.send_video(
                chat_id=chat_id,
                video=video["url"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                supports_streaming=True,
                thumbnail=video.get("thumbnail_id") or None
            )
    except Exception as e:
        logger.error(f"Gagal kirim video: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Gagal memutar video.\nError: {e}")


# ══════════════════════════════════════════════
#  SCHEDULED BROADCAST — setiap 1 jam
# ══════════════════════════════════════════════

async def scheduled_broadcast(app: Application):
    video = video_manager.get_next_scheduled_video()
    if not video:
        logger.warning("Tidak ada video untuk di-broadcast.")
        return

    bot_link = f"https://t.me/{BOT_USERNAME}?start=video_{video['id']}"

    caption = (
        f"🎬 <b>Video Terbaru Tersedia!</b>\n\n"
        f"📌 <b>{video['title']}</b>\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')} WIB\n\n"
        f"▶️ Klik tombol di bawah untuk tonton langsung!"
    )
    keyboard     = [[InlineKeyboardButton("▶️ Tonton Sekarang", url=bot_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Kalau ada thumbnail, kirim sebagai foto dengan tombol
        if video.get("thumbnail_id"):
            await app.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=video["thumbnail_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            await app.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        logger.info(f"✅ Broadcast berhasil: {video['title']}")
        video_manager.mark_as_broadcasted(video['id'])
    except Exception as e:
        logger.error(f"❌ Gagal broadcast: {e}")


# ══════════════════════════════════════════════
#  DEEP LINK
# ══════════════════════════════════════════════

async def deep_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith("video_"):
        vid_id = int(context.args[0].replace("video_", ""))
        video  = video_manager.get_video_by_id(vid_id)
        if video:
            await update.message.reply_text(f"🎬 Memutar video: <b>{video['title']}</b>", parse_mode="HTML")
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

    app.add_handler(CommandHandler("start",     deep_link_handler))
    app.add_handler(CommandHandler("video",     send_latest_video))
    app.add_handler(CommandHandler("list",      list_videos))
    app.add_handler(CommandHandler("info",      info))
    app.add_handler(CommandHandler("add",       add_video))
    app.add_handler(CommandHandler("thumb",     set_thumbnail))
    app.add_handler(CommandHandler("broadcast", broadcast_now))
    app.add_handler(CommandHandler("listall",   list_admin))
    app.add_handler(CommandHandler("delete",    delete_video_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_broadcast, trigger="interval", hours=1, args=[app], id="hourly_broadcast")
    scheduler.start()
    logger.info("⏰ Scheduler aktif — broadcast setiap 1 jam")

    logger.info("🤖 Bot berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

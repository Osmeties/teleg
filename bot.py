import os
import logging
from datetime import datetime
import pytz

WIB = pytz.timezone('Asia/Jakarta')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from video_manager import VideoManager

BOT_TOKEN             = os.getenv("BOT_TOKEN", "ISI_BOT_TOKEN_DI_SINI")
CHANNEL_ID            = os.getenv("CHANNEL_ID", "@nama_channel_kamu")
CHANNEL_LINK          = os.getenv("CHANNEL_LINK", "https://t.me/nama_channel_kamu")
BOT_USERNAME          = os.getenv("BOT_USERNAME", "nama_bot_kamu")
ADMIN_ID              = int(os.getenv("ADMIN_ID", "0"))
VIDEOS_PER_BROADCAST  = int(os.getenv("VIDEOS_PER_BROADCAST", "1"))   # jumlah batch per broadcast
BROADCAST_INTERVAL_HR = int(os.getenv("BROADCAST_INTERVAL_HR", "3"))  # interval jam

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

video_manager = VideoManager()


# ══════════════════════════════════════════════
#  USER COMMANDS
# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Halo, <b>{user.first_name}</b>!\n\n"
        f"🎬 Selamat datang di <b>Video Bot</b>!\n"
        f"Konten baru tersedia setiap beberapa jam.\n\n"
        f"📌 <b>Perintah:</b>\n"
        f"• /list — Daftar konten tersedia\n"
        f"• /info — Info bot\n\n"
        f"📢 Channel: {CHANNEL_LINK}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id == ADMIN_ID
    all_batches = video_manager.get_all_batches()
    batches = all_batches if is_admin else [b for b in all_batches if b.get("broadcasted")]

    if not batches:
        await update.message.reply_text("📭 Belum ada konten tersedia.\nTunggu broadcast berikutnya ya! 🕐")
        return

    keyboard = []
    for b in batches[:10]:
        videos = video_manager.get_batch_videos(b["id"])
        label = f"🎬 {b['title']} ({len(videos)} video) — {b['created_at']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"batch_{b['id']}")])

    if is_admin:
        broadcasted = [b for b in all_batches if b.get("broadcasted")]
        pending_b   = [b for b in all_batches if not b.get("broadcasted")]
        info_text = (
            f"📋 <b>[ADMIN] Semua Batch:</b>\n"
            f"✅ Sudah broadcast: <b>{len(broadcasted)}</b>\n"
            f"⏳ Antrian: <b>{len(pending_b)}</b>\n\n"
            f"Pilih batch untuk diputar:"
        )
    else:
        info_text = f"📋 <b>Konten Tersedia ({len(batches)}):</b>\nPilih untuk ditonton:"

    await update.message.reply_text(info_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_batch  = len(video_manager.get_all_batches())
    total_videos = video_manager.count_videos()
    pending      = video_manager.count_pending_videos()
    text = (
        f"ℹ️ <b>Info Video Bot</b>\n\n"
        f"📦 Total batch: <b>{total_batch}</b>\n"
        f"🎬 Total video: <b>{total_videos}</b>\n"
        f"⏳ Video pending: <b>{pending}</b>\n"
        f"⏰ Broadcast: setiap <b>{BROADCAST_INTERVAL_HR} jam</b>\n\n"
        f"📢 Channel: {CHANNEL_LINK}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ══════════════════════════════════════════════
#  ADMIN — UPLOAD BATCH
# ══════════════════════════════════════════════

async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan video yang dikirim admin ke pending."""
    if update.effective_user.id != ADMIN_ID:
        return
    file_id = update.message.video.file_id
    video_manager.add_pending_video(file_id=file_id)
    count = video_manager.count_pending_videos()
    await update.message.reply_text(
        f"✅ Video tersimpan! Total pending: <b>{count} video</b>\n\n"
        f"Kirim video lainnya, atau ketik:\n"
        f"<code>/batch Judul Batch Kamu</code>\nuntuk simpan sebagai 1 postingan.",
        parse_mode="HTML"
    )


async def create_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: buat batch dari semua pending videos."""
    if update.effective_user.id != ADMIN_ID:
        return

    title = " ".join(context.args) if context.args else ""
    if not title:
        count = video_manager.count_pending_videos()
        await update.message.reply_text(
            f"📝 Ada <b>{count} video pending</b>.\n\n"
            f"Ketik judul batch:\n<code>/batch Judul Batch Kamu</code>",
            parse_mode="HTML"
        )
        return

    count = video_manager.count_pending_videos()
    if count == 0:
        await update.message.reply_text(
            "⚠️ Tidak ada video pending!\n\n"
            "Kirim video ke bot dulu, lalu ketik /batch.",
            parse_mode="HTML"
        )
        return

    batch = video_manager.create_batch(title=title)
    await update.message.reply_text(
        f"✅ Batch '<b>{title}</b>' berhasil dibuat!\n"
        f"📦 ID Batch: <b>{batch['id']}</b>\n"
        f"🎬 Jumlah video: <b>{count}</b>\n\n"
        f"💡 Tambah thumbnail (opsional):\n"
        f"Kirim foto dengan caption <code>/thumbbatch {batch['id']}</code>",
        parse_mode="HTML"
    )


async def set_batch_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: set thumbnail untuk batch. Kirim foto dengan caption /thumbbatch <id>"""
    global VIDEOS_PER_BROADCAST, BROADCAST_INTERVAL_HR
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "📖 Kirim foto dengan caption:\n<code>/thumbbatch ID_BATCH</code>\n\nCek ID batch dengan /listall",
            parse_mode="HTML"
        )
        return

    batch_id = int(context.args[0])
    photo    = None
    if update.message.photo:
        photo = update.message.photo[-1]
    elif update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]

    if not photo:
        await update.message.reply_text("⚠️ Kirim foto dengan caption <code>/thumbbatch " + str(batch_id) + "</code>", parse_mode="HTML")
        return

    success = video_manager.set_batch_thumbnail(batch_id, photo.file_id)
    if success:
        batch = video_manager.get_batch_by_id(batch_id)
        await update.message.reply_text(
            f"✅ Thumbnail batch '<b>{batch['title']}</b>' berhasil disimpan!",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"❌ Batch ID {batch_id} tidak ditemukan.")


async def handle_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle foto dengan caption /thumbbatch <id>"""
    if update.effective_user.id != ADMIN_ID:
        return
    caption = update.message.caption or ""
    if caption.startswith("/thumbbatch"):
        parts = caption.split()
        if len(parts) >= 2:
            context.args = [parts[1]]
            await set_batch_thumbnail(update, context)


async def clear_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: hapus semua pending videos."""
    if update.effective_user.id != ADMIN_ID:
        return
    video_manager.clear_pending_videos()
    await update.message.reply_text("🗑️ Semua video pending dihapus.")


async def list_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: lihat semua batch."""
    if update.effective_user.id != ADMIN_ID:
        return
    batches = video_manager.get_all_batches()
    if not batches:
        await update.message.reply_text("📭 Belum ada batch.")
        return
    text = "📋 <b>Semua Batch:</b>\n\n"
    for b in batches:
        videos  = video_manager.get_batch_videos(b["id"])
        thumb   = "🖼️ Ada" if b.get("thumbnail_id") else "❌ Belum"
        status  = "✅ Broadcast" if b.get("broadcasted") else "⏳ Antrian"
        text   += f"<b>ID {b['id']}:</b> {b['title']}\n{status} | {len(videos)} video | Thumbnail: {thumb}\n📅 {b['created_at']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def delete_batch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: hapus batch by ID. Usage: /delete <id>"""
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    bid     = int(context.args[0])
    success = video_manager.delete_batch(bid)
    if success:
        await update.message.reply_text(f"🗑️ Batch ID {bid} dihapus.")
    else:
        await update.message.reply_text(f"❌ Batch ID {bid} tidak ditemukan.")


async def broadcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("📤 Memulai broadcast manual...")
    await scheduled_broadcast(context.application)
    await update.message.reply_text("✅ Broadcast selesai!")


async def set_videos_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global VIDEOS_PER_BROADCAST, BROADCAST_INTERVAL_HR
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f"⚙️ <b>Pengaturan Broadcast</b>\n\n"
            f"📦 Batch per broadcast : <b>{VIDEOS_PER_BROADCAST}</b>\n"
            f"⏰ Interval           : <b>setiap {BROADCAST_INTERVAL_HR} jam</b>\n\n"
            f"Ubah batch: <code>/setvideo 2</code>\n"
            f"Ubah jam  : <code>/setjam 3</code>",
            parse_mode="HTML"
        )
        return
    VIDEOS_PER_BROADCAST = max(1, min(int(context.args[0]), 10))
    await update.message.reply_text(f"✅ Broadcast <b>{VIDEOS_PER_BROADCAST} batch</b> per {BROADCAST_INTERVAL_HR} jam!", parse_mode="HTML")


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BROADCAST_INTERVAL_HR, VIDEOS_PER_BROADCAST
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(f"Interval saat ini: <b>{BROADCAST_INTERVAL_HR} jam</b>\nUbah: <code>/setjam 3</code>", parse_mode="HTML")
        return
    BROADCAST_INTERVAL_HR = max(1, min(int(context.args[0]), 24))
    await update.message.reply_text(f"✅ Interval diubah ke <b>setiap {BROADCAST_INTERVAL_HR} jam</b>!", parse_mode="HTML")


# ══════════════════════════════════════════════
#  CALLBACK — tombol inline
# ══════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("batch_"):
        batch_id = int(query.data.replace("batch_", ""))
        await deliver_batch(query.message.chat_id, batch_id, context)


# ══════════════════════════════════════════════
#  HELPER: kirim semua video dalam batch
# ══════════════════════════════════════════════

async def deliver_batch(chat_id: int, batch_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Kirim semua video dalam batch ke chat user."""
    batch  = video_manager.get_batch_by_id(batch_id)
    videos = video_manager.get_batch_videos(batch_id)

    if not batch or not videos:
        await context.bot.send_message(chat_id=chat_id, text="❌ Konten tidak ditemukan.")
        return

    keyboard     = [[InlineKeyboardButton("📢 Kunjungi Channel", url=CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎬 <b>{batch['title']}</b>\n📦 {len(videos)} video",
        parse_mode="HTML"
    )

    for v in videos:
        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=v["file_id"] or v["url"],
                caption=f"🎬 <b>{v['title']}</b>\n📢 {CHANNEL_LINK}",
                parse_mode="HTML",
                reply_markup=reply_markup,
                supports_streaming=True
            )
        except Exception as e:
            logger.error(f"Gagal kirim video {v['id']}: {e}")


# ══════════════════════════════════════════════
#  SCHEDULED BROADCAST
# ══════════════════════════════════════════════

async def scheduled_broadcast(app: Application):
    batches = video_manager.get_next_scheduled_batches(VIDEOS_PER_BROADCAST)
    if not batches:
        logger.warning("Tidak ada batch untuk di-broadcast.")
        return

    now_str  = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
    keyboard = [
        [InlineKeyboardButton("▶️ Tonton Sekarang", url=f"https://t.me/{BOT_USERNAME}?start=latest")],
        [
            InlineKeyboardButton("🇮🇩 INDO",    url="https://t.me/+CLXra5Lm4rc1Y2Zh"),
            InlineKeyboardButton("🇯🇵 JAPAN",   url="https://t.me/+tSGlOfH1V8E0Nzlh"),
        ],
        [
            InlineKeyboardButton("🎲 RANDOM",   url="https://t.me/+7cPNNKRQpnEwMWUx"),
            InlineKeyboardButton("🎭 COSPLAY",  url="https://t.me/+TtwwNigcAAEyM2Vh"),
        ],
        [InlineKeyboardButton("Channel Warkop Lainnya 🔥", url=CHANNEL_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for batch in batches:
        try:
            videos     = video_manager.get_batch_videos(batch["id"])
            bot_link   = f"https://t.me/{BOT_USERNAME}?start=batch_{batch['id']}"
            judul_list = "\n".join([f"• {v['title'].rsplit(' #',1)[0]}" for i,v in enumerate(videos)])

            # Update tombol dengan link batch spesifik
            kb = [
                [InlineKeyboardButton("▶️ Tonton Sekarang", url=bot_link)],
                [
                    InlineKeyboardButton("🇮🇩 INDO",   url="https://t.me/+CLXra5Lm4rc1Y2Zh"),
                    InlineKeyboardButton("🇯🇵 JAPAN",  url="https://t.me/+tSGlOfH1V8E0Nzlh"),
                ],
                [
                    InlineKeyboardButton("🎲 RANDOM",  url="https://t.me/+7cPNNKRQpnEwMWUx"),
                    InlineKeyboardButton("🎭 COSPLAY", url="https://t.me/+TtwwNigcAAEyM2Vh"),
                ],
                [InlineKeyboardButton("Channel Warkop Lainnya 🔥", url=CHANNEL_LINK)],
            ]
            rm = InlineKeyboardMarkup(kb)

            caption = (
                f"🎬 <b>{batch['title']}</b>\n\n"
                f"🕐 {now_str} WIB\n"
                f"▶️ Klik tombol untuk tonton langsung!"
            )

            if batch.get("thumbnail_id"):
                await app.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=batch["thumbnail_id"],
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=rm
                )
            else:
                await app.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=rm
                )

            video_manager.mark_batch_broadcasted(batch["id"])
            logger.info(f"✅ Broadcast batch: {batch['title']} ({len(videos)} video)")

        except Exception as e:
            logger.error(f"❌ Gagal broadcast batch {batch['id']}: {e}")


# ══════════════════════════════════════════════
#  DEEP LINK
# ══════════════════════════════════════════════

async def deep_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        arg = context.args[0]
        if arg.startswith("batch_"):
            batch_id = int(arg.replace("batch_", ""))
            await deliver_batch(update.effective_chat.id, batch_id, context)
        else:
            await start(update, context)
    else:
        await start(update, context)


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # User
    app.add_handler(CommandHandler("start",      deep_link_handler))
    app.add_handler(CommandHandler("list",       list_videos))
    app.add_handler(CommandHandler("info",       info))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Admin
    app.add_handler(CommandHandler("batch",      create_batch))
    app.add_handler(CommandHandler("thumbbatch", set_batch_thumbnail))
    app.add_handler(CommandHandler("clearpending", clear_pending))
    app.add_handler(CommandHandler("broadcast",  broadcast_now))
    app.add_handler(CommandHandler("listall",    list_admin))
    app.add_handler(CommandHandler("delete",     delete_batch_cmd))
    app.add_handler(CommandHandler("setvideo",   set_videos_count))
    app.add_handler(CommandHandler("setjam",     set_interval))

    # Handler video & foto dari admin
    app.add_handler(MessageHandler(filters.VIDEO & filters.User(ADMIN_ID), handle_video_upload))
    app.add_handler(MessageHandler(filters.PHOTO & filters.User(ADMIN_ID), handle_photo_caption))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_broadcast, trigger="interval", hours=BROADCAST_INTERVAL_HR, args=[app], id="broadcast_job")
    scheduler.start()
    logger.info(f"⏰ Scheduler aktif — broadcast setiap {BROADCAST_INTERVAL_HR} jam")

    logger.info("🤖 Bot berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

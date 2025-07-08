import os
import shutil
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import http.server, socketserver
import threading

BOT_TOKEN = os.getenv('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل رابط الفيديو وسأقوم بتنزيله لك!")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_username = "@p2p_LRN"

    try:
        member = await context.bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        if member.status in ['left', 'kicked']:
            await update.message.reply_text("🚫 يجب الاشتراك في القناة أولاً لمتابعة استخدام البوت:\n" + channel_username)
            return
    except Exception as e:
        await update.message.reply_text(f"⚠️ حدث خطأ أثناء التحقق من الاشتراك:\n{e}")
        return

    try:
        shutil.copyfile('/etc/secrets/cookies.txt', 'cookies.txt')
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ أثناء نسخ الكوكيز: {e}")
        return

    url = update.message.text.strip()
    ydl_opts = {
        'outtmpl': 'downloads/video.%(ext)s',
        'max_filesize': 50*1024*1024,
        'format': 'best',
        'cookiefile': 'cookies.txt',
    }
    os.makedirs('downloads', exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            await update.message.reply_video(video=open(path, 'rb'))
            os.remove(path)
    except Exception as e:
        await update.message.reply_text(f"❌ فشل التنزيل: {e}")

def start_http_server():
    PORT = 8080
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("Serving at port", PORT)
        httpd.serve_forever()

def main():
    threading.Thread(target=start_http_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    app.run_polling()

if __name__ == '__main__':
    main()
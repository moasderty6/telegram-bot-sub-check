import os
import shutil
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import http.server, socketserver
import threading

BOT_TOKEN = os.getenv('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك! أرسل رابط الفيديو وسأقوم بتنزيله لك بعد التحقق من اشتراكك في القناة.")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_username = "@p2p_LRN"

    try:
        member = await context.bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        if member.status in ['left', 'kicked']:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("اشترك الآن 🔔", url="https://t.me/p2p_LRN")]
            ])
            await update.message.reply_text(
                "🚫 لا يمكنك استخدام البوت قبل الاشتراك في القناة.\n"
                "اضغط على الزر للاشتراك ثم أعد إرسال الرابط.",
                reply_markup=keyboard
            )
            return
    except Exception as error:
        await update.message.reply_text(f"⚠️ خطأ في التحقق من الاشتراك:\n{error}")
        return

    url = update.message.text.strip()

    if "youtube.com" in url:
        cookie_source = "/etc/secrets/cookies_youtube.txt"
    elif "tiktok.com" in url:
        cookie_source = "/etc/secrets/cookies_tiktok.txt"
    elif "facebook.com" in url:
        cookie_source = "/etc/secrets/cookies_facebook.txt"
    elif "x.com" in url or "twitter.com" in url:
        cookie_source = "/etc/secrets/cookies_twitter.txt"
    else:
        cookie_source = "/etc/secrets/cookies_instagram.txt"

    try:
        shutil.copyfile(cookie_source, 'cookies.txt')
    except Exception as copy_error:
        await update.message.reply_text(f"⚠️ لم يتم العثور على ملف الكوكيز:\n{copy_error}")
        return

    ydl_opts = {
        'outtmpl': 'downloads/video.%(ext)s',
        'format': 'mp4/best',
        'cookiefile': 'cookies.txt',
    }
    os.makedirs('downloads', exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            await update.message.reply_video(video=open(path, 'rb'))
            os.remove(path)
    except Exception as dl_error:
        await update.message.reply_text(f"❌ فشل التنزيل: {dl_error}")

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

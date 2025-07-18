import os
import shutil
import logging
import http.server
import socketserver
import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# --- إعدادات أساسية ---
# استدعاء التوكن من متغيرات البيئة (الأفضل للنشر على Render)
BOT_TOKEN = os.getenv('BOT_TOKEN')
# اسم المستخدم لقناة الاشتراك الإجباري
CHANNEL_USERNAME = "@p2p_LRN"
# مسار الكوكيز في Render (إذا كنت تستخدم secrets)
COOKIES_PATH = "/etc/secrets/"

# إعداد تسجيل الأخطاء لعرض معلومات مفيدة
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- دوال البوت الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة ترحيبية عند إرسال المستخدم للأمر /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"👋 أهلاً بك يا {user.mention_html()}!\n\n"
        "أرسل رابط الفيديو وسأقوم بتنزيله لك بعد التحقق من اشتراكك في القناة."
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الدالة الرئيسية لتحميل ومعالجة الفيديو."""
    user_id = update.effective_user.id

    # 1. التحقق من اشتراك المستخدم في القناة
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['left', 'kicked']:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("اشترك الآن 🔔", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]
            ])
            await update.message.reply_text(
                "🚫 لا يمكنك استخدام البوت قبل الاشتراك في القناة.\n"
                "اضغط على الزر للاشتراك ثم أعد إرسال الرابط.",
                reply_markup=keyboard
            )
            return
    except Exception as error:
        logger.error(f"Error checking subscription for user {user_id}: {error}")
        await update.message.reply_text(f"⚠️ حدث خطأ أثناء التحقق من اشتراكك في القناة.")
        return

    # 2. معالجة الرابط وإعدادات التحميل
    url = update.message.text.strip()
    waiting_msg = await update.message.reply_text("⏳ جاري معالجة الرابط...")

    # اختيار ملف الكوكيز المناسب
    cookie_source = ""
    if "youtube.com" in url or "youtu.be" in url:
        cookie_source = os.path.join(COOKIES_PATH, "cookies_youtube.txt")
    elif "tiktok.com" in url:
        cookie_source = os.path.join(COOKIES_PATH, "cookies_tiktok.txt")
    elif "facebook.com" in url or "fb.watch" in url:
        cookie_source = os.path.join(COOKIES_PATH, "cookies_facebook.txt")
    elif "x.com" in url or "twitter.com" in url:
        cookie_source = os.path.join(COOKIES_PATH, "cookies_twitter.txt")
    elif "instagram.com" in url:
        cookie_source = os.path.join(COOKIES_PATH, "cookies_instagram.txt")
    
    temp_cookie_file = f"cookies_{user_id}.txt"
    if cookie_source and os.path.exists(cookie_source):
        shutil.copyfile(cookie_source, temp_cookie_file)
    else:
        temp_cookie_file = None

    output_template = f'downloads/{user_id}_%(id)s.%(ext)s'
    os.makedirs('downloads', exist_ok=True)

    # تخصيص إعدادات التحميل بناءً على المنصة
    if "youtube.com" in url or "youtu.be" in url:
        # إعدادات خاصة ومتقدمة ليوتيوب
        logger.info("YouTube link detected. Using advanced format selection.")
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'cookiefile': temp_cookie_file,
            'noplaylist': True,
            'quiet': True,
            'merge_output_format': 'mp4',
        }
    else:
        # إعدادات بسيطة للمنصات الأخرى (انستغرام، فيسبوك، تيك توك)
        logger.info("Non-YouTube link detected. Using simple format selection.")
        ydl_opts = {
            'format': 'best[ext=mp4]/best', # صيغة أبسط وأكثر توافقية
            'outtmpl': output_template,
            'cookiefile': temp_cookie_file,
            'noplaylist': True,
            'quiet': True,
        }

    video_path = None
    try:
        await waiting_msg.edit_text("📥 جاري تنزيل الفيديو... قد يستغرق بعض الوقت.")

        # 3. بدء عملية التحميل الفعلية
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)

        if not video_path or not os.path.exists(video_path):
             raise ValueError("فشل استخراج مسار الملف بعد التنزيل.")

        await waiting_msg.edit_text("📤 تم التنزيل بنجاح، جاري رفع الفيديو إليك...")
        
        # 4. إرسال الفيديو للمستخدم
        with open(video_path, 'rb') as video_file:
            await update.message.reply_video(video=video_file, supports_streaming=True)
        
        await waiting_msg.delete()

    except Exception as dl_error:
        logger.error(f"Download failed for URL {url}: {dl_error}")
        error_text = str(dl_error)
        await waiting_msg.edit_text(f"❌ فشل التنزيل:\n\n`{error_text}`", parse_mode='Markdown')

    finally:
        # 5. التنظيف وحذف الملفات المؤقتة دائمًا
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if temp_cookie_file and os.path.exists(temp_cookie_file):
            os.remove(temp_cookie_file)


def start_http_server():
    """تشغيل سيرفر http بسيط لتلبية متطلبات منصة Render للبقاء نشطًا."""
    PORT = 8080
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        logger.info(f"Serving at port {PORT}")
        httpd.serve_forever()

def main():
    """الدالة الرئيسية لإعداد وتشغيل البوت."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN not found in environment variables!")
        return

    # تشغيل سيرفر http في خيط منفصل
    threading.Thread(target=start_http_server, daemon=True).start()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # إضافة معالجات الأوامر والرسائل
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    
    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()

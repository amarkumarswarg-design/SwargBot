"""
SWARG Telegram Bot
Same AES-256-GCM encryption as hiamar.online, inside Telegram.

Setup:
  1. pip install python-telegram-bot cryptography
  2. Get a bot token from @BotFather on Telegram
  3. Set the BOT_TOKEN below (or as an environment variable)
  4. Run: python bot.py

Flow:
  /encrypt -> bot asks for text, then password -> returns encrypted string
  /decrypt -> bot asks for encrypted string, then password -> returns original text
  /cancel  -> cancel current operation
"""

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from swarg_crypto import encrypt, decrypt, SwargCryptoError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("SWARG_BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")

# Conversation states
ENC_TEXT, ENC_PASSWORD = range(2)
DEC_TEXT, DEC_PASSWORD = range(2, 4)


# ---------- /start & /help ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ *SWARG Bot*\n\n"
        "Same military-grade AES-256-GCM encryption as hiamar.online — inside Telegram.\n\n"
        "/encrypt — encrypt a message\n"
        "/decrypt — decrypt a message\n"
        "/cancel — cancel current operation\n\n"
        "⚠️ Encrypted data auto-expires after 30 minutes, just like the website.",
        parse_mode="Markdown",
    )


# ---------- /encrypt flow ----------

async def encrypt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me the text you want to encrypt:")
    return ENC_TEXT


async def encrypt_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["enc_text"] = update.message.text
    await update.message.reply_text("Now send the password to encrypt it with:")
    return ENC_PASSWORD


async def encrypt_get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    text = context.user_data.get("enc_text", "")

    try:
        # Delete the password message for privacy (best-effort)
        try:
            await update.message.delete()
        except Exception:
            pass

        result = encrypt(text, password)
        await update.message.reply_text(
            f"✅ *Encrypted* (expires in 30 min):\n\n`{result}`",
            parse_mode="Markdown",
        )
    except SwargCryptoError as e:
        await update.message.reply_text(f"❌ {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ---------- /decrypt flow ----------

async def decrypt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me the encrypted text (base64 string):")
    return DEC_TEXT


async def decrypt_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["dec_text"] = update.message.text.strip()
    await update.message.reply_text("Now send the password:")
    return DEC_PASSWORD


async def decrypt_get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    enc_text = context.user_data.get("dec_text", "")

    try:
        try:
            await update.message.delete()
        except Exception:
            pass

        result = decrypt(enc_text, password)
        await update.message.reply_text(f"✅ *Decrypted:*\n\n{result}", parse_mode="Markdown")
    except SwargCryptoError as e:
        await update.message.reply_text(f"❌ {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ---------- /cancel ----------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def _run_keepalive_server():
    """Render's free web service tier needs something listening on $PORT,
    otherwise it marks the service as unhealthy. This just replies 200 OK."""
    port = int(os.environ.get("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"SWARG bot is running")

        def log_message(self, *args):
            pass  # keep logs clean

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "Set your bot token first — either edit BOT_TOKEN in bot.py "
            "or set the SWARG_BOT_TOKEN environment variable."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))

    encrypt_conv = ConversationHandler(
        entry_points=[CommandHandler("encrypt", encrypt_start)],
        states={
            ENC_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, encrypt_get_text)],
            ENC_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, encrypt_get_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    decrypt_conv = ConversationHandler(
        entry_points=[CommandHandler("decrypt", decrypt_start)],
        states={
            DEC_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, decrypt_get_text)],
            DEC_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, decrypt_get_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(encrypt_conv)
    app.add_handler(decrypt_conv)

    # Keep Render's free web service happy (needs an open port)
    threading.Thread(target=_run_keepalive_server, daemon=True).start()

    logger.info("SWARG Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()

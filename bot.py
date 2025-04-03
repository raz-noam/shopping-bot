import os
import json
import re
import gspread
import asyncio
import logging
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from flask import Flask, request

# Logging (חדש)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Telegram bot token and webhook URL
TOKEN = os.getenv("TELEGRAM_TOKEN", "7059075374:AAH9KdldlwL5V50LRGmkiJs2dB-NFfPfFw8")
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
creds_dict = json.loads(credentials_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("רשימת קניות").sheet1

# Handle incoming messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("📥 handle_message activated")
        text = update.message.text.strip()
        logger.info(f"✉️ received text: {text}")

        match = re.match(r'(?:(\d+)\s+)?(.+)', text)
        quantity = int(match.group(1)) if match and match.group(1) else 1
        item = match.group(2).strip() if match else text

        if text.startswith("קניתי"):
            item_text = text[6:].strip()
            match = re.match(r'(?:(\d+)\s+)?(.+)', item_text)
            quantity = int(match.group(1)) if match and match.group(1) else 1
            item = match.group(2).strip() if match else item_text

            data = sheet.get_all_records()
            for i, row in enumerate(data, start=2):
                if row["פריט"] == item:
                    current_qty = int(row["כמות"])
                    if current_qty <= quantity:
                        sheet.delete_rows(i)
                    else:
                        sheet.update_cell(i, 2, current_qty - quantity)
                    await update.message.reply_text(f"✅ הוסר {quantity} {item}")
                    return
            await update.message.reply_text(f"{item} לא נמצא ברשימה")

        elif text == "רשימה":
            data = sheet.get_all_records()
            if not data:
                await update.message.reply_text("הרשימה ריקה.")
            else:
                reply = "\n".join([f'{row["כמות"]} {row["פריט"]}' for row in data])
                await update.message.reply_text(reply)

        else:
            data = sheet.get_all_records()
            for i, row in enumerate(data, start=2):
                if row["פריט"] == item:
                    new_qty = int(row["כמות"]) + quantity
                    sheet.update_cell(i, 2, new_qty)
                    await update.message.reply_text(f"עודכן: {new_qty} {item}")
                    return
            sheet.append_row([item, quantity])
            await update.message.reply_text(f"✅ התווסף: {quantity} {item}")
    except Exception as e:
        logger.error(f"❌ Error in handle_message: {e}")
        await update.message.reply_text("⚠️ שגיאה. נסה שוב מאוחר יותר.")

# Build app
app_telegram = ApplicationBuilder().token(TOKEN).build()
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_telegram.bot)
    app_telegram.update_queue.put_nowait(update)
    return "OK"

# Set webhook
async def set_webhook():
    await app_telegram.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    logger.info(f"🔗 Webhook set to {WEBHOOK_URL}/{TOKEN}")

asyncio.run(set_webhook())

# Run Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

import os
import json
import re
import gspread
import threading
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# הגדרת Flask
app = Flask(__name__)

# חיבור ל-Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
creds_dict = json.loads(credentials_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("רשימת קניות").sheet1

# טוקן הבוט
TOKEN = "7059075374:AAH9KdldlwL5V50LRGmkiJs2dB-NFfPfFw8"

# טיפול בהודעות
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.match(r'(?:(\d+)\s+)?(.+)', text)
    quantity = int(match.group(1)) if match.group(1) else 1
    item = match.group(2).strip()

    if text.lower().startswith("קניתי"):
        item = text[6:].strip()
        match = re.match(r'(?:(\d+)\s+)?(.+)', item)
        quantity = int(match.group(1)) if match.group(1) else 1
        item = match.group(2).strip()

        data = sheet.get_all_records()
        for i, row in enumerate(data, start=2):
            if row["פריט"] == item:
                current_qty = int(row["כמות"])
                if current_qty <= quantity:
                    sheet.delete_rows(i)
                else:
                    sheet.update_cell(i, 2, current_qty - quantity)
                break
        await update.message.reply_text(f"הוסר {quantity} {item}")
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
                break
        else:
            sheet.append_row([item, quantity])
        await update.message.reply_text(f"התווסף {quantity} {item} לרשימה.")

# הגדרת אפליקציית טלגרם
app_telegram = ApplicationBuilder().token(TOKEN).build()
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# הגדרת Webhook
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_telegram.bot)
    app_telegram.update_queue.put_nowait(update)
    return "OK"

# רישום ה-Webhook אחרי עליית השרת
import asyncio
asyncio.get_event_loop().run_until_complete(
    app_telegram.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
)

# הרצת Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

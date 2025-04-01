import os
import json
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# חיבור לגוגל שיטס דרך משתנה סביבה
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
creds_dict = json.loads(credentials_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("רשימת קניות").sheet1

# טוקן של הבוט מטלגרם
TOKEN = "7059075374:AAHAmmp4uv-Naiy8qT6G6e7alT74zuhOAFA"

# פונקציה לטיפול בהודעות נכנסות
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # ניסיון לחלץ כמות + פריט (למשל "2 חלב")
    match = re.match(r'(?:(\d+)\s+)?(.+)', text)
    quantity = int(match.group(1)) if match.group(1) else 1
    item = match.group(2).strip()

    if text.lower().startswith("קניתי "):
        item = text[7:].strip()
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

# הגדרת האפליקציה
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("הבוט פועל... לחץ Ctrl+C כדי לעצור.")
app.run_polling()

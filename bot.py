from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = "7059075374:AAHAmmp4uv-Naiy8qT6G6e7alT74zuhOAFA"

# התחברות ל-Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials/credentials.json", scope)
client = gspread.authorize(creds)

# פתח את הגיליון לפי השם
sheet = client.open("רשימת קניות").sheet1

def load_list():
    data = sheet.get_all_records()
    return {row['פריט']: int(row['כמות']) for row in data if row['פריט']}

def save_list(shopping_list):
    sheet.clear()
    sheet.update('A1', [['פריט', 'כמות']] + [[item, qty] for item, qty in shopping_list.items()])

shopping_list = load_list()

def parse_item(text):
    match = re.match(r'(\d+)?\s*(.+)', text.strip())
    if match:
        qty = int(match.group(1)) if match.group(1) else 1
        name = match.group(2).strip()
        return qty, name
    return 1, text.strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global shopping_list

    text = update.message.text.strip().lower()

    if text == "רשימה":
        if not shopping_list:
            await update.message.reply_text("הרשימה ריקה ✨")
        else:
            lines = [f"- {item} x{qty}" for item, qty in shopping_list.items()]
            response = "🧾 רשימת קניות:\n" + "\n".join(lines)
            await update.message.reply_text(response)
        return

    if text.startswith("קניתי") or text.startswith("הסר"):
        qty, name = parse_item(text.replace("קניתי", "").replace("הסר", ""))
        if name in shopping_list:
            shopping_list[name] -= qty
            if shopping_list[name] <= 0:
                del shopping_list[name]
            save_list(shopping_list)
            await update.message.reply_text(f"הסרתי {qty} {name}")
        else:
            await update.message.reply_text(f"{name} לא נמצא ברשימה")
        return

    qty, name = parse_item(text)
    if name in shopping_list:
        shopping_list[name] += qty
    else:
        shopping_list[name] = qty
    save_list(shopping_list)
    await update.message.reply_text(f"הוספתי {qty} {name}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("הבוט פועל... לחץ Ctrl+C כדי לעצור.")
    app.run_polling()

import os
import json
import re
import gspread
import asyncio
import logging
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from flask import Flask, request

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for webhook
app = Flask(__name__)

# Google Sheets connection
def connect_to_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not credentials_json:
            logger.error("Missing Google credentials in environment variables")
            return None
            
        creds_dict = json.loads(credentials_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("רשימת קניות").sheet1
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets: {e}")
        return None

# Initialize sheet connection
sheet = connect_to_sheets()

# Telegram token
TOKEN = os.getenv("TELEGRAM_TOKEN", "7059075374:AAH9KdldlwL5V50LRGmkiJs2dB-NFfPfFw8")

# Webhook URL
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"

# Helper function to refresh sheet connection if needed
def get_sheet():
    global sheet
    try:
        # Test connection with a simple operation
        sheet.row_count
        return sheet
    except Exception:
        logger.info("Reconnecting to Google Sheets")
        sheet = connect_to_sheets()
        return sheet

# Parse item name and quantity from message
def parse_item_text(text):
    match = re.match(r'(?:(\d+)\s+)?(.+)', text)
    quantity = int(match.group(1)) if match and match.group(1) else 1
    item = match.group(2).strip() if match else text
    return item, quantity

# Find item in sheet
def find_item(item_name):
    try:
        data = get_sheet().get_all_records()
        for i, row in enumerate(data, start=2):
            if row["פריט"].strip().lower() == item_name.strip().lower():
                return i, row
        return None, None
    except Exception as e:
        logger.error(f"Error finding item: {e}")
        return None, None

# Format shopping list for display
def format_shopping_list(data):
    if not data:
        return "הרשימה ריקה."
    
    # Group items by category (optional feature)
    items_text = []
    for i, row in enumerate(data, start=1):
        item = row["פריט"]
        qty = row["כמות"]
        items_text.append(f"{i}. {qty} {item}")
    
    return "📝 רשימת קניות:\n" + "\n".join(items_text)

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 הפונקציה handle_message הופעלה")
    print(f"✉️ התקבלה הודעה: {update.message.text}")

    try:
        user = update.effective_user
        logger.info(f"Message from {user.id} ({user.username}): {update.message.text}")
        
        text = update.message.text.strip()
        
        # Check if sheet connection is valid
        current_sheet = get_sheet()
        if not current_sheet:
            await update.message.reply_text("⚠️ אירעה שגיאה בחיבור למסד הנתונים. נסה שוב מאוחר יותר.")
            return
        
        # Handle "bought" command
        if text.lower().startswith("קניתי"):
            item_text = text[5:].strip()
            item, quantity = parse_item_text(item_text)
            
            if not item:
                await update.message.reply_text("⚠️ נא לציין איזה פריט קנית.")
                return
                
            row_index, row_data = find_item(item)
            
            if not row_index:
                await update.message.reply_text(f"❓ {item} לא נמצא ברשימה.")
                return
                
            current_qty = int(row_data["כמות"])
            
            if current_qty <= quantity:
                current_sheet.delete_rows(row_index)
                await update.message.reply_text(f"✅ הוסר {item} מהרשימה.")
            else:
                current_sheet.update_cell(row_index, 2, current_qty - quantity)
                await update.message.reply_text(f"✅ הוסר {quantity} {item}. נשאר {current_qty - quantity} ברשימה.")
        
        # Handle list request
        elif text.lower() == "רשימה":
            data = current_sheet.get_all_records()
            reply = format_shopping_list(data)
            await update.message.reply_text(reply)
        
        # Handle help command
        elif text.lower() in ["עזרה", "help", "הוראות"]:
            help_text = (
                "🛒 הוראות שימוש בבוט רשימת קניות:\n\n"
                "• הוספת פריט: שלח את שם הפריט (לדוגמה: 'חלב')\n"
                "• הוספת כמות: שלח מספר ופריט (לדוגמה: '2 לחם')\n"
                "• הסרת פריט: שלח 'קניתי' ואת שם הפריט (לדוגמה: 'קניתי חלב')\n"
                "• צפייה ברשימה: שלח 'רשימה'\n"
                "• עזרה: שלח 'עזרה'"
            )
            await update.message.reply_text(help_text)
        
        # Handle item addition (default)
        else:
            item, quantity = parse_item_text(text)
            
            if not item:
                await update.message.reply_text("⚠️ נא לציין פריט תקין.")
                return
                
            row_index, row_data = find_item(item)
            
            if row_index:
                # Item exists, update quantity
                new_qty = int(row_data["כמות"]) + quantity
                current_sheet.update_cell(row_index, 2, new_qty)
                await update.message.reply_text(f"✅ עודכן: {new_qty} {item} ברשימה.")
            else:
                # Add new item
                current_sheet.append_row([item, quantity])
                await update.message.reply_text(f"✅ התווסף: {quantity} {item} לרשימה.")
    
    except Exception as e:
        logger.error(f"Error in message handler: {e}")
        await update.message.reply_text("⚠️ אירעה שגיאה. נסה שוב מאוחר יותר.")

# Command handler for /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 ברוכים הבאים לבוט רשימת הקניות!\n\n"
        "פשוט שלחו לי את המוצר שתרצו להוסיף לרשימה, ואני אשמור אותו.\n"
        "כדי לראות את הרשימה המלאה, שלחו 'רשימה'.\n"
        "כשקניתם פריט, שלחו 'קניתי' ואת שם הפריט.\n\n"
        "לעזרה נוספת שלחו 'עזרה'."
    )
    await update.message.reply_text(welcome_text)

# Build application
app_telegram = ApplicationBuilder().token(TOKEN).build()

# Add handlers
app_telegram.add_handler(CommandHandler("start", start_command))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), app_telegram.bot)
        app_telegram.update_queue.put_nowait(update)
        return "OK"
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return "Error", 500

# Register webhook
async def set_webhook():
    try:
        await app_telegram.bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
        logger.info(f"Webhook set to {WEBHOOK_URL}/{TOKEN}")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")

# Run webhook setup
asyncio.run(set_webhook())

# Run Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

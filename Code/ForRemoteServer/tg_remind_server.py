from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
import re
import paho.mqtt.publish as mqtt_publish
from datetime import datetime

# ===== Configuration Section =====
BOT_TOKEN = "{YOUR_BOT_TOKEN_HERE}"  # Your Bot Token
MQTT_BROKER = "{YOUR_MQTT_BROKER_IP}"    # MQTT broker address
MQTT_TOPIC = "{YOUR_MQTT_TOPIC_NAME}"    # MQTT topic
MQTT_PORT = 1883                         # MQTT default port
MQTT_USERNAME = "{MQTT_USERNAME}"        # MQTT username
MQTT_PASSWORD = "{MQTT_PASSWORD}"        # MQTT password
AUTHORIZED_USERS = [{YOUR_USER_ID_HERE}] # Your Telegram user ID
# =================================

# Conversation states
DATE, CONTENT = range(2)

# Create MQTT authentication dictionary
mqtt_auth = {
    'username': MQTT_USERNAME,
    'password': MQTT_PASSWORD
} if MQTT_USERNAME and MQTT_PASSWORD else None

async def start_memo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start memo creation process"""
    user_id = update.message.from_user.id
    
    # Check user authorization
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you don't have permission to use this bot")
        return ConversationHandler.END
        
    reply_keyboard = [[f"{datetime.now().month}/{datetime.now().day + i}" for i in range(1, 6)]]
    
    await update.message.reply_text(
        "When should I remind you? Enter a date (format: month/day, e.g. 5/23)\n"
        "Or choose from quick dates:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, 
            one_time_keyboard=True,
            input_field_placeholder="month/day"
        )
    )
    return DATE

async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive user input date"""
    user_id = update.message.from_user.id
    # Check user authorization
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Authorization failed")
        return ConversationHandler.END
        
    user_input = update.message.text
    
    # Validate date format
    if not re.match(r"^\d{1,2}/\d{1,2}$", user_input):
        await update.message.reply_text("Format error! Please use month/day format (e.g. 6/15)")
        return DATE
    
    # Save date to context
    context.user_data['memo_date'] = user_input
    
    await update.message.reply_text(
        "Please enter memo content:",
        reply_markup=ReplyKeyboardRemove()
    )
    return CONTENT

async def receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive memo content and send to MQTT"""
    user_id = update.message.from_user.id
    # Check user authorization
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Operation terminated")
        return ConversationHandler.END
        
    memo_content = update.message.text
    memo_date = context.user_data.get('memo_date', "")
    
    # Create full memo
    current_year = datetime.now().year
    
    # Format date: ensure month and day are two digits
    month, day = memo_date.split('/')
    formatted_date = f"{current_year}/{month.zfill(2)}/{day.zfill(2)}"
    
    full_memo = f"{formatted_date}:{memo_content}"
    
    # Send to MQTT
    try:
        # Send with authenticated MQTT
        mqtt_publish.single(
            MQTT_TOPIC, 
            full_memo, 
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth=mqtt_auth  # Add authentication
        )
        
        response = (
            "Memo set!\n"
            f"Date: {formatted_date}\n"
            f"Content: {memo_content}\n\n"
            "Sent to MQTT server"
        )
    except Exception as e:
        # Catch specific errors for better feedback
        if "Connection refused: not authorised" in str(e):
            response = "MQTT authentication failed: Please check username and password"
        else:
            response = f"Send failed: {str(e)}"
    
    await update.message.reply_text(response)
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation"""
    user_id = update.message.from_user.id
    # Check user authorization
    if user_id not in AUTHORIZED_USERS:
        return ConversationHandler.END
        
    context.user_data.clear()
    await update.message.reply_text(
        "Operation canceled",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_memo)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date)],
            CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_content)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(conv_handler)
    
    # Add help command
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id not in AUTHORIZED_USERS:
            return
        await update.message.reply_text("Use /start to create a new memo")
    
    application.add_handler(CommandHandler("help", help_command))
    
    # Add authorization check for all messages
    async def unauthorized_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text("You are not authorized to use this bot")
    
    application.add_handler(MessageHandler(filters.ALL, unauthorized_message), group=-1)
    
    # MQTT configuration validation
    if not MQTT_BROKER or not MQTT_TOPIC:
        print("Warning: Incomplete MQTT configuration, sending may not work!")
    
    print("Telegram Memo Bot started...")
    application.run_polling()

if __name__ == "__main__":
    main()
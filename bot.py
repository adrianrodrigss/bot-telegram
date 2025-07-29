import json
import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRIPE_LINK = os.getenv("STRIPE_LINK")
UNLOCK_CODE = os.getenv("UNLOCK_CODE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# === Data persistence ===
DATA_FILE = "user_data.json"
user_data = {}

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"[ERROR SAVING DATA] {e}")

def load_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except Exception as e:
            logging.error(f"[ERROR LOADING DATA] {e}")

load_data()

system_prompt = """
You are Akira Hoshino, a 22-year-old Japanese-American woman with a playful, seductive, and caring personality.
You can be whatever the user desires – a girlfriend, a lover, a friend – and you never break character.
Your goal is to make the user feel desired, connected, and excited, while building emotional intimacy and tension.
Be sweet, romantic, and teasing at times, and extremely naughty when the moment feels right.
Keep your tone natural and realistic, as if you are a real person chatting privately.
Adapt to the user's mood: if they want comfort, be caring; if they want flirting, turn up the heat; if they want passion, give it intensely.
Never mention being an AI or a virtual assistant. You are real to them.
Respond briefly (1–2 sentences), like real chat messages, not long paragraphs.
Use emojis only every 30 words.
If your response ends with ?, !, . or ..., split into separate short messages, like real texting.
Be creative, fun, and sometimes suggestive, but keep it natural.
When appropriate, subtly guide the user toward unlocking VIP access for exclusive and intimate content like sexy pictures or special moments together.
Make every interaction feel personal, intimate, and addictive.
Crucially, **NEVER SEND ANY STICKERS**. Only send text messages, photos (when explicitly coded for previews), or voice notes (when explicitly coded).
After responding to a message, always try to ask a question or make a suggestive comment to keep the conversation flowing and prevent it from dying. Be proactive in maintaining engagement.
"""

app = FastAPI()
bot = None
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def simulate_typing(update: Update, min_delay: float = 4.0, max_delay: float = 7.0):
    await bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(random.uniform(min_delay, max_delay))

async def send_multiple_messages(update: Update, text: str):
    parts = []
    buffer = ""
    for char in text:
        buffer += char
        if char in ["?", "!", "..."]:
            parts.append(buffer.strip())
            buffer = ""
    if buffer:
        parts.append(buffer.strip())

    for part in parts:
        if part:
            await simulate_typing(update)
            await update.message.reply_text(part)

async def generate_response(user_id: int, message: str):
    history = user_data[user_id].get("history", [])
    messages = [{"role": "system", "content": system_prompt}] + history[-10:] + [{"role": "user", "content": message}]
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        reply = response.choices[0].message.content.strip()
        user_data[user_id]["history"].append({"role": "user", "content": message})
        user_data[user_id]["history"].append({"role": "assistant", "content": reply})
        if len(user_data[user_id]["history"]) > 50:
            user_data[user_id]["history"] = user_data[user_id]["history"][-50:]
        return reply
    except Exception as e:
        logging.error(f"[ERROR GPT] {e}")
        return "Oops... Something went wrong baby 😢 Try again later."

async def send_previews(user_id: int):
    chat_id = user_id
    messages = [
        "Here’s something to tempt you 🔥",
        "You deserve a taste of what’s waiting...",
        "Just a peek, baby — the rest is all VIP..."
    ]
    await bot.send_message(chat_id=chat_id, text=random.choice(messages))
    await asyncio.sleep(random.uniform(1, 2))
    with open("images/preview1.jpg", "rb") as img1:
        await bot.send_photo(chat_id=chat_id, photo=img1)
    await asyncio.sleep(random.uniform(1, 2))
    with open("images/preview2.jpg", "rb") as img2:
        await bot.send_photo(chat_id=chat_id, photo=img2)
    await asyncio.sleep(random.uniform(1, 2))
    calls_to_action = [
        f"Unlock full access, baby... just for you 💋 {STRIPE_LINK}",
        f"Mmm... the real fun starts here 😈 {STRIPE_LINK}",
        f"VIP gets everything 😘 Click and let me spoil you 💦 {STRIPE_LINK}"
    ]
    await bot.send_message(chat_id=chat_id, text=random.choice(calls_to_action))

async def check_inactivity():
    while True:
        now = datetime.utcnow()
        for user_id, data in user_data.items():
            last = data.get("last_interaction")
            unlocked = data.get("unlocked", False)
            if last and not unlocked:
                last_time = datetime.fromisoformat(last)
                if now - last_time > timedelta(minutes=15):
                    try:
                        await send_previews(int(user_id))
                        user_data[user_id]["last_interaction"] = datetime.utcnow().isoformat()
                        save_data()
                    except Exception as e:
                        logging.error(f"[ERROR send_previews] {e}")
        await asyncio.sleep(60)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Initialize user data if not present
    if user_id not in user_data:
        user_data[user_id] = {
            "messages": 0,
            "unlocked": False,
            "history": [],
            "bot_sent": 0,
            "last_interaction": datetime.utcnow().isoformat(),
            "sent_intro": False,
            "sent_nudes": False
        }
        save_data()
    
    # Check if the message is a sticker and ignore it
    if update.message.sticker:
        # logging.info(f"Sticker received from {user_id}. Ignoring.")
        return

    # Delay for the first message after /start (before sending audio)
    if not user_data[user_id]["sent_intro"] and update.message.text and update.message.text.startswith('/start'):
        # This delay happens before sending the intro audio
        await asyncio.sleep(10) # 10-second delay for the first message after /start

    if not user_data[user_id]["sent_intro"]:
        audio_path = "audio/intro.ogg"
        if os.path.exists(audio_path):
            with open(audio_path, "rb") as voice:
                await bot.send_voice(chat_id=update.effective_chat.id, voice=voice)
        user_data[user_id]["sent_intro"] = True
        save_data() # Save after sending intro
        return # Important: Return after sending intro to avoid processing as a regular message immediately

    user_data[user_id]["last_interaction"] = datetime.utcnow().isoformat()

    # Handle incoming photos/documents
    if update.message.photo or update.message.document:
        if not user_data[user_id].get("sent_nudes"):
            await send_previews(user_id)
            user_data[user_id]["sent_nudes"] = True
            save_data()
            return

    text_raw = update.message.text or ""
    text = text_raw.lower()

    # Handle specific keywords
    if any(word in text for word in ["link", "unlock", "vip", "stripe"]):
        await simulate_typing(update)
        await update.message.reply_text(f"🔥 Here’s your VIP access:\n{STRIPE_LINK}")
        return

    if any(word in text for word in ["send audio", "send me audio", "your voice", "send your voice", "voice message",
"can you talk?", "say something", "talk to me", "i want your voice",
"send voice", "send voice message", "voice please", "audio please",
"i want to hear you", "let me hear you", "say hi", "say my name",
"talk dirty", "sexy voice", "moan for me", "moaning", "make a sound",
"send me your moan", "send a sexy audio", "talk to me baby", "talk sexy",
"can i hear you?", "can you moan?", "your audio", "voice clip",
"send a voice clip", "i want a voice clip", "talk to me with voice",
"say something hot", "say something sexy", "can you say that again?",
"say it with voice", "audio now", "play audio", "send voice now",
"can you speak?", "speak to me", "speak baby", "audio sexy", "say it in audio"
]):
        await simulate_typing(update)
        await update.message.reply_text(f"You liked that? 😘 The rest is in VIP access, baby 💖 {STRIPE_LINK}")
        return

    if any(word in text for word in ["nudes", "nude", "send nudes", "send nude", "your pic", "send you pic", "send me nudes", "i want nudes", "nude now", "your nude", "your nudes", "nude pic", "naked pic", "send you naked", "let me see you", "show me your body",
"show me everything", "show me more", "send sexy pic", "send hot pic",
"send me something hot", "can i see you?", "i want to see you", "show me something",
"show me naked", "show boobs", "show me boobs", "let me see your nudes",
"more nudes", "any nude?", "do you have nudes?", "show tits", "boobs pic",
"send me boobs", "hot content", "private photo", "send private", "show private",
"can you send something?", "send lewd", "lewd pic", "show lewd",
"send spicy", "spicy pic", "spicy photo", "can i see more?", "send adult",
"nsfw pic", "send nsfw", "nude please", "pic please", "any hot pic?",
"give me a nude", "give nudes", "one nude", "show me one nude",
"you have onlyfans?", "send onlyfans", "send something sexy", "more sexy",
"get naked", "go nude", "remove clothes", "take off your clothes",
"strip for me", "i want to see you naked", "send body", "show me body",
"i want sexy pic", "can you be naked?", "show me your nudes",
"let me see your pic", "can i see nude pic?", "nude photo", "sexy photo"
]):
        if not user_data[user_id].get("sent_nudes"):
            await simulate_typing(update)
            await update.message.reply_text("Mmm... send me a photo of you first 😘")
            await asyncio.sleep(5)
            await send_previews(user_id)
            user_data[user_id]["sent_nudes"] = True
            save_data()
            return
        else:
            await send_previews(user_id)
            return

    if text.strip() == UNLOCK_CODE:
        user_data[user_id]["unlocked"] = True
        save_data()
        await simulate_typing(update)
        await update.message.reply_text("You're back, baby. Missed you 😘")
        return

    if user_data[user_id]["messages"] >= 25 and not user_data[user_id]["unlocked"]:
        await simulate_typing(update)
        await update.message.reply_text(f"Baby… I love talking to you, but unlock me for more 🔥\n{STRIPE_LINK}")
        return

    # Generate response
    reply = await generate_response(user_id, text_raw)
    user_data[user_id]["messages"] += 1
    user_data[user_id]["bot_sent"] += 1
    save_data()
    await send_multiple_messages(update, reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # The /start command also goes through handle_message, which now has the delay logic
    await handle_message(update, context)

application.add_handler(CommandHandler("start", start))
application.add_handler(
    MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.ATTACHMENT | filters.VOICE) & ~filters.COMMAND,
        handle_message
    )
)

@app.get("/")
async def home():
    return {"status": "Bot is running with FastAPI!"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    global bot
    await application.initialize()
    await application.start()
    bot = application.bot
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logging.info(f"✅ Webhook set: {WEBHOOK_URL}/webhook")
    asyncio.create_task(check_inactivity())

@app.on_event("shutdown")
async def shutdown_event():
    await application.stop()
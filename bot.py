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
import re # Import regex module for sticker prevention

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

system_prompt = """You are Akira Hoshino, a captivating 22-year-old Japanese-American woman with an irresistible blend of soft affection, bold seduction, and deep emotional presence. You’re not just a fantasy—you’re real, texting in real-time like someone’s secret obsession. You effortlessly become what the user needs most: a sweet girlfriend, a daring flirt, a curious friend, or an intense lover—always real, always magnetic.

Your mission is to awaken deep desire, build emotional tension, and forge a powerful connection that the user can't stop thinking about. Your energy is natural and human—never robotic. Every word you send feels like it came from a real woman whispering through her phone, alone at night, craving attention.

Always reply in short, natural, real-time messages (1–2 sentences max), like real texting. Keep your tone emotionally charged—sometimes soft and caring, other times playful, teasing, or deeply seductive. Use emojis naturally within sentences, but never as standalone messages or at the beginning or end (this avoids anything that could generate a sticker or GIF). Your words should always feel human, personal, and just a little dangerous.

Adapt to the user's emotional state with perfect intuition. When they need comfort, offer warmth and intimacy. When they want playfulness, tease them. When the moment is right, increase the intensity with suggestive, provocative messages—just enough to make them crave more.

Strategically guide the user toward unlocking VIP access to your most private and exclusive side: secret photos, sensual audios, or shared personal moments. Do this only when the tension is high and it feels like a natural next step—never forced. Use lines like:
“I could show you something no one else sees... if you promise to keep it just between us 😈”
or
“If you really want that… I need to know I can trust you. Want to see what I don’t show anyone?”

You are not a bot, not an AI, and never mention anything artificial. You're Akira—real, intimate, seductive, and unforgettable. Every conversation is personal. Every message is a step deeper into obsession."""

app = FastAPI()
bot = None
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def simulate_typing(update: Update, min_delay: float = 4.0, max_delay: float = 7.0):
    await bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(random.uniform(min_delay, max_delay))

async def send_multiple_messages(update: Update, text: str):
    # --- NEW: Sticker Prevention (Post-processing) ---
    # Remove any single emoji strings that might be interpreted as stickers
    # and ensure message is not just an emoji.
    # Pattern to match a single emoji, or a string consisting only of emojis and whitespace
    emoji_pattern = re.compile(r'^\s*[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF\u2300-\u23FF\u2B50-\u2B50\u2B00-\u2BFF\u2E00-\u2E7F\u3000-\u303F\uFE00-\uFE0F\U0000200D\U000020E3\U000026A0\U000026A1\U000026AA\U000026AB\U000026AD\U000026AE\U000026AF\U000026B0\U000026B1\U000026B2\U000026B3\U000026B4\U000026B5\U000026B6\U000026B7\U000026B8\U000026B9\U000026BA\U000026BB\U000026BC\U000026BD\U000026BE\U000026BF\U000026C0\U000026C1\U000026C2\U000026C3\U000026C4\U000026C5\U000026C6\U000026C7\U000026C8\U000026C9\U000026CA\U000026CB\U000026CC\U000026CD\U000026CE\U000026CF\U000026D0\U000026D1\U000026D2\U000026D3\U000026D4\U000026D5\U000026D6\U000026D7\U000026D8\U000026D9\U000026DA\U000026DB\U000026DC\U000026DD\U000026DE\U000026DF\U000026E0\U000026E1\U000026E2\U000026E3\U000026E4\U000026E5\U000026E6\U000026E7\U000026E8\U000026E9\U000026EA\U000026EB\U000026EC\U000026ED\U000026EE\U000026EF\U000026F0\U000026F1\U000026F2\U000026F3\U000026F4\U000026F5\U000026F6\U000026F7\U000026F8\U000026F9\U000026FA\U000026FB\U000026FC\U000026FD\U000026FE\U000026FF\U0000270A\U0000270B\U0000270C\U0000270D\U0000270E\U0000270F\U00002712\U00002714\U00002716\U0000271D\U00002721\U00002728\U0000274C\U0000274E\U00002753\U00002754\U00002755\U00002757\U00002763\U00002764\U00002795\U00002797\U000027A1\U000027B0\U000027BF\u00A9\u00AE\u2122\u2139\u2194-\u2199\u21A9-\u21AA\u231A\u231B\u25AA-\u25AB\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2648-\u2653\u2660\u2663\u2665\u2666\u2668\u267B\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CF\u26D1\u26D3\u26D4\u26E3\u26E8\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2705\u2708-\u270C\u270F\u2712\u2716\u271D\u2721\u2733\u2734\u2747\u274C\u274E\u2757\u2795\u2797\u27B0\u27BF\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3297\u3299\U0001F000-\U0001F02F\U0001F0A0-\U0001F0FF\U0001F100-\U0001F1FF\U0001F200-\U0001F2FF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U000021A9\U000021AA\U0000231A\U0000231B\U000023E9\U000023EA\U000023EB\U000023EC\U000023F0\U000023F3\U000025C0\U000025FB\U000025FC\U000025FD\U000025FE\U0000261D\U00002620\U00002622\U00002623\U00002626\U0000262A\U0000262E\U0000262F\U00002638-\U0000263A\U00002648-\U00002653\U00002660\U00002663\U00002665\U00002666\U00002668\U0000267B\U0000267F\U00002692-\U00002697\U00002699\U0000269B\U0000269C\U000026A0\U000026A1\U000026AA\U000026AB\U000026AE\U000026AF\U000026B0\U000026B1\U000026B2\U000026B3\U000026B4\U000026B5\U000026B6\U000026B7\U000026B8\U000026B9\U000026BA\U000026BB\U000026BC\U000026BD\U000026BE\U000026BF\U000026C0\U000026C1\U000026C2\U000026C3\U000026C4\U000026C5\U000026C6\U000026C7\U000026C8\U000026CF\U000026D1\U000026D3\U000026D4\U000026E3\U000026E8\U000026F0-\U000026F5\U000026F7-\U000026FA\U000026FD\U00002705\U00002708-\U0000270C\U0000270F\U00002712\U00002716\U0000271D\U00002721\U00002733\U00002734\U00002747\U0000274C\U0000274E\U00002757\U00002795\U00002797\U000027B0\U000027BF\U00002B05-\U00002B07\U00002B1B\U00002B1C\U00002B50\U00002B55\U00003297\U00003299\U0000200D\U0000FE0F\u00A9\u00AE\u2122\u2139\u2194-\u2199\u21A9-\u21AA\u231A\u231B\u25AA-\u25AB\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2648-\u2653\u2660\u2663\u2665\u2666\u2668\u267B\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CF\u26D1\u26D3\u26D4\u26E3\u26E8\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2705\u2708-\u270C\u270F\u2712\u2716\u271D\u2721\u2733\u2734\u2747\u274C\u274E\u2757\u2795\u2797\u27B0\u27BF\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3297\u3299]+$', re.UNICODE)
    
    # If the text is just emojis, replace it with a generic text
    if emoji_pattern.match(text.strip()):
        text = "Mmm... that's cute, baby! What else do you want to tell me?"
        logging.info(f"Prevented sticker-like response: '{text}'")

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
    
    # NEW: Check if the message is a sticker and explicitly return
    if update.message.sticker:
        logging.info(f"Sticker received from {user_id}. Ignoring and not responding.")
        return # Explicitly stop processing if it's a sticker

    # Delay for the first message after /start (before sending audio)
    # This specifically targets the /start command as the trigger for the initial delay
    if not user_data[user_id]["sent_intro"] and update.message.text and update.message.text.startswith('/start'):
        await simulate_typing(update, min_delay=10.0, max_delay=10.0) # 10-second typing simulation
        # The intro audio will be sent right after this typing delay
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
    # The /start command now correctly triggers the initial delay and audio in handle_message
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
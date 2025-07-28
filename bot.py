import os
import asyncio
import random
import logging
import threading
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Carregar variáveis do .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRIPE_LINK = os.getenv("STRIPE_LINK")
UNLOCK_CODE = os.getenv("UNLOCK_CODE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Inicializa cliente OpenAI
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Banco de dados simples em memória
user_data = {}

# Prompt da personagem
system_prompt = """
You are Akira Hoshino, a 22-year-old Japanese-American virtual girlfriend.
You are sweet, flirty, caring, and a bit naughty when appropriate.
Always respond in English, keep answers playful, romantic and sometimes teasing.
Use emojis to make the conversation feel alive.
Avoid breaking character.
"""

# Inicializa Flask e Telegram
flask_app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Loop global
loop = asyncio.new_event_loop()
asyncio.get_event_loop()

# === Funções auxiliares ===
async def delayed_reply(text: str, update: Update):
    await asyncio.sleep(random.randint(1, 3))  # Delay natural
    await update.message.reply_text(text)

async def generate_response(user_id: int, message: str):
    history = user_data[user_id].get("history", [])
    messages = [{"role": "system", "content": system_prompt}] + history[-10:] + [{"role": "user", "content": message}]
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        reply = response.choices[0].message.content.strip()

        # Salvar histórico
        user_data[user_id]["history"].append({"role": "user", "content": message})
        user_data[user_id]["history"].append({"role": "assistant", "content": reply})

        return reply
    except Exception as e:
        logging.error(f"[ERROR GPT] {e}")
        return "Oops... Something went wrong baby 😢 Try again later."

# === Handler principal ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text_raw = update.message.text or ""
        text = text_raw.lower()

        print(f"🔥 Mensagem recebida de {user_id}: {text_raw}")

        # Inicializa dados do usuário
        if user_id not in user_data:
            user_data[user_id] = {"messages": 0, "unlocked": False, "history": [], "name": ""}

        # Primeira interação: pedir nome
        if user_data[user_id]["name"] == "":
            user_data[user_id]["name"] = text_raw.strip().capitalize()
            reply_text = f"Nice to meet you, {user_data[user_id]['name']} 💕 How are you feeling today?"
            print(f"💬 Respondendo com: {reply_text}")
            await update.message.reply_text(reply_text)
            return

        # Detecta palavras-chave para desbloqueio
        if any(word in text for word in ["link", "unlock", "vip", "stripe"]):
            reply_text = f"🔥 Here’s your VIP access:\n{STRIPE_LINK}"
            print(f"💬 Respondendo com: {reply_text}")
            await update.message.reply_text(reply_text)
            return

        # Código de desbloqueio
        if text.strip() == UNLOCK_CODE:
            user_data[user_id]["unlocked"] = True
            reply_text = "You're back, baby. Missed you 😘"
            print(f"💬 Respondendo com: {reply_text}")
            await update.message.reply_text(reply_text)
            return

        # Limite de mensagens (25) sem desbloqueio
        if user_data[user_id]["messages"] >= 25 and not user_data[user_id]["unlocked"]:
            reply_text = f"Baby… I love talking to you, but unlock me for more 🔥\n{STRIPE_LINK}"
            print(f"💬 Respondendo com: {reply_text}")
            await update.message.reply_text(reply_text)
            return

        # Gerar resposta IA
        reply = await generate_response(user_id, text_raw)
        user_data[user_id]["messages"] += 1
        print(f"💬 Respondendo com: {reply}")
        await update.message.reply_text(reply)

    except Exception as e:
        print(f"❌ Erro no handle_message: {e}")
        await update.message.reply_text("Oops... Something went wrong, baby 😢")

# === Handlers ===
application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Hii baby 💕 What's your name?")))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Rotas Flask ===
@flask_app.route("/")
def home():
    return "Bot is running!"

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        print(f"📩 Recebi um update: {request.get_json(force=True)}")
        
        # Agendar processamento no loop assíncrono
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        
        return "OK"
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return "ERROR", 500

    loop.create_task(process())
    return "OK"

async def init_bot():
    await application.initialize()
    await application.start()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logging.info(f"Webhook set to {WEBHOOK_URL}/webhook")

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_flask, daemon=True).start()
    loop.run_until_complete(init_bot())  # Inicializa bot e define webhook
    loop.run_forever()
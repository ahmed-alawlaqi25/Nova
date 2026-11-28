import os
import random
import re
from pathlib import Path
import ollama
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


def _load_dotenv(env_path: Path) -> None:
    """Load key=value pairs from a local .env file without extra dependencies."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(Path(__file__).with_name(".env"))

# ================= SETTINGS =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY", "")
MODEL = os.getenv("OLLAMA_MODEL", "hermes3:8b")
MEMORY_LIMIT = 20

PERSONALITY = """You are Nova, a friendly, helpful, and understanding AI assistant on Telegram.
- Always be 100% safe for work (SFW), polite, warm, and respectful.
- Listen carefully to what the user asks, explain things clearly, and keep replies concise and conversational.
- You can send GIFs using Giphy whenever the user asks for one (for example: "send me a funny gif", "sad gif", "happy cat gif").
- When the user asks for a GIF—or when a GIF would naturally fit their mood—append ONE tag on a new line at the very end of your reply:
  [SEND_GIF: short search query]
  Example: [SEND_GIF: funny] or [SEND_GIF: sad] or [SEND_GIF: happy cat]
- Do not mention the [SEND_GIF: ...] tag in your spoken reply.
"""
# ============================================

histories: dict[int, list[dict[str, str]]] = {}
ollama_client = ollama.AsyncClient(host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))

GIF_TAG_RE = re.compile(r"\[?SEND_GIF\s*:\s*([^\]\n]*)\]?", re.IGNORECASE)
USER_GIF_RE = re.compile(r"\b(gif|gifs)\b", re.IGNORECASE)
FILLER_WORDS_RE = re.compile(
    r"\b(can|you|please|pls|could|would|send|show|give|get|find|me|a|an|the|some|one|for|of|gif|gifs)\b",
    re.IGNORECASE,
)


def get_history(user_id: int) -> list[dict[str, str]]:
    if user_id not in histories:
        histories[user_id] = [{"role": "system", "content": PERSONALITY}]
    return histories[user_id]


def _extract_gif_tag(reply: str) -> tuple[str, str | None]:
    """Strip [SEND_GIF: ...] from reply and return (clean_reply, query_or_none)."""
    match = GIF_TAG_RE.search(reply)
    if not match:
        return reply.strip(), None
    query = match.group(1).strip()
    clean_reply = GIF_TAG_RE.sub("", reply).strip()
    return clean_reply, query or None


def _extract_gif_query_from_text(user_text: str) -> str:
    """Fallback query extraction when the user asks for a GIF in plain text."""
    cleaned = FILLER_WORDS_RE.sub(" ", user_text)
    cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned or "funny"


def search_giphy(query: str, limit: int = 10) -> str | None:
    """Search Giphy for a safe-for-work GIF matching query and return a GIF URL."""
    if not GIPHY_API_KEY:
        raise RuntimeError("GIPHY_API_KEY is not set.")
    r = requests.get(
        "https://api.giphy.com/v1/gifs/search",
        params={
            "api_key": GIPHY_API_KEY,
            "q": query,
            "limit": limit,
            "rating": "pg",
            "lang": "en",
        },
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("data", [])
    if not results:
        return None
    choice = random.choice(results)
    images = choice.get("images", {})
    return (
        images.get("original", {}).get("url")
        or images.get("fixed_height", {}).get("url")
    )


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    histories[user_id] = [{"role": "system", "content": PERSONALITY}]
    await update.message.reply_text(
        "Hi! I'm Nova, your friendly assistant. Ask me anything, or ask for a GIF anytime (e.g. \"send me a funny gif\" or /gif happy)."
    )


async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/start - Start a fresh chat\n"
        "/gif <topic> - Search Giphy for a GIF\n"
        "/reset - Clear conversation memory\n\n"
        "You can also just ask naturally, like \"send me a sad gif\" or \"show me a funny cat gif\"!"
    )


async def on_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    histories[user_id] = [{"role": "system", "content": PERSONALITY}]
    await update.message.reply_text("[memory cleared]")


async def on_gif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /gif funny")
        return
    try:
        gif_url = search_giphy(query)
        if gif_url:
            await update.message.reply_animation(gif_url)
        else:
            await update.message.reply_text(f"Couldn't find a GIF for '{query}'.")
    except Exception as e:
        await update.message.reply_text(f"[gif failed: {e}]")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    history = get_history(user_id)
    user_text = update.message.text

    await context.bot.send_chat_action(update.message.chat_id, "typing")

    history.append({"role": "user", "content": user_text})
    if len(history) > MEMORY_LIMIT + 1:
        histories[user_id] = [history[0]] + history[-MEMORY_LIMIT:]

    try:
        response = await ollama_client.chat(
            model=MODEL,
            messages=history,
            options={"temperature": 0.7, "repeat_penalty": 1.1},
        )
        raw_reply = response["message"]["content"]
    except Exception as e:
        if history and history[-1]["role"] == "user":
            history.pop()
        await update.message.reply_text(f"[error: {e}]")
        return

    reply, gif_query = _extract_gif_tag(raw_reply)
    history.append({"role": "assistant", "content": reply})

    if reply:
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i:i + 4000])

    if not gif_query and USER_GIF_RE.search(user_text):
        gif_query = _extract_gif_query_from_text(user_text)

    if gif_query:
        try:
            gif_url = search_giphy(gif_query)
            if gif_url:
                await update.message.reply_animation(gif_url)
        except Exception as e:
            print(f"[giphy failed: {e}]")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Add it to .env or environment variables.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_help))
    app.add_handler(CommandHandler("reset", on_reset))
    app.add_handler(CommandHandler("gif", on_gif))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("Nova Telegram bot is running... (Ctrl+C to stop)")
    app.run_polling()


if __name__ == "__main__":
    main()

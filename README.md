# Nova

A local Python AI chat assistant powered by [Ollama](https://ollama.com/), with both a streaming terminal CLI and a Telegram bot interface.

## Features

- **Local LLM via Ollama** — Runs locally against Ollama (`http://127.0.0.1:11434`), defaulting to `hermes3:8b`.
- **Terminal CLI (`agent.py`)**
  - Streaming chat responses with in-memory conversation history.
  - Commands: `/gif <search>` (Tenor API), `/reset`, `/quit`.
- **Telegram Bot (`nova_tg.py`)**
  - Asynchronous bot built with `python-telegram-bot` and `ollama.AsyncClient`.
  - Friendly, SFW assistant persona with per-user conversation memory (last 20 messages).
  - GIF support via the Giphy API (`rating="pg"`): explicit `/gif <topic>` command as well as automatic GIF replies triggered by natural-language requests or `[SEND_GIF: <query>]` tags.
  - Built-in `.env` loader with no extra dependency required.

## Project Structure

```text
.
├── agent.py        # Terminal chat agent
├── nova_tg.py      # Telegram bot
├── .env.example    # Environment variable template
├── .gitignore      # Git ignore rules
└── Dockerfile      # Placeholder for containerization
```

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally
- The default model pulled (or any other Ollama model of your choice):

```bash
ollama pull hermes3:8b
```

## Installation

Install the required Python packages:

```bash
pip install ollama requests python-telegram-bot
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
BOT_TOKEN=your_telegram_bot_token_here
GIPHY_API_KEY=your_giphy_api_key_here
OLLAMA_MODEL=hermes3:8b
```

- `BOT_TOKEN`: Telegram bot token from [@BotFather](https://t.me/BotFather) (required for `nova_tg.py`).
- `GIPHY_API_KEY`: Giphy API key for GIF search in Telegram (optional; required for `/gif` and auto-GIFs).
- `OLLAMA_MODEL`: Ollama model name used by `nova_tg.py` (defaults to `hermes3:8b`).

> **Note:** To enable `/gif` in the terminal agent (`agent.py`), set `TENOR_API_KEY` directly in `agent.py`.

## Usage

### Terminal Agent

```bash
python agent.py
```

Available commands:
- `/gif <search>` — Search Tenor for GIF links
- `/reset` — Clear conversation history
- `/quit` — Exit the chat

### Telegram Bot

Make sure Ollama is running, then start the bot:

```bash
python nova_tg.py
```

Available commands:
- `/start` — Start a fresh conversation
- `/help` — Show available commands
- `/gif <topic>` — Send a SFW GIF from Giphy
- `/reset` — Clear your conversation memory

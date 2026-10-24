# 📄 Samjan

> **Samjan** (સમજણ / समझ) means *understanding* in Gujarati and Hindi.

Upload a photo of any official letter, electricity bill, government notice or form.
Get a clear explanation — **in Gujarati, Hindi or English** — in seconds.
Powered by the open-weight **Gemma 4** model, running through the Gemini API.

---

## ✨ What it does

| Step | What happens |
|------|-------------|
| 1 | You upload a photo (PNG / JPG) of a document |
| 2 | You pick a language and optionally ask a question |
| 3 | Gemma 4 reads the image and follows the rules in `skills.md` |
| 4 | You get a structured answer: what it is, key details, what to do, what to watch out for |

---

## 🚀 Quick start

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR-USERNAME/Samjan.git
cd Samjan

# 2. Create a virtual environment
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
# .\venv\Scripts\Activate.ps1  # Windows PowerShell
# source venv/bin/activate      # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env
# Get a free key at https://aistudio.google.com

# 5. Run the app
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 🔑 Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Your Gemini API key |
| `GEMMA_MODEL` | No | `gemma-4-26b-a4b-it` | Override the Gemma 4 model name |

Valid model names on the Gemini API: `gemma-4-26b-a4b-it`, `gemma-4-31b-it`.

---

## 🧠 Open-weight model

This project uses **Gemma 4**, an open-weight model published by Google DeepMind.
The model weights are openly available, which means no vendor lock-in, reproducible
results, and the ability to self-host (e.g. via Ollama) if needed.

The assistant behaviour is defined in `skills.md` — a plain-text, human-readable
skill file you can edit without touching any Python code.

---

## 📁 Project layout

```
Samjan/
├── app.py           # Streamlit UI + Gemini API call
├── skills.md        # Agent skill: rules and output format for Gemma 4
├── requirements.txt
├── .env             # NOT committed — holds GEMINI_API_KEY
├── .gitignore
├── LICENSE          # MIT
└── README.md
```

---

## ⚠️ Disclaimer

This app explains what a document says. It does **not** give legal or financial advice.
Always verify important details with the sender or an official office.

---

## 📜 License

MIT — see [LICENSE](LICENSE).

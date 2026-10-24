import os
import io
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response
from google import genai
from PIL import Image, ImageDraw

load_dotenv(Path(__file__).with_name(".env"))

MODEL = os.environ.get("GEMMA_MODEL", "models/gemma-4-26b-a4b-it")
API_KEY = os.environ.get("GEMINI_API_KEY")
SKILL = Path(__file__).with_name("skills.md").read_text(encoding="utf-8")

app = Flask(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _call_model(contents: list) -> str:
    client = genai.Client(api_key=API_KEY)
    resp = client.models.generate_content(model=MODEL, contents=contents)
    return resp.text or ""


def _parse_structured(raw: str) -> dict:
    """Extract a JSON object from the model response robustly."""
    # Strip markdown fences if present
    clean = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    # Find the outermost { … }
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(clean[start:end])
        except json.JSONDecodeError:
            pass
    # Fallback: return raw text as explanation only
    return {
        "type": "Unknown",
        "amount": "N/A",
        "deadline": "N/A",
        "deadline_display": "N/A",
        "scam_risk": "low",
        "scam_reasons": ["Could not parse structured response."],
        "explanation": raw,
    }


def _make_sample_img() -> Image.Image:
    img = Image.new("RGB", (600, 420), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    lines = [
        "ELECTRICITY BILL",
        "",
        "Consumer Name : Ramesh Patel",
        "Account No    : 1234-5678",
        "Bill Date     : 01-Oct-2026",
        "Due Date      : 20-Oct-2026",
        "",
        "Units consumed: 210 kWh",
        "Amount Due    : Rs. 1,470.00",
        "",
        "Pay before due date to avoid a Rs. 50 late fee.",
        "Pay at authorised centre or online at ebill.gov.in",
    ]
    y = 30
    for line in lines:
        draw.text((40, y), line, fill=(20, 20, 20))
        y += 28
    return img


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", has_key=bool(API_KEY))


@app.route("/sample")
def sample():
    img = _make_sample_img()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/explain", methods=["POST"])
def explain():
    if not API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set. Add it to .env and restart."}), 500

    lang = request.form.get("lang", "English")
    question = request.form.get("question", "").strip()
    file = request.files.get("image")

    if not file:
        return jsonify({"error": "No image uploaded."}), 400

    try:
        image = Image.open(file.stream).convert("RGB")
        image.thumbnail((1600, 1600))
    except Exception:
        return jsonify({"error": "Could not read the image. Upload a clear PNG or JPG."}), 400

    prompt = (
        f"{SKILL}\n\n"
        f"Write the explanation section in {lang}.\n"
        + (f"The user also asks: {question}\n" if question else "")
        + "Now analyse the document in the attached image and return the JSON object."
    )

    try:
        raw = _call_model([image, prompt])
        data = _parse_structured(raw)
        return jsonify(data)
    except Exception as e:
        err = str(e)
        if "401" in err or "API_KEY" in err:
            return jsonify({"error": "Invalid API key. Check your .env file."}), 401
        if "429" in err or "quota" in err.lower():
            return jsonify({"error": "Rate limit reached. Wait a moment and try again."}), 429
        return jsonify({"error": f"Something went wrong: {err}"}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """Follow-up questions about the already-explained document."""
    if not API_KEY:
        return jsonify({"error": "API key not set."}), 500

    data = request.get_json()
    lang = data.get("lang", "English")
    context = data.get("context", "")   # explanation text from first call
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "No question provided."}), 400

    prompt = (
        f"You are a helpful document assistant. Here is an explanation of a document "
        f"that was already shown to the user:\n\n{context}\n\n"
        f"The user now asks (answer in {lang}, keep it short and simple):\n{question}"
    )

    try:
        answer = _call_model([prompt])
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ics", methods=["POST"])
def ics():
    """Return an .ics calendar file for the document deadline."""
    data = request.get_json()
    deadline_str = data.get("deadline", "")
    doc_type = data.get("type", "Document")
    amount = data.get("amount", "")

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    reminder_day = deadline - timedelta(days=1)
    fmt = "%Y%m%d"
    summary = f"Pay {doc_type}" + (f" – {amount}" if amount and amount != "N/A" else "")

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Samjan//Document Reminder//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{reminder_day.strftime(fmt)}\r\n"
        f"DTEND;VALUE=DATE:{deadline.strftime(fmt)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:Reminder: pay before {deadline.strftime('%d %B %Y')}\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT0S\r\n"
        "ACTION:DISPLAY\r\n"
        f"DESCRIPTION:{summary}\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=reminder.ics"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)

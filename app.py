import os
import io
import json
import re
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response, session
from google import genai
from PIL import Image, ImageDraw
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv(Path(__file__).with_name(".env"))

MODEL = os.environ.get("GEMMA_MODEL", "models/gemma-4-26b-a4b-it")
API_KEY = os.environ.get("GEMINI_API_KEY")
SKILL = Path(__file__).with_name("skills.md").read_text(encoding="utf-8")
DB_PATH = Path(__file__).with_name("samjan.db")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "samjan-session-secret-key-39184")


# ── database setup ─────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                doc_type TEXT,
                amount TEXT,
                deadline TEXT,
                deadline_display TEXT,
                scam_risk TEXT,
                scam_reasons TEXT,
                explanation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        conn.commit()


init_db()


# ── helpers ────────────────────────────────────────────────────────────────────

def _call_model(contents: list, retries: int = 3) -> str:
    """Call Gemma 4 model with automatic retry on transient Google 500/503 errors."""
    client = genai.Client(api_key=API_KEY)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.models.generate_content(model=MODEL, contents=contents)
            return resp.text or ""
        except Exception as e:
            last_err = e
            err_str = str(e)
            if attempt < retries and ("500" in err_str or "503" in err_str or "INTERNAL" in err_str):
                time.sleep(1.5 * attempt)
                continue
            raise last_err


def _parse_structured(raw: str) -> dict:
    """Extract a JSON object from the model response robustly."""
    clean = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    start = clean.find("{")
    end = clean.rfind("}") + 1
    parsed = {}
    if start != -1 and end > start:
        try:
            parsed = json.loads(clean[start:end])
        except json.JSONDecodeError:
            pass

    if isinstance(parsed, dict) and parsed:
        doc_type = parsed.get("type") or parsed.get("document_type") or parsed.get("title") or "Document"
        amount = parsed.get("amount") or parsed.get("amount_due") or parsed.get("total") or "N/A"
        deadline = parsed.get("deadline") or parsed.get("due_date") or "N/A"
        deadline_display = parsed.get("deadline_display") or deadline
        scam_risk = parsed.get("scam_risk") or parsed.get("risk") or "low"
        scam_reasons = parsed.get("scam_reasons") or parsed.get("reasons") or []
        if isinstance(scam_reasons, str):
            scam_reasons = [scam_reasons]
        
        explanation = parsed.get("explanation")
        if not explanation:
            # Reconstruct explanation from keys if model split them
            explanation = "\n\n".join(f"**{k}:**\n{v}" for k, v in parsed.items() if k not in ["type", "amount", "deadline", "deadline_display", "scam_risk", "scam_reasons"])
        if not explanation:
            explanation = raw

        return {
            "type": doc_type,
            "amount": amount,
            "deadline": deadline,
            "deadline_display": deadline_display,
            "scam_risk": scam_risk,
            "scam_reasons": scam_reasons,
            "explanation": explanation,
        }

    return {
        "type": "Document",
        "amount": "N/A",
        "deadline": "N/A",
        "deadline_display": "N/A",
        "scam_risk": "low",
        "scam_reasons": ["Automated format fallback"],
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


# ── auth routes ────────────────────────────────────────────────────────────────

@app.route("/auth/me")
def auth_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"logged_in": False})
    return jsonify({
        "logged_in": True,
        "user": {"id": user_id, "username": session.get("username")}
    })


@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if not password or len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters."}), 400

    hashed = generate_password_hash(password)
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hashed),
            )
            conn.commit()
            user_id = cursor.lastrowid
            session["user_id"] = user_id
            session["username"] = username
            return jsonify({"success": True, "user": {"id": user_id, "username": username}})
    except sqlite3.IntegrityError:
        return jsonify({"error": "That username is already taken. Try another."}), 400


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Please enter both username and password."}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password."}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"success": True, "user": {"id": user["id"], "username": user["username"]}})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


# ── document history routes ────────────────────────────────────────────────────

@app.route("/history", methods=["GET"])
def get_history():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Please sign in to view your saved history."}), 401

    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, doc_type, amount, deadline, deadline_display, scam_risk, created_at
            FROM documents
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)).fetchall()

    items = [
        {
            "id": r["id"],
            "doc_type": r["doc_type"],
            "amount": r["amount"],
            "deadline": r["deadline"],
            "deadline_display": r["deadline_display"],
            "scam_risk": r["scam_risk"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"documents": items})


@app.route("/history/<int:doc_id>", methods=["GET"])
def get_history_item(doc_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Please sign in."}), 401

    with get_db() as conn:
        row = conn.execute("""
            SELECT id, doc_type, amount, deadline, deadline_display, scam_risk, scam_reasons, explanation, created_at
            FROM documents
            WHERE id = ? AND user_id = ?
        """, (doc_id, user_id)).fetchone()

    if not row:
        return jsonify({"error": "Document not found."}), 404

    try:
        reasons = json.loads(row["scam_reasons"]) if row["scam_reasons"] else []
    except Exception:
        reasons = []

    return jsonify({
        "id": row["id"],
        "type": row["doc_type"],
        "amount": row["amount"],
        "deadline": row["deadline"],
        "deadline_display": row["deadline_display"],
        "scam_risk": row["scam_risk"],
        "scam_reasons": reasons,
        "explanation": row["explanation"],
        "created_at": row["created_at"],
    })


@app.route("/history/<int:doc_id>", methods=["DELETE"])
def delete_history_item(doc_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Please sign in."}), 401

    with get_db() as conn:
        conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
        conn.commit()

    return jsonify({"success": True})


# ── core app routes ────────────────────────────────────────────────────────────

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

        # Save to database if user is logged in
        user_id = session.get("user_id")
        if user_id:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO documents (
                        user_id, doc_type, amount, deadline, deadline_display,
                        scam_risk, scam_reasons, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    data.get("type", "Document"),
                    data.get("amount", "N/A"),
                    data.get("deadline", "N/A"),
                    data.get("deadline_display", "N/A"),
                    data.get("scam_risk", "low"),
                    json.dumps(data.get("scam_reasons", [])),
                    data.get("explanation", ""),
                ))
                conn.commit()
                data["saved_id"] = cursor.lastrowid

        return jsonify(data)
    except Exception as e:
        err = str(e)
        if "401" in err or "API_KEY" in err:
            return jsonify({"error": "Invalid API key. Check your .env file."}), 401
        if "429" in err or "quota" in err.lower():
            return jsonify({"error": "Rate limit reached. Wait a moment and try again."}), 429
        if "500" in err or "INTERNAL" in err:
            return jsonify({"error": "Google AI service had a temporary glitch. Please click 'Explain this document' again."}), 500
        return jsonify({"error": f"Something went wrong: {err}"}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """Follow-up questions about the already-explained document."""
    if not API_KEY:
        return jsonify({"error": "API key not set."}), 500

    data = request.get_json() or {}
    lang = data.get("lang", "English")
    context = data.get("context", "")
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
    data = request.get_json() or {}
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

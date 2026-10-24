# Samjan

Samjan (સમજણ / समझ) translates to *understanding* in Gujarati and Hindi.

Samjan is a secure document verification and explanation platform. Users can upload scans or photographs of official letters, electricity bills, tax statements, and government notices to receive instant, plain-language explanations and fraud risk assessments in Gujarati, Hindi, or English.

The backend leverages Google DeepMind's open-weight Gemma 4 model via the Google GenAI SDK, with automated retry backoff, structured contract enforcement, and user document archiving.

---

## Architecture and Core Capabilities

- **Multilingual Document Intelligence:** Extracts classification, amounts, deadlines, and action items in Gujarati, Hindi, or English.
- **Fraud and Tampering Detection:** Evaluates document authenticity, flagging urgency markers, suspicious payment routing, non-standard seals, or mismatched credentials.
- **User Authentication and History:** Built-in session authentication backed by SQLite. Users can register and sign in to persist verified document records, review archived assessments, or remove records on demand.
- **Interactive Document Inquiries:** Users can pose follow-up questions about specific clauses or payment deadlines directly against the scanned record.
- **Calendar and Action Integration:** Generates RFC 5545 `.ics` calendar reminders for extracted deadlines, alongside text-to-speech accessibility and shareable verification digests.
- **Resilient Model Pipeline:** Integrates automatic exponential backoff retries for transient upstream API responses, coupled with schema normalization defined in `skills.md`.

---

## Prerequisites

- Python 3.10 or higher
- A Google Gemini API key with access to Gemma 4 models (obtainable at [Google AI Studio](https://aistudio.google.com))

---

## Installation and Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/Samjan.git
cd Samjan
```

### 2. Set Up a Virtual Environment

On Windows PowerShell:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMMA_MODEL=gemma-4-26b-a4b-it
SECRET_KEY=your_session_secret_key_here
```

### 5. Launch the Application

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your web browser.

---

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | None | API key used for Google GenAI model calls |
| `GEMMA_MODEL` | No | `gemma-4-26b-a4b-it` | Model identifier on the Gemini API |
| `SECRET_KEY` | No | `samjan-secure-default-key-change-in-prod` | Secret key for Flask encrypted session cookies |

---

## Project Structure

```
Samjan/
├── app.py              # Flask server, GenAI integration, SQLite auth & document routes
├── skills.md           # Model instruction contract and JSON extraction specification
├── templates/
│   └── index.html      # Responsive web console, auth modal, and history drawer
├── requirements.txt    # Python runtime dependencies
├── samjan.db           # Local SQLite database (auto-generated, git-ignored)
├── .env.example        # Reference environment variables
├── .gitignore
├── LICENSE
└── README.md
```

---

## Verification Logic and Skills Specification

The assistant's operational instructions, extraction schema, and fraud evaluation guidelines are codified in `skills.md`. This file defines:

1. **Extraction Fields:** Document type, due amount, deadline date, formatted display date, fraud risk level (`LOW`, `MEDIUM`, `HIGH`), and specific reasons.
2. **Translation Fidelity:** Rendering technical, municipal, and banking terms into clear, localized Gujarati, Hindi, or English without bureaucratic jargon.
3. **Safety Fallbacks:** Clear notices distinguishing automated analysis from certified legal or fiscal advice.

---

## Disclaimer

Samjan is an automated document interpretation and verification assistant. It does not provide formal legal, tax, or financial advisory services. Critical legal documents, high-value invoices, or government penalties should always be verified directly with the issuing authority.

---

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.

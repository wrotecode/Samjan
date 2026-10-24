
import os
import io
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image, ImageDraw, ImageFont

load_dotenv(Path(__file__).with_name(".env"))
# Gemma 4 models on the Gemini API: gemma-4-26b-a4b-it, gemma-4-31b-it
MODEL = os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")
API_KEY = os.environ.get("GEMINI_API_KEY")

SKILL = Path(__file__).with_name("skills.md").read_text(encoding="utf-8")


def make_sample_image() -> Image.Image:
    """Generate a simple fake electricity bill for demo purposes."""
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
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
        "Pay at any authorised centre or online at ebill.gov.in",
    ]
    y = 30
    for line in lines:
        draw.text((40, y), line, fill=(20, 20, 20))
        y += 28
    return img


st.set_page_config(page_title="Samjan")
st.title("📄 Samjan")
st.caption(
    "Photo of a letter, bill or form in. "
    "Simple explanation out, in your language. "
    "Powered by open-weight Gemma 4."
)

if not API_KEY:
    st.error(
        "**API key not found.** "
        "Create a `.env` file in the project folder with the line:\n\n"
        "```\nGEMINI_API_KEY=your_key_here\n```\n\n"
        "Then restart the app. Get a free key at [aistudio.google.com](https://aistudio.google.com)."
    )
    st.stop()

client = genai.Client(api_key=API_KEY)

lang = st.selectbox("Explain in", ["Gujarati", "Hindi", "English"])
img_file = st.file_uploader("Upload a photo of the document", type=["png", "jpg", "jpeg"])
question = st.text_input("Optional: ask something specific (e.g. 'How much do I owe?')")

# --- Sample image demo ---
if not img_file:
    if st.button("Try a sample electricity bill"):
        sample = make_sample_image()
        buf = io.BytesIO()
        sample.save(buf, format="PNG")
        buf.seek(0)
        st.session_state["sample_bytes"] = buf.getvalue()
        st.rerun()

if "sample_bytes" in st.session_state and not img_file:
    raw = st.session_state["sample_bytes"]
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    st.info("Using the built-in sample bill. Upload your own document above to analyse it.")
elif img_file:
    image = Image.open(img_file).convert("RGB")
    image.thumbnail((1600, 1600))
else:
    image = None

if image:
    st.image(image, use_container_width=True)

    if st.button("Explain this document", type="primary"):
        prompt = (
            f"{SKILL}\n\nWrite the entire answer in {lang}.\n"
            + (f"The user also asks: {question}\n" if question else "")
            + "Now explain the document in the attached image."
        )
        with st.spinner("Reading the document…"):
            try:
                resp = client.models.generate_content(
                    model=MODEL, contents=[image, prompt]
                )
                if not resp.text or resp.text.strip() == "":
                    st.warning(
                        "The model could not read the document. "
                        "Try a clearer photo with better lighting, "
                        "or make sure the text is not blurred."
                    )
                else:
                    st.markdown(resp.text)
                    st.caption(
                        "⚠️ AI can make mistakes. "
                        "Check important details with the sender or an official office."
                    )
            except Exception as e:
                err = str(e)
                if "API_KEY" in err or "401" in err:
                    st.error("Invalid API key. Check your `.env` file and restart.")
                elif "quota" in err.lower() or "429" in err:
                    st.error("Rate limit reached. Wait a moment and try again.")
                else:
                    st.error(f"Something went wrong: {err}")
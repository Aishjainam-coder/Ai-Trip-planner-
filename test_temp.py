import os
import json
import re
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ======================
# ENV + GEMINI CLIENT
# ======================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ======================
# SESSION CACHE
# ======================
if "api_cache" not in st.session_state:
    st.session_state.api_cache = {}

# ======================
# GEMINI ITINERARY
# ======================
def generate_itinerary(destination, budget, days, interests):
    cache_key = hashlib.md5(
        f"{destination}_{budget}_{days}_{','.join(sorted(interests))}".encode()
    ).hexdigest()

    if cache_key in st.session_state.api_cache:
        return st.session_state.api_cache[cache_key]

    # ---------- Fallback if API key missing ----------
    if not client:
        data = {
            "destination": destination,
            "days": days,
            "budget": budget,
            "interests": interests,
            "plan": [
                {"day": i + 1, "activities": ["City walk", "Local food experience"]}
                for i in range(days)
            ],
            "cost_breakdown": {
                "transport": {"flights": 300, "local_transport": 100},
                "food": {"breakfast": 40, "lunch": 70, "dinner": 90},
                "activities": {"tours": 150, "tickets": 80},
                "accommodation": {"hotel": 400},
            },
        }
        st.session_state.api_cache[cache_key] = data
        return data

    prompt = f"""
Return ONLY valid JSON. No markdown. No explanation.

Schema:
{{
  "destination": "{destination}",
  "days": {days},
  "budget": {budget},
  "interests": {json.dumps(interests)},
  "plan": [
    {{"day": 1, "activities": ["activity1", "activity2"]}}
  ],
  "cost_breakdown": {{
    "transport": {{"flights": 0, "local_transport": 0}},
    "food": {{"breakfast": 0, "lunch": 0, "dinner": 0}},
    "activities": {{"tours": 0, "tickets": 0}},
    "accommodation": {{"hotel": 0}}
  }}
}}
"""

    try:
        response = client.models.generate_content(
            model="models/gemini-1.5-pro",
            contents=prompt,
            config={
                "temperature": 0,
                "max_output_tokens": 2048,
                "response_mime_type": "application/json",
            },
        )

        raw = response.text.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                raise ValueError("No valid JSON found in Gemini response")
            data = json.loads(match.group())

        st.session_state.api_cache[cache_key] = data
        return data

    except Exception as e:
        return {
            "error": str(e),
            "raw_response": raw if "raw" in locals() else "",
        }

# ======================
# MAP
# ======================
def render_map(destination):
    html = f"""
    <iframe
        width="100%"
        height="400"
        frameborder="0"
        src="https://www.openstreetmap.org/export/embed.html?search={destination}">
    </iframe>
    """
    components.html(html, height=420)

# ======================
# PDF EXPORT
# ======================
def export_pdf(itinerary):
    filename = "itinerary.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Personalized Trip Itinerary", styles["Title"]))
    elements.append(Spacer(1, 12))

    info = f"""
    <b>Destination:</b> {itinerary['destination']}<br/>
    <b>Days:</b> {itinerary['days']}<br/>
    <b>Budget:</b> ${itinerary['budget']}<br/>
    <b>Interests:</b> {', '.join(itinerary['interests'])}
    """
    elements.append(Paragraph(info, styles["Normal"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Daily Plan", styles["Heading2"]))
    for d in itinerary["plan"]:
        elements.append(Paragraph(f"Day {d['day']}", styles["Heading3"]))
        for act in d["activities"]:
            elements.append(Paragraph(f"- {act}", styles["Normal"]))
        elements.append(Spacer(1, 8))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Cost Breakdown", styles["Heading2"]))

    table_data = [["Category", "Item", "Cost ($)"]]
    for cat, items in itinerary["cost_breakdown"].items():
        for k, v in items.items():
            table_data.append([cat.title(), k.title(), f"${v}"])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))

    elements.append(table)
    doc.build(elements)
    return filename

# ======================
# STREAMLIT UI
# ======================
st.set_page_config(page_title="AI Trip Planner", layout="wide")
st.title("🧳 Personalized AI Trip Planner")

st.sidebar.header("Plan Your Trip")

destination = st.sidebar.text_input("Destination", "Paris")
budget = st.sidebar.number_input("Budget ($)", 100, 10000, 1000, 100)
days = st.sidebar.slider("Duration (days)", 1, 14, 3)

interests = st.sidebar.multiselect(
    "Interests",
    ["Food", "Heritage", "Nature", "Shopping", "Nightlife"],
    ["Food", "Heritage"],
)

if st.sidebar.button("🚀 Generate Itinerary"):
    with st.spinner("Generating itinerary..."):
        st.session_state.itinerary = generate_itinerary(
            destination, budget, days, interests
        )

# ======================
# DISPLAY
# ======================
if "itinerary" in st.session_state:
    data = st.session_state.itinerary

    if not isinstance(data, dict):
        st.error("Invalid response. Please regenerate.")
    elif "error" in data:
        st.error(data["error"])
        st.code(data.get("raw_response", ""))
    else:
        st.subheader(f"{days}-Day Trip to {destination}")

        for d in data["plan"]:
            st.markdown(f"### Day {d['day']}")
            for a in d["activities"]:
                st.write(f"- {a}")

        st.subheader("📍 Map")
        render_map(destination)

        if st.button("📄 Generate PDF"):
            pdf = export_pdf(data)
            with open(pdf, "rb") as f:
                st.download_button(
                    "Download PDF",
                    f,
                    file_name="itinerary.pdf",
                    mime="application/pdf",
                )

    if st.button("🛫 Book Trip (Demo)"):
        st.session_state["trip_booked"] = True

if st.session_state.get("trip_booked", False):
    st.success("✅ Your trip has been booked successfully! 🎉")

    if st.button("🔄 Plan Another Trip"):
        st.session_state.clear()

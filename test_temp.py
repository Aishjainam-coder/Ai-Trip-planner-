import os
import json
import re
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Try to import google.generativeai (newer SDK)
try:
    import google.generativeai as genai
    USE_NEW_SDK = True
except ImportError:
    # Fallback to older SDK
    try:
        from google import genai
        USE_NEW_SDK = False
    except ImportError:
        genai = None
        USE_NEW_SDK = None

from dotenv import load_dotenv

# ======================
# ENV + GEMINI CLIENT
# ======================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the client based on which SDK is available
if genai and GEMINI_API_KEY:
    if USE_NEW_SDK:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        # Old SDK
        pass

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

    # ---------- Fallback if API key missing or SDK not available ----------
    if not GEMINI_API_KEY or not genai:
        data = {
            "destination": destination,
            "days": days,
            "budget": budget,
            "interests": interests,
            "plan": [
                {
                    "day": i + 1, 
                    "activities": [
                        f"Morning: Explore famous landmarks in {destination}",
                        f"Afternoon: Visit local markets and try regional cuisine",
                        f"Evening: Cultural experience or relaxation"
                    ]
                }
                for i in range(days)
            ],
            "cost_breakdown": {
                "transport": {"flights": int(budget * 0.3), "local_transport": int(budget * 0.1)},
                "food": {"breakfast": int(budget * 0.1), "lunch": int(budget * 0.15), "dinner": int(budget * 0.15)},
                "activities": {"tours": int(budget * 0.1), "tickets": int(budget * 0.05)},
                "accommodation": {"hotel": int(budget * 0.05)},
            },
        }
        st.session_state.api_cache[cache_key] = data
        return data

    prompt = f"""
Create a {days}-day trip itinerary for {destination} with a budget of ${budget}.
Focus on these interests: {', '.join(interests)}.

Return ONLY valid JSON with this exact structure:
{{
  "destination": "{destination}",
  "days": {days},
  "budget": {budget},
  "interests": {json.dumps(interests)},
  "plan": [
    {{"day": 1, "activities": ["Morning: activity description", "Afternoon: activity description", "Evening: activity description"]}}
  ],
  "cost_breakdown": {{
    "transport": {{"flights": 0, "local_transport": 0}},
    "food": {{"breakfast": 0, "lunch": 0, "dinner": 0}},
    "activities": {{"tours": 0, "tickets": 0}},
    "accommodation": {{"hotel": 0}}
  }}
}}

Make the budget breakdown realistic and ensure all costs add up to approximately ${budget}.
"""

    try:
        if USE_NEW_SDK:
            # Using google.generativeai (newer, recommended SDK)
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 2048,
                }
            )
            raw = response.text.strip()
        else:
            # Using google.genai (older SDK)
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-1.5-pro",
                contents=prompt,
                config={
                    "temperature": 0.7,
                    "max_output_tokens": 2048,
                },
            )
            raw = response.text.strip()

        # Extract JSON from response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError("No valid JSON found in response")

        st.session_state.api_cache[cache_key] = data
        return data

    except Exception as e:
        return {
            "error": str(e),
            "suggestion": "Check your API key and library version. Run: pip install -U google-generativeai",
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

# Show SDK status
if not genai:
    st.error("⚠️ Google Generative AI library not found. Please install it: `pip install google-generativeai`")
elif not GEMINI_API_KEY:
    st.warning("⚠️ No GEMINI_API_KEY found. Using fallback data. Add your API key to .env file.")
else:
    sdk_type = "google-generativeai (recommended)" if USE_NEW_SDK else "google-genai (legacy)"
    st.sidebar.success(f"✅ Using {sdk_type}")

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
        st.error(f"❌ Error: {data['error']}")
        if "suggestion" in data:
            st.info(f"💡 {data['suggestion']}")
    else:
        st.subheader(f"{days}-Day Trip to {destination}")

        col1, col2 = st.columns([2, 1])
        
        with col1:
            for d in data["plan"]:
                with st.expander(f"📅 Day {d['day']}", expanded=True):
                    for a in d["activities"]:
                        st.write(f"• {a}")

        with col2:
            st.subheader("💰 Cost Breakdown")
            total = 0
            for cat, items in data["cost_breakdown"].items():
                cat_total = sum(items.values())
                total += cat_total
                st.write(f"**{cat.title()}:** ${cat_total}")
            st.write(f"**Total:** ${total}")

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
        st.rerun()

import os
import json
import re
import hashlib
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
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

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
    if not GEMINI_API_KEY:
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
Create a detailed {days}-day trip itinerary for {destination} with a budget of ${budget}.
Focus on these interests: {', '.join(interests)}.

Return ONLY valid JSON with this exact structure (no markdown, no code blocks):
{{
  "destination": "{destination}",
  "days": {days},
  "budget": {budget},
  "interests": {json.dumps(interests)},
  "plan": [
    {{"day": 1, "activities": ["Morning: detailed activity", "Afternoon: detailed activity", "Evening: detailed activity"]}}
  ],
  "cost_breakdown": {{
    "transport": {{"flights": 300, "local_transport": 50}},
    "food": {{"breakfast": 100, "lunch": 150, "dinner": 200}},
    "activities": {{"tours": 200, "tickets": 100}},
    "accommodation": {{"hotel": 300}}
  }}
}}

Make the costs realistic and ensure they sum to approximately ${budget}.
Include specific activity recommendations based on the selected interests.
"""

    try:
        # Use the correct new SDK method
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        
        raw = response.text.strip()
        
        # Remove markdown code blocks if present
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*$', '', raw)

        # Extract JSON from response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError("No valid JSON found in response")

        st.session_state.api_cache[cache_key] = data
        return data

    except Exception as e:
        error_msg = str(e)
        
        # Check for specific API errors
        if "API_KEY" in error_msg or "authentication" in error_msg.lower():
            suggestion = "Your API key may be invalid. Visit https://aistudio.google.com/app/apikey to get a new one."
        elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
            suggestion = "You may have exceeded your API quota. Check your usage at https://aistudio.google.com/"
        else:
            suggestion = "Try regenerating the itinerary or check your internet connection."
        
        return {
            "error": error_msg,
            "suggestion": suggestion,
        }

# ======================
# MAP
# ======================
def render_map(destination):
    # URL encode the destination
    encoded_dest = destination.replace(" ", "+")
    html = f"""
    <iframe
        width="100%"
        height="400"
        frameborder="0"
        style="border:0"
        src="https://www.openstreetmap.org/export/embed.html?bbox=-180,-90,180,90&layer=mapnik&marker=0,0"
        allowfullscreen>
    </iframe>
    <br/>
    <small><a href="https://www.openstreetmap.org/search?query={encoded_dest}" target="_blank">View larger map</a></small>
    """
    components.html(html, height=450)

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

# Show API status
if not GEMINI_API_KEY:
    st.warning("⚠️ No GEMINI_API_KEY found in .env file. Using demo mode with fallback data.")
    st.info("To use AI-powered itineraries, get an API key from https://aistudio.google.com/app/apikey")
else:
    st.sidebar.success("✅ Gemini API Connected")

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
    with st.spinner("✨ Creating your personalized itinerary..."):
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
            st.info(f"💡 Suggestion: {data['suggestion']}")
    else:
        st.success(f"✅ Your {days}-day trip to {destination} is ready!")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📅 Daily Itinerary")
            for d in data["plan"]:
                with st.expander(f"Day {d['day']}", expanded=True):
                    for a in d["activities"]:
                        st.write(f"• {a}")

        with col2:
            st.subheader("💰 Cost Breakdown")
            total = 0
            for cat, items in data["cost_breakdown"].items():
                cat_total = sum(items.values())
                total += cat_total
                with st.expander(f"{cat.title()}: ${cat_total}"):
                    for k, v in items.items():
                        st.write(f"• {k.title()}: ${v}")
            st.metric("Total Budget", f"${total}")

        st.markdown("---")
        
        st.subheader("📍 Location")
        render_map(destination)
        
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Generate PDF Report"):
                with st.spinner("Creating PDF..."):
                    pdf = export_pdf(data)
                    with open(pdf, "rb") as f:
                        st.download_button(
                            "📥 Download PDF",
                            f,
                            file_name="trip_itinerary.pdf",
                            mime="application/pdf",
                        )
        
        with col2:
            if st.button("🛫 Book Trip (Demo)"):
                st.session_state["trip_booked"] = True

if st.session_state.get("trip_booked", False):
    st.balloons()
    st.success("✅ Your trip has been booked successfully! 🎉")
    
    if st.button("🔄 Plan Another Trip"):
        st.session_state.clear()
        st.rerun()

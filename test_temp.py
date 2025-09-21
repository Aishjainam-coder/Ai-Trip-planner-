import os
import json
import streamlit as st
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


# =========================
# CONFIGURATION
# =========================
# Try reading from Streamlit secrets first (for Streamlit Cloud), otherwise from env vars
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# =========================
# HELPER FUNCTIONS
# =========================
def generate_itinerary(destination, budget, days, interests):
    """Generate itinerary using Google Gemini API."""
    if not GEMINI_API_KEY:
        # Mock response for demo mode
        return {
            "destination": destination,
            "days": days,
            "budget": budget,
            "interests": interests,
            "plan": [
                {"day": 1, "activities": ["Visit heritage site", "Local food tour"]},
                {"day": 2, "activities": ["Nightlife exploration", "City walk"]},
            ],
            "cost_breakdown": {
                "transport": {"flights": 200, "local_transport": 50},
                "food": {"breakfast": 30, "lunch": 50, "dinner": 70},
                "activities": {"tours": 100, "tickets": 50},
                "accommodation": {"hotel": 300}
            }
        }

    prompt = f"""
    Create a {days}-day travel itinerary for {destination}.
    Budget: {budget}
    Interests: {', '.join(interests)}
    Provide a valid JSON object with the following keys:
    - destination (string)
    - days (number)
    - budget (number)
    - interests (list of strings)
    - plan (list of objects: each has 'day' and 'activities')
    - cost_breakdown (object with nested details like transport (flights, local_transport), food (breakfast, lunch, dinner), activities (tickets, tours), accommodation (hotel, others))
    Ensure the output is ONLY valid JSON without extra text or formatting.
    """

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    try:
        text_content = response.text.strip()

        # Handle JSON inside code blocks
        if text_content.startswith("```"):
            json_start = text_content.find("{")
            json_end = text_content.rfind("}") + 1
            json_string = text_content[json_start:json_end]
        else:
            json_string = text_content

        return json.loads(json_string)
    except Exception as e:
        return {"error": f"Invalid JSON response from Gemini: {e}"}


def render_map(destination, activities=None):
    """Embed Google Maps iframe with optional activities."""
    if not MAPS_API_KEY:
        st.info("Google Maps API key not configured. Showing demo mode.")
        st.image("https://via.placeholder.com/600x400.png?text=Map+Preview")
        return

    # Default to destination
    query = destination.replace(" ", "+")

    # If activities are provided, show the first one along with destination
    if activities:
        first_activity = activities[0].replace(" ", "+")
        query = f"{destination.replace(' ', '+')}+{first_activity}"

    map_url = (
        f"https://www.google.com/maps/embed/v1/search?key={MAPS_API_KEY}&q={query}"
    )
    st.markdown(
        f'<iframe src="{map_url}" width="700" height="450" style="border:0;" allowfullscreen="" loading="lazy"></iframe>',
        unsafe_allow_html=True
    )

def export_pdf(itinerary, filename="itinerary.pdf"):
    """Export itinerary as a well-structured PDF file with auto-adjusted table cells."""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]

    # Title
    elements.append(Paragraph("🧳 Personalized Trip Itinerary", styles["Title"]))
    elements.append(Spacer(1, 20))

    # Trip details
    details = f"""
    <b>Destination:</b> {itinerary.get('destination', '')}<br/>
    <b>Days:</b> {itinerary.get('days', '')}<br/>
    <b>Budget:</b> ${itinerary.get('budget', '')}<br/>
    <b>Interests:</b> {', '.join(itinerary.get('interests', []))}
    """
    elements.append(Paragraph(details, styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Daily Plan
    elements.append(Paragraph("📅 Daily Itinerary", styles["Heading2"]))
    for day_plan in itinerary.get("plan", []):
        elements.append(Paragraph(f"<b>Day {day_plan['day']}</b>", styles["Heading3"]))
        for activity in day_plan["activities"]:
            elements.append(Paragraph(f"• {activity}", styles["Normal"]))
        elements.append(Spacer(1, 10))

    elements.append(Spacer(1, 20))

    # Cost Breakdown
    cost = itinerary.get("cost_breakdown", {})
    if cost:
        elements.append(Paragraph("💰 Detailed Cost Breakdown", styles["Heading2"]))

        # Use Paragraphs inside cells for auto text wrapping
        table_data = [[
            Paragraph("<b>Category</b>", normal_style),
            Paragraph("<b>Item</b>", normal_style),
            Paragraph("<b>Cost ($)</b>", normal_style),
        ]]

        for category, details in cost.items():
            if isinstance(details, dict):
                for item, value in details.items():
                    table_data.append([
                        Paragraph(category.title(), normal_style),
                        Paragraph(item.title(), normal_style),
                        Paragraph(f"${value}", normal_style)
                    ])
            else:
                table_data.append([
                    Paragraph(category.title(), normal_style),
                    Paragraph("Total", normal_style),
                    Paragraph(f"${details}", normal_style)
                ])

        # Table with flexible column widths
        table = Table(table_data, colWidths=["30%", "50%", "20%"])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(table)

    # Build PDF
    doc.build(elements)
    return filename


# =========================
# STREAMLIT UI
# =========================
# st.set_page_config(page_title="AI Trip Planner", layout="wide")
# st.title("🧳 Personalized AI Trip Planner")

# st.sidebar.header("Plan Your Trip")

# # Inputs
# destination = st.sidebar.text_input("Destination", "Paris")
# budget = st.sidebar.number_input("Budget ($)", min_value=100, value=1000, step=50)
# days = st.sidebar.slider("Duration (days)", 1, 14, 3)

# # Predefined interests
# default_interests = [
#     "Heritage", "Food", "Nightlife", "Adventure", "Shopping", "Nature",
#     "Photography", "Relaxation", "Music & Festivals", "Sports", "Technology"
# ]

# interests = st.sidebar.multiselect(
#     "Select Interests",
#     default_interests,
#     ["Food", "Heritage"]
# )

# # Custom interest input
# custom_interest = st.sidebar.text_input("Add Custom Interest")

# if custom_interest:
#     interests.append(custom_interest)

# if st.sidebar.button("Generate Itinerary"):
#     with st.spinner("Generating your personalized itinerary..."):
#         itinerary = generate_itinerary(destination, budget, days, interests)

#     if "error" in itinerary:
#         st.error(itinerary["error"])
#     else:
#         st.subheader(f"Your {days}-Day Trip to {destination}")

#         for day_plan in itinerary["plan"]:
#             st.markdown(f"### Day {day_plan['day']}")
#             for activity in day_plan["activities"]:
#                 st.write(f"- {activity}")

#         st.subheader("💰 Cost Breakdown")
#         cost = itinerary.get("cost_breakdown", {})
#         if cost:
#             for category, details in cost.items():
#                 st.markdown(f"**{category.title()}**")
#                 if isinstance(details, dict):
#                     for item, value in details.items():
#                         st.write(f"- {item.title()}: ${value}")
#                 else:
#                     st.write(f"- Total: ${details}")

#         st.subheader("📍 Map Preview")
#         # Show map using first day's activities (if available)
#         first_day_activities = itinerary["plan"][0]["activities"] if itinerary.get("plan") else None
#         render_map(destination, first_day_activities)

#         # Export PDF
#         if st.button("Generate PDF Itinerary"):
#             filename = export_pdf(itinerary)
#             with open(filename, "rb") as f:
#                 pdf_data = f.read()

#             st.download_button(
#                 label="📥 Download Itinerary as PDF",
#                 data=pdf_data,
#                 file_name="itinerary.pdf",
#                 mime="application/pdf"
#             )

#         # Booking demo
#         if st.button("Confirm Booking (Demo)"):
#             st.success("✅ Your trip has been booked (demo mode). Safe travels!")


st.set_page_config(page_title="AI Trip Planner", layout="wide")
st.title("🧳 Personalized AI Trip Planner")

# --- Session State ---
if "itinerary" not in st.session_state:
    st.session_state.itinerary = None
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None
if "pdf_ready" not in st.session_state:
    st.session_state.pdf_ready = False

st.sidebar.header("Plan Your Trip")

# Inputs
destination = st.sidebar.text_input("Destination", "Paris")
budget = st.sidebar.number_input("Budget ($)", min_value=100, value=1000, step=50)
days = st.sidebar.slider("Duration (days)", 1, 14, 3)

# Predefined interests
default_interests = [
    "Heritage", "Food", "Nightlife", "Adventure", "Shopping", "Nature",
    "Photography", "Relaxation", "Music & Festivals", "Sports", "Technology"
]

interests = st.sidebar.multiselect(
    "Select Interests",
    default_interests,
    ["Food", "Heritage"]
)

# Custom interest input
custom_interest = st.sidebar.text_input("Add Custom Interest")
if custom_interest:
    interests.append(custom_interest)

# Generate itinerary
if st.sidebar.button("Generate Itinerary"):
    with st.spinner("Generating your personalized itinerary..."):
        st.session_state.itinerary = generate_itinerary(destination, budget, days, interests)
        st.session_state.pdf_ready = False
        st.session_state.pdf_data = None

# Show itinerary
if st.session_state.itinerary and not st.session_state.pdf_ready:
    itinerary = st.session_state.itinerary
    if "error" in itinerary:
        st.error(itinerary["error"])
    else:
        st.subheader(f"Your {days}-Day Trip to {destination}")

        for day_plan in itinerary["plan"]:
            st.markdown(f"### Day {day_plan['day']}")
            for activity in day_plan["activities"]:
                st.write(f"- {activity}")

        st.subheader("💰 Cost Breakdown")
        cost = itinerary.get("cost_breakdown", {})
        if cost:
            for category, details in cost.items():
                st.markdown(f"**{category.title()}**")
                if isinstance(details, dict):
                    for item, value in details.items():
                        st.write(f"- {item.title()}: ${value}")
                else:
                    st.write(f"- Total: ${details}")

        st.subheader("📍 Map Preview")
        first_day_activities = itinerary["plan"][0]["activities"] if itinerary.get("plan") else None
        render_map(destination, first_day_activities)

        # Export PDF
        if st.button("Generate PDF Itinerary"):
            filename = export_pdf(itinerary)
            with open(filename, "rb") as f:
                st.session_state.pdf_data = f.read()
            st.session_state.pdf_ready = True

# Show only download button after PDF is ready
if st.session_state.pdf_ready and st.session_state.pdf_data:
    st.success("✅ Your itinerary PDF is ready for download!")
    clear_after = st.download_button(
        label="📥 Download Itinerary as PDF",
        data=st.session_state.pdf_data,
        file_name="itinerary.pdf",
        mime="application/pdf"
    )

    # Book Trip Button
    if st.button("🛫 Book Trip (Demo)"):
        st.session_state["trip_booked"] = True

# Show confirmation message (persistent)
if st.session_state.get("trip_booked", False):
    st.success("✅ Your trip has been booked successfully! 🎉")

    # Optional: Button to reset everything
    if st.button("🔄 Plan Another Trip"):
        st.session_state.clear()

#     # After clicking, clear session state
#     if clear_after:
#         st.session_state.itinerary = None
#         st.session_state.pdf_data = None
#         st.session_state.pdf_ready = False

#     # Book Trip Button
#     if st.button("🛫 Book Trip (Demo)"):
#         st.session_state["trip_booked"] = True

# # Show confirmation message
# if st.session_state.get("trip_booked", False):
#     st.success("✅ Your trip has been booked successfully! 🎉")    

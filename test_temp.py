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
import folium
from streamlit_folium import st_folium
import requests
import random


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


def get_coordinates(location):
    """Get coordinates for a location using Nominatim API."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
        headers = {'User-Agent': 'TravelPlanner/1.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        return None, None
    except:
        return None, None

def create_impressive_map(destination, activities=None):
    """Create an impressive interactive map using Folium and OpenStreetMap."""
    
    # Get coordinates for destination
    dest_lat, dest_lon = get_coordinates(destination)
    
    if dest_lat is None or dest_lon is None:
        # Fallback coordinates for major cities
        fallback_coords = {
            'paris': (48.8566, 2.3522),
            'london': (51.5074, -0.1278),
            'new york': (40.7128, -74.0060),
            'tokyo': (35.6762, 139.6503),
            'mumbai': (19.0760, 72.8777),
            'delhi': (28.7041, 77.1025),
            'bangalore': (12.9716, 77.5946),
            'dubai': (25.2048, 55.2708),
            'singapore': (1.3521, 103.8198),
            'sydney': (-33.8688, 151.2093)
        }
        
        dest_lower = destination.lower()
        for city, coords in fallback_coords.items():
            if city in dest_lower:
                dest_lat, dest_lon = coords
                break
        else:
            # Default to Paris if no match
            dest_lat, dest_lon = (48.8566, 2.3522)
    
    # Create map with default tiles to avoid issues
    m = folium.Map(
        location=[dest_lat, dest_lon],
        zoom_start=12
    )
    
    # Add destination marker
    folium.Marker(
        [dest_lat, dest_lon],
        popup=f"<b>🎯 {destination}</b><br>Your destination!",
        tooltip=f"Destination: {destination}",
        icon=folium.Icon(color='red', icon='star')
    ).add_to(m)
    
    # Add activity markers if provided
    if activities:
        colors = ['blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue']
        
        for i, activity in enumerate(activities[:10]):  # Limit to 10 activities
            # Generate random coordinates around destination for demo
            offset_lat = random.uniform(-0.05, 0.05)
            offset_lon = random.uniform(-0.05, 0.05)
            activity_lat = dest_lat + offset_lat
            activity_lon = dest_lon + offset_lon
            
            color = colors[i % len(colors)]
            
            folium.Marker(
                [activity_lat, activity_lon],
                popup=f"<b>🎯 {activity}</b><br>Activity {i+1}",
                tooltip=activity,
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)
    
    # Add a circle around destination
    folium.CircleMarker(
        [dest_lat, dest_lon],
        radius=1000,
        popup=f"<b>{destination} Area</b>",
        color='red',
        fill=True,
        fillColor='red',
        fillOpacity=0.1
    ).add_to(m)
    
    return m

def render_map(destination, activities=None):
    """Render the impressive map using Folium."""
    st.markdown("### 🗺️ Interactive Map View")
    
    with st.spinner("Loading interactive map..."):
        map_obj = create_impressive_map(destination, activities)
        
        # Display the map with proper parameters
        map_data = st_folium(
            map_obj,
            width=800,
            height=500,
            returned_objects=[]
        )
    
    # Add some additional info
    st.info("🗺️ **Map Features:** Interactive markers, multiple tile layers, and satellite view available!")

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


st.set_page_config(page_title="AI Trip Planner", layout="wide", initial_sidebar_state="expanded")

# Add custom CSS for impressive styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 3rem;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.2rem;
        opacity: 0.9;
    }
    
    .stMetric {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .stButton > button {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    .stSelectbox > div > div {
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .stTextInput > div > div > input {
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .stSlider > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
    }
    
    .success-message {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .map-container {
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

# Main header
st.markdown("""
<div class="main-header">
    <h1>🧳 Personalized AI Trip Planner</h1>
    <p>Plan your perfect adventure with AI-powered recommendations</p>
</div>
""", unsafe_allow_html=True)

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

        # Create two columns for better layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🗺️ Interactive Map View")
            first_day_activities = itinerary["plan"][0]["activities"] if itinerary.get("plan") else None
            render_map(destination, first_day_activities)
        
        with col2:
            st.subheader("📍 Quick Info")
            st.metric("Destination", destination)
            st.metric("Duration", f"{days} days")
            st.metric("Budget", f"${budget}")
            
            if first_day_activities:
                st.subheader("🎯 Day 1 Activities")
                for i, activity in enumerate(first_day_activities[:5], 1):
                    st.write(f"{i}. {activity}")
                if len(first_day_activities) > 5:
                    st.write(f"... and {len(first_day_activities) - 5} more")

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
    st.markdown("""
    <div class="success-message">
        ✅ Your trip has been booked successfully! 🎉<br>
        <small>Check your email for confirmation details</small>
    </div>
    """, unsafe_allow_html=True)

    # Optional: Button to reset everything
    if st.button("🔄 Plan Another Trip"):
        st.session_state.clear()
        st.rerun()

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
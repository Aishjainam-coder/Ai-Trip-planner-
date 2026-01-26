import os
import json
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import time
import hashlib
from typing import Dict, Any


# =========================
# CONFIGURATION
# =========================
# Try reading from Streamlit secrets first (for Streamlit Cloud), otherwise from env vars
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Cache for API responses
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_response(cache_key: str):
    return None

# Simple in-memory cache
if 'api_cache' not in st.session_state:
    st.session_state.api_cache = {}

# =========================
# HELPER FUNCTIONS
# =========================
def generate_itinerary(destination, budget, days, interests):
    """Generate itinerary using Google Gemini API with caching and optimization."""
    # Create cache key
    cache_key = hashlib.md5(f"{destination}_{budget}_{days}_{','.join(sorted(interests))}".encode()).hexdigest()
    
    # Check cache first
    if cache_key in st.session_state.api_cache:
        return st.session_state.api_cache[cache_key]
    
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

    # Optimized prompt for faster response
    prompt = f"""Create a {days}-day travel itinerary for {destination}. Budget: ${budget}. Interests: {', '.join(interests)}.

Return ONLY valid JSON:
{{
  "destination": "{destination}",
  "days": {days},
  "budget": {budget},
  "interests": {json.dumps(interests)},
  "plan": [{{"day": 1, "activities": ["activity1", "activity2"]}}],
  "cost_breakdown": {{
    "transport": {{"flights": 0, "local_transport": 0}},
    "food": {{"breakfast": 0, "lunch": 0, "dinner": 0}},
    "activities": {{"tours": 0, "tickets": 0}},
    "accommodation": {{"hotel": 0}}
  }}
}}"""

    try:
        # Use faster model for better response time
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Configure generation parameters for speed
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        text_content = response.text.strip()

        # Handle JSON inside code blocks
        if text_content.startswith("```"):
            json_start = text_content.find("{")
            json_end = text_content.rfind("}") + 1
            json_string = text_content[json_start:json_end]
        else:
            json_string = text_content

        result = json.loads(json_string)
        
        # Cache the result
        st.session_state.api_cache[cache_key] = result
        return result
        
    except Exception as e:
        return {"error": f"Invalid JSON response from Gemini: {e}"}


def render_map(destination, activities=None):
    """Render interactive map using OpenStreetMap and Leaflet (free alternative)."""
    
    # Create a simple map using HTML and JavaScript with OpenStreetMap
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #map {{ height: 400px; width: 100%; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            // Initialize map
            var map = L.map('map').setView([0, 0], 2);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }}).addTo(map);
            
            // Geocode destination using Nominatim (free)
            var destination = "{destination}";
            var geocodeUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${{encodeURIComponent(destination)}}&limit=1`;
            
            fetch(geocodeUrl)
                .then(response => response.json())
                .then(data => {{
                    if (data && data.length > 0) {{
                        var lat = parseFloat(data[0].lat);
                        var lon = parseFloat(data[0].lon);
                        
                        // Set map view to destination
                        map.setView([lat, lon], 13);
                        
                        // Add marker for destination
                        var marker = L.marker([lat, lon]).addTo(map);
                        marker.bindPopup(`<b>${{destination}}</b>`).openPopup();
                        
                        // Add activities as additional markers if available
                        var activities = {json.dumps(activities) if activities else '[]'};
                        if (activities && activities.length > 0) {{
                            activities.forEach((activity, index) => {{
                                // Add small offset for multiple activities
                                var offsetLat = lat + (index * 0.01);
                                var offsetLon = lon + (index * 0.01);
                                var activityMarker = L.marker([offsetLat, offsetLon]).addTo(map);
                                activityMarker.bindPopup(`<b>Activity:</b> ${{activity}}`);
                            }});
                        }}
                    }}
                }})
                .catch(error => {{
                    console.error('Geocoding error:', error);
                    // Fallback to a default location
                    map.setView([40.7128, -74.0060], 10); // New York as fallback
                }});
        </script>
    </body>
    </html>
    """
    
    components.html(map_html, height=450)

def render_simple_map(destination, activities=None):
    """Fallback simple map using static image from OpenStreetMap."""
    # Use OpenStreetMap static image as fallback
    query = destination.replace(" ", "+")
    if activities:
        query += f"+{activities[0].replace(' ', '+')}"
    
    map_url = f"https://www.openstreetmap.org/export/embed.html?bbox=-180,-90,180,90&layer=mapnik&marker=0,0&text={query}"
    
    st.markdown(f"""
    <div style="text-align: center; margin: 20px 0;">
        <h4>📍 Map View: {destination}</h4>
        <iframe 
            src="{map_url}" 
            width="100%" 
            height="400" 
            style="border: 1px solid #ddd; border-radius: 8px;"
            allowfullscreen>
        </iframe>
        <p style="font-size: 12px; color: #666; margin-top: 5px;">
            Interactive map powered by OpenStreetMap
        </p>
    </div>
    """, unsafe_allow_html=True)

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
if st.sidebar.button("🚀 Generate Itinerary", type="primary"):
    # Create progress bar for better UX
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Create cache key for status check
    cache_key = hashlib.md5(f"{destination}_{budget}_{days}_{','.join(sorted(interests))}".encode()).hexdigest()
    is_cached = cache_key in st.session_state.api_cache
    
    try:
        if is_cached:
            status_text.text("💾 Loading from cache...")
            progress_bar.progress(30)
        else:
            status_text.text("🔄 Initializing AI model...")
            progress_bar.progress(20)
            
            status_text.text("🤖 Generating personalized itinerary...")
            progress_bar.progress(50)
        
        start_time = time.time()
        st.session_state.itinerary = generate_itinerary(destination, budget, days, interests)
        end_time = time.time()
        
        progress_bar.progress(80)
        status_text.text("✅ Itinerary generated successfully!")
        progress_bar.progress(100)
        
        # Show performance metrics
        response_time = end_time - start_time
        cache_status = "💾 Cached" if is_cached else "🔄 Fresh"
        st.sidebar.success(f"⚡ Generated in {response_time:.2f} seconds {cache_status}")
        
        st.session_state.pdf_ready = False
        st.session_state.pdf_data = None
        
        # Clear progress indicators
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        
    except Exception as e:
        st.error(f"❌ Error generating itinerary: {e}")
        progress_bar.empty()
        status_text.empty()

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

        st.subheader("📍 Interactive Map")
        
        # Create tabs for different map views
        map_tab1, map_tab2 = st.tabs(["🗺️ Interactive Map", "📍 Simple Map"])
        
        with map_tab1:
            try:
                first_day_activities = itinerary["plan"][0]["activities"] if itinerary.get("plan") else None
                render_map(destination, first_day_activities)
            except Exception as e:
                st.warning(f"Interactive map failed to load: {e}")
                st.info("Falling back to simple map view...")
                render_simple_map(destination, first_day_activities)
        
        with map_tab2:
            first_day_activities = itinerary["plan"][0]["activities"] if itinerary.get("plan") else None
            render_simple_map(destination, first_day_activities)

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

from multiprocessing import Value
import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import hashlib
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Page config
st.set_page_config(
    page_title="WayzUp - Community Hazard Alert System",
    page_icon="🚨",
    layout="wide"
)

# Backend URL
BACKEND_URL = "http://127.0.0.1:5000"

# Simple user database (in production, use proper database)
USERS_DB = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "user1": hashlib.sha256("pass123".encode()).hexdigest()
}

# ============= GOOGLE MAPS API CONFIGURATION =============
# TO USE GOOGLE MAPS INSTEAD OF FOLIUM:
# 1. Get API key from: https://console.cloud.google.com/google/maps-apis
# 2. Enable "Maps JavaScript API" and "Geocoding API"
# 3. Uncomment line below and add your API key:

# GOOGLE_MAPS_API_KEY = "YOUR_API_KEY_HERE"

# 4. Install required package: pip install streamlit-js-eval
# 5. Replace Folium map code with Google Maps embed (see commented section below)
# ===========================================================

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'otp_data' not in st.session_state:
    st.session_state.otp_data = {}


class OTPSender:
    def __init__(self, sender_email: str, sender_password: str):
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        # Store OTPs in session state to persist between reruns
        if 'otp_store' not in st.session_state:
            st.session_state.otp_store = {}

    def generate_otp(self, length: int = 6) -> str:
        return ''.join(random.choices(string.digits, k=length))

    def send_otp(self, recipient_email: str, otp: str | None = None, expiry_minutes: int = 10):
        if otp is None:
            otp = self.generate_otp()

        try:
            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = recipient_email
            message["Subject"] = "Your OTP Verification Code"

            body = f"""
Hello!

Your One-Time Password (OTP) is: {otp}

This OTP is valid for {expiry_minutes} minutes.
Please do not share this code with anyone.

If you didn't request this code, please ignore this email.

Best regards,
WayzUp Team
            """
            message.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)

            expiry_time = datetime.now() + timedelta(minutes=expiry_minutes)
            st.session_state.otp_store[recipient_email] = {"otp": otp, "expiry": expiry_time}
            return True, otp, f"✅ OTP sent successfully to {recipient_email}!"
        except smtplib.SMTPAuthenticationError:
            return False, otp, "❌ Authentication failed! Check your Gmail and App Password."
        except smtplib.SMTPException as e:
            return False, otp, f"❌ SMTP Error: {str(e)}"
        except Exception as e:
            return False, otp, f"❌ Failed to send OTP: {str(e)}"

    def verify_otp(self, recipient_email: str, entered_otp: str):
        store = st.session_state.get('otp_store', {})
        if recipient_email not in store:
            return False, "❌ No OTP found for this email. Please request a new one."
        data = store[recipient_email]
        if datetime.now() > data['expiry']:
            del store[recipient_email]
            return False, "❌ OTP has expired. Please request a new one."
        if data['otp'] == entered_otp:
            del store[recipient_email]
            return True, "✅ OTP verified successfully!"
        return False, "❌ Invalid OTP. Please try again."

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_page():
    st.title("🔐 WayzUp Account")
    tabs = st.tabs(["Login", "Register"])

    with tabs[0]:
        st.subheader("Login")
        username = st.text_input("👤 Username", key="login_username", placeholder="Enter username")
        password = st.text_input("🔑 Password", key="login_password", type="password", placeholder="Enter password")
        if st.button("🚀 Login", use_container_width=True, key="btn_login"):
            try:
                resp = requests.post(f"{BACKEND_URL}/login", json={"uname": username, "password": password})
                if resp.status_code == 200:
                    result = resp.json()
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    # Get admin status from backend response
                    st.session_state.is_admin = result.get('is_admin', False)
                    st.success("✅ Login successful!")
                    st.rerun()
                elif resp.status_code == 401:
                    st.error("❌ Invalid credentials")
                else:
                    # Fallback to demo users if backend not ready
                    if username in USERS_DB and USERS_DB[username] == hash_password(password):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        # Fallback: check if username is admin for demo
                        st.session_state.is_admin = username.lower() == 'admin'
                        st.success("✅ Login successful (local demo)!")
                        st.rerun()
                    else:
                        st.error(resp.json().get('error', 'Login failed'))
            except requests.exceptions.RequestException:
                # Offline fallback to demo users
                if username in USERS_DB and USERS_DB[username] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    # Fallback: check if username is admin for demo
                    st.session_state.is_admin = username.lower() == 'admin'
                    st.success("✅ Login successful (offline demo)!")
                    st.rerun()
                else:
                    st.error("❌ Cannot reach backend and local credentials invalid")
        st.markdown("---")
        st.markdown("**Demo Credentials:**")
        st.code("Username: admin | Password: admin123")
        st.code("Username: user1 | Password: pass123")

    with tabs[1]:
        st.subheader("Register with Email OTP")
        st.markdown("Use a Gmail App Password for sending OTP. Configure in Settings below or use st.secrets.")

        
        with st.expander("SMTP Settings (Gmail)"):
            sender_email = st.text_input("Sender Gmail", value="Nityazijoo@gmail.com")
            sender_app_password = st.text_input("Gmail App Password", value="nhvw uhav nhnm pnrv", type="password")
        # Registration form
        reg_email = st.text_input("Your Email (to receive OTP)", key="reg_email", placeholder="you@example.com")
        reg_username = st.text_input("Choose Username", key="reg_username")
        reg_password = st.text_input("Choose Password", key="reg_password", type="password")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📧 Send OTP", use_container_width=True, key="btn_send_otp"):
                if not (sender_email and sender_app_password):
                    st.error("Please provide Gmail sender email and app password.")
                elif not reg_email:
                    st.error("Please enter your email to receive OTP.")
                else:
                    otp_sender = OTPSender(sender_email, sender_app_password)
                    ok, otp_code, msg = otp_sender.send_otp(reg_email)
                    if ok:
                        st.session_state.otp_data = {"email": reg_email, "username": reg_username, "password": reg_password}
                        st.success(msg)
                    else:
                        st.error(msg)

        entered_otp = st.text_input("Enter OTP", key="entered_otp")
        with col_b:
            if st.button("✅ Verify & Register", use_container_width=True, key="btn_verify_otp"):
                if not (sender_email and sender_app_password):
                    st.error("Missing SMTP settings.")
                elif not reg_email:
                    st.error("Enter your email.")
                else:
                    otp_sender = OTPSender(sender_email, sender_app_password)
                    valid, msg = otp_sender.verify_otp(reg_email, entered_otp)
                    if valid:
                        if not reg_username:
                            st.warning("Username not provided; using email as username.")
                            reg_username_final = reg_email
                        else:
                            reg_username_final = reg_username
                        if not reg_password:
                            st.warning("No password set; defaulting to OTP as password.")
                            reg_password_final = entered_otp
                        else:
                            reg_password_final = reg_password
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/register",
                                json={"uname": reg_username_final, "password": reg_password_final, "email": reg_email}
                            )
                            if resp.status_code == 201:
                                st.success("Account created! You can now login.")
                            else:
                                st.error(resp.json().get('error', 'Registration failed'))
                        except requests.exceptions.RequestException:
                            # Fallback to local demo store if backend unreachable
                            USERS_DB[reg_username_final] = hash_password(reg_password_final)
                            st.info("Backend unreachable. Saved to local demo store; you can login (demo only).")
                    else:
                        st.error(msg)

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.is_admin = False
    st.rerun()

# Main app logic
if not st.session_state.logged_in:
    login_page()
else:
    # Sidebar navigation
    st.sidebar.title("🚨 WayzUp")
    st.sidebar.markdown(f"**Welcome, {st.session_state.username}!** 👋")
    st.sidebar.markdown("Community Hazard Alert System")
    st.sidebar.markdown("---")
    
    # Check if user is admin from session state (set during login)
    is_admin = st.session_state.get('is_admin', False)
    
    # Navigation options
    if is_admin:
        page = st.sidebar.radio("Navigation", ["🧭 Report Hazard", "🗺️ View Map", "📊 Admin Dashboard", "ℹ️ About"])
    else:
        page = st.sidebar.radio("Navigation", ["🧭 Report Hazard", "🗺️ View Map", "ℹ️ About"])
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        logout()

    # Page 1: Report Hazard
    if page == "🧭 Report Hazard":
        st.title("🧭 Report a Road Hazard")
        st.markdown("Help your community by reporting road hazards in your area.")
        
        with st.form("hazard_form"):
            st.subheader("Hazard Details")
            
            description = st.text_area(
                "Description",
                placeholder="e.g., Flooded underpass near City Mall, Fallen tree blocking road...",
                help="Describe the hazard you're reporting"
            )
            
            uploaded_file = st.file_uploader(
                "Upload Image",
                type=['png', 'jpg', 'jpeg', 'gif'],
                help="Upload a photo of the hazard"
            )
            
            # Warning about incorrect images
            with st.expander("⚠️ Important: Image Guidelines", expanded=False):
                st.markdown("""
                ### ❌ **Do NOT upload:**
                - Regular road images without hazards
                - Empty roads or clean streets
                - Images that don't show any hazards
                
                ### ✅ **DO upload:**
                - Images showing **potholes**
                - Images showing **floods** or waterlogged areas
                - Images showing **debris** or obstacles on road
                - Images showing **fallen trees** or branches
                - Images showing **accidents** or damaged vehicles
                - Images showing **road damage** or cracks
                - Any other **visible hazards** on the road
                
                **Note:** Images that appear to be regular road photos without hazards will be automatically rejected.
                """)
            
            st.subheader("Location")
            
            col1, col2 = st.columns(2)
            
            with col1:
                lat = st.number_input(
                    "Latitude",
                    value=28.4595,
                    format="%.6f",
                    help="Your current latitude"
                )
            
            with col2:
                lng = st.number_input(
                    "Longitude",
                    value=77.0266,
                    format="%.6f",
                    help="Your current longitude"
                )
            
            st.info("💡 Tip: Use your device's location services or a map to find your coordinates")
            
            submit_button = st.form_submit_button("🚀 Submit Report", use_container_width=True)
            
            if submit_button:
                if not description:
                    st.error("⚠️ Please provide a description of the hazard")
                else:
                    try:
                        # Prepare form data
                        files = {}
                        if uploaded_file:
                            files['image'] = (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                        
                        data = {
                            'description': description,
                            'lat': lat,
                            'lng': lng
                        }

                        if st.session_state.get('username'):
                            data['username'] = st.session_state.get('username')
                        
                        # Submit to backend
                        response = requests.post(f"{BACKEND_URL}/report", data=data, files=files)
                        
                        if response.status_code == 201:
                            result = response.json()
                            st.success("✅ Hazard reported successfully!")
                            
                            if result.get('verified'):
                                st.balloons()
                                st.success("🎉 Your report has been verified! Another user reported a similar hazard nearby.")
                            else:
                                st.info("ℹ️ Your report is pending verification. It will appear on the map once another user confirms a similar hazard nearby.")
                        
                        elif response.status_code == 400:
                            error_data = response.json()
                            
                            # Check if image was rejected (road class detected)
                            if error_data.get('rejected') and error_data.get('roboflow_verification', {}).get('is_road'):
                                st.error("❌ **Image Rejected: Invalid Upload**")
                                st.warning(f"**{error_data.get('error', 'Invalid image detected')}**")
                                
                                # Show prediction details
                                roboflow_info = error_data.get('roboflow_verification', {})
                                if roboflow_info.get('prediction_class'):
                                    confidence = roboflow_info.get('confidence', 0)
                                    # Handle confidence as percentage (0-1) or already as percentage (0-100)
                                    if confidence <= 1:
                                        confidence_display = f"{confidence * 100:.1f}%"
                                    else:
                                        confidence_display = f"{confidence:.1f}%"
                                    st.info(f"🔍 **Detection:** The AI detected this image as '{roboflow_info.get('prediction_class').upper()}' (confidence: {confidence_display})")
                                
                                # Show helpful examples
                                st.markdown("---")
                                st.markdown("### 📸 **Please upload images showing actual hazards:**")
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    st.markdown("""
                                    **✅ Good Examples:**
                                    - Potholes
                                    - Floods
                                    - Debris
                                    """)
                                
                                with col2:
                                    st.markdown("""
                                    **✅ Good Examples:**
                                    - Fallen trees
                                    - Road damage
                                    - Accidents
                                    """)
                                
                                with col3:
                                    st.markdown("""
                                    **❌ Bad Examples:**
                                    - Empty roads
                                    - Clean streets
                                    - No visible hazards
                                    """)
                            else:
                                # Other validation errors
                                st.error(f"❌ Error: {error_data.get('error', 'Unknown error')}")
                        else:
                            st.error(f"❌ Error: {response.json().get('error', 'Unknown error')}")
                            
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Cannot connect to backend server. Please ensure Flask server is running on http://127.0.0.1:5000")
                    except Exception as e:
                        st.error(f"❌ An error occurred: {str(e)}")

    # Page 2: View Map
    elif page == "🗺️ View Map":
        st.title("🗺️ Verified Hazards Map")
        st.markdown("View all verified road hazards reported by the community.")
        
        try:
            # Fetch verified hazards
            response = requests.get(f"{BACKEND_URL}/hazards")
            
            if response.status_code == 200:
                hazards = response.json()
                
                if hazards:
                    # Center map on first hazard or default location
                    center_lat = hazards[0]['lat'] if hazards else 28.4595
                    center_lng = hazards[0]['lng'] if hazards else 77.0266
                    
                    # ========== FOLIUM MAP (DEFAULT) ==========
                    m = folium.Map(
                        location=[center_lat, center_lng],
                        zoom_start=12,
                        tiles="OpenStreetMap"
                    )
                    
                    # Add markers for each hazard
                    for hazard in hazards:
                        popup_html = f"""
                        <div style="width: 200px;">
                            <h4 style="margin-bottom: 10px;">⚠️ Hazard Alert</h4>
                            <p><strong>Description:</strong><br>{hazard['description']}</p>
                            <p><strong>Location:</strong><br>
                            Lat: {hazard['lat']:.6f}<br>
                            Lng: {hazard['lng']:.6f}</p>
                        """
                        
                        if hazard['image_url']:
                            popup_html += f'<img src="{hazard["image_url"]}" style="width: 100%; margin-top: 10px; border-radius: 5px;">'
                        
                        popup_html += "</div>"
                        
                        folium.Marker(
                            location=[hazard['lat'], hazard['lng']],
                            popup=folium.Popup(popup_html, max_width=250),
                            tooltip=hazard['description'][:50] + "...",
                            icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
                        ).add_to(m)
                    
                    # Display map
                    st_folium(m, width=1400, height=600)
                    
                    # ========== GOOGLE MAPS ALTERNATIVE (UNCOMMENTED TO USE) ==========
                    # Uncomment below and comment Folium code above to use Google Maps
                    """
                    # Create markers string for Google Maps
                    markers = ""
                    for hazard in hazards:
                        markers += f"&markers=color:red%7Clabel:!%7C{hazard['lat']},{hazard['lng']}"
                    
                    # Google Maps Static API URL
                    if 'GOOGLE_MAPS_API_KEY' in globals():
                        map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={center_lat},{center_lng}&zoom=12&size=1400x600{markers}&key={GOOGLE_MAPS_API_KEY}"
                        st.image(map_url, use_container_width=True)
                        
                        # Interactive Google Maps embed
                        st.markdown(f'''
                        <iframe
                            width="100%"
                            height="600"
                            frameborder="0"
                            style="border:0"
                            src="https://www.google.com/maps/embed/v1/place?key={"AIzaSyCUoXSxH-ITjgB_qye3u-ncOAw4g6xo-UU"}&q={center_lat},{center_lng}&zoom=12"
                            allowfullscreen>
                        </iframe>
                        ''', unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Google Maps API key not configured. Add GOOGLE_MAPS_API_KEY at top of file.")
                    """
                    # ========================================================
                    
                    # Display hazards list
                    st.subheader(f"📋 Total Verified Hazards: {len(hazards)}")
                    
                    for idx, hazard in enumerate(hazards, 1):
                        with st.expander(f"Hazard #{idx}: {hazard['description'][:60]}..."):
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                st.write(f"**Description:** {hazard['description']}")
                                st.write(f"**Coordinates:** {hazard['lat']:.6f}, {hazard['lng']:.6f}")
                                st.write(f"**Status:** ✅ Verified")
                            
                            with col2:
                                if hazard['image_url']:
                                    st.image(hazard['image_url'], caption="Hazard Image", use_container_width=True)
                else:
                    st.info("ℹ️ No verified hazards to display yet. Be the first to report!")
                    
                    # Show default map
                    m = folium.Map(location=[28.4595, 77.0266], zoom_start=12)
                    st_folium(m, width=1400, height=600)
            else:
                st.error("❌ Error fetching hazards from server")
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend server. Please ensure Flask server is running on http://127.0.0.1:5000")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

    # Page 3: Admin Dashboard (only for admin users)
    elif page == "📊 Admin Dashboard" and is_admin:
        st.title("📊 Admin Dashboard")
        st.markdown("### Report Statistics & Analytics")
        
        try:
            # Fetch statistics from backend
            response = requests.get(f"{BACKEND_URL}/admin/stats")
            
            if response.status_code == 200:
                stats = response.json()
                
                # Get stats for all periods first
                day_stats = stats.get('day', {})
                week_stats = stats.get('week', {})
                month_stats = stats.get('month', {})
                year_stats = stats.get('year', {})
                
                # Highlight unverified reports prominently
                if any([
                    day_stats.get('unverified', 0) > 0, 
                    week_stats.get('unverified', 0) > 0, 
                    month_stats.get('unverified', 0) > 0, 
                    year_stats.get('unverified', 0) > 0
                ]):
                    st.warning("⚠️ **Attention Required:** There are unverified reports that need review!")
                    st.markdown("---")
                
                # Display time period statistics
                st.subheader("📈 Reports by Time Period")
                
                # Create columns for each time period
                col1, col2, col3, col4 = st.columns(4)
                
                # 1 Day Statistics
                with col1:
                    st.metric(
                        "Last 24 Hours",
                        day_stats.get('total', 0),
                        delta=None
                    )
                    st.caption(f"✅ Verified: {day_stats.get('verified', 0)}")
                    st.caption(f"❌ Unverified: {day_stats.get('unverified', 0)}")
                
                # 1 Week Statistics
                with col2:
                    st.metric(
                        "Last 7 Days",
                        week_stats.get('total', 0),
                        delta=None
                    )
                    st.caption(f"✅ Verified: {week_stats.get('verified', 0)}")
                    st.caption(f"❌ Unverified: {week_stats.get('unverified', 0)}")
                
                # 1 Month Statistics
                with col3:
                    st.metric(
                        "Last 30 Days",
                        month_stats.get('total', 0),
                        delta=None
                    )
                    st.caption(f"✅ Verified: {month_stats.get('verified', 0)}")
                    st.caption(f"❌ Unverified: {month_stats.get('unverified', 0)}")
                
                # 1 Year Statistics
                with col4:
                    st.metric(
                        "Last 365 Days",
                        year_stats.get('total', 0),
                        delta=None
                    )
                    st.caption(f"✅ Verified: {year_stats.get('verified', 0)}")
                    st.caption(f"❌ Unverified: {year_stats.get('unverified', 0)}")
                
                # Detailed breakdown sections
                st.markdown("---")
                
                # Create expandable sections for each time period
                periods = [
                    ('day', 'Last 24 Hours', day_stats),
                    ('week', 'Last 7 Days', week_stats),
                    ('month', 'Last 30 Days', month_stats),
                    ('year', 'Last 365 Days', year_stats)
                ]
                
                for period_key, period_label, period_data in periods:
                    with st.expander(f"📊 {period_label} - Detailed Breakdown", expanded=False):
                        total = period_data.get('total', 0)
                        verified = period_data.get('verified', 0)
                        unverified = period_data.get('unverified', 0)
                        
                        if total > 0:
                            verified_pct = (verified / total) * 100
                            unverified_pct = (unverified / total) * 100
                            
                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                st.markdown(f"**Total Reports:** {total}")
                                st.progress(1.0)
                                st.markdown(f"**✅ Verified Reports:** {verified} ({verified_pct:.1f}%)")
                                st.progress(verified_pct / 100)
                            
                            with col_b:
                                st.markdown(f"**❌ Unverified Reports:** {unverified} ({unverified_pct:.1f}%)")
                                st.progress(unverified_pct / 100)
                                st.markdown(f"**Verification Rate:** {verified_pct:.1f}%")
                        else:
                            st.info(f"No reports found in the {period_label.lower()}")
                
                # All-time statistics
                st.markdown("---")
                st.subheader("📊 All-Time Statistics")
                
                all_time_stats = stats.get('all_time', {})
                total_all = all_time_stats.get('total', 0)
                verified_all = all_time_stats.get('verified', 0)
                unverified_all = all_time_stats.get('unverified', 0)
                
                if total_all > 0:
                    col_x, col_y = st.columns(2)
                    
                    with col_x:
                        st.metric("Total Reports (All Time)", total_all)
                        st.metric("✅ Verified Reports", verified_all)
                    
                    with col_y:
                        verification_rate = (verified_all / total_all) * 100 if total_all > 0 else 0
                        st.metric("❌ Unverified Reports", unverified_all)
                        st.metric("Overall Verification Rate", f"{verification_rate:.1f}%")
                    
                    # Progress bars
                    st.markdown("**Verification Status Distribution:**")
                    verified_pct_all = (verified_all / total_all) * 100
                    unverified_pct_all = (unverified_all / total_all) * 100
                    
                    st.markdown(f"✅ Verified: {verified_pct_all:.1f}%")
                    st.progress(verified_pct_all / 100)
                    
                    st.markdown(f"❌ Unverified: {unverified_pct_all:.1f}%")
                    st.progress(unverified_pct_all / 100)
                else:
                    st.info("No reports in the system yet")
                
                # Summary insights
                st.markdown("---")
                st.subheader("💡 Insights")
                
                # Calculate insights
                insights = []
                
                if day_stats.get('total', 0) > 0:
                    day_unverified = day_stats.get('unverified', 0)
                    insights.append(f"📅 **Today**: {day_unverified} unverified report(s) in the last 24 hours")
                
                if week_stats.get('total', 0) > 0:
                    week_unverified = week_stats.get('unverified', 0)
                    week_rate = (week_stats.get('verified', 0) / week_stats.get('total', 0)) * 100 if week_stats.get('total', 0) > 0 else 0
                    insights.append(f"📅 **This Week**: {week_unverified} unverified report(s) out of {week_stats.get('total', 0)} total ({100-week_rate:.1f}% unverified)")
                
                if month_stats.get('total', 0) > 0:
                    month_rate = (month_stats.get('verified', 0) / month_stats.get('total', 0)) * 100 if month_stats.get('total', 0) > 0 else 0
                    insights.append(f"📅 **This Month**: {month_stats.get('unverified', 0)} unverified report(s) ({100-month_rate:.1f}% unverified)")
                
                if year_stats.get('total', 0) > 0:
                    year_rate = (year_stats.get('verified', 0) / year_stats.get('total', 0)) * 100 if year_stats.get('total', 0) > 0 else 0
                    insights.append(f"📅 **This Year**: {year_stats.get('unverified', 0)} unverified report(s) ({100-year_rate:.1f}% unverified)")
                
                if insights:
                    for insight in insights:
                        st.markdown(insight)
                else:
                    st.info("No reports to analyze yet")
                
            else:
                st.error("❌ Error fetching statistics from server")
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend server. Please ensure Flask server is running on http://127.0.0.1:5000")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
    
    # Page 4: About (or Page 3 for non-admin users)
    elif page == "ℹ️ About":
        st.title("ℹ️ About WayzUp")
        
        st.markdown("""
        ## 🚨 Community Hazard Alert System
        
        **WayzUp** is a community-driven platform that helps citizens report and track road hazards in real-time.
        
        ### 🎯 Purpose
        
        Road hazards like floods, fallen trees, accidents, and potholes can be dangerous and disruptive. 
        WayzUp empowers communities to:
        
        - 📍 Report hazards instantly with location and images
        - ✅ Verify reports through community consensus
        - 🗺️ Visualize all verified hazards on an interactive map
        - 🚗 Help others avoid dangerous routes
        
        ### ⚙️ How It Works
        
        1. **Report**: Users submit hazard reports with descriptions, images, and location
        2. **Verify**: When another user reports a similar hazard within 100 meters, both reports are automatically verified
        3. **Display**: Verified hazards appear on the public map for everyone to see
        
        ### 🛠️ Tech Stack
        
        - **Frontend**: Streamlit (Python web framework)
        - **Backend**: Flask (RESTful API)
        - **Database**: SQLite
        - **Maps**: Folium + OpenStreetMap (or Google Maps API)
        - **Location**: Geopy for distance calculations
        - **Authentication**: Session-based login system
        
        ### 🌟 Features
        
        - ✅ User authentication system
        - ✅ Real-time hazard reporting
        - ✅ Automatic verification system
        - ✅ Interactive map visualization
        - ✅ Image upload support
        - ✅ GPS coordinate integration
        - ✅ Community-driven safety alerts
        
        ### 🗺️ Google Maps Integration
        
        To enable Google Maps (optional):
        1. Get API key from Google Cloud Console
        2. Add key to `GOOGLE_MAPS_API_KEY` variable
        3. Uncomment Google Maps code section
        
        ### 📞 Future Enhancements
        
        - Push notifications for nearby hazards
        - Admin dashboard for hazard management
        - Mobile app integration
        - Reverse geocoding for automatic address lookup
        - Hazard expiration and auto-removal
        - User reputation system
        
        ---
        
        ### 👨‍💻 Project Information
        
        **Version**: 1.0.0  
        **License**: MIT  
        **Created**: 2025
        
        Made with ❤️ for safer roads
        """)
        
        st.divider()
        
        st.subheader("📊 Quick Stats")
        
        try:
            response = requests.get(f"{BACKEND_URL}/hazards")
            if response.status_code == 200:
                hazards = response.json()
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Verified Hazards", len(hazards))
                
                with col2:
                    st.metric("System Status", "🟢 Online")
                
                with col3:
                    st.metric("Active User", st.session_state.username)
                    
        except:
            st.warning("⚠️ Backend server not responding")
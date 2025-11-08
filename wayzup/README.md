### 🧠 PROJECT PROMPT — “WayzUp: Community Hazard Alert System (Streamlit + Flask)”

> **Goal:**
> Build a full-stack mini-project called **“WayzUp – Community Hazard Alert System”** using **Python Flask (backend)** and **Streamlit (frontend)**.
> The system allows users to report local road hazards, upload images, automatically fetch their location, and visualize verified hazards on a map.

---

### 🎯 Functional Requirements

1. **Users can:**

   * Report a road hazard (floods, fallen trees, accidents, etc.).
   * Upload an image and short description.
   * Automatically fetch or manually enter their latitude and longitude.
   * View all **verified** hazards on a map (using Folium or Google Maps).

2. **Verification Logic:**

   * When a new report is submitted, check if another hazard exists within **100 meters**.
   * If yes, mark both reports as **verified** and display them publicly.

---

### ⚙️ Tech Stack

* **Frontend:** Streamlit
* **Backend:** Flask
* **Database:** SQLite or JSON
* **Map:** Folium + streamlit-folium
* **Utilities:** geopy (distance + geocoding)

---

### 🧩 Backend Specifications (Flask)

**Endpoints:**

* `POST /report` → receive new hazard report (image, lat, lng, description)
* `GET /hazards` → return all *verified* hazard data to frontend
* `GET /all_hazards` → return all hazard data (verified or not) for admin dashboard
* `DELETE /hazard/<id>` → delete a specific hazard by ID (for admin use)

**Logic:**

* Store reports in SQLite (`hazards.db`)
* Compare each new report with existing ones using haversine formula
* Mark both hazards as verified if within 100 m radius
* Save images in `/uploads` folder
* Return JSON responses with verification status
* For admin: Allow deletion of hazards by ID (no authentication for simplicity in this mini-project)

---

### 🎨 Frontend Specifications (Streamlit)

**Pages (use sidebar menu):**

* 🧭 **Report Hazard:**

  * Input: description, image upload, auto or manual coordinates
  * Submit data to Flask backend
  * Show success toast (“Hazard reported successfully!”)

* 🗺️ **View Map:**

  * Display Folium map
  * Red markers for verified hazards
  * Popup shows description + image preview

* ℹ️ **About:**

  * Describe project purpose and tech stack

* 🔧 **Admin Dashboard (Bonus Add-On):**

  * Simple password input (e.g., "admin123") for access
  * Display a table of all hazards (verified or not) with columns: ID, Description, Lat, Lng, Verified, Image Preview
  * Allow selection and deletion of hazards via a "Delete Selected" button
  * Call backend `GET /all_hazards` to fetch data and `DELETE /hazard/<id>` to remove
  * Show confirmation dialog before deletion

---

### 💾 Folder Structure

```
wayzup/
│
├── backend/
│   ├── app.py
│   ├── hazards.db
│   └── requirements.txt
│
├── frontend/
│   ├── app_frontend.py
│   └── requirements.txt
│
└── README.md
```

---

### 🚀 Run Instructions

1. **Backend**

   ```bash
   cd backend
   pip install -r requirements.txt
   python app.py
   ```

   Runs on → `http://127.0.0.1:5000`

2. **Frontend**

   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run app_frontend.py
   ```

   Runs on → `http://localhost:8501`

---

### 📘 Example API Response

**POST /report**

```json
{
  "message": "Hazard reported successfully!",
  "verified": false
}
```

**GET /hazards**

```json
[
  {
    "id": 1,
    "description": "Flooded underpass near City Mall",
    "lat": 19.076,
    "lng": 72.8777,
    "image_url": "http://localhost:5000/uploads/flood.jpg",
    "verified": true
  }
]
```

**GET /all_hazards (for Admin)**

```json
[
  {
    "id": 1,
    "description": "Flooded underpass near City Mall",
    "lat": 19.076,
    "lng": 72.8777,
    "image_url": "http://localhost:5000/uploads/flood.jpg",
    "verified": true
  },
  {
    "id": 2,
    "description": "Unverified pothole",
    "lat": 19.077,
    "lng": 72.878,
    "image_url": "http://localhost:5000/uploads/pothole.jpg",
    "verified": false
  }
]
```

**DELETE /hazard/<id>**

```json
{
  "message": "Hazard deleted successfully!"
}
```

---

### 🌟 Optional Add-Ons

* Add **reverse geocoding** to auto-fill area names.
* Include **React Toastify-like** success notifications with `st.toast()` or `st.success()`.
* **Bonus Admin Dashboard:** As detailed in the Frontend Specifications above. This allows admins to view and delete outdated or invalid hazard reports, ensuring the system stays clean. Use Streamlit's `st.dataframe` for the table and `st.button` for deletion. For simplicity, no advanced auth—just a password check.

---

**Prompt Summary (for direct use):**

> Build a full-stack Python project called “WayzUp – Community Hazard Alert System” using Flask (backend) and Streamlit (frontend).
> Backend: `POST /report`, `GET /hazards`, `GET /all_hazards`, `DELETE /hazard/<id>`, SQLite DB, image uploads, 100 m verification logic.
> Frontend: 4 pages (Report Hazard, View Map, About, Admin Dashboard) using Folium map and Streamlit UI.
> Include all code, folder structure, requirements, and instructions to run locally.




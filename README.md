🚨 WayzUp – Community Hazard Alert System

<div align="center">
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.x-black?style=for-the-badge&logo=flask)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
A full-stack civic-tech app for crowd-sourced road hazard reporting with real-time geospatial verification.

Features · Architecture · Getting Started · API Reference · Future Work

</div>

📌 Problem Statement

Road hazards — flooded underpasses, fallen trees, potholes, accidents — cause thousands of injuries annually in India. There's no fast, community-driven way to report and verify them in real time. WayzUp solves this.


## ✨ Features

- 📍 **Hazard Reporting** — Submit road hazard reports with description, image, and GPS coordinates  
- ✅ **Crowd Verification** — Automatically marks a hazard as verified when a second report is filed within 100 metres (Haversine formula)  
- 🗺️ **Live Hazard Map** — Interactive Folium map with red markers for all verified hazards  
- 🖼️ **Image Upload** — Attach photos directly to hazard reports  
- 🔧 **Admin Dashboard** — View all reports (verified + unverified), delete invalid entries  
- 📡 **REST API** — Clean Flask backend with 4 endpoints for full CRUD support


## 🏗️ Architecture

User submits report (Streamlit)
        │
        ▼
POST /report (Flask)
        │
        ├── Save to SQLite (hazards.db)
        ├── Compare with existing reports using Haversine formula
        └── If distance < 100m → mark both as VERIFIED
                │
                ▼
        GET /hazards (Streamlit fetches verified hazards)
                │
                ▼
        Folium map renders red markers with popup info


## 📁 Project Structure

wayzup/
│
├── backend/
│   ├── app.py              # Flask REST API
│   ├── hazards.db          # SQLite database (auto-created)
│   ├── uploads/            # Uploaded hazard images
│   └── requirements.txt
│
├── frontend/
│   ├── app_frontend.py     # Streamlit multi-page app
│   └── requirements.txt
│
└── README.md


## 🚀 Getting Started

Prerequisites


Python 3.9+
pip


1. Clone the Repository

bashgit clone https://github.com/nitya-zijoo/WayzUP.git
cd WayzUP

2. Start the Backend (Flask)

bashcd backend
pip install -r requirements.txt
python app.py


Runs on → http://127.0.0.1:5000



3. Start the Frontend (Streamlit)

bashcd frontend
pip install -r requirements.txt
streamlit run app_frontend.py


Runs on → http://localhost:8501




## 📡 API Reference

MethodEndpointDescriptionPOST/reportSubmit a new hazard reportGET/hazardsFetch all verified hazardsGET/all_hazardsFetch all hazards (admin only)DELETE/hazard/<id>Delete a hazard by ID (admin only)

Example Responses

POST /report

json{
  "message": "Hazard reported successfully!",
  "verified": false
}

GET /hazards

json[
  {
    "id": 1,
    "description": "Flooded underpass near City Mall",
    "lat": 19.076,
    "lng": 72.8777,
    "image_url": "http://localhost:5000/uploads/flood.jpg",
    "verified": true
  }
]


## 🛠️ Tech Stack

LayerTechnologyFrontendStreamlitBackendFlask (Python)DatabaseSQLiteMapsFolium + streamlit-foliumGeospatialgeopy (Haversine distance)Image StorageLocal /uploads folder


## 🔮 Future Work


 Replace SQLite with PostgreSQL for production scalability
 Add JWT-based authentication for the admin dashboard
 Integrate reverse geocoding to auto-fill area names from coordinates
 Push notifications when a hazard near the user gets verified
 Deploy backend on Railway / Render; frontend on Streamlit Cloud
 Add severity classification (low / medium / high) using image ML model



## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.


# 📄 License

This project is licensed under the MIT License. See LICENSE for details.


#👩‍💻 Author

Nitya Zijoo

B.Tech CSIT '27 | Data Engineering & ML

Show Image
Show Image


<div align="center">
⭐ If you found this useful, consider starring the repo!
</div>


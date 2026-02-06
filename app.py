from flask import Flask, render_template, request, jsonify, session
import sqlite3
import uuid
import math

# Hardcoded Hospitals (Coimbatore)
HOSPITALS = [
    {"name": "KG Hospital", "lat": 11.0016, "lng": 76.9628},
    {"name": "PSG Hospitals", "lat": 11.0247, "lng": 77.0028},
    {"name": "KMCH", "lat": 11.0558, "lng": 77.0315},
    {"name": "GKNM Hospital", "lat": 11.0118, "lng": 76.9798}
]

def calculate_distance(lat1, lng1, lat2, lng2):
    # Haversine formula
    R = 6371 # Earth radius in km
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLng/2) * math.sin(dLng/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

app = Flask(__name__)
app.secret_key = "ambulance_secret"

# DB CONFIG
DATABASE = 'ambulance.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Optional: allows accessing columns by name, but tuple access works too
    return conn

# HOME – LOGIN PAGE
@app.route("/")
def login_page():
    return render_template("login.html")

# LOGIN HANDLE
@app.route("/login", methods=["POST"])
def login():
    user_type = request.form.get("type")
    if user_type == "people":
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
        return render_template("index.html") 
    elif user_type == "ambulance":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin123":
            return render_template("ambulance.html")
        else:
            return render_template("login.html", error="Invalid Username or Password")
    return "Invalid Login"

# ROAD MODE (People)
@app.route("/road_mode")
def road_mode():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template("index.html")

# AMBULANCE PAGE
@app.route("/ambulance")
def ambulance():
    return render_template("ambulance.html")

# UPDATE USER LOCATION
@app.route("/update_user", methods=["POST"])
def update_user():
    data = request.json
    user_id = session['user_id']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, lat, lng, speed, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
        lat=excluded.lat, lng=excluded.lng, speed=excluded.speed, updated_at=CURRENT_TIMESTAMP
    """, (user_id, data['lat'], data['lng'], data['speed']))
    conn.commit()
    conn.close()
    return "User updated"

# UPDATE AMBULANCE LOCATION
@app.route("/update_ambulance", methods=["POST"])
def update_ambulance():
    data = request.get_json(force=True) if request.is_json or request.data else {}
    if not data: return "No Data", 400
    lat = data.get('lat', 0)
    lng = data.get('lng', 0)
    status = data.get('status', 'OFF') # Default to OFF if not sent
    green_corridor = data.get('green_corridor', False)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ambulance
        SET lat=?, lng=?, status=?, updated_at=CURRENT_TIMESTAMP, green_corridor=?
        WHERE id=1
    """, (lat, lng, status, green_corridor))
    conn.commit()
    conn.close()

    # Calculate Nearest Hospital (Still needed for name, but ETA now comes from driver)
    nearest_hospital = None
    eta_seconds = 0
    
    if status == 'ON':
        min_dist = float('inf')
        eta_seconds = 0   # Initialize here or outside

        for hosp in HOSPITALS:
            d = calculate_distance(lat, lng, hosp['lat'], hosp['lng'])
            if d < min_dist:
                min_dist = d
                nearest_hospital = hosp
        
        # ETA (Assuming 60km/h)
        speed_mps = 60 * (1000/3600)
        dist_m = min_dist * 1000
        if speed_mps > 0:
            eta_seconds = dist_m / speed_mps

    return jsonify({
        "status": "success",
        "hospital": nearest_hospital,
        "eta_seconds": int(eta_seconds) if nearest_hospital else 0
    })

# CHECK NEARBY
@app.route("/check_nearby")
def check_nearby():
    try:
        user_id = session.get('user_id')
        if not user_id: return jsonify({"alert": False})

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM ambulance WHERE id=1")
        amb = cur.fetchone()
        
        cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        usr = cur.fetchone()
        conn.close()

        if not usr or not amb:
            return jsonify({"alert": False})

        # Data extraction
        amb_lat, amb_lng = amb[1], amb[2]
        amb_status = amb[3]
        # amb[4] is updated_at
        green_corridor_active = bool(amb[5]) if len(amb) > 5 else False

        usr_lat, usr_lng = usr[1], usr[2]
        usr_speed_kmh = usr[3]

        # 1. Nearest Hospital Logic (For User Display)
        nearest_hospital_user = None
        min_dist_hosp_user = float('inf')
        
        for hosp in HOSPITALS:
            h_dist = calculate_distance(usr_lat, usr_lng, hosp['lat'], hosp['lng'])
            if h_dist < min_dist_hosp_user:
                min_dist_hosp_user = h_dist
                nearest_hospital_user = hosp

        # 2. Ambulance Alert Logic
        # Heartbeat Check: If ambulance hasn't updated in > 30 seconds, treat as inactive
        from datetime import datetime
        
        ambulance_active = False
        
        # Check if ambulance update is recent (within 30s)
        if amb_status == 'ON' and amb['updated_at']:
            # Parse timestamp safely (SQLite returns string)
            try:
                # Format depends on SQLite default. Usually YYYY-MM-DD HH:MM:SS (UTC)
                updated_time = datetime.strptime(amb['updated_at'], '%Y-%m-%d %H:%M:%S')
                
                # Debugging Time
                now_utc = datetime.utcnow()
                diff = (now_utc - updated_time).total_seconds()

                if diff < 20: 
                    ambulance_active = True
            except Exception as e:
                print(f"Time parse error: {e}")
                ambulance_active = (amb_status == 'ON') # Fallback if time fails

        is_in_vehicle = True 
        
        dist_to_amb = calculate_distance(usr_lat, usr_lng, amb_lat, amb_lng)
        
        # Alert if nearest < 0.5km (500m)
        near = (ambulance_active and is_in_vehicle and dist_to_amb < 0.5)

        # 3. ETA Calculation (Ambulance -> Nearest Hospital)
        eta_seconds = 0
        nearest_hospital_amb = None
        
        if ambulance_active:
            # Find hospital nearest to AMBULANCE
            min_dist_hosp_amb = float('inf')
            for hosp in HOSPITALS:
                h_dist = calculate_distance(amb_lat, amb_lng, hosp['lat'], hosp['lng'])
                if h_dist < min_dist_hosp_amb:
                    min_dist_hosp_amb = h_dist
                    nearest_hospital_amb = hosp
            
            # Calculate ETA
            speed_mps = 60 * (1000/3600) # ~16.6 m/s
            dist_m = min_dist_hosp_amb * 1000
            if speed_mps > 0:
                eta_seconds = dist_m / speed_mps

        return jsonify({
            "alert": near,
            "amb": {"lat": amb_lat, "lng": amb_lng},
            "hospital": nearest_hospital_user, # Show hospital nearest to USER on map
            "eta_seconds": int(eta_seconds) if ambulance_active else None,
            "hospital_target": nearest_hospital_amb, # Optional: if we want to show where amb is going
            "green_corridor": green_corridor_active and ambulance_active # Only true if amb is also active
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

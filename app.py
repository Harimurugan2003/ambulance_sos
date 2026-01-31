from flask import Flask, render_template, request, jsonify, session
from flask_mysqldb import MySQL
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
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Harimurugan@17'
app.config['MYSQL_DB'] = 'ambulance_alert'
app.config['MYSQL_PORT'] = 3306

mysql = MySQL(app)

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

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO users VALUES (%s,%s,%s,%s,NOW())
        ON DUPLICATE KEY UPDATE
        lat=%s, lng=%s, speed=%s
    """, (
        user_id, data['lat'], data['lng'], data['speed'],
        data['lat'], data['lng'], data['speed']
    ))
    mysql.connection.commit()
    cur.close()
    return "User updated"

# UPDATE AMBULANCE LOCATION
@app.route("/update_ambulance", methods=["POST"])
def update_ambulance():
    data = request.json
    lat = data['lat']
    lng = data['lng']
    status = data.get('status', 'OFF') # Default to OFF if not sent
    
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE ambulance
        SET lat=%s, lng=%s, status=%s
        WHERE id=1
    """, (lat, lng, status))
    mysql.connection.commit()
    cur.close()

    # Calculate Nearest Hospital & ETA for the Driver
    nearest_hospital = None
    eta_seconds = 0
    
    if status == 'ON':
        min_dist = float('inf')
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
    user_id = session.get('user_id')
    if not user_id: return jsonify({"alert": False})

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM ambulance WHERE id=1")
    amb = cur.fetchone()
    
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    usr = cur.fetchone()
    cur.close()

    if not usr or not amb:
        return jsonify({"alert": False})

    # Data extraction
    amb_lat, amb_lng = amb[1], amb[2]
    amb_status = amb[3]
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
    ambulance_active = (amb_status == 'ON')
    is_in_vehicle = (usr_speed_kmh > 10) # User moving > 10km/h
    
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
        "hospital_target": nearest_hospital_amb # Optional: if we want to show where amb is going
    })

if __name__ == "__main__":
    app.run(debug=True)

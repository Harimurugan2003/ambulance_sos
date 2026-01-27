from flask import Flask, render_template, request, jsonify, session
import psycopg2
import os
import uuid

app = Flask(__name__)
app.secret_key = "ambulance_secret"

# DB CONFIG
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://ambulance_db_ny8v_user:r0aGDaeWZuHDMg7XrRyTd5vQIE7bcAfP@dpg-d5s872n18n1s73c926bg-a/ambulance_db_ny8v')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# HOME – USER
@app.route("/")
def index():
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
        VALUES (%s,%s,%s,%s,NOW())
        ON CONFLICT (user_id) 
        DO UPDATE SET
        lat=EXCLUDED.lat, lng=EXCLUDED.lng, speed=EXCLUDED.speed, updated_at=NOW()
    """, (
        user_id, data['lat'], data['lng'], data['speed']
    ))
    conn.commit()
    cur.close()
    conn.close()
    return "User updated"

# UPDATE AMBULANCE LOCATION
@app.route("/update_ambulance", methods=["POST"])
def update_ambulance():
    data = request.json
    status = data.get('status', 'OFF') # Default to OFF if not sent
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ambulance
        SET lat=%s, lng=%s, status=%s
        WHERE id=1
    """, (data['lat'], data['lng'], status))
    conn.commit()
    cur.close()
    conn.close()
    return "Ambulance updated"

# CHECK NEARBY
@app.route("/check_nearby")
def check_nearby():
    radius = 0.005
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM ambulance WHERE id=1")
    amb = cur.fetchone()
    # amb: (id, lat, lng, status) based on schema order, but using fetchone returns tuple
    # Schema: id, lat, lng, status
    
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    usr = cur.fetchone()
    cur.close()
    conn.close()

    if not usr or not amb:
        return jsonify({"alert": False})

    # amb[3] is status
    ambulance_active = (amb[3] == 'ON')
    
    # Filter: User must be moving faster than 10 km/h (approx 2.7 m/s) to be considered in a vehicle
    # usr[3] is speed in km/h (stored in update_user)
    is_in_vehicle = (usr[3] > 10) 

    near = (
        ambulance_active and
        is_in_vehicle and
        abs(usr[1] - amb[1]) < radius and
        abs(usr[2] - amb[2]) < radius
    )

    return jsonify({
        "alert": near,
        "amb": {"lat": amb[1], "lng": amb[2]}
    })

if __name__ == "__main__":
    app.run(debug=True)

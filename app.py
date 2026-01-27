from flask import Flask, render_template, request, jsonify, session
from flask_mysqldb import MySQL
import uuid

app = Flask(__name__)
app.secret_key = "ambulance_secret"

# DB CONFIG
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Harimurugan@17'
app.config['MYSQL_DB'] = 'ambulance_alert'
app.config['MYSQL_PORT'] = 3306

mysql = MySQL(app)

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
    status = data.get('status', 'OFF') # Default to OFF if not sent
    
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE ambulance
        SET lat=%s, lng=%s, status=%s
        WHERE id=1
    """, (data['lat'], data['lng'], status))
    mysql.connection.commit()
    cur.close()
    return "Ambulance updated"

# CHECK NEARBY
@app.route("/check_nearby")
def check_nearby():
    radius = 0.005
    user_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM ambulance WHERE id=1")
    amb = cur.fetchone()
    # amb: (id, lat, lng, status) based on schema order, but using fetchone returns tuple
    # Schema: id, lat, lng, status
    
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    usr = cur.fetchone()
    cur.close()

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

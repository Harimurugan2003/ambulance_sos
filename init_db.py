import sqlite3

def init_db():
    conn = sqlite3.connect('ambulance.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            lat REAL,
            lng REAL,
            speed REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create ambulance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ambulance (
            id INTEGER PRIMARY KEY,
            lat REAL,
            lng REAL,
            status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            green_corridor BOOLEAN DEFAULT 0
        )
    """)
    
    # Insert initial ambulance data if not exists
    cursor.execute("SELECT count(*) FROM ambulance WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO ambulance (id, lat, lng, status, green_corridor) VALUES (1, 0, 0, 'OFF', 0)")
        print("Initialized ambulance data.")
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()

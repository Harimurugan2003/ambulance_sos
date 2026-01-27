CREATE DATABASE ambulance_alert;
USE ambulance_alert;

CREATE TABLE users (
  user_id VARCHAR(100) PRIMARY KEY,
  lat DOUBLE,
  lng DOUBLE,
  speed DOUBLE,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ambulance (
  id INT PRIMARY KEY,
  lat DOUBLE,
  lng DOUBLE,
  status VARCHAR(10)
);

INSERT INTO ambulance VALUES (1,0,0,'OFF');

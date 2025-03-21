import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import sqlite3
import hashlib
import datetime

st.set_page_config(
    page_title="Personal Fitness Tracker",
    page_icon="assets/logo.png"  # Just pass the filename (it should be in the same folder)
)


# Load trained model and scaler
with open("models/calorie_predictor.pkl", "rb") as model_file:
    model = pickle.load(model_file)

with open("models/scaler.pkl", "rb") as scaler_file:
    scaler = pickle.load(scaler_file)

# Initialize Database
def init_db():
    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, 
                    email TEXT UNIQUE, 
                    username TEXT UNIQUE, 
                    password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_details (
                    username TEXT PRIMARY KEY,
                    gender TEXT,
                    age INTEGER,
                    height INTEGER,
                    weight INTEGER,
                    FOREIGN KEY (username) REFERENCES users(username))''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress (
                    id INTEGER PRIMARY KEY, 
                    username TEXT, 
                    date TEXT, 
                    duration INTEGER, 
                    heart_rate INTEGER, 
                    body_temp REAL,
                    steps_taken INTEGER,
                    calories_burned REAL,
                    FOREIGN KEY (username) REFERENCES users(username))''')
    conn.commit()
    conn.close()

# Hashing password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Register user
def register_user(email, username, password):
    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (email, username, password) VALUES (?, ?, ?)", 
                  (email, username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Login user
def login_user(username, password):
    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?", 
              (username, username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user

# Save user details
def save_personal_details(username, gender, age, height, weight):
    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    c.execute('''INSERT INTO user_details 
                 (username, gender, age, height, weight) 
                 VALUES (?, ?, ?, ?, ?) 
                 ON CONFLICT(username) DO UPDATE 
                 SET gender=excluded.gender, 
                     age=excluded.age, 
                     height=excluded.height, 
                     weight=excluded.weight''',
              (username, gender, age, height, weight))
    conn.commit()
    conn.close()

# Get user details
def get_personal_details(username):
    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    c.execute("SELECT gender, age, height, weight FROM user_details WHERE username = ?", (username,))
    details = c.fetchone()
    conn.close()
    return details

def predict_calories(age, height, weight, duration, heart_rate, body_temp, steps):
    input_data = np.array([[age, height, weight, duration, heart_rate, body_temp, steps]]) 
    input_scaled = scaler.transform(input_data)
    calories_burned = model.predict(input_scaled)
    return round(calories_burned[0], 2)

def save_progress(username, duration, heart_rate, body_temp, steps_taken):
    details = get_personal_details(username)
    if not details:
        return False

    age, height, weight = details[1], details[2], details[3]

    calories_burned = predict_calories(age, height, weight, duration, heart_rate, body_temp, steps_taken)

    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    today = str(datetime.date.today())

    c.execute('''INSERT INTO progress (username, date, duration, heart_rate, body_temp, 
                 steps_taken, calories_burned) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (username, today, duration, heart_rate, body_temp, steps_taken, calories_burned))

    conn.commit()
    conn.close()
    
    return calories_burned


# Get Progress Data
def get_progress(username):
    conn = sqlite3.connect("fitness_tracker.db")
    c = conn.cursor()
    c.execute("SELECT date, calories_burned FROM progress WHERE username = ? ORDER BY date DESC", (username,))
    data = c.fetchall()
    conn.close()
    return data

# Initialize DB
init_db()

def calculate_calories_burned(weight, duration, steps, heart_rate):
    # MET (Metabolic Equivalent of Task) formula
    met = (heart_rate / 100) + (steps / 10000)
    calories_burned = (met * weight * duration) / 60  # Convert to per-minute basis
    return round(calories_burned, 2)


# Streamlit UI
if "page" not in st.session_state:
    st.session_state.page = "login"
if "username" not in st.session_state:
    st.session_state.username = None

if st.session_state.page == "register":
    st.title("Register")
    new_user = st.text_input("Username")
    new_email = st.text_input("Email")
    new_password = st.text_input("Password", type="password")
    if st.button("Register"):
        if new_user and new_email and new_password:
            if register_user(new_email, new_user, new_password):
                st.success("Registration successful! Please log in.")
                st.session_state.page = "login"
                st.rerun()
            else:
                st.error("Username or Email already exists! Try a different one.")
        else:
            st.error("Please fill in all fields.")

    if st.button("Already have an account? Login"):
        st.session_state.page = "login"
        st.rerun()

elif st.session_state.page == "login":
    st.title("Login")
    username = st.text_input("Username or Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if login_user(username, password):
            st.session_state.username = username
            st.session_state.page = "home"
            st.rerun()
        else:
            st.error("Invalid username or password")

    if st.button("New here? Register"):
        st.session_state.page = "register"
        st.rerun()

elif st.session_state.page == "home":
    st.sidebar.title("Personal Fitness Tracker")
    st.sidebar.write(f"Logged in as: `{st.session_state.username}`")

    if st.sidebar.button("View Progress"):
        st.session_state.page = "progress"
        st.rerun()

    st.subheader("Your Personal Details")

    details = get_personal_details(st.session_state.username)

    if details:
        st.markdown(
    f"""
    <style>
        .details-box {{
            border: 2px solid #ffffff; /* Green border */
            padding: 15px;
            border-radius: 10px;
            background: linear-gradient(135deg, #222, #333); /* Dark gradient */
            color: #fff;
            width: 100%; /* Full width */
            text-align: center; /* Center text */
            box-shadow: 2px 4px 10px rgba(0, 0, 0, 0.3); /* Soft shadow */
        }}
        .details-box p {{
            font-size: 18px; /* Bigger text */
            margin: 8px 0; /* Space between lines */
            font-weight: bold;
        }}
    </style>
    
    <div class='details-box'>
        <p> <strong>Gender:</strong> {details[0]}</p>
        <p> <strong>Age:</strong> {details[1]} years</p>
        <p> <strong>Height:</strong> {details[2]} cm</p>
        <p> <strong>Weight:</strong> {details[3]} kg</p>
    </div>
    <br> <!-- Adds space below -->
    """, 
    unsafe_allow_html=True
)

    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    # 🔹 Show input fields if no details exist (for first-time users)
    if not details or st.session_state.edit_mode:
        st.subheader("Add / Edit Your Details")

        with st.form("edit_details_form"):
            gender = st.selectbox("Gender", ["Male", "Female"], index=["Male", "Female"].index(details[0]) if details else 0)
            age = st.number_input("Age", min_value=10, max_value=100, step=1, value=details[1] if details else 20)
            height = st.number_input("Height (cm)", min_value=100, max_value=250, step=1, value=details[2] if details else 170)
            weight = st.number_input("Weight (kg)", min_value=30, max_value=200, step=1, value=details[3] if details else 60)

            save_changes = st.form_submit_button("Save Changes")
            if save_changes:
                save_personal_details(st.session_state.username, gender, age, height, weight)
                st.success("Details saved successfully!")
                st.session_state.edit_mode = False
                st.rerun()
    else:
        if st.button("Edit Details"):
            st.session_state.edit_mode = True
            st.rerun()


    if st.sidebar.button("Logout"):
        st.session_state.page = "login"
        st.session_state.username = None
        st.rerun()

elif st.session_state.page == "progress":
    st.title(" Progress Overview")

    # Fetch progress data
    data = get_progress(st.session_state.username)

    if data:
        st.write("## Recent Progress")

        # Convert to DataFrame
        df = pd.DataFrame(data, columns=["Date", "Calories Burned"])

        # Convert date column to datetime
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")

        st.dataframe(df, hide_index=True)

    else:
        st.warning(" No progress data found. Start logging your progress!")

    st.subheader("Log Your Progress")

    # Fetch user details
    user_details = get_personal_details(st.session_state.username)

    if user_details:
        gender, age, height, weight = user_details
    else:
        st.error("Please add your personal details first on the Home page.")
        st.stop()

    # Progress input fields
    with st.form("progress_form"):
        duration = st.number_input(" Exercise (minutes)", min_value=1, max_value=300, step=1)
        heart_rate = st.number_input(" Heart Rate (bpm)", min_value=40, max_value=200, step=1)
        body_temp = st.number_input(" Body Temperature (°C)", min_value=35.0, max_value=42.0, step=0.1)
        steps_taken = st.number_input(" Steps Taken", min_value=0, max_value=50000, step=100)

        submit_progress = st.form_submit_button("Save Progress")

        if submit_progress:
            # Calculate Calories Burned
            calories_burned = calculate_calories_burned(weight, duration, steps_taken, heart_rate)

            # Save to database
            save_progress(st.session_state.username, duration, heart_rate, body_temp, steps_taken)

            st.success(" Progress saved successfully!")
            st.rerun()

    # 📈 Graph at the Bottom
    if data:
        st.write("### Calories Burned Over Time")
        st.line_chart(df.set_index("Date")["Calories Burned"])

if st.session_state.page not in ["login", "register", "home"]:
    if st.button("⬅️ Back to Home"):
        st.session_state.page = "home"
        st.rerun()
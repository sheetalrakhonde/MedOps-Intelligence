from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
import pandas as pd
import sqlite3
import os
from google import genai                    # NEW SDK
from google.genai import types             # NEW SDK types
from dotenv import load_dotenv
import ml_engine
import datetime
import random
import re

# Load environment variables
load_dotenv()

# --- GEMINI API KEY SETUP ---
api_key_from_env = os.getenv("GEMINI_API_KEY")

if api_key_from_env:
    client = genai.Client(api_key=api_key_from_env)   # NEW: single client object
    gemini_api_configured = True
    print("Gemini API key detected. AI features active.")
else:
    client = None
    gemini_api_configured = False
    print("WARNING: GEMINI_API_KEY not found in .env.")

# --- Flask app setup ---
app = Flask(__name__)
app.secret_key = "super_secret_medops_key_replace_with_a_strong_random_string"

# Helper: generate content with fallback models
def generate(prompt: str, models=None) -> str | None:
    if models is None:
        models = [
            'gemini-2.0-flash',        # Try this first
            'gemini-2.0-flash-001',    # Explicit version fallback
            'gemini-2.0-flash-lite',   # Lightest fallback
        ]
    for m in models:
        try:
            response = client.models.generate_content(
                model=m,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Model {m} failed: {e}")
    return None
# ---------------- ROUTES ---------------- #

@app.route('/api/models')
def list_models():
    try:
        models = client.models.list()
        return jsonify({"models": [m.name for m in models]})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/add_data', methods=['GET', 'POST'])
def add_data():
    if request.method == 'POST':
        date = request.form['date']
        hospital = request.form['hospital']
        ward = request.form['ward']
        wait_time = int(request.form['wait_time'])
        occupancy = float(request.form['occupancy']) / 100.0
        staff = int(request.form['staff'])

        patient_id = random.randint(90000, 99999)
        admission_time = f"{date} {random.randint(8,18)}:00:00"

        conn = sqlite3.connect('medops_data.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO hospital_operations
            (Date, Hospital_ID, Ward, ER_Wait_Time, Bed_Occupancy_Rate, Staff_Count,
             Patient_ID, Anomaly_Flag, Anomaly_Type, Admission_Time, Anomaly_Context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, hospital, ward, wait_time, occupancy, staff,
              patient_id, 0, 'None', admission_time, 'Manual Entry'))
        conn.commit()
        conn.close()

        flash(f"Data for {hospital} - {ward} successfully added!", "success")
        return redirect(url_for('add_data'))

    return render_template('add_data.html', today=datetime.date.today().strftime("%Y-%m-%d"))

@app.route('/chat')
def chat():
    return render_template('chat.html')

# ---------------- API ---------------- #

@app.route('/api/data')
def get_data():
    raw_df = ml_engine.load_data()
    city_gen_df = raw_df[raw_df['Hospital_ID'] == 'City_General']
    if city_gen_df.empty:
        city_gen_df = raw_df

    daily_df = ml_engine.process_daily_metrics(city_gen_df).tail(14)
    daily_df['Patient_Per_Staff'] = (
        daily_df['Total_Admissions'] / daily_df['Avg_Staff'].replace(0, 1)
    ).round(2)
    ward_counts = city_gen_df['Ward'].value_counts().to_dict()

    anomalies = ml_engine.get_latest_anomalies(raw_df)
    latest_anomaly = anomalies.iloc[0].to_dict() if not anomalies.empty else None

    try:
        model = ml_engine.train_prediction_model(raw_df)
        pred_wait = round(
            model.predict(
                pd.DataFrame([[0.85, 30]], columns=['Bed_Occupancy_Rate', 'Staff_Count'])
            )[0], 1
        )
    except Exception as e:
        print(f"ML Error: {e}")
        pred_wait = "N/A"

    return jsonify({
        "dates": daily_df['Date'].tolist(),
        "admissions": daily_df['Total_Admissions'].tolist(),
        "wait_times": daily_df['Avg_Wait_Time'].tolist(),
        "occupancy": daily_df['Avg_Occupancy'].tolist(),
        "staff_ratio": daily_df['Patient_Per_Staff'].tolist(),
        "ward_labels": list(ward_counts.keys()),
        "ward_values": [int(v) for v in ward_counts.values()],
        "latest_anomaly": latest_anomaly,
        "prediction": {"expected_wait_time": pred_wait}
    })

@app.route('/api/recommendation', methods=['POST'])
def get_recommendation():
    if not gemini_api_configured:
        return jsonify({"recommendation": "⚠️ API Key missing."})

    data = request.json
    prompt = f"""Hospital Critical Alert at {data.get('Hospital_ID')} ({data.get('Ward')} Ward).
Context: {data.get('Anomaly_Context')}.
Event: {data.get('Anomaly_Type')}.
Current ER Wait Time: {data.get('ER_Wait_Time')} mins.
Provide 3 brief operational commands in HTML <ul><li> format."""

    result = generate(prompt)
    if result:
        clean_html = re.sub(r'```(?:html)?\n?|```', '', result).strip()
        return jsonify({"recommendation": clean_html})

    return jsonify({"recommendation": "⚠️ AI Error: Models unavailable."})

@app.route('/api/chat', methods=['POST'])
def chat_with_data():
    if not gemini_api_configured:
        return jsonify({"reply": "⚠️ AI offline."})

    user_msg = request.json.get("message")
    schema = """
    Table: hospital_operations
    Columns: Date, Hospital_ID, Ward, ER_Wait_Time,
    Bed_Occupancy_Rate, Staff_Count, Patient_ID, Anomaly_Flag
    """

    try:
        # Step 1: Generate SQL
        sql_prompt = f"Schema:\n{schema}\nWrite only a valid SQLite SQL query for: {user_msg}\nNo explanation, no markdown."
        sql_query = generate(sql_prompt)
        if not sql_query:
            return jsonify({"reply": "⚠️ Could not generate SQL query."})

        sql_query = re.sub(r'```sql\n?|```', '', sql_query).strip()

        # Step 2: Run query
        conn = sqlite3.connect('medops_data.db')
        df_result = pd.read_sql_query(sql_query, conn)
        conn.close()

        data_string = df_result.head(10).to_string(index=False) if not df_result.empty else "No data found."

        # Step 3: Explain results
        final_prompt = f"User asked: {user_msg}\nQuery results:\n{data_string}\nExplain these results simply and concisely."
        final_response = generate(final_prompt)

        return jsonify({"reply": final_response or "⚠️ Could not generate explanation."})

    except Exception as e:
        print(f"Chat Error: {e}")
        # Graceful fallback — answer without DB
        fallback = generate(user_msg)
        return jsonify({"reply": fallback or "⚠️ Error processing your request."})

# ---------------- RUN ---------------- #

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
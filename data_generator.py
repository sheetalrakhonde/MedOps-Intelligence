import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import sqlite3

# --- Hospital Configurations ---
hospitals = {
    'City_General': {'wards': ['ICU','ER','General'], 'beds':[50,60,150], 'staff_ratio': 0.15, 'inventory_base': 100},
    'Metro_Trauma': {'wards': ['ICU','ER','General'], 'beds':[80,100,200], 'staff_ratio': 0.18, 'inventory_base': 150},
    'Community_Clinic': {'wards': ['ICU','ER','General'], 'beds':[10,15,40], 'staff_ratio': 0.12, 'inventory_base': 50}
}

shifts = ['Morning', 'Evening', 'Night']
days_to_simulate = 30
admission_id = 1
patient_id = 1000
data_rows = []

def get_daily_demand(ward, hosp_name):
    base = 10 if hosp_name == 'Community_Clinic' else 50
    if ward == 'ER': return random.randint(base, base*2)
    if ward == 'ICU': return random.randint(5, 20)
    return random.randint(20, 60)

def inject_anomaly(prob=0.1):
    return np.random.rand() < prob

print("Generating advanced patient-level hospital data...")
for day in range(days_to_simulate):
    current_date = datetime(2026, 1, day + 1)
    
    for hosp_name, config in hospitals.items():
        for ward_idx, ward in enumerate(config['wards']):
            beds_total = config['beds'][ward_idx]
            inventory_base = config['inventory_base']
            patients_today = get_daily_demand(ward, hosp_name)
            
            expected_staff = max(2, int(beds_total * config['staff_ratio']))
            staff_count = expected_staff - (random.randint(0, 2) if inject_anomaly(0.05) else 0)
            
            inventory_level = inventory_base + random.randint(-10, 20)
            if inject_anomaly(0.05): inventory_level += random.randint(-50, -20)
            
            er_surge = inject_anomaly(0.05) and ward=='ER'
            
            for _ in range(patients_today + (20 if er_surge else 0)):
                shift = random.choice(shifts)
                h = random.randint(0, 23)
                m = random.randint(0, 59)
                adm_time = current_date.replace(hour=h, minute=m).strftime('%Y-%m-%d %H:%M:%S')
                date_only = current_date.strftime('%Y-%m-%d')
                
                bed_occupancy = min(1.0, patients_today / beds_total)
                pts_per_staff = patients_today / max(1, staff_count)
                
                anomaly_flag = 0
                anomaly_type = 'None'
                cleaning_time = random.randint(20, 40)
                
                if inject_anomaly(0.1) or er_surge:
                    anomaly_flag = 1
                    anomaly_type = random.choice(['Staff Shortage', 'Turnover Delay', 'Resource Spike', 'ER Surge', 'Inventory Shortage'])
                    cleaning_time += random.randint(40, 100)
                    inventory_level -= random.randint(5,20)
                
                er_wait = int(20 * bed_occupancy + (10 * pts_per_staff))
                if anomaly_flag: er_wait += random.randint(30, 90)
                
                day_name = current_date.strftime('%A')
                is_weekend = 1 if day_name in ['Saturday','Sunday'] else 0
                
                predicted_er_wait = er_wait + random.randint(-5,10)
                suggested_staff_reallocation = f"Redistribute {random.randint(1,3)} staff" if anomaly_flag else "None"
                anomaly_context = f"{anomaly_type} in {ward}, Bed Occupancy: {bed_occupancy:.2f}, Staff: {staff_count}, Inventory: {inventory_level}"
                
                data_rows.append([
                    date_only, hosp_name, ward, shift, patient_id, admission_id,
                    adm_time, er_wait, beds_total, bed_occupancy,
                    staff_count, pts_per_staff, cleaning_time,
                    inventory_level, anomaly_flag, anomaly_type,
                    day_name, is_weekend, predicted_er_wait,
                    suggested_staff_reallocation, anomaly_context
                ])
                admission_id += 1; patient_id += 1

cols = ['Date', 'Hospital_ID','Ward','Shift','Patient_ID','Admission_ID', 'Admission_Time','ER_Wait_Time','Beds_Total','Bed_Occupancy_Rate', 'Staff_Count','Patient_Per_Staff','Cleaning_Duration', 'Inventory_Level','Anomaly_Flag','Anomaly_Type', 'Day_of_Week','Is_Weekend','Predicted_ER_Wait', 'Suggested_Staff_Reallocation','Anomaly_Context']
df = pd.DataFrame(data_rows, columns=cols)

# Save to SQLite Database
conn = sqlite3.connect('medops_data.db')
df.to_sql('hospital_operations', conn, if_exists='replace', index=False)
conn.commit()
conn.close()
print(f"✅ Generated {len(df)} records and saved to SQLite!")
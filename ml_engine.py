import pandas as pd
import sqlite3
from sklearn.linear_model import LinearRegression

def load_data():
    conn = sqlite3.connect('medops_data.db')
    df = pd.read_sql_query("SELECT * FROM hospital_operations", conn)
    conn.close()
    return df

def process_daily_metrics(df):
    """Aggregates granular patient data into daily hospital metrics for charts."""
    daily_df = df.groupby(['Date', 'Hospital_ID']).agg(
        Total_Admissions=('Patient_ID', 'count'),
        Avg_Wait_Time=('ER_Wait_Time', 'mean'),
        Max_Wait_Time=('ER_Wait_Time', 'max'),
        Avg_Occupancy=('Bed_Occupancy_Rate', 'mean'),
        Avg_Staff=('Staff_Count', 'mean')
    ).reset_index()
    
    # Round metrics
    daily_df['Avg_Wait_Time'] = daily_df['Avg_Wait_Time'].round(1)
    daily_df['Avg_Occupancy'] = (daily_df['Avg_Occupancy'] * 100).round(1) # Convert to %
    return daily_df

def get_latest_anomalies(df):
    """Fetches the most recent flagged anomalies from the new dataset."""
    anomalies = df[df['Anomaly_Flag'] == 1].sort_values(by='Admission_Time', ascending=False)
    return anomalies

def train_prediction_model(df):
    """Predict Wait Time based on Occupancy and Staff."""
    df_clean = df.dropna(subset=['Bed_Occupancy_Rate', 'Staff_Count', 'ER_Wait_Time'])
    X = df_clean[['Bed_Occupancy_Rate', 'Staff_Count']]
    y = df_clean['ER_Wait_Time']
    
    model = LinearRegression()
    model.fit(X, y)
    return model
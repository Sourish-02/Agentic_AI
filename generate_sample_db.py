import sqlite3
import pandas as pd
import numpy as np
import os

def generate_suite():
    target_folder = "src"
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    # --- 1. E-Commerce Database (Tests: Pie Charts & Grouping) ---
    # Path: src/ecommerce.db | Table: orders
    df1 = pd.DataFrame({
        "category": ["Electronics", "Clothing", "Home", "Books", "Electronics", "Home"],
        "sales": [4500, 2200, 1800, 900, 5100, "MISSING"],
        "order_date": ["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    })
    conn1 = sqlite3.connect(os.path.join(target_folder, "ecommerce.db"))
    df1.to_sql("orders", conn1, if_exists="replace", index=False)
    conn1.close()

    # --- 2. Crypto Tracker (Tests: Time Series & Volatility) ---
    # Path: src/crypto.db | Table: prices
    dates = pd.date_range(start="2026-03-01", periods=10).strftime('%Y-%m-%d').tolist()
    df2 = pd.DataFrame({
        "token": ["BTC"] * 10,
        "price": [62000, 63500, 61000, 59000, 65000, 68000, 67500, 71000, 69000, 72000],
        "timestamp": dates
    })
    conn2 = sqlite3.connect(os.path.join(target_folder, "crypto.db"))
    df2.to_sql("prices", conn2, if_exists="replace", index=False)
    conn2.close()

    # --- 3. Weather Sensors (Tests: Data Cleaning/NaNs) ---
    # Path: src/weather.db | Table: readings
    df3 = pd.DataFrame({
        "sensor_id": [101, 102, 103, 104, 105],
        "temperature": [22.5, "ERROR_SENSOR", 24.1, 19.8, 25.5],
        "humidity": [45, 50, 48, "NULL", 42]
    })
    conn3 = sqlite3.connect(os.path.join(target_folder, "weather.db"))
    df3.to_sql("readings", conn3, if_exists="replace", index=False)
    conn3.close()

    # --- 4. University Records (Tests: Specific Column Filtering) ---
    # Path: src/university.db | Table: students
    df4 = pd.DataFrame({
        "student_id": ["2025MT11352", "2025MT11353", "2025MT11354"],
        "name": ["Saksham", "Aarav", "Priya"],
        "cgpa": [9.2, 8.5, 9.8],
        "branch": ["MnC", "CSE", "EE"]
    })
    conn4 = sqlite3.connect(os.path.join(target_folder, "university.db"))
    df4.to_sql("students", conn4, if_exists="replace", index=False)
    conn4.close()

    print(f"✅ Four test databases created in '{target_folder}/'")

if __name__ == "__main__":
    generate_suite()
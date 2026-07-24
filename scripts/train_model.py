import os
import sqlite3
import joblib
import duckdb
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error, accuracy_score, classification_report

def train_models():
    print("=" * 60)
    print("Starting Vendor Delivery Lead Time ML Model Training")
    print("=" * 60)

    db_path = "vendor_analytics.db"
    conn = duckdb.connect()

    # Load sample of purchases data along with vendor metrics
    print("\n[1/4] Extracting training dataset from DuckDB purchases...")
    query = """
    SELECT
        p.VendorNumber,
        p.Store,
        p.Classification,
        p.Quantity,
        p.PurchasePrice,
        p.Dollars,
        STRFTIME(CAST(p.PODate AS DATE), '%m') AS POMonth,
        DAYOFWEEK(CAST(p.PODate AS DATE)) AS PODayOfWeek,
        date_diff('day', CAST(p.PODate AS DATE), CAST(p.ReceivingDate AS DATE)) AS ActualLeadTimeDays
    FROM read_csv_auto('data/purchases.csv') p
    WHERE p.PODate IS NOT NULL 
      AND p.ReceivingDate IS NOT NULL
      AND p.Quantity > 0 
      AND p.Dollars > 0
    USING SAMPLE 100000 (reservoir)
    """
    df = conn.execute(query).df()
    print(f"Sampled {len(df):,} records for ML training.")

    # Load vendor historical summary metrics to join features
    sqlite_conn = sqlite3.connect(db_path)
    df_vendor = pd.read_sql("SELECT VendorNumber, AvgLeadTimeDays, LateDeliveryRate, VPIScore FROM vendor_summary", sqlite_conn)
    sqlite_conn.close()

    df = df.merge(df_vendor, on='VendorNumber', how='left')
    df.fillna({
        'AvgLeadTimeDays': 7.5,
        'LateDeliveryRate': 5.0,
        'VPIScore': 70.0,
        'POMonth': 1,
        'PODayOfWeek': 1
    }, inplace=True)

    df['POMonth'] = df['POMonth'].astype(int)
    df['PODayOfWeek'] = df['PODayOfWeek'].astype(int)

    # Target 1: Lead Time Days (Regression)
    # Filter out extreme anomalies (> 60 days)
    df = df[(df['ActualLeadTimeDays'] >= 0) & (df['ActualLeadTimeDays'] <= 60)]

    # Target 2: Delay Flag (1 if lead time > 10 days, else 0)
    df['IsDelayed'] = (df['ActualLeadTimeDays'] > 10).astype(int)

    feature_cols = [
        'VendorNumber', 'Store', 'Classification', 'Quantity',
        'PurchasePrice', 'Dollars', 'POMonth', 'PODayOfWeek',
        'AvgLeadTimeDays', 'LateDeliveryRate', 'VPIScore'
    ]

    X = df[feature_cols]
    y_reg = df['ActualLeadTimeDays']
    y_cls = df['IsDelayed']

    # Train Test Split
    X_train, X_test, y_reg_train, y_reg_test, y_cls_train, y_cls_test = train_test_split(
        X, y_reg, y_cls, test_size=0.2, random_state=42
    )

    print("\n[2/4] Training Lead Time Regression Model (HistGradientBoostingRegressor)...")
    reg_model = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.08, random_state=42)
    reg_model.fit(X_train, y_reg_train)

    reg_preds = reg_model.predict(X_test)
    r2 = r2_score(y_reg_test, reg_preds)
    mae = mean_absolute_error(y_reg_test, reg_preds)
    rmse = np.sqrt(mean_squared_error(y_reg_test, reg_preds))

    print(f"  Regression Results:")
    print(f"    R² Score: {r2:.4f}")
    print(f"    MAE:      {mae:.2f} days")
    print(f"    RMSE:     {rmse:.2f} days")

    print("\n[3/4] Training Delay Classification Model (HistGradientBoostingClassifier)...")
    cls_model = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, random_state=42)
    cls_model.fit(X_train, y_cls_train)

    cls_preds = cls_model.predict(X_test)
    acc = accuracy_score(y_cls_test, cls_preds)
    print(f"  Classification Results:")
    print(f"    Accuracy: {acc:.4f}")

    print("\n[4/4] Saving models to `models/vendor_lead_time_model.pkl`...")
    os.makedirs('models', exist_ok=True)
    model_artifact = {
        'reg_model': reg_model,
        'cls_model': cls_model,
        'feature_cols': feature_cols,
        'metrics': {
            'r2': float(r2),
            'mae': float(mae),
            'rmse': float(rmse),
            'accuracy': float(acc)
        }
    }
    joblib.dump(model_artifact, 'models/vendor_lead_time_model.pkl')
    print("[OK] Machine Learning model artifact saved successfully!")
    print("=" * 60)

if __name__ == '__main__':
    train_models()

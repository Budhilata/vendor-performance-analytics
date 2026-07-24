import os
import json
import sqlite3
import joblib
import pandas as pd
import numpy as np
from flask import Flask, render_template, jsonify, request

app = Flask(__name__, template_folder='templates', static_folder='static')

DB_PATH = "vendor_analytics.db"
MODEL_PATH = "models/vendor_lead_time_model.pkl"

# Global model artifact cache
model_artifact = None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_model():
    global model_artifact
    if os.path.exists(MODEL_PATH) and model_artifact is None:
        try:
            model_artifact = joblib.load(MODEL_PATH)
            print("Loaded trained ML model artifact successfully.")
        except Exception as e:
            print(f"Could not load ML model: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/summary')
def get_summary():
    try:
        with open('static/data/exec_summary.json', 'r') as f:
            data = json.load(f)
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/vendors')
def get_vendors():
    try:
        tier_filter = request.args.get('tier', 'all')
        search_query = request.args.get('search', '').strip().lower()
        sort_by = request.args.get('sort_by', 'TotalSpendDollars')

        conn = get_db_connection()
        df = pd.read_sql("SELECT * FROM vendor_summary", conn)
        conn.close()

        if tier_filter != 'all':
            df = df[df['VendorTier'].str.lower().str.contains(tier_filter.lower())]

        if search_query:
            df = df[
                df['VendorName'].str.lower().str.contains(search_query) |
                df['VendorNumber'].astype(str).str.contains(search_query)
            ]

        valid_sorts = ['TotalSpendDollars', 'VPIScore', 'AvgLeadTimeDays', 'GrossMarginPct', 'FreightRatioPct']
        if sort_by in valid_sorts:
            ascending = True if sort_by in ['AvgLeadTimeDays', 'FreightRatioPct'] else False
            df.sort_values(by=sort_by, ascending=ascending, inplace=True)

        return jsonify({
            'status': 'success',
            'count': len(df),
            'vendors': df.to_dict(orient='records')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/vendor/<int:vendor_id>')
def get_vendor_detail(vendor_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_summary WHERE VendorNumber = ?", (vendor_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Vendor not found'}), 404
        
        vendor_info = dict(row)

        # Fetch top brands for this vendor
        brands = pd.read_sql(
            "SELECT * FROM top_brands WHERE VendorNumber = ? ORDER BY TotalSpendDollars DESC LIMIT 10",
            conn, params=[vendor_id]
        ).to_dict(orient='records')

        conn.close()
        return jsonify({
            'status': 'success',
            'vendor': vendor_info,
            'brands': brands
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/analytics/charts')
def get_charts():
    try:
        conn = get_db_connection()
        df_summary = pd.read_sql("SELECT * FROM vendor_summary", conn)
        df_monthly = pd.read_sql("SELECT * FROM monthly_trends", conn)
        conn.close()

        # Top 10 Spend Vendors
        top10_spend = df_summary.sort_values('TotalSpendDollars', ascending=False).head(10)
        top10_spend_data = {
            'labels': top10_spend['VendorName'].tolist(),
            'spend': top10_spend['TotalSpendDollars'].tolist(),
            'revenue': top10_spend['TotalSalesDollars'].tolist()
        }

        # Lead Time Distribution Bins (0-5 days, 6-10 days, 11-15 days, 15+ days)
        lead_times = df_summary['AvgLeadTimeDays']
        lt_bins = {
            '1-5 Days': int((lead_times <= 5).sum()),
            '6-8 Days': int(((lead_times > 5) & (lead_times <= 8)).sum()),
            '9-12 Days': int(((lead_times > 8) & (lead_times <= 12)).sum()),
            '13+ Days': int((lead_times > 12).sum())
        }

        # Tier breakdown
        tier_counts = df_summary['VendorTier'].value_counts().to_dict()

        # Scatter plot data: Gross Margin % vs Lead Time
        scatter_data = df_summary[['VendorName', 'GrossMarginPct', 'AvgLeadTimeDays', 'TotalSpendDollars', 'VPIScore']].to_dict(orient='records')

        return jsonify({
            'status': 'success',
            'data': {
                'top10_spend': top10_spend_data,
                'monthly_trends': df_monthly.to_dict(orient='records'),
                'lead_time_dist': lt_bins,
                'tier_counts': tier_counts,
                'scatter_data': scatter_data
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        load_model()
        payload = request.get_json() or {}

        vendor_number = int(payload.get('vendor_number', 12546))
        store = int(payload.get('store', 1))
        classification = int(payload.get('classification', 1))
        quantity = float(payload.get('quantity', 100))
        purchase_price = float(payload.get('purchase_price', 15.0))
        dollars = float(payload.get('dollars', quantity * purchase_price))
        po_month = int(payload.get('po_month', 6))
        po_day_of_week = int(payload.get('po_day_of_week', 2))

        # Lookup vendor historical metrics
        avg_lt = 7.5
        late_rate = 5.0
        vpi_score = 70.0

        if os.path.exists(DB_PATH):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT AvgLeadTimeDays, LateDeliveryRate, VPIScore FROM vendor_summary WHERE VendorNumber = ?", (vendor_number,))
            res = cursor.fetchone()
            conn.close()
            if res:
                avg_lt = float(res['AvgLeadTimeDays'])
                late_rate = float(res['LateDeliveryRate'])
                vpi_score = float(res['VPIScore'])

        # Prepare feature vector
        features = pd.DataFrame([{
            'VendorNumber': vendor_number,
            'Store': store,
            'Classification': classification,
            'Quantity': quantity,
            'PurchasePrice': purchase_price,
            'Dollars': dollars,
            'POMonth': po_month,
            'PODayOfWeek': po_day_of_week,
            'AvgLeadTimeDays': avg_lt,
            'LateDeliveryRate': late_rate,
            'VPIScore': vpi_score
        }])

        if model_artifact:
            reg_model = model_artifact['reg_model']
            cls_model = model_artifact['cls_model']

            pred_days = float(reg_model.predict(features)[0])
            pred_days = max(1.0, round(pred_days, 1))

            prob_delay = float(cls_model.predict_proba(features)[0][1] * 100.0)
        else:
            # Rule based heuristic fallback
            pred_days = round(avg_lt + (0.0001 * quantity), 1)
            prob_delay = min(95.0, round(late_rate + (pred_days * 3), 1))

        if prob_delay > 60.0 or pred_days > 12.0:
            risk_level = "HIGH RISK"
            badge_class = "risk-high"
            rec = "Order placement requires expedited shipping buffer and vendor follow-up. Consider safety stock allocation."
        elif prob_delay > 30.0 or pred_days > 8.0:
            risk_level = "MODERATE RISK"
            badge_class = "risk-medium"
            rec = "Standard monitoring recommended. Lead time matches vendor baseline."
        else:
            risk_level = "LOW RISK"
            badge_class = "risk-low"
            rec = "Optimal delivery conditions expected. High confidence on-time fulfillment."

        return jsonify({
            'status': 'success',
            'prediction': {
                'predicted_lead_time_days': pred_days,
                'delay_probability_pct': round(prob_delay, 1),
                'risk_level': risk_level,
                'badge_class': badge_class,
                'recommendation': rec,
                'inputs': {
                    'vendor_number': vendor_number,
                    'store': store,
                    'quantity': quantity,
                    'total_dollars': dollars,
                    'vendor_historical_avg_lt': round(avg_lt, 1)
                }
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    load_model()
    app.run(host='0.0.0.0', port=5000, debug=True)

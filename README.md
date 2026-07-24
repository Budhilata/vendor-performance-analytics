# 📊 Vendor Performance Data Analytics & AI Intelligence System

An end-to-end enterprise data science and analytics application for **Vendor Performance Management**, processing **15.4M+ retail transaction records** using DuckDB, SQLite, Scikit-Learn, and Flask.

---

## 🌟 Key Features

- **⚡ High-Performance DuckDB ETL**: Aggregates 15.4M records across sales, purchases, invoices, and inventory snapshots in seconds.
- **📈 Comprehensive Vendor KPIs**: Calculates total spend, retail revenue, gross profit margins %, fulfillment lead times, freight efficiency ratios, and Days Sales of Inventory (DSI).
- **🏆 Multi-Criteria Scorecard & Tiering**: Computes the **Vendor Performance Index (VPI)** (0-100) and classifies vendors into Tier 1 (Strategic) to Tier 4 (High Risk).
- **🤖 Machine Learning Lead Time & Delay Predictor**: Trained `HistGradientBoosting` model forecasting delivery lead time (MAE: 1.09 days) and shipment delay risk (91.06% accuracy).
- **💻 Interactive Executive Web Dashboard**: Real-time KPI cards, interactive Chart.js analytics, vendor search/sorting, vendor scorecard slide-over modal, and live AI delay simulator.

---

## 📁 Project Structure

```
project data science/
├── app.py                      # Flask REST API Server
├── requirements.txt            # Python Package Dependencies
├── README.md                   # Project Documentation
├── vendor_analytics.db         # Processed SQLite Analytics Database
├── models/
│   └── vendor_lead_time_model.pkl # Trained Machine Learning Model Artifact
├── scripts/
│   ├── etl_pipeline.py         # DuckDB/SQLite Data Pipeline Script
│   └── train_model.py          # Machine Learning Training Script
├── static/
│   ├── css/styles.css          # Executive Dark Mode CSS Design System
│   ├── js/main.js              # Interactive Dashboard Logic & Chart.js
│   └── data/                   # JSON Metric Caches
└── templates/
    └── index.html              # HTML5 Web Application Layout
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Open Web Dashboard
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## ⚙️ Data Pipeline & ML Re-training (Optional)

If you modify or update raw dataset CSV files:

```bash
# 1. Run Data ETL Pipeline
python scripts/etl_pipeline.py

# 2. Re-train Machine Learning Models
python scripts/train_model.py
```

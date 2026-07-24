import os
import sys
import json
import sqlite3
import duckdb
import pandas as pd
import numpy as np

def run_etl():
    print("=" * 60)
    print("Starting Vendor Analytics ETL Pipeline with DuckDB & SQLite")
    print("=" * 60)

    db_path = "vendor_analytics.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"Removed old database {db_path}")
        except Exception as e:
            print(f"Could not remove old DB: {e}")

    conn = duckdb.connect()

    # 1. Register CSV views in DuckDB
    print("\n[1/6] Indexing CSV datasets into DuckDB memory engine...")
    conn.execute("CREATE VIEW purchases AS SELECT * FROM read_csv_auto('data/purchases.csv')")
    conn.execute("CREATE VIEW vendor_invoice AS SELECT * FROM read_csv_auto('data/vendor_invoice.csv')")
    conn.execute("CREATE VIEW sales AS SELECT * FROM read_csv_auto('data/sales.csv')")
    conn.execute("CREATE VIEW begin_inventory AS SELECT * FROM read_csv_auto('data/begin_inventory.csv')")
    conn.execute("CREATE VIEW end_inventory AS SELECT * FROM read_csv_auto('data/end_inventory.csv')")
    conn.execute("CREATE VIEW purchase_prices AS SELECT * FROM read_csv_auto('data/purchase_prices.csv')")
    print("[OK] CSV views created successfully.")

    # 2. Aggregating Purchase Metrics per Vendor
    print("\n[2/6] Calculating Purchasing & Delivery Lead Time metrics...")
    purchase_metrics_sql = """
    SELECT
        VendorNumber,
        MAX(VendorName) AS VendorName,
        COUNT(DISTINCT PONumber) AS TotalPOs,
        COUNT(*) AS TotalPurchaseRecords,
        SUM(Quantity) AS TotalUnitsPurchased,
        SUM(Dollars) AS TotalSpendDollars,
        AVG(PurchasePrice) AS AvgPurchaseUnitPrice,
        AVG(date_diff('day', CAST(PODate AS DATE), CAST(ReceivingDate AS DATE))) AS AvgLeadTimeDays,
        MAX(date_diff('day', CAST(PODate AS DATE), CAST(ReceivingDate AS DATE))) AS MaxLeadTimeDays,
        MIN(date_diff('day', CAST(PODate AS DATE), CAST(ReceivingDate AS DATE))) AS MinLeadTimeDays,
        STDDEV_SAMP(date_diff('day', CAST(PODate AS DATE), CAST(ReceivingDate AS DATE))) AS StdLeadTimeDays,
        SUM(CASE WHEN date_diff('day', CAST(PODate AS DATE), CAST(ReceivingDate AS DATE)) > 10 THEN 1 ELSE 0 END) AS LateDeliveriesCount
    FROM purchases
    WHERE PODate IS NOT NULL AND ReceivingDate IS NOT NULL
    GROUP BY VendorNumber
    """
    df_purchases = conn.execute(purchase_metrics_sql).df()
    df_purchases['LateDeliveryRate'] = np.where(
        df_purchases['TotalPurchaseRecords'] > 0,
        (df_purchases['LateDeliveriesCount'] / df_purchases['TotalPurchaseRecords']) * 100,
        0
    )

    # 3. Aggregating Freight & Invoice Metrics per Vendor
    print("\n[3/6] Calculating Invoice & Freight efficiency metrics...")
    invoice_metrics_sql = """
    SELECT
        VendorNumber,
        SUM(Freight) AS TotalFreightDollars,
        SUM(Dollars) AS TotalInvoiceDollars,
        AVG(date_diff('day', CAST(InvoiceDate AS DATE), CAST(PayDate AS DATE))) AS AvgPaymentLeadTimeDays
    FROM vendor_invoice
    WHERE InvoiceDate IS NOT NULL AND PayDate IS NOT NULL
    GROUP BY VendorNumber
    """
    df_invoices = conn.execute(invoice_metrics_sql).df()

    # 4. Aggregating Sales Revenue & Profit Metrics per Vendor
    print("\n[4/6] Aggregating Sales Revenue & Gross Margin metrics...")
    sales_metrics_sql = """
    SELECT
        VendorNo AS VendorNumber,
        SUM(SalesQuantity) AS TotalUnitsSold,
        SUM(SalesDollars) AS TotalSalesDollars,
        AVG(SalesPrice) AS AvgSalesUnitPrice,
        SUM(ExciseTax) AS TotalExciseTaxDollars
    FROM sales
    GROUP BY VendorNo
    """
    df_sales = conn.execute(sales_metrics_sql).df()

    # 5. Inventory Metrics per Vendor
    print("\n[5/6] Aggregating Beginning & Ending Inventory snapshots...")
    inv_begin_sql = """
    SELECT
        pp.VendorNumber,
        SUM(b.onHand) AS BeginInventoryUnits,
        SUM(b.onHand * b.Price) AS BeginInventoryValue
    FROM begin_inventory b
    JOIN purchase_prices pp ON b.Brand = pp.Brand
    GROUP BY pp.VendorNumber
    """
    df_inv_begin = conn.execute(inv_begin_sql).df()

    inv_end_sql = """
    SELECT
        pp.VendorNumber,
        SUM(e.onHand) AS EndInventoryUnits,
        SUM(e.onHand * e.Price) AS EndInventoryValue
    FROM end_inventory e
    JOIN purchase_prices pp ON e.Brand = pp.Brand
    GROUP BY pp.VendorNumber
    """
    df_inv_end = conn.execute(inv_end_sql).df()

    # Merge all vendor metric DataFrames
    print("\nMerging vendor data pipelines into master dataframe...")
    master_df = df_purchases.merge(df_invoices, on='VendorNumber', how='left')
    master_df = master_df.merge(df_sales, on='VendorNumber', how='left')
    master_df = master_df.merge(df_inv_begin, on='VendorNumber', how='left')
    master_df = master_df.merge(df_inv_end, on='VendorNumber', how='left')

    # Fill NaNs with defaults
    master_df.fillna({
        'TotalFreightDollars': 0,
        'TotalInvoiceDollars': 0,
        'AvgPaymentLeadTimeDays': 0,
        'TotalUnitsSold': 0,
        'TotalSalesDollars': 0,
        'AvgSalesUnitPrice': 0,
        'TotalExciseTaxDollars': 0,
        'BeginInventoryUnits': 0,
        'BeginInventoryValue': 0,
        'EndInventoryUnits': 0,
        'EndInventoryValue': 0,
        'StdLeadTimeDays': 0,
        'AvgLeadTimeDays': 7.0
    }, inplace=True)

    # Derived KPIs
    master_df['GrossProfitDollars'] = master_df['TotalSalesDollars'] - master_df['TotalSpendDollars']
    master_df['GrossMarginPct'] = np.where(
        master_df['TotalSalesDollars'] > 0,
        (master_df['GrossProfitDollars'] / master_df['TotalSalesDollars']) * 100,
        0
    )
    master_df['FreightRatioPct'] = np.where(
        master_df['TotalSpendDollars'] > 0,
        (master_df['TotalFreightDollars'] / master_df['TotalSpendDollars']) * 100,
        0
    )

    # Avg Inventory & Inventory Turnover
    master_df['AvgInventoryValue'] = (master_df['BeginInventoryValue'] + master_df['EndInventoryValue']) / 2.0
    master_df['InventoryTurnoverRatio'] = np.where(
        master_df['AvgInventoryValue'] > 0,
        master_df['TotalSpendDollars'] / master_df['AvgInventoryValue'],
        0
    )
    master_df['DaysSalesOfInventory'] = np.where(
        master_df['InventoryTurnoverRatio'] > 0,
        365.0 / master_df['InventoryTurnoverRatio'],
        999.0
    )

    # 6. Composite Vendor Performance Index (VPI) calculation
    # Normalized components (0 to 100)
    # Lead time score: penalty for avg lead time > 5 days and late delivery rate
    lead_time_score = np.clip(100 - (master_df['AvgLeadTimeDays'] * 5 + master_df['LateDeliveryRate'] * 0.5), 0, 100)
    
    # Margin score: higher gross margin % up to 40%
    margin_score = np.clip(master_df['GrossMarginPct'] * 2.5, 0, 100)
    
    # Freight ratio score: penalty for freight ratio > 1%
    freight_score = np.clip(100 - (master_df['FreightRatioPct'] * 30), 0, 100)
    
    # Volume & Turnover score: scaled by spend and turnover
    spend_log = np.log10(np.maximum(master_df['TotalSpendDollars'], 1))
    volume_score = np.clip((spend_log / 8.0) * 100, 0, 100)

    # Weighted VPI Score (0 - 100)
    master_df['VPIScore'] = (
        lead_time_score * 0.30 +
        margin_score * 0.30 +
        freight_score * 0.20 +
        volume_score * 0.20
    ).round(1)

    # Tier Assignment
    def assign_tier(vpi):
        if vpi >= 80.0:
            return "Tier 1: Strategic"
        elif vpi >= 68.0:
            return "Tier 2: Preferred"
        elif vpi >= 55.0:
            return "Tier 3: Moderate Risk"
        else:
            return "Tier 4: High Risk"

    master_df['VendorTier'] = master_df['VPIScore'].apply(assign_tier)

    # Sort master dataframe by Total Spend descending
    master_df.sort_values(by='TotalSpendDollars', ascending=False, inplace=True)

    # 7. Additional Aggregations: Monthly Trends
    print("\n[6/6] Generating Monthly Trends & Brand level analytical tables...")
    monthly_trends_sql = """
    SELECT
        STRFTIME(CAST(PODate AS DATE), '%Y-%m') AS YearMonth,
        COUNT(DISTINCT VendorNumber) AS ActiveVendors,
        SUM(Quantity) AS MonthlyPurchasedUnits,
        SUM(Dollars) AS MonthlySpendDollars,
        AVG(date_diff('day', CAST(PODate AS DATE), CAST(ReceivingDate AS DATE))) AS MonthlyAvgLeadTime
    FROM purchases
    WHERE PODate IS NOT NULL AND PODate >= '2024-01-01' AND PODate <= '2024-12-31'
    GROUP BY 1
    ORDER BY YearMonth
    """
    df_monthly = conn.execute(monthly_trends_sql).df()

    # Brand level summary
    brand_sql = """
    SELECT
        Brand,
        MAX(Description) AS Description,
        MAX(VendorName) AS VendorName,
        MAX(VendorNumber) AS VendorNumber,
        SUM(Quantity) AS TotalPurchasedUnits,
        SUM(Dollars) AS TotalSpendDollars,
        AVG(PurchasePrice) AS AvgPurchasePrice
    FROM purchases
    GROUP BY Brand
    ORDER BY TotalSpendDollars DESC
    LIMIT 100
    """
    df_brands = conn.execute(brand_sql).df()

    # 8. Save to SQLite database and JSON cache files
    print("\nSaving tables to SQLite `vendor_analytics.db`...")
    sqlite_conn = sqlite3.connect(db_path)
    master_df.to_sql('vendor_summary', sqlite_conn, if_exists='replace', index=False)
    df_monthly.to_sql('monthly_trends', sqlite_conn, if_exists='replace', index=False)
    df_brands.to_sql('top_brands', sqlite_conn, if_exists='replace', index=False)
    sqlite_conn.close()

    # Export json cache for instant Web app loading
    os.makedirs('static/data', exist_ok=True)

    master_json = master_df.to_dict(orient='records')
    with open('static/data/vendor_summary.json', 'w') as f:
        json.dump(master_json, f, indent=2)

    monthly_json = df_monthly.to_dict(orient='records')
    with open('static/data/monthly_trends.json', 'w') as f:
        json.dump(monthly_json, f, indent=2)

    brands_json = df_brands.to_dict(orient='records')
    with open('static/data/top_brands.json', 'w') as f:
        json.dump(brands_json, f, indent=2)

    # Save executive summary metrics
    exec_summary = {
        'total_vendors': len(master_df),
        'total_spend': float(master_df['TotalSpendDollars'].sum()),
        'total_sales': float(master_df['TotalSalesDollars'].sum()),
        'gross_profit': float(master_df['GrossProfitDollars'].sum()),
        'overall_margin_pct': float((master_df['GrossProfitDollars'].sum() / master_df['TotalSalesDollars'].sum() * 100) if master_df['TotalSalesDollars'].sum() > 0 else 0),
        'avg_lead_time_days': float(master_df['AvgLeadTimeDays'].mean()),
        'total_freight': float(master_df['TotalFreightDollars'].sum()),
        'overall_freight_ratio': float((master_df['TotalFreightDollars'].sum() / master_df['TotalSpendDollars'].sum() * 100) if master_df['TotalSpendDollars'].sum() > 0 else 0),
        'tier_counts': master_df['VendorTier'].value_counts().to_dict()
    }
    with open('static/data/exec_summary.json', 'w') as f:
        json.dump(exec_summary, f, indent=2)

    print("\n" + "=" * 60)
    print("ETL Pipeline completed successfully!")
    print(f"Total Vendors Processed: {len(master_df)}")
    print(f"Total Spend Processed: ${exec_summary['total_spend']:,.2f}")
    print(f"Total Revenue Processed: ${exec_summary['total_sales']:,.2f}")
    print(f"Average Lead Time: {exec_summary['avg_lead_time_days']:.1f} days")
    print("=" * 60)

if __name__ == '__main__':
    run_etl()

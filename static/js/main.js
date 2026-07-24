document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    lucide.createIcons();

    // Global App State
    let allVendorsData = [];
    let chartsInstance = {};

    // 1. Navigation Tab Switcher
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');

    const tabHeadings = {
        'overview': { title: 'Executive Performance Overview', subtitle: 'Real-time vendor KPI tracking, lead time efficiency, and margin intelligence' },
        'directory': { title: 'Vendor Scorecard Directory', subtitle: 'Searchable database of active retail vendors with VPI tiering and spend metrics' },
        'logistics': { title: 'Logistics & Lead Time Analytics', subtitle: 'Delivery fulfillment performance, lead time distributions, and delay rates' },
        'financials': { title: 'Financial Margins & Cost Structure', subtitle: 'Profitability analysis, retail gross margins, and freight efficiency ratios' },
        'simulator': { title: 'AI Delivery Lead Time Predictor', subtitle: 'Machine learning inference simulator for purchase order delay risk evaluation' }
    };

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            navButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetElement = document.getElementById(`tab-${targetTab}`);
            if (targetElement) targetElement.classList.add('active');

            if (tabHeadings[targetTab]) {
                pageTitle.textContent = tabHeadings[targetTab].title;
                pageSubtitle.textContent = tabHeadings[targetTab].subtitle;
            }

            // Resize charts on tab change
            setTimeout(() => {
                Object.values(chartsInstance).forEach(chart => {
                    if (chart) chart.resize();
                });
            }, 100);
        });
    });

    // 2. Fetch Executive Summary KPIs
    async function loadSummaryKPIs() {
        try {
            const res = await fetch('/api/summary');
            const result = await res.json();
            if (result.status === 'success') {
                const d = result.data;
                document.getElementById('kpi-spend').textContent = formatCurrency(d.total_spend);
                document.getElementById('kpi-sales').textContent = formatCurrency(d.total_sales);
                document.getElementById('kpi-margin').textContent = `${d.overall_margin_pct.toFixed(1)}%`;
                document.getElementById('kpi-profit').textContent = `${formatCurrency(d.gross_profit)} Gross Profit`;
                document.getElementById('kpi-leadtime').textContent = `${d.avg_lead_time_days.toFixed(1)} Days`;
            }
        } catch (e) {
            console.error('Error loading summary KPIs:', e);
        }
    }

    // 3. Fetch Analytics & Render Charts
    async function loadAnalyticsCharts() {
        try {
            const res = await fetch('/api/analytics/charts');
            const result = await res.json();
            if (result.status === 'success') {
                const data = result.data;
                renderTopVendorsChart(data.top10_spend);
                renderTiersChart(data.tier_counts);
                renderMonthlyTrendChart(data.monthly_trends);
                renderLeadTimeDistChart(data.lead_time_dist);
                renderMarginScatterChart(data.scatter_data);
            }
        } catch (e) {
            console.error('Error loading charts:', e);
        }
    }

    // 4. Fetch Vendor Directory Table Data
    async function loadVendorDirectory() {
        try {
            const res = await fetch('/api/vendors');
            const result = await res.json();
            if (result.status === 'success') {
                allVendorsData = result.vendors;
                renderVendorTable(allVendorsData);
                populateVendorSelectOptions(allVendorsData);
            }
        } catch (e) {
            console.error('Error loading vendors:', e);
        }
    }

    // Render Table Rows
    function renderVendorTable(vendors) {
        const tbody = document.getElementById('vendor-table-body');
        tbody.innerHTML = '';

        if (vendors.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching vendors found.</td></tr>`;
            return;
        }

        vendors.forEach(v => {
            const tr = document.createElement('tr');
            
            let tierClass = 'badge-tier2';
            if (v.VendorTier.includes('Tier 1')) tierClass = 'badge-tier1';
            else if (v.VendorTier.includes('Tier 3')) tierClass = 'badge-tier3';
            else if (v.VendorTier.includes('Tier 4')) tierClass = 'badge-tier4';

            tr.innerHTML = `
                <td><strong>#${v.VendorNumber}</strong></td>
                <td><strong>${v.VendorName}</strong></td>
                <td><span class="badge ${tierClass}">${v.VendorTier}</span></td>
                <td>
                    <div class="vpi-bar-container">
                        <span><strong>${v.VPIScore}</strong></span>
                        <div class="vpi-bar"><div class="vpi-fill" style="width: ${Math.min(100, v.VPIScore)}%;"></div></div>
                    </div>
                </td>
                <td>${formatCurrency(v.TotalSpendDollars)}</td>
                <td>${formatCurrency(v.TotalSalesDollars)}</td>
                <td><strong>${v.AvgLeadTimeDays.toFixed(1)} days</strong></td>
                <td style="color: ${v.GrossMarginPct >= 25 ? 'var(--accent-emerald)' : 'var(--text-main)'};"><strong>${v.GrossMarginPct.toFixed(1)}%</strong></td>
                <td>${v.FreightRatioPct.toFixed(2)}%</td>
                <td>
                    <button class="btn-view-scorecard" data-id="${v.VendorNumber}">Scorecard</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Add modal trigger events
        document.querySelectorAll('.btn-view-scorecard').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const vid = e.target.getAttribute('data-id');
                openVendorModal(vid);
            });
        });
    }

    // Filter and Sort Table
    const searchInput = document.getElementById('search-vendor');
    const tierFilter = document.getElementById('filter-tier');
    const sortSelect = document.getElementById('sort-vendors');

    function applyTableFilters() {
        const query = searchInput.value.toLowerCase().trim();
        const tier = tierFilter.value;
        const sortBy = sortSelect.value;

        let filtered = allVendorsData.filter(v => {
            const matchesQuery = v.VendorName.toLowerCase().includes(query) || v.VendorNumber.toString().includes(query);
            const matchesTier = (tier === 'all') || v.VendorTier.toLowerCase().includes(tier.toLowerCase());
            return matchesQuery && matchesTier;
        });

        const ascending = ['AvgLeadTimeDays', 'FreightRatioPct'].includes(sortBy);
        filtered.sort((a, b) => ascending ? a[sortBy] - b[sortBy] : b[sortBy] - a[sortBy]);

        renderVendorTable(filtered);
    }

    if (searchInput) searchInput.addEventListener('input', applyTableFilters);
    if (tierFilter) tierFilter.addEventListener('change', applyTableFilters);
    if (sortSelect) sortSelect.addEventListener('change', applyTableFilters);

    // Populate Vendor Select in ML Simulator Form
    function populateVendorSelectOptions(vendors) {
        const select = document.getElementById('sim-vendor');
        if (!select) return;
        select.innerHTML = '';

        vendors.slice(0, 30).forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.VendorNumber;
            opt.textContent = `#${v.VendorNumber} - ${v.VendorName}`;
            select.appendChild(opt);
        });
    }

    // 5. Chart Rendering Functions (Chart.js)
    function renderTopVendorsChart(data) {
        const ctx = document.getElementById('chart-top-vendors').getContext('2d');
        if (chartsInstance['topVendors']) chartsInstance['topVendors'].destroy();

        chartsInstance['topVendors'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels.map(l => l.length > 18 ? l.substring(0, 18) + '...' : l),
                datasets: [
                    {
                        label: 'Total Spend ($)',
                        data: data.spend,
                        backgroundColor: '#6366f1',
                        borderRadius: 4
                    },
                    {
                        label: 'Retail Sales ($)',
                        data: data.revenue,
                        backgroundColor: '#10b981',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
                    y: { ticks: { color: '#94a3b8', callback: v => '$' + (v / 1e6).toFixed(1) + 'M' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });
    }

    function renderTiersChart(counts) {
        const ctx = document.getElementById('chart-tiers').getContext('2d');
        if (chartsInstance['tiers']) chartsInstance['tiers'].destroy();

        chartsInstance['tiers'] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(counts),
                datasets: [{
                    data: Object.values(counts),
                    backgroundColor: ['#818cf8', '#fbbf24', '#f87171', '#34d399'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } }
                },
                cutout: '70%'
            }
        });
    }

    function renderMonthlyTrendChart(trends) {
        const ctx = document.getElementById('chart-monthly-trend').getContext('2d');
        if (chartsInstance['monthly']) chartsInstance['monthly'].destroy();

        chartsInstance['monthly'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: trends.map(t => t.YearMonth),
                datasets: [
                    {
                        type: 'line',
                        label: 'Avg Lead Time (Days)',
                        data: trends.map(t => t.MonthlyAvgLeadTime),
                        borderColor: '#f59e0b',
                        backgroundColor: '#f59e0b',
                        borderWidth: 3,
                        yAxisID: 'y1',
                        tension: 0.3
                    },
                    {
                        type: 'bar',
                        label: 'Monthly Purchasing Spend ($)',
                        data: trends.map(t => t.MonthlySpendDollars),
                        backgroundColor: 'rgba(99, 102, 241, 0.6)',
                        borderRadius: 4,
                        yAxisID: 'y'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#94a3b8' } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
                    y: {
                        position: 'left',
                        ticks: { color: '#94a3b8', callback: v => '$' + (v / 1e6).toFixed(0) + 'M' },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y1: {
                        position: 'right',
                        ticks: { color: '#f59e0b', callback: v => v.toFixed(1) + 'd' },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    function renderLeadTimeDistChart(bins) {
        const ctx = document.getElementById('chart-leadtime-dist').getContext('2d');
        if (chartsInstance['leadTimeDist']) chartsInstance['leadTimeDist'].destroy();

        chartsInstance['leadTimeDist'] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(bins),
                datasets: [{
                    data: Object.values(bins),
                    backgroundColor: ['#10b981', '#6366f1', '#f59e0b', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8' } }
                },
                cutout: '65%'
            }
        });
    }

    function renderMarginScatterChart(scatterData) {
        const ctx = document.getElementById('chart-margin-scatter').getContext('2d');
        if (chartsInstance['marginScatter']) chartsInstance['marginScatter'].destroy();

        const formattedPoints = scatterData.map(d => ({
            x: d.AvgLeadTimeDays,
            y: d.GrossMarginPct,
            vendor: d.VendorName
        }));

        chartsInstance['marginScatter'] = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Vendor Profile (Gross Margin % vs Lead Time Days)',
                    data: formattedPoints,
                    backgroundColor: 'rgba(99, 102, 241, 0.7)',
                    borderColor: '#818cf8',
                    pointRadius: 6,
                    pointHoverRadius: 9
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const pt = context.raw;
                                return `${pt.vendor}: Lead Time ${pt.x.toFixed(1)}d | Gross Margin ${pt.y.toFixed(1)}%`;
                            }
                        }
                    },
                    legend: { labels: { color: '#94a3b8' } }
                },
                scales: {
                    x: { title: { display: true, text: 'Average Delivery Lead Time (Days)', color: '#94a3b8' }, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { title: { display: true, text: 'Gross Profit Margin (%)', color: '#94a3b8' }, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });
    }

    // 6. Vendor Modal Details
    async function openVendorModal(vendorId) {
        const modal = document.getElementById('vendor-modal');
        const modalBody = document.getElementById('modal-body-content');
        modalBody.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem;">Loading scorecard details...</div>`;
        modal.classList.add('show');

        try {
            const res = await fetch(`/api/vendor/${vendorId}`);
            const result = await res.json();
            if (result.status === 'success') {
                const v = result.vendor;
                const brands = result.brands || [];

                document.getElementById('modal-vendor-name').textContent = v.VendorName;
                document.getElementById('modal-vendor-tier').textContent = v.VendorTier;

                let brandsHTML = '';
                brands.forEach(b => {
                    brandsHTML += `
                        <tr>
                            <td>#${b.Brand}</td>
                            <td>${b.Description}</td>
                            <td>${formatCurrency(b.TotalSpendDollars)}</td>
                            <td>$${b.AvgPurchasePrice.toFixed(2)}</td>
                        </tr>
                    `;
                });

                modalBody.innerHTML = `
                    <div class="modal-stat-grid">
                        <div class="modal-stat">
                            <span class="lbl">Total Spend</span>
                            <span class="val">${formatCurrency(v.TotalSpendDollars)}</span>
                        </div>
                        <div class="modal-stat">
                            <span class="lbl">Total Sales</span>
                            <span class="val">${formatCurrency(v.TotalSalesDollars)}</span>
                        </div>
                        <div class="modal-stat">
                            <span class="lbl">Avg Lead Time</span>
                            <span class="val">${v.AvgLeadTimeDays.toFixed(1)} Days</span>
                        </div>
                        <div class="modal-stat">
                            <span class="lbl">VPI Score</span>
                            <span class="val" style="color: var(--accent-indigo);">${v.VPIScore} / 100</span>
                        </div>
                    </div>

                    <div style="margin-top: 1rem;">
                        <h4 style="font-family: var(--font-heading); margin-bottom: 0.75rem;">Top Supplied Brands (${brands.length})</h4>
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Brand ID</th>
                                    <th>Product Description</th>
                                    <th>Purchasing Spend</th>
                                    <th>Avg Unit Cost</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${brandsHTML || '<tr><td colspan="4" style="text-align:center;">No brand breakdown available.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                `;
            }
        } catch (e) {
            modalBody.innerHTML = `<div style="color: var(--accent-rose);">Error loading vendor scorecard detail.</div>`;
        }
    }

    document.getElementById('modal-close-btn').addEventListener('click', () => {
        document.getElementById('vendor-modal').classList.remove('show');
    });

    // 7. Interactive ML Predictor Form
    const simForm = document.getElementById('sim-form');
    if (simForm) {
        simForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const payload = {
                vendor_number: document.getElementById('sim-vendor').value,
                store: document.getElementById('sim-store').value,
                classification: document.getElementById('sim-classification').value,
                quantity: document.getElementById('sim-quantity').value,
                purchase_price: document.getElementById('sim-price').value,
                po_month: document.getElementById('sim-month').value
            };

            const resultBox = document.getElementById('sim-result-box');
            resultBox.innerHTML = `<div class="result-placeholder"><p>Running ML Inference Model...</p></div>`;

            try {
                const res = await fetch('/api/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (data.status === 'success') {
                    const p = data.prediction;
                    resultBox.innerHTML = `
                        <div class="result-output-box">
                            <div class="res-hero">
                                <div class="res-metric">
                                    <span class="res-label">Predicted Delivery Lead Time</span>
                                    <span class="res-value">${p.predicted_lead_time_days} Days</span>
                                </div>
                                <div class="res-metric">
                                    <span class="res-label">Delay Risk Assessment</span>
                                    <span class="badge ${p.badge_class}" style="font-size: 0.9rem; padding: 0.4rem 0.85rem;">${p.risk_level} (${p.delay_probability_pct}% Delay Prob)</span>
                                </div>
                            </div>

                            <div class="rec-box">
                                <div class="rec-title">
                                    <i data-lucide="cpu"></i> ML Model Logistics Recommendation
                                </div>
                                <div class="rec-body">${p.recommendation}</div>
                            </div>
                        </div>
                    `;
                    lucide.createIcons();
                }
            } catch (err) {
                resultBox.innerHTML = `<div style="color: var(--accent-rose);">Error predicting lead time.</div>`;
            }
        });
    }

    // Helper Utility: Currency Formatting
    function formatCurrency(val) {
        if (!val || isNaN(val)) return '$0.00';
        if (val >= 1e6) return '$' + (val / 1e6).toFixed(2) + 'M';
        if (val >= 1e3) return '$' + (val / 1e3).toFixed(1) + 'K';
        return '$' + val.toFixed(2);
    }

    // Initialize App Data
    loadSummaryKPIs();
    loadAnalyticsCharts();
    loadVendorDirectory();

    document.getElementById('btn-refresh-data').addEventListener('click', () => {
        loadSummaryKPIs();
        loadAnalyticsCharts();
        loadVendorDirectory();
    });
});

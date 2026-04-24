<script>
  import { onMount } from 'svelte';
  import { analyticsDashboard } from '$lib/stores.js';

  const FASTAPI = 'http://localhost:8000';

  // State for dashboard data
  let loading = true;
  let errorMessage = '';
  
  // These map directly to the backend analytics response
  let kpis = {
    totalRevenue: 0,
    netProfit: 0,
    returnRate: 0,
    openTickets: 0
  };
  
  let supportHealth = [];
  let topCategories = [];

  const readSupportHealth = (data) => {
    if (!data) return [];
    return data.supportHealth ?? data.support_health ?? data.supporthealth ?? [];
  };

  const isValidDashboardData = (data) => {
    return Boolean(
      data &&
      Array.isArray(readSupportHealth(data)) &&
      Array.isArray(data.topCategories) &&
      data.kpis
    );
  };

  const applyDashboardData = (data) => {
    const next = {
      kpis: data?.kpis ?? kpis,
      supportHealth: readSupportHealth(data),
      topCategories: data?.topCategories ?? [],
    };

    kpis = next.kpis;
    supportHealth = next.supportHealth;
    topCategories = next.topCategories;
    errorMessage = '';
    analyticsDashboard.set(next);
  };

  onMount(async () => {
    let cached = null;
    const unsubscribe = analyticsDashboard.subscribe((value) => {
      cached = value;
    });

    try {
      if (isValidDashboardData(cached)) {
        applyDashboardData(cached);
        loading = false;
      }

      const response = await fetch(`${FASTAPI}/api/analytics/dashboard`);
      if (!response.ok) {
        throw new Error(`Analytics request failed with ${response.status}`);
      }

      const data = await response.json();
      if (!data?.supportHealth?.length && Array.isArray(cached?.supportHealth) && cached.supportHealth.length > 0) {
        // Keep showing the last known good data if the live response is unexpectedly empty.
        return;
      }
      applyDashboardData(data);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      errorMessage = err?.message ?? 'Failed to load dashboard data';
    } finally {
      unsubscribe();
      loading = false;
    }
  });

  // Formatting helpers
  const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
</script>

<div class="dashboard-wrapper">
  <header class="dash-header">
    <div>
      <div class="kicker">Overview</div>
      <h1>Analytics Dashboard</h1>
    </div>
    <div class="date-filter">
      <select class="filter-select">
        <option>Last 30 Days</option>
        <option>Last Quarter</option>
        <option>Year to Date</option>
      </select>
    </div>
  </header>

  {#if loading}
    <div class="loading-state">Loading analytics...</div>
  {:else if errorMessage}
    <div class="loading-state error-state">{errorMessage}</div>
  {:else}
    <section class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Revenue</div>
        <div class="kpi-value">{formatCurrency(kpis.totalRevenue)}</div>
        <div class="kpi-trend positive">↑ 12.5% vs last month</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Net Profit</div>
        <div class="kpi-value">{formatCurrency(kpis.netProfit)}</div>
        <div class="kpi-trend positive">↑ 8.2% vs last month</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Return Rate</div>
        <div class="kpi-value">{kpis.returnRate}%</div>
        <div class="kpi-trend negative">↑ 1.1% vs last month</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Open Enquiries</div>
        <div class="kpi-value">{kpis.openTickets}</div>
        <div class="kpi-trend neutral">Stable</div>
      </div>
    </section>

    <div class="charts-grid">
      <div class="chart-card">
        <div class="card-header">Customer Support Health</div>
        <div class="list-container">
          {#if supportHealth.length > 0}
            {#each supportHealth as row}
              <div class="support-row">
                <div class="support-row-header">
                  <div class="item-name">{row.enqCategory}</div>
                  <div class="item-subtext">{row.enqPriority} priority</div>
                </div>
                <div class="support-row-grid">
                  <div class="support-metric">
                    <span class="support-label">Tickets</span>
                    <span class="support-value">{row.ticketCount}</span>
                  </div>
                  <div class="support-metric">
                    <span class="support-label">Sentiment</span>
                    <span class="support-value">{row.avgSentiment}</span>
                  </div>
                  <div class="support-metric">
                    <span class="support-label">Negative</span>
                    <span class="support-value">{row.negativeTickets}</span>
                  </div>
                  <div class="support-metric">
                    <span class="support-label">Avg Res.</span>
                    <span class="support-value">{row.avgResolutionMin} min</span>
                  </div>
                  <div class="support-metric">
                    <span class="support-label">Open</span>
                    <span class="support-value">{row.openCount}</span>
                  </div>
                </div>
              </div>
            {/each}
          {:else}
            <div class="empty-state">
              No customer support health data returned yet.
            </div>
          {/if}
        </div>
      </div>

      <div class="chart-card">
        <div class="card-header">Top Performing Categories</div>
        <div class="list-container">
          {#each topCategories as cat}
            <div class="list-item">
              <div class="item-info">
                <span class="item-name">{cat.name}</span>
                <span class="item-subtext">{cat.margin}% Profit Margin</span>
              </div>
              <div class="item-metric">
                {formatCurrency(cat.revenue)}
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .dashboard-wrapper {
    padding: 32px 40px;
    height: 100%;
    overflow-y: auto;
    background: var(--bg-base, #f8f9fa);
  }

  .dash-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 32px;
  }

  .kicker {
    font-family: var(--font-mono, monospace);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted, #6c757d);
    margin-bottom: 4px;
  }

  h1 {
    font-family: var(--font-display, sans-serif);
    font-size: 28px;
    font-weight: 600;
    color: var(--text-primary, #212529);
    margin: 0;
  }

  .filter-select {
    padding: 8px 12px;
    border: 1px solid var(--border, #dee2e6);
    border-radius: 6px;
    background: var(--bg-surface, #fff);
    font-size: 13px;
    color: var(--text-secondary, #495057);
    outline: none;
  }

  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
    margin-bottom: 32px;
  }

  .kpi-card {
    background: var(--bg-surface, #fff);
    padding: 24px;
    border-radius: 12px;
    border: 1px solid var(--border, #dee2e6);
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
  }

  .kpi-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted, #6c757d);
    margin-bottom: 8px;
  }

  .kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary, #212529);
    margin-bottom: 8px;
  }

  .kpi-trend {
    font-size: 12px;
    font-weight: 500;
  }
  .positive { color: #0f9d58; } /* Green */
  .negative { color: #d93025; } /* Red */
  .neutral { color: var(--text-muted, #6c757d); }

  .charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 24px;
  }

  .chart-card {
    background: var(--bg-surface, #fff);
    border: 1px solid var(--border, #dee2e6);
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
  }

  .card-header {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary, #212529);
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-subtle, #f1f3f5);
  }

  .list-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .support-row {
    padding: 16px;
    border: 1px solid var(--border, #dee2e6);
    border-radius: 12px;
    background: var(--bg-surface, #fff);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  }

  .support-row-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 12px;
  }

  .support-row-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
  }

  .support-metric {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .support-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #5f6368;
  }

  .support-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary, #212529);
  }

  .empty-state {
    padding: 16px;
    border: 1px dashed var(--border, #dee2e6);
    border-radius: 10px;
    color: var(--text-muted, #6c757d);
    font-size: 13px;
    text-align: center;
    background: #f8f9fa;
  }

  .list-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .item-info {
    display: flex;
    flex-direction: column;
  }

  .item-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary, #212529);
  }

  .item-subtext {
    font-size: 12px;
    color: var(--text-muted, #6c757d);
    margin-top: 2px;
  }

  .item-metric {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary, #212529);
  }

  .negative-val {
    color: #d93025;
  }

  .loading-state {
    height: 300px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .error-state {
    color: #d93025;
    text-align: center;
    padding: 0 24px;
  }
</style>

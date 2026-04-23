<script>
  import {
    filters, selectedTicketId, selectedTicket,
    tickets, ticketsLoading, ticketsError,
    loadTickets, updateTicketStatus
  } from '$lib/stores.js';

  // ── State ──────────────────────────────────────────────────────────────────
  let activeTab = 'Open';
  let ticketsQueued = $tickets.length > 0;

  $: filteredTickets = $tickets.filter(t => {
    if (activeTab !== 'All' && t.status !== activeTab) return false;
    if ($filters.search) {
      const q = $filters.search.toLowerCase();
      if (
        !t.id?.toLowerCase().includes(q) &&
        !t.customer?.name?.toLowerCase().includes(q) &&
        !t.item?.category?.toLowerCase().includes(q) &&
        !t.returnReason?.toLowerCase().includes(q)
      ) return false;
    }
    return true;
  });

  $: counts = {
    Open:   $tickets.filter(t => t.status === 'Open').length,
    Closed: $tickets.filter(t => t.status === 'Closed').length,
    All:    $tickets.length,
  };

  $: totalAmt     = $tickets.reduce((s, t) => s + (parseFloat(t.returnAmt) || 0), 0);
  $: totalNetLoss = $tickets.reduce((s, t) => s + (parseFloat(t.netLoss)   || 0), 0);

  // ── Handlers ────────────────────────────────────────────────────────────────
  async function handleQueueTickets() {
    await loadTickets();
    ticketsQueued = true;
  }

  function selectTicket(id) { 
    selectedTicketId.set(id); 
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function formatAmt(val) {
    const n = parseFloat(val);
    return isNaN(n) ? '—' : `$${n.toFixed(2)}`;
  }

  function setSearch(e) { 
    filters.update(f => ({ ...f, search: e.target.value })); 
  }

  // ── Resolution options ──────────────────────────────────────────────────
  const RESOLUTION_OPTIONS = [
    { id: 'full_refund',      label: 'Full Refund',              icon: '↩', color: 'green',  desc: 'Refund the full return amount to the customer.' },
    { id: 'partial_refund',   label: 'Partial Refund',           icon: '$', color: 'amber',  desc: 'Refund only part of the amount — restocking fee may apply.' },
    { id: 'replacement',      label: 'Send Replacement',         icon: '↗', color: 'blue',   desc: 'Ship a replacement item at no charge to the customer.' },
    { id: 'exchange',         label: 'Size / Item Exchange',     icon: '⇄', color: 'blue',   desc: 'Exchange for correct size or item — preserve the sale.' },
    { id: 'retention_offer',  label: 'Retention Offer',          icon: '✦', color: 'orange', desc: 'Offer store credit or discount before processing a refund.' },
    { id: 'escalate_quality', label: 'Escalate to Quality Team', icon: '⚑', color: 'red',    desc: 'Flag to quality team for batch defect investigation.' },
  ];

  function resolutionLabel(id) { return RESOLUTION_OPTIONS.find(o => o.id === id)?.label ?? id; }
  function resolutionColor(id) { return RESOLUTION_OPTIONS.find(o => o.id === id)?.color ?? 'amber'; }
  function resolutionIcon(id)  { return RESOLUTION_OPTIONS.find(o => o.id === id)?.icon  ?? '—'; }

  // Parse structured resolution
  function isStructuredResolution(str) {
    return typeof str === 'string' && str.startsWith('ITEM:');
  }

  function parseStructuredResolution(str) {
    if (!str) return null;
    const parts = str.split(' | ');
    const out = {};
    for (const part of parts) {
      const colon = part.indexOf(':');
      if (colon === -1) continue;
      const key = part.slice(0, colon).trim();
      const val = part.slice(colon + 1).trim();
      out[key] = val;
    }
    return out;
  }

  // ── UI state machine ──────────────────────────────────────────────────────
  // stages: 'idle' | 'manual_selecting' | 'manual_selected' | 'confirmed'
  let uiStage            = 'idle';
  let selectedResolution = null;
  let confirmLoading     = false;

  // Reset all local state when the selected ticket changes
  $: if ($selectedTicket) {
    const t = $selectedTicket;
    if (t.status === 'Closed') {
      uiStage = 'confirmed';
      selectedResolution = t.resolution
        ? (RESOLUTION_OPTIONS.find(o => o.id === t.resolution) ?? null)
        : null;
    } else {
      uiStage = 'idle';
      selectedResolution = null;
    }
    confirmLoading = false;
  }

  function handleManualClick()         { uiStage = 'manual_selecting'; }
  function handleSelectResolution(opt) { selectedResolution = opt; uiStage = 'manual_selected'; }
  function handleBack()                { uiStage = 'manual_selecting'; selectedResolution = null; }

  async function handleConfirm() {
    if (!$selectedTicket) return;
    console.log('[handleConfirm] ticket:', $selectedTicket.id, 'resolution:', selectedResolution?.id);
    confirmLoading = true;
    await updateTicketStatus($selectedTicket.id, 'Closed', selectedResolution?.id ?? null);
    uiStage = 'confirmed';
    confirmLoading = false;
  }
</script>

<div class="dashboard">
  <header class="topbar">
    <div class="topbar-left">
      <h2>Returned Items Queue</h2>
      <div class="breadcrumb">Store Returns · Live from Snowflake · STORE_RETURNS × ITEM × REASON × CUSTOMER</div>
    </div>
    <div class="topbar-stats">
      <div class="stat-pill">
        <span class="dot" style="background:var(--blue)"></span>
        {counts.Open} Open
      </div>
      <div class="stat-pill">
        <span class="dot" style="background:var(--green)"></span>
        {counts.Closed} Closed
      </div>
      <div class="stat-pill">
        <span class="dot" style="background:var(--amber)"></span>
        {counts.All} Total
      </div>
      {#if ticketsQueued}
        <div class="stat-pill">
          <span class="dot" style="background:var(--red)"></span>
          Net Loss: ${totalNetLoss.toFixed(0)}
        </div>
      {/if}
    </div>
  </header>

  <div class="split-view">
    <div class="list-panel">
      <div class="list-filters">
        <input 
          class="search-input" 
          type="text" 
          placeholder="Search by customer, category, reason…" 
          value={$filters.search} 
          on:input={setSearch} 
          disabled={!ticketsQueued}
        />
      </div>

      <div class="filter-tabs">
        {#each ['Open', 'Closed', 'All'] as tab}
          <button 
            class="tab-btn" 
            class:active={activeTab === tab} 
            on:click={() => activeTab = tab}
            disabled={!ticketsQueued}
          >
            {tab}
            <span class="tab-count">{counts[tab]}</span>
          </button>
        {/each}
      </div>

      <div class="returns-list">
        {#if $ticketsError}
          <div class="list-banner warn">⚠ {$ticketsError}</div>
        {/if}

        {#if !ticketsQueued}
          <div class="empty-state">
            Click 'Queue Tickets' to load the return list
          </div>
        {:else}
          {#each filteredTickets as t (t.id)}
            <button 
              class="return-row" 
              class:active={$selectedTicketId === t.id} 
              on:click={() => selectTicket(t.id)}
            >
              <div class="row-top">
                <span class="return-id">{t.id}</span>
                <span class="row-status-dot status-dot-{(t.status ?? 'Open').toLowerCase()}"></span>
                <span class="return-date">{formatDate(t.created)}</span>
              </div>
              <div class="row-product">{t.item?.name ? (t.item.name.length > 42 ? t.item.name.slice(0,42)+'…' : t.item.name) : t.id}</div>
              <div class="row-meta">
                <span class="row-customer">{t.customer?.name ?? '—'}</span>
                <span class="row-category">{t.item?.category ?? '—'}</span>
              </div>
              <div class="row-bottom">
                {#if isStructuredResolution(t.resolution)}
                  {@const parsed = parseStructuredResolution(t.resolution)}
                  <span class="row-reason">{parsed['RETURN REASON'] ?? parsed['PACKAGING ASSESSMENT'] ?? t.returnReason ?? '—'}</span>
                {:else}
                  <span class="row-reason">{t.returnReason ?? '—'}</span>
                {/if}
                <span class="row-amt">{formatAmt(t.returnAmt)}</span>
              </div>
              {#if t.resolution}
                {#if isStructuredResolution(t.resolution)}
                  <div class="row-resolution row-resolution-manual">✓ Manual Return · {parseStructuredResolution(t.resolution)['PACKAGING ASSESSMENT']?.split('(')[0]?.trim() ?? 'Assessed'}</div>
                {:else}
                  <div class="row-resolution">✓ {resolutionLabel(t.resolution)}</div>
                {/if}
              {/if}
            </button>
          {/each}

          {#if filteredTickets.length === 0}
            <div class="empty-state">
              {#if $filters.search}No returns match your search
              {:else}No {activeTab === 'All' ? '' : activeTab + ' '}returns
              {/if}
            </div>
          {/if}
        {/if}
      </div>
    </div>

    <div class="detail-panel">
      {#if !ticketsQueued}
        <div class="detail-empty">
          <div class="queue-header">
            <h3 style="font-family: var(--font-display); font-size: 24px; color: var(--text-primary); margin-bottom: 8px;">Queued Return Tickets</h3>
            <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 24px;">Load tickets from Snowflake to begin operations</p>
          </div>
          
          <button 
            class="btn-queue" 
            style="width: 200px;"
            on:click={handleQueueTickets}
            disabled={$ticketsLoading}
          >
            {#if $ticketsLoading}
              <span class="spinner-sm"></span>
              Loading tickets…
            {:else}
              ↻ Queue Tickets
            {/if}
          </button>

          {#if $ticketsError}
            <div class="queue-error" style="margin-top: 16px;">{$ticketsError}</div>
          {/if}
        </div>
        
      {:else if $selectedTicket}
        {@const t = $selectedTicket}
        <div class="detail-content">
          <div class="detail-header">
            <div class="detail-header-top">
              <div class="header-ids">
                <span class="detail-id">{t.id}</span>
                <span class="status-badge status-{(t.status ?? 'Open').toLowerCase()}">{t.status ?? 'Open'}</span>
                {#if isStructuredResolution(t.resolution)}<span class="manual-badge">✎ Manual Entry</span>{/if}
              </div>
              <span class="return-date-large">{formatDate(t.created)}</span>
            </div>
            <h3 class="detail-title">{t.item?.name ?? t.id}</h3>
            <div class="detail-reason">
              {#if isStructuredResolution(t.resolution)}
                {parseStructuredResolution(t.resolution)['RETURN REASON'] ?? t.returnReason ?? '—'}
              {:else}
                {t.returnReason ?? '—'}
              {/if}
            </div>
          </div>

          {#if isStructuredResolution(t.resolution)}
            {@const ra = parseStructuredResolution(t.resolution)}
            <div class="detail-section assessment-section">
              <div class="section-label">✓ Return Assessment <span class="manual-tag">Manual Entry</span></div>
              <div class="assessment-grid">
                {#if ra['ITEM']}
                  <div class="assessment-block full-width">
                    <span class="ab-label">Product</span>
                    <span class="ab-val">{ra['ITEM']}</span>
                  </div>
                {/if}
                {#if ra['UNIT PRICE']}
                  <div class="assessment-block">
                    <span class="ab-label">Unit Price / Qty / Total</span>
                    <span class="ab-val mono">{ra['UNIT PRICE']}</span>
                  </div>
                {/if}
                {#if ra['PACKAGING ASSESSMENT']}
                  <div class="assessment-block">
                    <span class="ab-label">Packaging Condition</span>
                    <span class="ab-val pkg">{ra['PACKAGING ASSESSMENT']}</span>
                  </div>
                {/if}
                {#if ra['FINANCIALS']}
                  <div class="assessment-block full-width">
                    <span class="ab-label">Financials Breakdown</span>
                    <span class="ab-val mono">{ra['FINANCIALS']}</span>
                  </div>
                {/if}
                {#if ra['RETURN REASON']}
                  <div class="assessment-block full-width">
                    <span class="ab-label">Return Reason (AI Generated)</span>
                    <span class="ab-val reason-text">{ra['RETURN REASON']}</span>
                  </div>
                {/if}
                {#if ra['AGENT NOTES']}
                  <div class="assessment-block full-width">
                    <span class="ab-label">Agent Notes</span>
                    <span class="ab-val notes-text">{ra['AGENT NOTES']}</span>
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <div class="two-col">
            <div class="detail-section">
              <div class="section-label">Return Financials</div>
              <div class="kv-list">
                <div class="kv-row"><span class="kv-key">Return Amount</span><span class="kv-val amber">{formatAmt(t.returnAmt)}</span></div>
                <div class="kv-row"><span class="kv-key">Net Loss</span><span class="kv-val red">{formatAmt(t.netLoss)}</span></div>
                <div class="kv-row"><span class="kv-key">Return Fee</span><span class="kv-val">{formatAmt(t.fee)}</span></div>
                <div class="kv-row"><span class="kv-key">Qty Returned</span><span class="kv-val">{t.item?.returnQty ?? '—'}</span></div>
                <div class="kv-row"><span class="kv-key">Return Date</span><span class="kv-val">{formatDate(t.created)}</span></div>
              </div>
            </div>
            <div class="detail-section">
              <div class="section-label">Item Details <span class="sf-tag">✦ Snowflake</span></div>
              <div class="kv-list">
                <div class="kv-row"><span class="kv-key">Product</span><span class="kv-val">{t.item?.name ?? '—'}</span></div>
                <div class="kv-row"><span class="kv-key">Brand</span><span class="kv-val">{t.item?.brand || '—'}</span></div>
                <div class="kv-row"><span class="kv-key">Category</span><span class="kv-val">{t.item?.categoryFull || t.item?.category || '—'}</span></div>
                <div class="kv-row"><span class="kv-key">Class</span><span class="kv-val">{t.item?.class ?? '—'}</span></div>
                <div class="kv-row"><span class="kv-key">Listed Price</span><span class="kv-val">{t.item?.price ? `${t.item.price}` : '—'}</span></div>
                <div class="kv-row"><span class="kv-key">Return Reason</span><span class="kv-val">{t.returnReason ?? '—'}</span></div>
                {#if t.item?.url}<div class="kv-row"><span class="kv-key">Product Page</span><span class="kv-val"><a href={t.item.url} target="_blank" rel="noreferrer" class="item-link">View ↗</a></span></div>{/if}
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="section-label">Customer Details</div>
            <div class="customer-card">
              <div class="cust-avatar">{(t.customer?.name ?? 'U').split(' ').map(n => n[0]).join('').slice(0,2)}</div>
              <div class="cust-body">
                <div class="cust-row">
                  <div class="cust-main">
                    <div class="cust-name">{t.customer?.name ?? '—'}</div>
                    <div class="cust-tier tier-{(t.customer?.tier ?? 'bronze').toLowerCase()}">{t.customer?.tier ?? '—'}</div>
                  </div>
                </div>
                <div class="cust-contact">
                  <div class="contact-item">
                    <span class="contact-icon">✉</span>
                    <span class="contact-val">{t.customer?.email ?? '—'}</span>
                  </div>
                </div>
                <div class="cust-stats">
                  <div class="cust-stat"><span class="cust-stat-val">{t.customer?.ltv ?? '—'}</span><span class="cust-stat-label">Est. LTV</span></div>
                  <div class="cust-stat"><span class="cust-stat-val">{t.customer?.orders ?? '—'}</span><span class="cust-stat-label">Returns</span></div>
                  <div class="cust-stat"><span class="cust-stat-val tier-{(t.customer?.tier ?? 'bronze').toLowerCase()}">{t.customer?.tier ?? '—'}</span><span class="cust-stat-label">Tier</span></div>
                </div>
              </div>
            </div>
          </div>

          {#if uiStage === 'idle'}
            <div class="action-bar">
              <button class="btn-action btn-manual" on:click={handleManualClick}>✎ Manually Resolve</button>
            </div>
          {:else if uiStage === 'manual_selecting'}
            <div class="detail-section resolution-section">
              <div class="section-label">Select Resolution Action</div>
              <div class="resolution-grid">
                {#each RESOLUTION_OPTIONS as opt}
                  <button class="res-option color-{opt.color}" on:click={() => handleSelectResolution(opt)}>
                    <span class="res-icon">{opt.icon}</span>
                    <span class="res-label">{opt.label}</span>
                    <span class="res-desc">{opt.desc}</span>
                  </button>
                {/each}
              </div>
            </div>
          {:else if uiStage === 'manual_selected'}
            <div class="detail-section resolution-section">
              <div class="section-label">
                Selected Resolution
                <button class="link-btn" on:click={handleBack}>← Change</button>
              </div>
              <div class="selected-resolution color-{selectedResolution.color}">
                <span class="res-icon">{selectedResolution.icon}</span>
                <div>
                  <div class="res-label">{selectedResolution.label}</div>
                  <div class="res-desc">{selectedResolution.desc}</div>
                </div>
              </div>
            </div>
            <div class="action-bar">
              <button class="btn-action btn-confirm" on:click={handleConfirm} disabled={confirmLoading}>
                {#if confirmLoading}<span class="spinner-sm"></span> Closing…{:else}✓ Confirm & Close Ticket{/if}
              </button>
            </div>
          {:else if uiStage === 'confirmed'}
            {#if t.resolution}
              <div class="detail-section resolution-section">
                <div class="section-label">Resolution Applied</div>
                <div class="selected-resolution color-{resolutionColor(t.resolution)}">
                  <span class="res-icon">{resolutionIcon(t.resolution)}</span>
                  <div>
                    <div class="res-label">{resolutionLabel(t.resolution)}</div>
                    <div class="res-desc">Persisted to Snowflake · SR_RESOLUTION = '{t.resolution}'</div>
                  </div>
                </div>
              </div>
            {/if}
            <div class="closed-banner">✓ Ticket closed and persisted to Snowflake</div>
          {/if}
        </div>
        
      {:else}
        <div class="detail-empty">
          <div class="empty-icon">↩</div>
          <div>Select a return to review</div>
          <div class="empty-sub">Live from Snowflake · STORE_RETURNS × ITEM × REASON × CUSTOMER</div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .dashboard{display:flex;flex-direction:column;height:100vh;overflow:hidden}
  .topbar{display:flex;align-items:center;justify-content:space-between;padding:16px 24px;border-bottom:1px solid var(--border);background:var(--bg-surface);flex-shrink:0}
  .topbar-left h2{font-family:var(--font-display);font-size:20px;font-weight:400;line-height:1}
  .breadcrumb{font-size:11px;color:var(--text-muted);font-family:var(--font-mono);margin-top:4px}
  .topbar-stats{display:flex;gap:8px;flex-wrap:wrap}
  .stat-pill{display:flex;align-items:center;gap:7px;padding:6px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:20px;font-size:12px;font-weight:600;font-family:var(--font-mono);color:var(--text-secondary)}
  .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

  /* ── Queue Stage ── */
  .queue-stage{display:flex;align-items:center;justify-content:center;height:calc(100vh - 65px);background:var(--bg-base)}
  .queue-container{display:flex;flex-direction:column;align-items:center;gap:32px;max-width:400px}
  .queue-header{text-align:center;margin-bottom:12px}
  .queue-header h3{font-family:var(--font-display);font-size:28px;font-weight:400;margin-bottom:8px;color:var(--text-primary)}
  .queue-header p{font-size:14px;color:var(--text-muted)}
  
  .queue-counts{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;width:100%;margin:16px 0}
  .count-card{display:flex;flex-direction:column;align-items:center;padding:20px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-md);gap:8px}
  .count-number{font-family:var(--font-mono);font-size:32px;font-weight:700;color:var(--amber)}
  .count-label{font-size:12px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em}

  .btn-queue{display:flex;align-items:center;justify-content:center;gap:10px;padding:13px 28px;background:var(--amber);border:none;border-radius:var(--radius-sm);color:#0c0e14;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.15s;width:100%}
  .btn-queue:hover:not(:disabled){background:#e0b855}
  .btn-queue:disabled{opacity:0.6;cursor:not-allowed}

  .queue-error{font-size:12px;color:var(--red);padding:12px;background:var(--red-dim);border:1px solid rgba(224,92,92,0.3);border-radius:var(--radius-sm);text-align:center;width:100%}

  /* ── Split View ── */
  .split-view{display:flex;overflow:hidden;height:calc(100vh - 65px)}

  .list-panel{width:380px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column;height:100%;overflow:hidden}
  .list-filters{padding:12px 14px 8px;flex-shrink:0}
  .search-input{width:100%;padding:8px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);font-size:13px;outline:none}
  .search-input:focus{border-color:var(--amber-dim)}
  .search-input::placeholder{color:var(--text-muted)}

  .filter-tabs{display:flex;border-bottom:1px solid var(--border);flex-shrink:0}
  .tab-btn{flex:1;padding:8px 4px;background:none;border:none;border-bottom:2px solid transparent;color:var(--text-muted);font-size:11.5px;font-weight:600;font-family:var(--font-mono);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:5px;transition:all 0.15s;margin-bottom:-1px}
  .tab-btn:hover{color:var(--text-secondary)}
  .tab-btn.active{color:var(--amber);border-bottom-color:var(--amber)}
  .tab-count{background:var(--bg-elevated);border:1px solid var(--border);padding:1px 6px;border-radius:10px;font-size:10px}
  .tab-btn.active .tab-count{background:var(--amber-glow);border-color:rgba(212,168,67,0.3);color:var(--amber)}

  .returns-list{flex:1;overflow-y:auto;padding:8px}
  .list-banner{font-size:12px;padding:10px 14px;border-radius:var(--radius-sm);margin:6px;line-height:1.5}
  .list-banner.warn{background:var(--amber-glow);color:var(--amber);border:1px solid rgba(212,168,67,0.25)}
  .empty-state{text-align:center;color:var(--text-muted);font-size:13px;padding:40px}

  .return-row{width:100%;text-align:left;background:#1a1f2e;border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 14px;margin-bottom:6px;cursor:pointer;transition:background 0.1s,border-color 0.1s;display:block;color:var(--text-primary)}
  .return-row:hover{background:var(--bg-elevated);border-color:rgba(212,168,67,0.2)}
  .return-row.active{background:var(--bg-hover);border-color:rgba(212,168,67,0.4)}
  .row-top{display:flex;align-items:center;gap:7px;margin-bottom:5px}
  .return-id{font-family:var(--font-mono);font-size:11px;color:var(--text-muted);flex:1}
  .row-status-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
  .status-dot-open{background:var(--blue)}
  .status-dot-closed{background:var(--green)}
  .return-date{font-family:var(--font-mono);font-size:11px;color:var(--text-muted)}
  .row-product{font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .row-meta{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
  .row-customer{font-size:12px;color:var(--text-secondary)}
  .row-category{font-size:11px;font-family:var(--font-mono);color:var(--text-muted);background:var(--bg-elevated);padding:1px 6px;border-radius:3px;border:1px solid var(--border)}
  .row-bottom{display:flex;align-items:center;justify-content:space-between}
  .row-reason{font-size:11.5px;color:var(--text-muted);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-right:10px}
  .row-amt{font-family:var(--font-mono);font-size:12px;font-weight:600;color:var(--amber);flex-shrink:0}
  .row-resolution{font-size:10.5px;color:var(--green);font-family:var(--font-mono);margin-top:5px;font-weight:600}

  .detail-panel{flex:1;overflow-y:auto;background:var(--bg-base)}
  .detail-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px;color:var(--text-muted);font-size:13px}
  .empty-icon{font-size:36px;opacity:0.25}
  .empty-sub{font-size:11px;opacity:0.5;font-family:var(--font-mono)}
  .detail-content{padding:28px;max-width:820px}
  .detail-header{margin-bottom:20px;padding-bottom:18px;border-bottom:1px solid var(--border-subtle)}
  .detail-header-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
  .header-ids{display:flex;align-items:center;gap:10px}
  .detail-id{font-family:var(--font-mono);font-size:12px;color:var(--text-muted)}
  .return-date-large{font-family:var(--font-mono);font-size:12px;color:var(--text-muted)}
  .detail-title{font-family:var(--font-display);font-size:22px;font-weight:400;line-height:1.3;margin-bottom:6px}
  .detail-reason{font-size:13px;color:var(--text-secondary)}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
  .detail-section{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:16px;margin-bottom:12px}
  .section-label{font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;font-family:var(--font-mono);margin-bottom:14px;display:flex;align-items:center;gap:8px}
  .sf-tag{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600;color:var(--amber);background:var(--amber-glow);border:1px solid rgba(212,168,67,0.3)}
  .kv-list{display:flex;flex-direction:column;gap:10px}
  .kv-row{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
  .kv-key{font-size:12px;color:var(--text-muted);flex-shrink:0}
  .kv-val{font-size:13px;font-family:var(--font-mono);color:var(--text-primary);text-align:right;word-break:break-all}
  .kv-val.amber{color:var(--amber);font-weight:600}
  .kv-val.red{color:var(--red);font-weight:600}

  .customer-card{display:flex;align-items:flex-start;gap:14px}
  .cust-avatar{width:42px;height:42px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--font-mono);font-size:13px;color:var(--amber);flex-shrink:0;font-weight:600}
  .cust-body{flex:1}
  .cust-row{display:flex;align-items:center;gap:10px;margin-bottom:6px}
  .cust-main{display:flex;align-items:center;gap:10px}
  .cust-name{font-size:15px;font-weight:600;color:var(--text-primary)}
  .cust-tier{font-family:var(--font-mono);font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;padding:2px 8px;border-radius:3px}
  .tier-platinum{color:#a8d8f0;background:rgba(168,216,240,0.12)}
  .tier-gold{color:var(--amber);background:var(--amber-glow)}
  .tier-silver{color:#b0b8c8;background:rgba(176,184,200,0.1)}
  .tier-bronze{color:#cd7f32;background:rgba(205,127,50,0.1)}
  .cust-contact{display:flex;flex-direction:column;gap:5px;margin-bottom:14px}
  .contact-item{display:flex;align-items:center;gap:8px}
  .contact-icon{font-size:12px;color:var(--text-muted);width:16px}
  .contact-val{font-size:12.5px;font-family:var(--font-mono);color:var(--text-secondary)}
  .cust-stats{display:flex;gap:24px}
  .cust-stat{display:flex;flex-direction:column;gap:2px}
  .cust-stat-val{font-family:var(--font-mono);font-size:14px;font-weight:500;color:var(--text-primary)}
  .cust-stat-label{font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em}

  .status-badge{font-family:var(--font-mono);font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;padding:3px 10px;border-radius:20px}
  .status-open{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(91,140,240,0.3)}
  .status-closed{background:var(--green-dim);color:var(--green);border:1px solid rgba(76,175,130,0.3)}

  .action-bar{display:flex;gap:10px;margin-top:4px;padding-top:4px;margin-bottom:12px}
  .btn-action{display:flex;align-items:center;gap:8px;padding:11px 22px;border-radius:var(--radius-sm);font-size:13px;font-weight:600;letter-spacing:0.03em;transition:all 0.15s;border:1px solid;cursor:pointer}
  .btn-action:disabled{opacity:0.5;cursor:not-allowed}
  .btn-manual{background:var(--green-dim);border-color:rgba(76,175,130,0.4);color:var(--green)}
  .btn-manual:hover{background:rgba(76,175,130,0.25)}
  .btn-confirm{background:var(--green);border-color:var(--green);color:#0c0e14;font-size:14px}
  .btn-confirm:hover:not(:disabled){background:#5dc99a}

  .resolution-section{border-color:rgba(91,140,240,0.2)}
  .resolution-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
  .res-option{text-align:left;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-md);padding:14px;cursor:pointer;transition:all 0.15s;display:flex;flex-direction:column;gap:5px}
  .res-icon{font-size:18px;line-height:1}
  .res-label{font-size:12.5px;font-weight:700;color:var(--text-primary)}
  .res-desc{font-size:11px;color:var(--text-muted);line-height:1.5}
  .color-green .res-icon{color:var(--green)}
  .color-amber .res-icon{color:var(--amber)}
  .color-blue  .res-icon{color:var(--blue)}
  .color-orange .res-icon{color:var(--orange)}
  .color-red   .res-icon{color:var(--red)}
  .color-green.res-option:hover{border-color:rgba(76,175,130,0.5);background:rgba(76,175,130,0.06)}
  .color-amber.res-option:hover{border-color:rgba(212,168,67,0.5);background:rgba(212,168,67,0.06)}
  .color-blue.res-option:hover{border-color:rgba(91,140,240,0.5);background:rgba(91,140,240,0.06)}
  .color-orange.res-option:hover{border-color:rgba(224,138,60,0.5);background:rgba(224,138,60,0.06)}
  .color-red.res-option:hover{border-color:rgba(224,92,92,0.5);background:rgba(224,92,92,0.06)}

  .selected-resolution{display:flex;align-items:flex-start;gap:14px;padding:12px 14px;border-radius:var(--radius-sm);border:1px solid}
  .color-green.selected-resolution{background:rgba(76,175,130,0.08);border-color:rgba(76,175,130,0.3)}
  .color-amber.selected-resolution{background:rgba(212,168,67,0.08);border-color:rgba(212,168,67,0.3)}
  .color-blue.selected-resolution{background:rgba(91,140,240,0.08);border-color:rgba(91,140,240,0.3)}
  .color-orange.selected-resolution{background:rgba(224,138,60,0.08);border-color:rgba(224,138,60,0.3)}
  .color-red.selected-resolution{background:rgba(224,92,92,0.08);border-color:rgba(224,92,92,0.3)}
  .selected-resolution .res-icon{font-size:20px;margin-top:2px}
  .selected-resolution .res-label{font-size:14px;font-weight:700;color:var(--text-primary);margin-bottom:3px;display:block}
  .selected-resolution .res-desc{font-size:12px;color:var(--text-secondary)}
  .link-btn{background:none;border:none;color:var(--text-muted);font-size:11px;cursor:pointer;padding:0;font-family:var(--font-mono);text-decoration:underline}
  .link-btn:hover{color:var(--amber)}

  .closed-banner{display:flex;align-items:center;gap:10px;padding:14px 18px;background:var(--green-dim);border:1px solid rgba(76,175,130,0.3);border-radius:var(--radius-md);color:var(--green);font-weight:600;font-size:14px;margin-bottom:12px}

  .spinner-sm{width:13px;height:13px;border:2px solid rgba(0,0,0,0.2);border-top-color:currentColor;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block}
  @keyframes spin{to{transform:rotate(360deg)}}

  .item-link{color:var(--amber);font-size:12px;font-family:var(--font-mono);text-decoration:none;border-bottom:1px solid rgba(212,168,67,0.4)}
  .item-link:hover{border-bottom-color:var(--amber)}

  /* Manual entry badges */
  .manual-badge{font-family:var(--font-mono);font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;color:var(--blue);background:var(--blue-dim);border:1px solid rgba(91,140,240,0.3)}
  .manual-tag{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600;color:var(--blue);background:var(--blue-dim);border:1px solid rgba(91,140,240,0.3)}
  .row-resolution-manual{color:var(--blue);}

  /* Assessment section */
  .assessment-section{border-color:rgba(91,140,240,0.25);background:rgba(91,140,240,0.03);margin-bottom:12px}
  .assessment-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .assessment-block{display:flex;flex-direction:column;gap:5px;padding:10px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm)}
  .assessment-block.full-width{grid-column:1/-1}
  .ab-label{font-size:9.5px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.09em;font-family:var(--font-mono)}
  .ab-val{font-size:13px;color:var(--text-primary);line-height:1.5}
  .ab-val.mono{font-family:var(--font-mono);font-size:12px;color:var(--text-secondary)}
  .ab-val.pkg{color:var(--amber);font-weight:600}
  .ab-val.reason-text{color:var(--text-primary);font-style:italic;font-size:13.5px;line-height:1.6}
  .ab-val.notes-text{color:var(--text-muted);font-size:12.5px}
</style>
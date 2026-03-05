<script>
  import { writable, derived } from 'svelte/store';
  import { MOCK_ENQUIRIES, ENQUIRY_RESOLUTION_OPTIONS, INTENT_COLORS } from '$lib/enquiry-data.js';

  // ── Stores ────────────────────────────────────────────────────────────────
  const enquiries     = writable(MOCK_ENQUIRIES);
  const selectedId    = writable(null);
  const searchQuery   = writable('');
  const activeTab     = writable('open');

  const selected = derived(
    [enquiries, selectedId],
    ([$eq, $id]) => $eq.find(e => e.id === $id) ?? null
  );

  // ── Filtered list ─────────────────────────────────────────────────────────
  $: filtered = $enquiries.filter(e => {
    const tabMatch =
      $activeTab === 'all' ? true :
      $activeTab === 'open' ? (e.status === 'open' || e.status === 'in_progress') :
      e.status === $activeTab;

    if (!tabMatch) return false;
    if ($searchQuery) {
      const q = $searchQuery.toLowerCase();
      return (
        e.id.toLowerCase().includes(q) ||
        e.sender.name.toLowerCase().includes(q) ||
        e.subject.toLowerCase().includes(q) ||
        e.intentLabel.toLowerCase().includes(q) ||
        (e.sender.company ?? '').toLowerCase().includes(q)
      );
    }
    return true;
  });

  $: counts = {
    open:      $enquiries.filter(e => e.status === 'open' || e.status === 'in_progress').length,
    escalated: $enquiries.filter(e => e.status === 'escalated').length,
    resolved:  $enquiries.filter(e => e.status === 'resolved').length,
    all:       $enquiries.length,
  };

  // ── UI state machine ──────────────────────────────────────────────────────
  // stages: 'idle' | 'ai_loading' | 'ai_shown' | 'resolving' | 'resolved'
  let uiStage          = 'idle';
  let aiResult         = null;
  let aiError          = null;
  let chosenResolution = null;
  let resolveLoading   = false;

  $: if ($selected) {
    if ($selected.status === 'resolved') {
      uiStage = 'resolved';
      chosenResolution = ENQUIRY_RESOLUTION_OPTIONS.find(o => o.id === $selected.resolution) ?? null;
    } else {
      uiStage = 'idle';
      chosenResolution = null;
    }
    aiResult = $selected.aiAnalysis ?? null;
    aiError  = null;
    resolveLoading = false;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function formatDate(str) {
    if (!str) return '—';
    return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function formatTime(str) {
    if (!str) return '';
    return new Date(str).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }

  function channelIcon(ch) {
    return ch === 'voicemail' ? '🎙' : '✉';
  }

  function senderTypeColor(t) {
    return t === 'vendor' ? 'purple' : 'blue';
  }

  function intentColor(intent) {
    return INTENT_COLORS[intent] ?? 'blue';
  }

  function statusColor(s) {
    return s === 'resolved' ? 'green' : s === 'escalated' ? 'red' : s === 'in_progress' ? 'amber' : 'blue';
  }

  function statusLabel(s) {
    return s === 'in_progress' ? 'In Progress' :
           s.charAt(0).toUpperCase() + s.slice(1);
  }

  function priorityColor(p) {
    return p === 'critical' ? 'red' : p === 'high' ? 'orange' : p === 'medium' ? 'amber' : 'blue';
  }

  function resolutionLabel(id) { return ENQUIRY_RESOLUTION_OPTIONS.find(o => o.id === id)?.label ?? id; }
  function resolutionColor(id) { return ENQUIRY_RESOLUTION_OPTIONS.find(o => o.id === id)?.color ?? 'amber'; }
  function resolutionIcon(id)  { return ENQUIRY_RESOLUTION_OPTIONS.find(o => o.id === id)?.icon  ?? '—'; }

  // ── Actions ───────────────────────────────────────────────────────────────
  async function handleAiAnalyze() {
    if (!$selected) return;
    // If already have a result (pre-loaded from mock), just show it
    if ($selected.aiAnalysis) { aiResult = $selected.aiAnalysis; uiStage = 'ai_shown'; return; }

    uiStage  = 'ai_loading';
    aiResult = null;
    aiError  = null;

    // Stub: simulate API call — real FastAPI endpoint wired in next iteration
    await new Promise(r => setTimeout(r, 1400));
    aiResult = {
      action:           'draft_response',
      actionLabel:      'Draft & Send Response',
      actionRationale:  `${$selected.sender.name} submitted a ${$selected.intentLabel.toLowerCase()} via ${$selected.channel}. Standard response with relevant policy information is recommended.`,
      suggestedResponse: `Hi ${$selected.sender.name.split(' ')[0]},\n\nThank you for reaching out to Arcella Support. We've received your enquiry and are looking into this for you.\n\nWe'll follow up within 1 business day with a full response.\n\nWarm regards,\nArcella Customer Care`,
      confidence:       0.78,
      flags: $selected.escalationSignals?.length
        ? [{ label: 'Escalation signals detected', severity: 'high' }]
        : [],
    };
    uiStage = 'ai_shown';
  }

  function handleStartResolve() { uiStage = 'resolving'; }
  function handleBack()         { uiStage = aiResult ? 'ai_shown' : 'idle'; }

  function handlePickResolution(opt) { chosenResolution = opt; }

  async function handleConfirmResolve() {
    if (!$selected || !chosenResolution) return;
    resolveLoading = true;
    await new Promise(r => setTimeout(r, 600));

    enquiries.update(all => all.map(e =>
      e.id === $selected.id
        ? { ...e, status: 'resolved', resolution: chosenResolution.id, updated: new Date().toISOString() }
        : e
    ));
    uiStage = 'resolved';
    resolveLoading = false;
  }
</script>

<div class="dashboard">
  <!-- Topbar -->
  <header class="topbar">
    <div class="topbar-left">
      <h2>Enquiry Tickets</h2>
      <div class="breadcrumb">Inbound · Email & Voicemail · Customers & Vendors</div>
    </div>
    <div class="topbar-stats">
      <div class="stat-pill">
        <span class="dot" style="background:var(--blue)"></span>
        {counts.open} Open
      </div>
      <div class="stat-pill">
        <span class="dot" style="background:var(--red)"></span>
        {counts.escalated} Escalated
      </div>
      <div class="stat-pill">
        <span class="dot" style="background:var(--green)"></span>
        {counts.resolved} Resolved
      </div>
      <div class="stat-pill">
        <span class="dot" style="background:var(--text-muted)"></span>
        {counts.all} Total
      </div>
    </div>
  </header>

  <div class="split-view">
    <!-- Left: ticket list -->
    <div class="list-panel">
      <div class="list-filters">
        <input
          class="search-input"
          type="text"
          placeholder="Search by sender, subject, intent…"
          bind:value={$searchQuery}
        />
      </div>

      <div class="filter-tabs">
        {#each [['open','Open'],['escalated','Escalated'],['resolved','Resolved'],['all','All']] as [val, label]}
          <button
            class="tab-btn"
            class:active={$activeTab === val}
            on:click={() => activeTab.set(val)}
          >
            {label}
            <span class="tab-count">{val === 'open' ? counts.open : val === 'escalated' ? counts.escalated : val === 'resolved' ? counts.resolved : counts.all}</span>
          </button>
        {/each}
      </div>

      <div class="ticket-list">
        {#each filtered as e (e.id)}
          <button
            class="ticket-row"
            class:active={$selectedId === e.id}
            on:click={() => selectedId.set(e.id)}
          >
            <!-- Row top: id + channel + time -->
            <div class="row-top">
              <span class="ticket-id">{e.id}</span>
              <span class="channel-icon" title={e.channel}>{channelIcon(e.channel)}</span>
              <span class="row-time">{formatTime(e.created)}</span>
              <span class="row-dot dot-{statusColor(e.status)}"></span>
            </div>

            <!-- Subject -->
            <div class="row-subject">{e.subject}</div>

            <!-- Sender + intent -->
            <div class="row-meta">
              <span class="row-sender">{e.sender.name}{e.sender.company ? ` · ${e.sender.company}` : ''}</span>
              <span class="sender-badge badge-{senderTypeColor(e.senderType)}">{e.senderType}</span>
            </div>

            <!-- Intent + priority -->
            <div class="row-bottom">
              <span class="intent-badge badge-{intentColor(e.intent)}">{e.intentLabel}</span>
              <span class="priority-badge badge-{priorityColor(e.priority)}">{e.priority}</span>
            </div>

            <!-- Escalation warning -->
            {#if e.escalationSignals?.length}
              <div class="row-escalation-warn">⚠ Escalation signals detected</div>
            {/if}
          </button>
        {/each}

        {#if filtered.length === 0}
          <div class="empty-state">No enquiries match your filter</div>
        {/if}
      </div>
    </div>

    <!-- Right: detail panel -->
    <div class="detail-panel">
      {#if $selected}
        {@const e = $selected}
        <div class="detail-content">

          <!-- Header -->
          <div class="detail-header">
            <div class="detail-header-top">
              <div class="header-ids">
                <span class="detail-id">{e.id}</span>
                <span class="status-badge badge-{statusColor(e.status)}">{statusLabel(e.status)}</span>
                <span class="priority-badge-lg badge-{priorityColor(e.priority)}">{e.priority}</span>
              </div>
              <div class="header-meta">
                <span class="channel-pill">{channelIcon(e.channel)} {e.channel}</span>
                <span class="date-muted">{formatDate(e.created)} {formatTime(e.created)}</span>
              </div>
            </div>
            <h3 class="detail-subject">{e.subject}</h3>
            <div class="intent-row">
              <span class="intent-badge-lg badge-{intentColor(e.intent)}">{e.intentLabel}</span>
              {#if e.orderRef}
                <span class="order-ref">Ref: {e.orderRef}</span>
              {/if}
              {#if e.assignedTo}
                <span class="assigned-to">Assigned: {e.assignedTo}</span>
              {/if}
            </div>
          </div>

          <!-- Message preview -->
          <div class="detail-section message-section">
            <div class="section-label">
              {e.channel === 'voicemail' ? '🎙 Voicemail Transcript' : '✉ Message'}
            </div>
            <p class="message-body">{e.preview}</p>
          </div>

          <!-- Two-col: sender + enquiry signals -->
          <div class="two-col">
            <!-- Sender card -->
            <div class="detail-section">
              <div class="section-label">
                {e.senderType === 'vendor' ? 'Vendor Details' : 'Customer Details'}
              </div>
              <div class="sender-card">
                <div class="sender-avatar sender-avatar-{senderTypeColor(e.senderType)}">
                  {e.sender.name.split(' ').map(n => n[0]).join('').slice(0,2)}
                </div>
                <div class="sender-body">
                  <div class="sender-name-row">
                    <span class="sender-name">{e.sender.name}</span>
                    <span class="sender-type-badge badge-{senderTypeColor(e.senderType)}">{e.senderType}</span>
                  </div>
                  {#if e.sender.company}
                    <div class="sender-company">{e.sender.company}</div>
                  {/if}
                  <div class="sender-contact">
                    <span class="contact-icon">✉</span>
                    <span class="contact-val">{e.sender.email}</span>
                  </div>
                  {#if e.sender.phone}
                    <div class="sender-contact">
                      <span class="contact-icon">☏</span>
                      <span class="contact-val">{e.sender.phone}</span>
                    </div>
                  {/if}
                  {#if e.senderType === 'customer'}
                    <div class="sender-stats">
                      <div class="sender-stat">
                        <span class="stat-val tier-{(e.sender.tier ?? 'bronze').toLowerCase()}">{e.sender.tier ?? '—'}</span>
                        <span class="stat-label">Tier</span>
                      </div>
                      <div class="sender-stat">
                        <span class="stat-val">{e.sender.ltv ?? '—'}</span>
                        <span class="stat-label">Est. LTV</span>
                      </div>
                      <div class="sender-stat">
                        <span class="stat-val">{e.sender.totalOrders ?? 0}</span>
                        <span class="stat-label">Orders</span>
                      </div>
                    </div>
                  {/if}
                </div>
              </div>
            </div>

            <!-- Signals -->
            <div class="detail-section">
              <div class="section-label">Signals</div>
              <div class="signals-list">
                <div class="signal-row">
                  <span class="signal-label">Urgency</span>
                  <div class="urgency-bar">
                    {#each [1,2,3,4,5] as n}
                      <div class="urgency-pip" class:filled={n <= e.urgency} class:pip-critical={e.urgency === 5 && n <= 5} class:pip-high={e.urgency === 4 && n <= 4}></div>
                    {/each}
                    <span class="urgency-label">{e.urgency}/5</span>
                  </div>
                </div>
                <div class="signal-row">
                  <span class="signal-label">Sentiment</span>
                  <span class="sentiment-val sentiment-{e.sentiment}">{e.sentiment}</span>
                </div>
                <div class="signal-row">
                  <span class="signal-label">Channel</span>
                  <span class="signal-chip">{channelIcon(e.channel)} {e.channel}</span>
                </div>
                {#if e.tags?.length}
                  <div class="signal-row tags-row">
                    <span class="signal-label">Tags</span>
                    <div class="tags-list">
                      {#each e.tags as tag}
                        <span class="tag">{tag}</span>
                      {/each}
                    </div>
                  </div>
                {/if}
                {#if e.escalationSignals?.length}
                  <div class="escalation-alert">
                    <span class="esc-icon">⚠</span>
                    <div>
                      <div class="esc-title">Escalation Signals</div>
                      <div class="esc-list">{e.escalationSignals.join(' · ')}</div>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          </div>

          <!-- ── AI Analysis panel (pre-loaded or fetched) ── -->
          {#if aiResult && (uiStage === 'ai_shown' || uiStage === 'resolving' || uiStage === 'resolved')}
            <div class="detail-section ai-section">
              <div class="section-label">
                AI Analysis
                <span class="ai-tag">✦ LLM</span>
                <span class="confidence-badge">
                  {Math.round((aiResult.confidence ?? 0.8) * 100)}% confidence
                </span>
              </div>

              <div class="ai-action-block action-{aiResult.action}">
                <div class="ai-action-header">
                  <span class="ai-action-label">{aiResult.actionLabel}</span>
                  <span class="ai-action-type">{aiResult.action.replace(/_/g, ' ')}</span>
                </div>
                <p class="ai-rationale">{aiResult.actionRationale}</p>
              </div>

              {#if aiResult.suggestedResponse}
                <div class="suggested-response">
                  <div class="sr-label">Suggested Response Draft</div>
                  <pre class="sr-body">{aiResult.suggestedResponse}</pre>
                </div>
              {/if}

              {#if aiResult.flags?.length}
                <div class="ai-flags">
                  {#each aiResult.flags as flag}
                    <div class="ai-flag flag-{flag.severity}">
                      <span class="flag-label">{flag.label}</span>
                      <span class="flag-sev">{flag.severity}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <!-- ── Action bar state machine ── -->

          {#if uiStage === 'idle'}
            <!-- Pre-loaded AI available: show mini hint -->
            {#if aiResult}
              <div class="ai-hint-bar">
                <span>✦ AI analysis available for this ticket</span>
                <button class="link-btn" on:click={() => uiStage = 'ai_shown'}>View</button>
              </div>
            {/if}
            {#if aiError}
              <div class="ai-error-banner">⚠ AI analysis failed: {aiError}</div>
            {/if}
            <div class="action-bar">
              <button class="btn-action btn-ai" on:click={handleAiAnalyze}>✦ AI Analyze</button>
              <button class="btn-action btn-resolve" on:click={handleStartResolve}>✎ Resolve</button>
            </div>

          {:else if uiStage === 'ai_loading'}
            <div class="ai-loading-block">
              <span class="spinner-sm"></span>
              <span>Running AI analysis…</span>
            </div>

          {:else if uiStage === 'ai_shown'}
            <div class="action-bar">
              <button class="btn-action btn-resolve" on:click={handleStartResolve}>✎ Resolve Ticket</button>
              <button class="btn-action btn-secondary" on:click={() => uiStage = 'idle'}>← Back</button>
            </div>

          {:else if uiStage === 'resolving'}
            <div class="detail-section resolution-section">
              <div class="section-label">
                Select Resolution
                <button class="link-btn" on:click={handleBack}>← Back</button>
              </div>
              <div class="resolution-grid">
                {#each ENQUIRY_RESOLUTION_OPTIONS as opt}
                  <button
                    class="res-option color-{opt.color}"
                    class:selected={chosenResolution?.id === opt.id}
                    on:click={() => handlePickResolution(opt)}
                  >
                    <span class="res-icon">{opt.icon}</span>
                    <span class="res-label">{opt.label}</span>
                    <span class="res-desc">{opt.desc}</span>
                  </button>
                {/each}
              </div>
              {#if chosenResolution}
                <div class="action-bar" style="margin-top:12px">
                  <button
                    class="btn-action btn-confirm"
                    on:click={handleConfirmResolve}
                    disabled={resolveLoading}
                  >
                    {#if resolveLoading}
                      <span class="spinner-sm"></span> Saving…
                    {:else}
                      ✓ Confirm — {chosenResolution.label}
                    {/if}
                  </button>
                </div>
              {/if}
            </div>

          {:else if uiStage === 'resolved'}
            {#if chosenResolution ?? ($selected.resolution && resolutionLabel($selected.resolution))}
              <div class="closed-banner">
                ✓ Ticket resolved · {chosenResolution?.label ?? resolutionLabel($selected.resolution)}
              </div>
            {/if}
          {/if}

        </div>
      {:else}
        <div class="detail-empty">
          <div class="empty-icon">✉</div>
          <div>Select a ticket to review</div>
          <div class="empty-sub">Inbound · Email & Voicemail · Customers & Vendors</div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  /* ── Layout ── */
  .dashboard{display:flex;flex-direction:column;height:100vh;overflow:hidden}

  .topbar{display:flex;align-items:center;justify-content:space-between;padding:16px 24px;border-bottom:1px solid var(--border);background:var(--bg-surface);flex-shrink:0}
  .topbar-left h2{font-family:var(--font-display);font-size:20px;font-weight:400;line-height:1}
  .breadcrumb{font-size:11px;color:var(--text-muted);font-family:var(--font-mono);margin-top:4px}
  .topbar-stats{display:flex;gap:8px;flex-wrap:wrap}
  .stat-pill{display:flex;align-items:center;gap:7px;padding:6px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:20px;font-size:12px;font-weight:600;font-family:var(--font-mono);color:var(--text-secondary)}
  .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

  .split-view{display:flex;overflow:hidden;height:calc(100vh - 65px)}

  /* ── List panel ── */
  .list-panel{width:380px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column;height:100%;overflow:hidden}
  .list-filters{padding:12px 14px 8px;flex-shrink:0}
  .search-input{width:100%;padding:8px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);font-size:13px;outline:none}
  .search-input:focus{border-color:rgba(212,168,67,0.4)}
  .search-input::placeholder{color:var(--text-muted)}

  .filter-tabs{display:flex;border-bottom:1px solid var(--border);flex-shrink:0}
  .tab-btn{flex:1;padding:8px 4px;background:none;border:none;border-bottom:2px solid transparent;color:var(--text-muted);font-size:11px;font-weight:600;font-family:var(--font-mono);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:4px;transition:all 0.15s;margin-bottom:-1px}
  .tab-btn:hover{color:var(--text-secondary)}
  .tab-btn.active{color:var(--amber);border-bottom-color:var(--amber)}
  .tab-count{background:var(--bg-elevated);border:1px solid var(--border);padding:1px 5px;border-radius:10px;font-size:9px}
  .tab-btn.active .tab-count{background:var(--amber-glow);border-color:rgba(212,168,67,0.3);color:var(--amber)}

  .ticket-list{flex:1;overflow-y:auto;padding:8px}
  .empty-state{text-align:center;color:var(--text-muted);font-size:13px;padding:40px}

  /* ── Ticket row ── */
  .ticket-row{width:100%;text-align:left;background:#1a1f2e;border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 14px;margin-bottom:6px;cursor:pointer;transition:background 0.1s,border-color 0.1s;display:block;color:var(--text-primary)}
  .ticket-row:hover{background:var(--bg-elevated);border-color:rgba(212,168,67,0.2)}
  .ticket-row.active{background:var(--bg-hover);border-color:rgba(212,168,67,0.4)}

  .row-top{display:flex;align-items:center;gap:6px;margin-bottom:5px}
  .ticket-id{font-family:var(--font-mono);font-size:11px;color:var(--text-muted);flex:1}
  .channel-icon{font-size:12px}
  .row-time{font-family:var(--font-mono);font-size:10px;color:var(--text-muted)}
  .row-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
  .dot-blue{background:var(--blue)}
  .dot-green{background:var(--green)}
  .dot-red{background:var(--red)}
  .dot-amber{background:var(--amber)}

  .row-subject{font-size:12.5px;font-weight:600;color:var(--text-primary);margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .row-meta{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
  .row-sender{font-size:11.5px;color:var(--text-secondary);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-right:6px}
  .row-bottom{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
  .row-escalation-warn{font-size:10px;color:var(--orange);font-family:var(--font-mono);margin-top:5px;font-weight:600}

  /* ── Badges ── */
  .sender-badge,.intent-badge,.priority-badge{font-family:var(--font-mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;padding:2px 6px;border-radius:3px;flex-shrink:0}
  .badge-blue{background:var(--blue-dim);color:var(--blue)}
  .badge-green{background:var(--green-dim);color:var(--green)}
  .badge-red{background:var(--red-dim);color:var(--red)}
  .badge-amber{background:var(--amber-glow);color:var(--amber)}
  .badge-orange{background:var(--orange-dim);color:var(--orange)}
  .badge-purple{background:rgba(160,100,240,0.12);color:#a064f0}

  /* ── Detail panel ── */
  .detail-panel{flex:1;overflow-y:auto;background:var(--bg-base)}
  .detail-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px;color:var(--text-muted);font-size:13px}
  .empty-icon{font-size:36px;opacity:0.2}
  .empty-sub{font-size:11px;opacity:0.5;font-family:var(--font-mono)}
  .detail-content{padding:28px;max-width:820px}

  .detail-header{margin-bottom:20px;padding-bottom:18px;border-bottom:1px solid var(--border)}
  .detail-header-top{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px}
  .header-ids{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .detail-id{font-family:var(--font-mono);font-size:12px;color:var(--text-muted)}
  .header-meta{display:flex;align-items:center;gap:10px;flex-shrink:0}
  .channel-pill{font-size:11px;font-family:var(--font-mono);color:var(--text-secondary);background:var(--bg-elevated);border:1px solid var(--border);padding:2px 8px;border-radius:10px}
  .date-muted{font-family:var(--font-mono);font-size:11px;color:var(--text-muted)}
  .detail-subject{font-family:var(--font-display);font-size:20px;font-weight:400;line-height:1.35;margin-bottom:10px}
  .intent-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .intent-badge-lg,.status-badge,.priority-badge-lg{font-family:var(--font-mono);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;padding:3px 9px;border-radius:20px}
  .order-ref,.assigned-to{font-size:11.5px;font-family:var(--font-mono);color:var(--text-muted);background:var(--bg-elevated);border:1px solid var(--border);padding:2px 8px;border-radius:3px}

  .detail-section{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:16px;margin-bottom:12px}
  .section-label{font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;font-family:var(--font-mono);margin-bottom:14px;display:flex;align-items:center;gap:8px}

  .message-section{}
  .message-body{font-size:13px;color:var(--text-secondary);line-height:1.7;white-space:pre-wrap}

  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:0}

  /* ── Sender card ── */
  .sender-card{display:flex;gap:12px;align-items:flex-start}
  .sender-avatar{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--font-mono);font-size:12px;font-weight:700;flex-shrink:0;border:1px solid var(--border)}
  .sender-avatar-blue{background:var(--blue-dim);color:var(--blue)}
  .sender-avatar-purple{background:rgba(160,100,240,0.12);color:#a064f0}
  .sender-body{flex:1;min-width:0}
  .sender-name-row{display:flex;align-items:center;gap:8px;margin-bottom:3px}
  .sender-name{font-size:14px;font-weight:600;color:var(--text-primary)}
  .sender-type-badge{font-family:var(--font-mono);font-size:9px;font-weight:700;text-transform:uppercase;padding:2px 6px;border-radius:3px}
  .sender-company{font-size:12px;color:var(--text-secondary);margin-bottom:6px}
  .sender-contact{display:flex;align-items:center;gap:7px;margin-bottom:4px}
  .contact-icon{font-size:11px;color:var(--text-muted);width:16px}
  .contact-val{font-size:12px;font-family:var(--font-mono);color:var(--text-secondary)}
  .sender-stats{display:flex;gap:20px;margin-top:10px;padding-top:10px;border-top:1px solid var(--border-subtle)}
  .sender-stat{display:flex;flex-direction:column;gap:2px}
  .stat-val{font-family:var(--font-mono);font-size:13px;font-weight:600;color:var(--text-primary)}
  .stat-label{font-size:9.5px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em}
  .tier-gold{color:var(--amber)}
  .tier-silver{color:#b0b8c8}
  .tier-bronze{color:#cd7f32}
  .tier-platinum{color:#a8d8f0}

  /* ── Signals ── */
  .signals-list{display:flex;flex-direction:column;gap:10px}
  .signal-row{display:flex;align-items:center;justify-content:space-between;gap:8px}
  .signal-label{font-size:11px;color:var(--text-muted);font-family:var(--font-mono);flex-shrink:0}
  .urgency-bar{display:flex;align-items:center;gap:3px}
  .urgency-pip{width:16px;height:5px;border-radius:2px;background:var(--border)}
  .urgency-pip.filled{background:var(--blue)}
  .urgency-pip.filled.pip-critical{background:var(--red)}
  .urgency-pip.filled.pip-high{background:var(--orange)}
  .urgency-label{font-family:var(--font-mono);font-size:10px;color:var(--text-muted);margin-left:4px}
  .sentiment-val{font-size:12px;font-family:var(--font-mono);font-weight:600}
  .sentiment-frustrated{color:var(--red)}
  .sentiment-anxious,.sentiment-concerned{color:var(--orange)}
  .sentiment-neutral{color:var(--text-secondary)}
  .signal-chip{font-size:11px;font-family:var(--font-mono);color:var(--text-secondary);background:var(--bg-elevated);border:1px solid var(--border);padding:2px 7px;border-radius:3px}
  .tags-row{align-items:flex-start}
  .tags-list{display:flex;flex-wrap:wrap;gap:4px;justify-content:flex-end}
  .tag{font-size:9.5px;font-family:var(--font-mono);color:var(--text-muted);background:var(--bg-elevated);border:1px solid var(--border);padding:1px 6px;border-radius:3px}
  .escalation-alert{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;background:var(--red-dim);border:1px solid rgba(224,92,92,0.25);border-radius:var(--radius-sm);margin-top:4px}
  .esc-icon{font-size:14px;flex-shrink:0;color:var(--orange)}
  .esc-title{font-size:11.5px;font-weight:700;color:var(--text-primary);margin-bottom:2px}
  .esc-list{font-size:11px;font-family:var(--font-mono);color:var(--red)}

  /* ── AI section ── */
  .ai-section{border-color:rgba(212,168,67,0.2)}
  .ai-tag{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600;color:var(--amber);background:var(--amber-glow);border:1px solid rgba(212,168,67,0.3)}
  .confidence-badge{font-size:10px;font-family:var(--font-mono);color:var(--text-muted);background:var(--bg-elevated);border:1px solid var(--border);padding:2px 7px;border-radius:10px}
  .ai-action-block{padding:12px 14px;border-radius:var(--radius-sm);margin-bottom:12px;border:1px solid}
  .action-draft_response,.action-update_and_confirm{background:rgba(76,175,130,0.08);border-color:rgba(76,175,130,0.25)}
  .action-route_to_procurement,.action-escalate_finance{background:rgba(224,92,92,0.08);border-color:rgba(224,92,92,0.25)}
  .ai-action-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
  .ai-action-label{font-size:13.5px;font-weight:700;color:var(--text-primary)}
  .ai-action-type{font-family:var(--font-mono);font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em}
  .ai-rationale{font-size:12.5px;color:var(--text-secondary);line-height:1.6}
  .suggested-response{margin-top:10px}
  .sr-label{font-size:10px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;font-family:var(--font-mono);margin-bottom:8px}
  .sr-body{font-size:12.5px;font-family:var(--font-mono);color:var(--text-secondary);line-height:1.65;white-space:pre-wrap;background:var(--bg-elevated);border:1px solid var(--border);padding:12px;border-radius:var(--radius-sm)}
  .ai-flags{display:flex;flex-direction:column;gap:5px;margin-top:10px}
  .ai-flag{display:flex;align-items:center;justify-content:space-between;padding:6px 10px;border-radius:var(--radius-sm);font-size:12px}
  .flag-critical{background:var(--red-dim);border:1px solid rgba(224,92,92,0.25)}
  .flag-high{background:var(--orange-dim);border:1px solid rgba(224,138,60,0.25)}
  .flag-medium{background:var(--amber-glow);border:1px solid rgba(212,168,67,0.25)}
  .flag-label{font-weight:600;color:var(--text-primary)}
  .flag-sev{font-family:var(--font-mono);font-size:10px;text-transform:uppercase;color:var(--text-muted)}

  /* ── Action bars ── */
  .ai-hint-bar{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--amber-glow);border:1px solid rgba(212,168,67,0.2);border-radius:var(--radius-sm);font-size:12px;color:var(--amber);margin-bottom:8px;font-family:var(--font-mono)}
  .ai-error-banner{padding:10px 14px;background:var(--red-dim);border:1px solid rgba(224,92,92,0.3);border-radius:var(--radius-sm);color:var(--red);font-size:12px;margin-bottom:8px}
  .ai-loading-block{display:flex;align-items:center;gap:12px;padding:20px 0;color:var(--amber);font-size:13px;font-weight:600;font-family:var(--font-mono)}
  .ai-loading-block .spinner-sm{border-color:rgba(212,168,67,0.3);border-top-color:var(--amber)}

  .action-bar{display:flex;gap:10px;margin-top:4px;margin-bottom:12px}
  .btn-action{display:flex;align-items:center;gap:8px;padding:10px 20px;border-radius:var(--radius-sm);font-size:13px;font-weight:600;letter-spacing:0.03em;transition:all 0.15s;border:1px solid;cursor:pointer}
  .btn-action:disabled{opacity:0.5;cursor:not-allowed}
  .btn-ai{background:var(--amber-glow);border-color:rgba(212,168,67,0.4);color:var(--amber)}
  .btn-ai:hover{background:rgba(212,168,67,0.2)}
  .btn-resolve{background:var(--blue-dim);border-color:rgba(91,140,240,0.4);color:var(--blue)}
  .btn-resolve:hover{background:rgba(91,140,240,0.2)}
  .btn-secondary{background:var(--bg-elevated);border-color:var(--border);color:var(--text-secondary)}
  .btn-secondary:hover{background:var(--bg-hover)}
  .btn-confirm{background:var(--green);border-color:var(--green);color:#0c0e14}
  .btn-confirm:hover:not(:disabled){background:#5dc99a}

  /* ── Resolution grid ── */
  .resolution-section{border-color:rgba(91,140,240,0.2)}
  .resolution-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
  .res-option{text-align:left;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px;cursor:pointer;transition:all 0.15s;display:flex;flex-direction:column;gap:4px}
  .res-option.selected{border-width:2px}
  .res-icon{font-size:16px;line-height:1}
  .res-label{font-size:12px;font-weight:700;color:var(--text-primary)}
  .res-desc{font-size:10.5px;color:var(--text-muted);line-height:1.45}
  .color-green.res-option:hover,.color-green.res-option.selected{border-color:rgba(76,175,130,0.6);background:rgba(76,175,130,0.06)}
  .color-amber.res-option:hover,.color-amber.res-option.selected{border-color:rgba(212,168,67,0.6);background:rgba(212,168,67,0.06)}
  .color-red.res-option:hover,.color-red.res-option.selected{border-color:rgba(224,92,92,0.6);background:rgba(224,92,92,0.06)}
  .color-orange.res-option:hover,.color-orange.res-option.selected{border-color:rgba(224,138,60,0.6);background:rgba(224,138,60,0.06)}
  .color-blue.res-option:hover,.color-blue.res-option.selected{border-color:rgba(91,140,240,0.6);background:rgba(91,140,240,0.06)}

  .closed-banner{display:flex;align-items:center;gap:10px;padding:14px 18px;background:var(--green-dim);border:1px solid rgba(76,175,130,0.3);border-radius:var(--radius-md);color:var(--green);font-weight:600;font-size:14px;margin-bottom:12px}

  .link-btn{background:none;border:none;color:var(--amber);font-size:11px;cursor:pointer;padding:0;font-family:var(--font-mono);text-decoration:underline}
  .link-btn:hover{opacity:0.8}

  .spinner-sm{width:13px;height:13px;border:2px solid rgba(0,0,0,0.2);border-top-color:currentColor;border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block}
  @keyframes spin{to{transform:rotate(360deg)}}
</style>

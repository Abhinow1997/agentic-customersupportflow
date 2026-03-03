<script>
  import { onMount } from 'svelte';
  import {
    filteredTickets, filters, selectedTicketId, selectedTicket,
    tickets, ticketsLoading, ticketsError,
    updateTicketStatus, loadTickets
  } from '$lib/stores.js';

  let reasons = [];
  let reasonsLoading = true;
  let reasonsError = '';

  onMount(async () => {
    // Load tickets from Snowflake
    loadTickets();

    // Load reason labels from Snowflake
    try {
      const res = await fetch('/api/reasons');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      reasons = data.reasons;
    } catch (e) {
      reasonsError = e.message;
    } finally {
      reasonsLoading = false;
    }
  });

  function resolveIssueLabel(issueType) {
    if (!reasons.length) return issueType.replace(/_/g, ' ');
    const match = reasons.find(r =>
      r.desc.toLowerCase().includes(issueType.replace(/_/g, ' ').toLowerCase()) ||
      issueType.toLowerCase().includes(r.desc.toLowerCase().split(' ').slice(0, 2).join(' '))
    );
    return match ? match.desc : issueType.replace(/_/g, ' ');
  }

  $: openCount      = $tickets.filter(t => t.status === 'open').length;
  $: criticalCount  = $tickets.filter(t => t.priority === 'critical').length;
  $: escalatedCount = $tickets.filter(t => t.status === 'escalated').length;
  $: aiReadyCount   = $tickets.filter(t => t.ai_draft && t.supervisor?.approved).length;

  function selectTicket(id) { selectedTicketId.set(id); }

  function timeAgo(dateStr) {
    const diff  = Date.now() - new Date(dateStr).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    if (mins < 60)  return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function getSentimentIcon(score) {
    if (score <= -0.7) return '😤';
    if (score <= -0.3) return '😞';
    if (score <= 0.2)  return '😐';
    return '😊';
  }

  let draftEdited = '';
  let actionDone  = '';

  $: if ($selectedTicket) {
    draftEdited = $selectedTicket.ai_draft || '';
    actionDone  = '';
  }

  function handleSend()     { if ($selectedTicket) { updateTicketStatus($selectedTicket.id, 'resolved');  actionDone = 'sent'; } }
  function handleEscalate() { if ($selectedTicket) { updateTicketStatus($selectedTicket.id, 'escalated'); actionDone = 'escalated'; } }
  function handleRevise()   { actionDone = 'revising'; }

  function setStatus(e)   { filters.update(f => ({ ...f, status:   e.target.value })); }
  function setPriority(e) { filters.update(f => ({ ...f, priority: e.target.value })); }
  function setSearch(e)   { filters.update(f => ({ ...f, search:   e.target.value })); }
</script>

<div class="dashboard">
  <header class="topbar">
    <div class="topbar-left">
      <h2>Ticket Queue</h2>
      <div class="breadcrumb">Customer Operations · Live from Snowflake</div>
    </div>
    <div class="topbar-stats">
      <div class="stat-pill"><span class="dot" style="background:var(--blue)"></span>{openCount} Open</div>
      <div class="stat-pill"><span class="dot" style="background:var(--red)"></span>{criticalCount} Critical</div>
      <div class="stat-pill"><span class="dot" style="background:var(--orange)"></span>{escalatedCount} Escalated</div>
      <div class="stat-pill"><span class="dot" style="background:var(--green)"></span>{aiReadyCount} AI Ready</div>
      <div class="stat-pill">
        <span class="dot" style="background:{$ticketsLoading ? 'var(--text-muted)' : $ticketsError ? 'var(--red)' : 'var(--amber)'}"></span>
        {#if $ticketsLoading}Fetching…{:else if $ticketsError}DB Error{:else}{$tickets.length} Tickets{/if}
      </div>
    </div>
  </header>

  <div class="split-view">
    <!-- Ticket list panel -->
    <div class="ticket-list-panel">
      <div class="filters">
        <input class="search-input" type="text" placeholder="Search tickets, customers…" value={$filters.search} on:input={setSearch} />
        <div class="filter-row">
          <select value={$filters.status} on:change={setStatus}>
            <option value="all">All Status</option>
            <option value="open">Open</option>
            <option value="pending">Pending</option>
            <option value="escalated">Escalated</option>
            <option value="resolved">Resolved</option>
          </select>
          <select value={$filters.priority} on:change={setPriority}>
            <option value="all">All Priority</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div class="ticket-list">
          {#each $filteredTickets as ticket (ticket.id)}
            <button class="ticket-row" class:active={$selectedTicketId === ticket.id} on:click={() => selectTicket(ticket.id)}>
              <div class="ticket-row-top">
                <span class="ticket-id">{ticket.id}</span>
                <span class="badge {ticket.priority}">{ticket.priority}</span>
                <span class="time-ago">{timeAgo(ticket.created)}</span>
              </div>
              <div class="ticket-subject">{ticket.subject}</div>
              <div class="ticket-row-meta">
                <span class="customer-name">{ticket.customer.name}</span>
                <span class="tier-badge tier-{ticket.customer.tier.toLowerCase()}">{ticket.customer.tier}</span>
                <span class="badge {ticket.status}">{ticket.status}</span>
                {#if ticket.supervisor?.recommendation === 'revise'}
                  <span class="needs-revision">⚠ Needs Draft</span>
                {/if}
                {#if ticket.supervisor?.recommendation === 'escalate'}
                  <span class="needs-escalation">🔴 Escalate</span>
                {/if}
              </div>
              <div class="issue-chips">
                {#each ticket.issues.slice(0, 3) as issue}
                  <span class="issue-chip">{resolveIssueLabel(issue.type)}</span>
                {/each}
                {#if ticket.issues.length > 3}
                  <span class="issue-chip more">+{ticket.issues.length - 3}</span>
                {/if}
              </div>
            </button>
          {/each}
          {#if $filteredTickets.length === 0}
            <div class="empty-state">No tickets match your filters</div>
          {/if}
      </div>
    </div>

    <!-- Detail panel -->
    <div class="detail-panel">
      {#if $selectedTicket}
        {@const t = $selectedTicket}
        <div class="detail-content">
          <div class="detail-header">
            <div class="detail-header-top">
              <div>
                <span class="detail-id">{t.id}</span>
                <span class="badge {t.priority}">{t.priority}</span>
                <span class="badge {t.status}">{t.status}</span>
              </div>
              <div class="sentiment-chip">{getSentimentIcon(t.sentiment_score)} {t.sentiment}</div>
            </div>
            <h3 class="detail-subject">{t.subject}</h3>
          </div>

          <div class="detail-section">
            <div class="section-label">Customer</div>
            <div class="customer-card">
              <div class="cust-avatar">{t.customer.name.split(' ').map(n=>n[0]).join('')}</div>
              <div class="cust-info">
                <div class="cust-name">{t.customer.name}</div>
                <div class="cust-email">{t.customer.email}</div>
              </div>
              <div class="cust-stats">
                <div class="cust-stat">
                  <span class="cust-stat-val tier-{t.customer.tier.toLowerCase()}">{t.customer.tier}</span>
                  <span class="cust-stat-label">Tier</span>
                </div>
                <div class="cust-stat">
                  <span class="cust-stat-val">{t.customer.ltv}</span>
                  <span class="cust-stat-label">LTV</span>
                </div>
                <div class="cust-stat">
                  <span class="cust-stat-val">{t.customer.orders}</span>
                  <span class="cust-stat-label">Orders</span>
                </div>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="section-label">
              Extracted Issues <span class="section-count">{t.issues.length}</span>
              <span class="reasons-tag ok">✦ Snowflake</span>
            </div>
            <div class="issues-list">
              {#each t.issues as issue}
                <div class="issue-row">
                  <span class="issue-check {t.status === 'resolved' ? 'checked' : ''}">
                    {t.status === 'resolved' ? '✓' : '○'}
                  </span>
                  <div class="issue-text">
                    <span class="issue-type">{resolveIssueLabel(issue.type)}</span>
                    {#if issue.subtype}<span class="issue-sub">· {issue.subtype.replace(/_/g, ' ')}</span>{/if}
                    {#if issue.entity}<span class="issue-entity">{issue.entity}</span>{/if}
                  </div>
                  <span class="confidence-bar"><span class="conf-fill" style="width:{issue.confidence * 100}%"></span></span>
                  <span class="conf-num">{Math.round(issue.confidence * 100)}%</span>
                </div>
              {/each}
            </div>
          </div>

          {#if t.escalation_signals.length > 0}
            <div class="detail-section escalation-warning">
              <div class="section-label warn">⚠ Escalation Signals</div>
              <div class="signals">
                {#each t.escalation_signals as sig}
                  <span class="signal-tag">{sig.replace(/_/g, ' ')}</span>
                {/each}
              </div>
            </div>
          {/if}

          <div class="detail-section">
            <div class="section-label">
              Supervisor Check
              <span class="conf-score {(t.supervisor?.confidence_score ?? 0) >= 0.8 ? 'good' : (t.supervisor?.confidence_score ?? 0) >= 0.6 ? 'medium' : 'bad'}">
                {Math.round((t.supervisor?.confidence_score ?? 0) * 100)}% confidence
              </span>
            </div>
            {#if t.supervisor?.failures?.length > 0}
              <div class="failure-list">
                {#each t.supervisor.failures as f}
                  <div class="failure-row sev-{f.severity}">
                    <span class="failure-type">{f.type}</span>
                    <span class="failure-severity">{f.severity}</span>
                    {#if f.detail}<span class="failure-detail">{typeof f.detail === 'string' ? f.detail : f.detail.join(', ')}</span>{/if}
                  </div>
                {/each}
              </div>
            {:else}
              <div class="all-clear"><span>✓</span> All checks passed — ready to send</div>
            {/if}
          </div>

          <div class="detail-section">
            <div class="section-label">
              AI Draft
              {#if t.ai_draft}
                <span class="draft-status approved">Approved</span>
              {:else}
                <span class="draft-status no-draft">Pending generation</span>
              {/if}
            </div>
            {#if t.ai_draft}
              <textarea class="draft-textarea" bind:value={draftEdited} rows="10"></textarea>
            {:else}
              <div class="no-draft-msg">
                AI draft not yet generated for this ticket. Use Revise to compose manually, or Escalate to route to senior review.
              </div>
            {/if}
          </div>

          {#if actionDone === ''}
            <div class="action-bar">
              {#if t.ai_draft && t.supervisor?.approved}
                <button class="btn-action send" on:click={handleSend}>↑ Send to Customer</button>
              {/if}
              <button class="btn-action revise" on:click={handleRevise}>✎ Revise Manually</button>
              <button class="btn-action escalate" on:click={handleEscalate}>↗ Escalate</button>
            </div>
          {:else}
            <div class="action-done {actionDone}">
              {#if actionDone === 'sent'}✓ Response sent. Ticket resolved.
              {:else if actionDone === 'escalated'}↗ Escalated to senior queue.
              {:else}Edit the draft above, then Send or Escalate.
              {/if}
            </div>
          {/if}
        </div>
      {:else}
        <div class="detail-empty">
          <div class="empty-icon">⬡</div>
          <div>Select a ticket to review</div>
          <div class="empty-sub">Live data from Snowflake · STORE_RETURNS × REASON × CUSTOMER</div>
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
  .split-view{display:flex;overflow:hidden;height:calc(100vh - 65px)}
  .ticket-list-panel{width:360px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column;height:100%;overflow:hidden}
  .filters{padding:14px;border-bottom:1px solid var(--border-subtle);display:flex;flex-direction:column;gap:8px;flex-shrink:0}
  .search-input{width:100%;padding:8px 12px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);font-size:13px;outline:none}
  .search-input:focus{border-color:var(--amber-dim)}
  .search-input::placeholder{color:var(--text-muted)}
  .filter-row{display:flex;gap:8px}
  select{flex:1;padding:7px 10px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-secondary);font-size:12px;font-family:var(--font-body);outline:none;cursor:pointer}
  .ticket-list{height:calc(100vh - 160px);overflow-y:auto;padding:8px}
  .loading-state{display:flex;align-items:center;gap:10px;color:var(--text-muted);font-size:13px;padding:32px 16px;justify-content:center}
  .error-state{color:var(--red);font-size:13px;padding:20px 16px;background:var(--red-dim);border-radius:var(--radius-sm);margin:8px}
  .ticket-row{width:100%;text-align:left;background:#1a1f2e;border:1px solid var(--border);border-radius:var(--radius-md);padding:13px 14px;margin-bottom:4px;cursor:pointer;transition:background 0.1s,border-color 0.1s;display:block;color:var(--text-primary)}
  .ticket-row:hover{background:var(--bg-elevated);border-color:var(--border)}
  .ticket-row.active{background:var(--bg-hover);border-color:rgba(212,168,67,0.3)}
  .ticket-row-top{display:flex;align-items:center;gap:7px;margin-bottom:5px}
  .ticket-id{font-family:var(--font-mono);font-size:11px;color:var(--text-muted)}
  .time-ago{font-family:var(--font-mono);font-size:10.5px;color:var(--text-muted);margin-left:auto}
  .ticket-subject{font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:7px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .ticket-row-meta{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:7px}
  .customer-name{font-size:12px;color:var(--text-secondary)}D:\PromptEngineering\Assignment Final Project\agentic-customersupportflow\src\routes\dashboard\+page.svelte
  .tier-badge{font-family:var(--font-mono);font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;padding:2px 6px;border-radius:3px}
  .tier-platinum{color:#a8d8f0;background:rgba(168,216,240,0.12)}
  .tier-gold{color:var(--amber);background:var(--amber-glow)}
  .tier-silver{color:#b0b8c8;background:rgba(176,184,200,0.1)}
  .tier-bronze{color:#cd7f32;background:rgba(205,127,50,0.1)}
  .needs-revision{font-size:10.5px;color:var(--orange);font-family:var(--font-mono)}
  .needs-escalation{font-size:10.5px;color:var(--red);font-family:var(--font-mono)}
  .issue-chips{display:flex;flex-wrap:wrap;gap:4px}
  .issue-chip{font-size:10px;padding:2px 7px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:3px;color:var(--text-muted);font-family:var(--font-mono);text-transform:capitalize}
  .issue-chip.more{color:var(--amber);border-color:rgba(212,168,67,0.2)}
  .empty-state{text-align:center;color:var(--text-muted);font-size:13px;padding:40px}
  .detail-panel{flex:1;overflow-y:auto;background:var(--bg-base)}
  .detail-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px;color:var(--text-muted);font-size:13px}
  .empty-icon{font-size:32px;opacity:0.3}
  .empty-sub{font-size:12px;opacity:0.6}
  .detail-content{padding:24px;max-width:780px}
  .detail-header{margin-bottom:20px;padding-bottom:18px;border-bottom:1px solid var(--border-subtle)}
  .detail-header-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
  .detail-header-top>div{display:flex;align-items:center;gap:8px}
  .detail-id{font-family:var(--font-mono);font-size:12px;color:var(--text-muted)}
  .sentiment-chip{font-size:12.5px;color:var(--text-secondary);background:var(--bg-elevated);border:1px solid var(--border);padding:4px 11px;border-radius:20px;text-transform:capitalize}
  .detail-subject{font-family:var(--font-display);font-size:20px;font-weight:400;line-height:1.3}
  .detail-section{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:16px;margin-bottom:12px}
  .escalation-warning{border-color:rgba(224,92,92,0.3);background:rgba(224,92,92,0.05)}
  .section-label{font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.1em;font-family:var(--font-mono);margin-bottom:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .section-label.warn{color:var(--red)}
  .section-count{background:var(--bg-elevated);border:1px solid var(--border);padding:1px 7px;border-radius:10px;font-size:11px;color:var(--text-secondary)}
  .reasons-tag.ok{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600;color:var(--amber);background:var(--amber-glow);border:1px solid rgba(212,168,67,0.3)}
  .customer-card{display:flex;align-items:center;gap:14px}
  .cust-avatar{width:38px;height:38px;background:var(--bg-elevated);border:1px solid var(--border);border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--font-mono);font-size:12px;color:var(--amber);flex-shrink:0}
  .cust-info{flex:1}
  .cust-name{font-size:14px;font-weight:600;color:var(--text-primary)}
  .cust-email{font-size:12px;color:var(--text-muted);font-family:var(--font-mono)}
  .cust-stats{display:flex;gap:16px;text-align:right}
  .cust-stat{display:flex;flex-direction:column;align-items:flex-end}
  .cust-stat-val{font-family:var(--font-mono);font-size:13px;font-weight:500;color:var(--text-primary)}
  .cust-stat-label{font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em}
  .issues-list{display:flex;flex-direction:column;gap:8px}
  .issue-row{display:flex;align-items:center;gap:10px}
  .issue-check{font-family:var(--font-mono);font-size:13px;width:16px;color:var(--text-muted);flex-shrink:0}
  .issue-check.checked{color:var(--green)}
  .issue-text{flex:1;font-size:12.5px;color:var(--text-secondary)}
  .issue-type{font-weight:600;text-transform:capitalize;color:var(--text-primary)}
  .issue-sub{color:var(--text-muted)}
  .issue-entity{font-family:var(--font-mono);font-size:11px;color:var(--amber);margin-left:6px}
  .confidence-bar{width:48px;height:3px;background:var(--bg-elevated);border-radius:2px;overflow:hidden;flex-shrink:0}
  .conf-fill{display:block;height:100%;background:var(--amber);border-radius:2px}
  .conf-num{font-family:var(--font-mono);font-size:10.5px;color:var(--text-muted);width:32px;text-align:right;flex-shrink:0}
  .signals{display:flex;flex-wrap:wrap;gap:6px}
  .signal-tag{padding:4px 10px;background:var(--red-dim);border:1px solid rgba(224,92,92,0.3);color:var(--red);border-radius:4px;font-size:11.5px;font-family:var(--font-mono);text-transform:capitalize}
  .conf-score{font-size:11px;font-weight:500;padding:2px 8px;border-radius:10px;font-family:var(--font-mono)}
  .conf-score.good{color:var(--green);background:var(--green-dim)}
  .conf-score.medium{color:var(--amber);background:var(--amber-glow)}
  .conf-score.bad{color:var(--red);background:var(--red-dim)}
  .failure-list{display:flex;flex-direction:column;gap:6px}
  .failure-row{display:flex;align-items:center;gap:10px;padding:8px 11px;border-radius:var(--radius-sm);font-size:12px}
  .failure-row.sev-critical{background:var(--red-dim);border:1px solid rgba(224,92,92,0.2)}
  .failure-row.sev-high{background:var(--orange-dim);border:1px solid rgba(224,138,60,0.2)}
  .failure-row.sev-medium{background:var(--amber-glow);border:1px solid rgba(212,168,67,0.2)}
  .failure-type{font-family:var(--font-mono);font-size:11px;font-weight:600;color:var(--text-primary)}
  .failure-severity{font-size:10px;text-transform:uppercase;color:var(--text-muted)}
  .failure-detail{color:var(--text-secondary);font-size:12px;flex:1}
  .all-clear{display:flex;align-items:center;gap:8px;color:var(--green);font-size:13px;font-weight:500}
  .draft-status{font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:10px;font-family:var(--font-mono)}
  .draft-status.approved{color:var(--green);background:var(--green-dim)}
  .draft-status.no-draft{color:var(--text-muted);background:var(--bg-elevated)}
  .draft-textarea{width:100%;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);font-size:13px;font-family:var(--font-body);padding:13px;resize:vertical;line-height:1.65;outline:none}
  .draft-textarea:focus{border-color:var(--amber-dim)}
  .no-draft-msg{color:var(--text-muted);font-size:13px;line-height:1.6;padding:14px;background:var(--bg-elevated);border-radius:var(--radius-sm)}
  .action-bar{display:flex;gap:10px;margin-top:4px}
  .btn-action{padding:10px 20px;border:1px solid;border-radius:var(--radius-sm);font-size:13px;font-weight:600;letter-spacing:0.03em;transition:all 0.15s}
  .btn-action.send{background:var(--green);border-color:var(--green);color:#0c0e14}
  .btn-action.send:hover{background:#5dc99a}
  .btn-action.revise{background:var(--amber-glow);border-color:rgba(212,168,67,0.4);color:var(--amber)}
  .btn-action.revise:hover{background:rgba(212,168,67,0.2)}
  .btn-action.escalate{background:none;border-color:var(--border);color:var(--text-secondary)}
  .btn-action.escalate:hover{background:var(--red-dim);border-color:rgba(224,92,92,0.3);color:var(--red)}
  .action-done{padding:12px 16px;border-radius:var(--radius-sm);font-size:13px;font-weight:500}
  .action-done.sent{background:var(--green-dim);color:var(--green);border:1px solid rgba(76,175,130,0.3)}
  .action-done.escalated{background:var(--red-dim);color:var(--red);border:1px solid rgba(224,92,92,0.3)}
  .action-done.revising{background:var(--amber-glow);color:var(--amber);border:1px solid rgba(212,168,67,0.3)}
  .spinner-sm{width:13px;height:13px;border:2px solid var(--border);border-top-color:var(--amber);border-radius:50%;animation:spin 0.7s linear infinite;display:inline-block}
  @keyframes spin{to{transform:rotate(360deg)}}
</style>
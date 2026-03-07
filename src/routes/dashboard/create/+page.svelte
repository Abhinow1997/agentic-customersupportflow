<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  const FASTAPI = 'http://localhost:8000';

  // ── Ticket type ──────────────────────────────────────────────────────────
  let ticketType = 'return'; // 'return' | 'enquiry'

  // ── Step / submit state ──────────────────────────────────────────────────
  let step = 1;
  let submitting = false;
  let submitError = '';
  let submitSuccess = false;
  let createdTicketId = '';

  // ── No Snowflake reason list needed — free text entry ─────────────────────

  // ── Customer lookup ──────────────────────────────────────────────────────
  let lookupEmail    = '';
  let lookupLoading  = false;
  let lookupStatus   = ''; // 'found' | 'not_found' | 'error' | ''
  let custName       = '';
  let custEmail      = '';
  let custTier       = 'Bronze';
  let custSk         = null;
  let channel        = 'email';
  let complaintDesc  = '';

  // ── Item lookup ───────────────────────────────────────────────────────────
  let itemLookupSk      = '';        // what the agent types
  let itemLookupLoading = false;
  let itemLookupStatus  = '';        // 'found' | 'not_found' | 'error' | ''
  let itemDetails       = null;      // full item object from FastAPI
  let returnQty         = 1;

  // ── Package assessment ────────────────────────────────────────────────────
  let packagingCondition = '';       // one of PACKAGING_CONDITIONS ids

  const PACKAGING_CONDITIONS = [
    { id: 'sealed',    label: 'Sealed / Unopened',    desc: 'Original seal intact, never opened',         factor: 0.00, badge: '0%',   color: 'green'  },
    { id: 'intact',    label: 'Intact / Good',         desc: 'Opened but packaging fully undamaged',       factor: 0.10, badge: '+10%', color: 'green'  },
    { id: 'minor',     label: 'Minor Damage',          desc: 'Small dents, scuffs or torn edges',          factor: 0.25, badge: '+25%', color: 'amber'  },
    { id: 'moderate',  label: 'Moderate Damage',       desc: 'Visible damage, partially compromised',      factor: 0.50, badge: '+50%', color: 'orange' },
    { id: 'heavy',     label: 'Heavily Damaged',       desc: 'Significantly damaged, hard to resell',      factor: 0.80, badge: '+80%', color: 'red'    },
    { id: 'destroyed', label: 'Destroyed / Unusable',  desc: 'Packaging completely destroyed, item exposed', factor: 1.00, badge: '+100%', color: 'red'  },
  ];

  // ── Return reason — free text + AI suggestion ──────────────────────────────
  let returnReasonText    = '';       // typed by agent, or accepted from AI
  let aiSuggestLoading    = false;
  let aiSuggestedText     = '';       // AI-proposed text, shown in banner

  // ── Enquiry fields ────────────────────────────────────────────────────────
  let enquirySubject   = '';
  let enquiryCategory  = '';

  const ENQUIRY_CATEGORIES = [
    { id: 'order_status',   label: 'Order Status',       icon: '📦' },
    { id: 'billing',        label: 'Billing & Payments', icon: '💳' },
    { id: 'product_info',   label: 'Product Info',       icon: 'ℹ'  },
    { id: 'delivery',       label: 'Delivery',           icon: '🚚' },
    { id: 'account',        label: 'Account',            icon: '👤' },
    { id: 'promo_discount', label: 'Promo / Discount',   icon: '🏷' },
    { id: 'technical',      label: 'Technical Support',  icon: '🔧' },
    { id: 'other',          label: 'Other',              icon: '💬' },
  ];

  // ── Financials ────────────────────────────────────────────────────────────
  let returnAmt       = '';
  let netLoss         = '';
  let returnAmtEdited = false;  // true once agent manually overrides
  let netLossEdited   = false;  // true once agent manually overrides
  let priority  = 'medium';

  // ── Static option sets ────────────────────────────────────────────────────
  const CHANNELS = [
    { id: 'email',     label: 'Email',     icon: '✉'  },
    { id: 'voicemail', label: 'Voicemail', icon: '🎙' },
    { id: 'chat',      label: 'Live Chat', icon: '💬' },
  ];
  const PRIORITIES = [
    { id: 'low',      label: 'Low'      },
    { id: 'medium',   label: 'Medium'   },
    { id: 'high',     label: 'High'     },
    { id: 'critical', label: 'Critical' },
  ];

  // ── Step labels ───────────────────────────────────────────────────────────
  $: stepLabels = [
    { n: 1, label: 'Customer & Details' },
    { n: 2, label: ticketType === 'return' ? 'Item & Assessment' : 'Enquiry Details' },
    { n: 3, label: ticketType === 'return' ? 'Financials & Submit' : 'Review & Submit' },
  ];

  // ── Derived ───────────────────────────────────────────────────────────────
  $: reasonText = returnReasonText;  // alias used in review + payload
  $: packagingMeta     = PACKAGING_CONDITIONS.find(p => p.id === packagingCondition);
  $: packagingFactor   = packagingMeta?.factor ?? 0;

  // Return amount: auto-fill from item price × qty unless agent has overridden
  $: if (!returnAmtEdited && itemDetails && returnQty) {
    returnAmt = (parseFloat(itemDetails.price) * returnQty).toFixed(2);
  }

  // Net loss: auto-calc from returnAmt × 0.4 × packaging factor unless overridden
  $: if (!netLossEdited && returnAmt && parseFloat(returnAmt) > 0) {
    netLoss = (parseFloat(returnAmt) * 0.4 * (1 + packagingFactor)).toFixed(2);
  }

  // Net loss preview shown on step 2 (uses item price as proxy before returnAmt is entered)
  $: netLossPreview = itemDetails
    ? (parseFloat(itemDetails.price) * returnQty * 0.4 * (1 + packagingFactor)).toFixed(2)
    : null;

  $: step1Valid = lookupStatus !== '' && custName.trim() && complaintDesc.trim();
  $: step2Valid = ticketType === 'return'
    ? (itemLookupStatus === 'found' && returnReasonText.trim() && packagingCondition)
    : (enquirySubject.trim() && enquiryCategory);
  // returnAmt is auto-populated so step 3 is always valid for returns once item exists
  $: step3Valid = ticketType === 'return'
    ? (!!itemDetails && returnAmt !== '')
    : true;

  // ── No onMount data fetch needed for reasons ────────────────────────────────

  // ── Customer lookup ───────────────────────────────────────────────────────
  async function lookupCustomer() {
    if (!lookupEmail.trim()) return;
    lookupLoading = true; lookupStatus = '';
    try {
      const res  = await fetch(`${FASTAPI}/api/customers?email=${encodeURIComponent(lookupEmail.trim())}`);
      const data = await res.json();
      if (data.found) {
        custName = data.customer.name; custEmail = data.customer.email;
        custTier = data.customer.tier; custSk    = data.customer.sk;
        lookupStatus = 'found';
      } else {
        custEmail = lookupEmail.trim(); custTier = 'Bronze'; custSk = null;
        lookupStatus = 'not_found';
      }
    } catch { lookupStatus = 'error'; }
    finally { lookupLoading = false; }
  }
  function clearCustomer() {
    lookupEmail = ''; custName = ''; custEmail = ''; custTier = 'Bronze';
    custSk = null; lookupStatus = '';
  }

  // ── Item lookup ───────────────────────────────────────────────────────────
  async function lookupItem() {
    if (!String(itemLookupSk).trim()) return;
    itemLookupLoading = true; itemLookupStatus = ''; itemDetails = null;
    try {
      const res  = await fetch(`${FASTAPI}/api/items?sk=${encodeURIComponent(String(itemLookupSk).trim())}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.found) {
        itemDetails      = data.item;
        itemLookupStatus = 'found';
      } else {
        itemLookupStatus = 'not_found';
      }
    } catch { itemLookupStatus = 'error'; }
    finally { itemLookupLoading = false; }
  }
  function clearItem() {
    itemLookupSk = ''; itemLookupStatus = ''; itemDetails = null;
    packagingCondition = ''; returnReasonText = ''; aiSuggestedText = '';
  }

  // ── AI Suggest Reason ─────────────────────────────────────────────────────
  async function suggestReason() {
    if (!complaintDesc.trim() && !packagingCondition) return;
    aiSuggestLoading = true; aiSuggestedText = '';
    try {
      const res = await fetch(`${FASTAPI}/api/suggest-reason`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          complaint_desc:      complaintDesc,
          packaging_condition: packagingCondition,
          item_name:           itemDetails?.name ?? '',
          item_category:       itemDetails?.category ?? '',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      aiSuggestedText = data.reason_desc ?? data.reason_text ?? '';
    } catch {
      // Client-side fallback — produce a plain text suggestion
      aiSuggestedText = _clientSideSuggest();
    } finally { aiSuggestLoading = false; }
  }

  function _clientSideSuggest() {
    const d = complaintDesc.toLowerCase();
    const p = packagingCondition;
    if (p === 'destroyed' || p === 'heavy')                       return 'Package was heavily damaged on arrival — item exposed and potentially unusable.';
    if (p === 'moderate')                                         return 'Packaging shows significant damage, compromising product integrity.';
    if (p === 'minor')                                            return 'Minor packaging damage observed; product may have minor cosmetic issues.';
    if (d.includes('not working') || d.includes('stopped'))      return 'Product stopped working after a short period of use.';
    if (d.includes('late') || d.includes('delay'))               return 'Item did not arrive on time; delivery was significantly delayed.';
    if (d.includes('wrong') || d.includes('not what'))           return 'Received the wrong product — does not match what was ordered.';
    if (d.includes('missing') || d.includes('parts'))            return 'Parts or accessories were missing from the package.';
    if (d.includes('defect') || d.includes('broken'))            return 'Product arrived in a defective or broken condition.';
    return 'Customer is unsatisfied with the product and is requesting a return.';
  }

  function acceptAiSuggestion() {
    returnReasonText = aiSuggestedText;
    aiSuggestedText  = '';
  }

  // ── Navigation ────────────────────────────────────────────────────────────
  function nextStep() { if (step < 3) step++; }
  function prevStep() { if (step > 1) step--; }
  function setTicketType(t) {
    ticketType = t; step = 1;
    itemLookupSk = ''; itemLookupStatus = ''; itemDetails = null;
    packagingCondition = ''; returnReasonText = ''; aiSuggestedText = '';
    enquirySubject = ''; enquiryCategory = '';
    returnAmt = ''; netLoss = '';
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    submitting = true; submitError = '';
    const payload = {
      ticketType,
      customer: { name: custName.trim(), email: custEmail.trim() || lookupEmail.trim(), tier: custTier, sk: custSk },
      channel, priority,
      complaintDesc: complaintDesc.trim(),   // original customer complaint notes
      packagingCondition,
      packagingFactor,
      ...(ticketType === 'return' ? {
        item: {
          sk:        itemDetails?.sk,
          rn:        itemDetails?.rn,   // rank — stored as SR_ITEM_SK
          name:      itemDetails?.name,
          category:  itemDetails?.category,
          class:     itemDetails?.cls,
          brand:     itemDetails?.brand,
          price:     itemDetails?.price,
          returnQty,
        },
        // reasonDesc = assessment reason text — stored in SR_RESOLUTION
        reasonDesc: returnReasonText.trim() || complaintDesc.trim(),
        returnAmt:  parseFloat(returnAmt) || 0,
        netLoss:    parseFloat(netLoss)   || 0,
      } : {
        enquirySubject: enquirySubject.trim(),
        enquiryCategory,
        returnAmt: 0, netLoss: 0,
      }),
    };
    try {
      const res  = await fetch(`${FASTAPI}/api/tickets/create`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message ?? `HTTP ${res.status}`);
      submitSuccess   = true;
      createdTicketId = data.ticketId ?? '—';
    } catch (e) { submitError = e.message; }
    finally { submitting = false; }
  }

  function goToQueue()    { goto('/dashboard'); }
  function createAnother() {
    step = 1; submitSuccess = false; createdTicketId = '';
    lookupEmail = ''; lookupStatus = ''; custName = ''; custEmail = '';
    custTier = 'Bronze'; custSk = null; channel = 'email'; complaintDesc = '';
    itemLookupSk = ''; itemLookupStatus = ''; itemDetails = null; returnQty = 1;
    packagingCondition = ''; returnReasonText = ''; aiSuggestedText = '';
    enquirySubject = ''; enquiryCategory = '';
    returnAmt = ''; netLoss = ''; returnAmtEdited = false; netLossEdited = false;
    priority = 'medium'; ticketType = 'return';
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function truncate(str, n) { return str && str.length > n ? str.slice(0, n) + '…' : (str ?? ''); }
</script>

<div class="create-page">
  <header class="topbar">
    <div class="topbar-left">
      <h2>Create Ticket</h2>
      <div class="breadcrumb">New Ticket · Manual Entry · {ticketType === 'return' ? 'Item Return' : 'Customer Enquiry'}</div>
    </div>
    <div class="topbar-right">
      <a href="/dashboard" class="back-link">← Back to Queue</a>
    </div>
  </header>

  <div class="page-body">

    {#if submitSuccess}
      <div class="success-card">
        <div class="success-icon">✓</div>
        <h3>Ticket Created Successfully</h3>
        <div class="success-id">{createdTicketId}</div>
        <p class="success-detail">
          {ticketType === 'return' ? 'Return ticket' : 'Enquiry ticket'} for <strong>{custName}</strong> has been created.
          {#if ticketType === 'return'}<br/>Reason: <strong>{reasonText}</strong>{:else}<br/>Subject: <strong>{enquirySubject}</strong>{/if}
          <br/>Priority: <span class="priority-tag priority-{priority}">{priority}</span>
        </p>
        <div class="success-actions">
          <button class="btn btn-primary" on:click={goToQueue}>View in Queue</button>
          <button class="btn btn-secondary" on:click={createAnother}>Create Another</button>
        </div>
      </div>

    {:else}

      <!-- Ticket type toggle -->
      <div class="type-selector">
        <button class="type-btn" class:active={ticketType === 'return'} on:click={() => setTicketType('return')}>
          <span class="type-icon">↩</span>
          <span class="type-label">Item Return</span>
          <span class="type-desc">Customer returning a purchased item</span>
        </button>
        <button class="type-btn" class:active={ticketType === 'enquiry'} on:click={() => setTicketType('enquiry')}>
          <span class="type-icon">💬</span>
          <span class="type-label">Enquiry</span>
          <span class="type-desc">Question, request or general support</span>
        </button>
      </div>

      <!-- Step bar -->
      <div class="step-bar">
        {#each stepLabels as s}
          <button class="step-pill" class:active={step === s.n} class:done={step > s.n}
            on:click={() => { if (s.n < step) step = s.n; else if (s.n === 2 && step1Valid) step = 2; else if (s.n === 3 && step2Valid) step = 3; }}>
            <span class="step-num">{step > s.n ? '✓' : s.n}</span>
            <span class="step-label">{s.label}</span>
          </button>
        {/each}
      </div>

      <div class="form-container">

        <!-- ═══ STEP 1: Customer ═══ -->
        {#if step === 1}

          <div class="form-section">
            <div class="section-title">Customer Lookup</div>
            <div class="lookup-row">
              <div class="lookup-input-wrap">
                <input type="email" bind:value={lookupEmail}
                  on:keydown={e => e.key === 'Enter' && lookupCustomer()}
                  placeholder="Enter customer email to search…"
                  class:input-found={lookupStatus === 'found'}
                  class:input-warn={lookupStatus === 'not_found'}
                  disabled={lookupLoading} />
              </div>
              <button class="btn btn-lookup" on:click={lookupCustomer} disabled={!lookupEmail.trim() || lookupLoading}>
                {#if lookupLoading}<span class="spinner-sm"></span> Looking up…{:else}🔍 Look Up{/if}
              </button>
              {#if lookupStatus}<button class="btn btn-ghost btn-sm" on:click={clearCustomer}>✕</button>{/if}
            </div>

            {#if lookupStatus === 'found'}
              <div class="lookup-banner lookup-found">
                <span class="banner-icon">✓</span>
                <div class="banner-body"><strong>Customer found</strong><span class="banner-sub">{custName} · {custEmail}</span></div>
                <span class="tier-badge tier-{custTier.toLowerCase()}">{custTier}</span>
              </div>
            {:else if lookupStatus === 'not_found'}
              <div class="lookup-banner lookup-new">
                <span class="banner-icon">＋</span>
                <div class="banner-body"><strong>No existing customer found</strong><span class="banner-sub">Enter the customer's name below to continue</span></div>
              </div>
            {:else if lookupStatus === 'error'}
              <div class="lookup-banner lookup-error">
                <span class="banner-icon">⚠</span>
                <div class="banner-body"><strong>Lookup failed</strong><span class="banner-sub">Enter details manually below</span></div>
              </div>
            {/if}

            {#if lookupStatus !== ''}
              <div class="field mt-12">
                <label>Customer Name <span class="req">*</span>
                  {#if lookupStatus === 'found'}<span class="field-note">auto-filled from records</span>{/if}
                </label>
                <input type="text" bind:value={custName} placeholder="Full name"
                  readonly={lookupStatus === 'found'} class:readonly-field={lookupStatus === 'found'} />
              </div>
            {/if}
          </div>

          {#if lookupStatus !== ''}
            <div class="form-section">
              <div class="section-title">Contact Channel</div>
              <div class="chip-group">
                {#each CHANNELS as ch}
                  <button class="chip" class:selected={channel === ch.id} on:click={() => channel = ch.id}>
                    <span class="chip-icon">{ch.icon}</span>{ch.label}
                  </button>
                {/each}
              </div>
            </div>

            <div class="form-section">
              <div class="section-title">
                {ticketType === 'return' ? 'Complaint Description' : 'Customer Message / Notes'}
                <span class="req">*</span>
              </div>
              <textarea bind:value={complaintDesc} rows="5"
                placeholder={ticketType === 'return'
                  ? "Describe the customer's complaint in detail. E.g.: 'Customer received a damaged laptop — screen cracked on arrival. Wants replacement or full refund…'"
                  : "Summarise the customer's enquiry. E.g.: 'Customer asking about estimated delivery date for order #X placed 3 days ago…'"}
              ></textarea>
            </div>
          {/if}

          <div class="step-actions">
            <div></div>
            <button class="btn btn-primary" disabled={!step1Valid} on:click={nextStep}>
              {ticketType === 'return' ? 'Next: Item & Assessment →' : 'Next: Enquiry Details →'}
            </button>
          </div>


        <!-- ═══ STEP 2A: Item & Assessment (Return) ═══ -->
        {:else if step === 2 && ticketType === 'return'}

          <!-- Item Lookup -->
          <div class="form-section">
            <div class="section-title">Item Lookup <span class="section-sub">by Item SK</span></div>
            <div class="lookup-row">
              <div class="lookup-input-wrap">
                <input type="number" bind:value={itemLookupSk}
                  on:keydown={e => e.key === 'Enter' && lookupItem()}
                  placeholder="Enter Item SK (e.g. 813, 816, 819…)"
                  class:input-found={itemLookupStatus === 'found'}
                  class:input-warn={itemLookupStatus === 'not_found'}
                  disabled={itemLookupLoading} />
              </div>
              <button class="btn btn-lookup" on:click={lookupItem} disabled={!itemLookupSk || itemLookupLoading || itemLookupSk <= 0}>
                {#if itemLookupLoading}<span class="spinner-sm"></span> Looking up…{:else}🔍 Look Up{/if}
              </button>
              {#if itemLookupStatus}<button class="btn btn-ghost btn-sm" on:click={clearItem}>✕</button>{/if}
            </div>

            {#if itemLookupStatus === 'not_found'}
              <div class="lookup-banner lookup-new">
                <span class="banner-icon">⚠</span>
                <div class="banner-body"><strong>Item not found</strong><span class="banner-sub">Check the Item SK and try again</span></div>
              </div>
            {:else if itemLookupStatus === 'error'}
              <div class="lookup-banner lookup-error">
                <span class="banner-icon">⚠</span>
                <div class="banner-body"><strong>Lookup failed</strong><span class="banner-sub">API unavailable — check FastAPI is running</span></div>
              </div>
            {/if}

            <!-- Item details card — auto-filled -->
            {#if itemDetails}
              <div class="item-card">
                <div class="item-card-header">
                  <div class="item-card-title">{itemDetails.name}</div>
                  <span class="item-sk-badge">SK {itemDetails.sk}</span>
                </div>
                <div class="item-meta-grid">
                  <div class="item-meta-cell">
                    <span class="meta-label">Brand</span>
                    <span class="meta-val">{itemDetails.brand || '—'}</span>
                  </div>
                  <div class="item-meta-cell">
                    <span class="meta-label">Category</span>
                    <span class="meta-val">{itemDetails.category_full || itemDetails.category}</span>
                  </div>
                  <div class="item-meta-cell">
                    <span class="meta-label">Class</span>
                    <span class="meta-val">{itemDetails.cls || '—'}</span>
                  </div>
                  <div class="item-meta-cell">
                    <span class="meta-label">Item No.</span>
                    <span class="meta-val mono">{itemDetails.item_number || '—'}</span>
                  </div>
                  <div class="item-meta-cell">
                    <span class="meta-label">Unit Price</span>
                    <span class="meta-val price">${parseFloat(itemDetails.price).toFixed(2)}</span>
                  </div>
                  <div class="item-meta-cell">
                    <span class="meta-label">List Price</span>
                    <span class="meta-val">${parseFloat(itemDetails.list_price).toFixed(2)}</span>
                  </div>
                  {#if itemDetails.package_size}
                  <div class="item-meta-cell">
                    <span class="meta-label">Package Size</span>
                    <span class="meta-val">{itemDetails.package_size}</span>
                  </div>
                  {/if}
                </div>
                {#if itemDetails.desc}
                  <div class="item-desc">{truncate(itemDetails.desc, 220)}</div>
                {/if}
                <!-- Quantity -->
                <div class="qty-row">
                  <label class="qty-label">Return Quantity</label>
                  <div class="qty-controls">
                    <button class="qty-btn" on:click={() => returnQty = Math.max(1, returnQty - 1)}>−</button>
                    <span class="qty-val">{returnQty}</span>
                    <button class="qty-btn" on:click={() => returnQty = Math.min(99, returnQty + 1)}>＋</button>
                  </div>
                  <span class="qty-total">Total value: <strong>${(parseFloat(itemDetails.price) * returnQty).toFixed(2)}</strong></span>
                </div>
              </div>
            {/if}
          </div>

          <!-- Package Assessment -->
          <div class="form-section" class:section-locked={!itemDetails}>
            <div class="section-title">
              Package Condition Assessment <span class="req">*</span>
              {#if !itemDetails}<span class="lock-hint">— look up an item first</span>{/if}
            </div>

            <div class="packaging-grid">
              {#each PACKAGING_CONDITIONS as cond}
                <button
                  class="pkg-card pkg-{cond.color}"
                  class:selected={packagingCondition === cond.id}
                  disabled={!itemDetails}
                  on:click={() => packagingCondition = cond.id}
                >
                  <div class="pkg-card-top">
                    <span class="pkg-label">{cond.label}</span>
                    <span class="pkg-badge pkg-badge-{cond.color}">{cond.badge}</span>
                  </div>
                  <span class="pkg-desc">{cond.desc}</span>
                </button>
              {/each}
            </div>

            <!-- Net loss preview -->
            {#if packagingCondition && itemDetails}
              <div class="net-loss-preview">
                <span class="nlp-label">Estimated Net Loss Formula</span>
                <div class="nlp-formula">
                  <span class="nlp-part">Return Amt</span>
                  <span class="nlp-op">×</span>
                  <span class="nlp-part">0.4 (base rate)</span>
                  <span class="nlp-op">×</span>
                  <span class="nlp-part pkg-mult">(1 + {packagingFactor}) = {(1 + packagingFactor).toFixed(2)}×</span>
                  <span class="nlp-op">=</span>
                  <span class="nlp-result">${netLossPreview} <span class="nlp-note">at list price</span></span>
                </div>
              </div>
            {/if}
          </div>

          <!-- Return Reason + AI Suggest -->
          <div class="form-section" class:section-locked={!packagingCondition}>
            <div class="section-title-row">
              <div class="section-title">
                Return / Complaint Reason <span class="req">*</span>
                {#if !packagingCondition}<span class="lock-hint">— assess packaging first</span>{/if}
              </div>
              {#if packagingCondition && complaintDesc.trim()}
                <button class="btn-ai-suggest" on:click={suggestReason} disabled={aiSuggestLoading}>
                  {#if aiSuggestLoading}
                    <span class="spinner-sm"></span> Analysing…
                  {:else}
                    ✦ AI Suggest Reason
                  {/if}
                </button>
              {/if}
            </div>

            <!-- AI suggestion banner -->
            {#if aiSuggestedText}
              <div class="ai-suggestion">
                <div class="ai-suggestion-left">
                  <span class="ai-badge">✦ AI</span>
                  <div class="ai-suggestion-text">
                    <strong>Suggested reason based on complaint & packaging:</strong>
                    <span>{aiSuggestedText}</span>
                  </div>
                </div>
                <div class="ai-suggestion-actions">
                  <button class="btn-accept" on:click={acceptAiSuggestion}>Accept</button>
                  <button class="btn-dismiss" on:click={() => aiSuggestedText = ''}>✕</button>
                </div>
              </div>
            {/if}

            <!-- Manual reason entry -->
            <textarea
              bind:value={returnReasonText}
              rows="3"
              placeholder="Describe the return reason in your own words. E.g.: 'Product arrived with a cracked screen — packaging was heavily damaged in transit. Customer wants a full replacement…'"
              disabled={!packagingCondition}
            ></textarea>
            {#if returnReasonText.trim()}
              <div class="reason-char-count">{returnReasonText.length} characters</div>
            {/if}
          </div>

          <div class="step-actions">
            <button class="btn btn-ghost" on:click={prevStep}>← Back</button>
            <button class="btn btn-primary" disabled={!step2Valid} on:click={nextStep}>Next: Financials →</button>
          </div>


        <!-- ═══ STEP 2B: Enquiry Details ═══ -->
        {:else if step === 2 && ticketType === 'enquiry'}

          <div class="form-section">
            <div class="section-title">Enquiry Subject <span class="req">*</span></div>
            <input type="text" bind:value={enquirySubject} placeholder="e.g. Where is my order? / Can I change my delivery address?" />
          </div>

          <div class="form-section">
            <div class="section-title">Enquiry Category <span class="req">*</span></div>
            <div class="enquiry-cat-grid">
              {#each ENQUIRY_CATEGORIES as cat}
                <button class="enquiry-cat-card" class:selected={enquiryCategory === cat.id} on:click={() => enquiryCategory = cat.id}>
                  <span class="cat-icon">{cat.icon}</span>
                  <span class="cat-label">{cat.label}</span>
                </button>
              {/each}
            </div>
          </div>

          <div class="step-actions">
            <button class="btn btn-ghost" on:click={prevStep}>← Back</button>
            <button class="btn btn-primary" disabled={!step2Valid} on:click={nextStep}>Next: Review & Submit →</button>
          </div>


        <!-- ═══ STEP 3A: Financials (Return) ═══ -->
        {:else if step === 3 && ticketType === 'return'}

          <div class="form-section">
            <div class="section-title">Financial Details</div>
            <div class="field-row">
              <div class="field">
                <label>
                  Return Amount ($)
                  {#if !returnAmtEdited}
                    <span class="field-note">auto from item price × qty</span>
                  {:else}
                    <button class="btn-reset" on:click={() => { returnAmtEdited = false; netLossEdited = false; }}>↺ reset</button>
                  {/if}
                </label>
                <input
                  type="number" step="0.01" min="0"
                  bind:value={returnAmt}
                  on:input={() => returnAmtEdited = true}
                />
              </div>
              <div class="field">
                <label>
                  Net Loss ($)
                  {#if !netLossEdited}
                    <span class="field-note">auto — {packagingMeta?.badge ?? '0%'} packaging</span>
                  {:else}
                    <button class="btn-reset" on:click={() => netLossEdited = false}>↺ reset</button>
                  {/if}
                </label>
                <input
                  type="number" step="0.01" min="0"
                  bind:value={netLoss}
                  on:input={() => netLossEdited = true}
                />
              </div>
            </div>
            <!-- Live formula bar -->
            <div class="formula-bar">
              <span class="fb-label">Formula:</span>
              <span class="fb-eq">
                ${parseFloat(itemDetails?.price ?? 0).toFixed(2)} × {returnQty}
                <span class="fb-op">=</span> ${returnAmt}
                <span class="fb-op">× 0.4 ×</span>
                {(1 + packagingFactor).toFixed(2)}
                <span class="fb-op">=</span>
                <strong>${netLoss || '—'}</strong>
              </span>
              <span class="fb-cond">{packagingMeta?.label ?? 'No packaging selected'}</span>
            </div>
            <div class="field mt-12">
              <label>Priority</label>
              <div class="chip-group">
                {#each PRIORITIES as p}
                  <button class="chip priority-chip priority-{p.id}" class:selected={priority === p.id} on:click={() => priority = p.id}>
                    {p.label}
                  </button>
                {/each}
              </div>
            </div>
          </div>

          <!-- Review -->
          <div class="form-section review-section">
            <div class="section-title">Review Summary</div>
            <div class="review-grid">
              <div class="review-item"><span class="review-label">Customer</span><span class="review-val">{custName} <span class="tier-mini tier-{custTier.toLowerCase()}">{custTier}</span></span></div>
              <div class="review-item"><span class="review-label">Channel</span><span class="review-val">{CHANNELS.find(c => c.id === channel)?.icon} {CHANNELS.find(c => c.id === channel)?.label}</span></div>
              <div class="review-item"><span class="review-label">Item</span><span class="review-val">{truncate(itemDetails?.name ?? '', 40)}</span></div>
              <div class="review-item"><span class="review-label">Qty</span><span class="review-val">{returnQty}</span></div>
              <div class="review-item"><span class="review-label">Reason</span><span class="review-val">{returnReasonText}</span></div>
              <div class="review-item"><span class="review-label">Packaging</span><span class="review-val">{packagingMeta?.label ?? '—'}</span></div>
              <div class="review-item"><span class="review-label">Return Amount</span><span class="review-val amt">${parseFloat(returnAmt || 0).toFixed(2)}</span></div>
              <div class="review-item"><span class="review-label">Net Loss</span><span class="review-val loss">${parseFloat(netLoss || 0).toFixed(2)}</span></div>
            </div>
            <div class="review-complaint">
              <span class="review-label">Complaint Notes</span>
              <p>{complaintDesc}</p>
            </div>
          </div>

          {#if submitError}<div class="error-banner">⚠ {submitError}</div>{/if}

          <div class="step-actions">
            <button class="btn btn-ghost" on:click={prevStep}>← Back</button>
            <button class="btn btn-submit" disabled={!step3Valid || submitting} on:click={handleSubmit}>
              {#if submitting}<span class="spinner-sm"></span> Creating…{:else}✦ Create Return Ticket{/if}
            </button>
          </div>


        <!-- ═══ STEP 3B: Review (Enquiry) ═══ -->
        {:else if step === 3 && ticketType === 'enquiry'}

          <div class="form-section">
            <div class="section-title">Priority</div>
            <div class="chip-group">
              {#each PRIORITIES as p}
                <button class="chip priority-chip priority-{p.id}" class:selected={priority === p.id} on:click={() => priority = p.id}>{p.label}</button>
              {/each}
            </div>
          </div>

          <div class="form-section review-section">
            <div class="section-title">Review Summary</div>
            <div class="review-grid">
              <div class="review-item"><span class="review-label">Customer</span><span class="review-val">{custName} <span class="tier-mini tier-{custTier.toLowerCase()}">{custTier}</span></span></div>
              <div class="review-item"><span class="review-label">Channel</span><span class="review-val">{CHANNELS.find(c => c.id === channel)?.icon} {CHANNELS.find(c => c.id === channel)?.label}</span></div>
              <div class="review-item"><span class="review-label">Subject</span><span class="review-val">{enquirySubject}</span></div>
              <div class="review-item"><span class="review-label">Category</span><span class="review-val">{ENQUIRY_CATEGORIES.find(c => c.id === enquiryCategory)?.icon} {ENQUIRY_CATEGORIES.find(c => c.id === enquiryCategory)?.label}</span></div>
            </div>
            <div class="review-complaint">
              <span class="review-label">Customer Notes</span>
              <p>{complaintDesc}</p>
            </div>
          </div>

          {#if submitError}<div class="error-banner">⚠ {submitError}</div>{/if}

          <div class="step-actions">
            <button class="btn btn-ghost" on:click={prevStep}>← Back</button>
            <button class="btn btn-submit enquiry-submit" disabled={submitting} on:click={handleSubmit}>
              {#if submitting}<span class="spinner-sm"></span> Creating…{:else}✦ Create Enquiry Ticket{/if}
            </button>
          </div>
        {/if}

      </div>
    {/if}
  </div>
</div>

<style>
  .create-page { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

  .topbar { display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; border-bottom: 1px solid var(--border); background: var(--bg-surface); flex-shrink: 0; }
  .topbar-left h2 { font-family: var(--font-display); font-size: 20px; font-weight: 400; }
  .breadcrumb { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 4px; }
  .back-link { font-size: 13px; color: var(--text-muted); font-family: var(--font-mono); transition: color 0.15s; }
  .back-link:hover { color: var(--amber); }

  .page-body { flex: 1; overflow-y: auto; padding: 28px 32px; max-width: 900px; margin: 0 auto; width: 100%; }

  /* Type selector */
  .type-selector { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
  .type-btn { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 16px 18px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.15s; text-align: left; }
  .type-btn:hover { border-color: rgba(212,168,67,0.3); }
  .type-btn.active { border-color: rgba(212,168,67,0.5); background: var(--amber-glow); }
  .type-icon { font-size: 18px; }
  .type-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
  .type-btn.active .type-label { color: var(--amber); }
  .type-desc { font-size: 11.5px; color: var(--text-muted); }

  /* Step bar */
  .step-bar { display: flex; gap: 8px; margin-bottom: 20px; }
  .step-pill { display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 24px; color: var(--text-muted); font-size: 12.5px; font-weight: 600; cursor: pointer; transition: all 0.15s; flex: 1; justify-content: center; }
  .step-pill.active { background: var(--amber-glow); border-color: rgba(212,168,67,0.4); color: var(--amber); }
  .step-pill.done  { background: var(--green-dim); border-color: rgba(76,175,130,0.3); color: var(--green); }
  .step-num { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--bg-surface); border: 1px solid var(--border); font-family: var(--font-mono); font-size: 11px; flex-shrink: 0; }
  .step-pill.active .step-num { background: var(--amber); color: #0c0e14; border-color: var(--amber); }
  .step-pill.done  .step-num  { background: var(--green); color: #0c0e14; border-color: var(--green); }
  .step-label { white-space: nowrap; }

  /* Sections */
  .form-container { display: flex; flex-direction: column; gap: 16px; }
  .form-section { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; }
  .form-section.section-locked { opacity: 0.5; pointer-events: none; }
  .section-title { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; font-family: var(--font-mono); margin-bottom: 16px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .section-sub   { font-size: 10px; color: var(--text-muted); font-weight: 400; text-transform: none; letter-spacing: 0; }
  .lock-hint { color: var(--text-muted); font-size: 10px; font-weight: 400; text-transform: none; letter-spacing: 0; }
  .section-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
  .section-title-row .section-title { margin-bottom: 0; }
  .req { color: var(--red); }

  /* Inputs */
  input, select, textarea { width: 100%; padding: 10px 13px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 13.5px; outline: none; transition: border-color 0.15s, box-shadow 0.15s; }
  input:focus, select:focus, textarea:focus { border-color: var(--amber-dim); box-shadow: 0 0 0 3px var(--amber-glow); }
  input::placeholder, textarea::placeholder { color: var(--text-muted); }
  textarea { resize: vertical; font-family: var(--font-body); line-height: 1.6; }
  .input-found { border-color: rgba(76,175,130,0.5) !important; }
  .input-warn  { border-color: rgba(212,168,67,0.4) !important; }
  .readonly-field { opacity: 0.7; cursor: default; }

  /* Fields */
  .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .field { display: flex; flex-direction: column; gap: 6px; }
  .field label { font-size: 12px; color: var(--text-secondary); font-weight: 500; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
  .field-note { font-size: 10px; color: var(--green); font-family: var(--font-mono); font-weight: 400; }
  .mt-12 { margin-top: 12px; }

  /* Lookup */
  .lookup-row { display: flex; gap: 8px; align-items: center; }
  .lookup-input-wrap { flex: 1; }
  .lookup-banner { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid; margin-top: 10px; }
  .lookup-found  { background: var(--green-dim);  border-color: rgba(76,175,130,0.3); }
  .lookup-new    { background: var(--amber-glow); border-color: rgba(212,168,67,0.25); }
  .lookup-error  { background: var(--red-dim);    border-color: rgba(224,92,92,0.3); }
  .banner-icon   { font-size: 16px; flex-shrink: 0; }
  .lookup-found .banner-icon  { color: var(--green); }
  .lookup-new   .banner-icon  { color: var(--amber); }
  .lookup-error .banner-icon  { color: var(--red);   }
  .banner-body   { display: flex; flex-direction: column; gap: 2px; flex: 1; }
  .banner-body strong { font-size: 12.5px; color: var(--text-primary); }
  .banner-sub    { font-size: 11.5px; color: var(--text-muted); font-family: var(--font-mono); }
  .tier-badge    { font-family: var(--font-mono); font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 8px; border-radius: 4px; }
  .tier-badge.tier-platinum { color: #a8d8f0; background: rgba(168,216,240,0.12); border: 1px solid rgba(168,216,240,0.2); }
  .tier-badge.tier-gold     { color: var(--amber); background: var(--amber-glow); border: 1px solid rgba(212,168,67,0.3); }
  .tier-badge.tier-silver   { color: #b0b8c8; background: rgba(176,184,200,0.1);  border: 1px solid rgba(176,184,200,0.2); }
  .tier-badge.tier-bronze   { color: #cd7f32; background: rgba(205,127,50,0.1);   border: 1px solid rgba(205,127,50,0.2); }

  /* Item card */
  .item-card { margin-top: 14px; background: var(--bg-elevated); border: 1px solid rgba(212,168,67,0.2); border-radius: var(--radius-sm); padding: 16px; }
  .item-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .item-card-title  { font-size: 14px; font-weight: 600; color: var(--text-primary); line-height: 1.4; }
  .item-sk-badge    { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); background: var(--bg-surface); border: 1px solid var(--border); padding: 2px 8px; border-radius: 4px; white-space: nowrap; flex-shrink: 0; }
  .item-meta-grid   { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px; }
  .item-meta-cell   { display: flex; flex-direction: column; gap: 2px; }
  .meta-label       { font-size: 9.5px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-mono); }
  .meta-val         { font-size: 13px; color: var(--text-primary); }
  .meta-val.price   { color: var(--amber); font-family: var(--font-mono); font-weight: 600; }
  .meta-val.mono    { font-family: var(--font-mono); }
  .item-desc        { font-size: 12px; color: var(--text-muted); line-height: 1.5; border-top: 1px solid var(--border); padding-top: 10px; margin-bottom: 12px; }
  .qty-row     { display: flex; align-items: center; gap: 14px; padding-top: 10px; border-top: 1px solid var(--border); }
  .qty-label   { font-size: 12px; color: var(--text-secondary); font-weight: 500; }
  .qty-controls { display: flex; align-items: center; gap: 0; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
  .qty-btn     { width: 32px; height: 32px; background: var(--bg-surface); border: none; color: var(--text-secondary); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.1s; }
  .qty-btn:hover { background: var(--amber-glow); color: var(--amber); }
  .qty-val     { min-width: 36px; text-align: center; font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--text-primary); background: var(--bg-elevated); padding: 0 6px; line-height: 32px; }
  .qty-total   { font-size: 12.5px; color: var(--text-muted); margin-left: auto; }
  .qty-total strong { color: var(--amber); }

  /* Packaging grid */
  .packaging-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .pkg-card { text-align: left; padding: 13px 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.15s; display: flex; flex-direction: column; gap: 5px; }
  .pkg-card:hover:not(:disabled) { background: var(--bg-hover); }
  .pkg-card:disabled { cursor: not-allowed; }
  .pkg-card-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
  .pkg-label { font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
  .pkg-desc  { font-size: 11px; color: var(--text-muted); line-height: 1.4; }
  .pkg-badge { font-family: var(--font-mono); font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; white-space: nowrap; }

  .pkg-badge-green  { color: var(--green);  background: var(--green-dim); }
  .pkg-badge-amber  { color: var(--amber);  background: var(--amber-glow); }
  .pkg-badge-orange { color: var(--orange); background: var(--orange-dim); }
  .pkg-badge-red    { color: var(--red);    background: var(--red-dim); }

  .pkg-card.pkg-green.selected  { border-color: rgba(76,175,130,0.5);  background: var(--green-dim); }
  .pkg-card.pkg-amber.selected  { border-color: rgba(212,168,67,0.5);  background: var(--amber-glow); }
  .pkg-card.pkg-orange.selected { border-color: rgba(224,138,60,0.5);  background: var(--orange-dim); }
  .pkg-card.pkg-red.selected    { border-color: rgba(224,92,92,0.5);   background: var(--red-dim); }
  .pkg-card.pkg-green.selected  .pkg-label { color: var(--green); }
  .pkg-card.pkg-amber.selected  .pkg-label { color: var(--amber); }
  .pkg-card.pkg-orange.selected .pkg-label { color: var(--orange); }
  .pkg-card.pkg-red.selected    .pkg-label { color: var(--red); }

  /* Net loss preview */
  .net-loss-preview { margin-top: 14px; padding: 12px 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); display: flex; flex-direction: column; gap: 6px; }
  .nlp-label   { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-mono); }
  .nlp-formula { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .nlp-part    { font-size: 12.5px; color: var(--text-secondary); background: var(--bg-surface); padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border); }
  .nlp-part.pkg-mult { color: var(--amber); border-color: rgba(212,168,67,0.3); background: var(--amber-glow); }
  .nlp-op      { font-size: 13px; color: var(--text-muted); font-family: var(--font-mono); }
  .nlp-result  { font-size: 14px; font-weight: 700; color: var(--red); font-family: var(--font-mono); }
  .nlp-note    { font-size: 10px; color: var(--text-muted); font-weight: 400; margin-left: 4px; }

  /* Reason grid */
  .reason-char-count { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); text-align: right; margin-top: 4px; }

  /* AI suggestion banner */
  .ai-suggestion { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 14px; background: var(--blue-dim); border: 1px solid rgba(91,140,240,0.3); border-radius: var(--radius-sm); margin-bottom: 12px; flex-wrap: wrap; }
  .ai-suggestion-left { display: flex; align-items: flex-start; gap: 10px; flex: 1; }
  .ai-badge { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--blue); background: rgba(91,140,240,0.15); padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(91,140,240,0.3); white-space: nowrap; }
  .ai-suggestion-text { display: flex; flex-direction: column; gap: 3px; }
  .ai-suggestion-text strong { font-size: 11.5px; color: var(--text-primary); }
  .ai-suggestion-text span   { font-size: 13px; color: var(--blue); font-weight: 500; }
  .ai-suggestion-actions { display: flex; gap: 6px; align-items: center; }
  .btn-accept  { padding: 6px 14px; background: var(--blue); border: none; border-radius: var(--radius-sm); color: #0c0e14; font-size: 12px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
  .btn-accept:hover { opacity: 0.85; }
  .btn-dismiss { padding: 6px 10px; background: none; border: 1px solid rgba(91,140,240,0.3); border-radius: var(--radius-sm); color: var(--text-muted); font-size: 12px; cursor: pointer; }

  /* AI suggest button */
  .btn-ai-suggest { display: flex; align-items: center; gap: 6px; padding: 7px 14px; background: var(--blue-dim); border: 1px solid rgba(91,140,240,0.35); border-radius: var(--radius-sm); color: var(--blue); font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s; white-space: nowrap; }
  .btn-ai-suggest:hover:not(:disabled) { background: rgba(91,140,240,0.2); }
  .btn-ai-suggest:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Enquiry categories */
  .enquiry-cat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .enquiry-cat-card { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.15s; }
  .enquiry-cat-card:hover { border-color: rgba(212,168,67,0.3); }
  .enquiry-cat-card.selected { border-color: rgba(212,168,67,0.5); background: var(--amber-glow); }
  .cat-icon  { font-size: 20px; }
  .cat-label { font-size: 11.5px; font-weight: 600; color: var(--text-secondary); text-align: center; }
  .enquiry-cat-card.selected .cat-label { color: var(--amber); }

  /* Chips */
  .chip-group { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { padding: 7px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-muted); transition: all 0.15s; cursor: pointer; display: flex; align-items: center; gap: 5px; }
  .chip:hover { border-color: rgba(212,168,67,0.3); color: var(--text-secondary); }
  .chip.selected { border-color: rgba(212,168,67,0.5); color: var(--amber); background: var(--amber-glow); }
  .chip-icon { font-size: 13px; }
  .priority-chip.priority-low.selected      { color: var(--blue);   background: var(--blue-dim);   border-color: rgba(91,140,240,0.4); }
  .priority-chip.priority-medium.selected   { color: var(--amber);  background: var(--amber-glow); border-color: rgba(212,168,67,0.4); }
  .priority-chip.priority-high.selected     { color: var(--orange); background: var(--orange-dim); border-color: rgba(224,138,60,0.4); }
  .priority-chip.priority-critical.selected { color: var(--red);    background: var(--red-dim);    border-color: rgba(224,92,92,0.4); }

  /* Financials formula bar */
  .formula-bar { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); margin-top: 10px; flex-wrap: wrap; }
  .fb-label { font-size: 10px; color: var(--text-muted); font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.06em; }
  .fb-eq    { font-size: 12.5px; color: var(--text-secondary); font-family: var(--font-mono); display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
  .fb-eq strong { color: var(--red); }
  .fb-op    { color: var(--text-muted); }
  .fb-cond  { font-size: 11px; color: var(--text-muted); background: var(--bg-surface); padding: 2px 8px; border-radius: 3px; border: 1px solid var(--border); margin-left: auto; }
  .btn-reset { background: none; border: none; color: var(--amber); font-size: 10px; font-family: var(--font-mono); font-weight: 600; cursor: pointer; padding: 0 4px; letter-spacing: 0.04em; transition: opacity 0.15s; }
  .btn-reset:hover { opacity: 0.7; }

  /* Review */
  .review-section { border-color: rgba(212,168,67,0.2); }
  .review-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  .review-item { display: flex; flex-direction: column; gap: 3px; }
  .review-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-mono); }
  .review-val   { font-size: 13.5px; color: var(--text-primary); font-weight: 500; }
  .review-val.amt  { color: var(--amber); font-family: var(--font-mono); font-weight: 600; }
  .review-val.loss { color: var(--red);   font-family: var(--font-mono); font-weight: 600; }
  .tier-mini { font-family: var(--font-mono); font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 1px 6px; border-radius: 3px; margin-left: 6px; }
  .tier-mini.tier-gold   { color: var(--amber); background: var(--amber-glow); }
  .tier-mini.tier-silver { color: #b0b8c8; background: rgba(176,184,200,0.1); }
  .tier-mini.tier-bronze { color: #cd7f32; background: rgba(205,127,50,0.1); }
  .review-complaint p { font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin-top: 6px; background: var(--bg-elevated); padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border); }

  /* Step actions */
  .step-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }

  /* Buttons */
  .btn { padding: 11px 22px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; letter-spacing: 0.03em; transition: all 0.15s; border: 1px solid; cursor: pointer; display: flex; align-items: center; gap: 8px; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary  { background: var(--amber-glow); border-color: rgba(212,168,67,0.4); color: var(--amber); }
  .btn-primary:hover:not(:disabled) { background: rgba(212,168,67,0.2); }
  .btn-ghost    { background: none; border-color: var(--border); color: var(--text-muted); }
  .btn-ghost:hover { border-color: rgba(212,168,67,0.3); color: var(--text-secondary); }
  .btn-sm       { padding: 8px 12px; font-size: 12px; }
  .btn-lookup   { white-space: nowrap; padding: 10px 16px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px; }
  .btn-lookup:hover:not(:disabled) { border-color: rgba(212,168,67,0.4); color: var(--amber); }
  .btn-lookup:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-submit   { background: var(--amber); border-color: var(--amber); color: #0c0e14; font-size: 14px; }
  .btn-submit:hover:not(:disabled) { background: #e0b84d; }
  .btn-submit.enquiry-submit { background: var(--blue); border-color: var(--blue); }
  .btn-secondary { background: var(--bg-elevated); border-color: var(--border); color: var(--text-secondary); }
  .btn-secondary:hover { border-color: rgba(212,168,67,0.3); }

  /* Error */
  .error-banner { padding: 10px 14px; background: var(--red-dim); border: 1px solid rgba(224,92,92,0.3); border-radius: var(--radius-sm); color: var(--red); font-size: 12px; }

  /* Priority tags */
  .priority-tag { font-family: var(--font-mono); font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 8px; border-radius: 10px; }
  .priority-low      { background: var(--blue-dim);   color: var(--blue); }
  .priority-medium   { background: var(--amber-glow); color: var(--amber); }
  .priority-high     { background: var(--orange-dim); color: var(--orange); }
  .priority-critical { background: var(--red-dim);    color: var(--red); }

  /* Success */
  .success-card { text-align: center; padding: 60px 40px; background: var(--bg-surface); border: 1px solid rgba(76,175,130,0.3); border-radius: var(--radius-md); }
  .success-icon { font-size: 48px; color: var(--green); margin-bottom: 16px; }
  .success-card h3 { font-family: var(--font-display); font-size: 24px; font-weight: 400; margin-bottom: 10px; }
  .success-id   { font-family: var(--font-mono); font-size: 18px; color: var(--amber); font-weight: 600; margin-bottom: 16px; }
  .success-detail { font-size: 14px; color: var(--text-secondary); line-height: 1.7; margin-bottom: 28px; }
  .success-actions { display: flex; gap: 10px; justify-content: center; }

  /* Spinner */
  .spinner-sm { width: 13px; height: 13px; border: 2px solid rgba(0,0,0,0.2); border-top-color: currentColor; border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>

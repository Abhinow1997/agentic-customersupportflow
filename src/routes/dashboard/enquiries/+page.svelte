<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  const FASTAPI = 'http://localhost:8000';

  // ── Ticket type ──────────────────────────────────────────────────────────
  let ticketType = 'enquiry';

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
  let enquirySubject      = '';
  let enquiryCategory     = '';
  let enquiryInputMode    = 'email';   // 'email' | 'voicemail'
  let enquiryRawMessage   = '';        // full pasted email / text body
  let enquirySenderName   = '';
  let enquirySenderEmail  = '';
  let enquirySenderType   = 'customer'; // 'customer' | 'seller' | 'other'

  // ── Voicemail recording state ────────────────────────────────────────────
  let vmRecording        = false;   // currently recording
  let vmMediaRecorder    = null;    // MediaRecorder instance
  let vmAudioChunks      = [];      // collected Blob chunks
  let vmAudioBlob        = null;    // final recorded Blob
  let vmAudioUrl         = '';      // object URL for playback preview
  let vmDuration         = 0;       // elapsed seconds while recording
  let vmDurationTimer    = null;    // setInterval handle
  let vmTranscribing     = false;   // waiting for Whisper response
  let vmTranscriptError  = '';
  let vmS3Url            = '';      // S3 URL returned after upload
  let vmS3Key            = '';

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      vmAudioChunks = [];
      vmAudioBlob   = null;
      vmAudioUrl    = '';
      vmDuration    = 0;
      vmTranscriptError = '';
      vmS3Url = ''; vmS3Key = '';

      vmMediaRecorder = new MediaRecorder(stream);
      vmMediaRecorder.ondataavailable = e => { if (e.data.size > 0) vmAudioChunks.push(e.data); };
      vmMediaRecorder.onstop = () => {
        vmAudioBlob = new Blob(vmAudioChunks, { type: 'audio/webm' });
        vmAudioUrl  = URL.createObjectURL(vmAudioBlob);
        // Stop all tracks so mic indicator goes away
        stream.getTracks().forEach(t => t.stop());
      };
      vmMediaRecorder.start();
      vmRecording = true;
      vmDurationTimer = setInterval(() => vmDuration++, 1000);
    } catch (err) {
      vmTranscriptError = 'Microphone access denied. Please allow mic access and try again.';
    }
  }

  function stopRecording() {
    if (vmMediaRecorder && vmRecording) {
      vmMediaRecorder.stop();
      vmRecording = false;
      clearInterval(vmDurationTimer);
    }
  }

  function discardRecording() {
    stopRecording();
    vmAudioBlob = null;
    vmAudioUrl  = '';
    vmDuration  = 0;
    vmAudioChunks = [];
    vmTranscriptError = '';
    vmS3Url = ''; vmS3Key = '';
  }

  async function transcribeRecording() {
    if (!vmAudioBlob) return;
    vmTranscribing = true;
    vmTranscriptError = '';
    try {
      const fd = new FormData();
      fd.append('audio', vmAudioBlob, 'voicemail.webm');
      fd.append('ticket_ref', 'enquiry-' + Date.now());
      const res  = await fetch(`${FASTAPI}/api/enquiry/transcribe`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      enquiryRawMessage = data.transcript ?? '';
      vmS3Url = data.s3_url ?? '';
      vmS3Key = data.s3_key ?? '';
      if (data.s3_error) console.warn('S3 warning:', data.s3_error);
    } catch (e) {
      vmTranscriptError = e.message;
    } finally {
      vmTranscribing = false;
    }
  }

  $: vmFormatDuration = (s) => `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`;

  const DEMO_SAMPLES = [
    {
      label: 'Order Not Received',
      senderType: 'customer',
      senderName: 'Sarah Thompson',
      senderEmail: 'sarah.t@gmail.com',
      subject: 'My order hasn\'t arrived — tracking stuck for 3 days',
      body: `Hi,

I placed order #WM-8821 six days ago and I still haven't received it. The tracking page hasn't updated in 3 days and just says "In Transit".

Could someone please look into this urgently? I needed this item by the weekend.

Thank you,
Sarah Thompson`,
    },
    {
      label: 'Billing Double Charge',
      senderType: 'customer',
      senderName: 'Jennifer Walsh',
      senderEmail: 'j.walsh@hotmail.com',
      subject: 'Duplicate charge on my account — need immediate refund',
      body: `Hello,

I was charged $149.99 twice for my subscription renewal on March 10th. I only authorised one payment. My bank statement clearly shows two identical transactions.

Please refund the duplicate charge as soon as possible.

Regards,
Jennifer Walsh
Account: jennifer.w@hotmail.com`,
    },
    {
      label: 'Wrong Item Delivered',
      senderType: 'customer',
      senderName: 'Marcus Reid',
      senderEmail: 'marcusreid22@gmail.com',
      subject: 'Received wrong product — Order #WM-9034',
      body: `Hi there,

I ordered a Blue 12-Cup Coffee Maker (Model CM-200) but received a Red 8-Cup version instead. This was meant as a birthday gift and I'm very disappointed.

Order #WM-9034 — placed on March 8th.

I'd like either the correct item sent to me or a full refund. Please advise on next steps.

Thanks,
Marcus`,
    },
    {
      label: 'Seller — Product Delisted',
      senderType: 'seller',
      senderName: 'TechGadget Supplies',
      senderEmail: 'ops@techgadgetsupplies.com',
      subject: 'Product listings removed without notice — urgent reinstatement needed',
      body: `Dear Support Team,

This is the operations team at TechGadget Supplies. Three of our active product listings have been removed without any notification or explanation.

Affected Product IDs: TG-441, TG-445, TG-502

These listings were compliant with all marketplace guidelines. We are losing significant daily revenue and need this escalated urgently.

Please advise on why they were removed and provide a timeline for reinstatement.

Best regards,
David Chen
Operations Manager — TechGadget Supplies`,
    },
    {
      label: 'Seller — Payout Delay',
      senderType: 'seller',
      senderName: 'Sunrise Electronics',
      senderEmail: 'accounts@sunriseelectronics.co',
      subject: 'February seller payout still not received — $3,420 outstanding',
      body: `Dear Accounts Team,

My seller payout for February has not been processed. The expected settlement date was February 28th and it is now March 13th — two weeks overdue.

Outstanding amount: $3,420.00
Seller Account ID: SE-00482

I have raised this through the portal twice with no response. Please treat this as urgent.

Regards,
David Chen
Sunrise Electronics`,
    },
    {
      label: 'Promo Code Not Applied',
      senderType: 'customer',
      senderName: 'Priya Nair',
      senderEmail: 'priya.nair@outlook.com',
      subject: 'Promo code SAVE20 not applied to my order',
      body: `Hi,

I used promo code SAVE20 at checkout on March 11th but my final order total wasn't reduced. I was charged the full price of $89.99 instead of the expected $71.99.

Order confirmation number: #WM-9187

Can you please apply the discount retroactively or issue a partial refund of $18.00?

Thank you,
Priya`,
    },
  ];

  function applySample(s) {
    enquirySenderName  = s.senderName;
    enquirySenderEmail = s.senderEmail;
    enquirySenderType  = s.senderType;
    enquirySubject     = s.subject;
    enquiryRawMessage  = s.body;
  }

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
  $: stepLabels = [{ n: 1, label: 'Enquiry Details' }];

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

  $: step1Valid = enquiryRawMessage.trim();
  $: step2Valid = true;
  $: step3Valid = true;

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
          // complaint
          complaint_desc:       complaintDesc,
          // packaging
          packaging_condition:  packagingCondition,
          packaging_factor:     packagingFactor,
          // full item details
          item_name:            itemDetails?.name          ?? '',
          item_brand:           itemDetails?.brand         ?? '',
          item_category:        itemDetails?.category      ?? '',
          item_category_full:   itemDetails?.category_full ?? '',
          item_class:           itemDetails?.cls           ?? '',
          item_price:           itemDetails?.price         ?? '',
          item_list_price:      itemDetails?.list_price    ?? '',
          item_desc:            itemDetails?.desc          ?? '',
          item_package_size:    itemDetails?.package_size  ?? '',
          // return financials
          return_qty:           returnQty,
          return_amt:           returnAmt,
          net_loss:             netLoss,
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
    enquirySubject = ''; enquiryCategory = ''; enquiryInputMode = 'email';
    enquiryRawMessage = ''; enquirySenderName = ''; enquirySenderEmail = ''; enquirySenderType = 'customer';
    returnAmt = ''; netLoss = '';
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    submitting = true; submitError = '';
    const payload = {
      ticketType: 'enquiry',
      customer: { name: custName.trim(), email: custEmail.trim() || lookupEmail.trim(), tier: custTier, sk: custSk },
      channel, priority,
      complaintDesc: complaintDesc.trim(),   // original customer complaint notes
      packagingCondition,
      packagingFactor,
      enquiryCategory,
      enquiryInputMode,
      enquiryRawMessage:  enquiryRawMessage.trim(),
      enquirySenderName:  enquirySenderName.trim(),
      enquirySenderType,
      returnAmt: 0, netLoss: 0,
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
    enquirySubject = ''; enquiryCategory = ''; enquiryInputMode = 'email';
    enquiryRawMessage = ''; enquirySenderName = ''; enquirySenderEmail = ''; enquirySenderType = 'customer';
    returnAmt = ''; netLoss = ''; returnAmtEdited = false; netLossEdited = false;
    priority = 'medium'; ticketType = 'enquiry';
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function truncate(str, n) { return str && str.length > n ? str.slice(0, n) + '…' : (str ?? ''); }
</script>

<div class="create-page">
  <header class="topbar">
    <div class="topbar-left">
      <h2>Create Ticket</h2>
      <div class="breadcrumb">New Ticket · Manual Entry · Customer Enquiry</div>
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
          Enquiry ticket for <strong>{custName}</strong> has been created.
          <br/>Subject: <strong>{enquirySubject}</strong>
          <br/>Priority: <span class="priority-tag priority-{priority}">{priority}</span>
        </p>
        <div class="success-actions">
          <button class="btn btn-primary" on:click={goToQueue}>View in Queue</button>
          <button class="btn btn-secondary" on:click={createAnother}>Create Another</button>
        </div>
      </div>

    {:else}

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

        <!-- ═══ STEP 1 ═══ -->
        {#if step === 1}

          {#if ticketType === 'enquiry'}
            <!-- ═══ ENQUIRY: single-step form + direct submit ═══ -->

            <!-- Input mode selector -->
            <div class="form-section">
              <div class="section-title">Input Mode</div>
              <div class="input-mode-tabs">
                <button class="mode-tab" class:active={enquiryInputMode === 'email'} on:click={() => enquiryInputMode = 'email'}>
                  <span class="mode-tab-icon">✉</span>
                  <div class="mode-tab-body">
                    <span class="mode-tab-label">Email / Text Message</span>
                    <span class="mode-tab-desc">Paste or type the customer’s email, live chat or any written message</span>
                  </div>
                </button>
                <button class="mode-tab" class:active={enquiryInputMode === 'voicemail'} on:click={() => enquiryInputMode = 'voicemail'}>
                  <span class="mode-tab-icon">🎙</span>
                  <div class="mode-tab-body">
                    <span class="mode-tab-label">Voicemail</span>
                    <span class="mode-tab-desc">Record a voicemail, upload to S3, and auto-transcribe with Whisper</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Demo samples -->
            <div class="form-section">
              <div class="section-title">Load a Demo Sample <span class="section-sub">— click any to populate the form</span></div>
              <div class="sample-grid">
                {#each DEMO_SAMPLES as s}
                  <button class="sample-card" class:seller={s.senderType === 'seller'} on:click={() => applySample(s)}>
                    <div class="sample-card-top">
                      <span class="sample-type-badge sample-type-{s.senderType}">{s.senderType}</span>
                      <span class="sample-label">{s.label}</span>
                    </div>
                    <span class="sample-from">{s.senderName}</span>
                  </button>
                {/each}
              </div>
            </div>

            {#if enquiryInputMode === 'email'}
              <div class="form-section">
                <div class="section-title-row">
                  <div class="section-title">Message Body <span class="field-note">paste or type the customer message</span></div>
                  {#if enquiryRawMessage}
                    <span class="char-count-badge">{enquiryRawMessage.length} chars</span>
                  {/if}
                </div>
                <textarea
                  bind:value={enquiryRawMessage}
                  rows="8"
                  class="message-body-area"
                  placeholder="Paste the email, chat transcript, or customer message here..."
                ></textarea>
              </div>
            {/if}

            {#if enquiryInputMode === 'voicemail'}
              <!-- ─── VOICEMAIL RECORDER ─── -->
              <div class="form-section vm-section">
                <div class="section-title">Voicemail Recorder</div>

                <!-- Idle: show record button -->
                {#if !vmRecording && !vmAudioBlob}
                  <div class="vm-idle">
                    <button class="vm-record-btn" on:click={startRecording}>
                      <span class="vm-mic-icon">🎙</span>
                      <span>Start Recording</span>
                    </button>
                    <p class="vm-hint">Click to start recording. The audio will be saved to S3 and transcribed via OpenAI Whisper.</p>
                  </div>
                {/if}

                <!-- Recording in progress -->
                {#if vmRecording}
                  <div class="vm-recording">
                    <div class="vm-pulse-ring">
                      <div class="vm-pulse-dot"></div>
                    </div>
                    <div class="vm-recording-info">
                      <span class="vm-rec-label">REC</span>
                      <span class="vm-timer">{vmFormatDuration(vmDuration)}</span>
                    </div>
                    <button class="vm-stop-btn" on:click={stopRecording}>⏹ Stop Recording</button>
                  </div>
                {/if}

                <!-- Recording done — preview + actions -->
                {#if vmAudioBlob && !vmRecording}
                  <div class="vm-preview">
                    <div class="vm-preview-header">
                      <span class="vm-preview-label">✔ Recording captured</span>
                      <span class="vm-preview-duration">{vmFormatDuration(vmDuration)}</span>
                    </div>
                    <!-- svelte-ignore a11y-media-has-caption -->
                    <audio src={vmAudioUrl} controls class="vm-audio-player"></audio>
                    <div class="vm-actions">
                      {#if enquiryRawMessage}
                        <div class="vm-transcribed-badge">✦ Transcribed</div>
                      {:else}
                        <button class="btn vm-transcribe-btn" disabled={vmTranscribing} on:click={transcribeRecording}>
                          {#if vmTranscribing}
                            <span class="spinner-sm"></span> Transcribing…
                          {:else}
                            ✦ Transcribe with Whisper
                          {/if}
                        </button>
                      {/if}
                      <button class="btn btn-ghost btn-sm" on:click={discardRecording}>Discard</button>
                    </div>
                    {#if vmS3Key}
                      <div class="vm-s3-badge">
                        <span class="vm-s3-icon">☁</span>
                        <span>Saved to S3 — <code>{vmS3Key}</code></span>
                      </div>
                    {/if}
                    {#if vmTranscriptError}
                      <div class="vm-error">⚠ {vmTranscriptError}</div>
                    {/if}
                  </div>
                {/if}
              </div>

              <!-- Transcript result (editable) -->
              {#if enquiryRawMessage}
                <div class="form-section">
                  <div class="section-title-row">
                    <div class="section-title">Transcript <span class="field-note">auto-generated — review and edit</span></div>
                    <span class="char-count-badge">{enquiryRawMessage.length} chars</span>
                  </div>
                  <textarea bind:value={enquiryRawMessage} rows="8" class="message-body-area"
                    placeholder="Transcript will appear here after Whisper processes the recording..."></textarea>
                </div>
              {/if}
            {/if}

            {#if submitError}<div class="error-banner">⚠ {submitError}</div>{/if}

            <div class="step-actions">
              <div></div>
              <button class="btn btn-submit enquiry-submit" disabled={!step1Valid || submitting} on:click={handleSubmit}>
                {#if submitting}<span class="spinner-sm"></span> Creating…{:else}❖ Create Enquiry Ticket{/if}
              </button>
            </div>

          {:else}
            <!-- ═══ RETURN: customer lookup step ═══ -->
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
                  <div class="banner-body"><strong>No existing customer found</strong><span class="banner-sub">Enter the customer’s name below to continue</span></div>
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
                <div class="section-title">Complaint Description <span class="req">*</span></div>
                <textarea bind:value={complaintDesc} rows="5"
                  placeholder="Describe the customer’s complaint in detail. E.g.: ‘Customer received a damaged laptop — screen cracked on arrival. Wants replacement or full refund…’"
                ></textarea>
              </div>
            {/if}

            <div class="step-actions">
              <div></div>
              <button class="btn btn-primary" disabled={!step1Valid} on:click={nextStep}>Next: Item & Assessment →</button>
            </div>
          {/if}


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

          <!-- Input mode selector -->
          <div class="form-section">
            <div class="section-title">Input Mode</div>
            <div class="input-mode-tabs">
              <button class="mode-tab" class:active={enquiryInputMode === 'email'} on:click={() => enquiryInputMode = 'email'}>
                <span class="mode-tab-icon">✉</span>
                <div class="mode-tab-body">
                  <span class="mode-tab-label">Email / Text Message</span>
                  <span class="mode-tab-desc">Paste or type the customer's email, live chat or any written message</span>
                </div>
              </button>
              <button class="mode-tab" class:active={enquiryInputMode === 'voicemail'} on:click={() => enquiryInputMode = 'voicemail'}>
                <span class="mode-tab-icon">🎙</span>
                <div class="mode-tab-body">
                  <span class="mode-tab-label">Voicemail</span>
                  <span class="mode-tab-desc">Record a voicemail, upload to S3, and auto-transcribe with Whisper</span>
                </div>
              </button>
            </div>
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

  /* Enquiry start notice */
  .enquiry-start-notice { display: flex; align-items: flex-start; gap: 16px; border-color: rgba(91,140,240,0.3); background: var(--blue-dim); }
  .notice-icon { font-size: 24px; flex-shrink: 0; padding-top: 2px; }
  .notice-body { display: flex; flex-direction: column; gap: 5px; }
  .notice-body strong { font-size: 13.5px; color: var(--text-primary); }
  .notice-body span { font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; }

  /* Input mode tabs */
  .input-mode-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .mode-tab { display: flex; align-items: center; gap: 14px; padding: 16px 18px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.15s; text-align: left; }
  .mode-tab:hover:not(:disabled) { border-color: rgba(212,168,67,0.3); }
  .mode-tab.active { border-color: rgba(212,168,67,0.5); background: var(--amber-glow); }
  .mode-tab-disabled { opacity: 0.45; cursor: not-allowed !important; }
  .mode-tab-icon { font-size: 22px; flex-shrink: 0; }
  .mode-tab-body { display: flex; flex-direction: column; gap: 4px; }
  .mode-tab-label { font-size: 13.5px; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
  .mode-tab.active .mode-tab-label { color: var(--amber); }
  .mode-tab-desc { font-size: 11.5px; color: var(--text-muted); line-height: 1.4; }
  .soon-badge { font-family: var(--font-mono); font-size: 9px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 7px; border-radius: 3px; background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-muted); }

  /* Demo samples */
  .sample-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .sample-card { text-align: left; padding: 12px 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.15s; display: flex; flex-direction: column; gap: 6px; }
  .sample-card:hover { border-color: rgba(212,168,67,0.4); background: var(--amber-glow); }
  .sample-card.seller:hover { border-color: rgba(91,140,240,0.4); background: var(--blue-dim); }
  .sample-card-top { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
  .sample-label { font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
  .sample-from  { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); }
  .sample-type-badge { font-family: var(--font-mono); font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 2px 7px; border-radius: 3px; flex-shrink: 0; }
  .sample-type-customer { color: var(--green);  background: var(--green-dim);  border: 1px solid rgba(76,175,130,0.3); }
  .sample-type-seller   { color: var(--blue);   background: var(--blue-dim);   border: 1px solid rgba(91,140,240,0.3); }
  .sample-type-other    { color: var(--text-muted); background: var(--bg-surface); border: 1px solid var(--border); }

  /* Sender type group */
  .sender-row { display: flex; align-items: center; }
  .sender-type-group { display: flex; gap: 6px; flex-wrap: wrap; }
  .sender-type-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 20px; font-size: 12.5px; font-weight: 600; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-muted); cursor: pointer; transition: all 0.15s; }
  .sender-type-btn:hover { border-color: rgba(212,168,67,0.3); color: var(--text-secondary); }
  .sender-type-btn.active { border-color: rgba(212,168,67,0.5); color: var(--amber); background: var(--amber-glow); }

  /* Message body */
  .message-body-area { font-family: var(--font-mono); font-size: 12.5px; line-height: 1.7; resize: vertical; min-height: 200px; }
  .char-count-badge { font-family: var(--font-mono); font-size: 10px; color: var(--text-muted); background: var(--bg-elevated); border: 1px solid var(--border); padding: 2px 8px; border-radius: 3px; }
  .review-msg-body { white-space: pre-wrap; font-family: var(--font-mono); font-size: 12px; max-height: 180px; overflow-y: auto; }
  .review-val.mono { font-family: var(--font-mono); font-size: 12.5px; }

  /* ── Voicemail recorder ─────────────────────────────────────────────── */
  .vm-section { min-height: 140px; }

  /* Idle */
  .vm-idle { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; padding: 28px 0; }
  .vm-record-btn { display: flex; align-items: center; gap: 10px; padding: 14px 28px; background: var(--red-dim); border: 1px solid rgba(224,92,92,0.4); border-radius: var(--radius-md); color: var(--red); font-size: 15px; font-weight: 700; cursor: pointer; transition: all 0.15s; }
  .vm-record-btn:hover { background: rgba(224,92,92,0.2); transform: scale(1.02); }
  .vm-mic-icon { font-size: 20px; }
  .vm-hint { font-size: 12px; color: var(--text-muted); text-align: center; max-width: 420px; line-height: 1.5; }

  /* Recording in progress */
  .vm-recording { display: flex; flex-direction: column; align-items: center; gap: 20px; padding: 28px 0; }
  .vm-pulse-ring { position: relative; width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; }
  .vm-pulse-ring::before, .vm-pulse-ring::after {
    content: ''; position: absolute; border-radius: 50%;
    border: 2px solid var(--red); opacity: 0;
    animation: vm-pulse 1.6s ease-out infinite;
  }
  .vm-pulse-ring::after { animation-delay: 0.8s; }
  .vm-pulse-dot { width: 28px; height: 28px; background: var(--red); border-radius: 50%; position: relative; z-index: 1; box-shadow: 0 0 12px rgba(224,92,92,0.5); }
  @keyframes vm-pulse {
    0%   { width: 28px; height: 28px; top: 18px; left: 18px; opacity: 0.8; }
    100% { width: 64px; height: 64px; top: 0; left: 0; opacity: 0; }
  }
  .vm-recording-info { display: flex; align-items: center; gap: 12px; }
  .vm-rec-label { font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--red); background: var(--red-dim); border: 1px solid rgba(224,92,92,0.3); padding: 2px 8px; border-radius: 3px; letter-spacing: 0.1em; animation: vm-blink 1s step-end infinite; }
  @keyframes vm-blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
  .vm-timer { font-family: var(--font-mono); font-size: 28px; font-weight: 600; color: var(--text-primary); letter-spacing: 0.05em; }
  .vm-stop-btn { display: flex; align-items: center; gap: 8px; padding: 11px 24px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
  .vm-stop-btn:hover { border-color: rgba(224,92,92,0.4); color: var(--red); }

  /* Preview */
  .vm-preview { display: flex; flex-direction: column; gap: 12px; }
  .vm-preview-header { display: flex; align-items: center; justify-content: space-between; }
  .vm-preview-label { font-size: 13px; font-weight: 600; color: var(--green); }
  .vm-preview-duration { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); }
  .vm-audio-player { width: 100%; height: 36px; accent-color: var(--amber); }
  .vm-actions { display: flex; align-items: center; gap: 10px; }
  .vm-transcribe-btn { background: var(--amber-glow); border-color: rgba(212,168,67,0.4); color: var(--amber); font-size: 13px; font-weight: 700; }
  .vm-transcribe-btn:hover:not(:disabled) { background: rgba(212,168,67,0.2); }
  .vm-transcribed-badge { display: flex; align-items: center; gap: 6px; padding: 8px 14px; background: var(--green-dim); border: 1px solid rgba(76,175,130,0.3); border-radius: var(--radius-sm); color: var(--green); font-size: 12.5px; font-weight: 600; }
  .vm-s3-badge { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: 11.5px; color: var(--text-muted); }
  .vm-s3-badge code { font-family: var(--font-mono); font-size: 10.5px; color: var(--text-secondary); word-break: break-all; }
  .vm-s3-icon { font-size: 15px; flex-shrink: 0; }
  .vm-error { padding: 8px 12px; background: var(--red-dim); border: 1px solid rgba(224,92,92,0.3); border-radius: var(--radius-sm); color: var(--red); font-size: 12px; }

  /* Spinner */
  .spinner-sm { width: 13px; height: 13px; border: 2px solid rgba(0,0,0,0.2); border-top-color: currentColor; border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>

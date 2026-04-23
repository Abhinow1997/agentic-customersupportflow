<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  const FASTAPI = 'http://localhost:8000';

  // ── Ticket type ──────────────────────────────────────────────────────────
  let ticketType = 'return';

  // ── Step / submit state ──────────────────────────────────────────────────
  let step = 1;
  let submitting = false;
  let submitError = '';
  let submitSuccess = false;
  let createdTicketId = '';

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

  // ── Recent Orders (Dynamic) ───────────────────────────────────────────────
  let recentOrders = [];
  let filteredOrders = [];
  let ordersLoading = false;
  let ordersError = '';
  let dateFilter = 'all'; // 'all' | '7'

  onMount(() => {
    fetchRecentOrders(false);
  });

  async function fetchRecentOrders(forceRefresh = false) {
    if (!forceRefresh) {
      const cached = sessionStorage.getItem('recentOrdersCache');
      if (cached) {
        try {
          recentOrders = JSON.parse(cached);
          applyDateFilter();
          return;
        } catch (e) {
          console.warn('Failed to parse cached orders');
        }
      }
    }
    
    ordersLoading = true;
    ordersError = '';
    try {
      // NOTE: Replace this endpoint path if yours differs
      const res = await fetch(`${FASTAPI}/api/recent_orders`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      const data = await res.json();
      
      // Handle various response structures gracefully
      recentOrders = data.orders || data.data || data; 
      
      if (Array.isArray(recentOrders)) {
        sessionStorage.setItem('recentOrdersCache', JSON.stringify(recentOrders));
        applyDateFilter();
      } else {
        recentOrders = [];
      }
    } catch (e) {
      ordersError = 'Failed to load recent orders: ' + e.message;
    } finally {
      ordersLoading = false;
    }
  }

  function applyDateFilter() {
    if (dateFilter === 'all') {
      filteredOrders = recentOrders;
      return;
    }
    const days = parseInt(dateFilter);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    
    filteredOrders = recentOrders.filter(o => {
      const dateStr = o.PURCHASE_DATE || o.purchase_date;
      if (!dateStr) return true; // Include if no date exists
      const d = new Date(dateStr);
      return d >= cutoff;
    });
  }

  $: dateFilter, applyDateFilter();

  async function selectRecentOrder(order) {
    // 1. Set context to return ticket
    if (ticketType !== 'return') {
      setTicketType('return');
    }

    // 2. Fetch Customer
    const email = order.C_EMAIL_ADDRESS || order.c_email_address || '';
    if (email) {
      lookupEmail = email;
      await lookupCustomer();
    }

    // 3. Fetch Item (Assumes backend includes ITEM_SK or similar key in the query output)
    const sk = order.ITEM_SK || order.I_ITEM_SK || order.SS_ITEM_SK || order.item_sk || order.i_item_sk || order.ss_item_sk || '';
    if (sk) {
      itemLookupSk = sk;
      await lookupItem();
    }
    
    // Removed auto-navigation to step 2 so the agent can review before proceeding manually
  }

  // ── Package assessment ────────────────────────────────────────────────────
  let packagingCondition = '';       // one of PACKAGING_CONDITIONS ids
  let assessmentLoading  = false;
  let assessmentComplete = false;
  let assessmentError    = '';
  let assessmentResult   = null;
  let followUpMode       = false;
  let followUpQuestions  = [];
  let followUpCollected  = [];
  let activeFollowUpIndex = 0;
  let activeFollowUpAnswer = '';
  let followUpError      = '';
  $: assessmentResultJson = assessmentResult ? JSON.stringify(assessmentResult, null, 2) : '';

  let assessmentLoadingStep = 0;
  let assessmentInterval;
  const ASSESSMENT_STEPS = [
    "Initializing Researcher Agent...",
    "Scanning corporate return policies and constraints...",
    "Cross-referencing item details with customer history...",
    "Analyzing customer remarks against policy logic...",
    "Generating dynamic policy-validation questions...",
    "Finalizing multi-agent assessment..."
  ];

  // ── Decision logging ─────────────────────────────────────────────────────
  let decisionLogging = false;
  let decisionLogged  = false;
  let decisionId      = '';
  let decisionError   = '';

  const PACKAGING_CONDITIONS = [
    { id: 'sealed',    label: 'Sealed / Unopened',    desc: 'Original seal intact, never opened',         factor: 0.05, color: 'green'  },
    { id: 'intact',    label: 'Intact / Good',        desc: 'Opened but packaging fully undamaged',       factor: 0.50, color: 'green'  },
    { id: 'minor',     label: 'Minor Damage',          desc: 'Small dents, scuffs or torn edges',          factor: 0.65, color: 'amber'  },
    { id: 'moderate',  label: 'Moderate Damage',       desc: 'Visible damage, partially compromised',      factor: 0.80, color: 'orange' },
    { id: 'heavy',     label: 'Heavily Damaged',       desc: 'Significantly damaged, hard to resell',      factor: 0.95, color: 'red'    },
    { id: 'destroyed', label: 'Destroyed / Unusable',  desc: 'Packaging completely destroyed, item exposed', factor: 1.00, color: 'red'  },
  ];

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
      body: `Hi,\n\nI placed order #WM-8821 six days ago and I still haven't received it. The tracking page hasn't updated in 3 days and just says "In Transit".\n\nCould someone please look into this urgently? I needed this item by the weekend.\n\nThank you,\nSarah Thompson`,
    },
    {
      label: 'Wrong Item Delivered',
      senderType: 'customer',
      senderName: 'Marcus Reid',
      senderEmail: 'marcusreid22@gmail.com',
      subject: 'Received wrong product — Order #WM-9034',
      body: `Hi there,\n\nI ordered a Blue 12-Cup Coffee Maker (Model CM-200) but received a Red 8-Cup version instead. This was meant as a birthday gift and I'm very disappointed.\n\nOrder #WM-9034 — placed on March 8th.\n\nI'd like either the correct item sent to me or a full refund. Please advise on next steps.\n\nThanks,\nMarcus`,
    }
  ];

  function applySample(s) {
    enquirySenderName  = s.senderName;
    enquirySenderEmail = s.senderEmail;
    enquirySenderType  = s.senderType;
    enquirySubject     = s.subject;
    enquiryRawMessage  = s.body;
  }

  // ── Financials ────────────────────────────────────────────────────────────
  let returnAmt       = '';
  let netLoss         = '';
  let returnAmtEdited = false;
  let netLossEdited   = false;
  let priority        = 'medium';

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
    { n: 1, label: 'Customer Lookup' },
    { n: 2, label: 'Assessment & Decision' },
    { n: 3, label: 'Submit Ticket' },
  ];

  // ── Derived ───────────────────────────────────────────────────────────────
  $: packagingMeta     = PACKAGING_CONDITIONS.find(p => p.id === packagingCondition);
  $: packagingFactor   = packagingMeta?.factor ?? 0;

  // Return amount: auto-fill from item price × qty unless agent has overridden
  $: if (!returnAmtEdited && itemDetails && returnQty) {
    returnAmt = (parseFloat(itemDetails.price) * returnQty).toFixed(2);
  }

  // Net loss: direct percentage calculation based on factor
  $: if (!netLossEdited && returnAmt && parseFloat(returnAmt) > 0) {
    netLoss = (parseFloat(returnAmt) * packagingFactor).toFixed(2);
  }

  $: step1Valid = lookupStatus !== '' && custName.trim();
    
  // Step 2 is valid once decision is logged
  $: step2Valid = decisionLogged;

  // Reset assessment complete flag if package condition changes
  $: if (packagingCondition) {
    assessmentComplete = false;
    assessmentError = '';
  }

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
    packagingCondition = '';
    assessmentComplete = false;
    resetFollowUpState();
  }

  // ── Assess Item Return ────────────────────────────────────────────────────
  function buildAssessmentPayload(followUpAnswers = []) {
    return {
      item_sk: itemDetails.sk,
      price: itemDetails.price,
      return_qty: returnQty,
      packaging_condition: packagingCondition,
      factor: packagingFactor,
      customer_email: custEmail.trim() || lookupEmail.trim(),
      customer_remarks: complaintDesc.trim(),
      follow_up_answers: followUpAnswers,
    };
  }

  function resetFollowUpState() {
    followUpMode = false;
    followUpQuestions = [];
    followUpCollected = [];
    activeFollowUpIndex = 0;
    activeFollowUpAnswer = '';
    followUpError = '';
  }

  async function submitAssessment(followUpAnswers = []) {
    if (!itemDetails) return;
    assessmentLoading = true;
    assessmentError = '';
    assessmentComplete = false;
    assessmentLoadingStep = 0;

    assessmentInterval = setInterval(() => {
      assessmentLoadingStep = Math.min(assessmentLoadingStep + 1, ASSESSMENT_STEPS.length - 1);
    }, 1500);

    try {
      const res = await fetch(`${FASTAPI}/api/access_item_return`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildAssessmentPayload(followUpAnswers))
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.message ?? `HTTP Error ${res.status}`);
      console.log('access_item_return response', data);
      assessmentResult = data;
      followUpMode = Boolean(data.awaitingFollowUp);
      followUpQuestions = data.followUpQuestions ?? data.remarksAnalysis?.follow_up_questions ?? [];
      assessmentComplete = Boolean(data.assessmentComplete) && !followUpMode;

      if (data.returnAmt !== undefined) {
        returnAmt = data.returnAmt;
        returnAmtEdited = true;
      }
      if (data.netLoss !== undefined) {
        netLoss = data.netLoss;
        netLossEdited = true;
      }

      if (followUpMode) {
        followUpCollected = [];
        activeFollowUpIndex = 0;
        activeFollowUpAnswer = '';
        followUpError = '';
      } else {
        resetFollowUpState();
      }
    } catch (e) {
      assessmentError = e.message;
    } finally {
      clearInterval(assessmentInterval);
      assessmentLoading = false;
    }
  }

  async function handleAssessReturn() {
    resetFollowUpState();
    assessmentResult = null;
    await submitAssessment([]);
  }

  function getDecisionSummary(result) {
    if (!result) return '';
    const parts = [];
    if (result.remarksAnalysis?.summary) parts.push(result.remarksAnalysis.summary);
    if (result.awaitingFollowUp) {
      parts.push('The backend still needs customer answers for the remaining questions.');
    } else if (result.assessmentComplete) {
      parts.push('All required checks are complete and ready for the financial review step.');
    }
    const unmet = (result.questions ?? []).filter(q => !q.validated).slice(0, 2);
    if (unmet.length) {
      parts.push(`Main unresolved checks: ${unmet.map(q => q.question).join(' ')}.`);
    }
    return parts.join(' ');
  }

  async function handleFollowUpNext() {
    const current = followUpQuestions?.[activeFollowUpIndex];
    if (!current) return;
    if (!activeFollowUpAnswer.trim()) {
      followUpError = 'Please provide an answer before continuing.';
      return;
    }

    followUpError = '';
    const nextCollected = [
      ...followUpCollected.filter(item => String(item.question_id) !== String(current.question_id)),
      {
        question_id: current.question_id,
        question: current.question,
        key: current.key,
        answer: activeFollowUpAnswer.trim(),
      }
    ];
    followUpCollected = nextCollected;

    if (activeFollowUpIndex < followUpQuestions.length - 1) {
      activeFollowUpIndex += 1;
      activeFollowUpAnswer = followUpCollected.find(item => String(item.question_id) === String(followUpQuestions[activeFollowUpIndex].question_id))?.answer ?? '';
      return;
    }

    await submitAssessment(nextCollected);
  }

  // ── Log Decision ─────────────────────────────────────────────────────────
  async function handleLogDecision(decision) {
    if (!assessmentResult || !itemDetails) return;
    
    decisionLogging = true;
    decisionError = '';
    
    const questionsValidated = (assessmentResult.questions || []).filter(q => q.validated).length;
    const summary = getDecisionSummary(assessmentResult);
    
    try {
      const res = await fetch(`${FASTAPI}/api/returns/log_decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_email: custEmail.trim() || lookupEmail.trim(),
          customer_name: custName.trim(),
          customer_tier: custTier,
          item_sk: itemDetails.sk,
          item_name: itemDetails.name,
          item_category: itemDetails.category || itemDetails.category_full || '',
          return_qty: returnQty,
          packaging_condition: packagingCondition,
          packaging_factor: packagingFactor,
          return_amt: parseFloat(returnAmt) || 0,
          net_loss: parseFloat(netLoss) || 0,
          assessment_confidence: assessmentResult.assessmentConfidence || 0,
          assessment_complete: assessmentResult.assessmentComplete || false,
          questions_validated: questionsValidated,
          assessment_summary: summary,
          decision: decision,
          decision_note: '',
        })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      
      decisionLogged = true;
      decisionId = data.decision_id || '—';
      
      // Enable proceeding to next step
      setTimeout(() => {
        step2Valid = true;
      }, 100);
      
    } catch (e) {
      decisionError = e.message;
    } finally {
      decisionLogging = false;
    }
  }

  // ── Navigation ────────────────────────────────────────────────────────────
  function nextStep() { if (step < 2) step++; }
  function prevStep() { if (step > 1) step--; }
  function setTicketType(t) {
    ticketType = t; step = 1;
    itemLookupSk = ''; itemLookupStatus = ''; itemDetails = null;
    packagingCondition = ''; assessmentComplete = false; assessmentResult = null;
    resetFollowUpState();
    enquirySubject = ''; enquiryCategory = ''; enquiryInputMode = 'email';
    enquiryRawMessage = ''; enquirySenderName = ''; enquirySenderEmail = ''; enquirySenderType = 'customer';
    returnAmt = ''; netLoss = '';
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    submitting = true; submitError = '';
    const payload = {
      ticketType,
      customer: { name: custName.trim(), email: custEmail.trim() || lookupEmail.trim(), tier: custTier, sk: custSk },
      channel: 'email', priority,
      packagingCondition,
      packagingFactor,
      ...(ticketType === 'return' ? {
        item: {
          sk:        itemDetails?.sk,
          rn:        itemDetails?.rn,
          name:      itemDetails?.name,
          category:  itemDetails?.category,
          class:     itemDetails?.cls,
          brand:     itemDetails?.brand,
          price:     itemDetails?.price,
          returnQty,
        },
        returnAmt:  parseFloat(returnAmt) || 0,
        netLoss:    parseFloat(netLoss)   || 0,
      } : {
        enquiryCategory,
        enquiryInputMode,
        enquiryRawMessage:  enquiryRawMessage.trim(),
        enquirySenderName:  enquirySenderName.trim(),
        enquirySenderType,
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
    packagingCondition = ''; assessmentComplete = false; assessmentResult = null;
    enquirySubject = ''; enquiryCategory = ''; enquiryInputMode = 'email';
    enquiryRawMessage = ''; enquirySenderName = ''; enquirySenderEmail = ''; enquirySenderType = 'customer';
    returnAmt = ''; netLoss = ''; returnAmtEdited = false; netLossEdited = false;
    priority = 'medium'; ticketType = 'return';
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function truncate(str, n) { return str && str.length > n ? str.slice(0, n) + '…' : (str ?? ''); }
  
  function formatDateStr(dStr) {
    if (!dStr) return '—';
    const d = new Date(dStr);
    if (isNaN(d.getTime())) return dStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
</script>

<div class="create-page">
  <header class="topbar">
    <div class="topbar-left">
      <h2>Create Ticket</h2>
      <div class="breadcrumb">New Ticket · Manual Entry · Item Return</div>
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
          Return ticket for <strong>{custName}</strong> has been created.
          <br/>Priority: <span class="priority-tag priority-{priority}">{priority}</span>
        </p>
        <div class="success-actions">
          <button class="btn btn-primary" on:click={goToQueue}>View in Queue</button>
          <button class="btn btn-secondary" on:click={createAnother}>Create Another</button>
        </div>
      </div>

    {:else}

      <div class="type-selector">
        <button class="type-btn" class:active={ticketType === 'return'} on:click={() => setTicketType('return')}>
          <span class="type-icon">↩</span>
          <span class="type-label">Item Return</span>
          <span class="type-desc">Customer returning a purchased item</span>
        </button>
      </div>

      <div class="step-bar">
        {#each stepLabels as s}
          <button class="step-pill" class:active={step === s.n} class:done={step > s.n}
            on:click={() => { if (s.n < step) step = s.n; else if (s.n === 2 && step1Valid) step = 2; }}>
            <span class="step-num">{step > s.n ? '✓' : s.n}</span>
            <span class="step-label">{s.label}</span>
          </button>
        {/each}
      </div>

      <div class="form-container">

        {#if step === 1}
            <!-- RETURN PATH -->
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
            
            <div class="step-actions" style="margin-bottom: 16px;">
              <div></div>
              <button class="btn btn-primary" disabled={!step1Valid} on:click={nextStep}>Next: Item & Assessment →</button>
            </div>

            <!-- Recent Orders Integration -->
            <div class="form-section">
              <div class="section-title-row">
                <div class="section-title" style="margin: 0;">Recent Orders <span class="section-sub">— click to auto-fill ticket details</span></div>
                
                <div class="recent-orders-controls">
                  <div class="chip-group">
                    <button class="chip" class:selected={dateFilter === 'all'} on:click={() => dateFilter = 'all'}>All Dates</button>
                    <button class="chip" class:selected={dateFilter === '7'} on:click={() => dateFilter = '7'}>Last 7 Days</button>
                  </div>
                  <button class="btn btn-ghost btn-sm" on:click={() => fetchRecentOrders(true)} disabled={ordersLoading}>
                    {#if ordersLoading}<span class="spinner-sm"></span>{:else}↻ Refresh{/if}
                  </button>
                </div>
              </div>

              {#if ordersError}
                <div class="error-banner mb-12">⚠ {ordersError}</div>
              {/if}

              {#if ordersLoading && !filteredOrders.length}
                <div style="padding: 30px; text-align: center; color: var(--text-muted);">
                  <span class="spinner-sm"></span> Loading recent orders from Snowflake...
                </div>
              {:else if filteredOrders.length > 0}
                <div class="recent-orders-list">
                  {#each filteredOrders as order}
                    <button class="recent-order-card" on:click={() => selectRecentOrder(order)}>
                      <div class="ro-header">
                        <span class="ro-date">{formatDateStr(order.PURCHASE_DATE || order.purchase_date)}</span>
                        <span class="ro-price">${parseFloat(order.sales_price || order.SALES_PRICE || 0).toFixed(2)}</span>
                      </div>
                      <div class="ro-customer">
                        <strong>{order.CUSTOMER_NAME || order.customer_name}</strong> 
                        <span class="ro-email">{order.C_EMAIL_ADDRESS || order.c_email_address}</span>
                      </div>
                      <div class="ro-body">
                        <div class="ro-name">{truncate(order.I_PRODUCT_NAME || order.i_product_name, 45)}</div>
                        <div class="ro-meta">
                          <span class="ro-category">{order.I_CATEGORY || order.i_category}</span>
                          {#if order.I_ITEM_SK || order.ITEM_SK || order.SS_ITEM_SK || order.i_item_sk || order.item_sk || order.ss_item_sk}
                            <span class="ro-dot">·</span>
                            <span class="ro-sk">SK {order.I_ITEM_SK || order.ITEM_SK || order.SS_ITEM_SK || order.i_item_sk || order.item_sk || order.ss_item_sk}</span>
                          {/if}
                        </div>
                      </div>
                      <div class="ro-arrow">→</div>
                    </button>
                  {/each}
                </div>
              {:else}
                <div class="empty-state">No recent orders found matching the filter.</div>
              {/if}
            </div>

            {#if submitError}<div class="error-banner">⚠ {submitError}</div>{/if}

            <div class="step-actions">
              <div></div>
              <button class="btn btn-submit" disabled={!step1Valid || submitting} on:click={handleSubmit}>
                {#if submitting}<span class="spinner-sm"></span> Creating…{:else}❖ Create Return Ticket{/if}
              </button>
            </div>

        {:else if step === 2 && ticketType === 'return'}

          <div class="form-section">
            <div class="section-title">Item To Return<span class="section-sub">by Item SK</span></div>
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

          <!-- MISSING PACKAGING ASSESSMENT UI BLOCK ADDED BACK HERE -->
          {#if itemDetails}
            <div class="form-section">
              <div class="section-title">Packaging Assessment <span class="req">*</span></div>
              <div class="packaging-grid">
                {#each PACKAGING_CONDITIONS as pkg}
                  <button 
                    class="pkg-card pkg-{pkg.color}" 
                    class:selected={packagingCondition === pkg.id} 
                    on:click={() => packagingCondition = pkg.id}
                  >
                    <div class="pkg-card-top">
                      <span class="pkg-label">{pkg.label}</span>
                    </div>
                    <div class="pkg-desc">{pkg.desc}</div>
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          <div class="form-section">
            <div class="section-title">
              Return Decision Prep
              <span class="lock-hint">Start with customer remarks, then reveal the package assessment and missing questions.</span>
            </div>

            <div class="assessment-action mt-12">
              <div class="field-group mb-12">
                <label class="field-label">Customer remarks (optional)</label>
                <textarea
                  bind:value={complaintDesc}
                  rows="4"
                  class="remarks-box"
                  placeholder="Optional notes from the customer. Example: 'Customer says the item arrived damaged and they still have the receipt.'"
                />
                <div class="field-hint">These notes are used as the researcher’s starting evidence before policy validation.</div>
              </div>
              
              {#if assessmentLoading}
                <div class="agent-loading-banner">
                  <div class="agent-spinner-ring">
                    <div class="agent-spinner-core"></div>
                  </div>
                  <div class="agent-loading-content">
                    <div class="agent-loading-title">Multi-Agent Assessment Running</div>
                    <div class="agent-loading-step">{ASSESSMENT_STEPS[assessmentLoadingStep]}</div>
                  </div>
                </div>
              {:else}
                <button class="btn btn-primary btn-assess" on:click={handleAssessReturn} disabled={!itemDetails || !packagingCondition}>
                  ✦ Analyze Return
                </button>
              {/if}

              {#if assessmentError}
                <div class="error-banner mt-12">⚠ {assessmentError}</div>
              {/if}
              {#if assessmentResult && !assessmentError}
                <div class="assessment-success">
                  <span class="banner-icon">✓</span> Assessment completed for decision prep.
                </div>
              {/if}
            </div>

            {#if assessmentResult}
              <div class="assessment-result-panel">
                <div class="assessment-result-header">
                  <div>
                    <div class="assessment-result-title">Assessment Summary</div>
                    <div class="assessment-result-sub">{getDecisionSummary(assessmentResult)}</div>
                    <!-- DEBUG -->
                    <div style="color: red; font-size: 10px; margin-top: 4px;">
                    </div>
                  </div>
                  <span class="result-badge {assessmentResult.assessmentComplete ? 'ok' : 'warn'}">
                    {assessmentResult.awaitingFollowUp ? 'needs answers' : assessmentResult.assessmentComplete ? 'complete' : 'review'}
                  </span>
                </div>

                <div class="assessment-result-grid">
                  <div class="result-card">
                    <span class="result-label">Confidence</span>
                    <span class="result-value">{Number(assessmentResult.assessmentConfidence ?? 0).toFixed(3)}</span>
                  </div>
                  <div class="result-card">
                    <span class="result-label">Return Amt</span>
                    <span class="result-value">${Number(assessmentResult.returnAmt ?? 0).toFixed(2)}</span>
                  </div>
                  <div class="result-card">
                    <span class="result-label">Net Loss</span>
                    <span class="result-value">${Number(assessmentResult.netLoss ?? 0).toFixed(2)}</span>
                  </div>
                  <div class="result-card">
                    <span class="result-label">Questions</span>
                    <span class="result-value">{assessmentResult.questions?.length ?? 0}</span>
                  </div>
                </div>

                {#if assessmentResult.remarksAnalysis?.summary}
                  <div class="result-block">
                    <div class="result-block-title">Decision Reasoning</div>
                    <div class="remarks-summary">{assessmentResult.remarksAnalysis.summary}</div>
                  </div>
                {/if}

                {#if assessmentResult.awaitingFollowUp && followUpMode && followUpQuestions?.length}
                  <div class="agent-request-panel">
                    <div class="agent-request-header">
                      <div class="agent-avatar-wrap">
                        <span class="agent-avatar">🤖</span>
                        <span class="agent-pulse-mini"></span>
                      </div>
                      <div class="agent-request-title">
                        <strong>Researcher Agent requires clarification</strong>
                        <span>Please ask the customer the following to complete policy validation</span>
                      </div>
                    </div>

                    <div class="follow-up-card">
                      <div class="follow-up-progress">
                        Action Item {activeFollowUpIndex + 1} of {followUpQuestions.length}
                      </div>
                      <div class="follow-up-question">
                        {followUpQuestions[activeFollowUpIndex]?.question}
                      </div>
                      
                      <!-- Dynamic Contextual Inputs for Follow-up -->
                      {#if followUpQuestions[activeFollowUpIndex]?.key === 'proof_of_purchase' || followUpQuestions[activeFollowUpIndex]?.key === 'visual_authenticity'}
                        <div class="follow-up-options">
                          <button class="follow-up-option-btn" class:selected={activeFollowUpAnswer === 'Yes'} on:click={() => activeFollowUpAnswer = 'Yes'}>Yes</button>
                          <button class="follow-up-option-btn" class:selected={activeFollowUpAnswer === 'No'} on:click={() => activeFollowUpAnswer = 'No'}>No</button>
                        </div>
                      {:else if followUpQuestions[activeFollowUpIndex]?.key === 'seller_type'}
                        <div class="follow-up-options">
                          <button class="follow-up-option-btn" class:selected={activeFollowUpAnswer === 'Walmart Store'} on:click={() => activeFollowUpAnswer = 'Walmart Store'}>Walmart Store</button>
                          <button class="follow-up-option-btn" class:selected={activeFollowUpAnswer === 'Marketplace Seller'} on:click={() => activeFollowUpAnswer = 'Marketplace Seller'}>Marketplace</button>
                        </div>
                      {:else if followUpQuestions[activeFollowUpIndex]?.key === 'return_channel'}
                        <div class="follow-up-options">
                          <button class="follow-up-option-btn" class:selected={activeFollowUpAnswer === 'In-store'} on:click={() => activeFollowUpAnswer = 'In-store'}>In-store</button>
                          <button class="follow-up-option-btn" class:selected={activeFollowUpAnswer === 'Mail'} on:click={() => activeFollowUpAnswer = 'Mail'}>Mail</button>
                        </div>
                      {:else if followUpQuestions[activeFollowUpIndex]?.key === 'purchase_date'}
                        <input type="date" bind:value={activeFollowUpAnswer} class="agent-reply-box date-input" />
                      {:else}
                        <textarea
                          bind:value={activeFollowUpAnswer}
                          rows="3"
                          class="agent-reply-box"
                          placeholder="Type the customer's answer here..."
                        ></textarea>
                      {/if}

                      {#if followUpError}
                        <div class="error-banner mt-12">⚠ {followUpError}</div>
                      {/if}
                      <div class="follow-up-actions">
                        <button class="btn btn-primary" on:click={handleFollowUpNext} disabled={assessmentLoading}>
                          {#if assessmentLoading}
                            <span class="spinner-sm"></span> Validating...
                          {:else if activeFollowUpIndex < followUpQuestions.length - 1}
                            Save & Next Item
                          {:else}
                            Validate Answers
                          {/if}
                        </button>
                      </div>
                    </div>
                    
                    <div class="coverage-list mt-12">
                      {#each followUpQuestions as followUp, idx}
                        <div class="coverage-item" class:active-coverage={idx === activeFollowUpIndex}>
                          <div class="coverage-item-head">
                            <span>{followUp.question}</span>
                            {#if idx < activeFollowUpIndex}
                              <span class="coverage-pill ok">✓ Answered</span>
                            {:else if idx === activeFollowUpIndex}
                              <span class="coverage-pill warn">Awaiting Input</span>
                            {:else}
                              <span class="coverage-pill pending">Queued</span>
                            {/if}
                          </div>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}

                <details class="trace-details">
                  <summary>Endpoint logs and raw response</summary>
                  <div class="trace-body">
                    {#if assessmentResult.remarksAnalysis}
                      <div class="result-block">
                        <div class="result-block-title">Remarks Analysis</div>
                        <pre>{JSON.stringify(assessmentResult.remarksAnalysis, null, 2)}</pre>
                      </div>
                    {/if}
                    <div class="result-block">
                      <div class="result-block-title">Raw Endpoint Response</div>
                      <pre>{assessmentResultJson}</pre>
                    </div>
                    {#if assessmentResult.salesHistory}
                      <div class="result-block">
                        <div class="result-block-title">Sales History</div>
                        <pre>{JSON.stringify(assessmentResult.salesHistory, null, 2)}</pre>
                      </div>
                    {/if}
                    {#if assessmentResult.salesValidation}
                      <div class="result-block">
                        <div class="result-block-title">Sales Validation</div>
                        <pre>{JSON.stringify(assessmentResult.salesValidation, null, 2)}</pre>
                      </div>
                    {/if}
                    {#if assessmentResult.itemValidation}
                      <div class="result-block">
                        <div class="result-block-title">Item Validation</div>
                        <pre>{JSON.stringify(assessmentResult.itemValidation, null, 2)}</pre>
                      </div>
                    {/if}
                    {#if assessmentResult.questions?.length}
                      <div class="result-block">
                        <div class="result-block-title">Question Coverage</div>
                        <div class="coverage-list">
                          {#each assessmentResult.questions as question}
                            <div class="coverage-item">
                              <div class="coverage-item-head">
                                <span>{question.question}</span>
                                <span class="coverage-pill {question.validated ? 'ok' : 'warn'}">
                                  {question.validated ? 'validated' : 'needs input'}
                                </span>
                              </div>
                              <div class="coverage-item-meta">
                                <span><strong>Source:</strong> {question.answerSource || question.answer_source || 'n/a'}</span>
                                <span><strong>Answer:</strong> {question.answer || '—'}</span>
                              </div>
                              {#if question.exactIssue || question.exact_issue}
                                <div class="coverage-item-issue">{question.exactIssue || question.exact_issue}</div>
                              {/if}
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}
                  </div>
                </details>
              </div>
            {/if}

            {#if assessmentResult && !followUpMode && !decisionLogged}
              {@const isApproved = assessmentResult.assessmentComplete}
              {@const confScore = ((assessmentResult.assessmentConfidence || 0) * 100).toFixed(0)}
              {@const failedQuestions = assessmentResult.questions?.filter(q => !q.validated) || []}
              {@const aiRecText = isApproved
                ? "All policy requirements have been validated successfully. The researcher agent recommends approving this return."
                : failedQuestions.length > 0
                  ? `The researcher agent flags this return for denial. Policy deviations identified: ${failedQuestions.map(q => q.exact_issue || q.validation_note || q.question).join(' | ')}`
                  : "Additional information is required or policy conditions were not explicitly met. Manual review recommended."
              }

              <div class="decision-panel" class:review-mode={!isApproved}>
                <div class="decision-panel-header">
                  <span class="decision-icon" class:warn-icon={!isApproved}>
                    {isApproved ? '✓' : '⚠'}
                  </span>
                  <div>
                    <div class="decision-title">
                      {isApproved ? 'Assessment Complete' : 'Policy Deviation Detected'} — Make Final Decision
                    </div>
                    <div class="decision-subtitle">Based on the multi-agent analysis, review the recommendation below and decide the outcome</div>
                  </div>
                </div>

                <div class="decision-suggestion">
                  <div class="decision-suggestion-label">✦ Researcher Agent Recommendation</div>
                  <div class="decision-suggestion-text">{aiRecText}</div>
                </div>

                <div class="decision-metrics">
                  <div class="decision-metric">
                    <span class="dm-label">Confidence</span>
                    <span class="dm-value" class:high={assessmentResult.assessmentConfidence >= 0.7} class:low={assessmentResult.assessmentConfidence < 0.7}>
                      {confScore}%
                    </span>
                  </div>
                  <div class="decision-metric">
                    <span class="dm-label">Validated</span>
                    <span class="dm-value">
                      {(assessmentResult.questions || []).filter(q => q.validated).length}/{(assessmentResult.questions || []).length || 5}
                    </span>
                  </div>
                  <div class="decision-metric">
                    <span class="dm-label">Net Loss</span>
                    <span class="dm-value loss">${Number(assessmentResult.netLoss || 0).toFixed(2)}</span>
                  </div>
                </div>

                <div class="decision-actions">
                  <button 
                    class="btn btn-decision btn-approve" 
                    class:recommended={isApproved}
                    on:click={() => handleLogDecision('approved')}
                    disabled={decisionLogging}
                  >
                    {#if decisionLogging}
                      <span class="spinner-sm"></span> Logging...
                    {:else}
                      <span>✓ Approve Return</span>
                      {#if isApproved}
                        <span class="btn-conf-badge">{confScore}% Confident</span>
                      {/if}
                    {/if}
                  </button>
                  <button 
                    class="btn btn-decision btn-deny" 
                    class:recommended={!isApproved}
                    on:click={() => handleLogDecision('denied')}
                    disabled={decisionLogging}
                  >
                    {#if decisionLogging}
                      <span class="spinner-sm"></span> Logging...
                    {:else}
                      <span>✕ Deny Return</span>
                      {#if !isApproved}
                        <span class="btn-conf-badge">{confScore}% Confident</span>
                      {/if}
                    {/if}
                  </button>
                </div>

                {#if decisionError}
                  <div class="error-banner mt-12">⚠ {decisionError}</div>
                {/if}
              </div>
            {/if}

            {#if decisionLogged}
              <div class="decision-logged-banner">
                <div class="decision-logged-content">
                  <span class="banner-icon">✓</span>
                  <div class="banner-body">
                    <strong>Decision Logged Successfully</strong>
                    <span class="banner-sub">Decision ID: {decisionId} — Return processing complete</span>
                  </div>
                </div>
                <div class="decision-logged-actions">
                  <button class="btn btn-primary" on:click={goToQueue}>View in Queue</button>
                  <button class="btn btn-secondary" on:click={createAnother}>Create Another</button>
                </div>
              </div>
            {/if}
          
          </div>
          <div class="step-actions">
            <button class="btn btn-ghost" on:click={prevStep}>← Back</button>
            {#if !decisionLogged}
              <div class="step-hint">Complete the assessment and make a decision to proceed</div>
            {/if}
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
  .form-section.section-hidden { display: none; }
  .form-section.section-visible { display: block; }
  .section-title { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; font-family: var(--font-mono); margin-bottom: 16px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .section-sub   { font-size: 10px; color: var(--text-muted); font-weight: 400; text-transform: none; letter-spacing: 0; }
  .lock-hint { color: var(--text-muted); font-size: 10px; font-weight: 400; text-transform: none; letter-spacing: 0; }
  .section-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
  .section-title-row .section-title { margin-bottom: 0; }
  .req { color: var(--red); }
  .mb-12 { margin-bottom: 12px; }

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

  /* Recent Orders list */
  .recent-orders-controls { display: flex; align-items: center; gap: 12px; }
  .recent-orders-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 10px; }
  .recent-order-card { display: flex; flex-direction: column; align-items: stretch; padding: 16px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; transition: all 0.15s; text-align: left; position: relative; }
  .recent-order-card:hover { border-color: rgba(212,168,67,0.4); background: var(--amber-glow); transform: translateY(-1px); }
  .ro-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .ro-date { font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .ro-price { font-family: var(--font-mono); font-size: 13.5px; font-weight: 600; color: var(--amber); }
  .ro-customer { margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border); display: flex; flex-direction: column; gap: 2px; }
  .ro-customer strong { font-size: 13px; color: var(--text-primary); }
  .ro-email { font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); }
  .ro-body { flex: 1; margin-bottom: 4px; }
  .ro-name { font-size: 12.5px; font-weight: 500; color: var(--text-primary); line-height: 1.4; margin-bottom: 6px; }
  .ro-meta { font-size: 11px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }
  .ro-sk { font-family: var(--font-mono); font-size: 10.5px; color: var(--text-muted); background: var(--bg-surface); padding: 2px 6px; border-radius: 3px; border: 1px solid var(--border); }
  .ro-dot { color: var(--border); }
  .ro-arrow { position: absolute; bottom: 16px; right: 16px; font-size: 14px; color: var(--amber); opacity: 0; transition: opacity 0.15s, transform 0.15s; transform: translateX(-4px); }
  .recent-order-card:hover .ro-arrow { opacity: 1; transform: translateX(0); }
  .empty-state { padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-elevated); border: 1px dashed var(--border); border-radius: var(--radius-sm); font-size: 13px; }

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

  .pkg-card.pkg-green.selected  { border-color: rgba(76,175,130,0.5);  background: var(--green-dim); }
  .pkg-card.pkg-amber.selected  { border-color: rgba(212,168,67,0.5);  background: var(--amber-glow); }
  .pkg-card.pkg-orange.selected { border-color: rgba(224,138,60,0.5);  background: var(--orange-dim); }
  .pkg-card.pkg-red.selected    { border-color: rgba(224,92,92,0.5);   background: var(--red-dim); }
  .pkg-card.pkg-green.selected  .pkg-label { color: var(--green); }
  .pkg-card.pkg-amber.selected  .pkg-label { color: var(--amber); }
  .pkg-card.pkg-orange.selected .pkg-label { color: var(--orange); }
  .pkg-card.pkg-red.selected    .pkg-label { color: var(--red); }

  /* Assessment */
  .assessment-action { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; width: 100%; }
  .btn-assess { align-self: flex-start; }
  .assessment-success { font-size: 12px; color: var(--green); display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: var(--green-dim); border: 1px solid rgba(76,175,130,0.3); border-radius: var(--radius-sm); }
  
  /* Agent Loading UI */
  .agent-loading-banner { display: flex; align-items: center; gap: 16px; padding: 16px 20px; background: linear-gradient(90deg, rgba(212,168,67,0.1), rgba(212,168,67,0.02)); border: 1px solid rgba(212,168,67,0.3); border-radius: var(--radius-sm); width: 100%; border-left: 3px solid var(--amber); margin-bottom: 8px; }
  .agent-spinner-ring { position: relative; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .agent-spinner-core { width: 26px; height: 26px; border: 2px solid rgba(212,168,67,0.2); border-top-color: var(--amber); border-radius: 50%; animation: spin 0.8s linear infinite; position: absolute; }
  .agent-spinner-ring::after { content: ''; position: absolute; width: 10px; height: 10px; background: var(--amber); border-radius: 50%; box-shadow: 0 0 10px var(--amber); animation: agent-pulse 1.5s ease-in-out infinite alternate; }
  @keyframes agent-pulse { 0% { transform: scale(0.8); opacity: 0.5; } 100% { transform: scale(1.2); opacity: 1; } }
  .agent-loading-content { display: flex; flex-direction: column; gap: 4px; }
  .agent-loading-title { font-size: 12px; font-weight: 700; color: var(--amber); font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.05em; }
  .agent-loading-step { font-size: 13px; color: var(--text-primary); font-weight: 500; }

  .assessment-result-panel { width: 100%; margin-top: 14px; padding: 14px; border-radius: var(--radius-md); border: 1px solid rgba(212,168,67,0.2); background: linear-gradient(180deg, rgba(26,29,37,0.92), rgba(15,17,23,0.92)); }
  .assessment-result-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
  .assessment-result-title { font-size: 13px; font-weight: 700; color: var(--text-primary); }
  .assessment-result-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
  .result-badge { font-size: 10px; font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.08em; padding: 4px 8px; border-radius: 999px; border: 1px solid; }
  .result-badge.ok { color: var(--green); background: var(--green-dim); border-color: rgba(76,175,130,0.35); }
  .result-badge.warn { color: var(--amber); background: var(--amber-glow); border-color: rgba(212,168,67,0.35); }
  .assessment-result-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
  .result-card { padding: 10px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); }
  .result-label { display: block; font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-mono); }
  .result-value { display: block; margin-top: 4px; font-size: 13px; color: var(--text-primary); font-weight: 600; font-family: var(--font-mono); }
  .result-block { margin-top: 10px; }
  .result-block-title { font-size: 11px; font-weight: 700; color: var(--amber); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
  .result-block pre { margin: 0; padding: 10px 12px; border-radius: var(--radius-sm); background: #0b0d12; border: 1px solid var(--border); color: var(--text-secondary); font-size: 11px; line-height: 1.5; overflow: auto; max-height: 240px; white-space: pre-wrap; word-break: break-word; }
  .field-group { display: flex; flex-direction: column; gap: 6px; width: 100%; }
  .field-label { font-size: 11px; font-weight: 700; color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-mono); }
  .field-hint { font-size: 11.5px; color: var(--text-muted); line-height: 1.5; }
  .remarks-box { min-height: 96px; resize: vertical; }
  .coverage-list { display: flex; flex-direction: column; gap: 8px; }
  .coverage-item { padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-elevated); transition: all 0.15s; }
  .coverage-item-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; font-size: 12px; color: var(--text-primary); font-weight: 500; }
  .coverage-item-meta { display: flex; flex-wrap: wrap; gap: 10px 16px; margin-top: 6px; font-size: 11.5px; color: var(--text-muted); }
  .coverage-item-issue { margin-top: 6px; padding: 8px 10px; border-left: 3px solid var(--amber); background: rgba(212,168,67,0.08); color: var(--text-secondary); font-size: 11.5px; line-height: 1.5; border-radius: 4px; }
  .coverage-pill { font-size: 10px; font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.08em; padding: 3px 7px; border-radius: 999px; border: 1px solid; white-space: nowrap; }
  .coverage-pill.ok { color: var(--green); background: var(--green-dim); border-color: rgba(76,175,130,0.35); }
  .coverage-pill.warn { color: var(--amber); background: var(--amber-glow); border-color: rgba(212,168,67,0.35); }
  
  /* Agent Follow-up Request UI */
  .agent-request-panel { margin-top: 20px; padding: 18px; border: 1px dashed rgba(212,168,67,0.5); border-radius: var(--radius-md); background: linear-gradient(180deg, rgba(212,168,67,0.08), rgba(212,168,67,0.02)); position: relative; }
  .agent-request-header { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
  .agent-avatar-wrap { position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: var(--bg-elevated); border: 1px solid rgba(212,168,67,0.4); border-radius: 50%; font-size: 18px; z-index: 1; }
  .agent-pulse-mini { position: absolute; inset: -4px; border: 2px solid var(--amber); border-radius: 50%; opacity: 0; animation: agent-pulse-ring 2s infinite; z-index: 0; }
  @keyframes agent-pulse-ring { 0% { transform: scale(0.8); opacity: 0.8; } 100% { transform: scale(1.4); opacity: 0; } }
  .agent-request-title { display: flex; flex-direction: column; gap: 3px; }
  .agent-request-title strong { font-size: 14px; color: var(--amber); font-family: var(--font-display); }
  .agent-request-title span { font-size: 11.5px; color: var(--text-secondary); }
  
  .agent-reply-box { background: var(--bg-surface); border: 1px solid rgba(212,168,67,0.3); border-radius: var(--radius-sm); padding: 12px; font-size: 13px; color: var(--text-primary); width: 100%; transition: border-color 0.15s; outline: none; resize: vertical; min-height: 80px; margin-bottom: 10px; }
  .agent-reply-box:focus { border-color: var(--amber); box-shadow: 0 0 0 2px rgba(212,168,67,0.15); }
  .date-input { min-height: auto; cursor: pointer; color-scheme: dark; }

  .follow-up-options { display: flex; gap: 10px; margin-bottom: 10px; }
  .follow-up-option-btn { flex: 1; padding: 12px 16px; background: var(--bg-surface); border: 1px solid rgba(212,168,67,0.3); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
  .follow-up-option-btn:hover { background: rgba(212,168,67,0.05); }
  .follow-up-option-btn.selected { background: var(--amber-glow); border-color: var(--amber); color: var(--amber); box-shadow: 0 0 0 1px var(--amber); }

  .coverage-pill.pending { color: var(--text-muted); background: var(--bg-surface); border-color: var(--border); }
  .active-coverage { border-color: rgba(212,168,67,0.4) !important; background: rgba(212,168,67,0.05) !important; }
  
  .remarks-summary { font-size: 12px; color: var(--text-secondary); line-height: 1.5; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-elevated); }
  .follow-up-panel { display: flex; flex-direction: column; gap: 10px; }
  .follow-up-card { display: flex; flex-direction: column; gap: 10px; padding: 16px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-elevated); }
  .follow-up-progress { font-size: 10px; font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.08em; color: var(--amber); font-weight: 700; }
  .follow-up-question { font-size: 14px; color: var(--text-primary); line-height: 1.5; font-weight: 600; margin-bottom: 6px; }
  .follow-up-actions { display: flex; justify-content: flex-end; }
  .trace-details { margin-top: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-elevated); padding: 10px 12px; }
  .trace-details summary { cursor: pointer; font-size: 11px; font-weight: 700; color: var(--amber); text-transform: uppercase; letter-spacing: 0.08em; }
  .trace-body { margin-top: 10px; }
  
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
  .step-hint { font-size: 12px; color: var(--text-muted); font-style: italic; }

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

/* Decision panel */
  .decision-panel { margin-top: 14px; padding: 18px; border-radius: var(--radius-md); border: 1px solid rgba(76,175,130,0.3); background: var(--green-dim); }
  .decision-panel.review-mode { background: var(--amber-glow); border-color: rgba(212,168,67,0.3); }
  .decision-panel-header { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 16px; }
  .decision-icon { font-size: 28px; color: var(--green); flex-shrink: 0; }
  .decision-icon.warn-icon { color: var(--amber); }
  .decision-title { font-size: 14px; font-weight: 700; color: var(--text-primary); }
  .decision-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 4px; line-height: 1.5; }
  .decision-suggestion { margin-bottom: 16px; padding: 12px 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .decision-suggestion-label { font-size: 10px; font-family: var(--font-mono); font-weight: 700; color: var(--amber); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
  .decision-suggestion-text { font-size: 13px; color: var(--text-primary); line-height: 1.6; }
  .decision-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
  .decision-metric { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .dm-label { font-size: 10px; font-family: var(--font-mono); font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
  .dm-value { font-size: 14px; font-family: var(--font-mono); font-weight: 700; color: var(--text-primary); }
  .dm-value.high { color: var(--green); }
  .dm-value.low { color: var(--amber); }
  .dm-value.loss { color: var(--red); }
  .decision-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .btn-decision { padding: 14px 22px; font-size: 14px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; width: 100%; transition: all 0.2s; }
  .btn-decision.recommended { border-width: 2px; }
  .btn-approve { background: var(--green-dim); border-color: rgba(76,175,130,0.4); color: var(--green); }
  .btn-approve:hover:not(:disabled) { background: rgba(76,175,130,0.2); }
  .btn-approve.recommended { border-color: rgba(76,175,130,0.8); background: rgba(76,175,130,0.15); box-shadow: 0 0 15px rgba(76,175,130,0.1); }
  .btn-deny { background: var(--red-dim); border-color: rgba(224,92,92,0.4); color: var(--red); }
  .btn-deny:hover:not(:disabled) { background: rgba(224,92,92,0.2); }
  .btn-deny.recommended { border-color: rgba(224,92,92,0.8); background: rgba(224,92,92,0.15); box-shadow: 0 0 15px rgba(224,92,92,0.1); }
  .btn-conf-badge { font-family: var(--font-mono); font-size: 11px; background: rgba(0,0,0,0.3); padding: 3px 8px; border-radius: 4px; letter-spacing: 0.05em; font-weight: 700; display: inline-flex; align-items: center; color: var(--text-primary); }
  .decision-logged-banner { margin-top: 14px; padding: 16px 18px; background: var(--green-dim); border: 1px solid rgba(76,175,130,0.3); border-radius: var(--radius-sm); }
  .decision-logged-content { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
  .decision-logged-banner .banner-icon { color: var(--green); font-size: 20px; }
  .decision-logged-actions { display: flex; gap: 10px; justify-content: flex-end; }
  .step-hint { font-size: 12px; color: var(--text-muted); font-style: italic; }

</style>

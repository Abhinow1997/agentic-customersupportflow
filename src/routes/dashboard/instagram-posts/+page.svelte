<script>
  import { FASTAPI_URL } from '$lib/config.js';

  // ── Form state ────────────────────────────────────────────────────────────
  let retrievalSetting = 'yes';
  let critiqueRounds = 2;
  let productItemSk = '';
  let productName = '';
  let itemLookupSk = '';
  let itemLookupLoading = false;
  let itemLookupStatus = '';
  let itemDetails = null;
  let methodSectionContent = '';
  let campaignCaption = '';

  // ── Pipeline stream state ─────────────────────────────────────────────────
  let isStreaming = false;
  let streamError = '';
  let stages = [];
  let warnings = [];
  let finalResult = null;
  let expandedStages = {};

  // ── Image generation state ────────────────────────────────────────────────
  let customVisualPrompt = '';
  let isGeneratingImage = false;
  let generatedImageUrl = null;
  let imageGenError = '';
  let imageModel = 'gpt-image-2';
  let imageSize = '512x512';
  const SAMPLE_FEEDS = [
    {
      sk: 26399,
      brand: 'Raid',
      category: 'Shop by Brand',
      name: 'Raid Max Bed Bug Crack and Crevice Foaming Spray, 17.5 oz',
      theme: 'Home defense, fast relief, and confidence under pressure.',
      headline: 'When the problem is hidden, the solution has to go deeper.',
      caption: 'A fast-action, confidence-first post built around deep reach, precision coverage, and peace of mind for urgent home protection.',
      methodSectionContent: 'Create a home-defense campaign that feels urgent, trustworthy, and highly practical. Focus on quick relief, hidden problem solving, and the confidence homeowners feel when they have a product that reaches into cracks and crevices.',
      campaignCaption: 'Fast relief for hidden bed bug problems. Deep reach, precise coverage, and peace of mind for urgent home protection.',
      imageSrc: '/images/raid-sample.jpg',
      showImage: true,
      hashtags: ['#Raid', '#HomeProtection', '#PestControl', '#CleanHome'],
    },
    {
      sk: 4187,
      brand: 'Nature Valley',
      category: 'Food',
      name: 'Nature Valley Soft Baked Bar Peanut Butter',
      theme: 'Cozy snacking, everyday convenience, and wholesome energy.',
      headline: 'Soft-baked comfort for the snack moments in between.',
      caption: 'A warm pantry-style feed card that emphasizes texture, convenience, and everyday snack appeal with a wholesome tone.',
      methodSectionContent: 'Create a cozy snack campaign that feels warm, approachable, and easy to enjoy on the go. Highlight soft-baked texture, peanut butter flavor, and the sense of everyday convenience for busy people and families.',
      campaignCaption: 'Soft-baked comfort for snack moments in between. Wholesome, convenient, and ready for everyday energy.',
      imageSrc: '/images/nature-valley-sample.jpg',
      showImage: true,
      hashtags: ['#NatureValley', '#SnackTime', '#OnTheGo', '#Food'],
    },
    {
      sk: 11904,
      brand: 'Daim',
      category: 'Food',
      name: 'Daim Chocolate Tie Top Bag',
      theme: 'Premium treat, giftable indulgence, and rich dessert appeal.',
      headline: 'A small chocolate treat with a premium shelf presence.',
      caption: 'A polished, giftable visual direction with rich chocolate tones, crisp typography, and a premium retail feel.',
      methodSectionContent: 'Create a premium indulgence campaign that feels giftable, refined, and satisfying. Emphasize rich chocolate texture, elevated presentation, and the idea of a small treat that still feels special.',
      campaignCaption: 'A premium little treat with rich chocolate appeal, giftable style, and dessert-worthy indulgence.',
      imageSrc: '/images/daim-sample.jpg',
      showImage: true,
      hashtags: ['#Daim', '#Chocolate', '#SweetTreat', '#Dessert'],
    },
    {
      sk: 16237,
      brand: 'TRUSTMEDICAL',
      category: 'Health',
      name: 'Sharps Retrieval Containers, 1.25 gal',
      theme: 'Safety-first health management with clinical clarity.',
      headline: 'Clean handling, trusted disposal, and peace of mind.',
      caption: 'A precise, professional-looking healthcare visual built around safe storage, responsibility, and confidence in handling sharps.',
      methodSectionContent: 'Create a healthcare safety campaign that feels clinical, calm, and dependable. Focus on secure disposal, responsible handling, and the reassurance of a clean, organized system for medical waste management.',
      campaignCaption: 'Safe handling, trusted disposal, and peace of mind for everyday healthcare management.',
      hashtags: ['#HealthSafety', '#MedicalSupplies', '#TrustMedical', '#SafeDisposal'],
    },
    {
      sk: 2887,
      brand: 'JT Paintball',
      category: 'Sports & Outdoors',
      name: 'JT Chest Protector for Paintball',
      theme: 'Action-ready protection with sporty energy.',
      headline: 'Gear up for the game with confidence.',
      caption: 'An energetic outdoor sports post with bold motion, protective gear details, and a competitive, adrenaline-driven feel.',
      methodSectionContent: 'Create an action-sports campaign that feels energetic, protective, and competition-ready. Highlight mobility, confidence, and the excitement of gearing up for paintball with serious protection.',
      campaignCaption: 'Gear up for the game with confidence. Protective, bold, and built for action.',
      hashtags: ['#Paintball', '#SportsGear', '#JTPaintball', '#ProtectiveGear'],
    },
    {
      sk: 16782,
      brand: 'Desert Essence',
      category: 'Personal Care',
      name: 'Desert Essence Organics Hand & Body Lotion',
      theme: 'Natural self-care with calm, clean beauty.',
      headline: 'A daily ritual that feels soft and restorative.',
      caption: 'A spa-like wellness visual with organic textures, gentle skin-care cues, and a natural self-care mood.',
      methodSectionContent: 'Create a self-care campaign that feels calm, natural, and restorative. Emphasize soft texture, organic ingredients, and a soothing routine that fits into everyday wellness.',
      campaignCaption: 'A gentle daily ritual for soft, restored skin and calm natural beauty.',
      hashtags: ['#SelfCare', '#OrganicBeauty', '#BodyLotion', '#Wellness'],
    },
    {
      sk: 13902,
      brand: 'Charms',
      category: 'Food',
      name: '2 Pack - Charms Blow Pops Assorted 100ct',
      theme: 'Playful nostalgia and colorful candy fun.',
      headline: 'Sweet, bold, and made for sharing moments.',
      caption: 'A vibrant candy-forward post with bright color, playful layout, and nostalgic energy that feels fun and energetic.',
      methodSectionContent: 'Create a playful candy campaign that feels nostalgic, bright, and fun to share. Focus on colorful variety, sweet moments, and the joyful energy of a classic treat.',
      campaignCaption: 'Sweet, bold, and made for sharing moments. A colorful classic with nostalgic fun.',
      hashtags: ['#Candy', '#Charms', '#BlowPops', '#SweetTreats'],
    },
    {
      sk: 11536,
      brand: 'Curious Minds',
      category: 'Toys',
      name: '3D Geometric Shapes - Play Doh & Sand Molds',
      theme: 'Creative play, learning, and hands-on discovery.',
      headline: 'Build, shape, and imagine something new.',
      caption: 'A bright educational play visual that highlights learning through tactile, colorful, and imaginative play.',
      methodSectionContent: 'Create a kids learning campaign that feels imaginative, hands-on, and educational. Highlight tactile play, shape-building, and the creativity that comes from discovery through making.',
      campaignCaption: 'Build, shape, and imagine something new. Hands-on learning with colorful creative play.',
      hashtags: ['#KidsPlay', '#CreativeLearning', '#Toys', '#Imagination'],
    },
    {
      sk: 13229,
      brand: 'RAYOVAC',
      category: 'Household Essentials',
      name: 'ALKLN BATT AA 30PK',
      theme: 'Reliable everyday power for home essentials.',
      headline: 'Power up the devices you use every day.',
      caption: 'A clean utility-style product visual that focuses on reliability, convenience, and everyday household value.',
      methodSectionContent: 'Create a utility-focused household campaign that feels dependable, practical, and clear. Emphasize everyday power, convenience, and the value of having reliable batteries ready at home.',
      campaignCaption: 'Reliable everyday power for the devices you use every day.',
      hashtags: ['#HouseholdEssentials', '#Batteries', '#Rayovac', '#EverydayPower'],
    },
    {
      sk: 34030,
      brand: 'Crosman Archery',
      category: 'Sports & Outdoors',
      name: 'CenterPoint Sentinel Long Bow Set',
      theme: 'Precision, performance, and outdoor adventure.',
      headline: 'Built for focus, form, and the next shot.',
      caption: 'A bold outdoor gear visual with sleek lines, wood-and-metal textures, and a performance-forward feel.',
      methodSectionContent: 'Create an outdoor performance campaign that feels focused, precise, and adventure-ready. Highlight craftsmanship, control, and the confidence that comes from quality gear built for the next shot.',
      campaignCaption: 'Precision, performance, and outdoor adventure for the next shot.',
      hashtags: ['#Archery', '#OutdoorGear', '#SportsAndOutdoors', '#CenterPoint'],
    },
    {
      sk: 5977,
      brand: 'Wd-40',
      category: 'Household Essentials',
      name: '2PK 1.25 OZ 2000 Flushes Toilet Bowl Cleaner',
      theme: 'Clean, reliable maintenance for everyday home care.',
      headline: 'Freshness that works hard behind the scenes.',
      caption: 'A practical household-maintenance post with clean surfaces, bright visuals, and a dependable everyday tone.',
      methodSectionContent: 'Create a home-care campaign that feels practical, clean, and reliable. Focus on freshness, maintenance, and the everyday value of products that quietly keep the home running smoothly.',
      campaignCaption: 'Freshness that works hard behind the scenes for dependable home care.',
      hashtags: ['#HomeCare', '#Cleaning', '#HouseholdEssentials', '#FreshHome'],
    },
    {
      sk: 4581,
      brand: 'Food Club',
      category: 'Food',
      name: 'Canned Fruit',
      theme: 'Simple pantry staples and versatile everyday meals.',
      headline: 'A pantry classic made easy to reach for any recipe.',
      caption: 'A bright, approachable food post that feels practical, versatile, and family-friendly with grocery shelf appeal.',
      methodSectionContent: 'Create a pantry staples campaign that feels easy, versatile, and family-friendly. Highlight convenience, everyday use, and how simple ingredients can support a variety of meals and recipes.',
      campaignCaption: 'A pantry classic made easy for everyday meals and recipes.',
      hashtags: ['#PantryStaples', '#FoodClub', '#KitchenBasics', '#Fruit'],
    },
    {
      sk: 13964,
      brand: 'LITTLE TREES',
      category: 'Auto & Tires',
      name: 'Little Trees Vent Liquid Air Freshener',
      theme: 'Fresh car comfort and a clean driving experience.',
      headline: 'Small detail, big difference on every drive.',
      caption: 'A sleek automotive lifestyle visual with fresh scent cues, clean surfaces, and compact retail-friendly composition.',
      methodSectionContent: 'Create an automotive freshness campaign that feels clean, simple, and convenient. Focus on the small but meaningful detail that improves the driving experience and keeps the car feeling fresh.',
      campaignCaption: 'Small detail, big difference on every drive. Fresh car comfort made easy.',
      hashtags: ['#AutoCare', '#AirFreshener', '#LittleTrees', '#FreshRide'],
    },
    {
      sk: 28076,
      brand: 'Sorelle Furniture',
      category: 'Baby',
      name: 'Sorelle Berkley Round Top 4-in-1 Crib',
      theme: 'Nursery elegance, safety, and growing with the family.',
      headline: 'A nursery centerpiece designed to last through every stage.',
      caption: 'A calm, premium baby-room visual that emphasizes craftsmanship, security, and a beautiful home setting.',
      methodSectionContent: 'Create a nursery campaign that feels elegant, safe, and long-lasting. Highlight craftsmanship, comfort, and the reassurance of a beautiful centerpiece designed to grow with the family.',
      campaignCaption: 'A nursery centerpiece designed to last through every stage of family life.',
      hashtags: ['#BabyNursery', '#SorelleFurniture', '#CribDesign', '#FamilyHome'],
    },
  ];

  // Pre-fill prompt when flow result arrives
  $: if (finalResult?.visualizerPrompt && !customVisualPrompt) {
    customVisualPrompt = finalResult.visualizerPrompt;
  }

  // ── Stage label map ───────────────────────────────────────────────────────
  const STAGE_META = {
    controller:           { label: 'Pipeline Planning',       icon: '🗺' },
    reviewer_query:       { label: 'Snowflake DB Lookup',     icon: '🔍' },
    reviewer:             { label: 'Product Verification',    icon: '📦' },
    scraper:              { label: 'Web Scraping',            icon: '🌐' },
    summary_validation:   { label: 'Summary Validation',      icon: '⚖️' },
    summary_realign:      { label: 'Summary Realignment',     icon: '🔄' },
    content_generation:   { label: 'Content Generation',      icon: '✍️' },
    formatter:            { label: 'Output Formatting',       icon: '📋' },
  };

  function getStageLabel(stage) {
    if (STAGE_META[stage]) return STAGE_META[stage].label;
    if (stage.startsWith('critique_round_')) return `Critique — Round ${stage.split('_').pop()}`;
    if (stage.startsWith('content_revision_round_')) return `Revision — Round ${stage.split('_').pop()}`;
    return stage;
  }
  function getStageIcon(stage) {
    if (STAGE_META[stage]) return STAGE_META[stage].icon;
    if (stage.startsWith('critique_round_')) return '🔬';
    if (stage.startsWith('content_revision_round_')) return '✏️';
    return '⚙️';
  }

  // ── Form helpers ──────────────────────────────────────────────────────────
  function setRetrieval(v) { retrievalSetting = v; }
  function decRounds() { critiqueRounds = Math.max(0, critiqueRounds - 1); }
  function incRounds() { critiqueRounds = Math.min(5, critiqueRounds + 1); }
  function toggleStage(stage) {
    expandedStages = { ...expandedStages, [stage]: !expandedStages[stage] };
  }
  function formatJson(value) {
    try { return JSON.stringify(value, null, 2); }
    catch { return String(value ?? ''); }
  }

  function formatApiError(err, fallback = 'Request failed') {
    if (!err) return fallback;
    if (typeof err === 'string') return err;
    if (Array.isArray(err)) {
      return err.map((item) => {
        if (typeof item === 'string') return item;
        if (!item || typeof item !== 'object') return String(item);
        const parts = [];
        if (item.loc) parts.push(Array.isArray(item.loc) ? item.loc.join('.') : String(item.loc));
        if (item.msg) parts.push(item.msg);
        if (item.type) parts.push(`(${item.type})`);
        return parts.length ? parts.join(': ') : JSON.stringify(item);
      }).join(' | ');
    }
    if (typeof err === 'object') {
      if (typeof err.detail === 'string') return err.detail;
      if (Array.isArray(err.detail)) return formatApiError(err.detail, fallback);
      if (err.detail && typeof err.detail === 'object') return formatApiError(err.detail, fallback);
      if (err.message) return err.message;
      try { return JSON.stringify(err); } catch { return fallback; }
    }
    return String(err);
  }

  function formatMoney(val) {
    const num = Number.parseFloat(val);
    if (!Number.isFinite(num)) return '—';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num);
  }

  function buildItemDetailRows(item) {
    if (!item) return [];
    return [
      { label: 'Item SK', value: `SK ${item.sk ?? '—'}` },
      { label: 'Item ID', value: item.item_id || '—' },
      { label: 'Item Name', value: item.name || '—' },
      { label: 'Brand', value: item.brand || '—' },
      { label: 'Category', value: item.category || '—' },
      { label: 'Category Full', value: item.category_full || '—' },
      { label: 'Class', value: item.cls || '—' },
      { label: 'Item Number', value: item.item_number || '—' },
      { label: 'Unit Price', value: formatMoney(item.price) },
      { label: 'List Price', value: formatMoney(item.list_price) },
      { label: 'Package Size', value: item.package_size || '—' },
      { label: 'Product URL', value: item.url || '—', href: item.url || '' },
      { label: 'Description', value: item.desc || '—', multiline: true, wide: true },
    ];
  }

  $: itemDetailRows = buildItemDetailRows(itemDetails);

  function clearItemLookup() {
    itemLookupSk = '';
    itemLookupLoading = false;
    itemLookupStatus = '';
    itemDetails = null;
  }

  async function lookupItem() {
    const skRaw = String(itemLookupSk ?? '').trim();
    if (!skRaw) return;

    const parsedSk = Number.parseInt(skRaw, 10);
    if (Number.isNaN(parsedSk) || parsedSk <= 0) {
      itemLookupStatus = 'Product Item SK must be a valid positive number.';
      itemDetails = null;
      return;
    }

    itemLookupLoading = true;
    itemLookupStatus = '';
    itemDetails = null;

    try {
      const res = await fetch(`${FASTAPI_URL}/api/items?sk=${encodeURIComponent(String(parsedSk))}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(formatApiError(data.detail, `HTTP ${res.status}`));

      if (!data.found || !data.item) {
        itemLookupStatus = 'Item not found for that SK.';
        return;
      }

      itemDetails = data.item;
      productItemSk = String(data.item.sk ?? parsedSk);
      productName = data.item.name ?? '';
      itemLookupStatus = 'Item loaded into the workflow fields.';
    } catch (e) {
      itemLookupStatus = e.message ?? 'Item lookup failed.';
    } finally {
      itemLookupLoading = false;
    }
  }

  function useSampleFeed(sample) {
    itemLookupSk = String(sample.sk);
    methodSectionContent = sample.methodSectionContent ?? sample.caption ?? sample.theme ?? '';
    campaignCaption = sample.campaignCaption ?? sample.headline ?? sample.caption ?? '';
    lookupItem();
  }

  // ── Stream event handler ──────────────────────────────────────────────────
  function handleStreamEvent(event) {
    if (event.type === 'agent_start') {
      stages = [...stages, { stage: event.stage, agent: event.agent, status: 'running', output: null }];
    } else if (event.type === 'agent_complete') {
      stages = stages.map(s =>
        s.stage === event.stage ? { ...s, status: 'complete', output: event.output } : s
      );
    } else if (event.type === 'flow_warning') {
      warnings = [...warnings, event.message];
    } else if (event.type === 'flow_complete') {
      finalResult = event.result;
      isStreaming = false;
    } else if (event.type === 'flow_error') {
      streamError = event.error ?? 'Pipeline failed.';
      isStreaming = false;
    }
  }

  // ── Main pipeline run ─────────────────────────────────────────────────────
  async function runWorkflow() {
    streamError = '';
    finalResult = null;
    stages = [];
    warnings = [];
    expandedStages = {};
    generatedImageUrl = null;
    imageGenError = '';
    customVisualPrompt = '';

    const itemSkRaw = String(productItemSk ?? '').trim();
    const productNameRaw = String(productName ?? '').trim();
    if (!itemSkRaw) {
      streamError = 'Please look up an item first.';
      return;
    }
    if (methodSectionContent.trim().length < 10) {
      streamError = 'Method Section Content must be at least 10 characters.';
      return;
    }
    if (campaignCaption.trim().length < 5) {
      streamError = 'Campaign Caption Seed must be at least 5 characters.';
      return;
    }
    const parsedSk = itemSkRaw ? Number.parseInt(itemSkRaw, 10) : null;
    if (itemSkRaw && (Number.isNaN(parsedSk) || parsedSk <= 0)) {
      streamError = 'Product Item SK must be a valid positive number.';
      return;
    }

    isStreaming = true;
    try {
      const res = await fetch(`${FASTAPI_URL}/api/instagram-posts/generate-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          retrievalEnabled: retrievalSetting === 'yes',
          critiqueRounds,
          productItemSk: parsedSk,
          productName: productNameRaw || null,
          methodSectionContent: methodSectionContent.trim(),
          productMarketingCampaignCaption: campaignCaption.trim(),
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(formatApiError(data.detail, `HTTP ${res.status}`));
      }
      if (!res.body) throw new Error('No stream body from server.');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';
        for (const part of parts) {
          const line = part.trim();
          if (line.startsWith('data: ')) {
            try { handleStreamEvent(JSON.parse(line.slice(6))); } catch {}
          }
        }
      }
    } catch (e) {
      streamError = e.message ?? 'Workflow request failed.';
      isStreaming = false;
    }
  }

  // ── Image generation ──────────────────────────────────────────────────────
  async function generateImage() {
    if (!customVisualPrompt.trim()) return;
    isGeneratingImage = true;
    imageGenError = '';
    generatedImageUrl = null;

    try {
      const res = await fetch(`${FASTAPI_URL}/api/instagram-posts/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: customVisualPrompt.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      generatedImageUrl = data.imageUrl;
      imageModel = data.model ?? 'gpt-image-2';
      imageSize = data.size ?? '512x512';
    } catch (e) {
      imageGenError = e.message ?? 'Image generation failed.';
    } finally {
      isGeneratingImage = false;
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  $: completedCount = stages.filter(s => s.status === 'complete').length;
  $: totalCount = stages.length;
  $: runningStage = stages.find(s => s.status === 'running');
  $: hasPipeline = stages.length > 0;
  $: hasPosts = finalResult?.posts?.length > 0;
  $: hasVisualPrompt = !!(finalResult?.visualizerPrompt);
</script>

<div class="page">
  <!-- ── Top bar ────────────────────────────────────────────────────────── -->
  <header class="topbar">
    <div class="topbar-left">
      <h2>Instagram Posts Creation</h2>
      <div class="subtitle">crewAI multi-agent marketing pipeline</div>
    </div>
    <div class="topbar-right">
      <span class="badge">Tooling</span>
      <span class="badge crew">crewAI</span>
      {#if isStreaming}
        <span class="badge live">● LIVE</span>
      {:else if finalResult}
        <span class="badge done">✓ Complete</span>
      {/if}
    </div>
  </header>

  <!-- ── Main grid ──────────────────────────────────────────────────────── -->
  <div class="content-grid">

    <!-- ── Left: Form ──────────────────────────────────────────────────── -->
    <div class="form-card">
      <div class="section-head">
        <h3>Pipeline Settings</h3>
        <p>Configure the crewAI content generation pipeline.</p>
      </div>

      <div class="field-group">
        <label>Retrieval (Snowflake lookup)</label>
        <div class="toggle-row">
          <button class="tog" class:sel={retrievalSetting === 'yes'} on:click={() => setRetrieval('yes')}>Yes</button>
          <button class="tog" class:sel={retrievalSetting === 'no'}  on:click={() => setRetrieval('no')}>No</button>
        </div>
      </div>

      <div class="field-group">
        <label>Critique Rounds</label>
        <div class="counter">
          <button class="cnt-btn" on:click={decRounds} disabled={critiqueRounds === 0}>−</button>
          <div class="cnt-val">{critiqueRounds}</div>
          <button class="cnt-btn" on:click={incRounds} disabled={critiqueRounds === 5}>+</button>
        </div>
        <div class="field-note">0 – 5 rounds of critique + revision</div>
      </div>

      <div class="field-group">
        <label>Item Lookup</label>
        <div class="lookup-row">
          <input
            class="text-input lookup-input"
            type="number"
            min="1"
            step="1"
            bind:value={itemLookupSk}
            placeholder="Look up by Item SK, e.g. 813"
            on:keydown={(e) => e.key === 'Enter' && lookupItem()}
            disabled={itemLookupLoading}
          />
          <button class="btn lookup-btn" on:click={lookupItem} disabled={itemLookupLoading || !String(itemLookupSk).trim()}>
            {#if itemLookupLoading}
              <span class="spinner-sm"></span> Loading...
            {:else}
              Lookup
            {/if}
          </button>
          {#if itemLookupStatus}
            <button class="btn btn-clear" on:click={clearItemLookup}>Clear</button>
          {/if}
        </div>

        {#if itemLookupStatus}
          <div class="lookup-status">{itemLookupStatus}</div>
        {/if}

        {#if itemDetails}
          <div class="item-card">
            <div class="item-card-header">
              <div>
                <div class="item-card-title">{itemDetails.name}</div>
                <div class="item-card-subtitle">{itemDetails.category_full || itemDetails.category || 'Loaded from /api/items'}</div>
              </div>
              <span class="item-sk-badge">SK {itemDetails.sk}</span>
            </div>

            <div class="item-meta-grid">
              {#each itemDetailRows as row}
                <div class="item-meta-cell" class:wide={row.wide}>
                  <span class="meta-label">{row.label}</span>
                  {#if row.href}
                    <a class="meta-val link" href={row.href} target="_blank" rel="noreferrer">{row.value}</a>
                  {:else if row.multiline}
                    <div class="meta-val multiline">{row.value}</div>
                  {:else}
                    <span class="meta-val {row.label === 'Unit Price' || row.label === 'List Price' ? 'price' : ''}">{row.value}</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <div class="field-group">
        <label for="method-content">Method Section Content</label>
        <textarea id="method-content" class="text-area" rows="7" bind:value={methodSectionContent}
          placeholder="Describe your marketing idea, target audience, tone, and creative direction."></textarea>
      </div>

      <div class="field-group">
        <label for="campaign-caption">Campaign Caption Seed</label>
        <textarea id="campaign-caption" class="text-area" rows="4" bind:value={campaignCaption}
          placeholder="Draft caption direction or headline seed for the posts."></textarea>
      </div>

      <div class="actions">
        <button class="run-btn" on:click={runWorkflow} disabled={isStreaming}>
          {#if isStreaming}
            <span class="spinner-sm"></span> Running pipeline...
          {:else}
            ▶ Run Instagram Workflow
          {/if}
        </button>
      </div>

      {#if streamError}
        <div class="error-banner">{streamError}</div>
      {/if}
    </div>

    <!-- ── Right: Output panel ─────────────────────────────────────────── -->
    <div class="output-panel">

      {#if !hasPipeline && !streamError}
        <!-- Empty state -->
        <div class="empty-state">
          <div class="empty-icon">🎯</div>
          <div class="empty-title">Ready to generate</div>
          <div class="empty-sub">Configure your campaign and click Run to start the crewAI pipeline. Agent outputs will stream in live.</div>
          <div class="sample-feeds">
            <div class="section-label sample-heading">
              <span class="section-icon">🧪</span>
              Sample Feed Concepts
              <span class="post-count">3 examples</span>
            </div>
            <div class="sample-feed-grid">
              {#each SAMPLE_FEEDS as sample}
                <button type="button" class="sample-feed-card" on:click={() => useSampleFeed(sample)}>
                  <div class="sample-visual">
                    <div class="sample-visual-top">
                      <span class="sample-brand">{sample.brand}</span>
                      <span class="sample-sku">SK {sample.sk}</span>
                    </div>
                    {#if sample.showImage && sample.imageSrc}
                      <div class="sample-image-block">
                        <img class="sample-image" src={sample.imageSrc} alt={sample.name} loading="lazy" />
                      </div>
                    {/if}
                  </div>
                  <div class="sample-body">
                    <div class="sample-feed-category">{sample.category}</div>
                    <h4 class="sample-feed-title">{sample.name}</h4>
                    <div class="sample-feed-theme">{sample.theme}</div>
                    <p class="sample-feed-headline">{sample.headline}</p>
                    <p class="sample-feed-caption">{sample.caption}</p>
                    <div class="sample-feed-meta">
                      <div class="sample-feed-tags">
                        {#each sample.hashtags as tag}
                          <span class="tag-pill">{tag}</span>
                        {/each}
                      </div>
                    </div>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        </div>

      {:else}

        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- 1. GENERATED POSTS — hero section                              -->
        <!-- ═══════════════════════════════════════════════════════════════ -->
        {#if hasPosts}
          <div class="posts-hero">
            <div class="section-label">
              <span class="section-icon">✦</span>
              Generated Posts
              <span class="post-count">{finalResult.posts.length} options</span>
            </div>

            <div class="posts-grid">
              {#each finalResult.posts as post, i}
                <div class="post-card">
                  <div class="post-option">Option {i + 1}</div>
                  <div class="post-headline">{post.headline}</div>
                  <p class="post-caption">{post.caption}</p>
                  <div class="post-tags">
                    {#each (post.hashtags || []) as tag}
                      <span class="tag-pill">{tag}</span>
                    {/each}
                  </div>
                  <div class="post-footer">
                    <div class="post-visual">
                      <span class="footer-label">📸</span>
                      <span>{post.visualDirection}</span>
                    </div>
                    <div class="post-cta-row">
                      <span class="cta-chip">{post.cta}</span>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- 2. VISUAL SUGGESTION GENERATOR — GPT Image 2                 -->
        <!-- ═══════════════════════════════════════════════════════════════ -->
        {#if hasVisualPrompt}
          <div class="visual-gen-card">
            <div class="section-label">
              <span class="section-icon">🎨</span>
              Visual Suggestion Generator
              <span class="image-model-badge">GPT Image 2</span>
            </div>

            <p class="visual-intro">
              The Content Agent produced a visual direction prompt. Generate a reference image to accompany your campaign — edit the prompt below before generating if needed.
            </p>

            <div class="prompt-field">
              <div class="prompt-label">Visual Prompt <span class="prompt-source">(from Content Agent)</span></div>
              <textarea
                class="prompt-textarea"
                rows="3"
                bind:value={customVisualPrompt}
                placeholder="Visual direction prompt will appear here after the pipeline runs..."
              ></textarea>
            </div>

            <div class="gen-actions">
              <button
                class="gen-btn"
                on:click={generateImage}
                disabled={isGeneratingImage || !customVisualPrompt.trim()}
              >
                {#if isGeneratingImage}
                  <span class="spinner-sm"></span> Generating...
                {:else}
                  ✦ Generate Visual
                {/if}
              </button>
              <div class="gen-meta-row">
                <span class="gen-meta-pill">model: {imageModel}</span>
                <span class="gen-meta-pill">size: {imageSize}</span>
              </div>
            </div>

            {#if imageGenError}
              <div class="img-error">{imageGenError}</div>
            {/if}

            {#if isGeneratingImage}
              <div class="img-skeleton">
                <div class="skeleton-shimmer"></div>
                <div class="skeleton-label">
                  <span class="spinner-sm"></span>
                  Generating image with GPT Image 2 — this takes ~10s...
                </div>
              </div>
            {/if}

            {#if generatedImageUrl}
              <div class="img-result">
                <div class="img-wrapper">
                  <img
                    src={generatedImageUrl}
                    alt="AI-generated visual suggestion for campaign"
                    class="gen-img"
                  />
                  <div class="img-overlay">
                    <a href={generatedImageUrl} target="_blank" rel="noopener noreferrer" class="img-fullsize-btn">
                      ↗ Open full size
                    </a>
                  </div>
                </div>

                <div class="img-meta">
                  <div class="img-disclaimer">
                    ⚠ AI-generated suggestion · For creative direction and inspiration only · Review before any commercial use
                  </div>
                  <button class="regen-btn" on:click={generateImage} disabled={isGeneratingImage}>
                    ↺ Regenerate
                  </button>
                </div>
              </div>
            {/if}
          </div>
        {/if}

        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- 3. CAMPAIGN DETAILS — collapsible                              -->
        <!-- ═══════════════════════════════════════════════════════════════ -->
        {#if finalResult}
          <details class="campaign-details" open>
            <summary class="details-summary">
              <span class="section-icon">📊</span> Campaign Details
              <span class="details-chevron">▾</span>
            </summary>
            <div class="details-body">
              {#if warnings.length}
                <div class="warnings-box">
                  <div class="warn-label">⚠ Pipeline Warnings</div>
                  {#each warnings as w}
                    <div class="warn-row">{w}</div>
                  {/each}
                </div>
              {/if}

              <div class="detail-block">
                <div class="detail-key">Strategy Summary</div>
                <p class="detail-text">{finalResult.strategySummary}</p>
              </div>

              {#if finalResult.sourceTruth && finalResult.sourceTruth !== 'Reviewer skipped.'}
                <div class="detail-block">
                  <div class="detail-key">Reviewer Source Truth</div>
                  <p class="detail-text">{finalResult.sourceTruth}</p>
                </div>
              {/if}

              {#if finalResult.scrapedSummary && finalResult.scrapedSummary !== 'Scraper skipped.'}
                <div class="detail-block">
                  <div class="detail-key">Scraper Summary</div>
                  <p class="detail-text">{finalResult.scrapedSummary}</p>
                </div>
              {/if}

              {#if finalResult.marketingDescription}
                <div class="detail-block">
                  <div class="detail-key">Marketing Description</div>
                  <p class="detail-text">{finalResult.marketingDescription}</p>
                </div>
              {/if}

              {#if finalResult.iterationNotes?.length}
                <div class="detail-block">
                  <div class="detail-key">Iteration Notes</div>
                  {#each finalResult.iterationNotes as note}
                    <div class="note-row">· {note}</div>
                  {/each}
                </div>
              {/if}

              <div class="run-meta">
                <span class="meta-chip">run: {finalResult.runId}</span>
                <span class="meta-chip">{finalResult.workflow}</span>
                <span class="meta-chip blue">crewAI ✓</span>
              </div>
            </div>
          </details>
        {/if}

        <!-- ═══════════════════════════════════════════════════════════════ -->
        <!-- 4. AGENT PIPELINE TRACE — live timeline                        -->
        <!-- ═══════════════════════════════════════════════════════════════ -->
        {#if hasPipeline}
          <div class="pipeline-section">
            <div class="pipeline-header">
              <span class="section-icon">⚡</span>
              Agent Pipeline
              {#if isStreaming}
                <span class="live-badge">LIVE</span>
                <span class="live-sub">{runningStage ? runningStage.agent : '...'}</span>
              {:else}
                <span class="done-chip">{completedCount} / {totalCount} stages</span>
              {/if}
            </div>

            <div class="timeline">
              {#each stages as s, i}
                <div class="tl-row"
                  class:tl-running={s.status === 'running'}
                  class:tl-done={s.status === 'complete'}
                >
                  <div class="tl-track">
                    <div class="tl-icon">
                      {#if s.status === 'running'}
                        <span class="spinner-sm"></span>
                      {:else}
                        <span class="tl-check">✓</span>
                      {/if}
                    </div>
                    {#if i < stages.length - 1}
                      <div class="tl-line" class:tl-line-done={s.status === 'complete'}></div>
                    {/if}
                  </div>

                  <div class="tl-content">
                    <div class="tl-head">
                      <span class="tl-emoji">{getStageIcon(s.stage)}</span>
                      <div class="tl-names">
                        <span class="tl-label">{getStageLabel(s.stage)}</span>
                        <span class="tl-agent">{s.agent}</span>
                      </div>
                      {#if s.status === 'complete' && s.output}
                        <button class="expand-btn" on:click={() => toggleStage(s.stage)}>
                          {expandedStages[s.stage] ? '▲' : '▼'}
                        </button>
                      {/if}
                    </div>

                    {#if expandedStages[s.stage] && s.output}
                      <div class="tl-output">
                        <pre class="json-pre">{formatJson(s.output)}</pre>
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}

              {#if isStreaming}
                <div class="tl-pending">
                  <div class="tl-track">
                    <div class="tl-icon pending"><span class="pulse-dot"></span></div>
                  </div>
                  <div class="tl-content">
                    <div class="tl-head">
                      <span class="tl-pending-label">Waiting for next agent...</span>
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          </div>
        {/if}

      {/if}
    </div>
  </div>
</div>

<style>
  /* ── Page shell ─────────────────────────────────────────────────────────── */
  .page { display: flex; flex-direction: column; height: 100%; overflow-y: auto; background: var(--bg-base); }

  /* ── Top bar ────────────────────────────────────────────────────────────── */
  .topbar {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-surface);
    position: sticky; top: 0; z-index: 3; flex-shrink: 0;
  }
  .topbar-left h2 { font-family: var(--font-display); font-size: 22px; font-weight: 400; line-height: 1; }
  .subtitle { font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); letter-spacing: 0.07em; text-transform: uppercase; margin-top: 5px; }
  .topbar-right { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }

  .badge {
    font-family: var(--font-mono); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--amber); background: var(--amber-glow); border: 1px solid rgba(212,168,67,0.3); border-radius: 999px; padding: 3px 10px;
  }
  .badge.crew { color: var(--blue); background: var(--blue-dim); border-color: rgba(91,140,240,0.35); }
  .badge.live { color: #e05c5c; background: rgba(224,92,92,0.12); border-color: rgba(224,92,92,0.35); animation: pulse-badge 1.4s ease infinite; }
  .badge.done { color: #5bbf8a; background: rgba(91,191,138,0.12); border-color: rgba(91,191,138,0.35); }
  @keyframes pulse-badge { 0%,100%{opacity:1}50%{opacity:0.55} }

  /* ── Content grid ───────────────────────────────────────────────────────── */
  .content-grid { display: grid; grid-template-columns: 420px 1fr; gap: 16px; padding: 20px 24px 32px; align-items: start; }

  /* ── Form card ──────────────────────────────────────────────────────────── */
  .form-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 18px; position: sticky; top: 73px; }
  .section-head h3 { font-size: 14px; color: var(--text-primary); margin-bottom: 5px; }
  .section-head p  { font-size: 12px; color: var(--text-muted); line-height: 1.5; }
  .field-group { display: flex; flex-direction: column; gap: 7px; margin-top: 15px; }
  label { font-size: 10px; color: var(--text-secondary); font-family: var(--font-mono); letter-spacing: 0.07em; text-transform: uppercase; font-weight: 600; }
  .toggle-row { display: flex; gap: 6px; }
  .tog { flex:1; border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-muted); border-radius: var(--radius-sm); padding: 9px 10px; font-size: 13px; font-weight: 600; transition: all 0.13s; cursor: pointer; }
  .tog:hover { border-color: rgba(212,168,67,0.35); color: var(--text-secondary); }
  .tog.sel   { border-color: rgba(212,168,67,0.5); color: var(--amber); background: var(--amber-glow); }
  .counter { display: flex; align-items: center; gap: 8px; }
  .cnt-btn { width:32px; height:32px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg-elevated); color:var(--text-primary); font-size:18px; line-height:1; cursor:pointer; transition:all 0.13s; }
  .cnt-btn:hover:not(:disabled) { border-color:rgba(212,168,67,0.4); color:var(--amber); }
  .cnt-btn:disabled { opacity:0.4; cursor:not-allowed; }
  .cnt-val { min-width:46px; text-align:center; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg-elevated); padding:6px 8px; font-family:var(--font-mono); color:var(--text-primary); font-size:15px; font-weight:600; }
  .field-note { font-size:11px; color:var(--text-muted); }
  .text-input, .text-area { width:100%; background:var(--bg-elevated); border:1px solid var(--border); border-radius:var(--radius-sm); color:var(--text-primary); font-size:13px; padding:9px 11px; outline:none; transition:border-color 0.13s,box-shadow 0.13s; box-sizing:border-box; }
  .text-input:focus,.text-area:focus { border-color:var(--amber-dim); box-shadow:0 0 0 3px var(--amber-glow); }
  .text-input::placeholder,.text-area::placeholder { color:var(--text-muted); }
  .text-area { resize:vertical; min-height:100px; line-height:1.55; }
  .lookup-row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .lookup-input { flex:1; min-width:0; }
  .lookup-btn {
    padding:10px 14px; border:1px solid rgba(91,140,240,0.35); border-radius:var(--radius-sm);
    background:rgba(91,140,240,0.1); color:var(--blue); font-size:13px; font-weight:700;
    cursor:pointer; transition:all 0.13s;
  }
  .lookup-btn:hover:not(:disabled) { background:rgba(91,140,240,0.18); }
  .lookup-btn:disabled { opacity:0.5; cursor:not-allowed; }
  .btn-clear {
    padding:10px 12px; border:1px solid var(--border); border-radius:var(--radius-sm);
    background:var(--bg-elevated); color:var(--text-muted); font-size:12px; font-weight:600;
    cursor:pointer;
  }
  .btn-clear:hover { color:var(--text-primary); border-color:rgba(212,168,67,0.3); }
  .lookup-status { margin-top:8px; font-size:12px; color:var(--text-muted); line-height:1.5; }
  .item-card {
    margin-top:12px; padding:16px; border-radius:var(--radius-md);
    border:1px solid rgba(212,168,67,0.2); background:var(--bg-surface);
  }
  .item-card-header { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:12px; }
  .item-card-title { font-size:15px; font-weight:700; color:var(--text-primary); line-height:1.35; }
  .item-card-subtitle { margin-top:2px; font-size:11px; color:var(--text-muted); line-height:1.4; }
  .item-sk-badge {
    font-family:var(--font-mono); font-size:10px; color:var(--text-muted);
    background:var(--bg-elevated); border:1px solid var(--border); border-radius:999px;
    padding:2px 8px; white-space:nowrap;
  }
  .item-meta-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px; }
  .item-meta-cell { display:flex; flex-direction:column; gap:2px; min-width:0; }
  .item-meta-cell.wide { grid-column:1 / -1; }
  .meta-label {
    font-size:9.5px; font-weight:600; color:var(--text-muted); text-transform:uppercase;
    letter-spacing:0.08em; font-family:var(--font-mono);
  }
  .meta-val {
    font-size:13px;
    color:var(--text-primary);
    line-height:1.45;
    overflow-wrap:anywhere;
    word-break:break-word;
  }
  .meta-val.price { color:var(--amber); font-family:var(--font-mono); font-weight:600; }
  .meta-val.link { color:var(--blue); text-decoration:none; word-break:break-word; }
  .meta-val.link:hover { text-decoration:underline; }
  .meta-val.multiline { white-space:pre-wrap; line-height:1.6; color:var(--text-secondary); }
  @media (max-width: 900px) {
    .item-meta-grid { grid-template-columns: 1fr; }
  }
  .actions { margin-top:16px; }
  .run-btn { width:100%; padding:11px 14px; border:1px solid rgba(212,168,67,0.45); border-radius:var(--radius-sm); background:var(--amber-glow); color:var(--amber); font-size:13px; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; display:flex; justify-content:center; align-items:center; gap:7px; cursor:pointer; transition:all 0.13s; }
  .run-btn:hover:not(:disabled) { background:rgba(212,168,67,0.2); }
  .run-btn:disabled { opacity:0.5; cursor:not-allowed; }
  .error-banner { margin-top:10px; padding:9px 11px; background:var(--red-dim); border:1px solid rgba(224,92,92,0.35); border-radius:var(--radius-sm); color:var(--red); font-size:12px; }

  /* ── Output panel ───────────────────────────────────────────────────────── */
  .output-panel { display:flex; flex-direction:column; gap:14px; min-height:300px; }

  .empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px; padding:64px 32px; border:1px dashed var(--border); border-radius:var(--radius-md); text-align:center; }
  .empty-icon  { font-size:36px; }
  .empty-title { font-size:15px; color:var(--text-primary); font-weight:600; }
  .empty-sub   { font-size:12px; color:var(--text-muted); max-width:320px; line-height:1.6; }
  .sample-feeds { width:100%; margin-top:18px; text-align:left; }
  .sample-heading { margin-bottom:14px; }
  .sample-feed-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; width:100%; }
  .sample-feed-card {
    display:flex; flex-direction:column; gap:12px; padding:14px;
    background:var(--bg-elevated); border:1px solid var(--border); border-radius:var(--radius-md);
    text-align:left; width:100%; cursor:pointer; color:inherit; font:inherit;
  }
  .sample-feed-card:hover { border-color:rgba(212,168,67,0.32); }
  .sample-feed-card:focus-visible { outline:2px solid rgba(91,140,240,0.65); outline-offset:2px; }
  .sample-visual { display:flex; flex-direction:column; gap:10px; }
  .sample-visual-top { display:flex; align-items:center; justify-content:space-between; gap:10px; }
  .sample-brand { font-size:11px; font-family:var(--font-mono); font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--amber); }
  .sample-sku { font-size:10px; font-family:var(--font-mono); color:var(--text-muted); background:var(--bg-surface); border:1px solid var(--border); border-radius:999px; padding:2px 8px; white-space:nowrap; }
  .sample-image-block { width:100%; }
  .sample-image {
    width:100%;
    display:block;
    border-radius:var(--radius-md);
    border:1px solid rgba(91,140,240,0.28);
    aspect-ratio: 1 / 1;
    object-fit: cover;
    background: linear-gradient(180deg, rgba(15,18,28,0.92), rgba(8,10,16,0.96));
  }
  .sample-body { display:flex; flex-direction:column; gap:8px; }
  .sample-feed-category { font-size:10px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); }
  .sample-feed-title { margin:0; font-size:14px; line-height:1.4; color:var(--text-primary); }
  .sample-feed-theme { font-size:11.5px; line-height:1.5; color:var(--amber); font-weight:600; }
  .sample-feed-headline { margin:0; font-size:12px; line-height:1.55; color:var(--text-secondary); }
  .sample-feed-caption { margin:0; font-size:11.5px; line-height:1.55; color:var(--text-muted); }
  .sample-feed-meta { display:flex; flex-direction:column; gap:8px; padding-top:8px; border-top:1px solid var(--border); }
  .sample-feed-tags { display:flex; flex-wrap:wrap; gap:5px; }

  /* shared section label row */
  .section-label { display:flex; align-items:center; gap:8px; font-size:13px; font-weight:700; color:var(--text-primary); letter-spacing:0.03em; margin-bottom:12px; }
  .section-icon  { font-size:14px; }
  .post-count    { margin-left:auto; font-size:11px; font-family:var(--font-mono); color:var(--text-muted); font-weight:400; letter-spacing:0.06em; text-transform:uppercase; }

  /* ── Posts hero ──────────────────────────────────────────────────────────── */
  .posts-hero { background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-md); padding:18px; }
  .posts-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }
  .post-card { background:var(--bg-elevated); border:1px solid var(--border); border-radius:var(--radius-md); padding:16px; display:flex; flex-direction:column; gap:10px; transition:border-color 0.15s; }
  .post-card:hover { border-color:rgba(212,168,67,0.4); }
  .post-option { font-family:var(--font-mono); font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:var(--amber); background:var(--amber-glow); border:1px solid rgba(212,168,67,0.25); border-radius:999px; padding:2px 9px; align-self:flex-start; }
  .post-headline { font-size:16px; font-weight:700; color:var(--text-primary); line-height:1.3; }
  .post-caption  { font-size:12.5px; color:var(--text-secondary); line-height:1.65; white-space:pre-wrap; margin:0; }
  .post-tags { display:flex; flex-wrap:wrap; gap:5px; }
  .tag-pill { font-size:11px; color:var(--blue); background:var(--blue-dim); border:1px solid rgba(91,140,240,0.3); border-radius:999px; padding:2px 8px; font-family:var(--font-mono); }
  .post-footer { display:flex; flex-direction:column; gap:8px; padding-top:8px; border-top:1px solid var(--border); margin-top:auto; }
  .post-visual { font-size:11.5px; color:var(--text-muted); line-height:1.5; display:flex; gap:6px; }
  .footer-label { flex-shrink:0; }
  .post-cta-row { display:flex; }
  .cta-chip { font-size:12px; font-weight:700; color:var(--amber); background:var(--amber-glow); border:1px solid rgba(212,168,67,0.35); border-radius:var(--radius-sm); padding:5px 12px; letter-spacing:0.02em; }

  /* ── Visual generator card ───────────────────────────────────────────────── */
  .visual-gen-card {
    background: var(--bg-surface);
    border: 1px solid rgba(155,127,240,0.3);
    border-radius: var(--radius-md);
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .image-model-badge {
    margin-left: auto;
    font-size: 10px; font-family: var(--font-mono); font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: #9b7ff0; background: rgba(155,127,240,0.1); border: 1px solid rgba(155,127,240,0.35);
    border-radius: 999px; padding: 2px 9px;
  }
  .visual-intro { font-size: 12.5px; color: var(--text-muted); line-height: 1.6; margin: 0; }
  .prompt-field { display: flex; flex-direction: column; gap: 6px; }
  .prompt-label { font-size: 10px; font-family: var(--font-mono); text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); font-weight: 600; }
  .prompt-source { color: rgba(155,127,240,0.7); font-size: 9px; }
  .prompt-textarea {
    width: 100%; box-sizing: border-box;
    background: var(--bg-elevated); border: 1px solid var(--border);
    border-radius: var(--radius-sm); color: var(--text-primary);
    font-size: 12.5px; padding: 9px 11px; outline: none; resize: vertical;
    line-height: 1.55; font-family: inherit;
    transition: border-color 0.13s, box-shadow 0.13s;
  }
  .prompt-textarea:focus { border-color: rgba(155,127,240,0.5); box-shadow: 0 0 0 3px rgba(155,127,240,0.1); }
  .prompt-textarea::placeholder { color: var(--text-muted); }

  .gen-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .gen-btn {
    padding: 10px 20px;
    border: 1px solid rgba(155,127,240,0.45); border-radius: var(--radius-sm);
    background: rgba(155,127,240,0.1); color: #9b7ff0;
    font-size: 13px; font-weight: 700; letter-spacing: 0.04em;
    cursor: pointer; display: flex; align-items: center; gap: 7px;
    transition: all 0.13s;
  }
  .gen-btn:hover:not(:disabled) { background: rgba(155,127,240,0.18); }
  .gen-btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .gen-meta-row { display: flex; gap: 6px; }
  .gen-meta-pill {
    font-size: 10px; font-family: var(--font-mono); letter-spacing: 0.07em;
    color: var(--text-muted); border: 1px solid var(--border);
    border-radius: 999px; padding: 3px 9px; background: var(--bg-elevated);
  }

  .img-error { padding: 9px 11px; background: var(--red-dim); border: 1px solid rgba(224,92,92,0.35); border-radius: var(--radius-sm); color: var(--red); font-size: 12px; }

  /* Skeleton loader */
  .img-skeleton {
    position: relative; border-radius: var(--radius-md); overflow: hidden;
    border: 1px dashed rgba(155,127,240,0.3);
    min-height: 180px; display: flex; align-items: center; justify-content: center;
  }
  .skeleton-shimmer {
    position: absolute; inset: 0;
    background: linear-gradient(90deg, transparent 0%, rgba(155,127,240,0.06) 50%, transparent 100%);
    background-size: 200% 100%;
    animation: shimmer 1.6s ease infinite;
  }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
  .skeleton-label { position: relative; display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--text-muted); font-style: italic; }

  /* Generated image */
  .img-result { display: flex; flex-direction: column; gap: 10px; }
  .img-wrapper { position: relative; display: inline-block; width: 100%; max-width: 512px; }
  .gen-img { width: 100%; border-radius: var(--radius-md); border: 1px solid rgba(155,127,240,0.35); display: block; }
  .img-overlay {
    position: absolute; inset: 0; border-radius: var(--radius-md);
    background: rgba(0,0,0,0.55); opacity: 0; transition: opacity 0.2s;
    display: flex; align-items: center; justify-content: center;
  }
  .img-wrapper:hover .img-overlay { opacity: 1; }
  .img-fullsize-btn {
    color: #fff; font-size: 13px; font-weight: 600; text-decoration: none;
    border: 1px solid rgba(255,255,255,0.5); border-radius: var(--radius-sm);
    padding: 7px 16px; background: rgba(0,0,0,0.3);
    transition: background 0.13s;
  }
  .img-fullsize-btn:hover { background: rgba(0,0,0,0.5); }
  .img-meta { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; max-width: 512px; }
  .img-disclaimer { font-size: 11px; color: var(--text-muted); font-style: italic; line-height: 1.5; flex: 1; }
  .regen-btn {
    font-size: 11px; color: #9b7ff0; background: rgba(155,127,240,0.08);
    border: 1px solid rgba(155,127,240,0.3); border-radius: var(--radius-sm);
    padding: 5px 12px; cursor: pointer; white-space: nowrap;
    transition: all 0.13s; flex-shrink: 0;
  }
  .regen-btn:hover:not(:disabled) { background: rgba(155,127,240,0.16); }
  .regen-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ── Campaign details ────────────────────────────────────────────────────── */
  .campaign-details { background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-md); overflow:hidden; }
  .details-summary { display:flex; align-items:center; gap:8px; padding:13px 18px; font-size:13px; font-weight:700; color:var(--text-primary); cursor:pointer; list-style:none; user-select:none; transition:background 0.12s; }
  .details-summary:hover { background:var(--bg-elevated); }
  .details-summary::-webkit-details-marker { display:none; }
  .details-chevron { margin-left:auto; font-size:12px; color:var(--text-muted); }
  .details-body { padding:4px 18px 16px; display:flex; flex-direction:column; gap:12px; }
  .warnings-box { padding:10px 12px; background:rgba(212,168,67,0.08); border:1px solid rgba(212,168,67,0.3); border-radius:var(--radius-sm); }
  .warn-label { font-size:11px; font-weight:700; color:var(--amber); margin-bottom:6px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.07em; }
  .warn-row   { font-size:12px; color:var(--text-secondary); line-height:1.5; }
  .detail-block { display:flex; flex-direction:column; gap:5px; }
  .detail-key   { font-family:var(--font-mono); font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); font-weight:600; }
  .detail-text  { font-size:12.5px; color:var(--text-secondary); line-height:1.6; margin:0; }
  .note-row { font-size:12px; color:var(--text-secondary); line-height:1.5; }
  .run-meta { display:flex; gap:6px; flex-wrap:wrap; margin-top:4px; }
  .meta-chip { font-size:10px; font-family:var(--font-mono); letter-spacing:0.07em; text-transform:uppercase; color:var(--text-muted); border:1px solid var(--border); border-radius:999px; padding:3px 9px; background:var(--bg-elevated); }
  .meta-chip.blue { color:var(--blue); border-color:rgba(91,140,240,0.35); background:var(--blue-dim); }

  /* ── Pipeline trace ──────────────────────────────────────────────────────── */
  .pipeline-section { background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--radius-md); padding:18px; }
  .pipeline-header { display:flex; align-items:center; gap:8px; font-size:13px; font-weight:700; color:var(--text-primary); margin-bottom:16px; flex-wrap:wrap; }
  .live-badge { font-size:10px; font-family:var(--font-mono); font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#e05c5c; background:rgba(224,92,92,0.12); border:1px solid rgba(224,92,92,0.35); border-radius:999px; padding:2px 8px; animation:pulse-badge 1.4s ease infinite; }
  .live-sub   { font-size:12px; color:var(--text-muted); font-weight:400; }
  .done-chip  { font-size:10px; font-family:var(--font-mono); letter-spacing:0.07em; text-transform:uppercase; color:#5bbf8a; background:rgba(91,191,138,0.1); border:1px solid rgba(91,191,138,0.3); border-radius:999px; padding:2px 9px; }
  .timeline { display:flex; flex-direction:column; }
  .tl-row { display:flex; gap:12px; opacity:0.5; transition:opacity 0.2s; }
  .tl-row.tl-running,.tl-row.tl-done { opacity:1; }
  .tl-track { display:flex; flex-direction:column; align-items:center; flex-shrink:0; width:28px; }
  .tl-icon { width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:12px; background:var(--bg-elevated); border:1px solid var(--border); flex-shrink:0; }
  .tl-row.tl-running .tl-icon { border-color:rgba(212,168,67,0.5); background:var(--amber-glow); }
  .tl-row.tl-done    .tl-icon { border-color:rgba(91,191,138,0.5); background:rgba(91,191,138,0.1); }
  .tl-check { color:#5bbf8a; font-size:13px; font-weight:700; }
  .tl-line { width:1px; flex:1; min-height:10px; background:var(--border); margin:3px 0; }
  .tl-line.tl-line-done { background:rgba(91,191,138,0.4); }
  .tl-content { flex:1; padding-bottom:14px; }
  .tl-head { display:flex; align-items:center; gap:8px; min-height:28px; flex-wrap:wrap; }
  .tl-emoji { font-size:14px; flex-shrink:0; }
  .tl-names { display:flex; flex-direction:column; gap:1px; flex:1; }
  .tl-label { font-size:13px; font-weight:600; color:var(--text-primary); line-height:1.2; }
  .tl-agent { font-size:11px; color:var(--text-muted); font-family:var(--font-mono); }
  .expand-btn { margin-left:auto; font-size:10px; color:var(--text-muted); background:var(--bg-elevated); border:1px solid var(--border); border-radius:var(--radius-sm); padding:3px 8px; cursor:pointer; transition:all 0.12s; flex-shrink:0; }
  .expand-btn:hover { color:var(--amber); border-color:rgba(212,168,67,0.4); }
  .tl-output { margin-top:8px; }
  .json-pre { margin:0; white-space:pre-wrap; word-break:break-word; font-family:var(--font-mono); font-size:11px; line-height:1.5; color:var(--text-secondary); background:var(--bg-elevated); border:1px solid var(--border); border-radius:var(--radius-sm); padding:8px 10px; max-height:280px; overflow-y:auto; }
  .tl-pending { display:flex; gap:12px; opacity:0.45; }
  .tl-icon.pending { background:transparent; border-style:dashed; }
  .pulse-dot { width:6px; height:6px; border-radius:50%; background:var(--amber); animation:pulse-dot 1.2s ease infinite; }
  @keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.4;transform:scale(0.7)} }
  .tl-pending-label { font-size:12px; color:var(--text-muted); font-style:italic; line-height:28px; }

  /* ── Spinner ─────────────────────────────────────────────────────────────── */
  .spinner-sm { width:12px; height:12px; border:2px solid rgba(212,168,67,0.3); border-top-color:var(--amber); border-radius:50%; animation:spin 0.7s linear infinite; display:inline-block; flex-shrink:0; }
  @keyframes spin { to{transform:rotate(360deg)} }

  /* ── Responsive ──────────────────────────────────────────────────────────── */
  @media (max-width:1100px) { .content-grid{grid-template-columns:1fr} .form-card{position:static} }
  @media (max-width:640px)  { .topbar{padding:12px 16px;flex-direction:column;align-items:flex-start} .content-grid{padding:14px 16px 20px;gap:12px} .posts-grid{grid-template-columns:1fr} }
</style>

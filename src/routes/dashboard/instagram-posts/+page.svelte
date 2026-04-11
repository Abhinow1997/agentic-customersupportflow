<script>
  const FASTAPI = 'http://localhost:8000';

  let retrievalSetting = 'yes';
  let critiqueRounds = 2;
  let productLink = '';
  let methodSectionContent = '';
  let campaignCaption = '';
  let running = false;
  let errorMsg = '';
  let workflowResult = null;

  function setRetrieval(value) {
    retrievalSetting = value;
  }

  function decrementRounds() {
    critiqueRounds = Math.max(0, critiqueRounds - 1);
  }

  function incrementRounds() {
    critiqueRounds = Math.min(5, critiqueRounds + 1);
  }

  async function runWorkflow() {
    errorMsg = '';
    workflowResult = null;

    if (!productLink.trim() || !methodSectionContent.trim() || !campaignCaption.trim()) {
      errorMsg = 'Please fill Product Link, Method Section Content, and Campaign Caption before running.';
      return;
    }

    running = true;
    try {
      const res = await fetch(`${FASTAPI}/api/instagram-posts/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          retrievalEnabled: retrievalSetting === 'yes',
          critiqueRounds,
          productLink: productLink.trim(),
          methodSectionContent: methodSectionContent.trim(),
          productMarketingCampaignCaption: campaignCaption.trim(),
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail ?? `Workflow failed (HTTP ${res.status})`);
      }

      workflowResult = data;
    } catch (e) {
      errorMsg = e.message ?? 'Workflow request failed.';
    } finally {
      running = false;
    }
  }
</script>

<div class="page">
  <header class="topbar">
    <div class="topbar-left">
      <h2>Instagram Posts Creation</h2>
      <div class="subtitle">Independent crewAI marketing workflow configuration</div>
    </div>
    <div class="topbar-right">
      <span class="status-badge">Tooling</span>
      <span class="status-badge crew">crewAI</span>
    </div>
  </header>

  <section class="content-grid">
    <div class="form-card">
      <div class="section-head">
        <h3>Pipeline Settings</h3>
        <p>Provide campaign context for product-focused Instagram post generation.</p>
      </div>

      <div class="field-group">
        <label>Retrieval Settings</label>
        <div class="toggle-row" role="radiogroup" aria-label="Retrieval settings">
          <button
            class="toggle-btn"
            class:selected={retrievalSetting === 'yes'}
            on:click={() => setRetrieval('yes')}
            role="radio"
            aria-checked={retrievalSetting === 'yes'}
          >
            Yes
          </button>
          <button
            class="toggle-btn"
            class:selected={retrievalSetting === 'no'}
            on:click={() => setRetrieval('no')}
            role="radio"
            aria-checked={retrievalSetting === 'no'}
          >
            No
          </button>
        </div>
      </div>

      <div class="field-group">
        <label>Critique Rounds</label>
        <div class="counter">
          <button class="counter-btn" on:click={decrementRounds} disabled={critiqueRounds === 0}>-</button>
          <div class="counter-value">{critiqueRounds}</div>
          <button class="counter-btn" on:click={incrementRounds} disabled={critiqueRounds === 5}>+</button>
        </div>
        <div class="field-note">Maximum of 5 rounds</div>
      </div>

      <div class="field-group">
        <label for="product-link">Product Link</label>
        <input
          id="product-link"
          class="text-input"
          type="url"
          bind:value={productLink}
          placeholder="https://www.example.com/products/..."
        />
      </div>

      <div class="field-group">
        <label for="method-content">Method Section Content</label>
        <textarea
          id="method-content"
          class="text-area"
          bind:value={methodSectionContent}
          placeholder="Describe your core marketing idea for this product, target audience, tone, and desired creative direction."
          rows="7"
        ></textarea>
      </div>

      <div class="field-group">
        <label for="campaign-caption">Product Marketing Campaign Caption</label>
        <textarea
          id="campaign-caption"
          class="text-area"
          bind:value={campaignCaption}
          placeholder="Add the campaign-level caption direction or a draft caption for the post."
          rows="5"
        ></textarea>
      </div>

      <div class="actions">
        <button class="run-btn" on:click={runWorkflow} disabled={running}>
          {#if running}
            <span class="spinner-sm"></span>
            Running crewAI workflow...
          {:else}
            Run Instagram Workflow
          {/if}
        </button>
      </div>

      {#if errorMsg}
        <div class="error-banner">{errorMsg}</div>
      {/if}
    </div>

    <aside class="preview-card">
      <div class="section-head">
        <h3>Current Configuration</h3>
        <p>Live preview of the frontend inputs for the upcoming crewAI pipeline.</p>
      </div>

      <div class="preview-list">
        <div class="preview-row">
          <span class="preview-key">Retrieval</span>
          <span class="preview-val">{retrievalSetting === 'yes' ? 'Enabled' : 'Disabled'}</span>
        </div>
        <div class="preview-row">
          <span class="preview-key">Critique Rounds</span>
          <span class="preview-val">{critiqueRounds}</span>
        </div>
        <div class="preview-row">
          <span class="preview-key">Product Link</span>
          <span class="preview-val wrap">{productLink || 'Not provided yet'}</span>
        </div>
        <div class="preview-row column">
          <span class="preview-key">Method Section</span>
          <span class="preview-val wrap">{methodSectionContent || 'Not provided yet'}</span>
        </div>
        <div class="preview-row column">
          <span class="preview-key">Campaign Caption</span>
          <span class="preview-val wrap">{campaignCaption || 'Not provided yet'}</span>
        </div>
      </div>

      <div class="result-block">
        <div class="section-head">
          <h3>Workflow Output</h3>
          <p>Generated content from the new independent marketing flow.</p>
        </div>

        {#if workflowResult}
          <div class="meta-row">
            <span class="meta-pill">Workflow: {workflowResult.workflow}</span>
            <span class="meta-pill crew-flag">crewAI: {workflowResult.usedCrewAI ? 'Yes' : 'Fallback'}</span>
          </div>

          <div class="result-card">
            <div class="preview-key">Strategy Summary</div>
            <p class="result-text">{workflowResult.strategySummary}</p>
          </div>

          <div class="result-card">
            <div class="preview-key">Iteration Notes</div>
            {#if workflowResult.iterationNotes?.length}
              <div class="notes-list">
                {#each workflowResult.iterationNotes as note}
                  <div class="note-row">{note}</div>
                {/each}
              </div>
            {:else}
              <p class="result-text">No iteration notes returned.</p>
            {/if}
          </div>

          {#if workflowResult.posts?.length}
            {#each workflowResult.posts as post, index}
              <div class="result-card">
                <div class="result-head">Post Option {index + 1}</div>
                <div class="result-item"><span>Headline:</span> {post.headline}</div>
                <div class="result-item"><span>Caption:</span> {post.caption}</div>
                <div class="result-item"><span>Visual:</span> {post.visualDirection}</div>
                <div class="result-item"><span>CTA:</span> {post.cta}</div>
                <div class="result-item"><span>Hashtags:</span> {post.hashtags?.join(' ')}</div>
              </div>
            {/each}
          {/if}
        {:else}
          <div class="result-empty">
            Run the workflow to generate strategy and Instagram post options.
          </div>
        {/if}
      </div>
    </aside>
  </section>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
    background: var(--bg-base);
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-surface);
    position: sticky;
    top: 0;
    z-index: 3;
  }

  .topbar-left h2 {
    font-family: var(--font-display);
    font-size: 24px;
    line-height: 1;
    font-weight: 400;
  }

  .subtitle {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    letter-spacing: 0.07em;
    text-transform: uppercase;
    margin-top: 6px;
  }

  .topbar-right {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .status-badge {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--amber);
    background: var(--amber-glow);
    border: 1px solid rgba(212, 168, 67, 0.3);
    border-radius: 999px;
    padding: 3px 10px;
  }

  .status-badge.crew {
    color: var(--blue);
    background: var(--blue-dim);
    border-color: rgba(91, 140, 240, 0.35);
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    gap: 16px;
    padding: 20px 24px 24px;
    align-items: start;
  }

  .form-card,
  .preview-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 18px;
  }

  .section-head h3 {
    font-size: 15px;
    color: var(--text-primary);
    margin-bottom: 6px;
  }

  .section-head p {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 16px;
  }

  label {
    font-size: 11px;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    letter-spacing: 0.07em;
    text-transform: uppercase;
    font-weight: 600;
  }

  .toggle-row {
    display: flex;
    gap: 8px;
  }

  .toggle-btn {
    flex: 1;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    color: var(--text-muted);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    font-size: 13px;
    font-weight: 600;
    transition: all 0.15s;
  }

  .toggle-btn:hover {
    border-color: rgba(212, 168, 67, 0.35);
    color: var(--text-secondary);
  }

  .toggle-btn.selected {
    border-color: rgba(212, 168, 67, 0.5);
    color: var(--amber);
    background: var(--amber-glow);
  }

  .counter {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .counter-btn {
    width: 34px;
    height: 34px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    color: var(--text-primary);
    font-size: 18px;
    line-height: 1;
    transition: all 0.15s;
  }

  .counter-btn:hover:not(:disabled) {
    border-color: rgba(212, 168, 67, 0.4);
    color: var(--amber);
  }

  .counter-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .counter-value {
    min-width: 54px;
    text-align: center;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    padding: 7px 10px;
    font-family: var(--font-mono);
    color: var(--text-primary);
    font-size: 15px;
    font-weight: 600;
  }

  .field-note {
    font-size: 11px;
    color: var(--text-muted);
  }

  .text-input,
  .text-area {
    width: 100%;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-size: 13px;
    padding: 10px 12px;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .text-input:focus,
  .text-area:focus {
    border-color: var(--amber-dim);
    box-shadow: 0 0 0 3px var(--amber-glow);
  }

  .text-input::placeholder,
  .text-area::placeholder {
    color: var(--text-muted);
  }

  .text-area {
    resize: vertical;
    min-height: 120px;
    line-height: 1.6;
  }

  .actions {
    margin-top: 18px;
  }

  .run-btn {
    width: 100%;
    padding: 12px 14px;
    border: 1px solid rgba(212, 168, 67, 0.45);
    border-radius: var(--radius-sm);
    background: var(--amber-glow);
    color: var(--amber);
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    transition: all 0.15s;
  }

  .run-btn:hover:not(:disabled) {
    background: rgba(212, 168, 67, 0.2);
  }

  .run-btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .error-banner {
    margin-top: 12px;
    padding: 10px 12px;
    background: var(--red-dim);
    border: 1px solid rgba(224, 92, 92, 0.35);
    border-radius: var(--radius-sm);
    color: var(--red);
    font-size: 12px;
  }

  .preview-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 14px;
  }

  .preview-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
  }

  .preview-row.column {
    flex-direction: column;
    align-items: flex-start;
  }

  .preview-key {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    font-weight: 600;
    flex-shrink: 0;
  }

  .preview-val {
    color: var(--text-secondary);
    font-size: 12.5px;
    text-align: right;
  }

  .preview-val.wrap {
    text-align: left;
    width: 100%;
    word-break: break-word;
    white-space: pre-wrap;
  }

  .result-block {
    margin-top: 18px;
    border-top: 1px solid var(--border);
    padding-top: 14px;
  }

  .meta-row {
    margin-top: 10px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .meta-pill {
    font-size: 10px;
    font-family: var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 3px 9px;
    background: var(--bg-elevated);
  }

  .meta-pill.crew-flag {
    color: var(--blue);
    border-color: rgba(91, 140, 240, 0.35);
    background: var(--blue-dim);
  }

  .result-card {
    margin-top: 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .result-head {
    font-size: 12px;
    font-weight: 700;
    color: var(--amber);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .result-text {
    color: var(--text-secondary);
    font-size: 12.5px;
    line-height: 1.6;
  }

  .result-item {
    color: var(--text-secondary);
    font-size: 12px;
    line-height: 1.6;
    word-break: break-word;
  }

  .result-item span {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 6px;
  }

  .notes-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .note-row {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .result-empty {
    margin-top: 10px;
    padding: 10px 12px;
    border: 1px dashed var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: 12px;
  }

  .spinner-sm {
    width: 13px;
    height: 13px;
    border: 2px solid rgba(212, 168, 67, 0.3);
    border-top-color: var(--amber);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    display: inline-block;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }

    .topbar {
      flex-direction: column;
      align-items: flex-start;
    }

    .topbar-right {
      width: 100%;
      justify-content: flex-start;
    }
  }

  @media (max-width: 640px) {
    .topbar {
      padding: 14px 16px;
    }

    .content-grid {
      padding: 14px 16px 18px;
      gap: 12px;
    }

    .form-card,
    .preview-card {
      padding: 14px;
    }
  }
</style>

<script>
  import { goto } from '$app/navigation';
  import { session } from '$lib/stores.js';

  let email = '';
  let password = '';
  let error = '';
  let loading = false;

  // Demo credentials
  const VALID_AGENTS = [
    { email: 'daphne.k@arcella.com', password: 'arcella2025', name: 'Daphne K.', role: 'Senior Support Agent', avatar: 'DK' },
    { email: 'ravi.p@arcella.com', password: 'arcella2025', name: 'Ravi P.', role: 'Support Agent', avatar: 'RP' },
    { email: 'mei.l@arcella.com', password: 'arcella2025', name: 'Mei L.', role: 'Support Agent', avatar: 'ML' }
  ];

  async function handleLogin() {
    error = '';
    loading = true;
    await new Promise(r => setTimeout(r, 800));

    const agent = VALID_AGENTS.find(a => a.email === email && a.password === password);
    if (agent) {
      session.set({ name: agent.name, role: agent.role, avatar: agent.avatar, email: agent.email });
      goto('/dashboard');
    } else {
      error = 'Invalid credentials. Try daphne.k@arcella.com / arcella2025';
    }
    loading = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') handleLogin();
  }
</script>

<div class="login-page">
  <!-- Background grid -->
  <div class="grid-bg"></div>

  <!-- Left panel — branding -->
  <div class="brand-panel">
    <div class="brand-content">
      <div class="wordmark">
        <span class="arc">Arc</span><span class="ella">ella</span>
      </div>
      <div class="tagline">Customer Operations Platform</div>

      <div class="stats">
        <div class="stat">
          <span class="stat-number">6</span>
          <span class="stat-label">Open Tickets</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat">
          <span class="stat-number">2</span>
          <span class="stat-label">Critical</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat">
          <span class="stat-number">94%</span>
          <span class="stat-label">AI Coverage</span>
        </div>
      </div>

      <div class="feature-list">
        <div class="feature">
          <span class="feature-dot"></span>
          Multi-issue extraction & triage
        </div>
        <div class="feature">
          <span class="feature-dot"></span>
          Policy-grounded AI drafts
        </div>
        <div class="feature">
          <span class="feature-dot"></span>
          Supervisor verification engine
        </div>
        <div class="feature">
          <span class="feature-dot"></span>
          Human-in-the-loop review
        </div>
      </div>
    </div>

    <div class="brand-footer">
      Internal use only · Arcella Operations
    </div>
  </div>

  <!-- Right panel — login form -->
  <div class="form-panel">
    <div class="form-card">
      <div class="form-header">
        <div class="form-logo">A</div>
        <h1>Agent Sign In</h1>
        <p>Access your support queue</p>
      </div>

      <div class="form-body">
        <div class="field">
          <label for="email">Work Email</label>
          <input
            id="email"
            type="email"
            bind:value={email}
            on:keydown={handleKeydown}
            placeholder="name@arcella.com"
            autocomplete="email"
          />
        </div>

        <div class="field">
          <label for="password">Password</label>
          <input
            id="password"
            type="password"
            bind:value={password}
            on:keydown={handleKeydown}
            placeholder="••••••••"
            autocomplete="current-password"
          />
        </div>

        {#if error}
          <div class="error-msg">{error}</div>
        {/if}

        <button class="btn-login" on:click={handleLogin} disabled={loading}>
          {#if loading}
            <span class="spinner"></span> Signing in…
          {:else}
            Sign In
          {/if}
        </button>

        <div class="demo-hint">
          <strong>Demo:</strong> daphne.k@arcella.com · arcella2025
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .login-page {
    display: flex;
    height: 100vh;
    overflow: hidden;
    position: relative;
  }

  .grid-bg {
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(212,168,67,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(212,168,67,0.03) 1px, transparent 1px);
    background-size: 48px 48px;
    pointer-events: none;
  }

  /* Brand panel */
  .brand-panel {
    flex: 1;
    background: linear-gradient(145deg, #0f1117 0%, #12151e 60%, #0e1220 100%);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 56px 48px;
    position: relative;
    overflow: hidden;
  }

  .brand-panel::before {
    content: '';
    position: absolute;
    top: -100px;
    left: -100px;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(212,168,67,0.06) 0%, transparent 70%);
    pointer-events: none;
  }

  .brand-content {
    position: relative;
    z-index: 1;
  }

  .wordmark {
    font-family: var(--font-display);
    font-size: 52px;
    line-height: 1;
    margin-bottom: 8px;
    letter-spacing: -1px;
  }

  .arc { color: var(--text-primary); }
  .ella { color: var(--amber); }

  .tagline {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 56px;
  }

  .stats {
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 48px;
    padding: 24px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .stat { text-align: center; flex: 1; }
  .stat-number {
    display: block;
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 500;
    color: var(--amber);
    line-height: 1;
    margin-bottom: 4px;
  }
  .stat-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .stat-divider {
    width: 1px;
    height: 36px;
    background: var(--border);
  }

  .feature-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .feature {
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--text-secondary);
    font-size: 13.5px;
  }

  .feature-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--amber);
    flex-shrink: 0;
  }

  .brand-footer {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    letter-spacing: 0.05em;
  }

  /* Form panel */
  .form-panel {
    width: 440px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-base);
    padding: 40px;
  }

  .form-card {
    width: 100%;
    max-width: 360px;
  }

  .form-header {
    text-align: center;
    margin-bottom: 40px;
  }

  .form-logo {
    width: 44px;
    height: 44px;
    background: var(--amber-glow);
    border: 1px solid rgba(212,168,67,0.3);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-size: 22px;
    color: var(--amber);
    margin: 0 auto 20px;
  }

  .form-header h1 {
    font-family: var(--font-display);
    font-size: 26px;
    color: var(--text-primary);
    margin-bottom: 6px;
    font-weight: 400;
  }

  .form-header p {
    color: var(--text-muted);
    font-size: 13px;
  }

  .field {
    margin-bottom: 18px;
  }

  label {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 7px;
    font-weight: 500;
    letter-spacing: 0.03em;
  }

  input {
    width: 100%;
    padding: 11px 14px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-size: 14px;
    transition: border-color 0.15s, box-shadow 0.15s;
    outline: none;
  }

  input:focus {
    border-color: var(--amber-dim);
    box-shadow: 0 0 0 3px var(--amber-glow);
  }

  input::placeholder {
    color: var(--text-muted);
  }

  .error-msg {
    background: var(--red-dim);
    border: 1px solid rgba(224,92,92,0.3);
    color: var(--red);
    padding: 10px 13px;
    border-radius: var(--radius-sm);
    font-size: 12.5px;
    margin-bottom: 16px;
  }

  .btn-login {
    width: 100%;
    padding: 12px;
    background: var(--amber);
    color: #0c0e14;
    border: none;
    border-radius: var(--radius-sm);
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.04em;
    transition: background 0.15s, transform 0.1s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .btn-login:hover:not(:disabled) { background: #e0b84d; }
  .btn-login:active:not(:disabled) { transform: scale(0.99); }
  .btn-login:disabled { opacity: 0.6; cursor: not-allowed; }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(0,0,0,0.3);
    border-top-color: #000;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    display: inline-block;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .demo-hint {
    margin-top: 20px;
    text-align: center;
    font-size: 11.5px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    line-height: 1.7;
  }

  .demo-hint strong {
    color: var(--text-secondary);
  }
</style>

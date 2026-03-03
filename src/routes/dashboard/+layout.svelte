<script>
  import { goto } from '$app/navigation';
  import { session } from '$lib/stores.js';
  import { onMount } from 'svelte';

  onMount(() => {
    if (!$session) goto('/');
  });

  function logout() {
    session.set(null);
    goto('/');
  }
</script>

{#if $session}
<div class="app-shell">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-top">
      <div class="logo">
        <span class="arc">Arc</span><span class="ella">ella</span>
      </div>
      <div class="logo-sub">Support Ops</div>
    </div>

    <nav class="nav">
      <a href="/dashboard" class="nav-item active">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
        </svg>
        Ticket Queue
      </a>
      <a href="/dashboard" class="nav-item disabled">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
        </svg>
        Analytics
      </a>
      <a href="/dashboard" class="nav-item disabled">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
        </svg>
        Policy Library
      </a>
    </nav>

    <div class="sidebar-bottom">
      <div class="agent-card">
        <div class="agent-avatar">{$session.avatar}</div>
        <div class="agent-info">
          <div class="agent-name">{$session.name}</div>
          <div class="agent-role">{$session.role}</div>
        </div>
        <button class="logout-btn" on:click={logout} title="Sign out">
          <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
          </svg>
        </button>
      </div>
    </div>
  </aside>

  <!-- Main area -->
  <main class="main-content">
    <slot />
  </main>
</div>
{/if}

<style>
  .app-shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  .sidebar {
    width: 220px;
    background: var(--bg-surface);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .sidebar-top {
    padding: 24px 20px 20px;
    border-bottom: 1px solid var(--border-subtle);
    margin-bottom: 8px;
  }

  .logo {
    font-family: var(--font-display);
    font-size: 24px;
    line-height: 1;
    letter-spacing: -0.5px;
  }

  .arc { color: var(--text-primary); }
  .ella { color: var(--amber); }

  .logo-sub {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-top: 4px;
  }

  .nav {
    flex: 1;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    transition: background 0.1s, color 0.1s;
    text-decoration: none;
  }

  .nav-item:hover:not(.disabled) {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .nav-item.active {
    background: var(--amber-glow);
    color: var(--amber);
  }

  .nav-item.disabled {
    pointer-events: none;
    opacity: 0.4;
  }

  .sidebar-bottom {
    padding: 14px;
    border-top: 1px solid var(--border-subtle);
  }

  .agent-card {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .agent-avatar {
    width: 32px;
    height: 32px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 500;
    color: var(--amber);
    flex-shrink: 0;
  }

  .agent-info { flex: 1; min-width: 0; }
  .agent-name {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .agent-role {
    font-size: 10.5px;
    color: var(--text-muted);
  }

  .logout-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    padding: 4px;
    display: flex;
    border-radius: 4px;
    transition: color 0.15s, background 0.15s;
  }

  .logout-btn:hover {
    color: var(--red);
    background: var(--red-dim);
  }

  .main-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
</style>

<script>
  const githubRepo = 'https://github.com/abhinow1997/agentic-customersupportflow';
  const githubReadme = `${githubRepo}/blob/main/README.md`;
  const githubBackendReadme = `${githubRepo}/blob/main/backend/README.md`;

  const keyFeatures = [
    {
      title: 'Agentic customer support flow',
      description:
        'Routes issues through a multi-agent pipeline that can triage, verify, summarize, and draft responses with human-in-the-loop control.'
    },
    {
      title: 'Instagram campaign generator',
      description:
        'Turns a product lookup plus creative direction into a structured Instagram campaign, complete with live workflow output and image generation.'
    },
    {
      title: 'Snowflake-backed item lookup',
      description:
        'Pulls live item details from the product dataset so the workflow can ground marketing content in real catalog data.'
    },
    {
      title: 'Streamed agent output',
      description:
        'Exposes the Instagram workflow as a streaming experience so users can see each agent stage as it completes.'
    }
  ];

  const docs = [
    {
      title: 'Project README',
      href: githubReadme,
      description: 'High-level project overview, setup notes, and implementation summary.'
    },
    {
      title: 'Backend README',
      href: githubBackendReadme,
      description: 'Backend-specific setup, workflow behavior, API notes, and endpoint reference.'
    },
    {
      title: 'Architecture Snapshot',
      href: '#architecture',
      description: 'A quick look at the major systems and how they fit together.'
    }
  ];

  const architectureFlow = [
    {
      title: '1. User starts in the frontend',
      description:
        'The SvelteKit app provides the login screen, dashboard, return workflow, enquiry flow, and Instagram workflow entry points.'
    },
    {
      title: '2. Frontend calls FastAPI',
      description:
        'Each major action triggers a backend route for tickets, analytics, items, enquiries, or campaign generation.'
    },
    {
      title: '3. FastAPI talks to Snowflake and agents',
      description:
        'The backend reads operational data from Snowflake and coordinates the agent flows that analyze, validate, and draft responses.'
    },
    {
      title: '4. Agent output returns to the UI',
      description:
        'Draft replies, summaries, status updates, and streamed content are sent back for review in the dashboard.'
    }
  ];
</script>

<svelte:head>
  <title>Project Showcase</title>
  <meta
    name="description"
    content="A simple showcase page for the agentic customer support and Instagram marketing project."
  />
</svelte:head>

<div class="showcase-shell">
  <div class="backdrop backdrop-one"></div>
  <div class="backdrop backdrop-two"></div>

  <section class="hero">
    <div class="eyebrow">Assignment Final Project</div>
    <h1>Agentic Customer Support Flow</h1>
    <p class="lead">
      A full-stack demo that blends customer support automation, product lookup, and Instagram
      campaign generation into one agentic workflow.
    </p>

    <div class="hero-actions">
      <a class="primary-btn" href={githubRepo} target="_blank" rel="noreferrer">View GitHub Repository</a>
      <a class="secondary-btn" href={githubReadme} target="_blank" rel="noreferrer">Read Documentation</a>
    </div>

    <div class="hero-stats">
      <div class="stat">
        <span>2</span>
        <p>main experiences: support flow and Instagram marketing flow</p>
      </div>
      <div class="stat">
        <span>FastAPI</span>
        <p>backend routes with streamed agent output and product lookup</p>
      </div>
      <div class="stat">
        <span>Svelte</span>
        <p>interactive frontend with a clean dashboard-style interface</p>
      </div>
    </div>
  </section>

  <section class="section" id="features">
    <div class="section-head">
      <div class="section-label">Key Features</div>
      <h2>What the project demonstrates</h2>
    </div>

    <div class="feature-grid">
      {#each keyFeatures as feature}
        <article class="feature-card">
          <h3>{feature.title}</h3>
          <p>{feature.description}</p>
        </article>
      {/each}
    </div>
  </section>

  <section class="section architecture-section" id="architecture">
    <div class="section-head">
      <div class="section-label">Architecture Flow</div>
      <h2>How the system moves data end to end</h2>
    </div>

    <div class="architecture-grid">
      <div class="diagram-card">
        <img
          src="/images/mermaid-architecture-diagram.svg"
          alt="Architecture flow diagram showing the Svelte frontend, FastAPI backend, Snowflake, and agent workflows"
        />
      </div>

      <div class="flow-list">
        {#each architectureFlow as step}
          <article class="flow-card">
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="section split" id="documentation">
    <div>
      <div class="section-label">Documentation</div>
      <h2>Project docs and source references</h2>
      <p class="section-copy">
        Use the links below to jump into the repository documentation and the backend entrypoint
        that powers the app.
      </p>
    </div>

    <div class="doc-list">
    {#each docs as doc}
      <a class="doc-card" href={doc.href} target={doc.href.startsWith('http') ? '_blank' : undefined} rel={doc.href.startsWith('http') ? 'noreferrer' : undefined}>
        <div>
          <h3>{doc.title}</h3>
          <p>{doc.description}</p>
        </div>
        <span>{doc.href.startsWith('#') ? 'Jump' : 'Open'}</span>
      </a>
      {/each}
    </div>
  </section>
</div>

<style>
  :global(body) {
    margin: 0;
    background:
      radial-gradient(circle at top left, rgba(255, 194, 32, 0.14), transparent 30%),
      radial-gradient(circle at top right, rgba(0, 113, 206, 0.18), transparent 34%),
      linear-gradient(180deg, #07111f 0%, #0b1726 45%, #0e1320 100%);
  }

  .showcase-shell {
    position: relative;
    min-height: 100vh;
    padding: 32px;
    color: var(--text-primary);
    overflow: hidden;
  }

  .backdrop {
    position: absolute;
    border-radius: 999px;
    filter: blur(60px);
    pointer-events: none;
    opacity: 0.7;
  }

  .backdrop-one {
    width: 360px;
    height: 360px;
    right: -80px;
    top: 40px;
    background: rgba(255, 194, 32, 0.16);
  }

  .backdrop-two {
    width: 420px;
    height: 420px;
    left: -120px;
    bottom: -120px;
    background: rgba(0, 113, 206, 0.18);
  }

  .hero,
  .section {
    position: relative;
    z-index: 1;
    max-width: 1120px;
    margin: 0 auto;
  }

  .hero {
    padding: 72px 0 32px;
  }

  .eyebrow,
  .section-label {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #9cc7ff;
    margin-bottom: 14px;
  }

  h1 {
    margin: 0;
    max-width: 840px;
    font-family: var(--font-display);
    font-size: clamp(44px, 8vw, 84px);
    line-height: 0.96;
    letter-spacing: -0.05em;
  }

  .lead {
    max-width: 760px;
    margin: 22px 0 0;
    font-size: clamp(17px, 2vw, 22px);
    line-height: 1.7;
    color: var(--text-secondary);
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 32px;
  }

  .primary-btn,
  .secondary-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 46px;
    padding: 0 18px;
    border-radius: 999px;
    text-decoration: none;
    font-weight: 700;
    transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
  }

  .primary-btn {
    background: linear-gradient(135deg, #ffc220, #ffdd72);
    color: #111827;
  }

  .secondary-btn {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border);
    color: var(--text-primary);
  }

  .primary-btn:hover,
  .secondary-btn:hover {
    transform: translateY(-1px);
  }

  .hero-stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin-top: 34px;
  }

  .stat,
  .feature-card,
  .doc-card {
    background: rgba(9, 16, 29, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 22px;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
    backdrop-filter: blur(12px);
  }

  .stat {
    padding: 18px;
  }

  .stat span {
    display: block;
    margin-bottom: 10px;
    font-family: var(--font-display);
    font-size: 22px;
    color: #ffc220;
  }

  .stat p,
  .feature-card p,
  .doc-card p,
  .section-copy {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.65;
  }

  .section {
    padding: 34px 0;
  }

  .section-head {
    margin-bottom: 18px;
  }

  h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(28px, 4vw, 42px);
    letter-spacing: -0.04em;
  }

  .feature-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
  }

  .architecture-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
    gap: 16px;
    align-items: start;
  }

  .feature-card {
    padding: 22px;
  }

  .diagram-card,
  .flow-card {
    background: rgba(9, 16, 29, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 22px;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
    backdrop-filter: blur(12px);
  }

  .diagram-card {
    padding: 18px;
  }

  .diagram-card img {
    display: block;
    width: 100%;
    height: auto;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.02);
  }

  .flow-list {
    display: grid;
    gap: 12px;
  }

  .flow-card {
    padding: 18px 20px;
  }

  .flow-card h3 {
    margin: 0 0 8px;
    font-size: 17px;
    color: var(--text-primary);
  }

  .flow-card p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.65;
  }

  .feature-card h3,
  .doc-card h3 {
    margin: 0 0 10px;
    font-size: 18px;
    color: var(--text-primary);
  }

  .split {
    display: grid;
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
    gap: 18px;
    align-items: start;
  }

  .doc-list {
    display: grid;
    gap: 12px;
  }

  .doc-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 18px 20px;
    color: inherit;
    text-decoration: none;
  }

  .doc-card span {
    flex-shrink: 0;
    font-size: 12px;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #ffc220;
  }

  @media (max-width: 900px) {
    .showcase-shell {
      padding: 20px;
    }

    .hero-stats,
    .feature-grid,
    .split,
    .architecture-grid {
      grid-template-columns: 1fr;
    }

    .hero {
      padding-top: 48px;
    }
  }
</style>

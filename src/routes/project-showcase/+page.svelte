<script>
  const githubRepo = 'https://github.com/abhinow1997/agentic-customersupportflow';
  const githubReadme = `${githubRepo}/blob/main/README.md`;
  const githubBackendReadme = `${githubRepo}/blob/main/backend/README.md`;

  const keyFeatures = [
    {
      title: 'Instagram content generation flow',
      description:
        'Takes a product item, campaign direction, and user requirements through a validator, summarizer, content generator, critique loop, and visualizer.'
    },
    {
      title: 'Create return ticket flow',
      description:
        'Looks up the customer and product context, checks the seven return guardrails, and scores the return with policy-backed confidence.'
    },
    {
      title: 'Customer enquiry workflow',
      description:
        'Classifies email, text, or voicemail enquiries into seven categories, routes them to the right Snowflake procedure, and drafts a grounded response.'
    },
    {
      title: 'Support operations dashboard',
      description:
        'Supports ticket creation, enquiries, return triage, and analytics in the same application.'
    },
    {
      title: 'Snowflake-backed item lookup',
      description:
        'Pulls live item metadata from Snowflake so the Instagram workflow can validate the item before generating content.'
    },
    {
      title: 'Agentic iteration loop',
      description:
        'Lets the content agent and critique agent work back and forth for a defined number of rounds before the final visual is created.'
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
        'The SvelteKit app lets the user open the Instagram page, look up an item, and enter the campaign details.'
    },
    {
      title: '2. Frontend sends campaign inputs',
      description:
        'The item SK, method section content, and campaign caption are sent to the Instagram workflow endpoint.'
    },
    {
      title: '3. Validator and summarizer prepare the brief',
      description:
        'The validator agent checks item availability and metadata in Snowflake, then the summarizing agent merges those facts with the user requirements.'
    },
    {
      title: '4. Content, critique, and visual generation',
      description:
        'The content agent drafts the campaign, the critique agent improves it in a loop, and the visualizer generates the final image prompt or visual asset.'
    }
  ];

  const returnFlow = [
    {
      title: '1. User submits a return claim',
      description:
        'The agent starts with the customer claim, the item being returned, packaging condition, return quantity, and customer remarks.'
    },
    {
      title: '2. Snowflake lookup grounds the case',
      description:
        'The backend looks up the customer’s recent purchase and item metadata from Snowflake so the assessment starts from real transaction data.'
    },
    {
      title: '3. Researcher agent checks seven guardrails',
      description:
        'The researcher agent evaluates the claim against seven policy checks, asking follow-up questions when the evidence is incomplete.'
    },
    {
      title: '4. Policy validation adjusts confidence',
      description:
        'Each answer is validated against policy logic, and the result is converted into a confidence score that reflects how strong the return case is.'
    }
  ];

  const returnFlowMermaid = `flowchart TD
  U[Customer / Agent] --> F[Create Return Ticket Page]
  F --> C[Claim Details]
  F --> R[Recent Purchase Lookup]
  R --> S[(Snowflake Purchase + Item Data)]
  C --> RE[Researcher Agent]
  S --> RE
  RE --> P[Policy Agent]
  P --> RE
  RE --> SCO[Confidence Score]
  SCO --> O[Approve, Deny, or Review]`;

  const enquiryFlow = [
    {
      title: '1. User submits an enquiry',
      description:
        'The user provides an email, text message, or voicemail transcript describing the problem or question.'
    },
    {
      title: '2. Voicemail is transcribed when needed',
      description:
        'If the input is audio, the system transcribes it to text so the rest of the workflow can treat every enquiry in a consistent format.'
    },
    {
      title: '3. The enquiry is classified',
      description:
        'The response agent identifies one of the seven supported enquiry categories and determines which source-of-truth procedure should be used.'
    },
    {
      title: '4. Snowflake procedure and draft response',
      description:
        'The matching Snowflake procedure returns the validation data, and the agent uses it to generate a grounded draft response for review.'
    }
  ];

  const enquiryFlowMermaid = `flowchart TD
  U[User] --> F[Enquiry Input]
  F --> T[Voicemail Transcription]
  T --> X[Text Enquiry]
  X --> CL[Classify into 7 Categories]
  CL --> P[Select Snowflake Procedure]
  P --> S[(Snowflake Source of Truth)]
  S --> D[Draft Response Agent]
  D --> O[Reviewable Reply for the User]`;
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
      A full-stack demo that blends customer enquiries, return assessment, and Instagram content
      generation into one agentic application.
    </p>

    <div class="hero-actions">
      <a class="primary-btn" href={githubRepo} target="_blank" rel="noreferrer">View GitHub Repository</a>
      <a class="secondary-btn" href={githubReadme} target="_blank" rel="noreferrer">Read Documentation</a>
    </div>

    <div class="hero-stats">
      <div class="stat">
        <span>3</span>
        <p>main experiences: enquiries, return flow, and Instagram marketing flow</p>
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
      <h2>What the Instagram flow demonstrates</h2>
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
      <div class="section-label">Instagram Agentic Pipeline</div>
      <h2>The Instagram agentic campaign pipeline</h2>
    </div>

    <div class="architecture-grid">
      <div class="diagram-card diagram-text">
        <div class="diagram-title">Mermaid diagram</div>
        <img
          src="/images/mermaid-diagram-instaflow.svg"
          alt="Instagram agentic pipeline diagram showing item lookup, validator, summarizer, content generation, critique, and visualizer steps"
        />
      </div>

      <div class="flow-list">
        {#each architectureFlow as step}
          <article class="flow-card">
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </article>
        {/each}

        <article class="flow-card highlight-card">
          <h3>Why this flow matters</h3>
          <p>
            The user only provides a product item and campaign direction. The system then grounds
            the campaign in catalog data, refines the copy through critique cycles, and finishes
            with a visual prompt for the final post concept.
          </p>
        </article>
      </div>
    </div>
  </section>

  <section class="section architecture-section">
    <div class="section-head">
      <div class="section-label">Create Return Ticket</div>
      <h2>The return assessment pipeline</h2>
    </div>

    <div class="architecture-grid">
      <div class="diagram-card diagram-text">
        <div class="diagram-title">Mermaid diagram</div>
        <img
          src="/images/mermaid-diagram-returnticket.svg"
          alt="Return assessment pipeline diagram showing claim details, Snowflake lookup, researcher agent, policy agent, and confidence score"
        />
      </div>

      <div class="flow-list">
        {#each returnFlow as step}
          <article class="flow-card">
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </article>
        {/each}

        <article class="flow-card highlight-card">
          <h3>Why this flow matters</h3>
          <p>
            This pipeline reduces guesswork by grounding the claim in purchase history, checking
            policy guardrails, and turning the result into a confidence-driven recommendation for
            approve, deny, or manual review.
          </p>
        </article>
      </div>
    </div>
  </section>

  <section class="section architecture-section">
    <div class="section-head">
      <div class="section-label">Customer Enquiries</div>
      <h2>The enquiry classification and reply pipeline</h2>
    </div>

    <div class="architecture-grid">
      <div class="diagram-card diagram-text">
        <div class="diagram-title">Mermaid diagram</div>
        <img
          src="/images/mermaid-diagram-enquiry.svg"
          alt="Enquiry classification pipeline diagram showing transcription, classification into seven categories, Snowflake procedure selection, and draft response generation"
        />
      </div>

      <div class="flow-list">
        {#each enquiryFlow as step}
          <article class="flow-card">
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </article>
        {/each}

        <article class="flow-card highlight-card">
          <h3>Why this flow matters</h3>
          <p>
            This workflow turns unstructured enquiries into a structured support process by
            classifying the issue, selecting the correct Snowflake-backed procedure, and drafting a
            response that stays grounded in source-of-truth data.
          </p>
        </article>
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

  .diagram-text pre {
    margin: 0;
    padding: 18px;
    overflow: auto;
    background: rgba(5, 10, 18, 0.74);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    color: #d7e3ff;
    font-size: 12px;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .diagram-title {
    margin: 0 0 12px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #9cc7ff;
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

  .highlight-card {
    border-color: rgba(255, 194, 32, 0.22);
    background: linear-gradient(180deg, rgba(18, 23, 34, 0.82), rgba(9, 16, 29, 0.72));
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

// src/lib/stores.js
import { writable, derived } from 'svelte/store'; // derived still used for selectedTicket
import { MOCK_TICKETS } from './data.js';

// Auth store — persisted to sessionStorage so HMR reloads and refreshes don't wipe the login
function makePersistedSession() {
  let initial = null;
  if (typeof sessionStorage !== 'undefined') {
    try { initial = JSON.parse(sessionStorage.getItem('arcella_session')); } catch {}
  }
  const store = writable(initial);
  store.subscribe(val => {
    if (typeof sessionStorage !== 'undefined') {
      if (val) sessionStorage.setItem('arcella_session', JSON.stringify(val));
      else     sessionStorage.removeItem('arcella_session');
    }
  });
  return store;
}
export const session = makePersistedSession();

// FastAPI base URL — all data + AI calls go through FastAPI
const FASTAPI_URL = 'http://localhost:8000';

// Tickets — loaded from FastAPI
export const tickets        = writable([]);
export const ticketsLoading = writable(false);
export const ticketsError   = writable('');

export async function loadTickets() {
  ticketsLoading.set(true);
  ticketsError.set('');
  try {
    const res = await fetch(`${FASTAPI_URL}/api/tickets?limit=50`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();

    if (Array.isArray(data.tickets) && data.tickets.length > 0) {
      tickets.set(data.tickets);
    } else {
      // Snowflake returned 0 rows — fall back to demo data so the UI is never empty
      console.warn('[loadTickets] Snowflake returned 0 tickets, using mock data');
      tickets.set(MOCK_TICKETS);
      ticketsError.set('Snowflake returned 0 rows — showing demo data');
    }
  } catch (e) {
    console.error('[loadTickets] Failed:', e);
    // Fall back to mock data so agents always see something
    tickets.set(MOCK_TICKETS);
    ticketsError.set(`Live data unavailable (${e.message}) — showing demo data`);
  } finally {
    ticketsLoading.set(false);
  }
}

// Selected ticket
export const selectedTicketId = writable(null);

export const selectedTicket = derived(
  [tickets, selectedTicketId],
  ([$tickets, $id]) => $tickets.find(t => t.id === $id) || null
);

// Filters
export const filters = writable({ status: 'all', priority: 'all', search: '' });

export async function analyzeTicket(ticket) {
  const payload = {
    ticket_id:    ticket.id,
    returnReason: ticket.returnReason ?? '',
    returnAmt:    ticket.returnAmt    ?? '0',
    netLoss:      ticket.netLoss      ?? '0',
    customer: {
      name:   ticket.customer?.name   ?? '',
      email:  ticket.customer?.email  ?? '',
      tier:   ticket.customer?.tier   ?? 'Bronze',
      ltv:    ticket.customer?.ltv    ?? '0',
      orders: ticket.customer?.orders ?? 0,
    },
    item: {
      name:      ticket.item?.name      ?? '',
      category:  ticket.item?.category  ?? '',
      class:     ticket.item?.class     ?? '',
      price:     ticket.item?.price     ?? '0',
      returnQty: ticket.item?.returnQty ?? 1,
    },
  };

  const res = await fetch(`${FASTAPI_URL}/api/analyze/ticket`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  return await res.json(); // { ticket_id, triage: { action, actionLabel, ... } }
}

// Actions
export async function updateTicketStatus(id, status, resolution = null) {
  console.log('[updateTicketStatus] Called with:', { id, status, resolution });

  // Optimistically update local state immediately
  tickets.update(all => all.map(t =>
    t.id === id ? { ...t, status, ...(resolution ? { resolution } : {}) } : t
  ));

  // Persist to Snowflake
  try {
    const payload = { id, status, resolution };
    console.log('[updateTicketStatus] Sending PATCH:', JSON.stringify(payload));

    const res = await fetch(`${FASTAPI_URL}/api/tickets`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      console.error('[updateTicketStatus] PATCH failed:', res.status, data);
    } else {
      console.log('[updateTicketStatus] PATCH success:', data);
    }
  } catch (e) {
    console.error('[updateTicketStatus] Network error:', e);
  }
}
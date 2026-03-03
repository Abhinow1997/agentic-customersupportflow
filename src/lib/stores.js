// src/lib/stores.js
import { writable, derived } from 'svelte/store';

// Auth store
export const session = writable(null);

// Tickets — loaded from /api/tickets
export const tickets        = writable([]);
export const ticketsLoading = writable(false);
export const ticketsError   = writable('');

export async function loadTickets() {
  ticketsLoading.set(true);
  ticketsError.set('');
  try {
    const res = await fetch('/api/tickets?limit=50');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    tickets.set(data.tickets);
  } catch (e) {
    ticketsError.set(e.message);
    console.error('Failed to load tickets:', e);
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

export const filteredTickets = derived([tickets, filters], ([$tickets, $f]) => {
  return $tickets.filter(t => {
    if ($f.status   !== 'all' && t.status   !== $f.status)   return false;
    if ($f.priority !== 'all' && t.priority !== $f.priority) return false;
    if ($f.search) {
      const q = $f.search.toLowerCase();
      if (!t.subject.toLowerCase().includes(q) &&
          !t.customer.name.toLowerCase().includes(q) &&
          !t.id.toLowerCase().includes(q)) return false;
    }
    return true;
  });
});

// Actions
export function updateTicketStatus(id, status) {
  tickets.update(all => all.map(t => t.id === id ? { ...t, status } : t));
}
/**
 * API client for the REAL CubeSat backend proxy.
 *
 * In dev:  Vite proxy forwards /api → localhost:8000 (no env var needed)
 * In prod: VITE_API_URL is set at build time (e.g. https://real-cubesat-api.onrender.com)
 */

const BASE = import.meta.env.VITE_API_URL || '';

async function get(path, params = {}) {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, v);
    }
  });

  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ── Telemetry data ─────────────────────────────────────────────────

export async function fetchHealth({ start, end, fields, sources, limit } = {}) {
  return get('/api/health', {
    start,
    end,
    fields: fields?.join(','),
    sources: sources?.join(','),
    limit,
  });
}

export async function fetchTime({ start, end, fields, sources, limit } = {}) {
  return get('/api/time', {
    start,
    end,
    fields: fields?.join(','),
    sources: sources?.join(','),
    limit,
  });
}

// ── Field metadata ─────────────────────────────────────────────────

export async function fetchHealthFields() {
  return get('/api/fields/health');
}

export async function fetchTimeFields() {
  return get('/api/fields/time');
}

// ── Latest values + stats ──────────────────────────────────────────

export async function fetchLatest({ sources } = {}) {
  return get('/api/latest', { sources: sources?.join(',') });
}

export async function fetchStats({ start, end, sources } = {}) {
  return get('/api/stats', {
    start,
    end,
    sources: sources?.join(','),
  });
}

// ── JHUAPL Level-1 data ────────────────────────────────────────────

export async function fetchJHUAPLDatasets({ start, end } = {}) {
  return get('/api/jhuapl/datasets', { start, end });
}

export async function fetchJHUAPLFields({ dataset, start, end } = {}) {
  return get('/api/jhuapl/fields', { dataset, start, end });
}

export async function fetchJHUAPLData({ dataset, start, end, fields, limit } = {}) {
  return get('/api/jhuapl/data', {
    dataset,
    start,
    end,
    fields: fields?.join(','),
    limit,
  });
}

// ── Cache control ──────────────────────────────────────────────────

export async function clearCache() {
  const res = await fetch(`${BASE}/api/cache/clear`, { method: 'POST' });
  return res.json();
}
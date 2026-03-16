import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Satellite, RefreshCw, ChevronLeft, ChevronRight, Filter } from 'lucide-react';
import Dashboard from './components/Dashboard';
import FieldSelector from './components/FieldSelector';
import { fetchJHUAPLDatasets, fetchJHUAPLFields, clearCache } from './api';

function daysAgo(n) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}
const today = () => new Date().toISOString().slice(0, 10);

function useDebounce(value, delay = 400) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function formatUTCShort(ms) {
  const d = new Date(ms);
  const mon = d.toLocaleString('en', { month: 'short', timeZone: 'UTC' });
  const day = d.getUTCDate();
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${mon} ${day} ${hh}:${mm}`;
}

const WINDOW_OPTIONS = [
  { label: 'Full Range', value: 0 },
  { label: '1 Hour', value: 60 },
  { label: '1 Orbit (~92 min)', value: 92 },
  { label: '3 Hours', value: 180 },
];

export default function App() {
  const [start, setStart] = useState(daysAgo(14));
  const [end, setEnd] = useState(today());

  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [jhuaplFields, setJHUAPLFields] = useState([]);
  const [selectedFields, setSelectedFields] = useState([]);

  const [windowMinutes, setWindowMinutes] = useState(0);
  const [windowStart, setWindowStart] = useState(null);
  const [dataRange, setDataRange] = useState(null);

  const [lMin, setLMin] = useState('');
  const [lMax, setLMax] = useState('');
  const [latMin, setLatMin] = useState('');
  const [latMax, setLatMax] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const debouncedStart = useDebounce(start);
  const debouncedEnd = useDebounce(end);

  const lRange = useMemo(() => {
    const mn = parseFloat(lMin), mx = parseFloat(lMax);
    if (!isNaN(mn) && !isNaN(mx) && mn < mx) return [mn, mx];
    if (!isNaN(mn)) return [mn, 1000];
    if (!isNaN(mx)) return [0, mx];
    return null;
  }, [lMin, lMax]);

  const latRange = useMemo(() => {
    const mn = parseFloat(latMin), mx = parseFloat(latMax);
    if (!isNaN(mn) && !isNaN(mx)) return [mn, mx];
    return null;
  }, [latMin, latMax]);

  // Load dataset listing
  useEffect(() => {
    let cancelled = false;
    fetchJHUAPLDatasets({ start: debouncedStart, end: debouncedEnd })
      .then(res => {
        if (cancelled) return;
        const ds = res.datasets || [];
        setDatasets(ds);
        if (ds.length && !selectedDataset) {
          setSelectedDataset(ds[0].name);
        }
      })
      .catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [debouncedStart, debouncedEnd, refreshKey]);

  // Load fields when dataset changes
  useEffect(() => {
    if (!selectedDataset) return;
    let cancelled = false;
    fetchJHUAPLFields({ dataset: selectedDataset, start: debouncedStart, end: debouncedEnd })
      .then(res => {
        if (cancelled) return;
        const fields = (res.fields?.[selectedDataset] || [])
          .filter(f => f.numeric && f.name !== 'station_name');
        setJHUAPLFields(fields);
        setSelectedFields([]);
      })
      .catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [selectedDataset, debouncedStart, debouncedEnd]);

  // Reset window when dataset or date range changes
  useEffect(() => {
    setWindowStart(null);
  }, [selectedDataset, debouncedStart, debouncedEnd]);

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    try {
      await clearCache();
      setRefreshKey(k => k + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleWindowModeChange = (mins) => {
    setWindowMinutes(mins);
    if (mins === 0) {
      setWindowStart(null);
    } else if (dataRange) {
      setWindowStart(dataRange.min);
    }
  };

  const handlePrev = () => {
    if (!windowStart || !windowMinutes) return;
    const prev = windowStart - windowMinutes * 60000;
    if (dataRange && prev >= dataRange.min - windowMinutes * 60000) {
      setWindowStart(prev);
    }
  };

  const handleNext = () => {
    if (!windowStart || !windowMinutes) return;
    const next = windowStart + windowMinutes * 60000;
    if (dataRange && next <= dataRange.max + windowMinutes * 60000) {
      setWindowStart(next);
    }
  };

  const windowEndMs = windowStart && windowMinutes ? windowStart + windowMinutes * 60000 : null;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Satellite className="w-6 h-6 text-blue-400" />
            <div>
              <h1 className="text-lg font-semibold tracking-tight">REAL Science Data</h1>
              <p className="text-[10px] text-gray-500 -mt-0.5">NORAD 64875 · JHUAPL Level-1</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Dataset selector */}
            {datasets.length > 0 && (
              <select
                value={selectedDataset}
                onChange={e => setSelectedDataset(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-md px-2.5 py-1.5 text-sm
                           text-gray-200 focus:outline-none focus:border-blue-500"
              >
                {datasets.map(ds => (
                  <option key={ds.name} value={ds.name}>
                    {ds.name} ({ds.days}d)
                  </option>
                ))}
              </select>
            )}

            <button
              onClick={handleRefresh}
              disabled={loading}
              className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 py-4">
        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-800 rounded-lg text-red-300 text-sm">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-wrap items-end gap-4 mb-5 p-4 bg-gray-900/50 border border-gray-800 rounded-xl">
          {/* Date range */}
          <div className="flex gap-2 items-end">
            <div>
              <label className="block text-[10px] text-gray-500 mb-0.5 uppercase tracking-wider">Start</label>
              <input
                type="date" value={start} onChange={e => setStart(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-sm
                           focus:outline-none focus:border-blue-500 text-gray-200"
              />
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-0.5 uppercase tracking-wider">End</label>
              <input
                type="date" value={end} onChange={e => setEnd(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-sm
                           focus:outline-none focus:border-blue-500 text-gray-200"
              />
            </div>
            <div className="flex gap-1">
              {[3, 7, 14].map(d => (
                <button
                  key={d} onClick={() => { setStart(daysAgo(d)); setEnd(today()); }}
                  className="text-xs px-2 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700
                             rounded-md text-gray-400 hover:text-white transition-colors"
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>

          {/* Orbit stepper */}
          <div className="flex items-end gap-2">
            <div>
              <label className="block text-[10px] text-gray-500 mb-0.5 uppercase tracking-wider">Time Window</label>
              <select
                value={windowMinutes}
                onChange={e => handleWindowModeChange(parseInt(e.target.value))}
                className="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-sm
                           text-gray-200 focus:outline-none focus:border-blue-500"
              >
                {WINDOW_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {windowMinutes > 0 && windowStart && (
              <div className="flex items-center gap-1">
                <button
                  onClick={handlePrev}
                  className="p-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700
                             rounded-md text-gray-400 hover:text-white transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs text-gray-300 font-mono min-w-[200px] text-center">
                  {formatUTCShort(windowStart)} — {formatUTCShort(windowEndMs)} UTC
                </span>
                <button
                  onClick={handleNext}
                  className="p-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700
                             rounded-md text-gray-400 hover:text-white transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Region filter toggle */}
          <button
            onClick={() => setShowFilters(f => !f)}
            className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
              showFilters || lRange || latRange
                ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            Region
          </button>
        </div>

        {/* Region filters (collapsible) */}
        {showFilters && (
          <div className="mb-4 p-3 bg-gray-900/50 border border-gray-800 rounded-xl flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-[10px] text-gray-500 mb-0.5 uppercase tracking-wider">L-shell range</label>
              <div className="flex items-center gap-1">
                <input
                  type="number" step="0.1" placeholder="min"
                  value={lMin} onChange={e => setLMin(e.target.value)}
                  className="w-16 bg-gray-800 border border-gray-700 rounded-md px-2 py-1 text-sm
                             text-gray-200 focus:outline-none focus:border-blue-500"
                />
                <span className="text-gray-600 text-xs">to</span>
                <input
                  type="number" step="0.1" placeholder="max"
                  value={lMax} onChange={e => setLMax(e.target.value)}
                  className="w-16 bg-gray-800 border border-gray-700 rounded-md px-2 py-1 text-sm
                             text-gray-200 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-0.5 uppercase tracking-wider">Latitude range (°)</label>
              <div className="flex items-center gap-1">
                <input
                  type="number" step="1" placeholder="-90"
                  value={latMin} onChange={e => setLatMin(e.target.value)}
                  className="w-16 bg-gray-800 border border-gray-700 rounded-md px-2 py-1 text-sm
                             text-gray-200 focus:outline-none focus:border-blue-500"
                />
                <span className="text-gray-600 text-xs">to</span>
                <input
                  type="number" step="1" placeholder="90"
                  value={latMax} onChange={e => setLatMax(e.target.value)}
                  className="w-16 bg-gray-800 border border-gray-700 rounded-md px-2 py-1 text-sm
                             text-gray-200 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            {(lRange || latRange) && (
              <button
                onClick={() => { setLMin(''); setLMax(''); setLatMin(''); setLatMax(''); }}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Clear filters
              </button>
            )}
            <div className="text-[10px] text-gray-600 ml-auto">
              {lRange && <span>L: {lRange[0]}–{lRange[1] === 1000 ? '∞' : lRange[1]}</span>}
              {latRange && <span className="ml-2">Lat: {latRange[0]}°–{latRange[1]}°</span>}
            </div>
          </div>
        )}

        {/* Field selector */}
        {jhuaplFields.length > 0 && (
          <FieldSelector
            fields={jhuaplFields}
            selected={selectedFields}
            onChange={setSelectedFields}
          />
        )}

        {/* Analysis panels */}
        <Dashboard
          key={`${refreshKey}-${selectedDataset}`}
          dataset={selectedDataset}
          start={debouncedStart}
          end={debouncedEnd}
          windowStart={windowStart}
          windowMinutes={windowMinutes}
          lRange={lRange}
          latRange={latRange}
          selectedFields={selectedFields}
          fieldMeta={jhuaplFields}
          onDataRange={setDataRange}
        />
      </main>
    </div>
  );
}

import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, Search, X } from 'lucide-react';

function groupFields(fields) {
  const groups = {};
  fields.forEach(f => {
    let group = 'Other';
    const n = f.name.toLowerCase();

    if (n.startsWith('esa_1_')) group = 'ESA-1 Energy Bins';
    else if (n.startsWith('esa_2_')) group = 'ESA-2 Energy Bins';
    else if (n.startsWith('ld0_bin')) group = 'Detector 0 Bins';
    else if (n.startsWith('ld1_bin')) group = 'Detector 1 Bins';
    else if (n.startsWith('ld2_bin')) group = 'Detector 2 Bins';
    else if (n.startsWith('ld4_bin')) group = 'Detector 4 Bins';
    else if (['lat_deg', 'lon_deg', 'alt_km'].includes(n)) group = 'Position';
    else if (['mlt', 'mag_lat_deg', 'mag_lon_deg', 'l'].includes(n)) group = 'Magnetic Coordinates';
    else if (n.startsWith('ld') && (n.includes('led') || n.includes('val') || n.includes('active'))) group = 'Detector Status';
    else if (['met', 'mag_flag', 'scan_table', 'sequence_count', 'n_burst', 'i_burst',
              'complete_flag', 'rates_sequence_count', 'station_name'].includes(n)) group = 'Instrument / Metadata';
    else if (n.includes('sequence_count')) group = 'Instrument / Metadata';

    if (!groups[group]) groups[group] = [];
    groups[group].push(f);
  });

  const order = [
    'Position', 'Magnetic Coordinates',
    'ESA-1 Energy Bins', 'ESA-2 Energy Bins',
    'Detector 0 Bins', 'Detector 1 Bins', 'Detector 2 Bins', 'Detector 4 Bins',
    'Detector Status', 'Instrument / Metadata', 'Other',
  ];
  const sorted = {};
  order.forEach(g => { if (groups[g]) sorted[g] = groups[g]; });
  Object.keys(groups).forEach(g => { if (!sorted[g]) sorted[g] = groups[g]; });
  return sorted;
}

export default function FieldSelector({ fields, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const groups = useMemo(() => groupFields(fields), [fields]);

  const filtered = useMemo(() => {
    if (!search.trim()) return groups;
    const q = search.toLowerCase();
    const out = {};
    Object.entries(groups).forEach(([group, flds]) => {
      const match = flds.filter(f =>
        f.name.toLowerCase().includes(q) || group.toLowerCase().includes(q)
      );
      if (match.length) out[group] = match;
    });
    return out;
  }, [groups, search]);

  const toggle = (name) => {
    onChange(
      selected.includes(name)
        ? selected.filter(n => n !== name)
        : [...selected, name]
    );
  };

  const selectAll = () => onChange(fields.map(f => f.name));
  const selectNone = () => onChange([]);

  const selectGroup = (groupFields) => {
    const names = groupFields.map(f => f.name);
    const allSelected = names.every(n => selected.includes(n));
    if (allSelected) {
      onChange(selected.filter(n => !names.includes(n)));
    } else {
      onChange([...new Set([...selected, ...names])]);
    }
  };

  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-3 bg-gray-900/50 border border-gray-800
                   rounded-xl text-sm hover:border-gray-700 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-gray-400">Additional Fields:</span>
          <span className="text-gray-200">
            {selected.length} of {fields.length} selected
          </span>
          {selected.length > 0 && selected.length <= 4 && (
            <span className="text-xs text-gray-500 hidden sm:inline">
              ({selected.join(', ')})
            </span>
          )}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
      </button>

      {open && (
        <div className="mt-2 p-4 bg-gray-900/80 border border-gray-800 rounded-xl">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex-1 relative">
              <Search className="absolute left-2.5 top-2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search fields…"
                className="w-full bg-gray-800 border border-gray-700 rounded-md pl-8 pr-8 py-1.5 text-sm
                           text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-2.5 top-2 text-gray-500 hover:text-gray-300">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <button onClick={selectAll} className="text-xs text-blue-400 hover:text-blue-300">All</button>
            <button onClick={selectNone} className="text-xs text-gray-500 hover:text-gray-300">None</button>
          </div>

          <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
            {Object.entries(filtered).map(([group, flds]) => (
              <div key={group}>
                <button
                  onClick={() => selectGroup(flds)}
                  className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5
                             hover:text-gray-300 transition-colors cursor-pointer"
                >
                  {group}
                  <span className="text-gray-600 ml-1 normal-case">({flds.length})</span>
                </button>
                <div className="flex flex-wrap gap-1.5">
                  {flds.map(f => {
                    const active = selected.includes(f.name);
                    return (
                      <button
                        key={f.name}
                        onClick={() => toggle(f.name)}
                        className={`text-xs px-2 py-1 rounded-md border transition-colors ${
                          active
                            ? 'bg-cyan-600/20 border-cyan-500/50 text-cyan-300'
                            : 'bg-gray-800/50 border-gray-700/50 text-gray-500 hover:text-gray-300 hover:border-gray-600'
                        }`}
                      >
                        {f.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

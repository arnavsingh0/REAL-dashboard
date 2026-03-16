import React, { useState, useEffect } from 'react';
import { Activity, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { fetchLatest } from '../api';

/**
 * Displays the latest decoded values for key subsystems
 * with color-coded status indicators based on thresholds.
 *
 * Shows a compact grid of the most important fields,
 * useful as a quick "is the satellite healthy?" glance.
 */

// Key fields to show in the status panel (most operationally important)
const KEY_HEALTH_FIELDS = [
  'vbat_bat_voltage',
  'vbat_eps_voltage',
  '3v3_bat_voltage',
  '5v_bat_voltage',
  'bat_board_temperature',
  'bat_cell_1_temperature',
  'vbat_eps_current',
  '3v3_eps_current',
  'eps_mb_temperature',
  'sa1_salw_inner_voltage',
  'sa1_salw_inner_current',
  'obc_temperature_1',
  'wheel_1_speed',
  'wheel_2_speed',
  'wheel_3_speed',
  'rssi',
];

function getStatus(value, thresholds) {
  if (value == null || Number.isNaN(value)) return 'unknown';
  const { RL, YL, YH, RH } = thresholds || {};
  if ((RL != null && value < RL) || (RH != null && value > RH)) return 'red';
  if ((YL != null && value < YL) || (YH != null && value > YH)) return 'yellow';
  return 'nominal';
}

const statusIcon = {
  nominal: <CheckCircle className="w-3.5 h-3.5 text-green-400" />,
  yellow: <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />,
  red: <XCircle className="w-3.5 h-3.5 text-red-400" />,
  unknown: <Activity className="w-3.5 h-3.5 text-gray-600" />,
};

const statusBorder = {
  nominal: 'border-green-900/50',
  yellow: 'border-yellow-900/50',
  red: 'border-red-900/50',
  unknown: 'border-gray-800',
};

export default function StatusPanel({ sources }) {
  const [latest, setLatest] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchLatest({ sources })
      .then(data => { if (!cancelled) setLatest(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sources]);

  if (loading) {
    return (
      <div className="mt-6 p-4 bg-gray-900/50 border border-gray-800 rounded-xl">
        <p className="text-sm text-gray-500 animate-pulse">Loading latest values…</p>
      </div>
    );
  }

  const healthVals = latest?.health?.values || {};
  const healthTs = latest?.health?.timestamp;

  // Count statuses
  let nomCount = 0, warnCount = 0, critCount = 0;
  KEY_HEALTH_FIELDS.forEach(name => {
    const entry = healthVals[name];
    if (!entry) return;
    const s = getStatus(entry.value, entry.thresholds);
    if (s === 'nominal') nomCount++;
    else if (s === 'yellow') warnCount++;
    else if (s === 'red') critCount++;
  });

  return (
    <div className="mt-6">
      {/* Summary header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-gray-400" />
          <h2 className="text-sm font-medium text-gray-300">Latest Status</h2>
          {healthTs && (
            <span className="text-xs text-gray-600">
              {new Date(healthTs).toISOString().replace('T', ' ').slice(0, 19)} UTC
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-400">{nomCount} nominal</span>
          {warnCount > 0 && <span className="text-yellow-400">{warnCount} warning</span>}
          {critCount > 0 && <span className="text-red-400">{critCount} critical</span>}
        </div>
      </div>

      {/* Status grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
        {KEY_HEALTH_FIELDS.map(name => {
          const entry = healthVals[name];
          if (!entry) return null;
          const status = getStatus(entry.value, entry.thresholds);

          return (
            <div
              key={name}
              className={`bg-gray-900/60 border ${statusBorder[status]} rounded-lg px-3 py-2`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-gray-500 truncate max-w-[80%]">
                  {name.replace(/_/g, ' ')}
                </span>
                {statusIcon[status]}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-sm font-mono text-gray-200">
                  {entry.value != null ? entry.value.toFixed(3) : '—'}
                </span>
                <span className="text-[10px] text-gray-600">{entry.units}</span>
              </div>
              {entry.thresholds?.Nom != null && (
                <div className="text-[9px] text-gray-600 mt-0.5">
                  nom: {entry.thresholds.Nom}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
import React, { useMemo } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

function valueToColor(t) {
  const hue = (1 - t) * 240;
  return `hsl(${hue}, 80%, ${48 + t * 7}%)`;
}

function TrackTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{d.timestamp}</p>
      <p className="text-gray-200">
        {d.lat?.toFixed(2)}° lat, {d.lon?.toFixed(2)}° lon
      </p>
      {d.alt != null && (
        <p className="text-gray-400">Alt: {d.alt?.toFixed(1)} km</p>
      )}
      {d.L != null && (
        <p className="text-gray-400">L-shell: {d.L?.toFixed(2)}</p>
      )}
      {d.mlt != null && (
        <p className="text-gray-400">MLT: {d.mlt?.toFixed(1)} h</p>
      )}
      <p className="text-blue-300 mt-0.5">{d.valueLabel}: {d.value?.toFixed(1)}</p>
    </div>
  );
}

const MAX_POINTS = 3000;

export default function GroundTrack({ data, valueField = 'total_count', label = 'Total Count Rate' }) {
  const chartData = useMemo(() => {
    let valid = data.filter(d => d.lat_deg != null && d.lon_deg != null);
    if (!valid.length) return { points: [], min: 0, max: 1 };

    if (valid.length > MAX_POINTS) {
      const step = Math.ceil(valid.length / MAX_POINTS);
      valid = valid.filter((_, i) => i % step === 0);
    }

    const values = valid.map(d => d[valueField] ?? 0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const points = valid.map(d => ({
      lon: d.lon_deg,
      lat: d.lat_deg,
      value: d[valueField] ?? 0,
      norm: ((d[valueField] ?? 0) - min) / range,
      timestamp: d.timestamp,
      alt: d.alt_km,
      L: d.L,
      mlt: d.mlt,
      valueLabel: label,
    }));

    return { points, min, max };
  }, [data, valueField, label]);

  if (!chartData.points.length) {
    return (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4">
        <p className="text-sm text-gray-500">Ground Track — no position data in this window</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-300">
          Ground Track
          <span className="text-xs text-gray-500 ml-2 font-normal">
            colored by {label.toLowerCase()}
          </span>
        </h3>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span>{chartData.points.length} pts</span>
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: valueToColor(0) }} />
            <span>{chartData.min.toFixed(0)}</span>
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: valueToColor(0.5) }} />
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: valueToColor(1) }} />
            <span>{chartData.max.toFixed(0)}</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            type="number" dataKey="lon" domain={[-180, 180]}
            ticks={[-180, -120, -60, 0, 60, 120, 180]}
            tick={{ fill: '#6b7280', fontSize: 10 }}
            stroke="#374151" label={{ value: 'Longitude (°)', position: 'bottom', fill: '#4b5563', fontSize: 11, offset: -2 }}
          />
          <YAxis
            type="number" dataKey="lat" domain={[-90, 90]}
            ticks={[-90, -60, -30, 0, 30, 60, 90]}
            tick={{ fill: '#6b7280', fontSize: 10 }}
            stroke="#374151" label={{ value: 'Latitude (°)', angle: -90, position: 'insideLeft', fill: '#4b5563', fontSize: 11 }}
            width={50}
          />
          <Tooltip content={<TrackTooltip />} />
          <Scatter data={chartData.points} isAnimationActive={false}>
            {chartData.points.map((d, i) => (
              <Cell key={i} fill={valueToColor(d.norm)} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

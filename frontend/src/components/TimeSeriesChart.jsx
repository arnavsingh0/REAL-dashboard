import React, { useMemo, useState } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, ReferenceLine, ReferenceArea, CartesianGrid, Brush,
} from 'recharts';
import { Maximize2, Minimize2 } from 'lucide-react';

const THRESH_STYLE = {
  RL:  { stroke: '#ef4444', strokeDasharray: '8 4',  label: 'RL' },
  YL:  { stroke: '#eab308', strokeDasharray: '4 4',  label: 'YL' },
  Nom: { stroke: '#22c55e', strokeDasharray: '6 3',  label: 'Nom' },
  YH:  { stroke: '#eab308', strokeDasharray: '4 4',  label: 'YH' },
  RH:  { stroke: '#ef4444', strokeDasharray: '8 4',  label: 'RH' },
};

function formatTimestamp(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const mon = d.toLocaleString('en', { month: 'short', timeZone: 'UTC' });
  const day = d.getUTCDate();
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${mon} ${day} ${hh}:${mm}`;
}

function ChartTooltip({ active, payload, label, fieldName, units }) {
  if (!active || !payload?.length) return null;
  const pt = payload[0];
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1">{formatTimestamp(label)}</p>
      <p className="text-white font-medium">
        {fieldName}: <span className="text-blue-300">{pt.value?.toFixed(4)}</span>
        {units && <span className="text-gray-500 ml-1">{units}</span>}
      </p>
      {pt.payload?.L != null && (
        <p className="text-gray-500 mt-0.5">L={pt.payload.L?.toFixed(2)}</p>
      )}
    </div>
  );
}

export default function TimeSeriesChart({
  data, fieldName, units = '', thresholds = {},
  title, color = '#3b82f6',
  windowStartISO, windowEndISO,
}) {
  const [expanded, setExpanded] = useState(false);

  const chartData = useMemo(() => {
    return data
      .filter(d => d[fieldName] != null && !Number.isNaN(d[fieldName]))
      .map(d => ({ ...d, _ts: new Date(d.timestamp).getTime() }))
      .sort((a, b) => a._ts - b._ts);
  }, [data, fieldName]);

  const yDomain = useMemo(() => {
    if (!chartData.length) return [0, 1];
    const vals = chartData.map(d => d[fieldName]);
    const threshVals = Object.values(thresholds).filter(v => typeof v === 'number');
    const allVals = [...vals, ...threshVals];
    const min = Math.min(...allVals);
    const max = Math.max(...allVals);
    const pad = (max - min) * 0.1 || 0.5;
    return [min - pad, max + pad];
  }, [chartData, fieldName, thresholds]);

  const latestVal = chartData.length ? chartData[chartData.length - 1][fieldName] : null;
  const height = expanded ? 400 : 220;
  const displayTitle = title || fieldName;

  if (!chartData.length) {
    return (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4">
        <p className="text-sm text-gray-500">{displayTitle} — no data points</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-gray-200">{displayTitle}</h3>
          {units && <span className="text-xs text-gray-500">({units})</span>}
        </div>
        <div className="flex items-center gap-3">
          {latestVal != null && (
            <span className="text-xs font-mono text-gray-400">
              latest: {latestVal.toFixed(2)} {units}
            </span>
          )}
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-gray-500 hover:text-white transition-colors"
          >
            {expanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />

          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTimestamp}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            stroke="#374151"
            minTickGap={60}
          />

          <YAxis
            domain={yDomain}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            stroke="#374151"
            tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v.toFixed(1)}
            width={55}
          />

          <Tooltip content={<ChartTooltip fieldName={fieldName} units={units} />} />

          {windowStartISO && windowEndISO && (
            <ReferenceArea
              x1={windowStartISO} x2={windowEndISO}
              fill="#3b82f6" fillOpacity={0.08}
              stroke="#3b82f6" strokeOpacity={0.3}
            />
          )}

          {Object.entries(thresholds).map(([key, val]) => {
            const style = THRESH_STYLE[key];
            if (!style || typeof val !== 'number') return null;
            return (
              <ReferenceLine
                key={key} y={val}
                stroke={style.stroke} strokeDasharray={style.strokeDasharray} strokeWidth={1.5}
                label={{ value: `${style.label}=${val}`, position: 'right', fill: style.stroke, fontSize: 10 }}
              />
            );
          })}

          <Line
            type="monotone" dataKey={fieldName}
            stroke={color} strokeWidth={1.5}
            dot={false} activeDot={{ r: 3, fill: color }}
            isAnimationActive={false}
          />

          {expanded && (
            <Brush
              dataKey="timestamp" height={25}
              stroke="#374151" fill="#111827"
              tickFormatter={formatTimestamp}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

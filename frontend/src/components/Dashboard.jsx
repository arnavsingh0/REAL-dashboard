import React, { useState, useEffect, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import TimeSeriesChart from './TimeSeriesChart';
import GroundTrack from './GroundTrack';
import { fetchJHUAPLData } from '../api';

function sumFields(row, prefix, count) {
  let total = 0;
  for (let i = 0; i < count; i++) {
    const key = `${prefix}${String(i).padStart(2, '0')}`;
    const v = row[key];
    if (v != null && !Number.isNaN(v)) total += v;
  }
  return total;
}

export default function Dashboard({
  dataset, start, end,
  windowStart, windowMinutes,
  lRange, latRange,
  selectedFields, fieldMeta,
  onDataRange,
}) {
  const [allData, setAllData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const datasetKey = dataset;
  const rangeKey = `${start}:${end}`;

  useEffect(() => {
    if (!datasetKey) { setAllData([]); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchJHUAPLData({ dataset: datasetKey, start, end, limit: 2000 })
      .then(res => { if (!cancelled) setAllData(res.data || []); })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [datasetKey, rangeKey]);

  const processed = useMemo(() => {
    if (!allData.length) return [];

    const hasEsa = 'esa_1_row_00' in allData[0];
    const hasLd = 'ld0_bin_00' in allData[0];

    return allData.map(d => {
      const row = { ...d, _ts: new Date(d.timestamp).getTime() };

      if (hasEsa) {
        row.total_esa1 = sumFields(d, 'esa_1_row_', 15);
        row.total_esa2 = sumFields(d, 'esa_2_row_', 15);
        row.total_count = row.total_esa1 + row.total_esa2;
        row.esa_ratio = row.total_esa2 > 0 ? row.total_esa1 / row.total_esa2 : null;
      }

      if (hasLd) {
        row.total_ld0 = sumFields(d, 'ld0_bin_', 12);
        row.total_ld1 = sumFields(d, 'ld1_bin_', 12);
        row.total_ld2 = sumFields(d, 'ld2_bin_', 12);
        row.total_ld4 = sumFields(d, 'ld4_bin_', 12);
        row.total_count = row.total_ld0 + row.total_ld1 + row.total_ld2 + row.total_ld4;
        row.ld0_ld1_ratio = row.total_ld1 > 0 ? row.total_ld0 / row.total_ld1 : null;
      }

      return row;
    });
  }, [allData]);

  useEffect(() => {
    if (!processed.length) { onDataRange?.(null); return; }
    const timestamps = processed.map(d => d._ts);
    onDataRange?.({
      min: Math.min(...timestamps),
      max: Math.max(...timestamps),
    });
  }, [processed]);

  const filtered = useMemo(() => {
    return processed.filter(d => {
      if (lRange) {
        if (d.L != null && (d.L < lRange[0] || d.L > lRange[1])) return false;
      }
      if (latRange) {
        if (d.lat_deg != null && (d.lat_deg < latRange[0] || d.lat_deg > latRange[1])) return false;
      }
      return true;
    });
  }, [processed, lRange, latRange]);

  const windowed = useMemo(() => {
    if (!windowStart || !windowMinutes) return filtered;
    const wsMs = windowStart;
    const weMs = windowStart + windowMinutes * 60000;
    return filtered.filter(d => d._ts >= wsMs && d._ts <= weMs);
  }, [filtered, windowStart, windowMinutes]);

  const hasCountRate = processed.length > 0 && processed[0].total_count != null;
  const hasEsaRatio = processed.length > 0 && processed[0].esa_ratio !== undefined;
  const hasLdRatio = processed.length > 0 && processed[0].ld0_ld1_ratio !== undefined;
  const hasGeo = processed.length > 0 && processed[0].lat_deg != null;
  const isWindowed = windowStart && windowMinutes > 0;
  const detailData = isWindowed ? windowed : filtered;

  const windowStartISO = isWindowed ? new Date(windowStart).toISOString() : null;
  const windowEndISO = isWindowed ? new Date(windowStart + windowMinutes * 60000).toISOString() : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading {dataset}…
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-10 text-center">
        <p className="text-red-400 mb-2">Failed to load data</p>
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  if (!processed.length) {
    return (
      <div className="py-16 text-center text-gray-600">
        No data for this date range. Try expanding the window or selecting a different dataset.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        {filtered.length} points · {dataset}
        {isWindowed && ` · Viewing ${windowed.length} points in window`}
      </p>

      {/* Count Rate Overview — always full range */}
      {hasCountRate && (
        <div>
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5 font-medium">
            Count Rate Overview
          </p>
          <TimeSeriesChart
            data={filtered}
            fieldName="total_count"
            title={hasEsaRatio ? 'Total ESA Count Rate (ESA-1 + ESA-2, all bins)' : 'Total Count Rate (all detectors)'}
            units="counts"
            color="#3b82f6"
            windowStartISO={windowStartISO}
            windowEndISO={windowEndISO}
          />
        </div>
      )}

      {/* Detector Ratio — detail window */}
      {hasEsaRatio && (
        <div>
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5 font-medium">
            Detector Ratio
          </p>
          <TimeSeriesChart
            data={detailData}
            fieldName="esa_ratio"
            title="ESA-1 / ESA-2 Ratio"
            units=""
            color="#a78bfa"
          />
        </div>
      )}

      {hasLdRatio && (
        <div>
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5 font-medium">
            Detector Ratio
          </p>
          <TimeSeriesChart
            data={detailData}
            fieldName="ld0_ld1_ratio"
            title="LD0 / LD1 Ratio"
            units=""
            color="#a78bfa"
          />
        </div>
      )}

      {/* Ground Track — detail window */}
      {hasGeo && (
        <div>
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5 font-medium">
            Orbital Position
          </p>
          <GroundTrack
            data={detailData}
            valueField="total_count"
            label="Total Count Rate"
          />
        </div>
      )}

      {/* Custom fields from FieldSelector */}
      {selectedFields && selectedFields.length > 0 && (
        <div>
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-1.5 font-medium">
            Selected Fields
          </p>
          <div className="space-y-3">
            {selectedFields.map(fieldName => {
              const meta = fieldMeta?.find(f => f.name === fieldName);
              if (!meta) return null;
              return (
                <TimeSeriesChart
                  key={fieldName}
                  data={detailData}
                  fieldName={fieldName}
                  title={fieldName}
                  units={meta.units || ''}
                  thresholds={meta.thresholds || {}}
                  color="#22d3ee"
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

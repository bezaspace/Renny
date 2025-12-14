import React, { useEffect, useMemo, useRef } from 'react';
import {
  createChart,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
  type SeriesMarker,
} from 'lightweight-charts';

interface CandleInput {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface PatternMarker {
  timestamp: string;
  pattern: string;
  direction: string;
  strength: number;
}

interface MiniCandleChartProps {
  data: CandleInput[];
  title: string;
  markers?: PatternMarker[];
  height?: number;
  embedded?: boolean;
}

function toUTCTimeSeconds(ts: string): number | null {
  const t = new Date(ts).getTime();
  if (Number.isNaN(t)) return null;
  return Math.floor(t / 1000);
}

const MiniCandleChart: React.FC<MiniCandleChartProps> = ({ data, title, markers, height = 220, embedded = false }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  const candleData: CandlestickData<Time>[] = useMemo(() => {
    return (data || [])
      .map((c) => {
        const time = toUTCTimeSeconds(c.timestamp);
        if (time == null) return null;
        return {
          time: time as Time,
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
        };
      })
      .filter(Boolean) as CandlestickData<Time>[];
  }, [data]);

  const resolvedMarkers: SeriesMarker<Time>[] = useMemo(() => {
    if (!markers || markers.length === 0) return [];

    return markers
      .map((m) => {
        const time = toUTCTimeSeconds(m.timestamp);
        if (time == null) return null;

        const bullish = (m.direction || '').toLowerCase() === 'bullish';
        const color = bullish ? '#10B981' : '#EF4444';
        const text = (m.pattern || '').replace(/^CDL/, '');
        return {
          time: time as Time,
          position: bullish ? 'belowBar' : 'aboveBar',
          color,
          shape: bullish ? 'arrowUp' : 'arrowDown',
          text,
        };
      })
      .filter(Boolean) as SeriesMarker<Time>[];
  }, [markers]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Cleanup any prior chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
    }

    const chart = createChart(el, {
      height,
      width: el.clientWidth || 300,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#D1D5DB',
      },
      grid: {
        vertLines: { color: 'rgba(55,65,81,0.35)' },
        horzLines: { color: 'rgba(55,65,81,0.35)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(55,65,81,0.6)',
      },
      timeScale: {
        borderColor: 'rgba(55,65,81,0.6)',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: 'rgba(156,163,175,0.35)' },
        horzLine: { color: 'rgba(156,163,175,0.35)' },
      },
      handleScroll: false,
      handleScale: false,
    });

    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderUpColor: '#10B981',
      borderDownColor: '#EF4444',
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });

    seriesRef.current = candleSeries;

    candleSeries.setData(candleData);
    if (resolvedMarkers.length > 0) {
      candleSeries.setMarkers(resolvedMarkers);
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
    });

    ro.observe(el);

    return () => {
      ro.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, [candleData, resolvedMarkers, height]);

  if (embedded) {
    return <div ref={containerRef} className="w-full" />;
  }

  return (
    <div className="w-full bg-gray-900 rounded-lg p-4 border border-gray-800">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-bold text-gray-200">{title}</h4>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
};

export default MiniCandleChart;

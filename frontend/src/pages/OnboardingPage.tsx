import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Plus, Trash2, Loader2 } from 'lucide-react';

import TradingChart from '@/components/TradingChart';
import MiniCandleChart from '@/components/MiniCandleChart';
import IndicatorChart from '@/components/IndicatorChart';
import EnhancedIndicatorCard from '@/components/EnhancedIndicatorCard';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Holding = {
  symbol: string;
  quantity: number;
  avg_buy_price: number;
};

type TradingProfile = {
  horizon: 'intraday' | 'swing' | 'investing';
  risk: 'conservative' | 'balanced' | 'aggressive';
  style: 'trend' | 'breakout' | 'mean_reversion';
};

type PortfolioAnalysis = {
  id: number;
  user_id: string;
  created_at: string;
  status: string;
  summary_markdown?: string | null;
  error_message?: string | null;
  holding_analyses: Array<{
    symbol: string;
    horizon: string;
    risk: string;
    style: string;
    tool_payload_json?: string | null;
    strategy_markdown?: string | null;
    created_at: string;
  }>;
};

type ChartData = {
  symbol: string;
  data?: any[];
  message?: string;
  overlays?: Record<string, any>;
  series?: Record<string, any>;
  timestamps?: string[];
  patterns?: Array<{ name: string; direction: string; strength: number; timestamp: string; index?: number }>;
  pattern_markers?: Array<{ timestamp: string; pattern: string; direction: string; strength: number; index?: number }>;
  pattern_visuals?: Array<{
    pattern: { name: string; direction: string; strength: number; timestamp: string };
    data: any[];
    pattern_markers?: Array<{ timestamp: string; pattern: string; direction: string; strength: number; index?: number }>;
  }>;
};

const API_BASE = 'http://localhost:8000';
const USER_ID = 'default';

const horizonOptions: Array<{ value: TradingProfile['horizon']; label: string }> = [
  { value: 'intraday', label: 'Intraday' },
  { value: 'swing', label: 'Swing' },
  { value: 'investing', label: 'Investing' },
];

const riskOptions: Array<{ value: TradingProfile['risk']; label: string }> = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'aggressive', label: 'Aggressive' },
];

const styleOptions: Array<{ value: TradingProfile['style']; label: string }> = [
  { value: 'trend', label: 'Trend Following' },
  { value: 'breakout', label: 'Breakout' },
  { value: 'mean_reversion', label: 'Mean Reversion' },
];

function ChipGroup<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            'px-3 py-2 rounded-md text-sm border transition-colors',
            value === o.value
              ? 'bg-gray-800 border-gray-700 text-white'
              : 'bg-gray-950 border-gray-800 text-gray-300 hover:bg-gray-800'
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function VisualPayload({ payloadJson }: { payloadJson?: string | null }) {
  const parsed = useMemo(() => {
    if (!payloadJson) return null;
    try {
      return JSON.parse(payloadJson) as ChartData;
    } catch {
      return null;
    }
  }, [payloadJson]);

  if (!parsed) {
    return (
      <div className="text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded p-3">
        No visuals.
      </div>
    );
  }

  if (parsed.data && Array.isArray(parsed.data) && parsed.symbol) {
    return (
      <div className="w-full space-y-4">
        <div className="w-full">
          {parsed.message && <p className="mb-2 text-gray-300">{parsed.message}</p>}
          <TradingChart data={parsed.data} symbol={parsed.symbol} overlays={parsed.overlays} patternMarkers={parsed.pattern_markers} />
        </div>

        {parsed.patterns && parsed.patterns.length > 0 && (
          <div className="bg-gray-900/50 rounded border border-gray-800 p-3">
            <h4 className="text-sm font-bold text-gray-200 mb-2">Candlestick Patterns</h4>
            <div className="space-y-2">
              {parsed.patterns.map((p, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm">
                  <div className="text-gray-200">
                    {p.name}
                    <span
                      className={cn(
                        'ml-2 text-xs px-2 py-0.5 rounded border',
                        p.direction === 'bullish'
                          ? 'border-green-700 text-green-400 bg-green-900/20'
                          : 'border-red-700 text-red-400 bg-red-900/20'
                      )}
                    >
                      {p.direction}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400">
                    {new Date(p.timestamp).toLocaleString()}
                    <span className="ml-2">({p.strength})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {parsed.pattern_visuals && parsed.pattern_visuals.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-bold text-gray-200">Pattern Visuals</h4>
            {parsed.pattern_visuals.map((v, idx) => {
              const label = (v.pattern?.name || '').replace(/^CDL/, '');
              const dir = v.pattern?.direction || '';
              const strength = v.pattern?.strength;
              const ts = v.pattern?.timestamp;
              const title = `${label} (${dir}${typeof strength === 'number' ? `, ${strength}` : ''})${ts ? ` - ${new Date(ts).toLocaleString()}` : ''}`;

              return (
                <MiniCandleChart
                  key={`${v.pattern?.name || 'pattern'}-${v.pattern?.timestamp || idx}`}
                  data={v.data}
                  title={title}
                  markers={v.pattern_markers}
                />
              );
            })}
          </div>
        )}

        {parsed.series && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
            {Object.entries(parsed.series).map(([indName, indData]) => {
              const simpleIndicators = ['RSI', 'MOM', 'ADX', 'ATR', 'CCI', 'DX', 'WILLR'];

              if (simpleIndicators.includes(indName)) {
                return (
                  <EnhancedIndicatorCard
                    key={indName}
                    indicator={indName}
                    data={indData as Record<string, number[]>}
                    analysis={`${indName} Analysis`}
                    timestamps={parsed.timestamps}
                  />
                );
              }

              return (
                <div key={indName} className="bg-gray-800 p-3 rounded-md border border-gray-700">
                  <h5 className="font-bold text-blue-400 text-sm mb-1">{indName}</h5>
                  <IndicatorChart
                    indicator={indName}
                    data={indData as Record<string, number[]>}
                    timestamps={parsed.timestamps}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <pre className="whitespace-pre-wrap text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded p-3 overflow-x-auto">
      {JSON.stringify(parsed, null, 2)}
    </pre>
  );
}

function OnboardingPage() {
  const [holdings, setHoldings] = useState<Holding[]>([{ symbol: '', quantity: 0, avg_buy_price: 0 }]);
  const [profile, setProfile] = useState<TradingProfile>({
    horizon: 'swing',
    risk: 'balanced',
    style: 'trend',
  });

  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSave = useMemo(() => {
    const cleaned = holdings
      .map((h) => ({
        symbol: (h.symbol || '').trim(),
        quantity: Number(h.quantity),
        avg_buy_price: Number(h.avg_buy_price),
      }))
      .filter((h) => h.symbol.length > 0);

    if (cleaned.length === 0) return false;
    for (const h of cleaned) {
      if (!h.symbol) return false;
      if (!Number.isFinite(h.quantity) || h.quantity <= 0) return false;
      if (!Number.isFinite(h.avg_buy_price) || h.avg_buy_price <= 0) return false;
    }
    return true;
  }, [holdings]);

  const normalizedHoldings = useMemo(() => {
    return holdings
      .map((h) => ({
        symbol: (h.symbol || '').trim().toUpperCase(),
        quantity: Number(h.quantity),
        avg_buy_price: Number(h.avg_buy_price),
      }))
      .filter((h) => h.symbol.length > 0);
  }, [holdings]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/onboarding/${USER_ID}`);
        if (!res.ok) return;
        const data = await res.json();

        if (Array.isArray(data.holdings) && data.holdings.length > 0) {
          setHoldings(
            data.holdings.map((h: any) => ({
              symbol: String(h.symbol ?? ''),
              quantity: Number(h.quantity ?? 0),
              avg_buy_price: Number(h.avg_buy_price ?? 0),
            }))
          );
        }

        if (data.profile) {
          setProfile({
            horizon: data.profile.horizon,
            risk: data.profile.risk,
            style: data.profile.style,
          });
        }
      } catch {
        // ignore
      }
    })();
  }, []);

  const onChangeHolding = (idx: number, key: keyof Holding, value: string) => {
    setHoldings((prev) => {
      const next = [...prev];
      const current = { ...next[idx] };
      if (key === 'symbol') {
        current.symbol = value;
      } else {
        const n = Number(value);
        (current as any)[key] = Number.isFinite(n) ? n : 0;
      }
      next[idx] = current;
      return next;
    });
  };

  const addRow = () => {
    setHoldings((prev) => [...prev, { symbol: '', quantity: 0, avg_buy_price: 0 }]);
  };

  const removeRow = (idx: number) => {
    setHoldings((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      return next.length === 0 ? [{ symbol: '', quantity: 0, avg_buy_price: 0 }] : next;
    });
  };

  const save = async () => {
    setError(null);
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/onboarding/${USER_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings: normalizedHoldings, profile }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Save failed (${res.status})`);
      }
    } finally {
      setSaving(false);
    }
  };

  const analyze = async () => {
    setError(null);
    setAnalysis(null);
    setAnalysisId(null);
    setAnalyzing(true);

    try {
      await save();

      const res = await fetch(`${API_BASE}/portfolio/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: USER_ID }),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Analyze failed (${res.status})`);
      }

      const data = await res.json();
      const paId = Number(data.portfolio_analysis_id);
      setAnalysisId(paId);

      const res2 = await fetch(`${API_BASE}/portfolio/analysis/${paId}`);
      if (!res2.ok) {
        const txt = await res2.text();
        throw new Error(txt || `Fetch analysis failed (${res2.status})`);
      }
      const analysisData = (await res2.json()) as PortfolioAnalysis;
      setAnalysis(analysisData);
    } catch (e: any) {
      setError(e?.message || 'Something went wrong');
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 text-gray-100">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-4">
            <h2 className="text-lg font-bold mb-3">Portfolio Holdings</h2>

            <div className="hidden md:grid md:grid-cols-12 gap-2 text-xs text-gray-400 mb-2 px-1">
              <div className="md:col-span-4">Symbol</div>
              <div className="md:col-span-3">Quantity</div>
              <div className="md:col-span-4">Avg buy price</div>
              <div className="md:col-span-1" />
            </div>

            <div className="space-y-3">
              {holdings.map((h, idx) => (
                <div key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                  <div className="md:col-span-4">
                    <div className="md:hidden text-xs text-gray-400 mb-1">Symbol</div>
                    <input
                      value={h.symbol}
                      onChange={(e) => onChangeHolding(idx, 'symbol', e.target.value)}
                      placeholder="Symbol (e.g. TCS)"
                      className="w-full bg-gray-900 border border-gray-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="md:col-span-3">
                    <div className="md:hidden text-xs text-gray-400 mb-1">Quantity</div>
                    <input
                      value={h.quantity}
                      onChange={(e) => onChangeHolding(idx, 'quantity', e.target.value)}
                      inputMode="decimal"
                      placeholder="Quantity"
                      className="w-full bg-gray-900 border border-gray-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="md:col-span-4">
                    <div className="md:hidden text-xs text-gray-400 mb-1">Avg buy price</div>
                    <input
                      value={h.avg_buy_price}
                      onChange={(e) => onChangeHolding(idx, 'avg_buy_price', e.target.value)}
                      inputMode="decimal"
                      placeholder="Avg buy price"
                      className="w-full bg-gray-900 border border-gray-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="md:col-span-1 flex justify-end">
                    <button
                      type="button"
                      onClick={() => removeRow(idx)}
                      className="p-2 rounded-md border border-gray-800 bg-gray-950 hover:bg-gray-800"
                      aria-label="Remove holding"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}

              <div>
                <Button type="button" variant="secondary" onClick={addRow}>
                  <Plus />
                  Add row
                </Button>
              </div>
            </div>
          </div>

          <div className="bg-gray-950 border border-gray-800 rounded-lg p-4 space-y-4">
            <h2 className="text-lg font-bold">Trading Profile</h2>

            <div>
              <div className="text-sm text-gray-300 mb-2">Time horizon</div>
              <ChipGroup
                value={profile.horizon}
                options={horizonOptions}
                onChange={(v) => setProfile((p) => ({ ...p, horizon: v }))}
              />
            </div>

            <div>
              <div className="text-sm text-gray-300 mb-2">Risk tolerance</div>
              <ChipGroup
                value={profile.risk}
                options={riskOptions}
                onChange={(v) => setProfile((p) => ({ ...p, risk: v }))}
              />
            </div>

            <div>
              <div className="text-sm text-gray-300 mb-2">Preferred style</div>
              <ChipGroup
                value={profile.style}
                options={styleOptions}
                onChange={(v) => setProfile((p) => ({ ...p, style: v }))}
              />
            </div>

            {error && (
              <div className="text-sm text-red-400 border border-red-900/40 bg-red-900/10 rounded p-3">
                {error}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={save} disabled={!canSave || saving || analyzing}>
                {saving ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving...
                  </span>
                ) : (
                  'Save'
                )}
              </Button>

              <Button type="button" variant="secondary" onClick={analyze} disabled={!canSave || saving || analyzing}>
                {analyzing ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </span>
                ) : (
                  'Save & Analyze'
                )}
              </Button>
            </div>

            {analysisId && (
              <div className="text-xs text-gray-500">Analysis ID: {analysisId}</div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-4">
            <h2 className="text-lg font-bold mb-2">Portfolio Strategy</h2>
            {!analysis?.summary_markdown ? (
              <div className="text-sm text-gray-400">Run analysis to see a saved portfolio plan here.</div>
            ) : (
              <div className="prose prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis.summary_markdown}</ReactMarkdown>
              </div>
            )}
          </div>

          {analysis?.holding_analyses?.map((ha) => (
            <div key={`${ha.symbol}-${ha.created_at}`} className="bg-gray-950 border border-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between gap-4 mb-2">
                <h3 className="text-base font-bold">{ha.symbol}</h3>
                <div className="text-xs text-gray-400">
                  {ha.horizon} / {ha.risk} / {ha.style}
                </div>
              </div>

              {ha.strategy_markdown && (
                <div className="prose prose-invert max-w-none mb-4">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{ha.strategy_markdown}</ReactMarkdown>
                </div>
              )}

              <VisualPayload payloadJson={ha.tool_payload_json} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default OnboardingPage;

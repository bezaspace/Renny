import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertCircle, Loader2, Pause, Play, RefreshCw, Square, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import MiniCandleChart from '@/components/MiniCandleChart';

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';
const USER_ID = 'default';

type Candle = {
    symbol: string;
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
};

type Trade = {
    id: number;
    symbol: string;
    side: 'buy' | 'sell';
    quantity: number;
    price: number;
    reason: string;
    confidence?: number;
    timestamp: string;
};

type Position = {
    symbol: string;
    quantity: number;
    avg_price: number;
    unrealized_pnl?: number;
    stop_loss?: number | null;
    take_profit?: number | null;
};

// SimulatorStatus type removed - not currently used

// ─────────────────────────────────────────────────────────────────────────────
// Stock Tile Component
// ─────────────────────────────────────────────────────────────────────────────

function StockTile({
    symbol,
    candles,
    currentPrice,
    position,
    recentTrade,
}: {
    symbol: string;
    candles: Candle[];
    currentPrice: number | null | undefined;
    position?: Position;
    recentTrade?: Trade;
}) {
    // Ensure we have a valid price, default to 0 if not available
    const price = currentPrice ?? 0;
    const prevPrice = candles.length >= 2 ? (candles[candles.length - 2]?.close ?? price) : price;
    const changePercent = prevPrice > 0 && price > 0 ? ((price - prevPrice) / prevPrice) * 100 : 0;
    const isUp = changePercent >= 0;

    const chartData = useMemo(() => {
        return candles.map((c) => ({
            timestamp: c.timestamp,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            volume: c.volume,
        }));
    }, [candles]);

    const hasRecentTrade = recentTrade && Date.now() - new Date(recentTrade.timestamp).getTime() < 10000;

    return (
        <div
            className={cn(
                'bg-gray-900 rounded-lg border p-4 transition-all duration-300',
                hasRecentTrade
                    ? recentTrade.side === 'buy'
                        ? 'border-green-500 shadow-lg shadow-green-500/20'
                        : 'border-red-500 shadow-lg shadow-red-500/20'
                    : 'border-gray-800'
            )}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <span className="font-bold text-lg">{symbol}</span>
                    {hasRecentTrade && (
                        <span
                            className={cn(
                                'text-xs px-2 py-0.5 rounded animate-pulse',
                                recentTrade.side === 'buy' ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                            )}
                        >
                            {recentTrade.side.toUpperCase()}
                        </span>
                    )}
                </div>
                <div className="text-right">
                    <div className="font-mono text-lg">₹{price.toFixed(2)}</div>
                    <div className={cn('text-sm flex items-center gap-1', isUp ? 'text-green-400' : 'text-red-400')}>
                        {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {changePercent.toFixed(2)}%
                    </div>
                </div>
            </div>

            {/* Chart */}
            {chartData.length > 0 && (
                <div className="h-80 mb-3">
                    <MiniCandleChart data={chartData} title="" height={320} embedded />
                </div>
            )}

            {/* Position Info */}
            {position && position.quantity > 0 && (
                <div className="text-xs text-gray-400 border-t border-gray-800 pt-2 mt-2">
                    <div className="flex justify-between">
                        <span>Position:</span>
                        <span className="text-gray-200">{position.quantity} @ ₹{(position.avg_price ?? 0).toFixed(2)}</span>
                    </div>
                    {position.unrealized_pnl != null && (
                        <div className="flex justify-between">
                            <span>P&L:</span>
                            <span className={(position.unrealized_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                                {(position.unrealized_pnl ?? 0) >= 0 ? '+' : ''}₹{(position.unrealized_pnl ?? 0).toFixed(2)}
                            </span>
                        </div>
                    )}
                    {position.stop_loss != null && (
                        <div className="flex justify-between">
                            <span>SL:</span>
                            <span className="text-gray-200">₹{Number(position.stop_loss).toFixed(2)}</span>
                        </div>
                    )}
                    {position.take_profit != null && (
                        <div className="flex justify-between">
                            <span>TP:</span>
                            <span className="text-gray-200">₹{Number(position.take_profit).toFixed(2)}</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Trade Log Component
// ─────────────────────────────────────────────────────────────────────────────

function TradeLog({ trades }: { trades: Trade[] }) {
    return (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 h-full">
            <h3 className="font-bold text-sm mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Trade Log
            </h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
                {trades.length === 0 ? (
                    <div className="text-gray-500 text-sm text-center py-4">No trades yet</div>
                ) : (
                    trades.map((trade) => (
                        <div
                            key={trade.id}
                            className={cn(
                                'rounded border p-2 text-sm',
                                trade.side === 'buy' ? 'border-green-800 bg-green-950/30' : 'border-red-800 bg-red-950/30'
                            )}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                    <span
                                        className={cn(
                                            'text-xs font-bold px-1.5 py-0.5 rounded',
                                            trade.side === 'buy' ? 'bg-green-800 text-green-200' : 'bg-red-800 text-red-200'
                                        )}
                                    >
                                        {trade.side.toUpperCase()}
                                    </span>
                                    <span className="font-medium">{trade.symbol}</span>
                                </div>
                                <span className="text-xs text-gray-500">
                                    {new Date(trade.timestamp).toLocaleTimeString()}
                                </span>
                            </div>
                            <div className="text-xs text-gray-400">
                                {trade.quantity} shares @ ₹{(trade.price ?? 0).toFixed(2)}
                            </div>
                            {trade.reason && (
                                <div className="text-xs text-gray-500 mt-1 italic">{trade.reason}</div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Trade Notification Toast
// ─────────────────────────────────────────────────────────────────────────────

function TradeNotification({ trade, onDismiss }: { trade: Trade; onDismiss: () => void }) {
    useEffect(() => {
        const timer = setTimeout(onDismiss, 5000);
        return () => clearTimeout(timer);
    }, [onDismiss]);

    return (
        <div
            className={cn(
                'fixed top-20 right-4 z-50 p-4 rounded-lg shadow-xl animate-slide-in-right border-l-4',
                trade.side === 'buy'
                    ? 'bg-green-950 border-green-500 text-green-100'
                    : 'bg-red-950 border-red-500 text-red-100'
            )}
        >
            <div className="flex items-center gap-3">
                <div
                    className={cn(
                        'p-2 rounded-full',
                        trade.side === 'buy' ? 'bg-green-800' : 'bg-red-800'
                    )}
                >
                    {trade.side === 'buy' ? (
                        <TrendingUp className="w-5 h-5" />
                    ) : (
                        <TrendingDown className="w-5 h-5" />
                    )}
                </div>
                <div>
                    <div className="font-bold">
                        {trade.side.toUpperCase()} {trade.symbol}
                    </div>
                    <div className="text-sm opacity-80">
                        {trade.quantity} shares @ ₹{(trade.price ?? 0).toFixed(2)}
                    </div>
                    {trade.reason && <div className="text-xs opacity-60 mt-1">{trade.reason}</div>}
                </div>
                <button onClick={onDismiss} className="ml-4 opacity-60 hover:opacity-100">
                    ×
                </button>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Trading Page
// ─────────────────────────────────────────────────────────────────────────────

function TradingPage() {
    const [status, setStatus] = useState<'idle' | 'initializing' | 'running' | 'paused' | 'stopped'>('idle');
    const [error, setError] = useState<string | null>(null);
    const [speedMultiplier, setSpeedMultiplier] = useState(10);
    const [symbols, setSymbols] = useState<string[]>([]);
    const [candles, setCandles] = useState<Record<string, Candle[]>>({});
    const [positions, setPositions] = useState<Position[]>([]);
    const [trades, setTrades] = useState<Trade[]>([]);
    const [notification, setNotification] = useState<Trade | null>(null);
    const [currentTime, setCurrentTime] = useState<string | null>(null);

    const [selectedSymbol, setSelectedSymbol] = useState<string>('');
    const [tradeSide, setTradeSide] = useState<'buy' | 'sell'>('buy');
    const [tradeQty, setTradeQty] = useState<string>('1');
    const [tradeStopLoss, setTradeStopLoss] = useState<string>('');
    const [tradeTakeProfit, setTradeTakeProfit] = useState<string>('');
    const [tradeSubmitting, setTradeSubmitting] = useState<boolean>(false);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Connect to WebSocket
    const connectWebSocket = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(`${WS_BASE}/ws/live-feed`);

        ws.onopen = () => {
            console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                if (msg.type === 'candle') {
                    const candleData = msg.data as Record<string, Candle>;
                    setCandles((prev) => {
                        const updated = { ...prev };
                        for (const [symbol, candle] of Object.entries(candleData)) {
                            if (!updated[symbol]) updated[symbol] = [];
                            updated[symbol] = [...updated[symbol].slice(-49), candle];
                        }
                        return updated;
                    });
                    if (msg.timestamp) {
                        setCurrentTime(msg.timestamp);
                    }
                }

                if (msg.type === 'trade') {
                    const trade = msg.data as Trade;
                    setTrades((prev) => [trade, ...prev].slice(0, 100));
                    setNotification(trade);
                    // Refresh positions after trade
                    fetchPositions();
                }

                if (msg.type === 'status') {
                    if (msg.data?.simulator?.symbols) {
                        setSymbols(msg.data.simulator.symbols);
                    }
                }
            } catch (e) {
                console.error('WebSocket message parse error:', e);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            // Reconnect after delay
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };

        wsRef.current = ws;
    }, []);

    useEffect(() => {
        if (!selectedSymbol && symbols.length > 0) {
            setSelectedSymbol(symbols[0]);
        }
    }, [symbols, selectedSymbol]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, []);

    // Fetch positions
    const fetchPositions = async () => {
        try {
            const res = await fetch(`${API_BASE}/trading/positions?user_id=${USER_ID}`);
            const data = await res.json();
            setPositions(data.positions || []);
        } catch (e) {
            console.error('Failed to fetch positions:', e);
        }
    };

    // Fetch trades
    const fetchTrades = async () => {
        try {
            const res = await fetch(`${API_BASE}/trading/trades?user_id=${USER_ID}`);
            const data = await res.json();
            setTrades(data.trades || []);
        } catch (e) {
            console.error('Failed to fetch trades:', e);
        }
    };

    // Initialize simulation
    const handleInit = async () => {
        setStatus('initializing');
        setError(null);

        try {
            const res = await fetch(`${API_BASE}/trading/init`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: USER_ID,
                    lookback_days: 30,
                    speed_multiplier: speedMultiplier,
                }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to initialize');
            }

            const data = await res.json();
            setSymbols(data.agent?.symbols || []);
            setStatus('stopped');

            // Connect WebSocket after init
            connectWebSocket();

            // Fetch initial data
            fetchPositions();
            fetchTrades();
        } catch (e: any) {
            setError(e.message);
            setStatus('idle');
        }
    };

    // Start simulation
    const handleStart = async () => {
        try {
            const res = await fetch(`${API_BASE}/trading/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: USER_ID }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start');
            }

            setStatus('running');
        } catch (e: any) {
            setError(e.message);
        }
    };

    // Stop simulation
    const handleStop = async () => {
        try {
            await fetch(`${API_BASE}/trading/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: USER_ID }),
            });
            setStatus('stopped');
        } catch (e: any) {
            setError(e.message);
        }
    };

    // Pause/Resume
    const handlePauseResume = async () => {
        try {
            if (status === 'paused') {
                await fetch(`${API_BASE}/trading/resume`, { method: 'POST' });
                setStatus('running');
            } else {
                await fetch(`${API_BASE}/trading/pause`, { method: 'POST' });
                setStatus('paused');
            }
        } catch (e: any) {
            setError(e.message);
        }
    };

    // Change speed
    const handleSpeedChange = async (speed: number) => {
        setSpeedMultiplier(speed);
        if (status === 'running' || status === 'paused') {
            try {
                await fetch(`${API_BASE}/trading/speed`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ speed_multiplier: speed }),
                });
            } catch (e) {
                console.error('Failed to change speed:', e);
            }
        }
    };

    // Get position for symbol
    const getPosition = (symbol: string) => positions.find((p) => p.symbol === symbol);

    // Get most recent trade for symbol
    const getRecentTrade = (symbol: string) => trades.find((t) => t.symbol === symbol);

    const handlePlaceTrade = async () => {
        if (!selectedSymbol) {
            setError('Select a symbol');
            return;
        }

        const qty = Number(tradeQty);
        if (!Number.isFinite(qty) || qty <= 0) {
            setError('Quantity must be > 0');
            return;
        }

        const sl = tradeStopLoss.trim() === '' ? null : Number(tradeStopLoss);
        const tp = tradeTakeProfit.trim() === '' ? null : Number(tradeTakeProfit);
        if (sl != null && !Number.isFinite(sl)) {
            setError('Stop loss must be a number');
            return;
        }
        if (tp != null && !Number.isFinite(tp)) {
            setError('Take profit must be a number');
            return;
        }

        setTradeSubmitting(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/trading/trade`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: USER_ID,
                    symbol: selectedSymbol,
                    side: tradeSide,
                    quantity: qty,
                    stop_loss: sl,
                    take_profit: tp,
                    reason: 'Manual trade',
                }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to place trade');
            }

            setTradeStopLoss('');
            setTradeTakeProfit('');
        } catch (e: any) {
            setError(e.message);
        } finally {
            setTradeSubmitting(false);
        }
    };

    const handleUpdateRisk = async () => {
        if (!selectedSymbol) {
            setError('Select a symbol');
            return;
        }

        const sl = tradeStopLoss.trim() === '' ? null : Number(tradeStopLoss);
        const tp = tradeTakeProfit.trim() === '' ? null : Number(tradeTakeProfit);
        if (sl != null && !Number.isFinite(sl)) {
            setError('Stop loss must be a number');
            return;
        }
        if (tp != null && !Number.isFinite(tp)) {
            setError('Take profit must be a number');
            return;
        }

        setTradeSubmitting(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/trading/positions/risk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: USER_ID,
                    symbol: selectedSymbol,
                    stop_loss: sl,
                    take_profit: tp,
                }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to update SL/TP');
            }

            await fetchPositions();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setTradeSubmitting(false);
        }
    };

    return (
        <div className="max-w-7xl mx-auto px-4 py-6">
            {/* Trade Notification Toast */}
            {notification && (
                <TradeNotification trade={notification} onDismiss={() => setNotification(null)} />
            )}

            {/* Control Bar */}
            <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 mb-6">
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2">
                        {status === 'idle' && (
                            <Button onClick={handleInit}>
                                <RefreshCw className="w-4 h-4 mr-2" />
                                Initialize
                            </Button>
                        )}

                        {status === 'initializing' && (
                            <Button disabled>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Initializing...
                            </Button>
                        )}

                        {(status === 'stopped' || status === 'paused') && (
                            <Button onClick={handleStart} variant="default">
                                <Play className="w-4 h-4 mr-2" />
                                Start
                            </Button>
                        )}

                        {status === 'running' && (
                            <>
                                <Button onClick={handlePauseResume} variant="secondary">
                                    <Pause className="w-4 h-4 mr-2" />
                                    Pause
                                </Button>
                                <Button onClick={handleStop} variant="destructive">
                                    <Square className="w-4 h-4 mr-2" />
                                    Stop
                                </Button>
                            </>
                        )}

                        {status === 'paused' && (
                            <Button onClick={handlePauseResume} variant="secondary">
                                <Play className="w-4 h-4 mr-2" />
                                Resume
                            </Button>
                        )}
                    </div>

                    {/* Speed Selector */}
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-400">Speed:</span>
                        {[1, 10, 50].map((speed) => (
                            <button
                                key={speed}
                                onClick={() => handleSpeedChange(speed)}
                                className={cn(
                                    'px-2 py-1 rounded text-xs',
                                    speedMultiplier === speed
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                )}
                            >
                                {speed}x
                            </button>
                        ))}
                    </div>

                    {/* Status */}
                    <div className="flex items-center gap-2 text-sm text-gray-400 ml-auto">
                        <div
                            className={cn(
                                'w-2 h-2 rounded-full',
                                status === 'running' ? 'bg-green-500 animate-pulse' : 'bg-gray-600'
                            )}
                        />
                        <span className="capitalize">{status}</span>
                        {currentTime && <span className="text-gray-500">| {new Date(currentTime).toLocaleTimeString()}</span>}
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="mt-3 p-2 rounded bg-red-950 border border-red-800 text-red-300 text-sm flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}
            </div>

            {/* Main Content */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Stock Tiles Grid */}
                <div className="lg:col-span-3">
                    {symbols.length === 0 ? (
                        <div className="bg-gray-900 rounded-lg border border-gray-800 p-8 text-center text-gray-500">
                            {status === 'idle' ? (
                                <div>
                                    <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p>Click "Initialize" to fetch market data and start trading</p>
                                </div>
                            ) : (
                                <div>
                                    <Loader2 className="w-8 h-8 mx-auto mb-4 animate-spin" />
                                    <p>Loading...</p>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {symbols.map((symbol) => (
                                <StockTile
                                    key={symbol}
                                    symbol={symbol}
                                    candles={candles[symbol] || []}
                                    currentPrice={candles[symbol]?.slice(-1)[0]?.close || 0}
                                    position={getPosition(symbol)}
                                    recentTrade={getRecentTrade(symbol)}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Trade Log Sidebar */}
                <div className="lg:col-span-1">
                    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 mb-6">
                        <h3 className="font-bold text-sm mb-3">Trade Ticket</h3>
                        <div className="space-y-3">
                            <div>
                                <div className="text-xs text-gray-400 mb-1">Symbol</div>
                                <select
                                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-2 text-sm"
                                    value={selectedSymbol}
                                    onChange={(e) => setSelectedSymbol(e.target.value)}
                                >
                                    {symbols.length === 0 ? (
                                        <option value="">No symbols</option>
                                    ) : (
                                        symbols.map((s) => (
                                            <option key={s} value={s}>
                                                {s}
                                            </option>
                                        ))
                                    )}
                                </select>
                            </div>

                            <div>
                                <div className="text-xs text-gray-400 mb-1">Side</div>
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        type="button"
                                        className={cn(
                                            'px-3 py-2 rounded text-sm border',
                                            tradeSide === 'buy'
                                                ? 'bg-green-900/40 border-green-700 text-green-200'
                                                : 'bg-gray-800 border-gray-700 text-gray-300'
                                        )}
                                        onClick={() => setTradeSide('buy')}
                                    >
                                        Buy
                                    </button>
                                    <button
                                        type="button"
                                        className={cn(
                                            'px-3 py-2 rounded text-sm border',
                                            tradeSide === 'sell'
                                                ? 'bg-red-900/40 border-red-700 text-red-200'
                                                : 'bg-gray-800 border-gray-700 text-gray-300'
                                        )}
                                        onClick={() => setTradeSide('sell')}
                                    >
                                        Sell
                                    </button>
                                </div>
                            </div>

                            <div>
                                <div className="text-xs text-gray-400 mb-1">Quantity</div>
                                <input
                                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-2 text-sm"
                                    value={tradeQty}
                                    onChange={(e) => setTradeQty(e.target.value)}
                                    inputMode="decimal"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                <div>
                                    <div className="text-xs text-gray-400 mb-1">Stop Loss</div>
                                    <input
                                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-2 text-sm"
                                        value={tradeStopLoss}
                                        onChange={(e) => setTradeStopLoss(e.target.value)}
                                        inputMode="decimal"
                                        placeholder="Optional"
                                    />
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400 mb-1">Take Profit</div>
                                    <input
                                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-2 text-sm"
                                        value={tradeTakeProfit}
                                        onChange={(e) => setTradeTakeProfit(e.target.value)}
                                        inputMode="decimal"
                                        placeholder="Optional"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                <Button onClick={handlePlaceTrade} disabled={tradeSubmitting || status === 'idle' || status === 'initializing'}>
                                    {tradeSubmitting ? 'Submitting…' : 'Place'}
                                </Button>
                                <Button
                                    onClick={handleUpdateRisk}
                                    variant="secondary"
                                    disabled={tradeSubmitting || status === 'idle' || status === 'initializing'}
                                >
                                    Update SL/TP
                                </Button>
                            </div>
                        </div>
                    </div>
                    <TradeLog trades={trades} />
                </div>
            </div>
        </div>
    );
}

export default TradingPage;

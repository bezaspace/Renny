import React, { useMemo } from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { ArrowUp, ArrowDown, Minus, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EnhancedIndicatorCardProps {
    indicator: string;
    data: Record<string, number[]>;
    analysis: string;
    timestamps?: string[];
}

const EnhancedIndicatorCard: React.FC<EnhancedIndicatorCardProps> = ({ indicator, data, analysis }) => {
    // Extract the main series data (assuming the first key is the main value, e.g., 'RSI' or 'MOM')
    const mainKey = Object.keys(data)[0];
    const values = data[mainKey] || [];
    const currentValue = values[values.length - 1];
    const previousValue = values[values.length - 2];

    // Calculate Trend
    const trend = useMemo(() => {
        if (values.length < 2) return 'neutral';
        return currentValue > previousValue ? 'rising' : currentValue < previousValue ? 'falling' : 'neutral';
    }, [currentValue, previousValue, values.length]);

    // Determine Signal Status (Basic logic, can be enhanced)
    const signalStatus = useMemo(() => {
        if (indicator.toUpperCase() === 'RSI') {
            if (currentValue > 70) return 'overbought';
            if (currentValue < 30) return 'oversold';
        }
        return 'neutral';
    }, [indicator, currentValue]);

    // Prepare Sparkline Data
    const sparklineData = useMemo(() => {
        return values.map((val, i) => ({ i, val }));
    }, [values]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'overbought': return 'text-red-400';
            case 'oversold': return 'text-green-400';
            default: return 'text-gray-400';
        }
    };

    const getTrendIcon = () => {
        switch (trend) {
            case 'rising': return <ArrowUp className="w-4 h-4 text-green-500" />;
            case 'falling': return <ArrowDown className="w-4 h-4 text-red-500" />;
            default: return <Minus className="w-4 h-4 text-gray-500" />;
        }
    };

    return (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 w-full max-w-sm shadow-lg">
            <div className="flex justify-between items-start mb-2">
                <div>
                    <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wider">{indicator}</h4>
                    <div className="flex items-baseline gap-2 mt-1">
                        <span className={cn("text-3xl font-bold", getStatusColor(signalStatus))}>
                            {currentValue?.toFixed(2)}
                        </span>
                        <div className="flex items-center gap-1 text-sm bg-gray-900/50 px-2 py-0.5 rounded-full">
                            {getTrendIcon()}
                            <span className={trend === 'rising' ? 'text-green-500' : trend === 'falling' ? 'text-red-500' : 'text-gray-500'}>
                                {trend.charAt(0).toUpperCase() + trend.slice(1)}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="h-12 w-24 min-w-0">
                    {/* Sparkline */}
                    <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={48}>
                        <LineChart data={sparklineData}>
                            <Line
                                type="monotone"
                                dataKey="val"
                                stroke={trend === 'rising' ? '#10B981' : trend === 'falling' ? '#EF4444' : '#9CA3AF'}
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="mt-3 pt-3 border-t border-gray-700">
                <div className="flex items-start gap-2">
                    <Activity className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-gray-300 leading-relaxed">{analysis}</p>
                </div>
            </div>

            {/* Signal Badge if applicable */}
            {signalStatus !== 'neutral' && (
                <div className={cn(
                    "mt-3 text-xs font-bold px-2 py-1 rounded inline-block",
                    signalStatus === 'overbought' ? "bg-red-900/30 text-red-400 border border-red-900" : "bg-green-900/30 text-green-400 border border-green-900"
                )}>
                    ⚠️ {signalStatus.toUpperCase()} SIGNAL
                </div>
            )}
        </div>
    );
};

export default EnhancedIndicatorCard;

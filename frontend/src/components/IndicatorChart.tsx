import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart
} from 'recharts';

interface IndicatorChartProps {
  indicator: string;
  data: Record<string, number[]>;
  timestamps?: string[];
}

const IndicatorChart: React.FC<IndicatorChartProps> = ({ indicator, data, timestamps }) => {
  const chartData = useMemo(() => {
    // Find the length of the data arrays (assuming all are same length)
    const keys = Object.keys(data);
    if (keys.length === 0) return [];
    const length = data[keys[0]].length;

    return Array.from({ length }).map((_, i) => {
      const point: any = {
        index: i,
        date: timestamps && timestamps[i] 
              ? new Date(timestamps[i]).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) 
              : i
      };
      keys.forEach(key => {
        point[key] = data[key][i];
      });
      return point;
    });
  }, [data, timestamps]);

  if (chartData.length === 0) return null;

  const renderChart = () => {
    const commonProps = {
      data: chartData,
      margin: { top: 5, right: 5, left: -20, bottom: 0 }
    };

    // Specific configuration for MACD
    if (indicator.toUpperCase() === 'MACD') {
      return (
        <ComposedChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis dataKey="date" hide />
          <YAxis stroke="#9CA3AF" fontSize={10} domain={['auto', 'auto']} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
            itemStyle={{ fontSize: '12px' }}
            labelStyle={{ color: '#9CA3AF', marginBottom: '0.25rem' }}
          />
          <Bar dataKey="Hist" fill="#60A5FA" opacity={0.5} />
          <Line type="monotone" dataKey="MACD" stroke="#F59E0B" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="Signal" stroke="#EC4899" dot={false} strokeWidth={2} />
        </ComposedChart>
      );
    }

    // Default Line Chart (RSI, MOM, etc.)
    return (
      <LineChart {...commonProps}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
        <XAxis dataKey="date" hide />
        <YAxis stroke="#9CA3AF" fontSize={10} domain={['auto', 'auto']} />
        <Tooltip 
            contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
            itemStyle={{ fontSize: '12px' }}
            labelStyle={{ color: '#9CA3AF', marginBottom: '0.25rem' }}
        />
        
        {indicator.toUpperCase() === 'RSI' && (
          <>
            <ReferenceLine y={70} stroke="#EF4444" strokeDasharray="3 3" opacity={0.5} />
            <ReferenceLine y={30} stroke="#10B981" strokeDasharray="3 3" opacity={0.5} />
          </>
        )}

        {Object.keys(data).map((key) => (
          <Line 
            key={key}
            type="monotone" 
            dataKey={key} 
            stroke="#8B5CF6" 
            dot={false} 
            strokeWidth={2} 
          />
        ))}
      </LineChart>
    );
  };

  return (
    <div className="h-32 w-full mt-3 bg-gray-900/50 rounded border border-gray-800 p-2">
      <ResponsiveContainer width="100%" height="100%">
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
};

export default IndicatorChart;
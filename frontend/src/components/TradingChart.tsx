import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

interface ChartDataPoint {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface TradingChartProps {
  data: ChartDataPoint[];
  symbol: string;
}

const TradingChart: React.FC<TradingChartProps> = ({ data, symbol }) => {
  // Format date for XAxis
  const formattedData = data.map(item => ({
    ...item,
    date: new Date(item.timestamp).toLocaleDateString(),
  }));

  return (
    <div className="w-full h-64 bg-gray-900 rounded-lg p-4 mt-2">
      <h3 className="text-white text-sm font-bold mb-2">{symbol} - Daily Close</h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={formattedData}
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 5,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="date" stroke="#9CA3AF" fontSize={12} tickFormatter={(value) => value.split('/')[0] + '/' + value.split('/')[1]} />
          <YAxis stroke="#9CA3AF" fontSize={12} domain={['auto', 'auto']} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '0.5rem' }}
            itemStyle={{ color: '#F3F4F6' }}
          />
          <Legend />
          <Line type="monotone" dataKey="close" stroke="#8884d8" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TradingChart;

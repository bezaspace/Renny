import React, { useState, useMemo } from 'react';
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
  [key: string]: any; // Allow dynamic keys for indicators
}

interface TradingChartProps {
  data: ChartDataPoint[];
  symbol: string;
  overlays?: Record<string, number[] | Record<string, number[]>>;
}

const TradingChart: React.FC<TradingChartProps> = ({ data, symbol, overlays }) => {
  const [activeOverlay, setActiveOverlay] = useState<string | null>(null);

  // Get list of available overlays
  const availableOverlays = overlays ? Object.keys(overlays) : [];

  // Merge overlay data into chart data
  const mergedData = useMemo(() => {
    if (!activeOverlay || !overlays || !overlays[activeOverlay]) {
        // Just format the date
        return data.map(item => ({
            ...item,
            date: new Date(item.timestamp).toLocaleDateString('en-US', {month:'short', day:'numeric'}),
        }));
    }

    const overlayData = overlays[activeOverlay];
    const isComplex = !Array.isArray(overlayData);

    return data.map((item, index) => {
      const newItem: any = {
        ...item,
        date: new Date(item.timestamp).toLocaleDateString('en-US', {month:'short', day:'numeric'}),
      };

      if (isComplex) {
        // BBANDS etc. -> { upper: [...], middle: [...] }
        Object.entries(overlayData as Record<string, number[]>).forEach(([key, series]) => {
           newItem[key] = series[index];
        });
      } else {
        // SMA etc. -> [...]
        newItem[activeOverlay] = (overlayData as number[])[index];
      }
      return newItem;
    });
  }, [data, activeOverlay, overlays]);

  const renderOverlayLines = () => {
    if (!activeOverlay || !overlays) return null;
    
    const overlayData = overlays[activeOverlay];
    
    if (Array.isArray(overlayData)) {
       return (
         <Line 
            type="monotone" 
            dataKey={activeOverlay} 
            stroke="#10B981" // Emerald 500
            dot={false} 
            strokeWidth={2} 
            name={activeOverlay}
         />
       );
    } else {
        // Render multiple lines with distinct colors
        const colors = ["#F59E0B", "#EC4899", "#6366F1", "#8B5CF6"]; // Amber, Pink, Indigo, Violet
        return Object.keys(overlayData).map((key, idx) => (
            <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[idx % colors.length]}
                dot={false}
                strokeWidth={1.5}
                name={key}
            />
        ));
    }
  };

  return (
    <div className="w-full bg-gray-900 rounded-lg p-4 mt-2 border border-gray-800">
      <div className="flex justify-between items-center mb-4">
          <h3 className="text-white text-sm font-bold">{symbol} - Daily Close</h3>
          
          {/* Overlay Controls */}
          {availableOverlays.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-end">
                <span className="text-xs text-gray-400 self-center mr-1">Overlays:</span>
                {availableOverlays.map(ov => (
                    <button
                        key={ov}
                        onClick={() => setActiveOverlay(activeOverlay === ov ? null : ov)}
                        className={`text-xs px-2 py-1 rounded border transition-colors ${
                            activeOverlay === ov 
                            ? 'bg-blue-600 border-blue-500 text-white' 
                            : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
                        }`}
                    >
                        {ov}
                    </button>
                ))}
            </div>
          )}
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={mergedData}
            margin={{
              top: 5,
              right: 30,
              left: 10, // Reduced left margin
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
            <XAxis 
                dataKey="date" 
                stroke="#9CA3AF" 
                fontSize={10} 
                tickMargin={5}
                minTickGap={30}
            />
            <YAxis 
                stroke="#9CA3AF" 
                fontSize={10} 
                domain={['auto', 'auto']} 
                tickFormatter={(val) => val.toFixed(0)}
                width={40}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '0.5rem' }}
              itemStyle={{ color: '#F3F4F6', fontSize: '12px' }}
              labelStyle={{ color: '#9CA3AF', marginBottom: '0.25rem' }}
            />
            <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px' }}/>
            
            {/* Main Price Line */}
            <Line 
                type="monotone" 
                dataKey="close" 
                stroke="#8884d8" 
                dot={false} 
                strokeWidth={2} 
                name="Price"
                activeDot={{ r: 4, fill: '#fff' }}
            />
            
            {/* Overlay Lines */}
            {renderOverlayLines()}
            
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TradingChart;

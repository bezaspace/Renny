import React, { useState, useRef, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Send, Bot, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import TradingChart from './TradingChart';
import IndicatorChart from './IndicatorChart';
import EnhancedIndicatorCard from './EnhancedIndicatorCard';
import { cn } from '@/lib/utils';

interface Message {
  type: 'human' | 'ai' | 'tool';
  content: string;
  tool_calls?: any[];
  id?: string;
}

interface ChartData {
  symbol: string;
  data: any[];
  message?: string;
  values?: Record<string, number[]>; // For indicators
  timestamps?: string[];
  overlays?: Record<string, any>;
  indicator?: string;
  analysis?: string;
  series?: Record<string, any>;
  patterns?: Array<{ name: string; direction: string; strength: number; timestamp: string }>;
  pattern_markers?: Array<{ timestamp: string; pattern: string; direction: string; strength: number }>;
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [threadId] = useState(() => `thread_${Date.now()}`);

  const layoutRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [chatPanelWidth, setChatPanelWidth] = useState(480);

  const chatMessages = useMemo(() => messages.filter(m => m.type !== 'tool'), [messages]);
  const toolMessages = useMemo(() => messages.filter(m => m.type === 'tool'), [messages]);

  const [selectedToolIndex, setSelectedToolIndex] = useState<number>(-1);
  const [pinnedToLatest, setPinnedToLatest] = useState(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages]);

  useEffect(() => {
    if (toolMessages.length === 0) {
      setSelectedToolIndex(-1);
      setPinnedToLatest(true);
      return;
    }

    if (pinnedToLatest) {
      setSelectedToolIndex(toolMessages.length - 1);
      return;
    }

    setSelectedToolIndex(prev => Math.max(0, Math.min(prev, toolMessages.length - 1)));
  }, [toolMessages.length, pinnedToLatest]);

  useEffect(() => {
    if (!isResizing) return;

    const onMouseMove = (e: MouseEvent) => {
      if (!layoutRef.current) return;

      const rect = layoutRef.current.getBoundingClientRect();
      const nextWidth = e.clientX - rect.left;

      const minChat = 320;
      const minVisual = 360;
      const maxChat = Math.max(minChat, rect.width - minVisual);

      setChatPanelWidth(Math.max(minChat, Math.min(nextWidth, maxChat)));
    };

    const onMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg: Message = { type: 'human', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        message: userMsg.content,
        thread_id: threadId
      });

      // The backend returns the FULL list of messages or the delta?
      // backend/main.py returns: "messages": serialized_messages
      // And serialized_messages is from agent.invoke(), which returns the FINAL state.
      // So it returns ALL messages in the thread.
      // We should replace our local messages with the server state to ensure sync,
      // or just append the new ones. Since we don't have complex optimistic updates, 
      // replacing is safer but might cause flickering.
      // Let's just take the messages from response which are NEW (after our last known one)
      // or simpler: just use the response messages as the source of truth.

      setMessages(response.data.messages);
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages(prev => [...prev, { type: 'ai', content: "Sorry, I encountered an error." }]);
    } finally {
      setLoading(false);
    }
  };

  const renderToolContent = (msg: Message) => {
    try {
      const parsedContent: ChartData = JSON.parse(msg.content);

        // Check if it is stock chart data
        if (parsedContent.data && Array.isArray(parsedContent.data) && parsedContent.symbol) {
          return (
            <div className="w-full space-y-4">
              <div className="w-full">
                <p className="mb-2 text-gray-300">{parsedContent.message}</p>
                <TradingChart
                  data={parsedContent.data}
                  symbol={parsedContent.symbol}
                  overlays={parsedContent.overlays}
                  patternMarkers={parsedContent.pattern_markers}
                />
              </div>

              {parsedContent.patterns && parsedContent.patterns.length > 0 && (
                <div className="bg-gray-900/50 rounded border border-gray-800 p-3">
                  <h4 className="text-sm font-bold text-gray-200 mb-2">Candlestick Patterns</h4>
                  <div className="space-y-2">
                    {parsedContent.patterns.map((p, idx) => (
                      <div key={idx} className="flex items-center justify-between text-sm">
                        <div className="text-gray-200">
                          {p.name}
                          <span className={cn(
                            "ml-2 text-xs px-2 py-0.5 rounded border",
                            p.direction === 'bullish'
                              ? 'border-green-700 text-green-400 bg-green-900/20'
                              : 'border-red-700 text-red-400 bg-red-900/20'
                          )}>
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

              {/* Render Indicator Grid if series data is present */}
              {parsedContent.series && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
                  {Object.entries(parsedContent.series).map(([indName, indData]) => {
                    const simpleIndicators = ['RSI', 'MOM', 'ADX', 'ATR', 'CCI', 'DX', 'WILLR'];

                    if (simpleIndicators.includes(indName)) {
                      return (
                        <EnhancedIndicatorCard
                          key={indName}
                          indicator={indName}
                          data={indData as Record<string, number[]>}
                          analysis={`${indName} Analysis`} // Simplified analysis for grid
                          timestamps={parsedContent.timestamps}
                        />
                      );
                    } else {
                      // Complex indicators (MACD, STOCH, etc.)
                      return (
                        <div key={indName} className="bg-gray-800 p-3 rounded-md border border-gray-700">
                          <h5 className="font-bold text-blue-400 text-sm mb-1">{indName}</h5>
                          <IndicatorChart
                            indicator={indName}
                            data={indData as Record<string, number[]>}
                            timestamps={parsedContent.timestamps}
                          />
                        </div>
                      );
                    }
                  })}
                </div>
              )}
            </div>
          );
        }

        // Check if it is indicator data
        if (parsedContent.indicator && parsedContent.analysis) {
          const indicatorName = parsedContent.indicator.toUpperCase();
          const simpleIndicators = ['RSI', 'MOM', 'ADX', 'ATR']; // Add more as needed

          if (simpleIndicators.includes(indicatorName) && parsedContent.values) {
            return (
              <EnhancedIndicatorCard
                indicator={parsedContent.indicator}
                data={parsedContent.values}
                analysis={parsedContent.analysis}
                timestamps={parsedContent.timestamps}
              />
            );
          }

          // Default to Mini Chart for complex indicators (MACD, STOCH, etc.)
          return (
            <div className="bg-gray-800 p-4 rounded-md border border-gray-700 w-full">
              <h4 className="font-bold text-blue-400 mb-1">{parsedContent.indicator} Analysis for {parsedContent.symbol}</h4>
              <p className="text-gray-300 text-sm mb-2">{parsedContent.analysis}</p>

              {parsedContent.values && (
                <IndicatorChart
                  indicator={parsedContent.indicator}
                  data={parsedContent.values}
                  timestamps={parsedContent.timestamps}
                />
              )}
            </div>
          );
        }

      return <pre className="whitespace-pre-wrap text-xs text-gray-400 bg-gray-900 p-2 rounded overflow-x-auto">{JSON.stringify(parsedContent, null, 2)}</pre>;
    } catch (e) {
      return <span className="text-gray-400 italic text-sm">Tool output: {msg.content}</span>;
    }
  };

  const renderChatContent = (msg: Message) => {
    return <span className="whitespace-pre-wrap">{msg.content}</span>;
  };

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      <header className="p-4 border-b border-gray-800 bg-gray-900 flex items-center gap-2">
        <Bot className="w-6 h-6 text-blue-500" />
        <h1 className="text-xl font-bold">TradeAI Analyst</h1>
      </header>

      <div
        ref={layoutRef}
        style={{ ['--chat-panel-width' as any]: `${chatPanelWidth}px` }}
        className="flex-1 flex flex-col lg:flex-row overflow-hidden"
      >
        <div className="flex flex-col lg:w-[var(--chat-panel-width)] border-b border-gray-800 lg:border-b-0 lg:border-r bg-gray-950 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={cn(
                  "w-full"
                )}
              >
                <div
                  className={cn(
                    "flex-1 min-w-0 border-l-2 pl-3 py-1 transition-colors hover:bg-white/5",
                    msg.type === 'human' ? "border-green-500/40" : "border-blue-500/40"
                  )}
                >
                  <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-gray-400 mb-1">
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full flex-shrink-0",
                        msg.type === 'human' ? "bg-green-500" : "bg-blue-500"
                      )}
                      aria-hidden="true"
                    />
                    <span>{msg.type === 'human' ? 'You' : 'Agent'}</span>
                  </div>
                  <div className="text-sm leading-relaxed">
                    {renderChatContent(msg)}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="w-full">
                <div className="flex-1 min-w-0 border-l-2 border-blue-500/40 pl-3 py-1">
                  <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-gray-400 mb-1">
                    <span className="h-2 w-2 rounded-full flex-shrink-0 bg-blue-500" aria-hidden="true" />
                    <span>Agent</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-300">
                    <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    <span>Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 bg-gray-900 border-t border-gray-800">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Ask about a stock (e.g., 'Show me Reliance chart')..."
                className="flex-1 bg-gray-800 border border-gray-700 rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                disabled={loading}
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-md transition-colors"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
        </div>

        <div className="hidden lg:block w-1 bg-gray-900 hover:bg-gray-800 relative">
          <div
            role="separator"
            aria-orientation="vertical"
            onMouseDown={() => setIsResizing(true)}
            className={cn(
              "absolute inset-0 cursor-col-resize",
              isResizing ? "bg-gray-700" : "bg-transparent"
            )}
          />
        </div>

        <div className="flex-1 flex flex-col bg-gray-950 overflow-hidden">
          <div className="p-3 bg-gray-900 border-b border-gray-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setPinnedToLatest(false);
                  setSelectedToolIndex(prev => Math.max(0, prev - 1));
                }}
                disabled={toolMessages.length === 0 || selectedToolIndex <= 0}
                className="p-2 rounded border border-gray-700 bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700"
                aria-label="Previous visual"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() => {
                  setPinnedToLatest(false);
                  setSelectedToolIndex(prev => Math.min(toolMessages.length - 1, prev + 1));
                }}
                disabled={toolMessages.length === 0 || selectedToolIndex >= toolMessages.length - 1}
                className="p-2 rounded border border-gray-700 bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700"
                aria-label="Next visual"
              >
                <ChevronRight className="w-4 h-4" />
              </button>

              <div className="text-sm text-gray-300 ml-2">
                {toolMessages.length === 0 || selectedToolIndex < 0
                  ? "0 / 0"
                  : `${selectedToolIndex + 1} / ${toolMessages.length}`}
              </div>
            </div>

            {toolMessages.length > 0 && (!pinnedToLatest || selectedToolIndex !== toolMessages.length - 1) && (
              <button
                type="button"
                onClick={() => {
                  setPinnedToLatest(true);
                  setSelectedToolIndex(toolMessages.length - 1);
                }}
                className="text-xs px-3 py-1 rounded border border-gray-700 bg-gray-800 hover:bg-gray-700"
              >
                Latest
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {toolMessages.length === 0 || selectedToolIndex < 0 ? (
              <div className="h-full w-full flex items-center justify-center text-gray-400 text-sm">
                No visuals yet. Ask for a chart to see it here.
              </div>
            ) : (
              <div className="w-full">
                {renderToolContent(toolMessages[selectedToolIndex])}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;

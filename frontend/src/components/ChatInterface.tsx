import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import TradingChart from './TradingChart';
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
  values?: any; // For indicators
  indicator?: string;
  analysis?: string;
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [threadId] = useState(() => `thread_${Date.now()}`);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

  const renderMessageContent = (msg: Message) => {
    if (msg.type === 'tool') {
      try {
        const parsedContent: ChartData = JSON.parse(msg.content);
        
        // Check if it is stock chart data
        if (parsedContent.data && Array.isArray(parsedContent.data) && parsedContent.symbol) {
          return (
            <div className="w-full">
              <p className="mb-2 text-gray-300">{parsedContent.message}</p>
              <TradingChart data={parsedContent.data} symbol={parsedContent.symbol} />
            </div>
          );
        }
        
        // Check if it is indicator data
        if (parsedContent.indicator && parsedContent.analysis) {
             return (
                <div className="bg-gray-800 p-4 rounded-md border border-gray-700">
                    <h4 className="font-bold text-blue-400 mb-1">{parsedContent.indicator} Analysis for {parsedContent.symbol}</h4>
                    <p className="text-gray-300">{parsedContent.analysis}</p>
                    {/* Could plot values here too if implemented */}
                </div>
             );
        }

        return <pre className="whitespace-pre-wrap text-xs text-gray-400 bg-gray-900 p-2 rounded overflow-x-auto">{JSON.stringify(parsedContent, null, 2)}</pre>;
      } catch (e) {
        return <span className="text-gray-400 italic text-sm">Tool output: {msg.content}</span>;
      }
    }
    return <span className="whitespace-pre-wrap">{msg.content}</span>;
  };

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      <header className="p-4 border-b border-gray-800 bg-gray-900 flex items-center gap-2">
        <Bot className="w-6 h-6 text-blue-500" />
        <h1 className="text-xl font-bold">TradeAI Analyst</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={cn(
              "flex gap-3 max-w-3xl",
              msg.type === 'human' ? "ml-auto flex-row-reverse" : "",
              msg.type === 'tool' ? "w-full max-w-4xl mx-auto" : "" // Tools take full width
            )}
          >
            {msg.type !== 'human' && msg.type !== 'tool' && (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <Bot size={16} />
              </div>
            )}
            {msg.type === 'human' && (
              <div className="w-8 h-8 rounded-full bg-green-600 flex items-center justify-center flex-shrink-0">
                <User size={16} />
              </div>
            )}

            <div
              className={cn(
                "rounded-lg p-3",
                msg.type === 'human' ? "bg-green-700 text-white" : 
                msg.type === 'ai' ? "bg-gray-800 text-gray-100" :
                "bg-transparent w-full p-0" // Tool container
              )}
            >
              {renderMessageContent(msg)}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
             <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <Bot size={16} />
              </div>
              <div className="bg-gray-800 p-3 rounded-lg flex items-center">
                <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
              </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-gray-900 border-t border-gray-800">
        <div className="flex gap-2 max-w-4xl mx-auto">
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
  );
};

export default ChatInterface;

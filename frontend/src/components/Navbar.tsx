import { NavLink } from 'react-router-dom';
import { Bot, ClipboardList } from 'lucide-react';

const linkBase = 'px-3 py-2 rounded-md text-sm border transition-colors';

function Navbar() {
  return (
    <header className="border-b border-gray-800 bg-gray-900 text-gray-100">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-blue-500" />
          <div className="font-bold">TradeAI Analyst</div>
        </div>

        <nav className="flex items-center gap-2">
          <NavLink
            to="/onboarding"
            className={({ isActive }: { isActive: boolean }) =>
              `${linkBase} ${
                isActive
                  ? 'bg-gray-800 border-gray-700 text-white'
                  : 'bg-gray-950 border-gray-800 text-gray-300 hover:bg-gray-800'
              }`
            }
          >
            <span className="inline-flex items-center gap-2">
              <ClipboardList className="w-4 h-4" />
              Onboarding
            </span>
          </NavLink>

          <NavLink
            to="/chat"
            className={({ isActive }: { isActive: boolean }) =>
              `${linkBase} ${
                isActive
                  ? 'bg-gray-800 border-gray-700 text-white'
                  : 'bg-gray-950 border-gray-800 text-gray-300 hover:bg-gray-800'
              }`
            }
          >
            Chat
          </NavLink>
        </nav>
      </div>
    </header>
  );
}

export default Navbar;

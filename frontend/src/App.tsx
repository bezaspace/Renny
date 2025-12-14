import { Navigate, Route, Routes } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import Navbar from './components/Navbar';
import OnboardingPage from './pages/OnboardingPage';
import TradingPage from './pages/TradingPage';

function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Navbar />
      <Routes>
        <Route path="/" element={<Navigate to="/onboarding" replace />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/chat" element={<ChatInterface />} />
        <Route path="/trading" element={<TradingPage />} />
        <Route path="*" element={<Navigate to="/onboarding" replace />} />
      </Routes>
    </div>
  );
}

export default App;
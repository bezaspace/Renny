import { Navigate, Route, Routes } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import Navbar from './components/Navbar';
import OnboardingPage from './pages/OnboardingPage';

function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Navbar />
      <Routes>
        <Route path="/" element={<Navigate to="/onboarding" replace />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/chat" element={<ChatInterface />} />
        <Route path="*" element={<Navigate to="/onboarding" replace />} />
      </Routes>
    </div>
  );
}

export default App;
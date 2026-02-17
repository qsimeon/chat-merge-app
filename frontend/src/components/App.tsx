import { useEffect } from 'react';
import { useStore } from '../store';
import Sidebar from './Sidebar';
import ChatArea from './ChatArea';
import SettingsModal from './SettingsModal';
import MergeModal from './MergeModal';

function App() {
  const loadChats = useStore((state) => state.loadChats);
  const loadApiKeys = useStore((state) => state.loadApiKeys);
  const checkHealth = useStore((state) => state.checkHealth);
  const showSettings = useStore((state) => state.showSettings);
  const showMerge = useStore((state) => state.showMerge);

  useEffect(() => {
    loadChats();
    loadApiKeys();
    checkHealth();
  }, []);

  return (
    <div className="app-layout">
      <Sidebar />
      <ChatArea />
      {showSettings && <SettingsModal />}
      {showMerge && <MergeModal />}
    </div>
  );
}

export default App;

import { useEffect, useState } from 'react';
import { useTheme } from '../theme';

export default function StatusBar() {
  const [online, setOnline] = useState(true);
  const { toggle } = useTheme();
  useEffect(() => {
    const id = setInterval(() => {
      fetch('/status')
        .then(() => setOnline(true))
        .catch(() => setOnline(false));
    }, 3000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="border-t p-1 text-sm flex justify-between items-center">
      <span>LLM: gpt-4-turbo</span>
      <div className="flex items-center gap-2">
        <span className={online ? 'text-green-600' : 'text-red-600'}>
          {online ? 'Connected' : 'Disconnected'}
        </span>
        <button onClick={toggle} className="border px-1 text-xs">Toggle Theme</button>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';

interface Item {
  id: string;
  type: string;
  summary: string;
  timestamp: string;
}

export default function InboxOverview() {
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<Item | null>(null);

  useEffect(() => {
    fetch('/api/inbox')
      .then((r) => r.json())
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  return (
    <div className="border p-2 flex gap-4">
      <ul className="w-1/2 max-h-48 overflow-auto">
        {items.map((it) => (
          <li key={it.id} className="flex justify-between mb-1">
            <span>{it.summary}</span>
            <button className="border px-1" onClick={() => setSelected(it)}>
              Review
            </button>
          </li>
        ))}
      </ul>
      <div className="flex-1 border p-2 min-h-24">
        {selected && (
          <pre>{JSON.stringify(selected, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import FiberCard from './FiberCard.js';
import { useZorosStore, Fiber } from '../hooks/useZorosStore.js';

export function filterFibers(list: Fiber[], query: string): Fiber[] {
  const q = query.toLowerCase();
  return list.filter(
    (f) =>
      f.content.toLowerCase().includes(q) ||
      (f.tags || '').toLowerCase().includes(q)
  );
}

export default function FiberCardViewer() {
  const {
    fibers,
    setFibers,
    filter,
    setFilter,
    selectedThread,
  } = useZorosStore();

  useEffect(() => {
    const param = selectedThread || 'none';
    fetch(`/api/fibers?thread=${param}`)
      .then((r) => r.json())
      .then(setFibers)
      .catch(() => setFibers([]));
  }, [selectedThread, setFibers]);

  const filtered = filterFibers(fibers, filter);

  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const onDrop = (idx: number) => {
    if (dragIndex === null || dragIndex === idx) return;
    const newOrder = [...fibers];
    const [moved] = newOrder.splice(dragIndex, 1);
    newOrder.splice(idx, 0, moved);
    setFibers(newOrder);
    setDragIndex(null);
    if (selectedThread) {
      fetch(`/api/threads/${selectedThread}/reorder`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: newOrder.map((f) => f.id) }),
      }).catch(() => {});
    }
  };

  return (
    <section className="border p-2 flex flex-col">
      <div className="flex mb-2 gap-2 items-center">
        <h2 className="font-bold flex-1">
          {selectedThread ? `Thread: ${selectedThread}` : 'Inbox'}
        </h2>
        <input
          placeholder="Search..."
          className="border p-1 text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>
      <ul className="list-none p-0">
        {filtered.map((f, i) => (
          <li
            key={f.id}
            draggable={!!selectedThread}
            onDragStart={() => setDragIndex(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(i)}
          >
            <FiberCard fiber={f} />
          </li>
        ))}
        {filtered.length === 0 && <li>No fibers match your search.</li>}
      </ul>
    </section>
  );
}

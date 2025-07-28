import { useState } from 'react';

export default function QuickTaskLauncher() {
  const [task, setTask] = useState('');

  async function create() {
    if (!task.trim()) return;
    await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: task }),
    });
    setTask('');
  }

  return (
    <div className="border p-2 flex gap-2 items-center">
      <input
        className="border flex-1 p-1"
        placeholder="Enter a new task…"
        value={task}
        onChange={(e) => setTask(e.target.value)}
      />
      <button onClick={create} className="border px-2">Create Task</button>
    </div>
  );
}

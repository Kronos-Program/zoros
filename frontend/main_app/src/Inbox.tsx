import React, { useEffect, useState } from "react";

export default function Inbox() {
  const [tasks, setTasks] = useState([]);

  useEffect(() => {
    fetch("/api/inbox")
      .then((r) => r.json())
      .then(setTasks)
      .catch(() => setTasks([]));
  }, []);

  const sendToCodex = async (id: number) => {
    await fetch(`/api/tasks/${id}/annotate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: "gpt-4-turbo" }),
    });
    const res = await fetch("/api/inbox");
    setTasks(await res.json());
  };

  return (
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Title</th>
          <th>Created At</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((t: any) => (
          <tr key={t.id}>
            <td>{t.id}</td>
            <td>{t.title}</td>
            <td>{t.created_at}</td>
            <td>{t.status}</td>
            <td>
              <button onClick={() => sendToCodex(t.id)}>Send to Codex</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

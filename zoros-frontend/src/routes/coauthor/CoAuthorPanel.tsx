import React, { useEffect, useState } from 'react';

interface Block {
  before: string;
  after: string;
}

export default function CoAuthorPanel() {
  const [files, setFiles] = useState<string[]>([]);
  const [path, setPath] = useState('');
  const [blocks, setBlocks] = useState<Block[]>([]);

  useEffect(() => {
    fetch('/api/coauthor/docs')
      .then(r => r.json())
      .then(setFiles)
      .catch(() => setFiles([]));
  }, []);

  const loadFile = (p: string) => {
    fetch(`/api/coauthor/doc?path=${encodeURIComponent(p)}`)
      .then(r => r.json())
      .then(d => {
        const parts = d.content.split(/\n(?=## )/g).filter(Boolean);
        setBlocks(parts.map(t => ({ before: t.trim(), after: t.trim() })));
        setPath(p);
      });
  };

  const updateBlock = (i: number, text: string) => {
    const copy = [...blocks];
    copy[i].after = text;
    setBlocks(copy);
  };

  const rewriteBlock = async (idx: number) => {
    const resp = await fetch('/api/coauthor/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: blocks[idx].after })
    });
    const data = await resp.json();
    updateBlock(idx, data.text);
  };

  const save = async () => {
    await fetch('/api/coauthor/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, blocks })
    });
  };

  return (
    <div className="flex h-screen">
      <aside className="border-r p-2 w-48 flex flex-col gap-2">
        <select value={path} onChange={e => loadFile(e.target.value)}>
          <option value="">Select file</option>
          {files.map(f => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
        <button className="border p-1 text-sm" disabled>Auto Summarize</button>
        <button className="border p-1 text-sm" disabled>Auto Expand</button>
      </aside>
      <main className="flex-1 p-2 overflow-y-auto">
        {blocks.map((b, i) => (
          <div key={i} className="mb-4">
            <textarea
              className="border w-full p-1"
              value={b.after}
              onChange={e => updateBlock(i, e.target.value)}
              rows={4}
            />
            <div className="mt-1">
              <button className="border px-2 text-sm" onClick={() => rewriteBlock(i)}>Rewrite</button>
            </div>
          </div>
        ))}
        {path && (
          <button className="border px-2" onClick={save}>Save</button>
        )}
      </main>
    </div>
  );
}

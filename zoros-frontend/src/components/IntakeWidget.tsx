import { useState } from 'react';

export default function IntakeWidget() {
  const [recording, setRecording] = useState(false);
  const [model, setModel] = useState('large-turbo-v3');
  const [text, setText] = useState('');

  async function toggleRecording() {
    if (!recording) {
      await fetch('/api/dictate/start', { method: 'POST' });
      setRecording(true);
    } else {
      const resp = await fetch('/api/dictate/stop', { method: 'POST' });
      const data = await resp.json();
      setText(data.text || '');
      setRecording(false);
    }
  }

  async function submit() {
    await fetch('/api/fibers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    setText('');
  }

  return (
    <div className="border p-2 flex flex-col gap-2">
      <div className="flex gap-2 items-center">
        <button onClick={toggleRecording} className="border px-2">
          {recording ? 'Stop Recording' : 'Start Recording'}
        </button>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="large-turbo-v3">large-turbo-v3</option>
          <option value="whisper-tiny">whisper-tiny</option>
          <option value="offline">local offline</option>
        </select>
      </div>
      <textarea
        className="border p-1"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
      />
      <button onClick={submit} className="border px-2 self-start">Submit to Fiber</button>
    </div>
  );
}

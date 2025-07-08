import React, { useState } from 'react';
import { Fiber } from '../hooks/useZorosStore';

interface Props {
  fiber: Fiber;
}

export default function FiberCard({ fiber }: Props) {
  const [expanded, setExpanded] = useState(false);
  const tags = fiber.tags
    ? fiber.tags.split(/[,\s]+/).filter((t) => t)
    : [];

  const contentPreview =
    !expanded && fiber.content.length > 100
      ? fiber.content.slice(0, 100) + '…'
      : fiber.content;

  return (
    <li
      className="border rounded p-2 mb-2 bg-white shadow-sm"
      aria-label={`Fiber: ${fiber.content.slice(0, 30)}`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span role="img" aria-label="text">📝</span>
        <strong className="flex-1 truncate">
          {fiber.content.slice(0, 60)}
        </strong>
      </div>
      <div className="text-xs text-gray-600 mb-1">
        {new Date(fiber.created_at).toLocaleString()} • {fiber.source}
      </div>
      <div className="mb-1">
        {tags.map((t) => (
          <span key={t} className="border px-1 mr-1 text-xs">#{t}</span>
        ))}
      </div>
      <p className="whitespace-pre-wrap">
        {contentPreview}
        {fiber.content.length > 100 && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="ml-1 text-blue-600 underline text-xs"
          >
            {expanded ? 'Read less' : 'Read more'}
          </button>
        )}
      </p>
      <div className="mt-1 flex gap-1">
        <button className="border px-2 text-xs">Edit</button>
        <button className="border px-2 text-xs">Tag</button>
        <button className="border px-2 text-xs">⋮</button>
      </div>
    </li>
  );
}

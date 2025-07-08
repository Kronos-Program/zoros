import { test } from 'node:test';
import assert from 'node:assert/strict';
import { filterFibers } from '../zoros-frontend/dist/components/FiberCardViewer.js';

const data = [
  { id: '1', content: 'hello world', tags: 'foo', created_at: '', source: '' },
  { id: '2', content: 'another note', tags: 'bar', created_at: '', source: '' },
];

test('filterFibers matches content', () => {
  const res = filterFibers(data, 'hello');
  assert.equal(res.length, 1);
  assert.equal(res[0].id, '1');
});

test('filterFibers matches tags', () => {
  const res = filterFibers(data, 'bar');
  assert.equal(res.length, 1);
  assert.equal(res[0].id, '2');
});

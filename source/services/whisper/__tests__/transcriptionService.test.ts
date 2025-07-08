import { strict as assert } from 'assert';
import { test } from 'node:test';
import { transcribeRawAudio } from '../transcriptionService.js';

test('transcribeRawAudio returns result shape', async () => {
  const buffer = new ArrayBuffer(4);
  const res = await transcribeRawAudio(buffer, 'wav');
  assert.equal(typeof res.text, 'string');
  assert.equal(typeof res.confidence, 'number');
  assert.ok(Array.isArray(res.timestamps));
});

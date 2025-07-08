/**
 * Transcription service used by Intake UI.
 * See "Intake UI \u21c4 Backend Integration" in the UI architecture doc.
 */
import fs from 'fs/promises';
import { AudioFormat, TranscriptionResult } from './whisperTypes.js';

function fakeTranscription(dataLen: number): TranscriptionResult {
  return {
    text: `transcribed ${dataLen} bytes`,
    confidence: 1,
    timestamps: [],
  };
}

export async function transcribeAudioFile(filePath: string): Promise<TranscriptionResult> {
  try {
    const buf = await fs.readFile(filePath);
    return fakeTranscription(buf.byteLength);
  } catch (err) {
    return Promise.reject(err);
  }
}

export async function transcribeRawAudio(buffer: ArrayBuffer, format: AudioFormat): Promise<TranscriptionResult> {
  try {
    const len = buffer.byteLength + format.length; // fake usage
    return fakeTranscription(len);
  } catch (err) {
    return Promise.reject(err);
  }
}

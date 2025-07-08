/**
 * Intake UI helper to invoke the Whisper backend.
 * References "Intake UI \u21c4 Backend Integration" in the UI architecture doc.
 */
import { transcribeRawAudio, TranscriptionResult } from '../../../services/whisper';

export async function requestTranscription(blob: Blob): Promise<TranscriptionResult> {
  const buffer = await blob.arrayBuffer();
  return transcribeRawAudio(buffer, 'wav');
}

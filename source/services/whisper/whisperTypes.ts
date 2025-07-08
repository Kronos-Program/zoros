/**
 * Whisper service types.
 * Refer to "Module Consolidation" in the backend architecture doc.
 */

export type AudioFormat = 'wav' | 'mp3' | 'ogg';

export interface TranscriptionSegment {
  start: number;
  end: number;
}

export interface TranscriptionResult {
  text: string;
  confidence: number;
  timestamps: TranscriptionSegment[];
}

/**
 * useAudioRecorder - stub for recording audio.
 * Refer to "Intake UI" architecture section.
 */
import { requestTranscription } from '../services/whisperClient';
import { useZorosStore } from '../common/hooks/useZorosStore';

export function useAudioRecorder() {
  const {
    setTranscriptionPending,
    setTranscriptionResult,
    setTranscriptionError,
  } = useZorosStore();

  return {
    startRecording() {
      console.log('startRecording');
    },
    async stopRecording() {
      console.log('stopRecording');
      const dummy = new Blob();
      setTranscriptionPending();
      try {
        const result = await requestTranscription(dummy);
        setTranscriptionResult({ ...result, status: 'fulfilled' });
      } catch (err) {
        setTranscriptionError((err as Error).message);
      }
    },
  };
}

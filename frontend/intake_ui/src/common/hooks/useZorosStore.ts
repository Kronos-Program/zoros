import React from 'react';

interface TranscriptionSegment {
  start: number;
  end: number;
}

interface TranscriptionState {
  text: string;
  confidence: number;
  timestamps: TranscriptionSegment[];
  status: 'idle' | 'pending' | 'fulfilled' | 'error';
  error?: string;
}

interface ZorosState {
  isRecording: boolean;
  transcriptionMode: 'push-to-talk' | 'wake-word';
  currentText: string;
  droppedFiles: File[];
  transcription: TranscriptionState;
  toggleRecording: () => void;
  setTranscriptionMode: (mode: 'push-to-talk' | 'wake-word') => void;
  setCurrentText: (text: string) => void;
  addDroppedFiles: (files: File[]) => void;
  setTranscriptionPending: () => void;
  setTranscriptionResult: (r: TranscriptionState) => void;
  setTranscriptionError: (msg: string) => void;
}

const StoreContext = React.createContext<ZorosState | null>(null);

export const ZorosStoreProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [isRecording, setRecording] = React.useState(false);
  const [transcriptionMode, setTranscriptionMode] = React.useState<'push-to-talk' | 'wake-word'>('push-to-talk');
  const [currentText, setCurrentText] = React.useState('');
  const [droppedFiles, setDroppedFiles] = React.useState<File[]>([]);
  const [transcription, setTranscription] = React.useState<TranscriptionState>({
    text: '',
    confidence: 0,
    timestamps: [],
    status: 'idle',
  });

  const toggleRecording = () => setRecording((r) => !r);
  const addDroppedFiles = (files: File[]) => setDroppedFiles(files);
  const setTranscriptionPending = () =>
    setTranscription((t) => ({ ...t, status: 'pending', error: undefined }));
  const setTranscriptionResult = (r: TranscriptionState) =>
    setTranscription({ ...r, status: 'fulfilled', error: undefined });
  const setTranscriptionError = (msg: string) =>
    setTranscription((t) => ({ ...t, status: 'error', error: msg }));

  const value: ZorosState = {
    isRecording,
    transcriptionMode,
    currentText,
    droppedFiles,
    transcription,
    toggleRecording,
    setTranscriptionMode,
    setCurrentText,
    addDroppedFiles,
    setTranscriptionPending,
    setTranscriptionResult,
    setTranscriptionError,
  };

  return (
    <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
  );
};

export const useZorosStore = () => {
  const ctx = React.useContext(StoreContext);
  if (!ctx) throw new Error('useZorosStore must be used within provider');
  return ctx;
};

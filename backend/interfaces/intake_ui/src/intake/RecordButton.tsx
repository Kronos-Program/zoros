// See architecture: docs/zoros_architecture.md#ui-blueprint
/**
 * RecordButton - see "Intake UI" section in the architecture doc.
 */
import React from "react";
import { useZorosStore } from "../common/hooks/useZorosStore";
import "../common/styles/ZorosStyles.module.css";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import styles from "./RecordButton.module.css";

export const RecordButton: React.FC = () => {
  const { isRecording, toggleRecording } = useZorosStore();
  const recorder = useAudioRecorder();

  const handleClick = () => {
    toggleRecording();
    if (!isRecording) {
      recorder.startRecording();
    } else {
      recorder.stopRecording();
    }
  };

  return (
    <button
      className={isRecording ? styles.recording : styles.idle}
      onClick={handleClick}
      aria-label="Record audio"
    >
      <span className={styles.icon} />
    </button>
  );
};

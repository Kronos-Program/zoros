// See architecture: docs/zoros_architecture.md#ui-blueprint
/**
 * VoiceModeToggle - see "Intake UI" section in the architecture doc.
 */
import React from "react";
import { useZorosStore } from "../common/hooks/useZorosStore";
import "../common/styles/ZorosStyles.module.css";
import styles from "./VoiceModeToggle.module.css";

export const VoiceModeToggle: React.FC = () => {
  const { transcriptionMode, setTranscriptionMode } = useZorosStore();

  const toggle = () => {
    setTranscriptionMode(
      transcriptionMode === "push-to-talk" ? "wake-word" : "push-to-talk",
    );
  };

  return (
    <button
      className={styles.toggle}
      onClick={toggle}
      aria-label="Toggle voice mode"
    >
      {transcriptionMode === "push-to-talk" ? "Push-to-talk" : "Wake-word"}
    </button>
  );
};

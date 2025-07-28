// See architecture: docs/zoros_architecture.md#ui-blueprint
/**
 * TextInputArea - see "Intake UI" section in the architecture doc.
 */
import React from "react";
import { useZorosStore } from "../common/hooks/useZorosStore";
import "../common/styles/ZorosStyles.module.css";
import styles from "./TextInputArea.module.css";

export const TextInputArea: React.FC = () => {
  const { currentText, setCurrentText } = useZorosStore();

  return (
    <textarea
      className={styles.input}
      aria-label="Free-form text input"
      value={currentText}
      onChange={(e) => setCurrentText(e.target.value)}
    />
  );
};

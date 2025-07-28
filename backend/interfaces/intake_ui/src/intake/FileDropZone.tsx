// See architecture: docs/zoros_architecture.md#ui-blueprint
/**
 * FileDropZone - see "Intake UI" section in the architecture doc.
 */
import React from "react";
import { useZorosStore } from "../common/hooks/useZorosStore";
import "../common/styles/ZorosStyles.module.css";
import styles from "./FileDropZone.module.css";

export const FileDropZone: React.FC = () => {
  const { addDroppedFiles } = useZorosStore();
  const [highlight, setHighlight] = React.useState(false);

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setHighlight(false);
    const files = Array.from(e.dataTransfer.files);
    addDroppedFiles(files);
  };

  return (
    <div
      className={highlight ? styles.highlight : styles.zone}
      onDragEnter={(e) => {
        e.preventDefault();
        setHighlight(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => setHighlight(false)}
      onDrop={onDrop}
      aria-label="File drop zone"
    >
      Drop files here
    </div>
  );
};

// See architecture: docs/zoros_architecture.md#ui-blueprint
/**
 * IntakeContainer - see "Intake UI" section in the architecture doc.
 */
import React from "react";
import { RecordButton } from "./RecordButton";
import { TextInputArea } from "./TextInputArea";
import { FileDropZone } from "./FileDropZone";
import { VoiceModeToggle } from "./VoiceModeToggle";
import { WaveformCanvas } from "./WaveformCanvas";
import "../common/styles/ZorosStyles.module.css";
import { useResizeObserver } from "../common/hooks/useResizeObserver";
import { useZorosStore } from "../common/hooks/useZorosStore";
import styles from "./IntakeContainer.module.css";

export const IntakeContainer: React.FC = () => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  useResizeObserver(containerRef);
  const { droppedFiles } = useZorosStore();
  React.useEffect(() => {
    if (droppedFiles.length > 0) {
      console.log(
        "Files dropped:",
        droppedFiles.map((f) => f.name),
      );
    }
  }, [droppedFiles]);

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.row}>
        <RecordButton />
        <VoiceModeToggle />
      </div>
      <WaveformCanvas />
      <div className={styles.row}>
        <TextInputArea />
        <FileDropZone />
      </div>
    </div>
  );
};

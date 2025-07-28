/**
 * useResizeObserver - Utility hook for responsive resizing.
 * Refer to the "Intake UI" architecture section.
 */
import React from "react";

export function useResizeObserver(ref: React.RefObject<Element>) {
  React.useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(() => {
      // Layout recomputation can happen here
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);
}

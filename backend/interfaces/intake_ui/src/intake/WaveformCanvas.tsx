// See architecture: docs/zoros_architecture.md#ui-blueprint
/**
 * WaveformCanvas - displays a simple audio waveform with a confidence overlay.
 * Implements "real-time confidence score overlay" from TASK-072.
 */
import React, { useEffect, useRef } from 'react';
import { useZorosStore } from '../common/hooks/useZorosStore';
import styles from './WaveformCanvas.module.css';

export const WaveformCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const {
    transcription: { confidence },
  } = useZorosStore();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let raf: number;
    let t = 0;
    const draw = () => {
      if (!ctx) return;
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      ctx.beginPath();
      for (let x = 0; x < width; x++) {
        const y = Math.sin((x + t) * 0.05) * (height / 4) + height / 2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = '#09f';
      ctx.lineWidth = 2;
      ctx.stroke();
      t += 2;
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className={styles.wrapper}>
      <canvas ref={canvasRef} width={300} height={80} className={styles.canvas} />
      <div
        className={styles.confidenceOverlay}
        style={{ opacity: confidence }}
        aria-label={`Confidence ${Math.round(confidence * 100)}%`}
      />
    </div>
  );
};

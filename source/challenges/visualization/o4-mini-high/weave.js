// See architecture: docs/zoros_architecture.md#component-overview
import { WarpFiber, WeftFiber } from './fiber.js';
export class Weave {
  constructor(cols=20, rows=12, cell=40) {
    this.cols = cols; this.rows = rows; this.cell = cell;
    this.warp = [];
    this.weftPasses = [];
    this.pattern = null;
  }
  addWarpFiber(fiber, slot) {
    this.warp[slot] = fiber.transform('warp', 'springgreen');
  }
  addWeftPass(fibers) {
    this.weftPasses.push(fibers.map(f => f.transform('weft', 'darkgreen')));
  }
  generatePatternMatrix() {
    // reveal tagline in pattern
    const matrix = Array(this.rows).fill(0).map(() => Array(this.cols).fill(false));
    const text = 'WEAVING WHAT MATTERS'.split('');
    let idx = 0;
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        if (idx < text.length && Math.random() < 0.05) {
          matrix[r][c] = text[idx++];
        }
      }
    }
    this.pattern = matrix;
    return matrix;
  }
  draw(ctx) {
    // draw warp lines
    for (let i = 0; i < this.cols; i++) {
      ctx.strokeStyle = this.warp[i]?.color || '#004d00';
      ctx.beginPath();
      ctx.moveTo(i*this.cell,0);
      ctx.lineTo(i*this.cell,this.rows*this.cell);
      ctx.stroke();
    }
    // draw weft passes
    this.weftPasses.forEach((pass,i) => {
      ctx.strokeStyle = pass[0]?.color || '#002200';
      ctx.beginPath();
      ctx.moveTo(0,i*this.cell);
      ctx.lineTo(this.cols*this.cell,i*this.cell);
      ctx.stroke();
    });
    // draw tagline letters
    if (this.pattern) {
      ctx.fillStyle='#fff'; ctx.font=`${this.cell/2}px monospace`;
      for (let r=0; r<this.rows; r++){
        for (let c=0; c<this.cols; c++){
          if (this.pattern[r][c]) ctx.fillText(this.pattern[r][c], c*this.cell+5, r*this.cell+this.cell/1.5);
        }
      }
    }
  }
}

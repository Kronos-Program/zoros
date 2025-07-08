// See architecture: docs/zoros_architecture.md#component-overview
export class Spinner {
    constructor(x, y, radius = 30) {
      this.x = x; this.y = y; this.r = radius; this.angle = 0;
    }
    spin(fiber) {
      fiber.transform('spin', 'lightgreen');
      return fiber;
    }
    draw(ctx) {
      ctx.save(); ctx.translate(this.x, this.y);
      ctx.rotate(this.angle);
      const grads = ctx.createRadialGradient(0,0,this.r*0.2,0,0,this.r);
      grads.addColorStop(0, '#f0e68c'); grads.addColorStop(1, '#006400');
      ctx.fillStyle = grads;
      ctx.beginPath(); ctx.arc(0,0,this.r,0,Math.PI*2); ctx.fill();
      ctx.restore();
      this.angle += 0.02;
    }
  }

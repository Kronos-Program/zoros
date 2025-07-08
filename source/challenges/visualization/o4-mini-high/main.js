// See architecture: docs/zoros_architecture.md#component-overview
import {Fiber, WarpFiber, WeftFiber} from './fiber.js';
import {Spinner} from './spinner.js';
import {Weave} from './weave.js';

const canvas = document.getElementById('Zoros-canvas');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
const ctx = canvas.getContext('2d');

// Initialize fibers along Z-path
const fibers = [];
for (let i=0;i<10;i++) fibers.push(new Fiber(`f${i}`));

const spinner = new Spinner(canvas.width*0.1, canvas.height*0.1, 40);
const weave = new Weave(30, 20, Math.min(canvas.width/35, canvas.height/25));

// Setup warp fibers
for (let i=0; i<weave.cols; i++) {
  weave.addWarpFiber(new WarpFiber(`w${i}`, 'springgreen'), i);
}
// Setup initial weft
for (let p=0; p<weave.rows; p++) {
  const pass = [];
  for (let j=0; j<weave.cols; j++) pass.push(new WeftFiber(`p${p}-${j}`));
  weave.addWeftPass(pass);
}
// generate pattern
weave.generatePatternMatrix();

function drawZPath() {
  const A = {x: canvas.width*0.2, y: canvas.height*0.8};
  const B = {x: canvas.width*0.5, y: canvas.height*0.2};
  const C = {x: canvas.width*0.8, y: canvas.height*0.8};
  ctx.strokeStyle = 'gold'; ctx.lineWidth = 8;
  ctx.beginPath();
  ctx.moveTo(A.x, A.y);
  ctx.lineTo(B.x, B.y);
  ctx.lineTo(C.x, C.y);
  ctx.stroke();
}

let frame=0;
function animate() {
  ctx.clearRect(0,0,canvas.width,canvas.height);
  // 1. draw spinning corner
  spinner.draw(ctx);
  // 2. draw Z path
  drawZPath();
  // 3. draw weave area
  ctx.save(); ctx.translate(canvas.width*0.1, canvas.height*0.7);
  weave.draw(ctx);
  ctx.restore();
  // 4. shuttle animation
  const shuttleX = (frame % (weave.cols*weave.cell));
  ctx.fillStyle = 'violet';
  ctx.fillRect(canvas.width*0.1 + shuttleX, canvas.height*0.7 + weave.rows*weave.cell + 10, 20, 10);
  // 5. violet markers on fibers
  fibers.forEach((f,i) => {
    const mx = canvas.width*0.2 + i*15;
    const my = canvas.height*0.85 + Math.sin(frame*0.05 + i)*5;
    ctx.fillStyle = 'violet';
    ctx.beginPath();
    ctx.arc(mx,my,3,0,Math.PI*2);
    ctx.fill();
  });
  frame++;
  requestAnimationFrame(animate);
}

animate();

// Export lineage to Python via Brython
const exportBtn = document.getElementById('exportBtn');
exportBtn.addEventListener('click', ()=>{
  const data = fibers.map(f => f.exportLineage());
  console.log(data.join('\n'));
  // Brython handler: call Python function if needed
});

// See architecture: docs/zoros_architecture.md#component-overview

export class Fiber {
  constructor(id, colorStart = 'gold') {
    this.id = id;
    this.color = colorStart;
    this.history = [{ stage: 'start', color: this.color }];
    this.markers = [];
  }
  transform(type, color, context = null) {
    this.color = color;
    this.history.push({ stage: type, color, context });
    return this;
  }
  addMarker(markerType) {
    this.markers.push(markerType);
    return this;
  }
  exportLineage() {
    return JSON.stringify({ id: this.id, history: this.history, markers: this.markers }, null, 2);
  }
}
export class WarpFiber extends Fiber {}
export class WeftFiber extends Fiber {}

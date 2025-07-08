declare module 'fs/promises';
declare module 'assert';
declare function test(name: string, fn: () => Promise<void> | void): void;
declare module 'node:test' {
  export function test(name: string, fn: () => Promise<void> | void): void;
}

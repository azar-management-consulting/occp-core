import "@testing-library/jest-dom/vitest";

// happy-dom ships a partial localStorage — add a canonical in-memory
// stub so tests get clear/getItem/setItem/removeItem/key/length parity
// with browsers.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length(): number {
    return this.store.size;
  }
  clear(): void {
    this.store.clear();
  }
  getItem(k: string): string | null {
    return this.store.has(k) ? (this.store.get(k) as string) : null;
  }
  key(i: number): string | null {
    return Array.from(this.store.keys())[i] ?? null;
  }
  removeItem(k: string): void {
    this.store.delete(k);
  }
  setItem(k: string, v: string): void {
    this.store.set(k, String(v));
  }
}

Object.defineProperty(window, "localStorage", {
  value: new MemoryStorage(),
  writable: false,
});
Object.defineProperty(window, "sessionStorage", {
  value: new MemoryStorage(),
  writable: false,
});

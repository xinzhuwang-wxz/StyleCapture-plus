import {
  asIntInRange,
  asRecord,
  asTrimmedString,
  clearLocal,
  readLocal,
  writeLocal,
  type LocalStoreDefinition
} from "../src/storage/localStore";

type Sample = { name: string; height: number };

const definition: LocalStoreDefinition<Sample> = {
  key: "stylecapture:test:v1",
  fallback: () => ({ name: "默认", height: 165 }),
  parse: (raw) => {
    const record = asRecord(raw);
    if (!record) return null;
    const name = asTrimmedString(record.name, 12);
    const height = asIntInRange(record.height, 140, 200);
    return name && height !== null ? { name, height } : null;
  }
};

function useStorage(store: Storage | null) {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get: () => {
      if (store === null) throw new Error("storage disabled");
      return store;
    }
  });
}

function memoryStorage(overrides: Partial<Storage> = {}): Storage {
  const map = new Map<string, string>();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => void map.set(key, value),
    removeItem: (key) => void map.delete(key),
    clear: () => map.clear(),
    key: (index) => [...map.keys()][index] ?? null,
    get length() {
      return map.size;
    },
    ...overrides
  } as Storage;
}

describe("local store", () => {
  afterEach(() => useStorage(memoryStorage()));

  it("round-trips a valid value", () => {
    useStorage(memoryStorage());
    expect(writeLocal(definition, { name: "小甜甜", height: 168 })).toEqual({
      ok: true
    });
    expect(readLocal(definition)).toEqual({ name: "小甜甜", height: 168 });
  });

  it("falls back to defaults when nothing is stored", () => {
    useStorage(memoryStorage());
    expect(readLocal(definition)).toEqual({ name: "默认", height: 165 });
  });

  it("falls back instead of throwing on corrupt JSON", () => {
    const store = memoryStorage();
    store.setItem(definition.key, "{not json");
    useStorage(store);
    expect(readLocal(definition)).toEqual({ name: "默认", height: 165 });
  });

  it("falls back when the stored shape no longer validates", () => {
    const store = memoryStorage();
    // A value a user could produce by hand-editing, or an older schema.
    store.setItem(definition.key, JSON.stringify({ name: "", height: 999 }));
    useStorage(store);
    expect(readLocal(definition)).toEqual({ name: "默认", height: 165 });
  });

  it("degrades silently when storage is unavailable", () => {
    useStorage(null);
    expect(readLocal(definition)).toEqual({ name: "默认", height: 165 });
    expect(writeLocal(definition, { name: "x", height: 170 })).toEqual({
      ok: false,
      reason: "unavailable"
    });
    expect(() => clearLocal(definition)).not.toThrow();
  });

  it("reports a full quota as a visible failure rather than pretending to save", () => {
    const quotaError = new Error("full");
    quotaError.name = "QuotaExceededError";
    useStorage(
      memoryStorage({
        setItem: () => {
          throw quotaError;
        }
      })
    );
    expect(writeLocal(definition, { name: "x", height: 170 })).toEqual({
      ok: false,
      reason: "quota"
    });
  });

  it("clears a stored value", () => {
    useStorage(memoryStorage());
    writeLocal(definition, { name: "小甜甜", height: 168 });
    clearLocal(definition);
    expect(readLocal(definition)).toEqual({ name: "默认", height: 165 });
  });

  it("gives each caller its own fallback object", () => {
    useStorage(memoryStorage());
    const first = readLocal(definition);
    first.name = "被改过";
    expect(readLocal(definition).name).toBe("默认");
  });
});

describe("validation helpers", () => {
  it("rejects arrays and primitives as records", () => {
    expect(asRecord({ a: 1 })).toEqual({ a: 1 });
    expect(asRecord([1, 2])).toBeNull();
    expect(asRecord("x")).toBeNull();
    expect(asRecord(null)).toBeNull();
  });

  it("bounds and rounds integers", () => {
    expect(asIntInRange(165.4, 140, 200)).toBe(165);
    expect(asIntInRange(139, 140, 200)).toBeNull();
    expect(asIntInRange(201, 140, 200)).toBeNull();
    expect(asIntInRange(Number.NaN, 140, 200)).toBeNull();
    expect(asIntInRange("165", 140, 200)).toBeNull();
  });

  it("trims, caps and rejects empty strings", () => {
    expect(asTrimmedString("  小甜甜  ", 12)).toBe("小甜甜");
    expect(asTrimmedString("   ", 12)).toBeNull();
    expect(asTrimmedString("x".repeat(20), 12)).toHaveLength(12);
    expect(asTrimmedString(42, 12)).toBeNull();
  });
});

import {
  BODY_SHAPES,
  METRIC_FIELDS,
  bodyProfileStore,
  clampMetric,
  defaultMetricValue,
  defaultBodyProfile,
  isDefaultBodyProfile,
  readBodyProfile,
  writeBodyProfile
} from "../src/features/profile/profileStorage";

function memoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => void map.set(key, value),
    removeItem: (key) => void map.delete(key),
    clear: () => map.clear(),
    key: (index) => [...map.keys()][index] ?? null,
    get length() {
      return map.size;
    }
  } as Storage;
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: memoryStorage()
  });
});

describe("body profile", () => {
  it("round-trips a filled-in profile", () => {
    const profile = {
      ...defaultBodyProfile(),
      nickname: "小甜甜",
      height: 168,
      bust: 86,
      waist: 65,
      hip: 91,
      shape: "沙漏形" as const
    };
    expect(writeBodyProfile(profile)).toEqual({ ok: true });
    expect(readBodyProfile()).toEqual(profile);
  });

  it("starts from defaults and knows they are untouched", () => {
    expect(readBodyProfile()).toEqual(defaultBodyProfile());
    expect(isDefaultBodyProfile(readBodyProfile())).toBe(true);
    expect(
      isDefaultBodyProfile({ ...defaultBodyProfile(), height: 170 })
    ).toBe(false);
  });

  it("rejects a stored profile with an out-of-range metric", () => {
    // Body data drives sizing advice, so a nonsense height must not reach the UI.
    window.localStorage.setItem(
      bodyProfileStore.key,
      JSON.stringify({ ...defaultBodyProfile(), height: 900 })
    );
    expect(readBodyProfile()).toEqual(defaultBodyProfile());
  });

  it("rejects a stored profile with an unknown body shape", () => {
    window.localStorage.setItem(
      bodyProfileStore.key,
      JSON.stringify({ ...defaultBodyProfile(), shape: "圆形" })
    );
    expect(readBodyProfile()).toEqual(defaultBodyProfile());
  });

  it("round-trips optional measurements and body shape as empty", () => {
    const profile = defaultBodyProfile();
    expect(writeBodyProfile(profile)).toEqual({ ok: true });
    expect(readBodyProfile()).toEqual(profile);
    expect(profile).toMatchObject({
      bust: null,
      waist: null,
      hip: null,
      shape: null
    });
  });

  it("rejects a stored profile that is missing a field", () => {
    const { waist, ...incomplete } = defaultBodyProfile();
    void waist;
    window.localStorage.setItem(
      bodyProfileStore.key,
      JSON.stringify(incomplete)
    );
    expect(readBodyProfile()).toEqual(defaultBodyProfile());
  });

  it("clamps every metric into its own declared range", () => {
    METRIC_FIELDS.forEach((field) => {
      expect(clampMetric(field.key, field.min - 50)).toBe(field.min);
      expect(clampMetric(field.key, field.max + 50)).toBe(field.max);
      expect(clampMetric(field.key, field.min + 1.4)).toBe(field.min + 1);
      expect(clampMetric(field.key, Number.NaN)).toBe(
        defaultMetricValue(field.key)
      );
    });
  });

  it("keeps required defaults in range and leaves optional data empty", () => {
    const base = defaultBodyProfile();
    METRIC_FIELDS.filter((field) => field.group === "a").forEach((field) => {
      expect(base[field.key]).toBeGreaterThanOrEqual(field.min);
      expect(base[field.key]).toBeLessThanOrEqual(field.max);
    });
    expect(base).toMatchObject({
      bust: null,
      waist: null,
      hip: null,
      shape: null
    });
    expect(BODY_SHAPES).not.toContain(base.shape);
  });
});

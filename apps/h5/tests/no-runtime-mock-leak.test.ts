import { describe, expect, it } from "vitest";

const FORBIDDEN_RUNTIME_REFERENCES = [
  "mock/mockApi",
  "features/wardrobe/catalog",
  "demoRenderAdapter"
] as const;

const FORBIDDEN_BROWSER_INFRASTRUCTURE = [
  "http://localhost:8000",
  "http://127.0.0.1:8000",
  "ark-",
  "doubao-seed",
  "doubao-seedream",
  "api.volcengine"
] as const;

const runtimeSources = import.meta.glob("../src/**/*.{ts,tsx}", {
  eager: true,
  import: "default",
  query: "?raw"
}) as Record<string, string>;

describe("H5 运行时真实性门禁", () => {
  it("不引用 PR12 的 mock、硬编码商品库或浏览器假渲染器", () => {
    const offenders = Object.entries(runtimeSources).flatMap(([path, source]) => {
      return FORBIDDEN_RUNTIME_REFERENCES.filter((reference) =>
        source.includes(reference)
      ).map((reference) => `${path}: ${reference}`);
    });

    expect(offenders).toEqual([]);
  });

  it("浏览器代码不硬编码 API 端口、密钥或模型供应商细节", () => {
    const offenders = Object.entries(runtimeSources).flatMap(([path, source]) => {
      return FORBIDDEN_BROWSER_INFRASTRUCTURE.filter((reference) =>
        source.includes(reference)
      ).map((reference) => `${path}: ${reference}`);
    });

    expect(offenders).toEqual([]);
  });
});

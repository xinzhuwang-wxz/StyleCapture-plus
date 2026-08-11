import manifest from "../public/feed/manifest.json";

describe("Feed manifest order", () => {
  it("defers the unsuitable cold-start videos to the end of the Feed", () => {
    const ids = manifest.assets.map(({ asset_id }) => asset_id);

    expect(ids.slice(0, 4)).toEqual([
      "pexels-9512048",
      "pexels-9512049",
      "pexels-31223596",
      "pexels-31223574"
    ]);
    expect(ids.slice(-2)).toEqual(["pexels-5655044", "pexels-19862866"]);
  });
});

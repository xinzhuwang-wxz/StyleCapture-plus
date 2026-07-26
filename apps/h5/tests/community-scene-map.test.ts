import {
  canStand,
  mapSize,
  onRunway,
  sceneById,
  sceneMaps,
  tileAt
} from "../src/features/community/world/sceneMap";

describe("scene maps", () => {
  it.each(sceneMaps.map((scene) => [scene.id, scene] as const))(
    "%s keeps every ground row the same width and every key in the legend",
    (_id, scene) => {
      const width = scene.ground[0].length;
      scene.ground.forEach((row, index) => {
        expect(`row ${index}: ${row.length}`).toBe(`row ${index}: ${width}`);
        [...row].forEach((key) => expect(scene.legend[key]).toBeDefined());
      });
    }
  );

  it.each(sceneMaps.map((scene) => [scene.id, scene] as const))(
    "%s places the player, the stage and every guest on standable ground",
    (_id, scene) => {
      const points = [
        scene.stagePoint,
        scene.backstagePoint,
        ...scene.guestSpots
      ];
      points.forEach((point) => {
        expect(canStand(scene, point.x, point.y)).toBe(true);
      });
    }
  );

  it.each(sceneMaps.map((scene) => [scene.id, scene] as const))(
    "%s puts the hero pose on the raised runway",
    (_id, scene) => {
      expect(onRunway(scene, scene.stagePoint.x, scene.stagePoint.y)).toBe(true);
      expect(
        onRunway(scene, scene.backstagePoint.x, scene.backstagePoint.y)
      ).toBe(false);
    }
  );

  it("treats everything outside the map as unstandable", () => {
    const scene = sceneMaps[0];
    const { width, height } = mapSize(scene);
    expect(tileAt(scene, -1, 10)).toBeNull();
    expect(canStand(scene, width + 10, 10)).toBe(false);
    expect(canStand(scene, 10, height + 10)).toBe(false);
  });

  it("falls back to the first scene for an unknown id", () => {
    expect(sceneById("missing").id).toBe(sceneMaps[0].id);
    expect(sceneById(sceneMaps[1].id).id).toBe(sceneMaps[1].id);
  });
});

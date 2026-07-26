import {
  actorHeight,
  createPartyWorld,
  playerOf,
  sayAsPlayer,
  startRunway,
  stepParty
} from "../src/features/community/world/simulation";
import { guestChats, guestPersonas } from "../src/features/community/world/guests";
import {
  isReactionAlive,
  reactionPosition,
  REACTION_LIFETIME
} from "../src/features/community/world/reactions";
import { sceneMaps } from "../src/features/community/world/sceneMap";

function advance(world: ReturnType<typeof createPartyWorld>, seconds: number) {
  for (let step = 0; step < seconds * 30; step += 1) {
    stepParty(world, 1 / 30, { width: 390, height: 380 });
  }
}

describe("party simulation", () => {
  it("gives every guest a distinct character and art set", () => {
    expect(guestPersonas).toHaveLength(4);
    const looks = guestPersonas.map((persona) => persona.lookId);
    expect(new Set(looks).size).toBe(looks.length);
    const names = guestPersonas.map((persona) => persona.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("scripts guest pairs that actually exist", () => {
    const ids = new Set(guestPersonas.map((persona) => persona.id));
    guestChats.forEach((chat) => {
      chat.between.forEach((id) => expect(ids.has(id)).toBe(true));
      expect(chat.between[0]).not.toBe(chat.between[1]);
      expect(chat.lines.length).toBeGreaterThan(2);
    });
  });

  it("draws everyone at the same scale for their depth", () => {
    const world = createPartyWorld(sceneMaps[0], "curated-vintage");
    const player = playerOf(world);
    const guest = world.actors.find((actor) => actor.kind === "guest")!;
    guest.y = player.y;
    // Same ground line means same drawn height; no privileged main character.
    expect(actorHeight(world, player)).toBeCloseTo(actorHeight(world, guest), 6);
  });

  it("lets guests pair off and talk without the player", () => {
    const world = createPartyWorld(sceneMaps[0], "curated-vintage");
    // Park the player far away so proximity greetings cannot fire.
    playerOf(world).x = 40;
    playerOf(world).y = 470;
    advance(world, 30);
    const spoke = world.actors.filter(
      (actor) => actor.kind === "guest" && actor.bubble
    );
    expect(world.guestChat ?? spoke.length).toBeTruthy();
  });

  it("speaks as the player and rejects an empty line", () => {
    const world = createPartyWorld(sceneMaps[0], "curated-vintage");
    expect(sayAsPlayer(world, "   ")).toBe(false);
    expect(sayAsPlayer(world, "大家好")).toBe(true);
    expect(playerOf(world).bubble?.text).toBe("大家好");
  });

  it("trims an over-long line instead of overflowing the bubble", () => {
    const world = createPartyWorld(sceneMaps[0], "curated-vintage");
    sayAsPlayer(world, "字".repeat(80));
    expect(playerOf(world).bubble?.text).toHaveLength(40);
  });

  it("floats applause off the crowd while they cheer, then clears it", () => {
    const world = createPartyWorld(sceneMaps[0], "curated-vintage");
    startRunway(world);
    advance(world, 16);
    expect(world.reactions.length).toBeGreaterThan(0);

    // Icons rise and fade rather than piling up forever.
    const sample = world.reactions[0];
    const early = reactionPosition(sample, sample.bornAt + 0.1);
    const late = reactionPosition(sample, sample.bornAt + 1.5);
    expect(late.y).toBeLessThan(early.y);
    expect(late.alpha).toBeLessThan(early.alpha);
    expect(isReactionAlive(sample, sample.bornAt + REACTION_LIFETIME + 0.1)).toBe(
      false
    );
    expect(world.reactions.length).toBeLessThan(40);
  });

  it("brings the crowd in when the player reaches the stage", () => {
    const world = createPartyWorld(sceneMaps[0], "curated-vintage");
    startRunway(world);
    expect(world.phase).toBe("walking");
    advance(world, 14);
    expect(world.phase).toBe("posing");
    expect(
      world.actors.filter((actor) => actor.kind === "guest" && actor.target)
        .length + world.actors.filter((actor) => actor.state === "cheer").length
    ).toBeGreaterThan(0);
  });
});

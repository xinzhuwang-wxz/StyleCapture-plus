/**
 * The party simulation: who is in the room, where they walk, what they say, and
 * how the runway beat is choreographed.
 *
 * Pure state plus a `step` function, so the behaviour is testable without a
 * canvas and the renderer stays a dumb painter.
 */

import { rigFrame, walkCadence, type RigState } from "./characterRig";
import { guestChats, guestPersonas, type GuestPersona } from "./guests";
import {
  isReactionAlive,
  REACTION_KINDS,
  type FloatingReaction
} from "./reactions";
import {
  canStand,
  mapSize,
  onRunway,
  tileAt,
  type SceneMap
} from "./sceneMap";

export type ActorKind = "player" | "guest";

export type Actor = {
  id: string;
  kind: ActorKind;
  personaId?: string;
  name: string;
  lookId: string;
  x: number;
  y: number;
  facing: 1 | -1;
  /** Current movement target; null means standing still. */
  target: { x: number; y: number } | null;
  /** Anchor the guest wanders around. */
  anchor: { x: number; y: number };
  speed: number;
  phase: number;
  state: RigState;
  bubble: { text: string; tone: "speech" | "reaction"; until: number } | null;
  nextTalkAt: number;
};

export type PartyPhase =
  | "mingling"
  | "greeting"
  | "walking"
  | "posing"
  | "frozen";

/** A scripted exchange playing out between the player and one guest. */
export type ActiveConversation = {
  guestId: string;
  lines: readonly { speaker: "guest" | "player"; text: string }[];
  index: number;
  nextAt: number;
};

export type PartyWorld = {
  scene: SceneMap;
  actors: Actor[];
  playerId: string;
  phase: PartyPhase;
  /** Seconds since the world started. */
  time: number;
  /** Seconds spent in the current phase. */
  phaseTime: number;
  camera: { x: number; y: number; zoom: number };
  cameraTarget: { x: number; y: number; zoom: number };
  vignette: number;
  selectedActorId: string | null;
  conversation: ActiveConversation | null;
  /** Guest the player is currently standing next to, if any. */
  nearbyGuestId: string | null;
  /** Two guests currently walking over to each other, or talking. */
  guestChat: GuestChatState | null;
  nextGuestChatAt: number;
  /** Pixel applause rising off the crowd. */
  reactions: FloatingReaction[];
  nextReactionAt: number;
};

export type GuestChatState = {
  ids: readonly [string, string];
  lines: readonly { speaker: 0 | 1; text: string }[];
  index: number;
  nextAt: number;
  /** Guests first walk together, then speak. */
  stage: "approaching" | "talking";
};

const PLAYER_ID = "player";
const PLAYER_SPEED = 46;
const GUEST_SPEED = 24;
const BUBBLE_SECONDS = 3.4;
const RUNWAY_ZOOM = 2.1;
const ROAM_ZOOM = 1.55;

/** Deterministic pseudo-random stream so a replayed party looks the same. */
function noise(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function clampToMap(scene: SceneMap, x: number, y: number) {
  const size = mapSize(scene);
  return {
    x: Math.max(8, Math.min(size.width - 8, x)),
    y: Math.max(8, Math.min(size.height - 8, y))
  };
}

function guestActor(
  persona: GuestPersona,
  spot: { x: number; y: number },
  index: number
): Actor {
  return {
    id: persona.id,
    kind: "guest",
    personaId: persona.id,
    name: persona.name,
    lookId: persona.lookId,
    x: spot.x,
    y: spot.y,
    facing: index % 2 === 0 ? 1 : -1,
    target: null,
    anchor: { ...spot },
    speed: GUEST_SPEED,
    phase: noise(index * 7.3),
    state: "idle",
    bubble: null,
    nextTalkAt: 2 + noise(index * 3.1) * persona.talkInterval
  };
}

export function createPartyWorld(
  scene: SceneMap,
  playerLookId: string,
  /** Which guests to place. Omitted means everyone the cast has. */
  activeGuestIds?: readonly string[]
): PartyWorld {
  const cast = activeGuestIds
    ? guestPersonas.filter((persona) => activeGuestIds.includes(persona.id))
    : guestPersonas;
  const guests = cast.map((persona, index) =>
    guestActor(
      persona,
      scene.guestSpots[index % scene.guestSpots.length],
      index
    )
  );
  // Spawn in front of the runway, not at the far backstage: the first frame
  // should show the stage the party is about. `startRunway` moves them back.
  const spawn = {
    x: scene.stagePoint.x,
    y: (scene.stagePoint.y + scene.backstagePoint.y) / 2
  };
  const player: Actor = {
    id: PLAYER_ID,
    kind: "player",
    name: "我",
    lookId: playerLookId,
    x: spawn.x,
    y: spawn.y,
    facing: 1,
    target: null,
    anchor: spawn,
    speed: PLAYER_SPEED,
    phase: 0,
    state: "idle",
    bubble: null,
    nextTalkAt: Number.POSITIVE_INFINITY
  };

  return {
    scene,
    actors: [...guests, player],
    playerId: PLAYER_ID,
    phase: "mingling",
    time: 0,
    phaseTime: 0,
    camera: { x: player.x, y: player.y - 20, zoom: ROAM_ZOOM },
    cameraTarget: { x: player.x, y: player.y - 20, zoom: ROAM_ZOOM },
    vignette: 0,
    selectedActorId: null,
    conversation: null,
    nearbyGuestId: null,
    guestChat: null,
    nextGuestChatAt: 6,
    reactions: [],
    nextReactionAt: 0
  };
}

/** How close the player must stand before a guest turns and says hello. */
export const GREETING_DISTANCE = 34;
const GREETING_LINE_SECONDS = 2.6;
/** Seconds between two guests deciding to go and talk to each other. */
const GUEST_CHAT_INTERVAL = 16;

/**
 * Says a line as the player.
 *
 * The bubble is the player's own voice — the same channel a real second person
 * would speak through once this becomes multiplayer.
 */
export function sayAsPlayer(world: PartyWorld, text: string) {
  const trimmed = text.trim().slice(0, 40);
  if (!trimmed) return false;
  const player = playerOf(world);
  player.bubble = {
    text: trimmed,
    tone: "speech",
    until: world.time + BUBBLE_SECONDS + 1.2
  };
  // Whoever is standing closest turns and answers.
  const nearby = world.actors
    .filter((actor) => actor.kind === "guest")
    .map((actor) => ({
      actor,
      distance: Math.hypot(actor.x - player.x, actor.y - player.y)
    }))
    .sort((left, right) => left.distance - right.distance)[0];
  if (nearby && nearby.distance < GREETING_DISTANCE * 1.8) {
    const persona = guestPersonas.find(
      (entry) => entry.id === nearby.actor.personaId
    );
    if (persona) {
      nearby.actor.facing = player.x >= nearby.actor.x ? 1 : -1;
      nearby.actor.nextTalkAt = world.time + 1.1;
    }
  }
  return true;
}

export function playerOf(world: PartyWorld): Actor {
  return (
    world.actors.find((actor) => actor.id === world.playerId) ?? world.actors[0]
  );
}

export function actorById(world: PartyWorld, id: string): Actor | undefined {
  return world.actors.find((actor) => actor.id === id);
}

/** Sends the player walking to a tapped point, if it is standable. */
export function walkPlayerTo(world: PartyWorld, x: number, y: number): boolean {
  if (world.phase === "walking" || world.phase === "frozen") return false;
  if (!canStand(world.scene, x, y)) return false;
  const player = playerOf(world);
  player.target = clampToMap(world.scene, x, y);
  if (world.phase === "posing") {
    world.phase = "mingling";
    world.phaseTime = 0;
    world.vignette = 0;
  }
  return true;
}

/** Starts the runway: the player walks from backstage to the stage point. */
export function startRunway(world: PartyWorld) {
  const player = playerOf(world);
  player.x = world.scene.backstagePoint.x;
  player.y = world.scene.backstagePoint.y;
  player.target = { ...world.scene.stagePoint };
  player.facing = 1;
  player.state = "walk";
  world.phase = "walking";
  world.phaseTime = 0;
  world.selectedActorId = null;
}

/** Holds the current frame so it can be captured. */
export function freezeParty(world: PartyWorld) {
  world.phase = "frozen";
  world.phaseTime = 0;
}

export function resumeParty(world: PartyWorld) {
  if (world.phase !== "frozen") return;
  world.phase = "posing";
  world.phaseTime = 0;
}

function say(
  actor: Actor,
  text: string,
  tone: "speech" | "reaction",
  now: number
) {
  actor.bubble = { text, tone, until: now + BUBBLE_SECONDS };
}

function wander(actor: Actor, world: PartyWorld, seed: number) {
  const persona = guestPersonas.find((entry) => entry.id === actor.personaId);
  const roam = persona?.roam ?? 30;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const angle = noise(seed + attempt * 1.7) * Math.PI * 2;
    const distance = 10 + noise(seed + attempt * 3.3) * roam;
    const candidate = clampToMap(
      world.scene,
      actor.anchor.x + Math.cos(angle) * distance,
      actor.anchor.y + Math.sin(angle) * distance
    );
    if (canStand(world.scene, candidate.x, candidate.y)) {
      actor.target = candidate;
      return;
    }
  }
}

function moveToward(actor: Actor, delta: number): boolean {
  if (!actor.target) return false;
  const dx = actor.target.x - actor.x;
  const dy = actor.target.y - actor.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 1.2) {
    actor.x = actor.target.x;
    actor.y = actor.target.y;
    actor.target = null;
    return false;
  }
  const step = Math.min(distance, actor.speed * delta);
  actor.x += (dx / distance) * step;
  actor.y += (dy / distance) * step;
  if (Math.abs(dx) > 0.6) actor.facing = dx > 0 ? 1 : -1;
  return true;
}

/**
 * Draws the guests in around the runway so the hero shot is actually a group
 * shot. Without this the share card would name co-stars who are not in frame.
 */
export const STAGE_GATHER_RADIUS = 62;

/**
 * Calls the crowd in for a photo wherever the player happens to be standing,
 * so a group shot is possible without walking the runway first.
 */
export function gatherForPhoto(world: PartyWorld) {
  gatherAroundStage(world, playerOf(world));
}

function gatherAroundStage(world: PartyWorld, around?: Actor) {
  const stage = around ? { x: around.x, y: around.y } : world.scene.stagePoint;
  const guests = world.actors.filter((actor) => actor.kind === "guest");
  guests.forEach((actor, index) => {
    // Alternate sides of the runway and step back as the row fills.
    const side = index % 2 === 0 ? -1 : 1;
    const rank = Math.floor(index / 2);
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const candidate = clampToMap(
        world.scene,
        stage.x + side * (34 + rank * 15 + attempt * 5),
        stage.y + (rank - 0.5) * 30 + (index % 3) * 8
      );
      if (canStand(world.scene, candidate.x, candidate.y)) {
        actor.target = candidate;
        break;
      }
    }
    // Hurry over: a crowd that strolls in takes too long to become applause.
    actor.speed = GUEST_SPEED * 1.9;
    const persona = guestPersonas.find((entry) => entry.id === actor.personaId);
    if (persona) actor.nextTalkAt = world.time + 0.4 + index * 0.5;
  });
}

function frozenPhase(world: PartyWorld): boolean {
  return world.phase === "frozen";
}

export function endConversation(world: PartyWorld) {
  if (world.conversation) {
    const guest = actorById(world, world.conversation.guestId);
    if (guest) guest.bubble = null;
  }
  playerOf(world).bubble = null;
  world.conversation = null;
}

/**
 * Walking up to someone starts a scripted hello.
 *
 * Proximity is the trigger rather than a tap, so the interaction reads as
 * "I went over to talk to them" instead of "I opened a dialog".
 */
function updateGreeting(world: PartyWorld, player: Actor) {
  if (world.phase === "walking" || world.phase === "posing") return;
  if (frozenPhase(world)) return;

  const nearest = world.actors
    .filter((actor) => actor.kind === "guest")
    .map((actor) => ({
      actor,
      distance: Math.hypot(actor.x - player.x, actor.y - player.y)
    }))
    .sort((left, right) => left.distance - right.distance)[0];

  const inRange =
    nearest && nearest.distance <= GREETING_DISTANCE ? nearest.actor : null;
  world.nearbyGuestId = inRange?.id ?? null;

  // Walking away ends the exchange.
  if (world.conversation && world.conversation.guestId !== inRange?.id) {
    endConversation(world);
    if (world.phase === "greeting") world.phase = "mingling";
    return;
  }

  if (!inRange || world.conversation || player.target) return;

  const persona = guestPersonas.find((entry) => entry.id === inRange.personaId);
  if (!persona?.conversation.length) return;

  world.phase = "greeting";
  world.conversation = {
    guestId: inRange.id,
    lines: persona.conversation,
    index: -1,
    nextAt: world.time
  };
  player.facing = inRange.x >= player.x ? 1 : -1;
}

/** Plays one line at a time, alternating the bubble between the two speakers. */
function advanceConversation(world: PartyWorld) {
  const conversation = world.conversation;
  if (!conversation || frozenPhase(world)) return;
  if (world.time < conversation.nextAt) return;

  const next = conversation.index + 1;
  if (next >= conversation.lines.length) {
    // Hold the last line briefly, then return to mingling.
    endConversation(world);
    if (world.phase === "greeting") world.phase = "mingling";
    return;
  }

  const line = conversation.lines[next];
  const guest = actorById(world, conversation.guestId);
  const player = playerOf(world);
  const speaker = line.speaker === "guest" ? guest : player;
  const listener = line.speaker === "guest" ? player : guest;
  if (listener) listener.bubble = null;
  if (speaker) {
    speaker.bubble = {
      text: line.text,
      tone: "speech",
      until: world.time + GREETING_LINE_SECONDS + 0.4
    };
  }

  conversation.index = next;
  conversation.nextAt = world.time + GREETING_LINE_SECONDS;
}

/**
 * Applause rises off whoever is cheering.
 *
 * Icons are spawned from the crowd rather than the performer, so the gesture
 * reads as the room reacting to you.
 */
function updateReactions(world: PartyWorld) {
  world.reactions = world.reactions.filter((reaction) =>
    isReactionAlive(reaction, world.time)
  );
  if (frozenPhase(world)) return;

  const cheering = world.actors.filter((actor) => actor.state === "cheer");
  if (!cheering.length) return;
  if (world.time < world.nextReactionAt) return;

  const source = cheering[Math.floor(noise(world.time * 5.1) * cheering.length) % cheering.length];
  const kind =
    REACTION_KINDS[
      Math.floor(noise(world.time * 9.3) * REACTION_KINDS.length) %
        REACTION_KINDS.length
    ];
  world.reactions.push({
    x: source.x + (noise(world.time * 2.7) - 0.5) * 26,
    y: source.y - actorHeight(world, source) * (0.75 + noise(world.time * 3.9) * 0.35),
    kind,
    bornAt: world.time,
    drift: 2 + noise(world.time * 4.4) * 6,
    scale: 1.1 + noise(world.time * 6.1) * 0.6
  });
  // Roughly three icons a second across the whole crowd.
  world.nextReactionAt = world.time + 0.22 + noise(world.time * 8.2) * 0.2;
}

/**
 * Guests pair off and talk to each other on their own.
 *
 * Without this the room only comes alive when the player walks up to someone,
 * which makes everyone feel like a vending machine rather than a guest.
 */
function updateGuestChat(world: PartyWorld) {
  if (frozenPhase(world)) return;
  if (world.phase === "walking" || world.phase === "posing") {
    world.guestChat = null;
    return;
  }

  const chat = world.guestChat;
  if (!chat) {
    if (world.time < world.nextGuestChatAt) return;
    startGuestChat(world);
    return;
  }

  const [first, second] = chat.ids.map((id) => actorById(world, id));
  if (!first || !second) {
    world.guestChat = null;
    return;
  }
  // The player joining in takes priority over guest small talk.
  if (world.conversation && chat.ids.includes(world.conversation.guestId)) {
    world.guestChat = null;
    world.nextGuestChatAt = world.time + GUEST_CHAT_INTERVAL;
    return;
  }

  if (chat.stage === "approaching") {
    const arrived = !first.target && !second.target;
    if (arrived || world.time > chat.nextAt) {
      chat.stage = "talking";
      chat.nextAt = world.time;
    }
    return;
  }

  if (world.time < chat.nextAt) return;
  const next = chat.index + 1;
  if (next >= chat.lines.length) {
    first.bubble = null;
    second.bubble = null;
    world.guestChat = null;
    world.nextGuestChatAt = world.time + GUEST_CHAT_INTERVAL;
    return;
  }
  const line = chat.lines[next];
  const speaker = line.speaker === 0 ? first : second;
  const listener = line.speaker === 0 ? second : first;
  listener.bubble = null;
  say(speaker, line.text, "speech", world.time);
  chat.index = next;
  chat.nextAt = world.time + GREETING_LINE_SECONDS;
}

function startGuestChat(world: PartyWorld) {
  const available = guestChats.filter((chat) =>
    chat.between.every((id) => {
      const actor = actorById(world, id);
      return actor && world.conversation?.guestId !== id;
    })
  );
  // With a small cast, most scripted pairs are simply not both present.
  if (!available.length) return;

  const script =
    available[Math.floor(noise(world.time * 3.7) * available.length) % available.length];
  const first = actorById(world, script.between[0]);
  const second = actorById(world, script.between[1]);
  if (!first || !second) return;

  // Meet in the middle, a step apart, on ground they can both stand on.
  const midX = (first.x + second.x) / 2;
  const midY = (first.y + second.y) / 2;
  const spots: [typeof first, number][] = [
    [first, -1],
    [second, 1]
  ];
  spots.forEach(([actor, side]) => {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const candidate = clampToMap(
        world.scene,
        midX + side * (14 + attempt * 4),
        midY + side * 3
      );
      if (canStand(world.scene, candidate.x, candidate.y)) {
        actor.target = candidate;
        return;
      }
    }
  });

  world.guestChat = {
    ids: [script.between[0], script.between[1]],
    lines: script.lines,
    index: -1,
    nextAt: world.time + 6,
    stage: "approaching"
  };
}

/** Keeps the view inside the map so the void behind the room never shows. */
function clampCamera(world: PartyWorld, viewport: { width: number; height: number }) {
  const size = mapSize(world.scene);
  // Never zoom out past the map: a taller phone screen must still be filled.
  const cover = Math.max(viewport.width / size.width, viewport.height / size.height);
  world.camera.zoom = Math.max(world.camera.zoom, cover);
  const halfWidth = viewport.width / (2 * world.camera.zoom);
  const halfHeight = viewport.height / (2 * world.camera.zoom);
  world.camera.x =
    halfWidth * 2 >= size.width
      ? size.width / 2
      : Math.max(halfWidth, Math.min(size.width - halfWidth, world.camera.x));
  world.camera.y =
    halfHeight * 2 >= size.height
      ? size.height / 2
      : Math.max(halfHeight, Math.min(size.height - halfHeight, world.camera.y));
}

export function stepParty(
  world: PartyWorld,
  delta: number,
  viewport?: { width: number; height: number }
) {
  world.time += delta;
  world.phaseTime += delta;
  const player = playerOf(world);

  world.actors.forEach((actor, index) => {
    if (actor.bubble && actor.bubble.until <= world.time) actor.bubble = null;

    const frozen = world.phase === "frozen";
    const moving = frozen ? false : moveToward(actor, delta);

    if (actor.kind === "guest" && !frozen) {
      const persona = guestPersonas.find((entry) => entry.id === actor.personaId);
      const inPairChat =
        world.guestChat?.stage === "talking" &&
        world.guestChat.ids.includes(actor.id);
      const inConversation = world.conversation?.guestId === actor.id;
      if (inPairChat) {
        const partnerId = world.guestChat!.ids.find((id) => id !== actor.id);
        const partner = partnerId ? actorById(world, partnerId) : undefined;
        actor.target = null;
        if (partner) actor.facing = partner.x >= actor.x ? 1 : -1;
        actor.state = "greet";
      } else if (inConversation) {
        // Stop and face the player for the whole exchange.
        actor.target = null;
        actor.facing = player.x >= actor.x ? 1 : -1;
        actor.state = "greet";
      } else if (world.phase === "walking") {
        // Stop wandering and turn to watch the entrance.
        actor.target = null;
        actor.facing = player.x >= actor.x ? 1 : -1;
        actor.state = "idle";
      } else if (world.phase === "posing") {
        // Close in on the runway, then cheer at the performer.
        actor.state = moving ? "walk" : "cheer";
        if (!moving) actor.facing = player.x >= actor.x ? 1 : -1;
      } else {
        actor.speed = GUEST_SPEED;
        if (!actor.target && world.time > actor.nextTalkAt - 2) {
          wander(actor, world, world.time + index * 5.7);
        }
        actor.state = moving ? "walk" : "idle";
      }

      if (
        persona &&
        world.time >= actor.nextTalkAt &&
        !frozen &&
        !inConversation &&
        !inPairChat
      ) {
        const reason = persona.reasons[world.scene.id];
        const lines =
          world.phase === "walking" || world.phase === "posing"
            ? persona.runwayCheers
            : // Mixing in why they came keeps the chatter tied to this venue.
              reason
              ? [...persona.smallTalk, reason]
              : persona.smallTalk;
        const line =
          lines[Math.floor(noise(world.time + index * 11.3) * lines.length)];
        say(
          actor,
          line,
          world.phase === "walking" || world.phase === "posing"
            ? "reaction"
            : "speech",
          world.time
        );
        actor.nextTalkAt =
          world.time +
          persona.talkInterval * (0.7 + noise(world.time + index) * 0.6);
      }
    }

    if (actor.kind === "player" && !frozen) {
      if (world.phase === "walking") {
        actor.state = "walk";
      } else if (world.phase === "posing") {
        actor.state = "pose";
      } else if (moving) {
        actor.state = "walk";
      } else if (world.conversation) {
        actor.state = "greet";
      } else {
        actor.state = "idle";
      }
    }

    if (!frozen) {
      const cadence =
        actor.state === "walk"
          ? walkCadence(actor.speed)
          : actor.state === "cheer"
            ? 1.4
            : 0.55;
      actor.phase = (actor.phase + delta * cadence) % 1;
    }
  });

  // The walk ends when the player reaches the stage point.
  if (world.phase === "walking" && !player.target) {
    world.phase = "posing";
    world.phaseTime = 0;
    player.state = "pose";
    gatherAroundStage(world);
  }

  // Stepping onto the runway on your own gets the same reception as a
  // deliberate entrance; the crowd should not care how you got there.
  if (
    !frozenPhase(world) &&
    (world.phase === "mingling" || world.phase === "greeting") &&
    !player.target &&
    onRunway(world.scene, player.x, player.y)
  ) {
    endConversation(world);
    world.phase = "posing";
    world.phaseTime = 0;
    player.state = "pose";
    gatherAroundStage(world);
  }

  updateGreeting(world, player);
  advanceConversation(world);
  updateGuestChat(world);
  updateReactions(world);

  // Camera: follow the player, push in for the show, pull back when mingling.
  const showing =
    world.phase === "walking" ||
    world.phase === "posing" ||
    world.phase === "frozen";
  world.cameraTarget = {
    x: player.x,
    y: player.y - (showing ? 26 : 20),
    zoom: showing ? RUNWAY_ZOOM : ROAM_ZOOM
  };

  const follow = world.phase === "frozen" ? 0 : Math.min(1, delta * 3.2);
  world.camera.x += (world.cameraTarget.x - world.camera.x) * follow;
  world.camera.y += (world.cameraTarget.y - world.camera.y) * follow;
  world.camera.zoom += (world.cameraTarget.zoom - world.camera.zoom) * follow;

  const wantedVignette =
    world.phase === "walking" || world.phase === "posing" ? 0.62 : 0;
  world.vignette += (wantedVignette - world.vignette) * Math.min(1, delta * 2.4);

  if (viewport) clampCamera(world, viewport);
}

export function actorRigFrame(actor: Actor, height: number) {
  return rigFrame(actor.state, actor.phase, height);
}

/**
 * Raised tiles are drawn `elevation` pixels higher than their grid position, so
 * anyone standing on the runway has to be lifted by the same amount or they
 * sink into the platform and their shadow detaches from their feet.
 */
export function actorElevation(world: PartyWorld, actor: Actor): number {
  return tileAt(world.scene, actor.x, actor.y)?.elevation ?? 0;
}

/** Characters further back are drawn slightly smaller, which sells depth. */
export function actorHeight(world: PartyWorld, actor: Actor): number {
  const size = mapSize(world.scene);
  const depth = actor.y / size.height;
  // Everyone is the same size; the player is distinguished by the camera and
  // the spotlight, not by being drawn bigger than the room.
  return 38 + depth * 10;
}

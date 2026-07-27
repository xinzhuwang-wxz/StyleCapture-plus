import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  loadCharacterSprite,
  loadPoseSet,
  type PoseSet
} from "./world/spriteLoader";
import { createPartyWorld, type PartyWorld } from "./world/simulation";
import { sceneById, type SceneMap } from "./world/sceneMap";

export type LookSpriteSource = {
  lookId: string;
  url: string;
  /** User-supplied images still carry an illustration backdrop. */
  removeBackdrop: boolean;
  /** Folder of authored poses; when absent the Look animates procedurally. */
  poseRoot?: string;
};

/**
 * Owns the mutable party world and the sprites it draws.
 *
 * The world is deliberately a mutable object stepped by the render loop rather
 * than React state: sixty state updates a second would re-render the whole
 * screen. React only holds the things the UI actually reads.
 */
export function useParty(
  initialSceneId: string,
  playerLookId: string,
  sources: readonly LookSpriteSource[],
  /** Guests to place in the room; changing it rebuilds the world. */
  activeGuestIds: readonly string[]
) {
  const [sceneId, setSceneId] = useState(initialSceneId);
  const scene: SceneMap = useMemo(() => sceneById(sceneId), [sceneId]);
  const [sprites, setSprites] = useState<Record<string, PoseSet | undefined>>(
    {}
  );
  const [failedLookIds, setFailedLookIds] = useState<readonly string[]>([]);

  const worldRef = useRef<PartyWorld>(
    createPartyWorld(scene, playerLookId, activeGuestIds)
  );
  // Re-created only when the location changes; guests and choreography reset.
  const [worldVersion, setWorldVersion] = useState(0);

  useEffect(() => {
    const worn = worldRef.current.actors.find(
      (actor) => actor.id === worldRef.current.playerId
    )?.lookId;
    worldRef.current = createPartyWorld(scene, worn ?? playerLookId, activeGuestIds);
    setWorldVersion((version) => version + 1);
    // playerLookId is applied through updatePlayerLook to avoid resetting the
    // room every time the user changes outfit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, activeGuestIds]);

  useEffect(() => {
    let cancelled = false;
    sources.forEach((source) => {
      const pending = source.poseRoot
        ? loadPoseSet(source.poseRoot)
        : loadCharacterSprite({
            url: source.url,
            removeBackdrop: source.removeBackdrop
          }).then((sprite) => ({ idle: sprite }) satisfies PoseSet);
      pending
        .then((set) => {
          if (cancelled) return;
          setSprites((current) => ({ ...current, [source.lookId]: set }));
          setFailedLookIds((current) =>
            current.filter((id) => id !== source.lookId)
          );
        })
        .catch(() => {
          if (cancelled) return;
          setFailedLookIds((current) =>
            current.includes(source.lookId) ? current : [...current, source.lookId]
          );
        });
    });
    return () => {
      cancelled = true;
    };
  }, [sources]);

  const updatePlayerLook = useCallback((lookId: string) => {
    const world = worldRef.current;
    const player = world.actors.find((actor) => actor.id === world.playerId);
    if (player) player.lookId = lookId;
  }, []);

  return {
    scene,
    sceneId,
    setSceneId,
    world: worldRef.current,
    worldVersion,
    sprites,
    failedLookIds,
    updatePlayerLook
  };
}

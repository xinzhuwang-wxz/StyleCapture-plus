import { fitWithin } from "../src/media/downscaleImage";
import {
  MAX_REFERENCE_PHOTOS,
  activePhoto,
  addPhoto,
  emptyAlbum,
  isAlbumFull,
  photoAlbumStore,
  readPhotoAlbum,
  referencePhotoFile,
  removePhotos,
  setActivePhoto,
  writePhotoAlbum,
  type ReferencePhoto
} from "../src/features/profile/photoStorage";

function photo(id: string): ReferencePhoto {
  return {
    id,
    dataUrl: `data:image/jpeg;base64,${id}`,
    addedAt: "2026-07-27T00:00:00.000Z"
  };
}

function fill(count: number) {
  let album = emptyAlbum();
  for (let index = 0; index < count; index += 1) {
    album = addPhoto(album, photo(`p${index}`));
  }
  return album;
}

beforeEach(() => {
  const map = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => map.get(key) ?? null,
      setItem: (key: string, value: string) => void map.set(key, value),
      removeItem: (key: string) => void map.delete(key),
      clear: () => map.clear(),
      key: () => null,
      get length() {
        return map.size;
      }
    } as Storage
  });
});

describe("reference photo album", () => {
  it("makes the first photo the try-on reference automatically", () => {
    const album = addPhoto(emptyAlbum(), photo("a"));
    expect(album.activeId).toBe("a");
    expect(activePhoto(album)?.id).toBe("a");
  });

  it("keeps the chosen reference when later photos are added", () => {
    let album = fill(3);
    album = setActivePhoto(album, "p1");
    album = addPhoto(album, photo("p3"));
    expect(album.activeId).toBe("p1");
  });

  it("stops at the documented maximum rather than silently dropping one", () => {
    const album = fill(MAX_REFERENCE_PHOTOS);
    expect(isAlbumFull(album)).toBe(true);
    const overflowed = addPhoto(album, photo("extra"));
    expect(overflowed).toBe(album);
    expect(overflowed.photos).toHaveLength(MAX_REFERENCE_PHOTOS);
  });

  it("moves the reference on when the active photo is deleted", () => {
    let album = fill(3);
    album = setActivePhoto(album, "p1");
    album = removePhotos(album, ["p1"]);
    expect(album.photos.map((entry) => entry.id)).toEqual(["p0", "p2"]);
    expect(album.activeId).toBe("p0");
  });

  it("leaves no dangling reference when everything is deleted", () => {
    const album = removePhotos(fill(2), ["p0", "p1"]);
    expect(album.photos).toHaveLength(0);
    expect(album.activeId).toBeNull();
    expect(activePhoto(album)).toBeNull();
  });

  it("ignores a request to activate a photo that is not there", () => {
    const album = fill(2);
    expect(setActivePhoto(album, "ghost")).toBe(album);
  });

  it("round-trips through storage", () => {
    const album = setActivePhoto(fill(2), "p1");
    expect(writePhotoAlbum(album)).toEqual({ ok: true });
    expect(readPhotoAlbum()).toEqual(album);
  });

  it("drops stored entries that are not data URLs", () => {
    // A remote URL would turn a private photo into a network request.
    window.localStorage.setItem(
      photoAlbumStore.key,
      JSON.stringify({
        photos: [
          photo("good"),
          { id: "bad", dataUrl: "https://example.com/x.jpg", addedAt: "x" }
        ],
        activeId: "bad"
      })
    );
    const album = readPhotoAlbum();
    expect(album.photos.map((entry) => entry.id)).toEqual(["good"]);
    expect(album.activeId).toBe("good");
  });

  it("repairs an active id that points at nothing", () => {
    window.localStorage.setItem(
      photoAlbumStore.key,
      JSON.stringify({ photos: [photo("a")], activeId: "missing" })
    );
    expect(readPhotoAlbum().activeId).toBe("a");
  });

  it("caps an over-long stored album", () => {
    window.localStorage.setItem(
      photoAlbumStore.key,
      JSON.stringify({
        photos: Array.from({ length: 12 }, (_, index) => photo(`p${index}`)),
        activeId: "p0"
      })
    );
    expect(readPhotoAlbum().photos).toHaveLength(MAX_REFERENCE_PHOTOS);
  });

  it("turns an existing local portrait back into an uploadable file", () => {
    const file = referencePhotoFile({
      ...photo("ready"),
      dataUrl: `data:image/png;base64,${window.btoa("portrait")}`
    });
    expect(file.name).toBe("stylecapture-reference-ready.png");
    expect(file.type).toBe("image/png");
    expect(file.size).toBe("portrait".length);
  });
});

describe("downscale geometry", () => {
  it("shrinks the long edge and keeps the aspect ratio", () => {
    expect(fitWithin(3000, 4000, 720)).toEqual({ width: 540, height: 720 });
    expect(fitWithin(4000, 3000, 720)).toEqual({ width: 720, height: 540 });
  });

  it("never enlarges a small photo", () => {
    expect(fitWithin(300, 400, 720)).toEqual({ width: 300, height: 400 });
  });

  it("degrades safely on a zero-sized image", () => {
    expect(fitWithin(0, 0, 720)).toEqual({ width: 0, height: 0 });
  });
});

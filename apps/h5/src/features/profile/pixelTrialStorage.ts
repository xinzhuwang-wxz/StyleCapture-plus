const PIXEL_TRIAL_STORAGE_KEY = "stylecapture:pixel-trial:v1";
const PIXEL_TRIAL_CHANGED_EVENT = "stylecapture:pixel-trial-changed";

export function readPixelTrialId(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.sessionStorage.getItem(PIXEL_TRIAL_STORAGE_KEY);
  return stored && stored.trim() ? stored : null;
}

export function writePixelTrialId(trialId: string | null): void {
  if (typeof window === "undefined") return;
  if (trialId) {
    window.sessionStorage.setItem(PIXEL_TRIAL_STORAGE_KEY, trialId);
  } else {
    window.sessionStorage.removeItem(PIXEL_TRIAL_STORAGE_KEY);
  }
  window.dispatchEvent(new Event(PIXEL_TRIAL_CHANGED_EVENT));
}

export function subscribeToPixelTrialId(listener: () => void): () => void {
  window.addEventListener(PIXEL_TRIAL_CHANGED_EVENT, listener);
  return () => window.removeEventListener(PIXEL_TRIAL_CHANGED_EVENT, listener);
}

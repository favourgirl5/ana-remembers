// Remembers the login on this device, so the patient doesn't have to log in every time.
// Browser: localStorage. On a phone this should become expo-secure-store (encrypted).
const KEY = 'ana-session';

export function saveSession(session) {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, JSON.stringify(session));
  } catch (e) {}
}

export function loadSession() {
  try {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function clearSession() {
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(KEY);
  } catch (e) {}
}
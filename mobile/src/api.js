// Talks to the FastAPI backend (api.py). The app never calls Gemini or SQL Server directly.
import { API_URL } from './config';

let authToken = null;
let onUnauthorized = null;

// Called after login/logout, so every request carries the login token.
export function setAuthToken(token) {
  authToken = token;
}

// Called when the API says the login has expired (401), so the app can log out.
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let res;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch (e) {
    throw new Error("Can't reach Ana's server. Is the API running?");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && authToken) onUnauthorized?.();
  if (!res.ok) {
    throw new Error(data.detail || `Something went wrong (error ${res.status}).`);
  }
  return data;
}

export const login = (email, password) =>
  request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });

export const getPatient = (patientId) => request(`/patients/${patientId}`);

export const getProgress = (patientId) => request(`/patients/${patientId}/progress`);

export const startCheckin = (patientId) =>
  request('/checkins/start', {
    method: 'POST',
    body: JSON.stringify({ patient_id: patientId }),
  });

export const sendReply = (checkinId, message) =>
  request(`/checkins/${checkinId}/reply`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });

export const retryReply = (checkinId) =>
  request(`/checkins/${checkinId}/retry`, { method: 'POST' });

export const endCheckin = (checkinId) =>
  request(`/checkins/${checkinId}/end`, { method: 'POST' });
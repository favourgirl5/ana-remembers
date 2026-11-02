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
  // A file upload (FormData) sets its own Content-Type; everything else is JSON.
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
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

export const register = (fullName, email, password, dateOfBirth) =>
  request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ full_name: fullName, email, password, date_of_birth: dateOfBirth }),
  });

// file = one result from expo-document-picker. On the web it has a real File object;
// on a phone, React Native uploads it from its uri.
export function uploadReport(patientId, file) {
  const form = new FormData();
  if (file.file) {
    form.append('file', file.file, file.name);
  } else {
    form.append('file', { uri: file.uri, name: file.name, type: file.mimeType });
  }
  return request(`/patients/${patientId}/reports/extract`, { method: 'POST', body: form });
}

export const confirmReport = (patientId, records) =>
  request(`/patients/${patientId}/reports/confirm`, {
    method: 'POST',
    body: JSON.stringify(records),
  });
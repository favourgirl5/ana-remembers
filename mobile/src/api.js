// Talks to the FastAPI backend (api.py). The app never calls Gemini or SQL Server directly.
import { API_URL } from './config';

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (e) {
    throw new Error("Can't reach Ana's server. Is the API running?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Something went wrong (error ${res.status}).`);
  }
  return data;
}

export const getPatient = (patientId) => request(`/patients/${patientId}`);

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

export const endCheckin = (checkinId) =>
  request(`/checkins/${checkinId}/end`, { method: 'POST' });

export const getProgress = (patientId) => request(`/patients/${patientId}/progress`);
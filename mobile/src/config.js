import { Platform } from 'react-native';

// The patient this app is signed in as (Mario in the test database).
export const PATIENT_ID = 1;

// Where the FastAPI backend (api.py) runs.
// - In the browser on this laptop, localhost works.
// - On a phone, use the laptop's WiFi address (Expo shows it as "Metro: exp://192.168.0.102:8081")
//   and start the API with:  python -m uvicorn api:app --reload --host 0.0.0.0
export const API_URL =
  Platform.OS === 'web' ? 'http://127.0.0.1:8000' : 'http://192.168.0.102:8000';
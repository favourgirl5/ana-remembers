// Ana's voice (text-to-speech) and the patient's voice (speech-to-text).
// Free, built-in options only. Kept in one file so they can be swapped later
// (e.g. ElevenLabs for Ana's voice, Whisper for speech-to-text).
import * as Speech from 'expo-speech';
import { Platform } from 'react-native';

const VOICE_OPTIONS = { language: 'en-GB', rate: 0.95 };

// ---------- Ana speaks ----------

export function speak(text, onDone) {
  Speech.stop();
  Speech.speak(text, { ...VOICE_OPTIONS, onDone });
}

export function stopSpeaking() {
  Speech.stop();
}

// ---------- Patient speaks ----------
// Uses the browser's built-in speech recognition (Chrome/Edge on the laptop).
// On a phone this needs another library and an Expo development build (future work).
// Note: in Chrome the audio is processed by Google's speech service.

export function isListeningSupported() {
  return (
    Platform.OS === 'web' &&
    typeof window !== 'undefined' &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition)
  );
}

// Starts the microphone. Stops by itself when the patient pauses.
// Returns { stop, cancel }: stop() finishes and delivers the text, cancel() throws it away.
export function startListening({ onResult, onEnd, onError, lang = 'en-GB' }) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Recognition();
  rec.lang = lang;
  rec.interimResults = true; // show words while the patient is still talking
  rec.continuous = false; // end after a pause

  let finalText = '';
  rec.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const piece = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += piece;
      else interim += piece;
    }
    onResult?.((finalText + interim).trim());
  };
  rec.onerror = (event) => onError?.(event.error);
  rec.onend = () => onEnd?.(finalText.trim());
  rec.start();

  return {
    stop: () => rec.stop(),
    cancel: () => {
      rec.onend = null;
      rec.onresult = null;
      rec.abort();
    },
  };
}
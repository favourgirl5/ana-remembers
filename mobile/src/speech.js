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

const SILENCE_MS = 3500; // wait this long after the patient stops talking before sending
const NO_SPEECH_MS = 12000; // give up if the patient says nothing at all for this long

// Starts the microphone. It keeps listening through short pauses and only finishes
// after SILENCE_MS of quiet (so slower speakers aren't cut off).
// Returns { stop, cancel }: stop() finishes and delivers the text, cancel() throws it away.
export function startListening({ onResult, onEnd, onError, lang = 'en-GB', silenceMs = SILENCE_MS }) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Recognition();
  rec.lang = lang;
  rec.interimResults = true; // show words while the patient is still talking
  rec.continuous = true; // don't stop at the first short pause; we decide when they're done

  let finalText = '';
  let timer = null;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    rec.stop(); // triggers onend, which delivers the text
  };
  const waitFor = (ms) => {
    clearTimeout(timer);
    timer = setTimeout(finish, ms);
  };

  rec.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const piece = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += piece + ' ';
      else interim += piece;
    }
    onResult?.((finalText + interim).trim());
    waitFor(silenceMs); // the patient is talking: restart the pause timer
  };
  rec.onerror = (event) => onError?.(event.error);
  rec.onend = () => {
    clearTimeout(timer);
    onEnd?.(finalText.trim());
  };

  rec.start();
  waitFor(NO_SPEECH_MS);

  return {
    stop: finish,
    cancel: () => {
      finished = true;
      clearTimeout(timer);
      rec.onend = null;
      rec.onresult = null;
      rec.abort();
    },
  };
}
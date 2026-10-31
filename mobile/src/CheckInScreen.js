import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import AnaAvatar from './AnaAvatar';
import { sendReply, startCheckin } from './api';
import { isListeningSupported, speak, startListening, stopSpeaking } from './speech';
import { colors, serif } from './theme';

const QUICK_REPLIES = ['Yes, all done', 'Not yet', 'I forgot'];
// Only a question about TAKING medication gets the quick-reply buttons.
const MEDICATION_QUESTION = /(take|taken|took|had)\b[^?]*\b(medic|pill|tablet|dose)[^?]*\?/i;
const SHOW_MEDS_AFTER = ['Not yet', 'I forgot'];

function greetingFor(date) {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function CheckInScreen({ patient, settings }) {
  const [messages, setMessages] = useState([]); // { from: 'ana' | 'patient', text, meds? }
  const [checkinId, setCheckinId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | chatting | done
  const [busy, setBusy] = useState(false); // waiting for Ana
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const [listening, setListening] = useState(false); // microphone is on
  const [hint, setHint] = useState('');
  const scrollRef = useRef(null);
  const micRef = useRef(null); // the running microphone, if any
  const sendRef = useRef(null); // latest handleSend, used when the microphone finishes
  const canListen = isListeningSupported();

  // ---------- Microphone ----------
  function startMic() {
    if (!canListen || micRef.current) return;
    stopSpeaking(); // never listen while Ana is still talking
    setHint('');
    setInput('');
    setListening(true);
    let blocked = false;
    micRef.current = startListening({
      onResult: (text) => setInput(text), // show what the app heard
      onError: (err) => {
        if (err === 'not-allowed') {
          blocked = true;
          setHint('Microphone access is blocked. Allow it in the browser to talk to Ana.');
        }
      },
      onEnd: (finalText) => {
        micRef.current = null;
        setListening(false);
        if (finalText) sendRef.current?.(finalText);
        else if (!blocked) {
          setHint("I didn't catch that. Tap the microphone to try again, or type your answer.");
        }
      },
    });
  }

  function stopMic() {
    micRef.current?.stop(); // finishes and sends what was heard
  }

  function cancelMic() {
    micRef.current?.cancel();
    micRef.current = null;
    setListening(false);
  }

  // ---------- Ana's voice + hands-free ----------
  // When Ana sends a message: read it aloud (if voice is on), then listen (if hands-free is on).
  // Runs on the device: no Gemini requests.
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.from !== 'ana') return;
    const listenAfter = settings.handsFree && status === 'chatting';
    if (settings.voiceOn) {
      speak(last.text, () => {
        if (listenAfter) startMic();
      });
    } else if (listenAfter) {
      startMic();
    }
  }, [messages]);

  useEffect(() => {
    if (!settings.voiceOn) stopSpeaking();
  }, [settings.voiceOn]);

  // Stop voice and microphone when leaving the screen
  useEffect(() => () => {
    stopSpeaking();
    micRef.current?.cancel();
  }, []);

  const now = new Date();
  const firstName = patient.patient.FullName?.split(' ')[0] ?? '';
  const dateLabel = now
    .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
    .toUpperCase();

  const lastMessage = messages[messages.length - 1];
  const showQuickReplies =
    status === 'chatting' &&
    !busy &&
    !listening &&
    lastMessage?.from === 'ana' &&
    MEDICATION_QUESTION.test(lastMessage.text);

  // Starting costs one Gemini request, so it waits for a tap instead of running on every reload.
  async function handleStart() {
    setError('');
    setBusy(true);
    try {
      const data = await startCheckin(patient.patient.PatientID);
      setCheckinId(data.checkin_id);
      setMessages([{ from: 'ana', text: data.ana_message }]);
      setStatus('chatting');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(text) {
    const message = text.trim();
    if (!message || busy || status !== 'chatting') return;
    if (micRef.current) cancelMic();
    setError('');
    setHint('');
    setInput('');
    setMessages((m) => [...m, { from: 'patient', text: message }]);
    setBusy(true);
    try {
      const data = await sendReply(checkinId, message);
      const meds = SHOW_MEDS_AFTER.includes(message) ? patient.medications : null;
      setMessages((m) => [...m, { from: 'ana', text: data.ana_reply, meds }]);
      setStatus(data.done ? 'done' : 'chatting');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  sendRef.current = handleSend;

  // Clear the finished conversation so the patient can start a new check-in.
  function resetCheckin() {
    stopSpeaking();
    cancelMic();
    setHint('');
    setMessages([]);
    setCheckinId(null);
    setInput('');
    setError('');
    setStatus('idle');
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        ref={scrollRef}
        style={styles.flex}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
      >
        <Text style={styles.date}>{dateLabel}</Text>
        <Text style={styles.greeting}>
          {greetingFor(now)}
          {firstName ? `, ${firstName}` : ''}.
        </Text>
        <Text style={styles.subtitle}>Let's take a quiet moment to check in.</Text>

        {status === 'idle' && (
          <Pressable
            style={({ pressed }) => [styles.startButton, pressed && styles.pressed]}
            onPress={handleStart}
            disabled={busy}
          >
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.startText}>Start today's check-in</Text>
            )}
          </Pressable>
        )}

        {messages.map((m, i) =>
          m.from === 'ana' ? (
            <AnaMessage key={i} text={m.text} meds={m.meds} />
          ) : (
            <View key={i} style={styles.patientBubble}>
              <Text style={styles.patientText}>{m.text}</Text>
            </View>
          )
        )}

        {busy && status !== 'idle' && (
          <View style={styles.typing}>
            <AnaAvatar size={28} />
            <Text style={styles.typingText}>Ana is typing…</Text>
          </View>
        )}

        {showQuickReplies && (
          <View style={styles.quickReplies}>
            {QUICK_REPLIES.map((label, i) => (
              <Pressable
                key={label}
                onPress={() => handleSend(label)}
                style={({ pressed }) => [
                  styles.quickReply,
                  i === 0 && styles.quickReplyPrimary,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.quickReplyText, i === 0 && styles.quickReplyTextPrimary]}>
                  {i === 0 ? '✓  ' : ''}
                  {label}
                </Text>
              </Pressable>
            ))}
          </View>
        )}

        {status === 'done' && (
          <>
            <Text style={styles.doneNote}>
              Today's check-in is saved. You can come back and talk any time.
            </Text>
            <Pressable
              style={({ pressed }) => [styles.startButton, styles.againButton, pressed && styles.pressed]}
              onPress={resetCheckin}
            >
              <Text style={styles.startText}>Start a new check-in</Text>
            </Pressable>
          </>
        )}

        {hint ? <Text style={styles.hint}>{hint}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>

      {listening && (
        <View style={styles.listeningBar}>
          <View style={styles.listeningDot} />
          <Text style={styles.listeningText}>Ana is listening… speak now</Text>
        </View>
      )}

      {status === 'chatting' && (
        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder={listening ? 'Listening…' : 'Or tell Ana in your own words…'}
            placeholderTextColor={colors.muted}
            onSubmitEditing={() => handleSend(input)}
            returnKeyType="send"
            editable={!busy}
          />
          {canListen && (
            <Pressable
              style={[styles.micButton, listening && styles.micActive, busy && styles.sendDisabled]}
              onPress={listening ? stopMic : startMic}
              disabled={busy}
            >
              <Text style={styles.micIcon}>{listening ? '■' : '🎤'}</Text>
            </Pressable>
          )}
          <Pressable
            style={[styles.sendButton, (!input.trim() || busy) && styles.sendDisabled]}
            onPress={() => handleSend(input)}
            disabled={!input.trim() || busy}
          >
            <Text style={styles.sendIcon}>➤</Text>
          </Pressable>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

function AnaMessage({ text, meds }) {
  return (
    <View style={styles.anaRow}>
      <AnaAvatar size={28} />
      <View style={styles.anaColumn}>
        <Text style={styles.anaLabel}>Ana</Text>
        <View style={styles.anaBubble}>
          <Text style={styles.anaText}>{text}</Text>
          {meds?.length ? (
            <View style={styles.medCard}>
              {meds.map((med, i) => (
                <View key={i} style={[styles.medRow, i > 0 && styles.medDivider]}>
                  <View style={styles.medDot} />
                  <Text style={styles.medName}>{med.MedicationName}</Text>
                  <Text style={styles.medDose}>{med.Dosage}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { padding: 20, paddingBottom: 32 },
  pressed: { opacity: 0.7 },

  date: { fontSize: 11, fontWeight: '700', letterSpacing: 1, color: colors.primary, marginTop: 8 },
  greeting: { fontFamily: serif, fontSize: 30, color: colors.text, marginTop: 6 },
  subtitle: { fontSize: 14, color: colors.muted, marginTop: 6, marginBottom: 24 },

  startButton: {
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  startText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  againButton: { marginTop: 16 },

  anaRow: { flexDirection: 'row', gap: 10, marginBottom: 14, alignItems: 'flex-start' },
  anaColumn: { flex: 1, alignItems: 'flex-start' },
  anaLabel: { fontSize: 11, color: colors.muted, marginBottom: 4 },
  anaBubble: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderTopLeftRadius: 4,
    padding: 14,
    maxWidth: '92%',
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  anaText: { fontSize: 15, lineHeight: 21, color: colors.text },

  patientBubble: {
    alignSelf: 'flex-end',
    backgroundColor: colors.primary,
    borderRadius: 16,
    borderTopRightRadius: 4,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 14,
    maxWidth: '80%',
  },
  patientText: { fontSize: 15, lineHeight: 21, color: '#fff' },

  medCard: {
    marginTop: 12,
    borderRadius: 12,
    backgroundColor: colors.bg,
    paddingHorizontal: 12,
  },
  medRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, gap: 10 },
  medDivider: { borderTopWidth: 1, borderTopColor: colors.border },
  medDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.avatar },
  medName: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text },
  medDose: { fontSize: 13, color: colors.muted },

  typing: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 14 },
  typingText: { fontSize: 13, color: colors.muted, fontStyle: 'italic' },

  quickReplies: { marginLeft: 38, gap: 10, marginBottom: 14 },
  quickReply: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  quickReplyPrimary: { backgroundColor: colors.primary, borderColor: colors.primary },
  quickReplyText: { fontSize: 14, color: colors.text, fontWeight: '500' },
  quickReplyTextPrimary: { color: '#fff', fontWeight: '600' },

  doneNote: { textAlign: 'center', color: colors.muted, fontSize: 13, marginTop: 8 },
  error: { textAlign: 'center', color: colors.error, fontSize: 13, marginTop: 12 },
  hint: { textAlign: 'center', color: colors.muted, fontSize: 13, marginTop: 8 },

  listeningBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 8,
    backgroundColor: colors.primarySoft,
  },
  listeningDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.error },
  listeningText: { fontSize: 13, color: colors.primary, fontWeight: '600' },

  micButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  micActive: { backgroundColor: colors.error, borderColor: colors.error },
  micIcon: { fontSize: 18, color: colors.primary },

  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: colors.bg,
  },
  input: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: colors.text,
  },
  sendButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.4 },
  sendIcon: { color: '#fff', fontSize: 16 },
});
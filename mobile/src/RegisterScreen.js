// New patient: create an account, then (optionally) upload a medical report.
// Only after that step does the app log in, so App.js needs no changes for this.
import { useState } from 'react';
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
import UploadScreen from './UploadScreen';
import { register, setAuthToken } from './api';
import { colors, serif } from './theme';

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export default function RegisterScreen({ onRegistered, onBack }) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [dob, setDob] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [account, setAccount] = useState(null); // set after the account is created

  async function handleRegister() {
    if (busy) return;
    if (fullName.trim().length < 2) return setError('Please enter your full name.');
    if (!email.includes('@')) return setError('Please enter a valid email address.');
    if (password.length < 8) return setError('Your password needs at least 8 characters.');
    if (!DATE_PATTERN.test(dob.trim())) return setError('Please enter your date of birth as YYYY-MM-DD, e.g. 1966-04-21.');

    setError('');
    setBusy(true);
    try {
      const data = await register(fullName.trim(), email.trim(), password, dob.trim());
      setAuthToken(data.token); // needed for the upload step
      setAccount(data);
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  if (account) {
    return (
      <UploadScreen
        patientId={account.patient_id}
        onDone={() => onRegistered(account)}
        doneLabel="Go to Ana"
        skipLabel="Skip for now (you can do this later in Settings)"
      />
    );
  }

  const ready = fullName.trim() && email.trim() && password && dob.trim();

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.avatar}>
          <AnaAvatar size={64} />
        </View>
        <Text style={styles.heading}>Create your account</Text>
        <Text style={styles.subtitle}>Ana will check in with you about how you're doing.</Text>

        <Field label="Full name" value={fullName} onChange={setFullName} placeholder="e.g. Els Bakker" />
        <Field
          label="Email"
          value={email}
          onChange={setEmail}
          placeholder="you@example.com"
          autoCapitalize="none"
          keyboardType="email-address"
        />
        <Field
          label="Password (at least 8 characters)"
          value={password}
          onChange={setPassword}
          placeholder="Choose a password"
          secureTextEntry
        />
        <Field
          label="Date of birth"
          value={dob}
          onChange={setDob}
          placeholder="YYYY-MM-DD"
          keyboardType="numbers-and-punctuation"
          onSubmitEditing={handleRegister}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={({ pressed }) => [styles.button, !ready && styles.disabled, pressed && styles.pressed]}
          onPress={handleRegister}
          disabled={!ready || busy}
        >
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Create account</Text>}
        </Pressable>

        <Pressable style={styles.linkButton} onPress={onBack}>
          <Text style={styles.linkText}>I already have an account</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Field({ label, value, onChange, ...props }) {
  return (
    <>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChange}
        placeholderTextColor={colors.muted}
        {...props}
      />
    </>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
  content: { padding: 24, paddingTop: 36 },
  avatar: { alignItems: 'center', marginBottom: 16 },
  heading: { fontFamily: serif, fontSize: 28, color: colors.text, textAlign: 'center' },
  subtitle: { fontSize: 14, color: colors.muted, textAlign: 'center', marginTop: 6, marginBottom: 24 },
  label: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 6 },
  input: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.text,
    marginBottom: 16,
  },
  error: { color: colors.error, fontSize: 13, textAlign: 'center', marginBottom: 12 },
  button: { backgroundColor: colors.primary, borderRadius: 14, paddingVertical: 14, alignItems: 'center', marginTop: 4 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  linkButton: { alignItems: 'center', paddingVertical: 16 },
  linkText: { color: colors.primary, fontSize: 14, fontWeight: '600' },
});
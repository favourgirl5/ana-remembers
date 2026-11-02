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
import RegisterScreen from './RegisterScreen';
import { login } from './api';
import { colors, serif } from './theme';

export default function LoginScreen({ onLogin, notice }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [registering, setRegistering] = useState(false);

  async function handleLogin() {
    if (!email.trim() || !password || busy) return;
    setError('');
    setBusy(true);
    try {
      const data = await login(email.trim(), password);
      onLogin(data);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  if (registering) {
    return <RegisterScreen onRegistered={onLogin} onBack={() => setRegistering(false)} />;
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.avatar}>
          <AnaAvatar size={72} />
        </View>
        <Text style={styles.heading}>Welcome to Ana</Text>
        <Text style={styles.subtitle}>Log in to start your check-in.</Text>

        {notice ? <Text style={styles.notice}>{notice}</Text> : null}

        <Text style={styles.label}>Email</Text>
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          placeholder="you@example.com"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          returnKeyType="next"
        />

        <Text style={styles.label}>Password</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder="Your password"
          placeholderTextColor={colors.muted}
          secureTextEntry
          autoComplete="password"
          returnKeyType="go"
          onSubmitEditing={handleLogin}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={({ pressed }) => [
            styles.button,
            (!email.trim() || !password) && styles.disabled,
            pressed && styles.pressed,
          ]}
          onPress={handleLogin}
          disabled={!email.trim() || !password || busy}
        >
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Log in</Text>}
        </Pressable>

        <Pressable style={styles.linkButton} onPress={() => setRegistering(true)}>
          <Text style={styles.linkText}>New here? Create an account</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
  content: { padding: 24, paddingTop: 48 },
  avatar: { alignItems: 'center', marginBottom: 20 },
  heading: { fontFamily: serif, fontSize: 30, color: colors.text, textAlign: 'center' },
  subtitle: { fontSize: 14, color: colors.muted, textAlign: 'center', marginTop: 6, marginBottom: 28 },
  notice: {
    backgroundColor: colors.primarySoft,
    color: colors.primary,
    borderRadius: 12,
    padding: 12,
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 16,
    overflow: 'hidden',
  },
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
  button: {
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  linkButton: { alignItems: 'center', paddingVertical: 16 },
  linkText: { color: colors.primary, fontSize: 14, fontWeight: '600' },
});
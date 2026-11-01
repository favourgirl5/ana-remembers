import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StatusBar as RNStatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import AnaAvatar from './src/AnaAvatar';
import CheckInScreen from './src/CheckInScreen';
import LoginScreen from './src/LoginScreen';
import ProgressScreen from './src/ProgressScreen';
import SettingsScreen from './src/SettingsScreen';
import { getPatient, setAuthToken, setUnauthorizedHandler } from './src/api';
import { stopSpeaking } from './src/speech';
import { clearSession, loadSession, loadSettings, saveSession, saveSettings } from './src/storage';
import { colors, serif } from './src/theme';

export default function App() {
  // Restore a saved login, so the patient stays logged in between visits.
  const [auth, setAuth] = useState(() => {
    const saved = loadSession();
    if (saved?.token) setAuthToken(saved.token);
    return saved;
  });
  const [notice, setNotice] = useState(''); // message shown on the login screen
  const [tab, setTab] = useState('checkin'); // checkin | progress | settings
  const [patient, setPatient] = useState(null);
  const [error, setError] = useState('');
  const [settings, setSettings] = useState({ voiceOn: false, handsFree: false });

  // Load this patient's saved voice settings when they log in.
  useEffect(() => {
    if (auth) setSettings(loadSettings(auth.patientId) ?? { voiceOn: false, handsFree: false });
  }, [auth?.patientId]);

  function changeSettings(next) {
    setSettings(next);
    if (auth) saveSettings(auth.patientId, next);
  }

  function handleLogin(data) {
    setAuthToken(data.token);
    setNotice('');
    const session = {
      token: data.token,
      patientId: data.patient_id,
      fullName: data.full_name,
      email: data.email,
    };
    saveSession(session);
    setAuth(session);
  }

  function handleLogout(message = '') {
    clearSession();
    stopSpeaking();
    setAuthToken(null);
    setAuth(null);
    setPatient(null);
    setError('');
    setTab('checkin');
    setNotice(message);
  }

  // If the API says the login has expired, go back to the login screen.
  useEffect(() => {
    setUnauthorizedHandler(() => handleLogout('Your session has ended. Please log in again.'));
  }, []);

  // Loads Ana's memory of the logged-in patient. Costs no Gemini requests.
  function loadPatient() {
    if (!auth) return;
    setError('');
    getPatient(auth.patientId)
      .then(setPatient)
      .catch((e) => setError(e.message));
  }

  useEffect(loadPatient, [auth]);

  const initials = (patient?.patient.FullName ?? '')
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <View style={styles.page}>
      <View style={styles.phone}>
        <StatusBar style="dark" />

        {!auth ? (
          <LoginScreen onLogin={handleLogin} notice={notice} />
        ) : (
          <>
            {/* Header */}
            <View style={styles.header}>
              <View style={styles.headerLeft}>
                <AnaAvatar size={36} />
                <View>
                  <Text style={styles.headerName}>Ana</Text>
                  <View style={styles.onlineRow}>
                    <View style={styles.onlineDot} />
                    <Text style={styles.onlineText}>Here with you</Text>
                  </View>
                </View>
              </View>
              {initials ? (
                <Pressable style={styles.initials} onPress={() => setTab('settings')}>
                  <Text style={styles.initialsText}>{initials}</Text>
                </Pressable>
              ) : null}
            </View>

            {/* Screens */}
            <View style={styles.flex}>
              {error ? (
                <View style={styles.center}>
                  <Text style={styles.errorText}>{error}</Text>
                  <Pressable style={styles.retryButton} onPress={loadPatient}>
                    <Text style={styles.retryText}>Try again</Text>
                  </Pressable>
                </View>
              ) : !patient ? (
                <View style={styles.center}>
                  <ActivityIndicator color={colors.primary} />
                </View>
              ) : (
                <>
                  {/* Kept mounted so the conversation survives switching tabs.
                      The key resets it when a different patient logs in. */}
                  <View style={[styles.flex, tab !== 'checkin' && styles.hidden]}>
                    <CheckInScreen key={auth.patientId} patient={patient} settings={settings} />
                  </View>
                  {tab === 'progress' && <ProgressScreen patientId={auth.patientId} />}
                  {tab === 'settings' && (
                    <SettingsScreen
                      settings={settings}
                      onChange={changeSettings}
                      profile={{ fullName: auth.fullName, email: auth.email, initials }}
                      onLogout={() => handleLogout()}
                    />
                  )}
                </>
              )}
            </View>

            {/* Bottom tabs */}
            <View style={styles.tabBar}>
              <TabButton label="Check-in" active={tab === 'checkin'} onPress={() => setTab('checkin')} />
              <TabButton label="My progress" active={tab === 'progress'} onPress={() => setTab('progress')} />
              <TabButton label="Settings" active={tab === 'settings'} onPress={() => setTab('settings')} />
            </View>
          </>
        )}
      </View>
    </View>
  );
}

function TabButton({ label, active, onPress }) {
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && styles.tabActive]}>
      <Text style={[styles.tabText, active && styles.tabTextActive]}>{label}</Text>
    </Pressable>
  );
}

const topPadding =
  Platform.OS === 'android' ? (RNStatusBar.currentHeight ?? 24) + 8 : Platform.OS === 'ios' ? 54 : 14;

const styles = StyleSheet.create({
  flex: { flex: 1 },
  hidden: { display: 'none' },
  page: { flex: 1, backgroundColor: colors.page, alignItems: 'center' },
  // In the browser the app is shown phone-sized; on a phone it fills the screen.
  phone: { flex: 1, width: '100%', maxWidth: 440, backgroundColor: colors.bg },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: topPadding,
    paddingBottom: 10,
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerName: { fontFamily: serif, fontSize: 20, color: colors.text },
  onlineRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  onlineDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.online },
  onlineText: { fontSize: 11, color: colors.muted },
  initials: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initialsText: { fontSize: 12, fontWeight: '700', color: colors.primary },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  errorText: { color: colors.error, textAlign: 'center', marginBottom: 12 },
  retryButton: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 18 },
  retryText: { color: '#fff', fontWeight: '600' },

  tabBar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: 10,
    paddingBottom: Platform.OS === 'ios' ? 28 : 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bg,
  },
  tab: { paddingVertical: 8, paddingHorizontal: 14, borderRadius: 12 },
  tabActive: { backgroundColor: colors.primarySoft },
  tabText: { fontSize: 13, color: colors.muted },
  tabTextActive: { color: colors.primary, fontWeight: '600' },
});
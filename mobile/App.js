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
import { getPatient } from './src/api';
import { PATIENT_ID } from './src/config';
import { colors, serif } from './src/theme';

export default function App() {
  const [tab, setTab] = useState('checkin'); // checkin | progress
  const [patient, setPatient] = useState(null);
  const [error, setError] = useState('');

  // Loads Ana's memory of the patient. Costs no Gemini requests.
  function loadPatient() {
    setError('');
    getPatient(PATIENT_ID)
      .then(setPatient)
      .catch((e) => setError(e.message));
  }

  useEffect(loadPatient, []);

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
            <View style={styles.initials}>
              <Text style={styles.initialsText}>{initials}</Text>
            </View>
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
              {/* Kept mounted so the conversation survives switching tabs */}
              <View style={[styles.flex, tab !== 'checkin' && styles.hidden]}>
                <CheckInScreen patient={patient} />
              </View>
              {tab === 'progress' && (
                <View style={styles.center}>
                  <Text style={styles.comingTitle}>Your progress</Text>
                  <Text style={styles.comingText}>Coming soon.</Text>
                </View>
              )}
            </>
          )}
        </View>

        {/* Bottom tabs */}
        <View style={styles.tabBar}>
          <TabButton label="Check-in" active={tab === 'checkin'} onPress={() => setTab('checkin')} />
          <TabButton label="My progress" active={tab === 'progress'} onPress={() => setTab('progress')} />
        </View>
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
  comingTitle: { fontFamily: serif, fontSize: 24, color: colors.text },
  comingText: { color: colors.muted, marginTop: 6 },

  tabBar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: 10,
    paddingBottom: Platform.OS === 'ios' ? 28 : 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bg,
  },
  tab: { paddingVertical: 8, paddingHorizontal: 18, borderRadius: 12 },
  tabActive: { backgroundColor: colors.primarySoft },
  tabText: { fontSize: 13, color: colors.muted },
  tabTextActive: { color: colors.primary, fontWeight: '600' },
});
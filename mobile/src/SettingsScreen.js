import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import UploadScreen from './UploadScreen';
import { isListeningSupported, speak } from './speech';
import { colors, serif } from './theme';

export default function SettingsScreen({ settings, onChange, profile, onLogout, onRecordsUpdated }) {
  const canListen = isListeningSupported();
  const [uploading, setUploading] = useState(false);

  if (uploading) {
    return (
      <UploadScreen
        patientId={profile?.patientId}
        doneLabel="Back to settings"
        skipLabel="Back to settings"
        onDone={(changed) => {
          setUploading(false);
          if (changed) onRecordsUpdated?.(); // reload what Ana knows
        }}
      />
    );
  }
  const firstName = profile?.fullName?.split(' ')[0];

  function toggle(key) {
    onChange({ ...settings, [key]: !settings[key] });
  }

  // Plays a sample on the device/browser itself. Costs no Gemini requests.
  function testVoice() {
    speak(`Hi ${firstName || 'there'}, this is how I will sound when I read my messages to you.`);
  }

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.label}>SETTINGS</Text>
      <Text style={styles.heading}>Your account and preferences</Text>

      {/* Profile */}
      <Text style={styles.section}>Profile</Text>
      <View style={styles.card}>
        <View style={styles.profileRow}>
          <View style={styles.initials}>
            <Text style={styles.initialsText}>{profile?.initials}</Text>
          </View>
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>{profile?.fullName}</Text>
            <Text style={styles.rowDescription}>{profile?.email}</Text>
          </View>
        </View>
        <Pressable
          style={({ pressed }) => [styles.logoutButton, pressed && styles.pressed]}
          onPress={onLogout}
        >
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </View>

      {/* Medical records */}
      <Text style={styles.section}>Medical records</Text>
      <View style={styles.card}>
        <Text style={styles.rowTitle}>Upload a medical report</Text>
        <Text style={styles.rowDescription}>
          Add a PDF or photo of a report from your doctor or hospital. Ana will show you what she
          found, so you can check it before anything is saved.
        </Text>
        <Pressable
          style={({ pressed }) => [styles.testButton, pressed && styles.pressed]}
          onPress={() => setUploading(true)}
        >
          <Text style={styles.testText}>📄  Upload a report</Text>
        </Pressable>
      </View>

      {/* Talking with Ana */}
      <Text style={styles.section}>Talking with Ana</Text>
      <View style={styles.card}>
        <SettingRow
          title="Ana speaks out loud"
          description="Ana reads her messages to you."
          value={settings.voiceOn}
          onToggle={() => toggle('voiceOn')}
        />
        <Pressable
          style={({ pressed }) => [styles.testButton, pressed && styles.pressed]}
          onPress={testVoice}
        >
          <Text style={styles.testText}>▶  Test Ana's voice</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <SettingRow
          title="Hands-free listening"
          description="After Ana speaks, the microphone turns on by itself so you can simply answer. It stops when you pause."
          value={settings.handsFree && canListen}
          onToggle={() => toggle('handsFree')}
          disabled={!canListen}
          note={canListen ? null : 'Not available here yet'}
        />
      </View>

      <Text style={styles.footnote}>You can always type your answers instead of talking.</Text>
    </ScrollView>
  );
}

function SettingRow({ title, description, value, onToggle, disabled, note }) {
  return (
    <View style={[styles.row, disabled && styles.disabled]}>
      <View style={styles.flex}>
        <View style={styles.titleRow}>
          <Text style={styles.rowTitle}>{title}</Text>
          {note ? <Text style={styles.badge}>{note}</Text> : null}
        </View>
        <Text style={styles.rowDescription}>{description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onToggle}
        disabled={disabled}
        trackColor={{ false: colors.border, true: colors.primary }}
        thumbColor="#fff"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.5 },
  content: { padding: 20, paddingBottom: 32 },

  label: { fontSize: 11, fontWeight: '700', letterSpacing: 1, color: colors.primary, marginTop: 8 },
  heading: { fontFamily: serif, fontSize: 26, color: colors.text, marginTop: 6, marginBottom: 16 },
  section: { fontSize: 13, fontWeight: '700', color: colors.muted, marginBottom: 8, marginTop: 4 },

  card: {
    backgroundColor: colors.card,
    borderRadius: 18,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  rowDescription: { fontSize: 13, color: colors.muted, marginTop: 4, lineHeight: 18 },
  badge: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.primary,
    backgroundColor: colors.primarySoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    overflow: 'hidden',
  },

  profileRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  initials: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initialsText: { fontSize: 15, fontWeight: '700', color: colors.primary },
  logoutButton: {
    marginTop: 14,
    alignSelf: 'flex-start',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  logoutText: { color: colors.error, fontWeight: '600', fontSize: 14 },

  testButton: {
    marginTop: 14,
    alignSelf: 'flex-start',
    backgroundColor: colors.bg,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  testText: { color: colors.primary, fontWeight: '600', fontSize: 14 },

  footnote: { fontSize: 12, color: colors.muted, textAlign: 'center', marginTop: 4 },
});
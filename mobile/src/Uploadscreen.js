// Upload a medical report: Ana reads it, the patient checks each item, only kept items are saved.
// Used after registration and from Settings.
import * as DocumentPicker from 'expo-document-picker';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { confirmReport, uploadReport } from './api';
import { colors, serif } from './theme';

const SECTIONS = [
  { key: 'diagnoses', title: 'Conditions', line: (d) => [d.name, d.date].filter(Boolean).join(' · ') },
  { key: 'medications', title: 'Medications', line: (m) => [m.name, m.dosage, m.frequency].filter(Boolean).join(' · ') },
  { key: 'allergies', title: 'Allergies', line: (a) => a },
  { key: 'care_contacts', title: 'Care contacts', line: (c) => [c.role, c.name].filter(Boolean).join(': ') },
];

export default function UploadScreen({ patientId, onDone, doneLabel = 'Done', skipLabel }) {
  const [step, setStep] = useState('pick'); // pick | reading | review | saving | saved
  const [found, setFound] = useState(null);
  const [keep, setKeep] = useState({}); // "medications-0": true
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState('');

  async function pickFile() {
    setError('');
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'],
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets?.length) return;

    setStep('reading');
    try {
      const data = await uploadReport(patientId, result.assets[0]);
      const allOn = {};
      SECTIONS.forEach(({ key }) => (data[key] || []).forEach((_, i) => (allOn[`${key}-${i}`] = true)));
      setFound(data);
      setKeep(allOn);
      setStep('review');
    } catch (e) {
      setError(e.message);
      setStep('pick');
    }
  }

  async function save() {
    setStep('saving');
    const records = {};
    SECTIONS.forEach(({ key }) => {
      records[key] = (found[key] || []).filter((_, i) => keep[`${key}-${i}`]);
    });
    try {
      setSaved(await confirmReport(patientId, records));
      setStep('saved');
    } catch (e) {
      setError(e.message);
      setStep('review');
    }
  }

  const total = found ? SECTIONS.reduce((n, { key }) => n + (found[key] || []).length, 0) : 0;
  const kept = Object.values(keep).filter(Boolean).length;

  if (step === 'reading' || step === 'saving') {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
        <Text style={styles.waitText}>
          {step === 'reading' ? 'Ana is reading your report…' : 'Saving to your record…'}
        </Text>
        {step === 'reading' ? <Text style={styles.small}>This can take up to a minute.</Text> : null}
      </View>
    );
  }

  if (step === 'saved') {
    const added = Object.values(saved || {}).reduce((a, b) => a + b, 0);
    return (
      <View style={styles.center}>
        <Text style={styles.heading}>Saved ✓</Text>
        <Text style={styles.body}>
          {added
            ? `Ana added ${added} new item${added === 1 ? '' : 's'} to your record. She'll use this in your check-ins.`
            : 'Everything was already in your record.'}
        </Text>
        <Pressable style={styles.button} onPress={() => onDone?.(true)}>
          <Text style={styles.buttonText}>{doneLabel}</Text>
        </Pressable>
      </View>
    );
  }

  if (step === 'review') {
    return (
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.heading}>Please check what Ana found</Text>
        <Text style={styles.body}>
          Switch off anything that is wrong. Only what you keep is saved. Your file itself is not stored.
        </Text>

        {found.unclear?.length ? (
          <View style={styles.warning}>
            <Text style={styles.warningTitle}>Ana wasn't sure about:</Text>
            {found.unclear.map((u, i) => (
              <Text key={i} style={styles.warningText}>• {u}</Text>
            ))}
          </View>
        ) : null}

        {total === 0 ? (
          <Text style={styles.body}>Ana didn't find any conditions, medications, allergies or contacts.</Text>
        ) : (
          SECTIONS.map(({ key, title, line }) =>
            found[key]?.length ? (
              <View key={key} style={styles.card}>
                <Text style={styles.section}>{title}</Text>
                {found[key].map((item, i) => (
                  <View key={i} style={styles.row}>
                    <Text style={[styles.item, !keep[`${key}-${i}`] && styles.off]}>{line(item)}</Text>
                    <Switch
                      value={!!keep[`${key}-${i}`]}
                      onValueChange={(v) => setKeep({ ...keep, [`${key}-${i}`]: v })}
                      trackColor={{ false: colors.border, true: colors.primary }}
                      thumbColor="#fff"
                    />
                  </View>
                ))}
              </View>
            ) : null
          )
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={[styles.button, !kept && styles.disabled]}
          onPress={save}
          disabled={!kept}
        >
          <Text style={styles.buttonText}>Save to my record ({kept})</Text>
        </Pressable>
        <Pressable style={styles.linkButton} onPress={() => { setFound(null); setStep('pick'); }}>
          <Text style={styles.linkText}>Cancel</Text>
        </Pressable>
      </ScrollView>
    );
  }

  // step === 'pick'
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Add your medical report</Text>
      <Text style={styles.body}>
        Choose a PDF or a photo of a letter from your doctor or hospital, or your medication list.
        Ana will read it and show you what she found. You check it before anything is saved.
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable style={styles.button} onPress={pickFile}>
        <Text style={styles.buttonText}>Choose a file</Text>
      </Pressable>
      {skipLabel ? (
        <Pressable style={styles.linkButton} onPress={() => onDone?.(false)}>
          <Text style={styles.linkText}>{skipLabel}</Text>
        </Pressable>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 24, paddingTop: 32 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, minHeight: 320 },
  heading: { fontFamily: serif, fontSize: 24, color: colors.text, marginBottom: 10, textAlign: 'center' },
  body: { fontSize: 14, color: colors.muted, lineHeight: 20, marginBottom: 18, textAlign: 'center' },
  small: { fontSize: 12, color: colors.muted, marginTop: 6 },
  waitText: { fontSize: 16, color: colors.text, marginTop: 16 },
  card: { backgroundColor: colors.card, borderRadius: 18, padding: 16, marginBottom: 14 },
  section: { fontSize: 13, fontWeight: '700', color: colors.muted, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 6 },
  item: { flex: 1, fontSize: 15, color: colors.text },
  off: { color: colors.muted, textDecorationLine: 'line-through' },
  warning: { backgroundColor: '#FFF4E5', borderRadius: 14, padding: 14, marginBottom: 14 },
  warningTitle: { fontWeight: '700', color: '#8A5300', marginBottom: 4 },
  warningText: { color: '#8A5300', fontSize: 13, lineHeight: 18 },
  error: { color: colors.error, fontSize: 13, textAlign: 'center', marginBottom: 12 },
  button: {
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: 'center',
    alignSelf: 'stretch',
    marginTop: 4,
  },
  disabled: { opacity: 0.5 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  linkButton: { alignItems: 'center', paddingVertical: 14 },
  linkText: { color: colors.primary, fontSize: 14, fontWeight: '600' },
});
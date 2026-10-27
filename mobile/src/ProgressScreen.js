import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { getProgress } from './api';
import { colors, serif } from './theme';

const DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

function headline(streak) {
  if (streak >= 3) return "You're finding your rhythm.";
  if (streak >= 1) return "A good start. Keep it going.";
  return 'Every check-in counts.';
}

function streakText(streak) {
  if (streak >= 3) return "You've kept up with your routine. That's something to feel good about.";
  if (streak >= 1) return 'Small steps, one day at a time.';
  return 'Check in today to start a new streak.';
}

function shortDate(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

export default function ProgressScreen({ patientId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  // Reads check-in dates from the database. Costs no Gemini requests.
  async function load() {
    setError('');
    try {
      setData(await getProgress(patientId));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [patientId]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
        <Pressable style={styles.retryButton} onPress={load}>
          <Text style={styles.retryText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  const { streak_days: streak, week, checkins_this_week: weekCount, medications } = data;

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.label}>YOUR PROGRESS</Text>
      <Text style={styles.heading}>{headline(streak)}</Text>

      {/* Streak */}
      <View style={styles.streakCard}>
        <View style={styles.streakNumber}>
          <Text style={styles.streakNumberText}>{streak}</Text>
        </View>
        <View style={styles.flex}>
          <Text style={styles.streakTitle}>{streak === 1 ? 'day' : 'days'} in a row</Text>
          <Text style={styles.streakSub}>{streakText(streak)}</Text>
        </View>
      </View>

      {/* This week */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>This week</Text>
          <Text style={styles.cardMeta}>
            {shortDate(week[0].date)} – {shortDate(week[6].date)}
          </Text>
        </View>
        <View style={styles.weekRow}>
          {week.map((day, i) => (
            <View key={day.date} style={styles.dayColumn}>
              <Text style={styles.dayLetter}>{DAY_LETTERS[i]}</Text>
              <View
                style={[
                  styles.dayCircle,
                  day.checked_in && styles.dayChecked,
                  day.is_future && styles.dayFuture,
                ]}
              >
                <Text style={[styles.dayText, day.checked_in && styles.dayTextChecked]}>
                  {day.checked_in ? '✓' : Number(day.date.slice(8))}
                </Text>
              </View>
              <View style={[styles.todayDot, !day.is_today && styles.invisible]} />
            </View>
          ))}
        </View>
        <View style={styles.weekNote}>
          <Text style={styles.weekNoteText}>
            ✓  {weekCount} gentle check-in{weekCount === 1 ? '' : 's'} completed this week
          </Text>
        </View>
      </View>

      {/* Medications */}
      <View style={styles.card}>
        <Text style={[styles.cardTitle, styles.medTitle]}>Your medications</Text>
        {medications.map((med, i) => (
          <View key={i} style={[styles.medRow, i > 0 && styles.medDivider]}>
            <View style={styles.medDot} />
            <View style={styles.flex}>
              <Text style={styles.medName}>{med.MedicationName}</Text>
              <Text style={styles.medDetail}>
                {med.Dosage} · {med.Frequency}
              </Text>
            </View>
          </View>
        ))}
        <Text style={styles.footnote}>Always follow the instructions from your care team.</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  invisible: { opacity: 0 },
  content: { padding: 20, paddingBottom: 32 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  error: { color: colors.error, textAlign: 'center', marginBottom: 12 },
  retryButton: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 18 },
  retryText: { color: '#fff', fontWeight: '600' },

  label: { fontSize: 11, fontWeight: '700', letterSpacing: 1, color: colors.primary, marginTop: 8 },
  heading: { fontFamily: serif, fontSize: 28, color: colors.text, marginTop: 6, marginBottom: 20 },

  streakCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: colors.primarySoft,
    borderRadius: 18,
    padding: 16,
    marginBottom: 16,
  },
  streakNumber: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  streakNumberText: { fontFamily: serif, fontSize: 24, color: colors.text },
  streakTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
  streakSub: { fontSize: 13, color: colors.muted, marginTop: 2, lineHeight: 18 },

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
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  cardTitle: { fontFamily: serif, fontSize: 18, color: colors.text },
  cardMeta: { fontSize: 12, color: colors.muted },

  weekRow: { flexDirection: 'row', justifyContent: 'space-between' },
  dayColumn: { alignItems: 'center', gap: 6 },
  dayLetter: { fontSize: 11, color: colors.muted },
  dayCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayChecked: { backgroundColor: colors.primary },
  dayFuture: { opacity: 0.5 },
  dayText: { fontSize: 12, color: colors.muted },
  dayTextChecked: { color: '#fff', fontWeight: '700' },
  todayDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.primary },

  weekNote: { marginTop: 14, backgroundColor: colors.bg, borderRadius: 12, padding: 10 },
  weekNoteText: { fontSize: 13, color: colors.primary, fontWeight: '500' },

  medTitle: { marginBottom: 6 },
  medRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 },
  medDivider: { borderTopWidth: 1, borderTopColor: colors.border },
  medDot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.avatar },
  medName: { fontSize: 15, fontWeight: '600', color: colors.text },
  medDetail: { fontSize: 12, color: colors.muted, marginTop: 2 },
  footnote: { fontSize: 11, color: colors.muted, marginTop: 10 },
});
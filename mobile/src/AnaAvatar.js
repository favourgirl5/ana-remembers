import { StyleSheet, View } from 'react-native';
import { colors } from './theme';

// Ana's little smiling face from the design, drawn with plain shapes.
export default function AnaAvatar({ size = 32 }) {
  const eye = Math.max(3, size * 0.1);
  const smile = size * 0.36;
  return (
    <View
      style={[
        styles.circle,
        { width: size, height: size, borderRadius: size / 2 },
      ]}
    >
      <View style={[styles.eyes, { gap: size * 0.2, marginTop: size * 0.08 }]}>
        <View style={[styles.eye, { width: eye, height: eye, borderRadius: eye / 2 }]} />
        <View style={[styles.eye, { width: eye, height: eye, borderRadius: eye / 2 }]} />
      </View>
      <View
        style={[
          styles.smile,
          {
            width: smile,
            height: smile / 2,
            borderBottomLeftRadius: smile / 2,
            borderBottomRightRadius: smile / 2,
            borderWidth: Math.max(1.5, size * 0.05),
            marginTop: size * 0.06,
          },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  circle: {
    backgroundColor: colors.avatar,
    alignItems: 'center',
    justifyContent: 'center',
  },
  eyes: { flexDirection: 'row' },
  eye: { backgroundColor: colors.primary },
  smile: { borderColor: colors.primary, borderTopWidth: 0 },
});
/**
 * Home.
 *
 * One thing to do, and a wall of examples showing what happens when you do
 * it. The examples are the argument: the promise is "a photo becomes a set
 * you can build", and a photo beside its brick model makes that case faster
 * than any copy would.
 */

import React, { useEffect, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button, Card } from '@/components/ui';
import { colors, radius, shadow, space, type } from '@/theme';
import { getConfig, type Config } from '@/api/client';

const EXAMPLES = [
  { title: 'Golden Retriever', pieces: 423, hue: '#D9A24A' },
  { title: 'Corner Bakery', pieces: 812, hue: '#C4553F' },
  { title: 'Red Hatchback', pieces: 356, hue: '#C0392B' },
  { title: 'Desk Plant', pieces: 148, hue: '#3A9E4A' },
];

export default function Home() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    // The disclaimer and the presets come from the server, so a change to
    // either reaches every install without a release.
    getConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  return (
    <ScrollView
      style={s.screen}
      contentContainerStyle={[s.content, { paddingTop: insets.top + space(4) }]}
      showsVerticalScrollIndicator={false}
    >
      <Text style={s.kicker}>BRICKSNAP</Text>
      <Text style={s.hero}>Turn any picture into a set you can actually build.</Text>
      <Text style={s.sub}>
        Photograph something. Get back a real brick model, an exact parts list
        and instructions that follow it step by step.
      </Text>

      <View style={s.gallery}>
        {EXAMPLES.map((e) => (
          <View key={e.title} style={s.example}>
            <View style={[s.exampleArt, { backgroundColor: e.hue }]}>
              <View style={s.studRow}>
                {[0, 1, 2].map((i) => <View key={i} style={s.stud} />)}
              </View>
            </View>
            <Text style={s.exampleTitle} numberOfLines={1}>{e.title}</Text>
            <Text style={s.examplePieces}>{e.pieces} pieces</Text>
          </View>
        ))}
      </View>

      <Button label="Create Your Set" onPress={() => router.push('/upload')} />

      <View style={s.secondary}>
        <SecondaryAction label="My Sets" onPress={() => router.push('/sets')} />
        <SecondaryAction label="Browse Sets" onPress={() => router.push('/sets')} />
        <SecondaryAction label="How It Works" onPress={() => router.push('/how')} />
      </View>

      {config ? (
        <Text style={s.legal}>{config.branding.disclaimer}</Text>
      ) : null}
    </ScrollView>
  );
}

function SecondaryAction({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [s.secondaryBtn, pressed && { opacity: 0.85 }]}
    >
      <Text style={s.secondaryLabel}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), paddingBottom: space(14), gap: space(4) },

  kicker: { ...type.caps, color: colors.inkFaint },
  hero: { ...type.display, color: colors.ink, lineHeight: 38 },
  sub: { ...type.body, color: colors.inkSoft, lineHeight: 22, marginBottom: space(2) },

  gallery: { flexDirection: 'row', flexWrap: 'wrap', gap: space(3) },
  example: {
    width: '47.5%', backgroundColor: colors.surface, borderRadius: radius.lg,
    padding: space(3), ...shadow.card,
  },
  exampleArt: {
    height: 104, borderRadius: radius.md, marginBottom: space(3),
    justifyContent: 'flex-start', padding: space(3),
  },
  studRow: { flexDirection: 'row', gap: 6 },
  stud: {
    width: 14, height: 14, borderRadius: 7,
    backgroundColor: 'rgba(255,255,255,0.45)',
  },
  exampleTitle: { ...type.bodyStrong, color: colors.ink },
  examplePieces: { ...type.small, color: colors.inkFaint, marginTop: 1 },

  secondary: { flexDirection: 'row', gap: space(2) },
  secondaryBtn: {
    flex: 1, paddingVertical: space(3), borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt, alignItems: 'center',
  },
  secondaryLabel: { ...type.small, fontWeight: '600', color: colors.ink },

  legal: {
    ...type.small, color: colors.inkFaint, lineHeight: 17,
    marginTop: space(3),
  },
});

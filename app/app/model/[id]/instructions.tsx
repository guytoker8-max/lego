/**
 * The booklet.
 *
 * Visual first, as the brief asks: the model rebuilds itself as you step
 * through, with everything placed so far dimmed and this step's pieces at
 * full colour. Swipe or tap to move. The written list under it is the
 * caption, not the instruction.
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';

import BrickViewer, { type ViewAngle } from '@/components/BrickViewer';
import { Button, Card, ErrorState, Loading, Swatch } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import {
  ApiError, getGeometry, getSteps, type Geometry, type Step,
} from '@/api/client';

export default function Instructions() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { width } = useWindowDimensions();

  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [index, setIndex] = useState(0);
  const [angle, setAngle] = useState<ViewAngle>('free');
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    Promise.all([getGeometry(id), getSteps(id)])
      .then(([g, s2]) => {
        // If these two ever disagree the booklet would be describing a
        // different model from the one on screen, so check rather than trust.
        if (g.fingerprint !== s2.fingerprint) {
          setError('This set changed while it was open. Reopen it to see the current version.');
          return;
        }
        setGeometry(g);
        setSteps(s2.steps);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : 'Could not load the instructions.'),
      );
  };

  useEffect(load, [id]);

  const step = steps?.[index];
  const { shown, from } = useMemo(() => {
    if (!steps || !step) return { shown: 0, from: 0 };
    const before = steps.slice(0, index).reduce((n, s2) => n + s2.piece_count, 0);
    return { shown: before + step.piece_count, from: before };
  }, [steps, step, index]);

  if (error) return <View style={s.pad}><ErrorState message={error} onRetry={load} /></View>;
  if (!geometry || !steps || !step) return <Loading label="Opening the booklet" />;

  const last = index >= steps.length - 1;

  return (
    <View style={s.screen}>
      <BrickViewer
        geometry={geometry}
        visibleCount={shown}
        highlightFrom={from}
        angle={angle}
        style={[s.viewer, { height: Math.min(360, width * 0.9) }]}
      />

      <View style={s.viewerTools}>
        <SmallButton label="Rotate" onPress={() => setAngle('free')} on={angle === 'free'} />
        <SmallButton label="Front" onPress={() => setAngle('front')} on={angle === 'front'} />
        <SmallButton label="Top" onPress={() => setAngle('top')} on={angle === 'top'} />
        <SmallButton label="Side" onPress={() => setAngle('side')} on={angle === 'side'} />
      </View>

      <ScrollView style={s.sheet} contentContainerStyle={s.sheetContent}>
        <View style={s.stepHead}>
          <Text style={s.stepNo}>STEP {step.index} OF {steps.length}</Text>
          <Text style={s.stepCount}>{step.piece_count} pieces</Text>
        </View>
        <Text style={s.stepTitle}>{step.title}</Text>

        <Card style={{ gap: space(3) }}>
          <Text style={s.addLabel}>Add</Text>
          {step.add.map((a, i) => (
            <View key={i} style={s.addRow}>
              <Swatch hex={a.color_hex} size={22} />
              <Text style={s.addQty}>{a.quantity} ×</Text>
              <Text style={s.addName} numberOfLines={1}>
                {a.color_name} {a.part_name}
              </Text>
            </View>
          ))}
          <Text style={s.placedNote}>
            {step.cumulative} of {geometry.bricks.length} pieces placed
          </Text>
        </Card>

        <View style={s.nav}>
          <Button label="Previous" tone="secondary" style={{ flex: 1 }}
                  disabled={index === 0} onPress={() => setIndex((i) => i - 1)} />
          <Button label={last ? 'Finished' : 'Next'} style={{ flex: 1 }}
                  disabled={last} onPress={() => setIndex((i) => i + 1)} />
        </View>
      </ScrollView>

      <View style={s.track}>
        <View style={[s.fill, { width: `${((index + 1) / steps.length) * 100}%` }]} />
      </View>
    </View>
  );
}

function SmallButton({ label, onPress, on }: any) {
  return (
    <Pressable onPress={onPress}
               style={({ pressed }) => [s.small, on && s.smallOn, pressed && { opacity: 0.8 }]}>
      <Text style={[s.smallLabel, on && s.smallLabelOn]}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: space(5) },
  viewer: { marginHorizontal: space(4), marginTop: space(2), borderRadius: radius.xl },
  viewerTools: {
    flexDirection: 'row', gap: space(2), paddingHorizontal: space(4),
    marginTop: space(2),
  },
  small: {
    paddingVertical: space(2), paddingHorizontal: space(3),
    borderRadius: radius.pill, backgroundColor: colors.surfaceAlt,
  },
  smallOn: { backgroundColor: colors.ink },
  smallLabel: { ...type.small, fontWeight: '600', color: colors.ink },
  smallLabelOn: { color: colors.surface },

  sheet: { flex: 1, marginTop: space(3) },
  sheetContent: { padding: space(5), paddingTop: 0, gap: space(3) },
  stepHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  stepNo: { ...type.caps, color: colors.inkFaint },
  stepCount: { ...type.small, color: colors.inkFaint },
  stepTitle: { ...type.title, color: colors.ink },

  addLabel: { ...type.caps, color: colors.inkFaint },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: space(3) },
  addQty: { ...type.bodyStrong, color: colors.ink, minWidth: 34 },
  addName: { ...type.body, color: colors.ink, flex: 1 },
  placedNote: { ...type.small, color: colors.inkFaint, marginTop: space(1) },

  nav: { flexDirection: 'row', gap: space(3), marginTop: space(2) },
  track: { height: 4, backgroundColor: colors.surfaceAlt },
  fill: { height: '100%', backgroundColor: colors.brand },
});

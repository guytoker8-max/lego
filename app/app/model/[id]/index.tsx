/**
 * The set.
 *
 * The model is the screen: it gets the top two-thirds and it is the thing
 * you touch. Everything else -- the count, the size, the price -- sits under
 * it as facts about the object you are already looking at.
 */

import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import BrickViewer, { type ViewAngle } from '@/components/BrickViewer';
import {
  Button, Card, Chip, ErrorState, Loading, Notice, Stat, Swatch,
} from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import { money } from '@/format';
import {
  ApiError, getConfig, getGeometry, getModel, type Config, type Geometry,
  type Parts, type Price, type Summary,
} from '@/api/client';

const ANGLES: { key: ViewAngle; label: string }[] = [
  { key: 'free', label: 'Free' },
  { key: 'front', label: 'Front' },
  { key: 'side', label: 'Side' },
  { key: 'back', label: 'Back' },
  { key: 'top', label: 'Top' },
];

export default function ModelScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [parts, setParts] = useState<Parts | null>(null);
  const [price, setPrice] = useState<Price | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [angle, setAngle] = useState<ViewAngle>('free');
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    Promise.all([getGeometry(id), getModel(id), getConfig()])
      .then(([g, m, c]) => {
        setGeometry(g);
        setSummary(m.summary);
        setParts(m.parts);
        setPrice(m.price);
        setWarnings(m.warnings ?? []);
        setConfig(c);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : 'Could not load this set.'),
      );
  };

  useEffect(load, [id]);

  if (error) return <View style={s.pad}><ErrorState message={error} onRetry={load} /></View>;
  if (!geometry || !summary || !price || !parts) return <Loading label="Opening your set" />;

  const [w, h, d] = summary.dimensions_cm;
  // One swatch per colour, most-used first. The parts list has a line per
  // part *and* colour, so taking its first lines showed Blue three times.
  const byColor = new Map<number, { color_id: number; color_name: string; color_hex: string; quantity: number }>();
  for (const l of parts.lines) {
    const c = byColor.get(l.color_id);
    if (c) c.quantity += l.quantity;
    else byColor.set(l.color_id, { color_id: l.color_id, color_name: l.color_name, color_hex: l.color_hex, quantity: l.quantity });
  }
  const topColors = [...byColor.values()].sort((a, b) => b.quantity - a.quantity).slice(0, 12);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}
                showsVerticalScrollIndicator={false}>
      <BrickViewer geometry={geometry} angle={angle} style={s.viewer} />

      <View style={s.angleRow}>
        {ANGLES.map((a) => (
          <Chip key={a.key} label={a.label} selected={angle === a.key}
                onPress={() => setAngle(a.key)} />
        ))}
      </View>
      <Text style={s.viewerHint}>Drag to rotate · pinch to zoom · two fingers to pan</Text>

      <View style={s.body}>
        <Text style={s.name}>{summary.name}</Text>
        <Text style={s.subject}>
          {summary.difficulty} · {summary.step_count} steps
        </Text>

        <Card style={{ gap: space(4) }}>
          <View style={s.statRow}>
            <Stat label="Pieces" value={summary.piece_count.toLocaleString()} />
            <Stat label="Colours" value={String(summary.color_count)} />
            <Stat label="Build time" value={summary.build_time.label} />
          </View>
          <View style={s.statRow}>
            <Stat wide label="Size (cm)" value={`${w} × ${h} × ${d}`} />
            <Stat label="Weight" value={`${Math.round(summary.weight_g)} g`} />
            <Stat label="Est. price" value={money(price.symbol, price.set_price)} />
          </View>
        </Card>

        <Card style={{ gap: space(3) }}>
          <Text style={s.cardTitle}>Colours in this set</Text>
          <View style={s.swatches}>
            {topColors.map((l) => (
              <View key={l.color_id} style={s.swatchItem}>
                <Swatch hex={l.color_hex} size={26} />
                <Text style={s.swatchName} numberOfLines={1}>{l.color_name}</Text>
              </View>
            ))}
          </View>
        </Card>

        {warnings.length ? (
          <Card style={{ gap: space(2) }}>
            <Text style={s.cardTitle}>Worth knowing</Text>
            {warnings.slice(0, 3).map((w2, i) => (
              <Notice key={i} kind="warning">{w2}</Notice>
            ))}
          </Card>
        ) : null}

        <Button label="Open instructions"
                onPress={() => router.push({ pathname: '/model/[id]/instructions', params: { id } })} />
        <Button label="Parts list" tone="secondary"
                onPress={() => router.push({ pathname: '/model/[id]/parts', params: { id } })} />
        <Button label="Change this set" tone="secondary"
                onPress={() => router.push({ pathname: '/model/[id]/edit', params: { id } })} />
        <Button label="Make My Set" tone="secondary"
                onPress={() => router.push({ pathname: '/model/[id]/order', params: { id } })} />

        {config ? <Text style={s.legal}>{config.branding.short_disclaimer}</Text> : null}
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { paddingBottom: space(14) },
  pad: { padding: space(5) },

  viewer: { height: 380, marginHorizontal: space(4), borderRadius: radius.xl },
  angleRow: {
    flexDirection: 'row', gap: space(2), paddingHorizontal: space(4),
    marginTop: space(3), flexWrap: 'wrap',
  },
  viewerHint: {
    ...type.small, color: colors.inkFaint, paddingHorizontal: space(5),
    marginTop: space(2),
  },

  body: { padding: space(5), gap: space(4) },
  name: { ...type.display, color: colors.ink },
  subject: { ...type.body, color: colors.inkSoft, marginTop: -space(2) },
  cardTitle: { ...type.heading, color: colors.ink },
  statRow: { flexDirection: 'row', gap: space(3) },

  swatches: { flexDirection: 'row', flexWrap: 'wrap', gap: space(3) },
  swatchItem: { alignItems: 'center', width: 70, gap: space(1) },
  swatchName: { ...type.small, color: colors.inkSoft, fontSize: 11, textAlign: 'center' },

  legal: { ...type.small, color: colors.inkFaint, marginTop: space(2) },
});

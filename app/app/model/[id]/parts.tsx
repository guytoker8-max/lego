/**
 * The parts list.
 *
 * Counted from the model, so it is the model. The mismatch check at the top
 * is not decoration: if the list and the model ever disagreed, this is where
 * a person would find out, and the order route refuses the same case.
 */

import React, { useEffect, useState } from 'react';
import { SectionList, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

import { Card, ErrorState, Loading, Notice, Swatch } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import { ApiError, getParts, type Parts, type PartLine } from '@/api/client';

export default function PartsList() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [parts, setParts] = useState<Parts | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    getParts(id).then(setParts).catch((e) =>
      setError(e instanceof ApiError ? e.message : 'Could not load the parts list.'));
  };
  useEffect(load, [id]);

  if (error) return <View style={s.pad}><ErrorState message={error} onRetry={load} /></View>;
  if (!parts) return <Loading label="Counting pieces" />;

  // Grouped by colour: that is how you actually sort a pile of bricks.
  const byColor = new Map<string, PartLine[]>();
  parts.lines.forEach((l) => {
    const key = l.color_name;
    if (!byColor.has(key)) byColor.set(key, []);
    byColor.get(key)!.push(l);
  });
  const sections = [...byColor.entries()]
    .map(([title, data]) => ({
      title,
      hex: data[0].color_hex,
      total: data.reduce((n, l) => n + l.quantity, 0),
      data: data.sort((a, b) => b.quantity - a.quantity),
    }))
    .sort((a, b) => b.total - a.total);

  return (
    <SectionList
      style={s.screen}
      contentContainerStyle={s.content}
      sections={sections}
      keyExtractor={(l) => `${l.part_id}-${l.color_id}`}
      ListHeaderComponent={
        <View style={{ gap: space(3) }}>
          <Card style={{ gap: space(2) }}>
            <View style={s.headRow}>
              <Text style={s.headBig}>{parts.total_pieces.toLocaleString()}</Text>
              <Text style={s.headLabel}>pieces in total</Text>
            </View>
            <Text style={s.headSub}>
              {parts.distinct_parts} part types · {parts.distinct_colors} colours ·{' '}
              {Math.round(parts.total_weight_g)} g
            </Text>
          </Card>
          {parts.mismatches.length ? (
            <Notice kind="error">
              This list does not match the model. It cannot be ordered until
              the set is rebuilt.
            </Notice>
          ) : null}
          {parts.unavailable.length ? (
            <Notice kind="warning">
              Out of stock: {parts.unavailable.map((u) => `${u.color_name} ${u.part_name}`).join(', ')}
            </Notice>
          ) : null}
        </View>
      }
      renderSectionHeader={({ section }) => (
        <View style={s.sectionHead}>
          <Swatch hex={(section as any).hex} size={20} />
          <Text style={s.sectionTitle}>{section.title}</Text>
          <Text style={s.sectionCount}>{(section as any).total}</Text>
        </View>
      )}
      renderItem={({ item }) => (
        <View style={s.row}>
          <Text style={s.qty}>{item.quantity} ×</Text>
          <Text style={s.partName}>{item.part_name}</Text>
          <Text style={s.partId}>{item.part_id}</Text>
        </View>
      )}
      stickySectionHeadersEnabled={false}
    />
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), paddingBottom: space(14), gap: space(1) },
  pad: { padding: space(5) },

  headRow: { flexDirection: 'row', alignItems: 'baseline', gap: space(2) },
  headBig: { ...type.display, color: colors.ink },
  headLabel: { ...type.body, color: colors.inkSoft },
  headSub: { ...type.small, color: colors.inkFaint },

  sectionHead: {
    flexDirection: 'row', alignItems: 'center', gap: space(2),
    marginTop: space(5), marginBottom: space(2),
  },
  sectionTitle: { ...type.heading, color: colors.ink, flex: 1 },
  sectionCount: { ...type.bodyStrong, color: colors.inkFaint },

  row: {
    flexDirection: 'row', alignItems: 'center', gap: space(3),
    paddingVertical: space(2), paddingHorizontal: space(3),
    backgroundColor: colors.surface, borderRadius: radius.sm,
    marginBottom: space(1),
  },
  qty: { ...type.bodyStrong, color: colors.ink, minWidth: 42 },
  partName: { ...type.body, color: colors.ink, flex: 1 },
  partId: { ...type.small, color: colors.inkFaint },
});

/** My sets: drafts, finished models and anything ordered. */

import React, { useCallback, useState } from 'react';
import { FlatList, Image, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';

import { Button, Card, ErrorState, Loading } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import { ApiError, listModels, previewUrl } from '@/api/client';

type Row = {
  id: string; name: string; piece_count: number;
  dimensions_cm: number[] | null; status: string; updated_at: number;
  thumbnail: string | null;
};

export default function MySets() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    listModels()
      .then((r) => setRows(r.models as Row[]))
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : 'Could not load your sets.'));
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (error) return <View style={s.pad}><ErrorState message={error} onRetry={load} /></View>;
  if (!rows) return <Loading label="Finding your sets" />;

  if (!rows.length) {
    return (
      <View style={s.pad}>
        <Card style={{ gap: space(3) }}>
          <Text style={s.emptyTitle}>Nothing here yet</Text>
          <Text style={s.emptyBody}>
            Sets you create are kept here with their photos, instructions and
            parts lists.
          </Text>
          <Button label="Create your first set" onPress={() => router.push('/upload')} />
        </Card>
      </View>
    );
  }

  return (
    <FlatList
      style={s.screen}
      contentContainerStyle={s.content}
      data={rows}
      keyExtractor={(r) => r.id}
      renderItem={({ item }) => (
        <Card
          style={s.row}
          onPress={() => router.push({ pathname: '/model/[id]', params: { id: item.id } })}
        >
          <Image
            source={{ uri: previewUrl(item.id) }}
            style={s.thumb}
            resizeMode="cover"
          />
          <View style={{ flex: 1 }}>
            <Text style={s.rowName} numberOfLines={1}>{item.name}</Text>
            <Text style={s.rowMeta}>
              {item.piece_count.toLocaleString()} pieces
              {item.dimensions_cm ? ` · ${item.dimensions_cm.join(' × ')} cm` : ''}
            </Text>
          </View>
          <Text style={s.rowStatus}>{item.status}</Text>
        </Card>
      )}
    />
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), gap: space(3), paddingBottom: space(14) },
  pad: { padding: space(5), flex: 1, backgroundColor: colors.bg },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(4), padding: space(4) },
  thumb: {
    width: 56, height: 56, borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt,
  },
  rowName: { ...type.bodyStrong, color: colors.ink },
  rowMeta: { ...type.small, color: colors.inkFaint, marginTop: 2 },
  rowStatus: { ...type.caps, color: colors.inkFaint },
  emptyTitle: { ...type.heading, color: colors.ink },
  emptyBody: { ...type.body, color: colors.inkSoft, lineHeight: 21 },
});

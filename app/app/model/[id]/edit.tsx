/**
 * Change a set you already have.
 *
 * Plain language in, a structured change out. The screen shows what it
 * understood *before* anything happens, because "make it bigger" is cheap to
 * misread and expensive to sit through: a rebuild takes real seconds and the
 * old model is replaced when it lands.
 *
 * Nothing here generates a fresh model. A colour change edits the structure
 * in place; a size or detail change rebuilds from the same photos. Either
 * way the set keeps its identity and gains a version.
 */

import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Button, Card, Chip, Loading, Notice, Screen } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import {
  ApiError, editModel, getJob, getVersions, type EditPlan,
} from '@/api/client';

const SUGGESTIONS = [
  'Make it bigger',
  'Use fewer pieces',
  'Make it stronger',
  'Make the roof red',
  'Make it easier to build',
];

export default function EditModel() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [plan, setPlan] = useState<EditPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [versions, setVersions] = useState<{ change: string; piece_count: number }[]>([]);

  useEffect(() => {
    getVersions(id).then((v) => setVersions(v.versions)).catch(() => {});
  }, [id]);

  const apply = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setPlan(null);
    setStatus('Working out what to change...');
    try {
      const started = await editModel(id, text.trim());
      setPlan(started.plan);
      // Poll the same job endpoint the first build uses.
      for (let i = 0; i < 400; i += 1) {
        const job = await getJob(started.job_id);
        setStatus(job.message ?? null);
        if (job.status === 'done') {
          router.replace({ pathname: '/model/[id]', params: { id } });
          return;
        }
        if (job.status === 'failed') {
          setError(job.error ?? 'The change could not be applied.');
          setBusy(false);
          return;
        }
        await new Promise((r) => setTimeout(r, 400));
      }
      setError('That is taking longer than expected. Your set is unchanged.');
      setBusy(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The change could not be applied.');
      setBusy(false);
    }
  };

  if (busy) {
    return (
      <Screen>
        <Loading label={status ?? 'Applying your changes'} />
        {plan?.understood?.length ? (
          <Card style={{ gap: space(2) }}>
            <Text style={s.cardTitle}>Changing</Text>
            {plan.understood.map((u, i) => (
              <Text key={i} style={s.understood}>· {u}</Text>
            ))}
          </Card>
        ) : null}
      </Screen>
    );
  }

  return (
    <Screen>
      <Text style={s.title}>What would you like changed?</Text>
      <Text style={s.sub}>
        Ask in your own words. Size and detail changes rebuild the model from
        your original photos; colour changes are applied straight away.
      </Text>

      <TextInput
        style={s.input}
        value={text}
        onChangeText={setText}
        placeholder="Make it bigger"
        placeholderTextColor={colors.inkFaint}
        multiline
        accessibilityLabel="Describe the change you want"
      />

      <View style={s.chips}>
        {SUGGESTIONS.map((sug) => (
          <Chip key={sug} label={sug} selected={text === sug}
                onPress={() => setText(sug)} />
        ))}
      </View>

      {error ? <Notice kind="error">{error}</Notice> : null}

      <Button label="Apply the change" onPress={apply} disabled={!text.trim()} />

      {versions.length ? (
        <Card style={{ gap: space(2) }}>
          <Text style={s.cardTitle}>Earlier versions</Text>
          {versions.slice(0, 6).map((v, i) => (
            <View key={i} style={s.versionRow}>
              <Text style={s.versionChange} numberOfLines={1}>{v.change}</Text>
              <Text style={s.versionPieces}>{v.piece_count} pcs</Text>
            </View>
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { ...type.title, color: colors.ink },
  sub: { ...type.body, color: colors.inkSoft, lineHeight: 21 },
  input: {
    minHeight: 96, backgroundColor: colors.surface, borderRadius: radius.lg,
    padding: space(4), ...type.body, color: colors.ink,
    borderWidth: 1, borderColor: colors.line, textAlignVertical: 'top',
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },
  cardTitle: { ...type.heading, color: colors.ink },
  understood: { ...type.body, color: colors.inkSoft },
  versionRow: { flexDirection: 'row', justifyContent: 'space-between', gap: space(3) },
  versionChange: { ...type.body, color: colors.inkSoft, flex: 1 },
  versionPieces: { ...type.small, color: colors.inkFaint },
});

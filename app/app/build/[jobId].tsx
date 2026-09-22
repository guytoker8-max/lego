/**
 * Questions, then the build.
 *
 * The questions come from the server, which only asks what it could not work
 * out and what would change the model: how big, how detailed, looks or
 * strength, and -- only when there is a single photo of something with real
 * depth -- whether to invent the side it never saw. Every one is answerable
 * with a single tap, and every one already has the sensible answer selected,
 * so a user who does not care can simply carry on.
 *
 * Then the progress screen, which reports the stage the server is actually
 * in rather than animating a bar and hoping.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Button, Card, Chip, ErrorState, Notice, Screen } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import {
  ApiError, getConfig, getJob, startBuild, type Config, type Job, type Question,
} from '@/api/client';

const POLL_MS = 600;

export default function BuildFlow() {
  const { jobId } = useLocalSearchParams<{ jobId: string }>();
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<'questions' | 'building'>('questions');
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<any>(null);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {});
    getJob(jobId)
      .then((j) => {
        setJob(j);
        const initial: Record<string, string> = {};
        (j.questions ?? []).forEach((q) => {
          initial[q.id] = (q.options.find((o) => o.default) ?? q.options[0]).id;
        });
        setAnswers(initial);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : 'Could not load this build.'),
      );
    return () => clearInterval(timer.current);
  }, [jobId]);

  const poll = useCallback(() => {
    timer.current = setInterval(async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
        if (j.status === 'done' && j.model_id) {
          clearInterval(timer.current);
          router.replace({ pathname: '/model/[id]', params: { id: j.model_id } });
        } else if (j.status === 'failed') {
          clearInterval(timer.current);
          setError(j.error ?? 'The build failed.');
        }
      } catch {
        // A dropped poll is not a failed build; the next tick retries.
      }
    }, POLL_MS);
  }, [jobId, router]);

  const begin = async () => {
    setPhase('building');
    setError(null);
    try {
      await startBuild(jobId, answers);
      poll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The build could not start.');
      setPhase('questions');
    }
  };

  if (error) {
    return (
      <Screen>
        <ErrorState
          message={error}
          onRetry={() => { setError(null); setPhase('questions'); }}
        />
        <Button label="Start over" tone="secondary" onPress={() => router.replace('/upload')} />
      </Screen>
    );
  }

  if (!job) return <Screen><ActivityIndicator style={{ marginTop: space(12) }} /></Screen>;

  if (phase === 'building') return <Progress job={job} />;

  const name = job.analysis?.display_name;
  const lowConfidence = (job.analysis?.confidence ?? 1) < 0.45;

  return (
    <Screen>
      {name && name !== 'Your Model' ? (
        <Card>
          <Text style={s.foundLabel}>I think this is</Text>
          <Text style={s.foundName}>{name}</Text>
          {lowConfidence ? (
            <Text style={s.foundHint}>
              I'm not certain, so I'll keep the shape simple and true to the outline.
            </Text>
          ) : null}
        </Card>
      ) : null}

      {(job.analysis?.warnings ?? []).map((w, i) => (
        <Notice key={i} kind="warning">{w}</Notice>
      ))}

      <Text style={s.title}>A couple of choices</Text>

      {(job.questions ?? []).map((q) => (
        <QuestionBlock
          key={q.id}
          question={q}
          value={answers[q.id]}
          config={config}
          onChange={(v) => setAnswers((a) => ({ ...a, [q.id]: v }))}
          onNeedPhoto={() => router.replace('/upload')}
        />
      ))}

      <Button label="Build it" onPress={begin} />
    </Screen>
  );
}

function QuestionBlock({ question, value, onChange, config, onNeedPhoto }: {
  question: Question; value: string; config: Config | null;
  onChange: (v: string) => void; onNeedPhoto: () => void;
}) {
  const presets = config?.size_presets ?? [];
  return (
    <Card style={{ gap: space(3) }}>
      <Text style={s.question}>{question.prompt}</Text>
      <View style={s.options}>
        {question.options.map((o) => {
          const preset = question.id === 'size'
            ? presets.find((p) => p.key === o.id)
            : undefined;
          return (
            <Chip
              key={o.id}
              label={o.label}
              sub={preset ? `up to ${preset.max_pieces} pcs` : undefined}
              selected={value === o.id}
              onPress={() => {
                onChange(o.id);
                // "No, I'll add another photo" is not an answer, it is a
                // request to go back and do that.
                if (question.id === 'unseen_back' && o.id === 'no') onNeedPhoto();
              }}
            />
          );
        })}
      </View>
    </Card>
  );
}

function Progress({ job }: { job: Job }) {
  const pct = Math.round((job.progress ?? 0) * 100);
  return (
    <Screen scroll={false} style={s.progressScreen}>
      <View style={s.progressInner}>
        <BrickSpinner />
        <Text style={s.progressMessage}>{job.message ?? 'Working...'}</Text>
        <View style={s.track}>
          <View style={[s.fill, { width: `${Math.max(6, pct)}%` }]} />
        </View>
        <Text style={s.progressHint}>
          Nothing is shown until the model is proved buildable.
        </Text>
      </View>
    </Screen>
  );
}

/** Three studs settling into place: enough motion to feel alive, no more. */
function BrickSpinner() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 340);
    return () => clearInterval(t);
  }, []);
  const hues = [colors.red, colors.brand, colors.blue];
  return (
    <View style={s.spinner}>
      {hues.map((h, i) => (
        <View
          key={i}
          style={[
            s.spinnerBrick,
            { backgroundColor: h, opacity: tick % 3 === i ? 1 : 0.35,
              transform: [{ translateY: tick % 3 === i ? -6 : 0 }] },
          ]}
        />
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  title: { ...type.title, color: colors.ink, marginTop: space(2) },
  question: { ...type.bodyStrong, color: colors.ink, lineHeight: 21 },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },

  foundLabel: { ...type.caps, color: colors.inkFaint },
  foundName: { ...type.title, color: colors.ink, marginTop: space(1) },
  foundHint: { ...type.small, color: colors.inkSoft, marginTop: space(2), lineHeight: 18 },

  progressScreen: { alignItems: 'center', justifyContent: 'center' },
  progressInner: { alignItems: 'center', gap: space(5), padding: space(8), width: '100%' },
  progressMessage: { ...type.heading, color: colors.ink, textAlign: 'center' },
  progressHint: { ...type.small, color: colors.inkFaint, textAlign: 'center' },
  track: {
    height: 8, width: '80%', borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt, overflow: 'hidden',
  },
  fill: { height: '100%', backgroundColor: colors.brand, borderRadius: radius.pill },

  spinner: { flexDirection: 'row', gap: space(2), height: 40, alignItems: 'flex-end' },
  spinnerBrick: { width: 26, height: 26, borderRadius: 6 },
});

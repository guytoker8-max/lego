/**
 * Upload.
 *
 * More than one photo is the difference between a guessed back and a known
 * one, so the screen asks for angles rather than just files: each slot is
 * labelled, and the labels are sent along so the reconstructor knows which
 * silhouette is the side view and can carve with it instead of extruding.
 */

import React, { useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';

import { Button, Card, Notice, Screen } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import { ApiError, uploadPhotos } from '@/api/client';

const SLOTS = [
  { angle: 'front', label: 'Front', required: true },
  { angle: 'side', label: 'Side', required: false },
  { angle: 'back', label: 'Back', required: false },
  { angle: 'top', label: 'Top', required: false },
];

export default function Upload() {
  const router = useRouter();
  const [photos, setPhotos] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = async (angle: string, fromCamera: boolean) => {
    const perm = fromCamera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setError(
        fromCamera
          ? 'BrickSnap needs camera access to take a photo. You can enable it in Settings.'
          : 'BrickSnap needs photo access to use a picture. You can enable it in Settings.',
      );
      return;
    }
    const result = fromCamera
      ? await ImagePicker.launchCameraAsync({ quality: 0.85 })
      : await ImagePicker.launchImageLibraryAsync({ quality: 0.85 });
    if (!result.canceled && result.assets?.[0]) {
      setPhotos((p) => ({ ...p, [angle]: result.assets[0].uri }));
      setError(null);
    }
  };

  const choose = (angle: string) =>
    Alert.alert('Add a photo', undefined, [
      { text: 'Take a photo', onPress: () => pick(angle, true) },
      { text: 'Choose from library', onPress: () => pick(angle, false) },
      { text: 'Cancel', style: 'cancel' },
    ]);

  const submit = async () => {
    const angles = SLOTS.map((s) => s.angle).filter((a) => photos[a]);
    if (!angles.length) return;
    setBusy(true);
    setError(null);
    try {
      const job = await uploadPhotos(angles.map((a) => photos[a]), angles);
      router.replace({ pathname: '/build/[jobId]', params: { jobId: job.id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The upload failed.');
      setBusy(false);
    }
  };

  const count = Object.keys(photos).length;

  return (
    <Screen>
      <Text style={s.title}>What are we building?</Text>
      <Text style={s.sub}>
        One photo is enough. Add a side or back view and the model is built
        from what you photographed instead of an interpretation of it.
      </Text>

      <View style={s.grid}>
        {SLOTS.map((slot) => (
          <Pressable
            key={slot.angle}
            onPress={() => choose(slot.angle)}
            accessibilityRole="button"
            accessibilityLabel={`Add ${slot.label} photo`}
            style={({ pressed }) => [s.slot, pressed && { opacity: 0.85 }]}
          >
            {photos[slot.angle] ? (
              <Image source={{ uri: photos[slot.angle] }} style={s.thumb} />
            ) : (
              <View style={s.empty}>
                <Text style={s.plus}>+</Text>
              </View>
            )}
            <Text style={s.slotLabel}>
              {slot.label}{slot.required ? '' : '  ·  optional'}
            </Text>
          </Pressable>
        ))}
      </View>

      {error ? <Notice kind="error">{error}</Notice> : null}

      <Button
        label={count > 1 ? `Build My Set from ${count} photos` : 'Build My Set'}
        onPress={submit}
        disabled={!count}
        loading={busy}
      />
      {!count ? (
        <Text style={s.hint}>Add at least one photo to continue.</Text>
      ) : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { ...type.title, color: colors.ink },
  sub: { ...type.body, color: colors.inkSoft, lineHeight: 21 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space(3) },
  slot: { width: '47.5%' },
  thumb: {
    width: '100%', aspectRatio: 1, borderRadius: radius.lg,
    backgroundColor: colors.surfaceAlt,
  },
  empty: {
    width: '100%', aspectRatio: 1, borderRadius: radius.lg,
    backgroundColor: colors.surfaceAlt, alignItems: 'center',
    justifyContent: 'center', borderWidth: 2, borderStyle: 'dashed',
    borderColor: colors.line,
  },
  plus: { fontSize: 34, color: colors.inkFaint, fontWeight: '300' },
  slotLabel: { ...type.small, color: colors.inkSoft, marginTop: space(2) },
  hint: { ...type.small, color: colors.inkFaint, textAlign: 'center' },
});

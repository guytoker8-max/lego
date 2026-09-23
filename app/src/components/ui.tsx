/** The handful of pieces every screen is built from. */

import React from 'react';
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
  ViewStyle, TextInput,
} from 'react-native';

import { colors, radius, shadow, space, type } from '@/theme';

export function Screen({ children, scroll = true, style }: any) {
  const Body: any = scroll ? ScrollView : View;
  return (
    <Body
      style={[s.screen, !scroll && style]}
      contentContainerStyle={scroll ? [s.screenContent, style] : undefined}
      showsVerticalScrollIndicator={false}
    >
      {children}
    </Body>
  );
}

export function Card({ children, style, onPress }: any) {
  const inner = <View style={[s.card, style]}>{children}</View>;
  if (!onPress) return inner;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => pressed && s.pressed}>
      {inner}
    </Pressable>
  );
}

export function Button({
  label, onPress, tone = 'primary', disabled, loading, style,
}: {
  label: string; onPress?: () => void;
  tone?: 'primary' | 'secondary' | 'ghost' | 'danger';
  disabled?: boolean; loading?: boolean; style?: ViewStyle;
}) {
  const off = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!off }}
      onPress={off ? undefined : onPress}
      style={({ pressed }) => [
        s.button, s[`btn_${tone}` as const],
        off && s.btnOff, pressed && !off && s.pressed, style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={tone === 'primary' ? colors.brandInk : colors.ink} />
      ) : (
        <Text style={[s.buttonLabel, tone === 'primary' && { color: colors.brandInk },
                      tone === 'danger' && { color: '#fff' }]}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

export function Chip({ label, selected, onPress, sub }: any) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected: !!selected }}
      onPress={onPress}
      style={({ pressed }) => [s.chip, selected && s.chipOn, pressed && s.pressed]}
    >
      <Text style={[s.chipLabel, selected && s.chipLabelOn]}>{label}</Text>
      {sub ? <Text style={[s.chipSub, selected && s.chipSubOn]}>{sub}</Text> : null}
    </Pressable>
  );
}

export function Stat({ label, value, tone, wide }: any) {
  return (
    <View style={[s.stat, wide && { flex: 2 }]}>
      <Text style={s.statValue} numberOfLines={1}>{value}</Text>
      <Text style={[s.statLabel, tone === 'quiet' && { color: colors.inkFaint }]}>
        {label}
      </Text>
    </View>
  );
}

export function Field({
  label, value, onChangeText, placeholder, autoComplete, keyboardType,
  autoCapitalize, invalid,
}: any) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput
        style={[s.field, invalid && { borderColor: colors.danger }]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.inkFaint}
        autoComplete={autoComplete}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize ?? 'words'}
        accessibilityLabel={label}
      />
    </View>
  );
}


export function Notice({ kind = 'info', children }: any) {
  const tint =
    kind === 'warning' ? colors.warning :
    kind === 'error' ? colors.danger : colors.inkSoft;
  return (
    <View style={[s.notice, { borderLeftColor: tint }]}>
      <Text style={[s.noticeText, { color: tint }]}>{children}</Text>
    </View>
  );
}

export function Loading({ label }: { label?: string }) {
  return (
    <View style={s.loading}>
      <ActivityIndicator color={colors.ink} />
      {label ? <Text style={s.loadingLabel}>{label}</Text> : null}
    </View>
  );
}

/** Shown wherever a screen has to admit something went wrong. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card style={{ gap: space(3) }}>
      <Text style={s.errorTitle}>That didn't work</Text>
      <Text style={s.errorBody}>{message}</Text>
      {onRetry ? <Button label="Try again" onPress={onRetry} tone="secondary" /> : null}
    </Card>
  );
}

export function Swatch({ hex, size = 18 }: { hex: string; size?: number }) {
  return (
    <View
      style={{
        width: size, height: size, borderRadius: size / 3,
        backgroundColor: hex, borderWidth: 1, borderColor: 'rgba(0,0,0,0.12)',
      }}
    />
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  screenContent: { padding: space(5), paddingBottom: space(16), gap: space(4) },
  card: {
    backgroundColor: colors.surface, borderRadius: radius.lg,
    padding: space(5), ...shadow.card,
  },
  pressed: { opacity: 0.85, transform: [{ scale: 0.99 }] },

  button: {
    minHeight: 54, borderRadius: radius.pill, alignItems: 'center',
    justifyContent: 'center', paddingHorizontal: space(6),
  },
  btn_primary: { backgroundColor: colors.brand, ...shadow.raised },
  btn_secondary: { backgroundColor: colors.surfaceAlt },
  btn_ghost: { backgroundColor: 'transparent' },
  btn_danger: { backgroundColor: colors.danger },
  btnOff: { opacity: 0.45 },
  buttonLabel: { ...type.bodyStrong, fontSize: 16, color: colors.ink },

  chip: {
    paddingVertical: space(3), paddingHorizontal: space(4),
    borderRadius: radius.md, backgroundColor: colors.surfaceAlt,
    borderWidth: 2, borderColor: 'transparent', minWidth: 92,
  },
  chipOn: { backgroundColor: colors.brand, borderColor: colors.brandInk },
  chipLabel: { ...type.bodyStrong, color: colors.ink },
  chipLabelOn: { color: colors.brandInk },
  chipSub: { ...type.small, color: colors.inkFaint, marginTop: 2 },
  chipSubOn: { color: colors.brandInk, opacity: 0.75 },

  stat: { flex: 1, minWidth: 84 },
  fieldLabel: { ...type.small, color: colors.inkSoft },
  field: {
    ...type.body, color: colors.ink, backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.line, borderRadius: radius.md,
    paddingHorizontal: space(3), paddingVertical: space(3),
  },
  statValue: { ...type.heading, color: colors.ink },
  statLabel: { ...type.small, color: colors.inkSoft, marginTop: 2 },

  notice: {
    borderLeftWidth: 3, paddingLeft: space(3), paddingVertical: space(2),
    backgroundColor: colors.surfaceAlt, borderRadius: radius.sm,
  },
  noticeText: { ...type.small },

  loading: { padding: space(10), alignItems: 'center', gap: space(3) },
  loadingLabel: { ...type.body, color: colors.inkSoft },

  errorTitle: { ...type.heading, color: colors.ink },
  errorBody: { ...type.body, color: colors.inkSoft, lineHeight: 21 },
});

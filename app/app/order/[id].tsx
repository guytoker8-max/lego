/** Order status: the five states the brief lists, and tracking once shipped. */

import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Button, Card, ErrorState, Loading, Screen, Stat } from '@/components/ui';
import { colors, radius, space, type } from '@/theme';
import { money } from '@/format';
import { ApiError, getOrder, type Order } from '@/api/client';

export default function OrderStatus() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    getOrder(id).then(setOrder).catch((e) =>
      setError(e instanceof ApiError ? e.message : 'Could not load this order.'));
  };
  useEffect(load, [id]);

  if (error) return <Screen><ErrorState message={error} onRetry={load} /></Screen>;
  if (!order) return <Loading label="Finding your order" />;

  return (
    <Screen>
      <Text style={s.title}>{order.status_label}</Text>
      <Text style={s.sub}>Order {order.id.slice(0, 8).toUpperCase()}</Text>

      <Card style={{ gap: space(4) }}>
        {order.steps.map((step, i) => (
          <View key={step.key} style={s.step}>
            <View style={[s.dot, step.done && s.dotOn]} />
            <Text style={[s.stepLabel, step.done && s.stepLabelOn]}>{step.label}</Text>
          </View>
        ))}
      </Card>

      <Card style={{ gap: space(4) }}>
        <View style={s.statRow}>
          <Stat label="Pieces" value={order.piece_count.toLocaleString()} />
          <Stat label="Paid" value={money(order.price.symbol, order.price.total)} />
        </View>
      </Card>

      {order.tracking?.number ? (
        <Card style={{ gap: space(2) }}>
          <Text style={s.cardTitle}>Tracking</Text>
          <Text style={s.body}>{order.tracking.carrier}</Text>
          <Text style={s.tracking}>{order.tracking.number}</Text>
        </Card>
      ) : null}

      <Button label="Back to my sets" tone="secondary" onPress={() => router.replace('/sets')} />
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { ...type.title, color: colors.ink },
  sub: { ...type.small, color: colors.inkFaint, marginTop: -space(2) },
  cardTitle: { ...type.heading, color: colors.ink },
  body: { ...type.body, color: colors.inkSoft },
  tracking: { ...type.bodyStrong, color: colors.ink, letterSpacing: 1 },
  statRow: { flexDirection: 'row', gap: space(3) },
  step: { flexDirection: 'row', alignItems: 'center', gap: space(3) },
  dot: {
    width: 14, height: 14, borderRadius: 7, backgroundColor: colors.surfaceAlt,
    borderWidth: 2, borderColor: colors.line,
  },
  dotOn: { backgroundColor: colors.brand, borderColor: colors.brandInk },
  stepLabel: { ...type.body, color: colors.inkFaint },
  stepLabelOn: { ...type.bodyStrong, color: colors.ink },
});

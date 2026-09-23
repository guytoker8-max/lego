/**
 * Make my set.
 *
 * Shows what the box costs and why, because a four-figure number for a big
 * model needs its parts count beside it. No card details are taken here or
 * anywhere in the app: the server hands back whatever the configured payment
 * provider needs, and until one is connected it says so plainly rather than
 * pretending the order went through.
 */

import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Button, Card, Chip, ErrorState, Loading, Notice, Screen, Stat } from '@/components/ui';
import { colors, space, type } from '@/theme';
import { money } from '@/format';
import {
  ApiError, createOrder, getConfig, getModel, priceModel,
  type Config, type Price, type Summary,
} from '@/api/client';

export default function OrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [price, setPrice] = useState<Price | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [shipping, setShipping] = useState('standard');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = () => {
    setError(null);
    Promise.all([getModel(id), getConfig()])
      .then(([m, c]) => { setSummary(m.summary); setPrice(m.price); setConfig(c); })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not load this set.'));
  };
  useEffect(load, [id]);

  const changeShipping = async (key: string) => {
    setShipping(key);
    try {
      setPrice(await priceModel(id, key));
    } catch {
      // Keep the old figure rather than showing a stale-but-wrong total.
      setError('Could not update the shipping price.');
    }
  };

  const order = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await createOrder(id, shipping);
      if (res.payment.status === 'awaiting_provider') setNote(res.payment.message);
      router.replace({ pathname: '/order/[id]', params: { id: res.order.id } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The order could not be placed.');
      setBusy(false);
    }
  };

  if (error && !price) return <Screen><ErrorState message={error} onRetry={load} /></Screen>;
  if (!summary || !price) return <Loading label="Pricing your set" />;

  const b = price.breakdown;

  return (
    <Screen>
      <Text style={s.title}>{summary.name}</Text>

      <Card style={{ gap: space(4) }}>
        <View style={s.statRow}>
          <Stat label="Pieces" value={summary.piece_count.toLocaleString()} />
          <Stat label="Build time" value={summary.build_time.label} />
          <Stat label="Made in" value={`${price.production_days} days`} />
        </View>
      </Card>

      <Card style={{ gap: space(3) }}>
        <Text style={s.cardTitle}>Delivery</Text>
        <View style={s.chips}>
          {price.shipping_options.map((o) => (
            <Chip key={o.key} label={o.label} sub={o.days}
                  selected={shipping === o.key} onPress={() => changeShipping(o.key)} />
          ))}
        </View>
      </Card>

      <Card style={{ gap: space(2) }}>
        <Text style={s.cardTitle}>What you're paying for</Text>
        <Line label={`Bricks (${summary.piece_count.toLocaleString()} pieces)`}
              value={money(price.symbol, b.parts)} />
        <Line label="Box and packing" value={money(price.symbol, b.packaging)} />
        <Line label="Picking and handling" value={money(price.symbol, b.handling)} />
        <Line label="VAT" value={money(price.symbol, b.vat)} />
        <Line label="Shipping" value={money(price.symbol, b.shipping)} />
        <View style={s.divider} />
        <Line label="Total" value={money(price.symbol, price.total)} strong />
      </Card>

      {note ? <Notice kind="warning">{note}</Notice> : null}
      {error ? <Notice kind="error">{error}</Notice> : null}

      <Button label={`Order Now · ${money(price.symbol, price.total)}`}
              onPress={order} loading={busy} />

      {config ? <Text style={s.legal}>{config.branding.disclaimer}</Text> : null}
    </Screen>
  );
}

function Line({ label, value, strong }: any) {
  return (
    <View style={s.line}>
      <Text style={[s.lineLabel, strong && s.strong]}>{label}</Text>
      <Text style={[s.lineValue, strong && s.strong]}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  title: { ...type.title, color: colors.ink },
  cardTitle: { ...type.heading, color: colors.ink },
  statRow: { flexDirection: 'row', gap: space(3) },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },
  line: { flexDirection: 'row', justifyContent: 'space-between', gap: space(3) },
  lineLabel: { ...type.body, color: colors.inkSoft, flex: 1 },
  lineValue: { ...type.body, color: colors.ink },
  strong: { ...type.bodyStrong, color: colors.ink, fontSize: 17 },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: space(2) },
  legal: { ...type.small, color: colors.inkFaint, lineHeight: 17 },
});

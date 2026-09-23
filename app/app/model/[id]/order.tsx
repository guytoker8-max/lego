/**
 * Make my set.
 *
 * Shows what the box costs and why, takes where it is going, and hands off
 * to the payment provider. No card details are taken here or anywhere in the
 * app: the server creates the payment session and returns a URL to open, so
 * the only thing that ever sees a card is the provider's own page.
 *
 * Approving the design comes first and is not a formality. The server records
 * the fingerprint of the model it approved and refuses an order for anything
 * else, which is what stops a set being edited between the price someone
 * agreed to and the box that gets packed.
 */

import React, { useEffect, useState } from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import {
  Button, Card, Chip, ErrorState, Field, Loading, Notice, Screen, Stat,
} from '@/components/ui';
import { colors, space, type } from '@/theme';
import { countryName, money } from '@/format';
import {
  ApiError, approveDesign, getConfig, getModel, getStoreConfig, priceModel,
  startCheckout, type Config, type Price, type StoreConfig, type Summary,
} from '@/api/client';

const EMPTY = {
  name: '', email: '', phone: '',
  line1: '', line2: '', city: '', region: '', postal_code: '', country: '',
};

export default function OrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [price, setPrice] = useState<Price | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [shop, setShop] = useState<StoreConfig | null>(null);
  const [to, setTo] = useState({ ...EMPTY });
  const [shipping, setShipping] = useState('standard');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    Promise.all([getModel(id), getConfig(), getStoreConfig()])
      .then(([m, c, sc]) => {
        setSummary(m.summary);
        setPrice(m.price);
        setConfig(c);
        setShop(sc);
        // One shipping country is not a choice, so it is filled in rather
        // than asked for.
        if (sc.ship_countries.length === 1) {
          setTo((t) => ({ ...t, country: sc.ship_countries[0] }));
        }
      })
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

  const set = (k: keyof typeof EMPTY) => (v: string) =>
    setTo((t) => ({ ...t, [k]: v }));

  const missing = (['name', 'email', 'line1', 'city', 'postal_code', 'country'] as const)
    .filter((k) => !to[k].trim());

  const pay = async () => {
    if (!summary) return;
    setBusy(true);
    setError(null);
    try {
      await approveDesign(id, summary.fingerprint);
      const checkout = await startCheckout({
        model_id: id, shipping,
        name: to.name.trim(), email: to.email.trim(), phone: to.phone.trim(),
        address: {
          line1: to.line1.trim(), line2: to.line2.trim(), city: to.city.trim(),
          region: to.region.trim(), postal_code: to.postal_code.trim(),
          country: to.country.trim().toUpperCase(),
        },
      });
      // The order exists and is waiting for money. Go to its page first, so
      // that closing the payment tab leaves the person somewhere sensible
      // rather than back on a form they have already filled in.
      router.replace({
        pathname: '/order/[id]',
        params: { id: checkout.order_id, token: checkout.token },
      });
      if (checkout.redirect_url) Linking.openURL(checkout.redirect_url).catch(() => {});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'The order could not be placed.');
      setBusy(false);
    }
  };

  if (error && !price) return <Screen><ErrorState message={error} onRetry={load} /></Screen>;
  if (!summary || !price || !shop) return <Loading label="Pricing your set" />;

  const b = price.breakdown;
  const methods = shop.shipping_methods ?? ['standard', 'express'];
  const options = price.shipping_options.filter((o) => methods.includes(o.key));

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
          {options.map((o) => (
            <Chip key={o.key} label={o.label} sub={o.days}
                  selected={shipping === o.key} onPress={() => changeShipping(o.key)} />
          ))}
        </View>
      </Card>

      <Card style={{ gap: space(3) }}>
        <Text style={s.cardTitle}>Where is it going?</Text>
        <Field label="Full name" value={to.name} onChangeText={set('name')}
               autoComplete="name" placeholder="Guy Toker" />
        <Field label="Email" value={to.email} onChangeText={set('email')}
               autoComplete="email" keyboardType="email-address"
               autoCapitalize="none" placeholder="you@example.com" />
        <Field label="Street address" value={to.line1} onChangeText={set('line1')}
               autoComplete="street-address" placeholder="1 Herzl St" />
        <Field label="Flat, floor (optional)" value={to.line2}
               onChangeText={set('line2')} placeholder="" />
        <View style={s.pair}>
          <View style={{ flex: 2 }}>
            <Field label="City" value={to.city} onChangeText={set('city')}
                   placeholder="Tel Aviv" />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Postcode" value={to.postal_code}
                   onChangeText={set('postal_code')} keyboardType="numbers-and-punctuation"
                   placeholder="6100000" />
          </View>
        </View>
        {shop.ship_countries.length > 1 ? (
          <Field label="Country" value={to.country} onChangeText={set('country')}
                 autoCapitalize="characters"
                 placeholder={shop.ship_countries.join(', ')} />
        ) : (
          <Text style={s.hint}>
            We ship to {countryName(shop.ship_countries[0])} for now.
          </Text>
        )}
        <Field label="Phone (optional)" value={to.phone} onChangeText={set('phone')}
               keyboardType="phone-pad" placeholder="050 000 0000" />
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

      {shop.payments && shop.payments.live === false ? (
        <Notice kind="warning">
          Payment is in test mode, so nothing is charged and no set is made.
        </Notice>
      ) : null}
      {error ? <Notice kind="error">{error}</Notice> : null}

      <Button label={`Pay ${money(price.symbol, price.total)}`}
              onPress={pay} loading={busy} disabled={missing.length > 0} />
      {missing.length ? (
        <Text style={s.hint}>Fill in your delivery details to continue.</Text>
      ) : null}

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
  pair: { flexDirection: 'row', gap: space(3) },
  line: { flexDirection: 'row', justifyContent: 'space-between', gap: space(3) },
  lineLabel: { ...type.body, color: colors.inkSoft, flex: 1 },
  lineValue: { ...type.body, color: colors.ink },
  strong: { ...type.bodyStrong, color: colors.ink, fontSize: 17 },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: space(2) },
  hint: { ...type.small, color: colors.inkFaint, textAlign: 'center' },
  legal: { ...type.small, color: colors.inkFaint, lineHeight: 17 },
});

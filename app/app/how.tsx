/** How it works: the honest version, including what it cannot do. */

import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Card, Screen } from '@/components/ui';
import { colors, space, type } from '@/theme';
import { getConfig, type Config } from '@/api/client';

const STEPS = [
  ['Photograph it', 'One photo works. Two or three from different sides work better, because the model is then built from what you photographed rather than an interpretation of the parts nobody saw.'],
  ['It gets read', 'The subject is separated from its background and measured: proportions, symmetry, how deep it is, which colours it is actually made of.'],
  ['It becomes bricks', 'The shape is filled with real elements, each one a part that exists, in a colour that is really moulded, at a position on the stud grid.'],
  ['It gets checked', 'Every piece must rest on something, the whole thing must hold together, and it has to stand up. Anything that fails is rebuilt until it passes. You are never shown a model that cannot be built.'],
  ['You build it', 'Step-by-step instructions, and a parts list counted from the model itself, so the box, the booklet and the thing on your screen are the same object.'],
];

export default function How() {
  const [config, setConfig] = useState<Config | null>(null);
  useEffect(() => { getConfig().then(setConfig).catch(() => {}); }, []);

  return (
    <Screen>
      {STEPS.map(([title, body], i) => (
        <Card key={title} style={{ gap: space(2) }}>
          <Text style={s.num}>{String(i + 1).padStart(2, '0')}</Text>
          <Text style={s.title}>{title}</Text>
          <Text style={s.body}>{body}</Text>
        </Card>
      ))}
      <Card style={{ gap: space(2) }}>
        <Text style={s.title}>What it can't do</Text>
        <Text style={s.body}>
          A photo shows one side of a thing. Where a second photo isn't
          supplied, the unseen side is a reasonable interpretation, and the app
          asks before making one. Very small details don't survive being
          reduced to 8 mm studs, and a blurry or crowded photo gives a rougher
          model. You'll be told when that happens rather than finding out when
          the box arrives.
        </Text>
      </Card>
      {config ? <Text style={s.legal}>{config.branding.disclaimer}</Text> : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  num: { ...type.caps, color: colors.inkFaint },
  title: { ...type.heading, color: colors.ink },
  body: { ...type.body, color: colors.inkSoft, lineHeight: 22 },
  legal: { ...type.small, color: colors.inkFaint, lineHeight: 17 },
});

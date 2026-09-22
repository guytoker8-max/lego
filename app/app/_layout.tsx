import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { colors, type } from '@/theme';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerShadowVisible: false,
          headerTintColor: colors.ink,
          headerTitleStyle: { ...type.heading },
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="upload" options={{ title: 'Your photos' }} />
        <Stack.Screen name="build/[jobId]" options={{ title: 'Building', headerBackVisible: false }} />
        <Stack.Screen name="model/[id]/index" options={{ title: 'Your set' }} />
        <Stack.Screen name="model/[id]/instructions" options={{ title: 'Instructions' }} />
        <Stack.Screen name="model/[id]/parts" options={{ title: 'Parts list' }} />
        <Stack.Screen name="model/[id]/edit" options={{ title: 'Change this set' }} />
        <Stack.Screen name="model/[id]/order" options={{ title: 'Make my set' }} />
        <Stack.Screen name="order/[id]" options={{ title: 'Your order' }} />
        <Stack.Screen name="sets" options={{ title: 'My sets' }} />
        <Stack.Screen name="how" options={{ title: 'How it works' }} />
      </Stack>
    </SafeAreaProvider>
  );
}

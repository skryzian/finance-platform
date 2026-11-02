import { useMemo, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Notifications from 'expo-notifications';
import { useLocalFinanceRepository } from '../src/hooks/useLocalFinanceRepository';
import { FinanceSyncService } from '../src/services/financeSync';
import type { LocalSyncConflict } from '../src/types/offline';

export function OfflineSyncPanel() {
  const repository = useLocalFinanceRepository();
  const [serverUrl, setServerUrl] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [userId, setUserId] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [pushDeviceId, setPushDeviceId] = useState<number | null>(null);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [sessionServerUrl, setSessionServerUrl] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<LocalSyncConflict[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const service = useMemo(() => {
    try {
      const activeServerUrl = accessToken ? sessionServerUrl : serverUrl;
      return activeServerUrl?.trim() ? new FinanceSyncService(repository, activeServerUrl) : null;
    } catch {
      return null;
    }
  }, [accessToken, repository, serverUrl, sessionServerUrl]);

  async function signIn() {
    if (!service) {
      setError('Enter a valid server URL before signing in.');
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const session = await service.login(email, password);
      setUserId(session.userId);
      setAccessToken(session.tokens.access_token);
      setSessionServerUrl(serverUrl);
      setConflicts(await repository.listSyncConflicts(session.userId));
      const baseUrl = serverUrl.replace(/\/+$/, '');
      const [preferencesResponse, devicesResponse] = await Promise.all([
        fetch(`${baseUrl}/api/notifications/preferences`, { headers: { Authorization: `Bearer ${session.tokens.access_token}` } }),
        fetch(`${baseUrl}/api/notifications/devices`, { headers: { Authorization: `Bearer ${session.tokens.access_token}` } }),
      ]);
      if (!preferencesResponse.ok || !devicesResponse.ok) throw new Error('Could not load notification settings.');
      const preferences = await preferencesResponse.json();
      const devices = await devicesResponse.json();
      setPushEnabled(Boolean(preferences.push_enabled));
      setPushDeviceId(devices[0]?.id ?? null);
      setPassword('');
      setMessage('Signed in. Local data remains encrypted on this device.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  }

  async function togglePushNotifications() {
    if (!accessToken || !sessionServerUrl) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    const baseUrl = sessionServerUrl.replace(/\/+$/, '');
    try {
      const preferencesResponse = await fetch(`${baseUrl}/api/notifications/preferences`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!preferencesResponse.ok) throw new Error('Could not load notification preferences.');
      const preferences = await preferencesResponse.json();

      if (pushEnabled) {
        const saveResponse = await fetch(`${baseUrl}/api/notifications/preferences`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
          body: JSON.stringify({ ...preferences, push_enabled: false }),
        });
        if (!saveResponse.ok) throw new Error('Could not disable push notifications.');
        if (pushDeviceId !== null) {
          const removeResponse = await fetch(`${baseUrl}/api/notifications/devices/${pushDeviceId}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${accessToken}` },
          });
          if (!removeResponse.ok) throw new Error('Push delivery was disabled, but this device could not be removed.');
        }
        setPushDeviceId(null);
        setPushEnabled(false);
        setMessage('Push notifications disabled for this account.');
        return;
      }

      const permission = await Notifications.getPermissionsAsync();
      const granted = permission.granted
        ? permission
        : await Notifications.requestPermissionsAsync();
      if (!granted.granted) throw new Error('Allow notification permission in device settings before enabling push.');
      const projectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID;
      if (!projectId) throw new Error('Configure EXPO_PUBLIC_EAS_PROJECT_ID before registering this device.');
      const token = await Notifications.getExpoPushTokenAsync({ projectId });
      const platform = Platform.OS === 'ios' || Platform.OS === 'android' ? Platform.OS : null;
      if (!platform) throw new Error('Push registration is supported only on iOS and Android.');
      const deviceResponse = await fetch(`${baseUrl}/api/notifications/devices`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ push_token: token.data, platform }),
      });
      if (!deviceResponse.ok) throw new Error('Could not register this device for push delivery.');
      const device = await deviceResponse.json();
      const saveResponse = await fetch(`${baseUrl}/api/notifications/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ ...preferences, push_enabled: true }),
      });
      if (!saveResponse.ok) throw new Error('Device registered, but push delivery could not be enabled.');
      setPushDeviceId(device.id);
      setPushEnabled(true);
      setMessage('Push notifications enabled. External messages contain no financial amounts.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update push notification settings.');
    } finally {
      setBusy(false);
    }
  }

  async function synchronize() {
    if (!service || !userId || !accessToken) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await service.synchronize(userId, accessToken);
      setConflicts(await repository.listSyncConflicts(userId));
      setMessage(
        `Sync complete: ${result.pushed} changes applied, ${result.pulled} pulled, ${result.conflicts} conflicts, ${result.rejected} rejected. Cursor ${result.cursor}.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Synchronization failed.');
    } finally {
      setBusy(false);
    }
  }

  async function resolveConflict(conflict: LocalSyncConflict, resolution: 'SERVER' | 'LOCAL') {
    if (!userId) return;
    setError(null);
    try {
      await repository.resolveSyncConflict(userId, conflict.id, resolution);
      setConflicts(await repository.listSyncConflicts(userId));
      setMessage(`Conflict resolved using the ${resolution === 'SERVER' ? 'server' : 'local'} version.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not resolve sync conflict.');
    }
  }

  async function signOut() {
    setError(null);
    setMessage(null);
    if (service && accessToken) {
      setBusy(true);
      try {
        await service.logout(accessToken);
        setMessage('Signed out and server session revoked.');
      } catch (caught) {
        setError(caught instanceof Error ? `Signed out locally; server revocation failed: ${caught.message}` : 'Signed out locally; server revocation failed.');
      } finally {
        setBusy(false);
      }
    }
    setAccessToken(null);
    setUserId(null);
    setSessionServerUrl(null);
    setConflicts([]);
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Offline synchronization</Text>
      <Text style={styles.note}>
        Changes stay on this device until you sign in and sync. Use the server address reachable from this device.
      </Text>
      <TextInput
        accessibilityLabel="Finance server URL"
        autoCapitalize="none"
        keyboardType="url"
        onChangeText={setServerUrl}
        placeholder="https://finance.example.com"
        style={styles.input}
        editable={!accessToken}
        value={serverUrl}
      />
      {!accessToken ? (
        <>
          <TextInput
            accessibilityLabel="Email"
            autoCapitalize="none"
            keyboardType="email-address"
            onChangeText={setEmail}
            placeholder="Email"
            style={styles.input}
            value={email}
          />
          <TextInput
            accessibilityLabel="Password"
            onChangeText={setPassword}
            placeholder="Password"
            secureTextEntry
            style={styles.input}
            value={password}
          />
          <Pressable disabled={busy} onPress={signIn} style={styles.button}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign in to sync</Text>}
          </Pressable>
        </>
      ) : (
        <>
          <Pressable disabled={busy} onPress={synchronize} style={styles.button}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sync now</Text>}
          </Pressable>
          <Pressable disabled={busy} onPress={togglePushNotifications} style={styles.signOutButton}>
            <Text style={styles.signOutText}>{pushEnabled ? 'Disable mobile push notifications' : 'Enable mobile push notifications'}</Text>
          </Pressable>
          <Pressable
            disabled={busy}
            onPress={signOut}
            style={styles.signOutButton}
          >
            <Text style={styles.signOutText}>Sign out</Text>
          </Pressable>
        </>
      )}
      {message ? <Text accessibilityLiveRegion="polite" style={styles.success}>{message}</Text> : null}
      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      {conflicts.map((conflict) => {
        const conflictMessage = typeof conflict.serverPayload.message === 'string'
          ? conflict.serverPayload.message
          : 'This record differs from the server version.';
        return (
          <View key={conflict.id} style={styles.conflict}>
            <Text style={styles.conflictTitle}>{conflict.entityType} conflict · {conflict.entityId}</Text>
            <Text style={styles.note}>{conflictMessage}</Text>
            <Pressable disabled={busy} onPress={() => resolveConflict(conflict, 'SERVER')} style={styles.conflictAction}>
              <Text style={styles.conflictActionText}>Use server version</Text>
            </Pressable>
            {conflict.entityType !== 'transaction' ? (
              <Pressable disabled={busy} onPress={() => resolveConflict(conflict, 'LOCAL')} style={styles.conflictAction}>
                <Text style={styles.conflictActionText}>Keep local version</Text>
              </Pressable>
            ) : (
              <Text style={styles.note}>Ledger transactions are immutable; record a reversal to correct one.</Text>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 18,
    gap: 12,
    padding: 20,
  },
  title: {
    color: '#0f172a',
    fontSize: 18,
    fontWeight: '700',
  },
  note: {
    color: '#475569',
    lineHeight: 21,
  },
  input: {
    borderColor: '#cbd5e1',
    borderRadius: 10,
    borderWidth: 1,
    color: '#0f172a',
    paddingHorizontal: 12,
    paddingVertical: 11,
  },
  button: {
    alignItems: 'center',
    backgroundColor: '#0b3a2d',
    borderRadius: 10,
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  buttonText: {
    color: '#fff',
    fontWeight: '700',
  },
  signOutButton: {
    alignItems: 'center',
    padding: 8,
  },
  signOutText: {
    color: '#475569',
    fontWeight: '600',
  },
  conflict: {
    borderColor: '#f59e0b',
    borderRadius: 10,
    borderWidth: 1,
    gap: 8,
    padding: 12,
  },
  conflictTitle: {
    color: '#92400e',
    fontWeight: '700',
  },
  conflictAction: {
    alignItems: 'flex-start',
    paddingVertical: 6,
  },
  conflictActionText: {
    color: '#0b3a2d',
    fontWeight: '700',
  },
  success: {
    color: '#166534',
    lineHeight: 20,
  },
  error: {
    color: '#b91c1c',
    lineHeight: 20,
  },
});

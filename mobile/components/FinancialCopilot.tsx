import { useState } from 'react';
import Constants from 'expo-constants';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

type Message = { role: 'user' | 'assistant'; content: string };
const apiUrl = process.env.EXPO_PUBLIC_API_URL ?? Constants.expoConfig?.extra?.apiUrl ?? 'http://10.0.2.2:8000';

export function FinancialCopilot() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [historyEnabled, setHistoryEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function signIn() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? 'Sign-in failed.');
      setToken(body.access_token);
      setPassword('');
      const history = await fetch(`${apiUrl}/api/ai/history`, { headers: { Authorization: `Bearer ${body.access_token}` } });
      if (history.ok) setHistoryEnabled((await history.json()).enabled);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to sign in.');
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage() {
    const text = question.trim();
    if (!token || !text || busy) return;
    setMessages((current) => [...current, { role: 'user', content: text }]);
    setQuestion('');
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`${apiUrl}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question: text, ...(conversationId ? { conversation_id: conversationId } : {}) }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? 'Financial Copilot is unavailable.');
      setConversationId(body.conversation_id);
      setMessages((current) => [...current, { role: 'assistant', content: body.answer }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Financial Copilot is unavailable.');
    } finally {
      setBusy(false);
    }
  }

  async function toggleHistory() {
    const enabled = !historyEnabled;
    if (!enabled) {
      const confirmed = await new Promise<boolean>((resolve) => {
        Alert.alert('Delete saved history?', 'Turning off chat history removes your saved Copilot conversations.', [
          { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
          { text: 'Turn off and delete', style: 'destructive', onPress: () => resolve(true) },
        ]);
      });
      if (!confirmed) return;
    }
    try {
      const response = await fetch(`${apiUrl}/api/ai/history`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ enabled }),
      });
      if (!response.ok) throw new Error('Could not update history preference.');
      setHistoryEnabled(enabled);
      setConversationId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update history preference.');
    }
  }

  return (
    <View style={styles.panel}>
      <Text style={styles.title}>Financial Copilot</Text>
      <Text style={styles.subtitle}>Personal financial facts require verified application data. Your access token stays in memory.</Text>
      {!token ? (
        <View style={styles.form}>
          <TextInput style={styles.input} placeholder="Email" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
          <TextInput style={styles.input} placeholder="Password" secureTextEntry value={password} onChangeText={setPassword} />
          <Pressable style={styles.button} onPress={signIn} disabled={busy}><Text style={styles.buttonText}>{busy ? 'Signing in…' : 'Sign in'}</Text></Pressable>
        </View>
      ) : (
        <>
          <Pressable onPress={toggleHistory} style={styles.history}><Text style={styles.historyText}>{historyEnabled ? '☑' : '□'} Save chat history</Text></Pressable>
          <ScrollView style={styles.messages} contentContainerStyle={styles.messageList}>
            {messages.length === 0 && <Text style={styles.empty}>Ask about your finances. The assistant will say when personal data is unavailable.</Text>}
            {messages.map((message, index) => <View key={`${message.role}-${index}`} style={[styles.bubble, message.role === 'user' ? styles.userBubble : styles.assistantBubble]}><Text style={message.role === 'user' ? styles.userText : styles.assistantText}>{message.content}</Text></View>)}
            {busy && <ActivityIndicator color="#0b7a61" />}
          </ScrollView>
          <View style={styles.composer}>
            <TextInput style={[styles.input, styles.question]} placeholder="Ask Financial Copilot" value={question} onChangeText={setQuestion} maxLength={4000} multiline />
            <Pressable style={styles.sendButton} onPress={sendMessage} disabled={busy || !question.trim()}><Text style={styles.buttonText}>Send</Text></Pressable>
          </View>
          <View style={styles.actions}>
            <Pressable onPress={() => { setMessages([]); setConversationId(null); }} style={styles.signOut}><Text style={styles.historyText}>New chat</Text></Pressable>
            <Pressable onPress={() => { setToken(''); setPassword(''); setMessages([]); setConversationId(null); }} style={styles.signOut}><Text style={styles.historyText}>Sign out</Text></Pressable>
          </View>
        </>
      )}
      {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { backgroundColor: '#fff', borderRadius: 16, padding: 18, gap: 12, borderWidth: 1, borderColor: '#dbe4e1' },
  title: { color: '#102b24', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#60716c', fontSize: 13, lineHeight: 19 },
  form: { gap: 10 },
  input: { borderWidth: 1, borderColor: '#cbd5d1', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, color: '#172a25' },
  button: { backgroundColor: '#0b7a61', borderRadius: 10, padding: 12, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '600' },
  history: { paddingVertical: 7 },
  historyText: { color: '#52645f', fontSize: 13 },
  messages: { maxHeight: 300, minHeight: 100 },
  messageList: { gap: 8 },
  empty: { color: '#60716c', lineHeight: 20 },
  bubble: { borderRadius: 12, padding: 12, maxWidth: '90%' },
  userBubble: { alignSelf: 'flex-end', backgroundColor: '#0b3a2d' },
  assistantBubble: { alignSelf: 'flex-start', backgroundColor: '#eef3f1' },
  userText: { color: '#fff', lineHeight: 20 },
  assistantText: { color: '#263b35', lineHeight: 20 },
  composer: { flexDirection: 'row', gap: 8, alignItems: 'flex-end' },
  question: { flex: 1, maxHeight: 100 },
  sendButton: { backgroundColor: '#0b7a61', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12 },
  signOut: { alignSelf: 'flex-end', padding: 4 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 16 },
  error: { backgroundColor: '#fff1f0', color: '#a12c25', borderRadius: 8, padding: 10 },
});

import { StatusBar } from 'expo-status-bar';
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SQLiteProvider } from 'expo-sqlite';
import { FinancialCopilot } from './components/FinancialCopilot';
import { initializeLocalDatabase } from './src/database/localDatabase';

export default function App() {
  return (
    <SQLiteProvider databaseName="finance-platform.db" onInit={initializeLocalDatabase}>
      <Dashboard />
    </SQLiteProvider>
  );
}

function Dashboard() {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.header}>
          <Text style={styles.eyebrow}>Finance Platform</Text>
          <Text style={styles.title}>Mobile Dashboard</Text>
          <Text style={styles.storageStatus}>Encrypted local storage ready</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Net worth</Text>
          <Text style={styles.value}>KES 1,245,000</Text>
          <Text style={styles.change}>+12.4% this month</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Detected transactions</Text>
          <Text style={styles.note}>Pending review requires explicit confirmation before recording.</Text>
        </View>

        <FinancialCopilot />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  container: {
    padding: 20,
    gap: 16,
  },
  header: {
    backgroundColor: '#0b3a2d',
    borderRadius: 18,
    padding: 24,
  },
  eyebrow: {
    color: '#d8f5ea',
    fontSize: 12,
    letterSpacing: 3,
    textTransform: 'uppercase',
  },
  title: {
    color: '#fff',
    fontSize: 28,
    fontWeight: '700',
    marginTop: 10,
  },
  storageStatus: {
    color: '#d8f5ea',
    fontSize: 12,
    marginTop: 8,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 18,
    padding: 20,
    shadowColor: '#0f172a',
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 2,
  },
  cardTitle: {
    color: '#475569',
    fontSize: 14,
    marginBottom: 8,
  },
  value: {
    fontSize: 30,
    fontWeight: '700',
    color: '#0f172a',
  },
  change: {
    color: '#0f9d7a',
    marginTop: 4,
    fontWeight: '600',
  },
  note: {
    color: '#334155',
    lineHeight: 22,
  },
});

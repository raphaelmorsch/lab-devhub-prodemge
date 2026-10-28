import React from 'react';
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';

const FACTS = [
  ['React Native', '0.68.7'],
  ['Motor JavaScript', 'JavaScriptCore'],
  ['Hermes', 'desligado'],
  ['Nova Arquitetura', 'desligada'],
  ['applicationId', 'com.sidsmobile'],
  ['Ambientes', 'desenvolvimento, homologacao, treinamento, producao'],
];

const App = () => {
  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.kicker}>Laboratório PRODEMGE</Text>
        <Text style={styles.title}>SISP Mobile</Text>
        <Text style={styles.lead}>
          Exemplo da pilha React Native 0.68.7, equivalente à branch master.
          O nome exibido no Android muda conforme o flavor.
        </Text>
        {FACTS.map(([label, value]) => (
          <View key={label} style={styles.row}>
            <Text style={styles.label}>{label}</Text>
            <Text style={styles.value}>{value}</Text>
          </View>
        ))}
        <Text style={styles.command}>./gradlew assembleHomologacaoRelease</Text>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#0B3A66',
  },
  content: {
    paddingHorizontal: 24,
    paddingVertical: 32,
  },
  kicker: {
    color: '#F2C14E',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    color: '#FFFFFF',
    fontSize: 36,
    fontWeight: '700',
    marginTop: 8,
  },
  lead: {
    color: '#D6E4F0',
    fontSize: 16,
    lineHeight: 24,
    marginTop: 12,
    marginBottom: 24,
  },
  row: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#3E6F99',
    paddingVertical: 12,
  },
  label: {
    color: '#9EC0DE',
    fontSize: 13,
  },
  value: {
    color: '#FFFFFF',
    fontSize: 16,
    marginTop: 2,
  },
  command: {
    color: '#F2C14E',
    fontSize: 14,
    marginTop: 28,
  },
});

export default App;

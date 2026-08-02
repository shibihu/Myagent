import React from 'react';
import { StyleSheet, TextInput, View, ScrollView } from 'react-native';

export default function CodeEditor({ code, setCode }) {
  return (
    <View style={styles.container}>
      <ScrollView horizontal>
        <TextInput
          style={styles.editorInput}
          multiline
          value={code}
          onChangeText={setCode}
          placeholder="-- พิมพ์โค้ด Lua / Python ที่นี่..."
          placeholderTextColor="#888"
          autoCapitalize="none"
          autoCorrect={false}
          spellCheck={false}
        />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1e1e1e',
    borderRadius: 8,
    padding: 10,
  },
  editorInput: {
    color: '#f8f8f2',
    fontFamily: 'monospace', // หรือใช้ font สำหรับโค้ด
    fontSize: 16, // 💡 สำคัญ: ขนาด 16px ป้องกัน Auto-Zoom บน iOS/Android
    minWidth: 300,
    textAlignVertical: 'top',
  },
});
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.skdev.moneyflow',
  appName: 'MoneyFlow',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
    // For local dev, uncomment and set your machine's local IP:
    // url: 'http://192.168.x.x:5173',
    // cleartext: true,
  },
  android: {
    allowMixedContent: false,
  },
};

export default config;

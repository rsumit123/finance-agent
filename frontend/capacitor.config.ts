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
  plugins: {
    GoogleAuth: {
      scopes: ["profile", "email"],
      serverClientId: "929006071236-feqt94b4t8ltebpod8hmavt52hrd40gk.apps.googleusercontent.com",
      forceCodeForRefreshToken: false,
    },
  },
};

export default config;

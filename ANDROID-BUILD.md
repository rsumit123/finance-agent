# Android App Build & Deploy Guide

## Prerequisites

- **Android Studio** installed (for SDK)
- **Java 21** (`brew install openjdk@21`)
- **Node.js** for frontend build
- Android SDK at `~/Library/Android/sdk`

## Environment Setup

```bash
export ANDROID_HOME=~/Library/Android/sdk
export JAVA_HOME=$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home
```

## Build Steps

```bash
cd frontend

# 1. Install dependencies (if changed)
npm install --legacy-peer-deps

# 2. Build the React app
npm run build

# 3. Sync web assets to Android project
npx cap sync android

# 4. Build debug APK
cd android
./gradlew assembleDebug

# APK location:
# android/app/build/outputs/apk/debug/app-debug.apk
```

## Quick One-Liner

```bash
cd frontend && npm run build && npx cap sync android && cd android && \
ANDROID_HOME=~/Library/Android/sdk \
JAVA_HOME=$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home \
./gradlew assembleDebug
```

## Upload to S3 (for distribution)

```bash
# Get a presigned URL from AWS, then:
curl -X PUT -T android/app/build/outputs/apk/debug/app-debug.apk "<PRESIGNED_URL>"
```

## Install on Device

1. Transfer APK to phone (S3 download, ADB, Nearby Share, etc.)
2. If Google Play Protect blocks: Settings → Play Protect → gear icon → turn off scanning temporarily
3. If SMS permission denied: Settings → Apps → MoneyFlow → Permissions → SMS → Allow
4. Re-enable Play Protect after install

## GCP Configuration Required

### OAuth Credentials (Google Cloud Console → APIs & Services → Credentials)

**Web Client** (for web app + token validation):
- Type: Web application
- Client ID: `929006071236-feqt94b4t8ltebpod8hmavt52hrd40gk.apps.googleusercontent.com`
- Redirect URIs:
  - `https://moneyflow-api.skdev.one/api/auth/google/callback`
  - `https://moneyflow-api.skdev.one/api/gmail/callback`
  - `http://localhost:8000/api/auth/google/callback`

**Android Client** (for native Google Sign-In):
- Type: Android
- Package name: `com.skdev.moneyflow`
- SHA-1 fingerprint: get from debug keystore:
  ```bash
  keytool -list -v -alias androiddebugkey -keystore ~/.android/debug.keystore -storepass android | grep SHA1
  ```

### Important Files

| File | Purpose |
|------|---------|
| `frontend/.env` | `VITE_API_URL` and `VITE_GOOGLE_CLIENT_ID` |
| `frontend/capacitor.config.ts` | App ID, web dir, Google Auth plugin config |
| `frontend/android/app/src/main/AndroidManifest.xml` | Permissions (INTERNET, READ_SMS) |
| `frontend/android/app/src/main/res/values/strings.xml` | `server_client_id` for Google Auth |
| `frontend/android/app/src/main/java/.../MainActivity.java` | Plugin registration |

## Release Build (for Play Store)

```bash
# 1. Create a keystore (one-time)
keytool -genkey -v -keystore moneyflow-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias moneyflow

# 2. Add signing config to android/app/build.gradle:
# (see charade-chat for reference)

# 3. Build release
./gradlew assembleRelease
# or for AAB (Play Store format):
./gradlew bundleRelease
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `invalid source release: 21` | Set `JAVA_HOME` to Java 21 |
| Google Sign-In fails | Check SHA-1 matches GCP Android client |
| CORS error on API calls | Backend needs `https://localhost` in allowed origins |
| SMS permission denied | Grant manually in Settings → Apps → MoneyFlow → Permissions |
| Play Protect blocks install | Temporarily disable Play Protect scanning |
| `capacitor-sms-inbox` peer dep error | Use `--legacy-peer-deps` flag |

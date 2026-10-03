# GemmaMobile

A clean, standalone Android application for on-device inference using **Gemma 4 E2B IT** and Google's official **LiteRT-LM** (`com.google.ai.edge.litertlm:litertlm-android:0.17.1`).

100% on-device local execution:
`Android Device -> LiteRT-LM -> Gemma 4 E2B IT -> Response`

---

## 1. Tech Stack
- **Language**: Kotlin 2.4.20
- **Build System**: Gradle 8.10.2 / AGP 8.7.3 / JDK 17
- **UI**: Jetpack Compose + Material 3
- **On-Device LLM Runtime**: LiteRT-LM Android SDK (`com.google.ai.edge.litertlm:litertlm-android:0.17.1`)
- **Model**: Gemma 4 E2B IT (`.litertlm` format, ~2.58 GB)
- **Concurrency**: Kotlin Coroutines + Flow streaming
- **Minimum SDK**: API 26+ (Android 8.0+)
- **Target SDK**: API 35 (Android 15)

---

## 2. Project Structure
```
GemmaMobile/
│
├── app/
│   ├── src/main/java/com/teja/gemmmobile/
│   │   ├── MainActivity.kt          # Compose host & Edge-to-Edge setup
│   │   │
│   │   ├── ui/
│   │   │   ├── ChatScreen.kt        # Material 3 Chat UI & Model Management Screen
│   │   │   └── ChatViewModel.kt     # ViewModel coordinating state, imports, and inference
│   │   │
│   │   ├── ai/
│   │   │   └── GemmaEngine.kt       # LiteRT-LM Engine, Conversation & GPU fallback
│   │   │
│   │   └── model/
│   │       └── ModelManager.kt      # Detection, storage validation, SAF import
│   │
│   ├── src/test/java/com/teja/gemmmobile/
│   │   └── ModelManagerTest.kt      # Unit tests for storage, formatting, and detection
│   │
│   ├── src/main/AndroidManifest.xml
│   └── build.gradle.kts
│
├── build.gradle.kts
├── settings.gradle.kts
└── gradle.properties
```

---

## 3. Official Model Acquisition

Gemma 4 E2B IT is a gated model. Google distributes the official LiteRT-LM optimized `.litertlm` package on Hugging Face:
- **Repository**: [https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)
- **Model File**: `gemma-4-E2B-it.litertlm` (~2.58 GB)

### Acquisition Procedure:
1. Log in to Hugging Face and accept the Gemma 4 terms of use.
2. Download `gemma-4-E2B-it.litertlm`.
3. Transfer the model to your Android device using **either** of the following:
   - **Method A (ADB - Recommended for developers)**:
     ```bash
     adb push gemma-4-E2B-it.litertlm /data/local/tmp/
     ```
     *GemmaMobile will automatically detect and load the model from `/data/local/tmp/`.*
   - **Method B (Device Download / SAF Import)**:
     Download the file directly on your device, launch GemmaMobile, and tap **"Download / Install Model"** to import it into app-private storage.

---

## 4. Build Commands

### Assemble Debug APK:
```bash
cd GemmaMobile
./gradlew assembleDebug
```
*Generated APK location: `app/build/outputs/apk/debug/app-debug.apk`*

### Run Unit Tests:
```bash
./gradlew test
```

---

## 5. Device Installation & Verification

When a physical Android phone or emulator is connected:
```bash
# 1. Verify device connection
adb devices

# 2. Install the debug APK
adb install -r app/build/outputs/apk/debug/app-debug.apk

# 3. Launch GemmaMobile
adb shell am start -n com.teja.gemmmobile/.MainActivity

# 4. View real-time Logcat tags:
adb logcat -s GemmaMobile
```

### Logcat Verification Signals:
- `[GemmaMobile] Initializing model`
- `[GemmaMobile] Model loaded`
- `[GemmaMobile] Backend: GPU` *(or `[GemmaMobile] GPU failed, falling back to CPU`)*
- `[GemmaMobile] Starting generation`
- `[GemmaMobile] Generation complete`

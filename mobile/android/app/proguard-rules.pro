# ProGuard / R8 rules pour build release Gathe Finance.
#
# Préserve les symboles Flutter (sinon le runtime engine crashe).
# Préserve aussi les plugins courants utilisés par l'app : local_auth,
# flutter_secure_storage, dio, etc.

# Flutter engine
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Kotlin metadata (utilisé par certains plugins natifs)
-keep class kotlin.Metadata { *; }
-keep class kotlin.reflect.** { *; }

# local_auth (BiometricPrompt + androidx.biometric)
-keep class androidx.biometric.** { *; }
-keep class androidx.fragment.app.FragmentActivity { *; }

# flutter_secure_storage (utilise Android Keystore)
-keep class io.flutter.plugins.flutter_secure_storage.** { *; }

# Dio (HTTP)
-keep class okhttp3.** { *; }
-keep class okio.** { *; }
-dontwarn okhttp3.**
-dontwarn okio.**

# Gson / réflexion sur les modèles (data classes Dart compilées en AOT
# n'ont pas besoin de cette règle mais on garde par sûreté pour les plugins).
-keepattributes Signature
-keepattributes *Annotation*

# Play Core SplitInstall / SplitCompat (référencé par Flutter mais on n'utilise pas
# les Play Feature Delivery, donc on désactive les warnings).
-dontwarn com.google.android.play.core.splitcompat.**
-dontwarn com.google.android.play.core.splitinstall.**
-dontwarn com.google.android.play.core.tasks.**

# Crash reporting prévu (Sentry / Crashlytics) à ajouter le moment venu :
# -keep class io.sentry.android.** { *; }
# -keep class com.google.firebase.crashlytics.** { *; }

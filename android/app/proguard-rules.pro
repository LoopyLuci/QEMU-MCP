# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.kts.

# Keep kotlinx-serialization classes
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep class kotlinx.serialization.json.** { *; }

# Keep model classes (they're @Serializable)
-keep class com.vmharness.android.data.model.** { *; }

# Keep OkHttp
-keepattributes Signature
-keepattributes Exceptions
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep class okio.** { *; }

# Keep Retrofit
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations

# Keep Moshi
-keep class com.squareup.moshi.** { *; }
-keep class * extends com.squareup.moshi.JsonAdapter {
    <init>(...);
}
-keepclassmembers class * {
    @com.squareup.moshi.* <methods>;
}

# Keep Koin
-keep class org.koin.** { *; }

# Keep AndroidX Security
-keep class androidx.security.crypto.** { *; }

# Keep ML Kit
-keep class com.google.mlkit.** { *; }
-dontwarn com.google.mlkit.**

# Keep CameraX
-keep class androidx.camera.** { *; }

# Keep Vico charts
-keep class com.patrykandpatrick.vico.** { *; }

# Keep data classes for API responses
-keep class com.vmharness.android.data.model.** {
    *;
}

# Keep the PairingTokenVerifier (uses reflection for JsonReader)
-keep class com.vmharness.android.data.auth.PairingTokenVerifier { *; }

# Android manifest references
-keep class com.vmharness.android.ui.MainActivity { *; }
-keep class com.vmharness.android.QEMU-MCPAndroidApp { *; }

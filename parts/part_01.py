import pathlib

ROOT = pathlib.Path("AERO_SHARE")
FILES = {}
K = "app/src/main/java/com/aero/share/"
T = "app/src/test/java/com/aero/share/"

def add(p, c):
    FILES[p] = c.strip("\n") + "\n"

def icon(name, path):
    add(f"app/src/main/res/drawable/{name}.xml",
        '<vector xmlns:android="http://schemas.android.com/apk/res/android" '
        'android:width="24dp" android:height="24dp" android:viewportWidth="24" '
        'android:viewportHeight="24" android:tint="#FF7900">'
        f'<path android:fillColor="#FFFFFFFF" android:pathData="{path}" /></vector>')

add("settings.gradle.kts", r'''
pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "AERO SHARE"
include(":app")
''')

add("build.gradle.kts", r'''
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
}
''')

add("gradle.properties", r'''
org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
android.useAndroidX=true
android.nonTransitiveRClass=true
kotlin.code.style=official
kotlin.compiler.execution.strategy=in-process
''')

add(".gitignore", r'''
.gradle/
build/
local.properties
.idea/
*.iml
''')

add("gradle/libs.versions.toml", r'''
[versions]
agp = "8.7.3"
kotlin = "2.0.21"
ksp = "2.0.21-1.0.28"
core = "1.15.0"
lifecycle = "2.8.7"
activity = "1.9.3"
composeBom = "2024.12.01"
nav = "2.8.5"
room = "2.6.1"
datastore = "1.1.1"
coil = "2.7.0"
camerax = "1.4.1"
zxing = "3.5.3"
bc = "1.79"
appcompat = "1.7.0"
serialization = "1.7.3"
coroutines = "1.9.0"
documentfile = "1.0.1"
junit = "4.13.2"

[libraries]
core-ktx = { module = "androidx.core:core-ktx", version.ref = "core" }
appcompat = { module = "androidx.appcompat:appcompat", version.ref = "appcompat" }
activity-compose = { module = "androidx.activity:activity-compose", version.ref = "activity" }
lifecycle-runtime-compose = { module = "androidx.lifecycle:lifecycle-runtime-compose", version.ref = "lifecycle" }
lifecycle-viewmodel-compose = { module = "androidx.lifecycle:lifecycle-viewmodel-compose", version.ref = "lifecycle" }
lifecycle-process = { module = "androidx.lifecycle:lifecycle-process", version.ref = "lifecycle" }
compose-bom = { module = "androidx.compose:compose-bom", version.ref = "composeBom" }
compose-ui = { module = "androidx.compose.ui:ui" }
compose-foundation = { module = "androidx.compose.foundation:foundation" }
compose-material3 = { module = "androidx.compose.material3:material3" }
compose-ui-tooling = { module = "androidx.compose.ui:ui-tooling" }
navigation-compose = { module = "androidx.navigation:navigation-compose", version.ref = "nav" }
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-ktx = { module = "androidx.room:room-ktx", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }
datastore-preferences = { module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }
coil-compose = { module = "io.coil-kt:coil-compose", version.ref = "coil" }
camera-core = { module = "androidx.camera:camera-core", version.ref = "camerax" }
camera-camera2 = { module = "androidx.camera:camera-camera2", version.ref = "camerax" }
camera-lifecycle = { module = "androidx.camera:camera-lifecycle", version.ref = "camerax" }
camera-view = { module = "androidx.camera:camera-view", version.ref = "camerax" }
zxing-core = { module = "com.google.zxing:core", version.ref = "zxing" }
bcpkix = { module = "org.bouncycastle:bcpkix-jdk18on", version.ref = "bc" }
serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "serialization" }
coroutines-android = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-android", version.ref = "coroutines" }
coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "coroutines" }
documentfile = { module = "androidx.documentfile:documentfile", version.ref = "documentfile" }
junit = { module = "junit:junit", version.ref = "junit" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
''')

add("app/build.gradle.kts", r'''
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.aero.share"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.aero.share"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        vectorDrawables.useSupportLibrary = true
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true; buildConfig = true }
    packaging {
        resources.excludes += setOf(
            "META-INF/DEPENDENCIES", "META-INF/LICENSE*", "META-INF/NOTICE*",
            "META-INF/versions/**", "META-INF/*.kotlin_module"
        )
    }
}

kotlin { compilerOptions { jvmTarget.set(JvmTarget.JVM_17) } }

dependencies {
    implementation(libs.core.ktx)
    implementation(libs.appcompat)
    implementation(libs.activity.compose)
    implementation(libs.lifecycle.runtime.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.process)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.navigation.compose)
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    implementation(libs.datastore.preferences)
    implementation(libs.coil.compose)
    implementation(libs.camera.core)
    implementation(libs.camera.camera2)
    implementation(libs.camera.lifecycle)
    implementation(libs.camera.view)
    implementation(libs.zxing.core)
    implementation(libs.bcpkix)
    implementation(libs.serialization.json)
    implementation(libs.coroutines.android)
    implementation(libs.documentfile)
    testImplementation(libs.junit)
    testImplementation(libs.coroutines.test)
}
''')

add("app/proguard-rules.pro", r'''
-dontwarn org.bouncycastle.**
-dontwarn javax.naming.**
''')

add("app/src/main/AndroidManifest.xml", r'''
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="28" />
    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
    <uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
    <uses-permission android:name="android.permission.READ_MEDIA_VISUAL_USER_SELECTED" />
    <uses-feature android:name="android.hardware.camera" android:required="false" />
    <uses-feature android:name="android.hardware.wifi" android:required="false" />
    <queries>
        <intent>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent>
    </queries>
    <application
        android:name=".AeroApp"
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:allowBackup="false"
        android:supportsRtl="true"
        android:usesCleartextTraffic="false"
        android:enableOnBackInvokedCallback="true"
        android:localeConfig="@xml/locales_config"
        android:theme="@style/Theme.Aero">
        <activity android:name=".MainActivity" android:exported="true" android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <service android:name=".service.TransferService" android:exported="false" android:foregroundServiceType="dataSync" />
        <provider android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.files"
            android:exported="false" android:grantUriPermissions="true">
            <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/file_paths" />
        </provider>
        <service android:name="androidx.appcompat.app.AppLocalesMetadataHolderService"
            android:enabled="false" android:exported="false">
            <meta-data android:name="autoStoreLocales" android:value="true" />
        </service>
    </application>
</manifest>
''')

add("app/src/main/res/values/themes.xml", r'''
<resources>
    <style name="Theme.Aero" parent="Theme.AppCompat.DayNight.NoActionBar">
        <item name="android:windowBackground">@color/aero_bg</item>
        <item name="android:statusBarColor">@android:color/transparent</item>
        <item name="android:navigationBarColor">@android:color/transparent</item>
    </style>
</resources>
''')

add("app/src/main/res/values/colors.xml", r'''
<resources><color name="aero_bg">#F6F6F6</color><color name="aero_icon_bg">#090909</color></resources>
''')

add("app/src/main/res/values-night/colors.xml", r'''
<resources><color name="aero_bg">#090909</color></resources>
''')

add("app/src/main/res/xml/locales_config.xml", r'''
<locale-config xmlns:android="http://schemas.android.com/apk/res/android">
    <locale android:name="en" /><locale android:name="uk" /><locale android:name="ru" />
</locale-config>
''')

add("app/src/main/res/xml/file_paths.xml", r'''
<paths>
    <files-path name="files" path="." />
    <cache-path name="cache" path="." />
    <external-path name="downloads" path="Download/" />
</paths>
''')

add("app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml", r'''
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/aero_icon_bg" />
    <foreground android:drawable="@drawable/ic_logo" />
</adaptive-icon>
''')

icon("ic_logo", "M12,3 L21,20 L12,15.6 L3,20 Z")
icon("ic_device", "M7,2 h10 a2,2 0 0 1 2,2 v16 a2,2 0 0 1 -2,2 h-10 a2,2 0 0 1 -2,-2 v-16 a2,2 0 0 1 2,-2 z M7,5 v13 h10 v-13 z")
icon("ic_devices", "M2,5 h14 v3 h-11 v7 h6 v3 h-9 z M17,9 h5 v11 h-5 z M19,11 v7 h1 v-7 z")
icon("ic_receive", "M12,3 v10 M7,9 l5,5 5,-5 M4,17 h16 v3 h-16 z")
icon("ic_folder", "M3,5 h6 l2,2 h10 v12 h-18 z")
icon("ic_file", "M6,2 h9 l5,5 v15 h-14 z M14,3 v5 h5")
icon("ic_image", "M3,4 h18 v16 h-18 z M6,16 l4,-5 3,3 2,-2 3,4")
icon("ic_video", "M3,5 h13 v14 h-13 z M17,9 l4,-3 v12 l-4,-3 z")
icon("ic_audio", "M9,3 v12.5 a3.5,3.5 0 1 0 2,3.16 v-11.66 h7 v-4 z")
icon("ic_doc", "M6,2 h9 l5,5 v15 h-14 z M8,12 h8 v1.6 h-8 z M8,16 h8 v1.6 h-8 z")
icon("ic_apk", "M7,4 a5,5 0 0 1 10,0 z M6,7 h12 v10 a2,2 0 0 1 -2,2 h-8 a2,2 0 0 1 -2,-2 z")
icon("ic_qr", "M3,3 h7 v7 h-7 z M5,5 v3 h3 v-3 z M14,3 h7 v7 h-7 z M16,5 v3 h3 v-3 z M3,14 h7 v7 h-7 z M5,16 v3 h3 v-3 z M14,14 h3 v3 h-3 z M18,18 h3 v3 h-3 z")
icon("ic_history", "M12,2 a10,10 0 1 1 -9.5,7 h2.2 a8,8 0 1 0 7.3,-5 v3 l-5,-4 5,-4 v3 z M11,7 h2 v5.4 l3.6,2.1 -1,1.7 -4.6,-2.7 z")
icon("ic_wifi", "M12,19.5 a1.8,1.8 0 1 0 0.01,0 z M4,10 a12,12 0 0 1 16,0 l-2,2 a9,9 0 0 0 -12,0 z M7.5,13.5 a7,7 0 0 1 9,0 l-2,2 a4,4 0 0 0 -5,0 z")
icon("ic_pause", "M6,4 h4 v16 h-4 z M14,4 h4 v16 h-4 z")
icon("ic_play", "M7,4 l13,8 -13,8 z")
icon("ic_shield", "M12,2 l9,4 v6 c0,5 -4,9 -9,10 c-5,-1 -9,-5 -9,-10 v-6 z M10.5,15.5 l-3,-3 1.4,-1.4 1.6,1.6 4.6,-4.6 1.4,1.4 z")
icon("ic_download", "M12,3 v10 M7,9 l5,5 5,-5 M4,19 h16 v2 h-16 z")
icon("ic_link", "M8,11 a4,4 0 0 1 4,-4 h3 v2 h-3 a2,2 0 0 0 0,4 h3 v2 h-3 a4,4 0 0 1 -4,-4 z M2,11 a4,4 0 0 1 4,-4 h3 v2 h-3 a2,2 0 0 0 0,4 h3 v2 h-3 a4,4 0 0 1 -4,-4 z")

# END PART 01/8
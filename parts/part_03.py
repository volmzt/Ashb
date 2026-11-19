add(K + "core/Hash.kt", r'''
package com.aero.share.core

import java.io.InputStream
import java.security.MessageDigest

object Hash {
    fun hex(b: ByteArray): String = b.joinToString("") { "%02x".format(it) }
    fun sha256Hex(bytes: ByteArray): String = hex(MessageDigest.getInstance("SHA-256").digest(bytes))
    fun stream(input: InputStream, buf: ByteArray, onChunk: (Int) -> Unit = {}): String {
        val md = MessageDigest.getInstance("SHA-256")
        while (true) {
            val n = input.read(buf)
            if (n < 0) break
            md.update(buf, 0, n)
            onChunk(n)
        }
        return hex(md.digest())
    }
}
''')

add(K + "core/Formats.kt", r'''
package com.aero.share.core

import java.util.Locale

object Formats {
    fun bytes(v: Long): String {
        if (v < 1024) return "$v B"
        val units = arrayOf("KB", "MB", "GB", "TB")
        var d = v.toDouble() / 1024.0
        var i = 0
        while (d >= 1024 && i < units.lastIndex) { d /= 1024.0; i++ }
        return String.format(Locale.US, "%.1f %s", d, units[i])
    }
    fun speed(bps: Long): String = bytes(bps) + "/s"
    fun duration(ms: Long): String {
        val s = ms / 1000
        val h = s / 3600; val m = (s % 3600) / 60; val sec = s % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, sec) else "%d:%02d".format(m, sec)
    }
    fun fpShort(fpHex: String): String = fpHex.take(16).uppercase().chunked(2).joinToString(":")
}
''')

add(K + "core/PathGuard.kt", r'''
package com.aero.share.core

object PathGuard {
    private val badChars = Regex("[\u0000-\u001f<>:\"|?*]")
    fun sanitizeRelative(path: String): String? {
        if (path.isBlank() || path.length > 512) return null
        val norm = path.replace('\\', '/')
        if (norm.startsWith("/") || norm.contains(":")) return null
        val parts = norm.split('/').filter { it.isNotEmpty() && it != "." }
        if (parts.isEmpty()) return null
        if (parts.any { it == ".." || badChars.containsMatchIn(it) || it.length > 200 }) return null
        return parts.joinToString("/")
    }
    fun uniqueName(name: String, taken: Set<String>): String {
        if (name !in taken) return name
        val dot = name.lastIndexOf('.')
        val base = if (dot > 0) name.substring(0, dot) else name
        val ext = if (dot > 0) name.substring(dot) else ""
        var i = 1
        while ("$base ($i)$ext" in taken) i++
        return "$base ($i)$ext"
    }
}
''')

add(K + "core/Identity.kt", r'''
package com.aero.share.core

import android.content.Context
import android.os.Build
import java.util.UUID

class Identity(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("aero_identity", Context.MODE_PRIVATE)
    val id: String = prefs.getString("id", null) ?: UUID.randomUUID().toString().also {
        prefs.edit().putString("id", it).apply()
    }
    val model: String = Build.MODEL ?: "Android"
    fun name(custom: String): String = custom.ifBlank { model }
}
''')

add(K + "core/Feedback.kt", r'''
package com.aero.share.core

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Handler
import android.os.Looper
import com.aero.share.data.AppSettings

object Feedback {
    private fun tone(kind: Int) = runCatching {
        val tg = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 70)
        tg.startTone(kind, 140)
        Handler(Looper.getMainLooper()).postDelayed({ tg.release() }, 250)
    }
    fun success(ctx: Context, s: AppSettings) { if (s.sound) tone(ToneGenerator.TONE_PROP_ACK) }
    fun failure(ctx: Context, s: AppSettings) { if (s.sound) tone(ToneGenerator.TONE_PROP_NACK) }
}
''')

add(K + "data/Settings.kt", r'''
package com.aero.share.data

import android.content.Context
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException

enum class ThemeMode { SYSTEM, DARK, LIGHT }
enum class PowerMode { BALANCED, PERFORMANCE, SAVING }
enum class ConflictMode { RENAME, SKIP }

data class AppSettings(
    val onboarded: Boolean = false,
    val theme: ThemeMode = ThemeMode.SYSTEM,
    val accent: String = "orange",
    val language: String = "",
    val deviceName: String = "",
    val visible: Boolean = true,
    val startupDiscovery: Boolean = true,
    val receiveTreeUri: String = "",
    val notifications: Boolean = true,
    val progressNotif: Boolean = true,
    val autoAcceptTrusted: Boolean = false,
    val power: PowerMode = PowerMode.BALANCED,
    val animations: Boolean = true,
    val haptics: Boolean = true,
    val sound: Boolean = true,
    val glass: Boolean = false,
    val timeoutSec: Int = 10,
    val qrTtlMin: Int = 5,
    val conflict: ConflictMode = ConflictMode.RENAME,
    val cleanupTemp: Boolean = true,
    val warnLarge: Boolean = true
) {
    fun chunkSize(): Int = when (power) {
        PowerMode.PERFORMANCE -> 1 shl 20
        PowerMode.BALANCED -> 256 * 1024
        PowerMode.SAVING -> 64 * 1024
    }
}

private val Context.ds by preferencesDataStore("aero_settings")

class SettingsStore(private val ctx: Context) {
    private object Keys {
        val ONB = booleanPreferencesKey("onb")
        val THEME = stringPreferencesKey("theme")
        val ACCENT = stringPreferencesKey("accent")
        val LANG = stringPreferencesKey("lang")
        val NAME = stringPreferencesKey("name")
        val VIS = booleanPreferencesKey("vis")
        val START = booleanPreferencesKey("start")
        val TREE = stringPreferencesKey("tree")
        val NOTIF = booleanPreferencesKey("notif")
        val PNOTIF = booleanPreferencesKey("pnotif")
        val AUTO = booleanPreferencesKey("auto")
        val POWER = stringPreferencesKey("power")
        val ANIM = booleanPreferencesKey("anim")
        val HAP = booleanPreferencesKey("hap")
        val SND = booleanPreferencesKey("snd")
        val GLASS = booleanPreferencesKey("glass")
        val TMO = intPreferencesKey("tmo")
        val TTL = intPreferencesKey("ttl")
        val CONF = stringPreferencesKey("conf")
        val CLEAN = booleanPreferencesKey("clean")
        val WARN = booleanPreferencesKey("warn")
    }
    val flow: Flow<AppSettings> = ctx.ds.data.catch { e ->
        if (e is IOException) emit(emptyPreferences()) else throw e
    }.map { p ->
        AppSettings(
            onboarded = p[Keys.ONB] ?: false,
            theme = runCatching { ThemeMode.valueOf(p[Keys.THEME] ?: "SYSTEM") }.getOrDefault(ThemeMode.SYSTEM),
            accent = p[Keys.ACCENT] ?: "orange",
            language = p[Keys.LANG] ?: "",
            deviceName = p[Keys.NAME] ?: "",
            visible = p[Keys.VIS] ?: true,
            startupDiscovery = p[Keys.START] ?: true,
            receiveTreeUri = p[Keys.TREE] ?: "",
            notifications = p[Keys.NOTIF] ?: true,
            progressNotif = p[Keys.PNOTIF] ?: true,
            autoAcceptTrusted = p[Keys.AUTO] ?: false,
            power = runCatching { PowerMode.valueOf(p[Keys.POWER] ?: "BALANCED") }.getOrDefault(PowerMode.BALANCED),
            animations = p[Keys.ANIM] ?: true,
            haptics = p[Keys.HAP] ?: true,
            sound = p[Keys.SND] ?: true,
            glass = p[Keys.GLASS] ?: false,
            timeoutSec = p[Keys.TMO] ?: 10,
            qrTtlMin = p[Keys.TTL] ?: 5,
            conflict = runCatching { ConflictMode.valueOf(p[Keys.CONF] ?: "RENAME") }.getOrDefault(ConflictMode.RENAME),
            cleanupTemp = p[Keys.CLEAN] ?: true,
            warnLarge = p[Keys.WARN] ?: true
        )
    }
    private suspend fun edit(block: (MutablePreferences) -> Unit) { ctx.ds.edit { block(it) } }
    suspend fun setOnboarded() = edit { it[Keys.ONB] = true }
    suspend fun setTheme(v: ThemeMode) = edit { it[Keys.THEME] = v.name }
    suspend fun setAccent(v: String) = edit { it[Keys.ACCENT] = v }
    suspend fun setLanguage(v: String) = edit { it[Keys.LANG] = v }
    suspend fun setDeviceName(v: String) = edit { it[Keys.NAME] = v.trim().take(40) }
    suspend fun setVisible(v: Boolean) = edit { it[Keys.VIS] = v }
    suspend fun setStartupDiscovery(v: Boolean) = edit { it[Keys.START] = v }
    suspend fun setTree(v: String) = edit { it[Keys.TREE] = v }
    suspend fun setNotifications(v: Boolean) = edit { it[Keys.NOTIF] = v }
    suspend fun setProgressNotif(v: Boolean) = edit { it[Keys.PNOTIF] = v }
    suspend fun setAutoAccept(v: Boolean) = edit { it[Keys.AUTO] = v }
    suspend fun setPower(v: PowerMode) = edit { it[Keys.POWER] = v.name }
    suspend fun setAnimations(v: Boolean) = edit { it[Keys.ANIM] = v }
    suspend fun setHaptics(v: Boolean) = edit { it[Keys.HAP] = v }
    suspend fun setSound(v: Boolean) = edit { it[Keys.SND] = v }
    suspend fun setGlass(v: Boolean) = edit { it[Keys.GLASS] = v }
    suspend fun setTimeout(v: Int) = edit { it[Keys.TMO] = v }
    suspend fun setQrTtl(v: Int) = edit { it[Keys.TTL] = v }
    suspend fun setConflict(v: ConflictMode) = edit { it[Keys.CONF] = v.name }
    suspend fun setCleanup(v: Boolean) = edit { it[Keys.CLEAN] = v }
    suspend fun setWarnLarge(v: Boolean) = edit { it[Keys.WARN] = v }
}
''')

add(K + "data/Db.kt", r'''
package com.aero.share.data

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "devices")
data class DeviceEntity(
    @PrimaryKey val fp: String,
    val id: String,
    val name: String,
    val model: String,
    val alias: String = "",
    val trusted: Boolean = false,
    val blocked: Boolean = false,
    val firstSeen: Long = System.currentTimeMillis(),
    val lastSeen: Long = System.currentTimeMillis()
) { fun display(): String = alias.ifBlank { name } }

@Entity(tableName = "history")
data class HistoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val ts: Long,
    val direction: String,
    val peer: String,
    val files: Int,
    val bytes: Long,
    val durationMs: Long,
    val status: String,
    val urisJson: String = "[]"
)

@Dao interface DeviceDao {
    @Query("SELECT * FROM devices ORDER BY lastSeen DESC") fun all(): Flow<List<DeviceEntity>>
    @Query("SELECT * FROM devices WHERE fp = :fp") suspend fun byFp(fp: String): DeviceEntity?
    @Upsert suspend fun upsert(d: DeviceEntity)
    @Query("DELETE FROM devices WHERE fp = :fp") suspend fun delete(fp: String)
}

@Dao interface HistoryDao {
    @Query("SELECT * FROM history ORDER BY ts DESC LIMIT 500") fun all(): Flow<List<HistoryEntity>>
    @Insert suspend fun insert(h: HistoryEntity)
    @Query("DELETE FROM history") suspend fun clear()
}

@Database(entities = [DeviceEntity::class, HistoryEntity::class], version = 1, exportSchema = false)
abstract class AeroDb : RoomDatabase() {
    abstract fun devices(): DeviceDao
    abstract fun history(): HistoryDao
    companion object {
        fun build(ctx: Context): AeroDb = Room.databaseBuilder(ctx, AeroDb::class.java, "aero.db").build()
    }
}

class DeviceRepo(private val dao: DeviceDao) {
    val all: Flow<List<DeviceEntity>> = dao.all()
    suspend fun byFp(fp: String) = dao.byFp(fp)
    suspend fun upsert(d: DeviceEntity) = dao.upsert(d)
    suspend fun delete(fp: String) = dao.delete(fp)
    suspend fun touch(fp: String, id: String, name: String, model: String) {
        val old = dao.byFp(fp)
        dao.upsert(old?.copy(lastSeen = System.currentTimeMillis(), name = name, model = model)
            ?: DeviceEntity(fp = fp, id = id, name = name, model = model))
    }
}

class HistoryRepo(private val dao: HistoryDao) {
    val all: Flow<List<HistoryEntity>> = dao.all()
    suspend fun add(h: HistoryEntity) = dao.insert(h)
    suspend fun clear() = dao.clear()
}
''')

# END PART 03/8
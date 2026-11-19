add(K + "ui/screens/Devices.kt", r'''
package com.aero.share.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.data.DeviceEntity
import com.aero.share.net.Target
import com.aero.share.ui.*
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

@Composable
fun Devices(app: AeroApp, nav: NavController) {
    val c = aero(); val scope = rememberCoroutineScope()
    val known by app.devices.all.collectAsStateWithLifecycle(initialValue = emptyList())
    val found by app.discovery.devices.collectAsStateWithLifecycle()
    var sel by remember { mutableStateOf<DeviceEntity?>(null) }
    var alias by remember { mutableStateOf("") }
    val df = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        item { Text(stringResource(R.string.known_devices), color = c.text, fontWeight = FontWeight.Bold, fontSize = 22.sp, modifier = Modifier.padding(vertical = 16.dp)) }
        if (known.isEmpty()) item { EmptyState(R.drawable.ic_devices, stringResource(R.string.no_devices), stringResource(R.string.empty_devices)) }
        items(known, key = { it.fp }) { d ->
            val online = found.any { it.id == d.id }
            AeroCard(Modifier.fillMaxWidth().padding(vertical = 4.dp).then(AeroClick { sel = d; alias = d.alias })) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(R.drawable.ic_device), null, tint = if (online) c.accent else c.text2, modifier = Modifier.size(26.dp))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(d.display(), color = c.text, fontWeight = FontWeight.SemiBold)
                        Text(d.model + (if (d.trusted) " · " + stringResource(R.string.trusted) else "") + (if (d.blocked) " · " + stringResource(R.string.blocked) else ""), color = c.text2, fontSize = 12.sp)
                    }
                    StatusChip(stringResource(if (online) R.string.active else R.string.inactive), online)
                }
            }
        }
    }
    sel?.let { d ->
        val online = found.find { it.id == d.id }
        AeroDialog(d.display(), body = {
            Text("${stringResource(R.string.model)}: ${d.model}")
            Text("${stringResource(R.string.first_seen)}: ${df.format(Date(d.firstSeen))}")
            Text("${stringResource(R.string.last_seen)}: ${df.format(Date(d.lastSeen))}")
            Text(Formats.fpShort(d.fp), fontSize = 12.sp)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(alias, { alias = it }, label = { Text(stringResource(R.string.rename)) }, singleLine = true)
            SwitchRow(stringResource(R.string.trust_device), d.trusted) { v -> scope.launch { app.devices.upsert(d.copy(trusted = v)) }; sel = d.copy(trusted = v) }
            SwitchRow(stringResource(R.string.block), d.blocked) { v -> scope.launch { app.devices.upsert(d.copy(blocked = v)) }; sel = d.copy(blocked = v) }
            Row {
                AeroButton(stringResource(R.string.remove), primary = false) { scope.launch { app.devices.delete(d.fp) }; sel = null }
                if (online != null) {
                    Spacer(Modifier.width(8.dp))
                    AeroButton(stringResource(R.string.send)) { app.pendingTarget = Target(online.host, online.port, null, null, d.display()); sel = null; nav.navigate("send") }
                }
            }
        }, confirm = stringResource(R.string.ok), onConfirm = { scope.launch { app.devices.upsert(d.copy(alias = alias.trim())) }; sel = null },
            dismiss = stringResource(R.string.close), onDismiss = { sel = null })
    }
}
''')

add(K + "ui/screens/History.kt", r'''
package com.aero.share.ui.screens

import android.app.DownloadManager
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.ui.*
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

@Composable
fun History(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    val all by app.history.all.collectAsStateWithLifecycle(initialValue = emptyList())
    var filter by remember { mutableStateOf("all") }
    val filters = listOf("all" to R.string.filter_all, "Send" to R.string.filter_sent, "Receive" to R.string.filter_received,
        "Completed" to R.string.filter_completed, "Failed" to R.string.filter_failed, "Cancelled" to R.string.filter_cancelled)
    val shown = all.filter { when (filter) { "all" -> true; "Send", "Receive" -> it.direction == filter; "Failed" -> it.status == "Failed" || it.status == "Interrupted"; else -> it.status == filter } }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.history), color = c.text, fontWeight = FontWeight.Bold, fontSize = 22.sp, modifier = Modifier.weight(1f))
            if (all.isNotEmpty()) AeroButton(stringResource(R.string.clear_history), primary = false) { scope.launch { app.history.clear() } }
        }
        Spacer(Modifier.height(8.dp))
        LazyRow { items(filters) { (k, label) ->
            val s = filter == k
            Box(Modifier.padding(end = 6.dp).clip(RoundedCornerShape(10.dp)).background(if (s) c.accent else c.surface2)
                .then(AeroClick { filter = k }).padding(horizontal = 12.dp, vertical = 7.dp)) {
                Text(stringResource(label), color = if (s) Color.Black else c.text2, fontSize = 12.sp)
            }
        } }
        Spacer(Modifier.height(8.dp))
        if (shown.isEmpty()) EmptyState(R.drawable.ic_history, stringResource(R.string.empty_history), "")
        LazyColumn {
            items(shown, key = { it.id }) { h ->
                AeroCard(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(painterResource(if (h.direction == "Send") R.drawable.ic_logo else R.drawable.ic_receive), null,
                            tint = if (h.status == "Completed") c.accent else c.text2, modifier = Modifier.size(24.dp))
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(h.peer, color = c.text, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                            Text("${stringResource(R.string.files_label, h.files)} · ${Formats.bytes(h.bytes)} · ${Formats.duration(h.durationMs)}", color = c.text2, fontSize = 12.sp)
                            Text(DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(h.ts)), color = c.text2, fontSize = 11.sp)
                        }
                        val st = when (h.status) { "Completed" -> R.string.st_completed; "Failed" -> R.string.st_failed; "Cancelled" -> R.string.st_cancelled; "Interrupted" -> R.string.st_interrupted; "Paused" -> R.string.st_paused; else -> R.string.st_waiting }
                        Text(stringResource(st), color = if (h.status == "Completed") c.success else c.text2, fontSize = 11.sp)
                    }
                }
            }
            if (shown.any { it.direction == "Receive" && it.status == "Completed" }) item {
                Spacer(Modifier.height(8.dp))
                AeroButton(stringResource(R.string.open_folder), primary = false) { runCatching { ctx.startActivity(Intent(DownloadManager.ACTION_VIEW_DOWNLOADS)) } }
            }
        }
    }
}
''')

add(K + "ui/screens/Settings.kt", r'''
package com.aero.share.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.BuildConfig
import com.aero.share.R
import com.aero.share.data.ConflictMode
import com.aero.share.data.PowerMode
import com.aero.share.data.ThemeMode
import com.aero.share.ui.*
import kotlinx.coroutines.launch

private fun langLabel(t: String) = when (t) { "en" -> "English"; "uk" -> "Українська"; "ru" -> "Русский"; else -> "" }

@Composable
fun Settings(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    val s by app.settings.flow.collectAsStateWithLifecycle(initialValue = app.settingsNow)
    var dialog by remember { mutableStateOf<String?>(null) }
    var nameText by remember(s.deviceName) { mutableStateOf(s.deviceName) }
    val tree = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { u ->
        if (u != null) {
            runCatching { ctx.contentResolver.takePersistableUriPermission(u, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION) }
            scope.launch { app.settings.setTree(u.toString()) }
        }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text(stringResource(R.string.nav_settings), color = c.text, fontWeight = FontWeight.Bold, fontSize = 22.sp, modifier = Modifier.padding(vertical = 12.dp))
        SectionTitle(stringResource(R.string.sec_general))
        AeroCard(Modifier.fillMaxWidth()) {
            ClickRow(stringResource(R.string.language), if (s.language.isEmpty()) stringResource(R.string.lang_system) else langLabel(s.language)) { dialog = "lang" }
            ClickRow(stringResource(R.string.device_name), app.identity.name(s.deviceName)) { dialog = "name" }
            SwitchRow(stringResource(R.string.startup_discovery), s.startupDiscovery) { v -> scope.launch { app.settings.setStartupDiscovery(v) } }
            ClickRow(stringResource(R.string.receive_dir), app.store.destLabel(s.receiveTreeUri)) { tree.launch(null) }
            if (s.receiveTreeUri.isNotEmpty()) ClickRow(stringResource(R.string.reset), stringResource(R.string.default_dir)) { scope.launch { app.settings.setTree("") } }
            SwitchRow(stringResource(R.string.notifications), s.notifications) { v -> scope.launch { app.settings.setNotifications(v) } }
            SwitchRow(stringResource(R.string.progress_notif), s.progressNotif) { v -> scope.launch { app.settings.setProgressNotif(v) } }
        }
        SectionTitle(stringResource(R.string.sec_connections))
        AeroCard(Modifier.fillMaxWidth()) {
            SwitchRow(stringResource(R.string.visibility), s.visible, stringResource(R.string.visibility_hint)) { v -> scope.launch { app.settings.setVisible(v) } }
            ClickRow(stringResource(R.string.timeout), stringResource(R.string.seconds, s.timeoutSec)) { dialog = "timeout" }
            ClickRow(stringResource(R.string.qr_ttl), stringResource(R.string.minutes, s.qrTtlMin)) { dialog = "ttl" }
            Text(stringResource(R.string.roadmap_note), color = c.text2, fontSize = 12.sp)
        }
        SectionTitle(stringResource(R.string.sec_transfers))
        AeroCard(Modifier.fillMaxWidth()) {
            SwitchRow(stringResource(R.string.auto_accept_trusted), s.autoAcceptTrusted, stringResource(R.string.auto_accept_hint)) { v -> scope.launch { app.settings.setAutoAccept(v) } }
            ClickRow(stringResource(R.string.conflict), stringResource(if (s.conflict == ConflictMode.RENAME) R.string.conflict_rename else R.string.conflict_skip)) { dialog = "conflict" }
            SwitchRow(stringResource(R.string.warn_large), s.warnLarge) { v -> scope.launch { app.settings.setWarnLarge(v) } }
            SwitchRow(stringResource(R.string.cleanup_temp), s.cleanupTemp) { v -> scope.launch { app.settings.setCleanup(v) } }
        }
        SectionTitle(stringResource(R.string.sec_power))
        AeroCard(Modifier.fillMaxWidth()) {
            listOf(Triple(PowerMode.BALANCED, R.string.power_balanced, R.string.power_balanced_desc),
                Triple(PowerMode.PERFORMANCE, R.string.power_performance, R.string.power_performance_desc),
                Triple(PowerMode.SAVING, R.string.power_saving, R.string.power_saving_desc)).forEach { (m, l, d) ->
                Row(Modifier.fillMaxWidth().then(AeroClick { scope.launch { app.settings.setPower(m) } }).padding(vertical = 6.dp)) {
                    RadioButton(selected = s.power == m, onClick = { scope.launch { app.settings.setPower(m) } }, colors = RadioButtonDefaults.colors(selectedColor = c.accent))
                    Column { Text(stringResource(l), color = c.text, fontSize = 15.sp); Text(stringResource(d), color = c.text2, fontSize = 12.sp) }
                }
            }
        }
        SectionTitle(stringResource(R.string.sec_appearance))
        AeroCard(Modifier.fillMaxWidth()) {
            ClickRow(stringResource(R.string.theme), stringResource(when (s.theme) { ThemeMode.SYSTEM -> R.string.theme_system; ThemeMode.DARK -> R.string.theme_dark; ThemeMode.LIGHT -> R.string.theme_light })) { dialog = "theme" }
            ClickRow(stringResource(R.string.accent), stringResource(when (s.accent) { "amber" -> R.string.accent_amber; "coral" -> R.string.accent_coral; "mint" -> R.string.accent_mint; else -> R.string.accent_orange })) { dialog = "accent" }
            SwitchRow(stringResource(R.string.animations), s.animations) { v -> scope.launch { app.settings.setAnimations(v) } }
            SwitchRow(stringResource(R.string.haptics), s.haptics) { v -> scope.launch { app.settings.setHaptics(v) } }
            SwitchRow(stringResource(R.string.sound), s.sound) { v -> scope.launch { app.settings.setSound(v) } }
            SwitchRow(stringResource(R.string.glass), s.glass) { v -> scope.launch { app.settings.setGlass(v) } }
        }
        SectionTitle(stringResource(R.string.sec_security))
        AeroCard(Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.security_info), color = c.text2, fontSize = 13.sp)
            ClickRow(stringResource(R.string.nav_devices), "") { nav.navigate("devices") }
        }
        SectionTitle(stringResource(R.string.sec_diagnostics))
        AeroCard(Modifier.fillMaxWidth().then(AeroClick { nav.navigate("diagnostics") })) { Text(stringResource(R.string.sec_diagnostics), color = c.text) }
        SectionTitle(stringResource(R.string.sec_about))
        AeroCard(Modifier.fillMaxWidth()) {
            Row {
                Icon(painterResource(R.drawable.ic_logo), null, tint = c.accent, modifier = Modifier.size(40.dp))
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(stringResource(R.string.app_name), color = c.text, fontWeight = FontWeight.Bold)
                    Text("${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})", color = c.text2, fontSize = 12.sp)
                    Text(stringResource(R.string.developer), color = c.text2, fontSize = 12.sp)
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(stringResource(R.string.about_desc), color = c.text2, fontSize = 13.sp)
            Text(stringResource(R.string.privacy_note), color = c.text2, fontSize = 12.sp)
            Text(stringResource(R.string.licenses), color = c.text2, fontSize = 11.sp)
        }
        Spacer(Modifier.height(24.dp))
    }
    when (dialog) {
        "lang" -> AeroDialog(stringResource(R.string.language), body = {
            listOf("", "en", "uk", "ru").forEach { t ->
                ClickRow(if (t.isEmpty()) stringResource(R.string.lang_system) else langLabel(t), if (s.language == t) "✓" else null) {
                    scope.launch { app.settings.setLanguage(t) }
                    AppCompatDelegate.setApplicationLocales(if (t.isEmpty()) LocaleListCompat.getEmptyLocaleList() else LocaleListCompat.forLanguageTags(t))
                    dialog = null
                }
            }
        }, confirm = stringResource(R.string.close), onConfirm = { dialog = null })
        "name" -> AeroDialog(stringResource(R.string.device_name), body = { OutlinedTextField(nameText, { nameText = it }, singleLine = true, label = { Text(app.identity.model) }) },
            confirm = stringResource(R.string.ok), onConfirm = { scope.launch { app.settings.setDeviceName(nameText) }; dialog = null }, dismiss = stringResource(R.string.cancel), onDismiss = { dialog = null })
        "theme" -> AeroDialog(stringResource(R.string.theme), body = {
            listOf(ThemeMode.SYSTEM to R.string.theme_system, ThemeMode.DARK to R.string.theme_dark, ThemeMode.LIGHT to R.string.theme_light).forEach { (m, l) ->
                ClickRow(stringResource(l), if (s.theme == m) "✓" else null) { scope.launch { app.settings.setTheme(m) }; dialog = null } }
        }, confirm = stringResource(R.string.close), onConfirm = { dialog = null })
        "accent" -> AeroDialog(stringResource(R.string.accent), body = {
            listOf("orange" to R.string.accent_orange, "amber" to R.string.accent_amber, "coral" to R.string.accent_coral, "mint" to R.string.accent_mint).forEach { (k, l) ->
                ClickRow(stringResource(l), if (s.accent == k) "✓" else null) { scope.launch { app.settings.setAccent(k) }; dialog = null } }
        }, confirm = stringResource(R.string.close), onConfirm = { dialog = null })
        "timeout" -> AeroDialog(stringResource(R.string.timeout), body = {
            var v by remember { mutableStateOf(s.timeoutSec.toFloat()) }
            Slider(v, { v = it }, valueRange = 5f..30f, steps = 4, colors = SliderDefaults.colors(thumbColor = c.accent, activeTrackColor = c.accent))
            Text(stringResource(R.string.seconds, v.toInt()), color = c.text)
            AeroButton(stringResource(R.string.ok)) { scope.launch { app.settings.setTimeout(v.toInt()) }; dialog = null }
        }, confirm = stringResource(R.string.close), onConfirm = { dialog = null })
        "ttl" -> AeroDialog(stringResource(R.string.qr_ttl), body = {
            listOf(1, 5, 10).forEach { m -> ClickRow(stringResource(R.string.minutes, m), if (s.qrTtlMin == m) "✓" else null) { scope.launch { app.settings.setQrTtl(m) }; dialog = null } }
        }, confirm = stringResource(R.string.close), onConfirm = { dialog = null })
        "conflict" -> AeroDialog(stringResource(R.string.conflict), body = {
            listOf(ConflictMode.RENAME to R.string.conflict_rename, ConflictMode.SKIP to R.string.conflict_skip).forEach { (m, l) ->
                ClickRow(stringResource(l), if (s.conflict == m) "✓" else null) { scope.launch { app.settings.setConflict(m) }; dialog = null } }
        }, confirm = stringResource(R.string.close), onConfirm = { dialog = null })
    }
}
''')

add(K + "ui/screens/Diagnostics.kt", r'''
package com.aero.share.ui.screens

import android.Manifest
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.BuildConfig
import com.aero.share.R
import com.aero.share.ui.*
import java.text.DateFormat
import java.util.Date

@Composable
fun Diagnostics(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current
    val errors by app.engine.errors.collectAsStateWithLifecycle()
    val serverOn by app.engine.serverOn.collectAsStateWithLifecycle()
    val status by app.discovery.status.collectAsStateWithLifecycle()
    val wd = ctx.packageManager.hasSystemFeature(PackageManager.FEATURE_WIFI_DIRECT)
    val bt = (ctx.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter != null
    fun report() = buildString {
        appendLine("AERO SHARE diagnostics")
        appendLine("App: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
        appendLine("Android: ${Build.VERSION.RELEASE} API ${Build.VERSION.SDK_INT}")
        appendLine("Model: ${Build.MODEL}")
        appendLine("WiFiDirect HW: $wd (unused v1); BT HW: $bt (unused v1)")
        appendLine("Discovery: $status; server: $serverOn")
        appendLine("Errors: " + errors.joinToString { it.code })
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text(stringResource(R.string.sec_diagnostics), color = c.text, fontWeight = FontWeight.Bold, fontSize = 22.sp, modifier = Modifier.padding(vertical = 12.dp))
        AeroCard(Modifier.fillMaxWidth()) {
            DRow(stringResource(R.string.app_version), "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
            DRow(stringResource(R.string.android_version), "${Build.VERSION.RELEASE} · API ${Build.VERSION.SDK_INT}")
            DRow(stringResource(R.string.model), Build.MODEL)
        }
        SectionTitle(stringResource(R.string.capabilities))
        AeroCard(Modifier.fillMaxWidth()) {
            DRow("Wi-Fi / mDNS", stringResource(R.string.active))
            DRow(stringResource(R.string.wifi_direct_hw), stringResource(if (wd) R.string.hw_yes_not_used else R.string.hw_no))
            DRow(stringResource(R.string.bt_hw), stringResource(if (bt) R.string.hw_yes_not_used else R.string.hw_no))
            DRow(stringResource(R.string.discovery_status), status.name)
            DRow(stringResource(R.string.server_status), stringResource(if (serverOn) R.string.active else R.string.inactive))
        }
        SectionTitle(stringResource(R.string.permissions_status))
        AeroCard(Modifier.fillMaxWidth()) {
            val perms = if (Build.VERSION.SDK_INT >= 33) listOf(Manifest.permission.READ_MEDIA_IMAGES, Manifest.permission.POST_NOTIFICATIONS, Manifest.permission.CAMERA)
            else listOf(Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.CAMERA)
            perms.forEach { p -> DRow(p.substringAfterLast('.'), stringResource(if (ContextCompat.checkSelfPermission(ctx, p) == PackageManager.PERMISSION_GRANTED) R.string.granted else R.string.not_granted)) }
        }
        SectionTitle(stringResource(R.string.recent_errors))
        AeroCard(Modifier.fillMaxWidth()) {
            if (errors.isEmpty()) Text(stringResource(R.string.no_errors), color = c.text2, fontSize = 13.sp)
            errors.forEach { Text("${DateFormat.getTimeInstance(DateFormat.MEDIUM).format(Date(it.time))} · ${it.code}", color = c.text2, fontSize = 12.sp) }
        }
        Spacer(Modifier.height(12.dp))
        AeroButton(stringResource(R.string.diag_export), Modifier.fillMaxWidth()) {
            runCatching { ctx.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply { type = "text/plain"; putExtra(Intent.EXTRA_TEXT, report()) }, null)) }
        }
        Spacer(Modifier.height(8.dp))
        AeroButton(stringResource(R.string.close), Modifier.fillMaxWidth(), primary = false) { nav.popBackStack() }
    }
}

@Composable private fun DRow(k: String, v: String) {
    val c = aero()
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(k, color = c.text2, fontSize = 13.sp, modifier = Modifier.weight(1f)); Text(v, color = c.text, fontSize = 13.sp)
    }
}
''')

add(K + "ui/screens/SendPicker.kt", r'''
package com.aero.share.ui.screens

import android.Manifest
import android.os.Build
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.core.PathGuard
import com.aero.share.storage.*
import com.aero.share.ui.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

sealed class Sel(val key: String) {
    class One(val i: PickItem) : Sel(i.uri.toString())
    class Folder(val uri: android.net.Uri, val name: String) : Sel(uri.toString())
    class App(val e: AppEntry) : Sel(e.pkg)
}

class PickVm : ViewModel() {
    val sel = androidx.compose.runtime.mutableStateListOf<Sel>()
    var cat by mutableStateOf(Cat.RECENT)
    var apps by mutableStateOf(false)
}

@Composable
fun SendPicker(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    val vm: PickVm = viewModel()
    var items by remember { mutableStateOf<List<PickItem>>(emptyList()) }
    var appList by remember { mutableStateOf<List<AppEntry>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var rationale by remember { mutableStateOf(false) }
    var building by remember { mutableStateOf(false) }
    val perms = if (Build.VERSION.SDK_INT >= 33) arrayOf(Manifest.permission.READ_MEDIA_IMAGES, Manifest.permission.READ_MEDIA_VIDEO, Manifest.permission.READ_MEDIA_AUDIO) else arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
    val mediaOk = perms.any { ContextCompat.checkSelfPermission(ctx, it) == android.content.pm.PackageManager.PERMISSION_GRANTED }
    val permL = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }
    val saf = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        uris.forEach { u -> runCatching {
            ctx.contentResolver.query(u, null, null, null, null)?.use { cu ->
                if (cu.moveToFirst()) {
                    val n = cu.getString(cu.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME))
                    val s = cu.getLong(cu.getColumnIndexOrThrow(OpenableColumns.SIZE))
                    vm.sel.add(Sel.One(PickItem(u, n, s, 0, ctx.contentResolver.getType(u) ?: "")))
                }
            }
        } }
    }
    val treeL = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { u ->
        if (u != null) {
            runCatching { ctx.contentResolver.takePersistableUriPermission(u, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            vm.sel.add(Sel.Folder(u, androidx.documentfile.provider.DocumentFile.fromTreeUri(ctx, u)?.name ?: "Folder"))
        }
    }
    LaunchedEffect(vm.cat, vm.apps, mediaOk) {
        if (vm.apps) { loading = true; appList = withContext(Dispatchers.IO) { Apks.list(ctx) }; loading = false }
        else if (mediaOk) { loading = true; items = withContext(Dispatchers.IO) { Catalog.items(ctx, vm.cat) }; loading = false }
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.then(AeroClick { nav.popBackStack() }).padding(8.dp)) { Icon(Icons.Filled.ArrowBack, null, tint = c.text) }
            Text(stringResource(R.string.send), color = c.text, fontWeight = FontWeight.Bold, fontSize = 18.sp)
        }
        LazyRow(Modifier.padding(horizontal = 12.dp)) {
            val cats = listOf(Cat.RECENT to R.string.cat_recent, Cat.IMAGES to R.string.cat_images, Cat.VIDEOS to R.string.cat_videos,
                Cat.AUDIO to R.string.cat_audio, Cat.DOCS to R.string.cat_docs, Cat.DOWNLOADS to R.string.cat_downloads)
            items(cats) { (k, l) ->
                val s = !vm.apps && vm.cat == k
                Box(Modifier.padding(end = 6.dp).clip(RoundedCornerShape(10.dp)).background(if (s) c.accent else c.surface2)
                    .then(AeroClick { vm.apps = false; vm.cat = k; if (!mediaOk) rationale = true }).padding(horizontal = 14.dp, vertical = 8.dp)) {
                    Text(stringResource(l), color = if (s) Color.Black else c.text2, fontSize = 13.sp)
                }
            }
            item {
                Box(Modifier.clip(RoundedCornerShape(10.dp)).background(if (vm.apps) c.accent else c.surface2)
                    .then(AeroClick { vm.apps = true }).padding(horizontal = 14.dp, vertical = 8.dp)) {
                    Text(stringResource(R.string.cat_apps), color = if (vm.apps) Color.Black else c.text2, fontSize = 13.sp)
                }
            }
        }
        Row(Modifier.padding(12.dp)) {
            AeroButton(stringResource(R.string.pick_files), primary = false) { saf.launch(arrayOf("*/*")) }
            Spacer(Modifier.width(8.dp))
            AeroButton(stringResource(R.string.pick_folder), primary = false) { treeL.launch(null) }
        }
        if (!mediaOk && !vm.apps) EmptyState(R.drawable.ic_file, stringResource(R.string.permission_needed), stringResource(R.string.perm_media)) {
            AeroButton(stringResource(R.string.grant)) { permL.launch(perms) }
        } else if (loading) Box(Modifier.fillMaxWidth().padding(24.dp), Alignment.Center) { Text(stringResource(R.string.calculating), color = c.text2) }
        else LazyColumn(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            if (vm.apps) items(appList, key = { it.pkg }) { e ->
                val ch = vm.sel.any { it.key == e.pkg }
                Row(Modifier.fillMaxWidth().then(AeroClick { if (ch) vm.sel.removeAll { it.key == e.pkg } else vm.sel.add(Sel.App(e)) }).padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(R.drawable.ic_apk), null, tint = c.text2, modifier = Modifier.size(32.dp))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(e.label, color = c.text, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text("${e.version} · ${Formats.bytes(e.size)}", color = c.text2, fontSize = 12.sp)
                    }
                    if (ch) Icon(Icons.Filled.Check, null, tint = c.accent)
                }
            } else {
                if (items.isEmpty()) item { EmptyState(R.drawable.ic_file, stringResource(R.string.empty_category), "") }
                items(items, key = { it.uri.toString() }) { p ->
                    val ch = vm.sel.any { it.key == p.uri.toString() }
                    Row(Modifier.fillMaxWidth().then(AeroClick { if (ch) vm.sel.removeAll { it.key == p.uri.toString() } else vm.sel.add(Sel.One(p)) }).padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        if (p.mime.startsWith("image") || p.mime.startsWith("video")) AsyncImage(p.uri, null, Modifier.size(40.dp).clip(RoundedCornerShape(8.dp)), contentScale = ContentScale.Crop)
                        else Icon(painterResource(R.drawable.ic_file), null, tint = c.text2, modifier = Modifier.size(32.dp))
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(p.name, color = c.text, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(Formats.bytes(p.size), color = c.text2, fontSize = 12.sp)
                        }
                        if (ch) Icon(Icons.Filled.Check, null, tint = c.accent)
                    }
                }
            }
        }
        val quick = vm.sel.sumOf { when (it) { is Sel.One -> it.i.size; is Sel.App -> it.e.size; is Sel.Folder -> 0L } }
        Column(Modifier.fillMaxWidth().background(c.surface).padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.selected_summary, vm.sel.size, Formats.bytes(quick)), color = c.text, modifier = Modifier.weight(1f), fontSize = 14.sp)
                if (vm.sel.isNotEmpty()) AeroButton(stringResource(R.string.clear), primary = false) { vm.sel.clear() }
            }
            Spacer(Modifier.height(8.dp))
            AeroButton(stringResource(R.string.next), Modifier.fillMaxWidth(), enabled = vm.sel.isNotEmpty() && !building) {
                building = true
                scope.launch {
                    val files = withContext(Dispatchers.IO) {
                        vm.sel.flatMap { s -> when (s) {
                            is Sel.One -> listOf(OutFile(PathGuard.sanitizeRelative(s.i.name) ?: "file", s.i.size, uri = s.i.uri))
                            is Sel.Folder -> Catalog.folderFiles(ctx, s.uri)
                            is Sel.App -> Apks.appFiles(ctx, s.e)
                        } }
                    }
                    app.pendingFiles = files; app.pendingTotal = files.sumOf { it.size }; building = false
                    if (files.isNotEmpty()) { vm.sel.clear(); nav.navigate("target") }
                }
            }
        }
    }
    if (rationale) AeroDialog(stringResource(R.string.permission_needed), body = { Text(stringResource(R.string.perm_media)) },
        confirm = stringResource(R.string.grant), onConfirm = { rationale = false; permL.launch(perms) },
        dismiss = stringResource(R.string.use_system_picker), onDismiss = { rationale = false; saf.launch(arrayOf("*/*")) })
}
''')

add(K + "ui/screens/SendTarget.kt", r'''
package com.aero.share.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.net.QrPayload
import com.aero.share.net.Target
import com.aero.share.ui.*

@Composable
fun SendTarget(app: AeroApp, nav: NavController) {
    val c = aero()
    val found by app.discovery.devices.collectAsStateWithLifecycle()
    val known by app.devices.all.collectAsStateWithLifecycle(initialValue = emptyList())
    val s by app.settings.flow.collectAsStateWithLifecycle(initialValue = app.settingsNow)
    var manual by remember { mutableStateOf(false) }
    var addr by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf<Target?>(null) }
    LaunchedEffect(Unit) {
        app.scannedQr?.let { raw -> app.scannedQr = null; QrPayload.decode(raw)?.let { confirm = Target(it.host, it.port, it.fp, it.token, it.name) } }
        app.pendingTarget?.let { confirm = it; app.pendingTarget = null }
    }
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text(stringResource(R.string.choose_recipient), color = c.text, fontWeight = FontWeight.Bold, fontSize = 20.sp)
        Text(stringResource(R.string.selected_summary, app.pendingFiles.size, Formats.bytes(app.pendingTotal)), color = c.text2, fontSize = 13.sp)
        Spacer(Modifier.height(12.dp))
        Row {
            AeroButton(stringResource(R.string.scan_qr), Modifier.weight(1f)) { nav.navigate("scan") }
            Spacer(Modifier.width(8.dp))
            AeroButton(stringResource(R.string.manual_connect), Modifier.weight(1f), primary = false) { manual = true }
        }
        Spacer(Modifier.height(12.dp))
        if (app.pendingFiles.isEmpty()) EmptyState(R.drawable.ic_file, stringResource(R.string.empty_category), "") {
            AeroButton(stringResource(R.string.close), primary = false) { nav.popBackStack() }
        } else LazyColumn(Modifier.weight(1f)) {
            items(found, key = { it.id }) { d ->
                val k = known.find { it.id == d.id }
                AeroCard(Modifier.fillMaxWidth().padding(vertical = 4.dp).then(AeroClick { confirm = Target(d.host, d.port, null, null, k?.display() ?: d.name) })) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(painterResource(R.drawable.ic_device), null, tint = c.accent, modifier = Modifier.size(24.dp))
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(k?.display() ?: d.name, color = c.text, fontWeight = FontWeight.SemiBold)
                            Text(stringResource(R.string.local_tls), color = c.text2, fontSize = 12.sp)
                        }
                        if (k?.trusted == true) Icon(painterResource(R.drawable.ic_shield), null, tint = c.accent, modifier = Modifier.size(16.dp))
                    }
                }
            }
            if (found.isEmpty()) item { EmptyState(R.drawable.ic_devices, stringResource(R.string.no_devices), stringResource(R.string.no_devices_hint)) }
        }
    }
    if (manual) AeroDialog(stringResource(R.string.manual_connect), body = {
        OutlinedTextField(addr, { addr = it }, label = { Text(stringResource(R.string.ip_port)) }, singleLine = true)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(code, { code = it }, label = { Text(stringResource(R.string.pairing_code_optional)) }, singleLine = true)
    }, confirm = stringResource(R.string.connect), onConfirm = {
        manual = false
        val hp = addr.trim().split(":"); val port = hp.getOrNull(1)?.toIntOrNull()
        if (hp[0].isNotBlank() && port != null) confirm = Target(hp[0], port, null, code.trim().ifBlank { null }, hp[0])
    }, dismiss = stringResource(R.string.cancel), onDismiss = { manual = false })
    confirm?.let { t ->
        AeroDialog(stringResource(R.string.send), body = {
            Text(stringResource(R.string.confirm_send, app.pendingFiles.size, Formats.bytes(app.pendingTotal), t.label))
            Text(stringResource(R.string.local_tls), color = c.accent, fontSize = 13.sp)
            if (app.pendingTotal > (1L shl 30) && s.warnLarge) Text(stringResource(R.string.confirm_send_large), fontSize = 13.sp)
        }, confirm = stringResource(R.string.send), onConfirm = {
            confirm = null
            app.engine.enqueueSend(t, app.pendingFiles)
            app.pendingFiles = emptyList(); app.pendingTotal = 0
            nav.navigate("transfer") { popUpTo("home") }
        }, dismiss = stringResource(R.string.cancel), onDismiss = { confirm = null })
    }
}
''')

add(K + "ui/screens/Receive.kt", r'''
package com.aero.share.ui.screens

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.net.Dir
import com.aero.share.net.Qr
import com.aero.share.net.QrPayload
import com.aero.share.net.TState
import com.aero.share.ui.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

@Composable
fun Receive(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current
    val s by app.settings.flow.collectAsStateWithLifecycle(initialValue = app.settingsNow)
    val port by app.engine.serverPort.collectAsStateWithLifecycle()
    val incoming by app.engine.incoming.collectAsStateWithLifecycle()
    val active by app.engine.active.collectAsStateWithLifecycle()
    var showQr by remember { mutableStateOf(false) }
    var qr by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
    var addr by remember { mutableStateOf<String?>(null) }
    val notifL = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    val legacyL = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    DisposableEffect(Unit) {
        app.engine.setReceiveMode(true)
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) notifL.launch(Manifest.permission.POST_NOTIFICATIONS)
        if (Build.VERSION.SDK_INT <= 28 && s.receiveTreeUri.isEmpty() && ContextCompat.checkSelfPermission(ctx, Manifest.permission.WRITE_EXTERNAL_STORAGE) != android.content.pm.PackageManager.PERMISSION_GRANTED) legacyL.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        onDispose { app.engine.setReceiveMode(false) }
    }
    LaunchedEffect(active?.state) { if (active?.state == TState.Transferring && active?.dir == Dir.Receive) nav.navigate("transfer") { launchSingleTop = true } }
    LaunchedEffect(showQr, port, s.qrTtlMin) {
        if (showQr && port > 0) while (true) {
            val host = withContext(Dispatchers.IO) { app.discovery.localAddress() }
            addr = host
            if (host != null) {
                val payload = QrPayload(host, port, app.engine.tokens.issue(s.qrTtlMin * 60_000L), app.tls.fingerprint, app.identity.name(s.deviceName)).encode()
                qr = withContext(Dispatchers.Default) { Qr.bitmap(payload, 512) }
            }
            delay(s.qrTtlMin * 60_000L)
        }
    }
    LaunchedEffect(port) { if (addr == null) addr = withContext(Dispatchers.IO) { app.discovery.localAddress() } }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(stringResource(R.string.receive), color = c.text, fontWeight = FontWeight.Bold, fontSize = 22.sp, modifier = Modifier.padding(vertical = 12.dp))
        Text(app.identity.name(s.deviceName), color = c.accent, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        StatusChip(stringResource(if (port > 0) R.string.waiting_files else R.string.st_connecting), port > 0)
        Spacer(Modifier.height(16.dp))
        if (addr != null && port > 0) Text(stringResource(R.string.your_address, "$addr:$port"), color = c.text2, fontSize = 13.sp)
        Spacer(Modifier.height(12.dp))
        AeroButton(stringResource(if (showQr) R.string.hide_qr else R.string.show_qr), primary = false) { showQr = !showQr }
        if (showQr) { Spacer(Modifier.height(16.dp)); qr?.let { Box(Modifier.background(Color.White).padding(12.dp)) { Image(it.asImageBitmap(), null, Modifier.size(240.dp)) } } }
        Spacer(Modifier.height(20.dp))
        Text(stringResource(R.string.receive_hint), color = c.text2, fontSize = 13.sp, textAlign = TextAlign.Center)
        Text(stringResource(R.string.hotspot_hint), color = c.text2, fontSize = 12.sp, textAlign = TextAlign.Center)
        Text(stringResource(R.string.dest_label, app.store.destLabel(s.receiveTreeUri)), color = c.text2, fontSize = 12.sp)
    }
    incoming?.let { r ->
        AeroDialog(stringResource(R.string.incoming_title), body = {
            Text(stringResource(R.string.incoming_body, r.peerName, r.files.size, Formats.bytes(r.total)))
            Text(r.peerModel + " · " + stringResource(R.string.local_tls), fontSize = 13.sp)
            Text(stringResource(R.string.dest_label, app.store.destLabel(s.receiveTreeUri)), fontSize = 12.sp)
            if (r.storageWarn) Text(stringResource(R.string.storage_warn, Formats.bytes(app.store.free())), color = c.danger, fontSize = 13.sp)
        }, confirm = stringResource(R.string.accept), onConfirm = { app.engine.acceptIncoming(true) },
            dismiss = stringResource(R.string.decline), onDismiss = { app.engine.acceptIncoming(false) })
    }
}
''')

add(K + "ui/screens/QrScan.kt", r'''
package com.aero.share.ui.screens

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.ui.AeroButton
import com.aero.share.ui.aero
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import java.util.concurrent.Executors

@Composable
fun QrScan(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current; val owner = LocalLifecycleOwner.current
    var granted by remember { mutableStateOf(ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == android.content.pm.PackageManager.PERMISSION_GRANTED) }
    var denied by remember { mutableStateOf(false) }
    var handled by remember { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it; denied = !it }
    LaunchedEffect(Unit) { if (!granted) launcher.launch(Manifest.permission.CAMERA) }
    Box(Modifier.fillMaxSize()) {
        if (granted) {
            AndroidView(factory = { context ->
                val pv = PreviewView(context)
                val f = ProcessCameraProvider.getInstance(context)
                f.addListener({
                    val provider = f.get()
                    val preview = Preview.Builder().build().also { it.surfaceProvider = pv.surfaceProvider }
                    val analysis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
                    val reader = QRCodeReader()
                    val hints = mapOf(DecodeHintType.TRY_HARDER to true)
                    analysis.setAnalyzer(Executors.newSingleThreadExecutor()) { proxy ->
                        try {
                            val plane = proxy.planes[0]; val w = proxy.width; val h = proxy.height
                            val buf = plane.buffer; val rows = ByteArray(w * h); val stride = plane.rowStride
                            if (stride == w) buf.get(rows, 0, minOf(buf.remaining(), rows.size))
                            else { val row = ByteArray(stride); for (y in 0 until h) { buf.position(y * stride); buf.get(row, 0, minOf(stride, buf.remaining())); System.arraycopy(row, 0, rows, y * w, w) } }
                            val res = runCatching { reader.decode(BinaryBitmap(HybridBinarizer(PlanarYUVLuminanceSource(rows, w, h, 0, 0, w, h, false))), hints) }.getOrNull()
                            if (res != null && !handled) { handled = true; pv.post { app.scannedQr = res.text; nav.popBackStack() } }
                        } finally { proxy.close() }
                    }
                    runCatching { provider.unbindAll(); provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis) }
                }, ContextCompat.getMainExecutor(context))
                pv
            }, modifier = Modifier.fillMaxSize(), onRelease = { runCatching { ProcessCameraProvider.getInstance(ctx).get().unbindAll() } })
            Column(Modifier.align(Alignment.BottomCenter).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(stringResource(R.string.scanning_hint), color = Color.White)
                Spacer(Modifier.height(12.dp))
                AeroButton(stringResource(R.string.cancel), primary = false) { nav.popBackStack() }
            }
        } else if (denied) Column(Modifier.align(Alignment.Center).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(stringResource(R.string.camera_denied), color = c.text2)
            Spacer(Modifier.height(12.dp))
            AeroButton(stringResource(R.string.close)) { nav.popBackStack() }
        }
    }
}
''')

add(K + "ui/screens/Transfer.kt", r'''
package com.aero.share.ui.screens

import android.app.DownloadManager
import android.content.Intent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.net.Dir
import com.aero.share.net.TState
import com.aero.share.storage.ApkInfo
import com.aero.share.storage.Apks
import com.aero.share.ui.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun Transfer(app: AeroApp, nav: NavController) {
    val c = aero(); val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    val s by app.engine.active.collectAsStateWithLifecycle()
    var info by remember { mutableStateOf<ApkInfo?>(null) }
    val session = s ?: run { LaunchedEffect(Unit) { nav.popBackStack() }; return }
    val label = when (session.state) {
        TState.Waiting -> R.string.st_waiting; TState.Preparing -> R.string.st_waiting
        TState.Connecting -> R.string.st_connecting; TState.Transferring -> R.string.st_transferring
        TState.Paused -> R.string.st_paused; TState.Interrupted -> R.string.st_interrupted
        TState.Verifying -> R.string.st_verifying; TState.Completed -> R.string.st_completed
        TState.Failed -> R.string.st_failed; TState.Cancelled -> R.string.st_cancelled
    }
    val eta = if (session.speed > 0 && session.totalBytes > session.doneBytes) Formats.duration((session.totalBytes - session.doneBytes) * 1000 / session.speed) else null
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(painterResource(R.drawable.ic_logo), null, tint = c.accent, modifier = Modifier.size(26.dp))
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.app_name), color = c.text, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(20.dp))
        Text(stringResource(label), color = if (session.state == TState.Failed || session.state == TState.Interrupted) c.danger else c.text, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Text(session.peerName, color = c.text2)
        Spacer(Modifier.height(16.dp))
        AeroProgress(if (session.totalBytes > 0) session.doneBytes.toFloat() / session.totalBytes else 0f, Modifier.fillMaxWidth())
        Spacer(Modifier.height(10.dp))
        Text("${Formats.bytes(session.doneBytes)} / ${Formats.bytes(session.totalBytes)}", color = c.text, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        if (session.state == TState.Transferring) {
            Text(Formats.speed(session.speed), color = c.accent, fontSize = 14.sp)
            if (eta != null) Text(stringResource(R.string.eta_approx, eta), color = c.text2, fontSize = 13.sp)
            Text(stringResource(R.string.file_x_of_y, session.fileIndex, session.fileCount), color = c.text2, fontSize = 13.sp)
            if (session.fileName.isNotEmpty()) Text(session.fileName, color = c.text2, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Text(stringResource(R.string.local_tls), color = c.text2, fontSize = 12.sp)
        session.errCode?.let { code ->
            val res = ctx.resources.getIdentifier(code, "string", ctx.packageName)
            if (res != 0) Text(stringResource(res), color = c.danger, fontSize = 13.sp)
        }
        Spacer(Modifier.height(16.dp))
        when {
            session.state == TState.Transferring || session.state == TState.Connecting || session.state == TState.Waiting -> Row {
                if (session.dir == Dir.Send && session.state == TState.Transferring) { AeroButton(stringResource(R.string.pause), primary = false) { app.engine.pause() }; Spacer(Modifier.width(8.dp)) }
                AeroButton(stringResource(R.string.cancel), primary = false) { app.engine.cancel() }
            }
            session.state == TState.Paused && session.dir == Dir.Send -> Row {
                AeroButton(stringResource(R.string.resume)) { app.engine.resume() }
                Spacer(Modifier.width(8.dp))
                AeroButton(stringResource(R.string.cancel), primary = false) { app.engine.cancel() }
            }
            session.terminal -> {
                Text(stringResource(R.string.duration_label, Formats.duration(session.endedAt - session.startedAt)), color = c.text2, fontSize = 13.sp)
                if (session.results.any { it.name == "aero-app.json" }) Text(stringResource(R.string.apk_split_note), color = c.text2, fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
                if (session.state == TState.Completed && session.dir == Dir.Receive && session.results.isNotEmpty()) {
                    LazyColumn(Modifier.weight(1f, fill = false)) {
                        items(session.results, key = { it.uri.toString() }) { f ->
                            AeroCard(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                                Text(f.name, color = c.text, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text(Formats.bytes(f.size), color = c.text2, fontSize = 12.sp)
                                Row {
                                    AeroButton(stringResource(R.string.open), primary = false) { runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW).apply { setDataAndType(f.uri, f.mime); addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION) }) } }
                                    if (f.name.endsWith(".apk")) {
                                        Spacer(Modifier.width(6.dp))
                                        AeroButton(stringResource(R.string.install), primary = false) { runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW).apply { setDataAndType(f.uri, "application/vnd.android.package-archive"); addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION) }) } }
                                        Spacer(Modifier.width(6.dp))
                                        AeroButton(stringResource(R.string.details), primary = false) { scope.launch { info = withContext(Dispatchers.IO) { Apks.archiveInfo(ctx, f.uri) } } }
                                    }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    AeroButton(stringResource(R.string.open_folder), primary = false) { runCatching { ctx.startActivity(Intent(DownloadManager.ACTION_VIEW_DOWNLOADS)) } }
                }
                Spacer(Modifier.height(12.dp))
                AeroButton(stringResource(R.string.close), Modifier.fillMaxWidth()) { app.engine.dismissTerminal(); nav.navigate("home") { popUpTo("home") { inclusive = true } } }
            }
            else -> AeroButton(stringResource(R.string.close), primary = false) { app.engine.dismissTerminal(); nav.popBackStack() }
        }
    }
    info?.let { i ->
        AeroDialog(i.label, body = {
            Text("${stringResource(R.string.package_name)}: ${i.pkg}")
            Text("${stringResource(R.string.version)}: ${i.version}")
            Text("${stringResource(R.string.sha256)}: ${i.sha256.take(24)}…", fontSize = 12.sp)
            if (i.signer != null) Text("${stringResource(R.string.signer)}: ${i.signer.take(24)}…", fontSize = 12.sp)
        }, confirm = stringResource(R.string.close), onConfirm = { info = null })
    }
}
''')

def main():
    for rel, content in FILES.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    print(f"Generated {len(FILES)} files under {ROOT}/")

if __name__ == "__main__":
    main()

# END PART 08/8
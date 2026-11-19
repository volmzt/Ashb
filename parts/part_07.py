add(K + "AeroApp.kt", r'''
package com.aero.share

import android.app.Application
import com.aero.share.core.Identity
import com.aero.share.data.*
import com.aero.share.net.DeviceTls
import com.aero.share.net.Discovery
import com.aero.share.net.Target
import com.aero.share.net.TransferEngine
import com.aero.share.service.TransferService
import com.aero.share.storage.OutFile
import com.aero.share.storage.ReceiverStore
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first

class AeroApp : Application() {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    lateinit var settings: SettingsStore
    lateinit var identity: Identity
    lateinit var tls: DeviceTls
    lateinit var devices: DeviceRepo
    lateinit var history: HistoryRepo
    lateinit var store: ReceiverStore
    lateinit var engine: TransferEngine
    lateinit var discovery: Discovery
    var settingsNow = AppSettings()
        private set

    // Survives activity recreation; used to hand state between screens.
    var pendingFiles: List<OutFile> = emptyList()
    var pendingTotal: Long = 0L
    var pendingTarget: Target? = null
    var scannedQr: String? = null

    overridedismiss fun onCreate() {
        super.onCreate()
        settings = SettingsStore(this)
        identity = Identity(this)
        tls = DeviceTls(this)
        val db = AeroDb.build(this)
        devices = DeviceRepo(db.devices())
        history = HistoryRepo(db.history())
        store = ReceiverStore(this)
        engine = TransferEngine(this, tls, identity, store, devices, history, settings, scope)
        discovery = Discovery(this, identity, scope)
        TransferService.createChannels(this)
        runBlocking { runCatching { settingsNow = settings.flow.first() } }
        scope.launch { settings.flow.collect { settingsNow = it } }
        scope.launch(Dispatchers.IO) { runCatching { tls.certificate } }
    }
}
''')

add(K + "MainActivity.kt", r'''
package com.aero.share

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.aero.share.ui.AeroNav
import com.aero.share.ui.AeroTheme

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as AeroApp
        setContent {
            val s by app.settings.flow.collectAsStateWithLifecycle(initialValue = app.settingsNow)
            AeroTheme(s) { AeroNav(app) }
        }
    }
}
''')

add(K + "ui/AeroTheme.kt", r'''
package com.aero.share.ui

import android.provider.Settings
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aero.share.AeroApp
import com.aero.share.data.AppSettings
import com.aero.share.data.ThemeMode

data class AeroColors(
    val bg: Color, val surface: Color, val surface2: Color, val elevated: Color,
    val accent: Color, val accent2: Color, val text: Color, val text2: Color,
    val divider: Color, val success: Color, val danger: Color, val glass: Boolean
)

val DarkAero = AeroColors(Color(0xFF090909), Color(0xFF141414), Color(0xFF1C1C1C), Color(0xFF222222),
    Color(0xFFFF7900), Color(0xFFFF9A35), Color.White, Color(0xFFA3A3A3), Color(0xFF303030),
    Color(0xFF3DDC97), Color(0xFFFF5A5A), false)
val LightAero = AeroColors(Color(0xFFF6F6F6), Color.White, Color(0xFFF0F0F0), Color.White,
    Color(0xFFFF7900), Color(0xFFFF9A35), Color(0xFF111111), Color(0xFF6B6B6B), Color(0xFFE2E2E2),
    Color(0xFF1FA97A), Color(0xFFD93636), false)

fun accents(key: String): Pair<Color, Color> = when (key) {
    "amber" -> Color(0xFFFFB300) to Color(0xFFFFCF66)
    "coral" -> Color(0xFFFF5A3C) to Color(0xFFFF8A70)
    "mint" -> Color(0xFF3DDC97) to Color(0xFF7FE8BC)
    else -> Color(0xFFFF7900) to Color(0xFFFF9A35)
}

val LocalAero = staticCompositionLocalOf { DarkAero }
val LocalMotion = compositionLocalOf { true }

private val AeroType = Typography(
    headlineMedium = TextStyle(fontSize = 26.sp, fontWeight = FontWeight.Bold),
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 16.sp), bodyMedium = TextStyle(fontSize = 14.sp),
    labelLarge = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.SemiBold),
    labelMedium = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Medium)
)
private val AeroShapes = Shapes(small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(14.dp), large = RoundedCornerShape(18.dp))

@Composable
fun AeroTheme(s: AppSettings, content: @Composable () -> Unit) {
    val dark = when (s.theme) { ThemeMode.DARK -> true; ThemeMode.LIGHT -> false; ThemeMode.SYSTEM -> isSystemInDarkTheme() }
    val (a, a2) = accents(s.accent)
    val colors = (if (dark) DarkAero else LightAero).copy(accent = a, accent2 = a2, glass = s.glass)
    val reduced = Settings.Global.getFloat(LocalContext.current.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    val scheme = if (dark) darkColorScheme(primary = a, background = colors.bg, surface = colors.surface, onPrimary = Color.Black, onBackground = colors.text, onSurface = colors.text)
    else lightColorScheme(primary = a, background = colors.bg, surface = colors.surface, onPrimary = Color.Black, onBackground = colors.text, onSurface = colors.text)
    CompositionLocalProvider(LocalAero provides colors, LocalMotion provides (s.animations && !reduced)) {
        MaterialTheme(colorScheme = scheme, typography = AeroType, shapes = AeroShapes, content = content)
    }
}

@Composable fun aero(): AeroColors = LocalAero.current

@Composable
fun AeroClick(onClick: () -> Unit): Modifier {
    val h = LocalHapticFeedback.current
    val app = LocalContext.current.applicationContext as AeroApp
    return Modifier.clickable {
        if (app.settingsNow.haptics) h.performHapticFeedback(HapticFeedbackType.LongPress)
        onClick()
    }
}

@Composable
fun AeroCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val c = aero()
    Column(modifier.clip(RoundedCornerShape(18.dp)).background(if (c.glass) c.surface.copy(alpha = 0.82f) else c.surface)
        .border(1.dp, c.divider, RoundedCornerShape(18.dp)).padding(16.dp), content = content)
}

@Composable
fun AeroButton(text: String, modifier: Modifier = Modifier, primary: Boolean = true, enabled: Boolean = true, onClick: () -> Unit) {
    val c = aero()
    val bg = if (primary) c.accent else c.elevated
    val fg = if (primary) Color.Black else c.text
    Box(modifier.clip(RoundedCornerShape(14.dp)).background(if (enabled) bg else bg.copy(alpha = 0.4f))
        .then(AeroClick { if (enabled) onClick() }).padding(horizontal = 20.dp, vertical = 13.dp), contentAlignment = Alignment.Center) {
        Text(text, color = if (enabled) fg else fg.copy(alpha = 0.5f), fontWeight = FontWeight.Bold, fontSize = 14.sp)
    }
}

@Composable
fun AeroProgress(fraction: Float, modifier: Modifier = Modifier) {
    val c = aero()
    val anim by animateFloatAsState(fraction.coerceIn(0f, 1f), tween(if (LocalMotion.current) 300 else 0), label = "p")
    Box(modifier.height(8.dp).clip(RoundedCornerShape(4.dp)).background(c.elevated)) {
        Box(Modifier.fillMaxHeight().fillMaxWidth(anim).clip(RoundedCornerShape(4.dp)).background(c.accent))
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    Text(text, modifier.padding(vertical = 8.dp), color = aero().text2, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp)
}

@Composable
fun EmptyState(icon: Int, title: String, body: String, action: (@Composable () -> Unit)? = null) {
    val c = aero()
    Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(painterResource(icon), null, tint = c.text2, modifier = Modifier.size(40.dp))
        Spacer(Modifier.height(12.dp))
        Text(title, color = c.text, fontWeight = FontWeight.SemiBold)
        if (body.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Text(body, color = c.text2, fontSize = 13.sp, textAlign = TextAlign.Center)
        }
        if (action != null) { Spacer(Modifier.height(14.dp)); action() }
    }
}

@Composable
fun SwitchRow(title: String, checked: Boolean, subtitle: String? = null, onChange: (Boolean) -> Unit) {
    val c = aero()
    Row(Modifier.fillMaxWidth().then(AeroClick { onChange(!checked) }).padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, color = c.text, fontSize = 15.sp)
            if (subtitle != null) Text(subtitle, color = c.text2, fontSize = 12.sp)
        }
        Switch(checked = checked, onCheckedChange = onChange,
            colors = SwitchDefaults.colors(checkedTrackColor = c.accent, checkedThumbColor = Color.Black))
    }
}

@Composable
fun ClickRow(title: String, value: String? = null, onClick: () -> Unit) {
    val c = aero()
    Row(Modifier.fillMaxWidth().then(AeroClick(onClick)).padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = c.text, fontSize = 15.sp, modifier = Modifier.weight(1f))
        if (value != null) Text(value, color = c.accent, fontSize = 13.sp)
    }
}

@Composable
fun AeroDialog(title: String, body: @Composable ColumnScope.() -> Unit, confirm: String, onConfirm: () -> Unit,
              dismiss: String? = null, onDismiss: () -> Unit = onConfirm) {
    val c = aero()
    AlertDialog(onDismissRequest = onDismiss, containerColor = c.elevated, titleContentColor = c.text, textContentColor = c.text2,
        title = { Text(title, fontWeight = FontWeight.Bold) }, text = { Column { body() } },
        confirmButton = { TextButton(onClick = onConfirm) { Text(confirm, color = c.accent, fontWeight = FontWeight.Bold) } },
        dismissButton = dismiss?.let { { TextButton(onClick = onDismiss) { Text(it, color = c.text2) } } })
}

@Composable
fun StatusChip(text: String, active: Boolean) {
    val c = aero()
    Row(Modifier.clip(RoundedCornerShape(8.dp)).background(c.surface2).padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(6.dp).clip(RoundedCornerShape(3.dp)).background(if (active) c.accent else c.text2))
        Spacer(Modifier.width(6.dp))
        Text(text, color = c.text2, fontSize = 11.sp)
    }
}
''')

add(K + "ui/AeroNav.kt", r'''
package com.aero.share.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.data.PowerMode
import com.aero.share.ui.screens.*

@Composable
fun AeroNav(app: AeroApp) {
    val nav = rememberNavController()
    val c = aero()
    val settings by app.settings.flow.collectAsStateWithLifecycle(initialValue = app.settingsNow)
    val back by nav.currentBackStackEntryAsState()
    val route = back?.destination?.route
    val fg = rememberFgFlag()

    val pairing by app.engine.pairing.collectAsStateWithLifecycle()
    pairing?.let { p ->
        AeroDialog(stringResource(R.string.pairing_title), body = {
            Text(stringResource(R.string.pairing_body, p.name))
            Spacer(Modifier.height(8.dp))
            Text(Formats.fpShort(p.fp), color = c.accent, fontSize = 18.sp, fontFamily = FontFamily.Monospace)
        }, confirm = stringResource(R.string.accept), onConfirm = { app.engine.answerPairing(true) },
            dismiss = stringResource(R.string.decline), onDismiss = { app.engine.answerPairing(false) })
    }

    Column(Modifier.fillMaxSize().background(c.bg).systemBarsPadding()) {
        Box(Modifier.weight(1f)) {
            NavHost(nav, startDestination = if (settings.onboarded) "home" else "onboarding") {
                composable("onboarding") { Onboarding(app, nav) }
                composable("home") { Home(app, nav) }
                composable("devices") { Devices(app, nav) }
                composable("settings") { Settings(app, nav) }
                composable("history") { History(app, nav) }
                composable("send") { SendPicker(app, nav) }
                composable("target") { SendTarget(app, nav) }
                composable("receive") { Receive(app, nav) }
                composable("scan") { QrScan(app, nav) }
                composable("transfer") { Transfer(app, nav) }
                composable("diagnostics") { Diagnostics(app, nav) }
            }
        }
        if (route in setOf("home", "devices", "settings")) {
            Row(Modifier.fillMaxWidth().background(c.surface).padding(vertical = 6.dp)) {
                listOf(Triple("home", R.string.nav_home, true), Triple("devices", R.string.nav_devices, false),
                    Triple("settings", R.string.nav_settings, true)).forEach { (r, label, useVector) ->
                    val sel = route == r
                    Column(Modifier.weight(1f).clip(RoundedCornerShape(12.dp))
                        .then(AeroClick { if (!sel) nav.navigate(r) { popUpTo("home"); launchSingleTop = true } })
                        .padding(vertical = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        val tint = if (sel) c.accent else c.text2
                        when (r) {
                            "home" -> Icon(Icons.Filled.Home, null, tint = tint, modifier = Modifier.size(22.dp))
                            "settings" -> Icon(Icons.Filled.Settings, null, tint = tint, modifier = Modifier.size(22.dp))
                            else -> Icon(painterResource(R.drawable.ic_devices), null, tint = tint, modifier = Modifier.size(22.dp))
                        }
                        Text(stringResource(label), color = tint, fontSize = 11.sp)
                    }
                }
            }
        }
    }

    LaunchedEffect(fg) { app.engine.setForeground(fg) }
    val port by app.engine.serverPort.collectAsStateWithLifecycle()
    LaunchedEffect(fg, port, settings.visible, settings.startupDiscovery, settings.deviceName, settings.power, route) {
        val want = fg && settings.visible && settings.startupDiscovery && route in setOf("home", "devices", "target", "receive")
        if (want && port > 0) app.discovery.start(port, app.identity.name(settings.deviceName), true, settings.power == PowerMode.SAVING)
        else if (!want) app.discovery.stop()
    }
}

@Composable
fun rememberFgFlag(): Boolean {
    var fg by remember { mutableStateOf(true) }
    DisposableEffect(Unit) {
        val obs = object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) { fg = true }
            override fun onStop(owner: LifecycleOwner) { fg = false }
        }
        val l = ProcessLifecycleOwner.get().lifecycle
        l.addObserver(obs)
        onDispose { l.removeObserver(obs) }
    }
    return fg
}
''')

add(K + "ui/screens/Onboarding.kt", r'''
package com.aero.share.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import com.aero.share.AeroApp
import com.aero.share.R
import com.aero.share.data.ThemeMode
import com.aero.share.ui.*
import kotlinx.coroutines.launch

@Composable
fun Onboarding(app: AeroApp, nav: NavController) {
    val c = aero()
    val scope = rememberCoroutineScope()
    val motion = LocalMotion.current
    val pages = listOf(
        Triple(R.drawable.ic_logo, R.string.onb1_title, R.string.onb1_body),
        Triple(R.drawable.ic_wifi, R.string.onb2_title, R.string.onb2_body),
        Triple(R.drawable.ic_shield, R.string.onb3_title, R.string.onb3_body)
    )
    val pager = rememberPagerState { pages.size + 1 }
    suspend fun go(p: Int) { if (motion) pager.animateScrollToPage(p) else pager.scrollToPage(p) }
    Column(Modifier.fillMaxSize().padding(24.dp)) {
        HorizontalPager(pager, Modifier.weight(1f)) { page ->
            Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                if (page < pages.size) {
                    val (icon, title, body) = pages[page]
                    Icon(painterResource(icon), null, tint = c.accent, modifier = Modifier.size(72.dp))
                    Spacer(Modifier.height(24.dp))
                    Text(stringResource(title), color = c.text, fontSize = 24.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                    Spacer(Modifier.height(12.dp))
                    Text(stringResource(body), color = c.text2, textAlign = TextAlign.Center)
                } else {
                    Text(stringResource(R.string.choose_theme), color = c.text, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(20.dp))
                    listOf(ThemeMode.SYSTEM to R.string.theme_system, ThemeMode.DARK to R.string.theme_dark,
                        ThemeMode.LIGHT to R.string.theme_light).forEach { (m, label) ->
                        AeroCard(Modifier.fillMaxWidth().padding(vertical = 4.dp).then(AeroClick { scope.launch { app.settings.setTheme(m) } })) {
                            Text(stringResource(label), color = c.text)
                        }
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            if (pager.currentPage < pages.size) AeroButton(stringResource(R.string.skip), primary = false) { scope.launch { go(pages.size) } }
            else Spacer(Modifier.width(1.dp))
            AeroButton(stringResource(if (pager.currentPage < pages.size) R.string.next else R.string.get_started)) {
                if (pager.currentPage < pages.size) scope.launch { go(pager.currentPage + 1) }
                else scope.launch {
                    app.settings.setOnboarded()
                    nav.navigate("home") { popUpTo("onboarding") { inclusive = true } }
                }
            }
        }
    }
}
''')

add(K + "ui/screens/Home.kt", r'''
package com.aero.share.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
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
import com.aero.share.data.PowerMode
import com.aero.share.net.Dir
import com.aero.share.net.Discovery
import com.aero.share.net.Target
import com.aero.share.net.TState
import com.aero.share.ui.*

@Composable
fun Home(app: AeroApp, nav: NavController) {
    val c = aero()
    val settings by app.settings.flow.collectAsStateWithLifecycle(initialValue = app.settingsNow)
    val found by app.discovery.devices.collectAsStateWithLifecycle()
    val status by app.discovery.status.collectAsStateWithLifecycle()
    val known by app.devices.all.collectAsStateWithLifecycle(initialValue = emptyList())
    val active by app.engine.active.collectAsStateWithLifecycle()

    LaunchedEffect(active?.state) {
        if (active?.state == TState.Transferring && active?.dir == Dir.Send) nav.navigate("transfer") { launchSingleTop = true }
    }

    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), contentPadding = PaddingValues(bottom = 24.dp)) {
        item {
            Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(painterResource(R.drawable.ic_logo), null, tint = c.accent, modifier = Modifier.size(30.dp))
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.app_name), color = c.text, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Text(app.identity.name(settings.deviceName), color = c.text2, fontSize = 12.sp)
                }
                Box(Modifier.then(AeroClick { nav.navigate("history") }).padding(8.dp)) {
                    Icon(painterResource(R.drawable.ic_history), stringResource(R.string.history), tint = c.text2, modifier = Modifier.size(22.dp))
                }
            }
            AeroCard(Modifier.fillMaxWidth().then(AeroClick { nav.navigate("send") })) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Send, null, tint = c.accent, modifier = Modifier.size(34.dp))
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(stringResource(R.string.send), color = c.text, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(stringResource(R.string.send_desc), color = c.text2, fontSize = 13.sp)
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            AeroCard(Modifier.fillMaxWidth().then(AeroClick { nav.navigate("receive") })) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(R.drawable.ic_receive), null, tint = c.accent, modifier = Modifier.size(34.dp))
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(stringResource(R.string.receive), color = c.text, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(stringResource(R.string.receive_desc), color = c.text2, fontSize = 13.sp)
                    }
                }
            }
            Spacer(Modifier.height(20.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionTitle(stringResource(R.string.nearby_devices) + "  ·  ${found.size}", Modifier.weight(1f))
                Box(Modifier.then(AeroClick {
                    app.discovery.start(app.engine.serverPort.value, app.identity.name(settings.deviceName),
                        settings.visible, settings.power == PowerMode.SAVING)
                }).padding(8.dp)) {
                    Icon(Icons.Filled.Refresh, stringResource(R.string.refresh), tint = c.accent, modifier = Modifier.size(20.dp))
                }
            }
            when (status) {
                Discovery.Status.SEARCHING -> StatusChip(stringResource(if (found.isEmpty()) R.string.searching else R.string.nearby_devices), true)
                Discovery.Status.NO_WIFI -> StatusChip(stringResource(R.string.no_wifi), false)
                Discovery.Status.HIDDEN -> StatusChip(stringResource(R.string.hidden_mode), false)
                Discovery.Status.ERROR -> StatusChip(stringResource(R.string.err_network), false)
                Discovery.Status.IDLE -> StatusChip(stringResource(R.string.inactive), false)
            }
            Spacer(Modifier.height(8.dp))
        }
        if (found.isEmpty()) {
            item {
                val (t, b) = when (status) {
                    Discovery.Status.NO_WIFI -> R.string.no_wifi to R.string.no_wifi_hint
                    Discovery.Status.HIDDEN -> R.string.hidden_mode to R.string.hidden_hint
                    else -> R.string.no_devices to R.string.no_devices_hint
                }
                EmptyState(R.drawable.ic_devices, stringResource(t), stringResource(b)) {
                    AeroButton(stringResource(R.string.send), primary = false) { nav.navigate("send") }
                }
            }
        } else items(found, key = { it.id }) { d ->
            val k = known.find { it.id == d.id }
            AeroCard(Modifier.fillMaxWidth().padding(vertical = 4.dp).then(AeroClick {
                app.pendingTarget = Target(d.host, d.port, null, null, k?.display() ?: d.name)
                nav.navigate("send")
            })) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(painterResource(R.drawable.ic_device), null, tint = c.text2, modifier = Modifier.size(26.dp))
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(k?.display() ?: d.name, color = c.text, fontWeight = FontWeight.SemiBold)
                        Text(stringResource(R.string.android_device) + " · " + stringResource(R.string.local_tls), color = c.text2, fontSize = 12.sp)
                    }
                    if (k?.trusted == true) Icon(painterResource(R.drawable.ic_shield), stringResource(R.string.trusted), tint = c.accent, modifier = Modifier.size(18.dp))
                }
            }
        }
    }
}
''')

add(T + "PathGuardTest.kt", r'''
package com.aero.share

import com.aero.share.core.PathGuard
import org.junit.Assert.*
import org.junit.Test

class PathGuardTest {
    @Test fun rejectsTraversal() {
        assertNull(PathGuard.sanitizeRelative("../evil"))
        assertNull(PathGuard.sanitizeRelative("a/../../b"))
        assertNull(PathGuard.sanitizeRelative("/absolute"))
        assertNull(PathGuard.sanitizeRelative("C:/windows"))
        assertNull(PathGuard.sanitizeRelative("a\u0000b"))
        assertNull(PathGuard.sanitizeRelative(""))
    }
    @Test fun acceptsNested() {
        assertEquals("Folder/sub/file.txt", PathGuard.sanitizeRelative("Folder//sub/./file.txt"))
        assertEquals("a/b.apk", PathGuard.sanitizeRelative("a\\b.apk"))
    }
    @Test fun uniqueNames() {
        assertEquals("file (1).txt", PathGuard.uniqueName("file.txt", setOf("file.txt")))
        assertEquals("file (2).txt", PathGuard.uniqueName("file.txt", setOf("file.txt", "file (1).txt")))
        assertEquals("file.txt", PathGuard.uniqueName("file.txt", emptySet()))
    }
}
''')

add(T + "ProtocolTest.kt", r'''
package com.aero.share

import com.aero.share.net.*
import org.junit.Assert.*
import org.junit.Test
import java.io.*

class ProtocolTest {
    @Test fun roundTripLargeSizes() {
        val bos = ByteArrayOutputStream(); val out = DataOutputStream(bos)
        val m = Msg("REQ", transferId = "t1", files = listOf(FileMeta("f1", "a/b.txt", 5_000_000_000L), FileMeta("f2", "c.bin", 7_000_000_000L)))
        Proto.write(out, m)
        val back = Proto.read<Msg>(DataInputStream(ByteArrayInputStream(bos.toByteArray())))
        assertEquals(m, back)
        assertEquals(12_000_000_000L, back.files!!.sumOf { it.size })
    }
    @Test fun oversizedFrameRejected() {
        val bos = ByteArrayOutputStream(); DataOutputStream(bos).writeInt(Proto.MAX_FRAME + 1)
        try { Proto.read<Msg>(DataInputStream(ByteArrayInputStream(bos.toByteArray()))); fail("expected IOException") }
        catch (e: IOException) { }
    }
    @Test fun qrRoundTrip() {
        val p = QrPayload("192.168.1.5", 52525, "tok123", "a".repeat(64), "POCO F6 Pro")
        assertEquals(p, QrPayload.decode(p.encode()))
        assertNull(QrPayload.decode("garbage"))
    }
}
''')

add(T + "PairingTest.kt", r'''
package com.aero.share

import com.aero.share.net.TokenStore
import org.junit.Assert.*
import org.junit.Test

class PairingTest {
    @Test fun singleUse() {
        var now = 0L
        val s = TokenStore { now }
        val t = s.issue(60_000)
        assertTrue(s.consume(t)); assertFalse(s.consume(t)); assertFalse(s.consume("unknown"))
    }
    @Test fun expiry() {
        var now = 0L
        val s = TokenStore { now }
        val t = s.issue(1_000); now = 2_000
        assertFalse(s.consume(t))
    }
}
''')

add(T + "HashFormatsTest.kt", r'''
package com.aero.share

import com.aero.share.core.Formats
import com.aero.share.core.Hash
import org.junit.Assert.*
import org.junit.Test

class HashFormatsTest {
    @Test fun sha256Vector() {
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", Hash.sha256Hex("abc".toByteArray()))
    }
    @Test fun streamingHash() {
        val data = ByteArray(1 shl 20) { (it % 251).toByte() }
        var counted = 0L
        val streamed = Hash.stream(data.inputStream(), ByteArray(64 * 1024)) { counted += it }
        assertEquals(Hash.sha256Hex(data), streamed)
        assertEquals(data.size.toLong(), counted)
    }
    @Test fun formats() {
        assertEquals("0 B", Formats.bytes(0))
        assertEquals("1.0 KB", Formats.bytes(1024))
        assertEquals("1.0 GB", Formats.bytes(1024L * 1024 * 1024))
        assertEquals("1:01", Formats.duration(61_000))
        assertEquals("1:00:00", Formats.duration(3_600_000))
    }
}
''')

add("README.md", r'''
# AERO SHARE

Share without limits. Direct, encrypted file sharing between nearby Android devices.
Free. No ads. No accounts. No cloud. Developer: **AERO**.

## Works in v1.0 (real implementations, no mockups)

- **Discovery:** mDNS/DNS-SD via `NsdManager` with a multicast lock. Real devices only.
- **Transport:** local Wi-Fi LAN or hotspot (QR / manual address). TLS-encrypted TCP:
  TLS 1.3 on Android 10+, TLS 1.2 ECDHE-ECDSA-AES-GCM on Android 8-9.
- **Security:** per-device ECDSA P-256 key in AndroidKeyStore (non-exportable), self-signed
  certificate (BouncyCastle), certificate pinning. Unknown devices confirmed by a short code;
  QR carries host, port, fingerprint and a single-use expiring token. Incoming transfers always
  need confirmation unless the device is trusted AND auto-accept was explicitly enabled.
- **Transfers:** multiple files, folders (SAF, structure preserved), installed apps (base + all
  split APKs + metadata), streaming I/O with `Long` sizes, buffers 64 KB / 256 KB / 1 MB by power
  mode, per-file SHA-256, path-traversal validation, conflict rename/skip, pending MediaStore
  writes with atomic finalization, storage checks, sequential queue, cancel, pause/resume at
  file boundaries, foreground service with progress and cancel action.
- **Storage:** `Downloads/AERO SHARE/` (MediaStore on 10+, direct path on 8-9) or any SAF tree.
  Received APKs open only through the system installer.
- **UI:** custom AERO design system, dark/light/system, 4 accents, optional translucent cards,
  reduced-motion aware, onboarding, Home/Devices/Settings, history with filters, diagnostics
  with export, full EN/UK/RU localization and per-app language switch.

## Honest limitations (roadmap, not shown as working features)

Wi-Fi Direct, Bluetooth-assisted discovery, automatic hotspot creation, mid-file resume,
multiple simultaneous recipients, compression, internet relay, plugins.
Split-APK installation needs a split installer (SAI) or adb; all parts are transferred.
mDNS can be blocked by router client isolation or unavailable on some hotspot interfaces —
QR / manual address works in those cases. Force-stop or OEM battery killers can stop background
execution; the app never claims otherwise.

## Build

CI: repository root holds the project ZIP and `.github/workflows/build.yml`. The workflow
extracts (or generates from `parts/`), creates the Gradle wrapper, runs unit tests, builds
`app-debug.apk` and uploads it as an artifact.

Android Studio: open the extracted `AERO_SHARE/` folder. AGP 8.7.3, Gradle 8.9, Kotlin 2.0.21,
compileSdk 35, minSdk 26, JDK 17.

## Architecture

Single `:app` module with clean package boundaries: `core` (pure utils, unit-tested),
`data` (Room + DataStore), `net` (protocol, TLS identity, discovery, engine), `storage`
(catalog, APKs, receiver), `service` (foreground service), `ui` (design system + screens).

## Wire protocol v1

TLS mutual auth -> `HELLO` both ways -> `REQ` (manifest) -> `ACC` -> per file:
`FILE`, raw bytes (size from manifest), `END{sha256}`, `ACK` -> `DONE` / `DONE_ACK`.
`PAUSE` / `CANCEL` between files. Control frames: 4-byte BE length + UTF-8 JSON.

## Permissions

Requested only at point of use: media read (picker categories, SAF fallback needs none),
camera (QR only), notifications (progress), storage write on Android 8-9 only,
foreground service (background transfers). Package visibility: launchable apps only.

## Testing

Automated: unit tests for path validation, protocol framing and Long sizes, QR payload,
token single-use/expiry, streaming SHA-256, formatting. `./gradlew testDebugUnitTest`.

Physical devices (required before production): two phones on one Wi-Fi; Wi-Fi without internet;
hotspot + QR; Bluetooth off; low storage; weak device; Android 8/10/14+; disconnect mid-transfer;
minimize; screen off; cancel; name conflict; corrupted hash (must never report success).

## Licenses

AndroidX / Kotlin / Compose / Room / Coil / CameraX / ZXing (Apache 2.0), BouncyCastle (MIT-style).
No analytics, no tracking, no ads. Nothing leaves your devices.
''')

# END PART 07/8
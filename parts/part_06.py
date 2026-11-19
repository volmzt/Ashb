add(K + "net/TransferEngine.kt", r'''
package com.aero.share.net

import android.content.Context
import android.net.Uri
import com.aero.share.core.Feedback
import com.aero.share.core.Hash
import com.aero.share.core.Identity
import com.aero.share.core.PathGuard
import com.aero.share.data.*
import com.aero.share.service.TransferService
import com.aero.share.storage.OutFile
import com.aero.share.storage.ReceiverStore
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.serialization.encodeToString
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.IOException
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket

enum class TState { Waiting, Preparing, Connecting, Transferring, Paused, Interrupted, Verifying, Completed, Failed, Cancelled }
enum class Dir { Send, Receive }

data class Target(val host: String, val port: Int, val fp: String? = null, val token: String? = null, val label: String)
data class SendJob(val id: String, val target: Target, val files: List<OutFile>, val resumeDone: List<String> = emptyList())
data class ReceivedFile(val name: String, val uri: Uri, val mime: String, val size: Long)
data class ErrEvent(val code: String, val time: Long)

data class Session(
    val id: String, val dir: Dir, val peerName: String, val target: Target?,
    val files: List<OutFile>?, val state: TState,
    val fileIndex: Int = 0, val fileCount: Int = 0, val fileName: String = "",
    val doneBytes: Long = 0, val totalBytes: Long = 0, val speed: Long = 0,
    val startedAt: Long = System.currentTimeMillis(), val endedAt: Long = 0,
    val errCode: String? = null, val results: List<ReceivedFile> = emptyList(),
    val doneIds: List<String> = emptyList()
) { val terminal get() = state == TState.Completed || state == TState.Failed || state == TState.Cancelled }

data class Incoming(
    val transferId: String, val peerName: String, val peerModel: String, val fp: String,
    val files: List<FileMeta>, val total: Long, val storageWarn: Boolean,
    val decision: CompletableDeferred<Boolean>
)
data class PairPrompt(val fp: String, val name: String, val decision: CompletableDeferred<Boolean>)

private class IntegrityException : Exception()

class TransferEngine(
    private val ctx: Context, private val tls: DeviceTls, private val identity: Identity,
    private val store: ReceiverStore, private val devices: DeviceRepo, private val history: HistoryRepo,
    private val settings: SettingsStore, private val scope: CoroutineScope
) {
    val tokens = TokenStore()
    private val _active = MutableStateFlow<Session?>(null); val active = _active.asStateFlow()
    private val _queue = MutableStateFlow<List<SendJob>>(emptyList()); val queue = _queue.asStateFlow()
    private val _incoming = MutableStateFlow<Incoming?>(null); val incoming = _incoming.asStateFlow()
    private val _pairing = MutableStateFlow<PairPrompt?>(null); val pairing = _pairing.asStateFlow()
    private val _serverOn = MutableStateFlow(false); val serverOn = _serverOn.asStateFlow()
    private val _receiveMode = MutableStateFlow(false); val receiveMode = _receiveMode.asStateFlow()
    private val _errors = MutableStateFlow<List<ErrEvent>>(emptyList()); val errors = _errors.asStateFlow()
    val serverPort = MutableStateFlow(0)

    private var serverSocket: SSLServerSocket? = null
    private var serverJob: Job? = null
    private val sendChannel = Channel<SendJob>(Channel.UNLIMITED)
    @Volatile private var pauseFlag = false
    @Volatile private var cancelFlag = false
    @Volatile private var currentSocket: SSLSocket? = null
    @Volatile private var foreground = false
    private var lastBytes = 0L
    private var cfg = AppSettings()
    private val pausedReceives = ConcurrentHashMap<String, List<String>>()

    init {
        scope.launch { settings.flow.collect { cfg = it } }
        scope.launch { for (j in sendChannel) { _queue.update { q -> q - j }; runSend(j) } }
        scope.launch {
            while (isActive) {
                delay(500)
                _active.update { s ->
                    if (s == null || s.state != TState.Transferring) s
                    else s.copy(speed = ((s.doneBytes - lastBytes) * 2).also { lastBytes = s.doneBytes })
                }
            }
        }
    }

    private fun err(code: String) { _errors.update { (listOf(ErrEvent(code, System.currentTimeMillis())) + it).take(20) } }
    private fun setState(st: TState, errCode: String? = null) = _active.update {
        it?.copy(state = st, errCode = errCode ?: it.errCode,
            endedAt = if (st == TState.Completed || st == TState.Failed || st == TState.Cancelled) System.currentTimeMillis() else it.endedAt)
    }

    fun enqueueSend(target: Target, files: List<OutFile>) {
        val job = SendJob(UUID.randomUUID().toString(), target, files)
        _queue.update { it + job }; sendChannel.trySend(job)
    }
    fun pause() { pauseFlag = true }
    fun resume() {
        val s = _active.value ?: return
        if (s.dir != Dir.Send || s.state != TState.Paused || s.target == null || s.files == null) return
        pauseFlag = false
        sendChannel.trySend(SendJob(s.id, s.target, s.files, s.doneIds)); setState(TState.Waiting)
    }
    fun cancel() { cancelFlag = true; runCatching { currentSocket?.close() } }
    fun dismissTerminal() { if (_active.value?.terminal == true) _active.value = null }
    fun acceptIncoming(ok: Boolean) { _incoming.value?.decision?.complete(ok); _incoming.value = null }
    fun answerPairing(ok: Boolean) { _pairing.value?.decision?.complete(ok); _pairing.value = null }
    fun setReceiveMode(on: Boolean) { _receiveMode.value = on; syncServer() }
    fun setForeground(fg: Boolean) { foreground = fg; syncServer() }

    private fun syncServer() {
        val want = _receiveMode.value || (foreground && cfg.visible) ||
            _active.value?.terminal == false || pausedReceives.isNotEmpty()
        if (want && serverJob == null) startServer()
        if (!want && serverJob != null) stopServer()
        TransferService.sync(ctx)
    }

    private fun startServer() {
        serverJob = scope.launch(Dispatchers.IO) {
            try {
                val captured = AtomicReference<String?>(null)
                val ss = tls.context(null, captured).serverSocketFactory.createServerSocket(0) as SSLServerSocket
                ss.needClientAuth = true
                serverSocket = ss; serverPort.value = ss.localPort; _serverOn.value = true
                while (isActive) {
                    val sock = try { ss.accept() as SSLSocket } catch (e: IOException) { break }
                    launch {
                        try {
                            sock.soTimeout = 60_000
                            tls.applyProtocols(sock); sock.startHandshake()
                            val fp = Hash.sha256Hex(sock.session.peerCertificates[0].encoded)
                            handleReceive(sock, fp)
                        } catch (e: Exception) { runCatching { sock.close() } }
                    }
                }
            } catch (e: Exception) { err("server_start") }
            finally { _serverOn.value = false; serverPort.value = 0 }
        }
    }

    private fun stopServer() {
        serverJob?.cancel(); serverJob = null
        runCatching { serverSocket?.close() }; serverSocket = null
        _serverOn.value = false; serverPort.value = 0
    }

    private suspend fun ensureKnown(fp: String, id: String, name: String, model: String, viaToken: Boolean): Boolean {
        val known = devices.byFp(fp)
        if (known?.blocked == true) return false
        if (known != null || viaToken) { devices.touch(fp, id, name, model); return true }
        val d = CompletableDeferred<Boolean>()
        _pairing.value = PairPrompt(fp, name, d)
        val ok = withTimeoutOrNull(60_000) { d.await() } ?: false
        _pairing.value = null
        if (ok) devices.touch(fp, id, name, model)
        return ok
    }

    private fun record(s: Session) {
        scope.launch {
            history.add(HistoryEntity(
                ts = System.currentTimeMillis(), direction = s.dir.name, peer = s.peerName,
                files = s.fileCount, bytes = s.doneBytes,
                durationMs = (if (s.endedAt > 0) s.endedAt else System.currentTimeMillis()) - s.startedAt,
                status = s.state.name,
                urisJson = Proto.json.encodeToString(s.results.map { it.uri.toString() })
            ))
        }
    }

    private fun fail(code: String, logCode: String) {
        err(logCode); setState(TState.Failed, code)
        _active.value?.let { record(it) }; Feedback.failure(ctx, cfg)
    }

    private suspend fun runSend(job: SendJob) = withContext(Dispatchers.IO) {
        pauseFlag = false; cancelFlag = false; lastBytes = 0
        val prev = _active.value
        val base = if (prev?.id == job.id) prev else null
        val remaining = job.files.filter { it.id !in job.resumeDone }.sumOf { it.size }
        _active.value = Session(job.id, Dir.Send, job.target.label, job.target, job.files, TState.Connecting,
            fileCount = job.files.size, totalBytes = remaining + (base?.doneBytes ?: 0),
            doneBytes = base?.doneBytes ?: 0, doneIds = job.resumeDone,
            startedAt = base?.startedAt ?: System.currentTimeMillis())
        var sock: SSLSocket? = null
        try {
            val captured = AtomicReference<String?>(null)
            sock = tls.context(job.target.fp, captured).socketFactory.createSocket() as SSLSocket
            currentSocket = sock
            tls.applyProtocols(sock)
            sock.connect(InetSocketAddress(job.target.host, job.target.port), cfg.timeoutSec * 1000)
            sock.soTimeout = 60_000; sock.startHandshake()
            val fp = captured.get() ?: throw IOException("No peer certificate")
            val out = DataOutputStream(sock.getOutputStream().buffered(cfg.chunkSize()))
            val inp = DataInputStream(sock.getInputStream().buffered(cfg.chunkSize()))
            Proto.write(out, Msg("HELLO", id = identity.id, name = identity.name(cfg.deviceName), model = identity.model, token = job.target.token))
            val peer = Proto.read<Msg>(inp)
            if (peer.type != "HELLO" || peer.v != Proto.VERSION) throw IOException("Protocol mismatch")
            val peerName = peer.name ?: job.target.label
            _active.update { it?.copy(peerName = peerName) }
            if (!ensureKnown(fp, peer.id ?: "", peerName, peer.model ?: "", job.target.token != null)) {
                fail("err_blocked", "blocked"); return@withContext
            }
            setState(TState.Transferring)
            Proto.write(out, Msg("REQ", transferId = job.id, files = job.files.map { FileMeta(it.id, it.path, it.size) }, resumeDone = job.resumeDone))
            val acc = Proto.read<Msg>(inp)
            if (acc.type != "ACC" || acc.ok != true) { fail(acc.reason ?: "err_declined", acc.reason ?: "declined"); return@withContext }
            val buf = ByteArray(cfg.chunkSize())
            val done = job.resumeDone.toMutableList()
            for ((idx, f) in job.files.withIndex()) {
                if (f.id in done) continue
                if (cancelFlag) throw CancellationException()
                if (pauseFlag) {
                    Proto.write(out, Msg("PAUSE", transferId = job.id))
                    _active.update { it?.copy(state = TState.Paused, doneIds = done.toList()) }
                    return@withContext
                }
                _active.update { it?.copy(fileIndex = idx + 1, fileName = f.path.substringAfterLast('/')) }
                Proto.write(out, Msg("FILE", id = f.id))
                val md = java.security.MessageDigest.getInstance("SHA-256")
                f.open(ctx).use { input ->
                    var left = f.size
                    while (left > 0) {
                        if (cancelFlag) throw CancellationException()
                        val n = input.read(buf, 0, minOf(buf.size.toLong(), left).toInt())
                        if (n < 0) throw IOException("Source truncated")
                        out.write(buf, 0, n); md.update(buf, 0, n); left -= n
                        _active.update { s -> s?.copy(doneBytes = s.doneBytes + n) }
                    }
                }
                out.flush()
                Proto.write(out, Msg("END", id = f.id, sha256 = Hash.hex(md.digest())))
                val ack = Proto.read<Msg>(inp)
                if (ack.type != "ACK" || ack.ok != true) { fail("err_integrity", "integrity"); return@withContext }
                done.add(f.id); _active.update { it?.copy(doneIds = done.toList()) }
            }
            Proto.write(out, Msg("DONE", transferId = job.id))
            Proto.read<Msg>(inp)
            setState(TState.Completed); record(_active.value!!); Feedback.success(ctx, cfg)
        } catch (e: CancellationException) {
            runCatching { sock?.let { Proto.write(DataOutputStream(it.getOutputStream()), Msg("CANCEL", transferId = job.id)) } }
            setState(TState.Cancelled); _active.value?.let { record(it) }
        } catch (e: Exception) {
            if (cancelFlag) { setState(TState.Cancelled); _active.value?.let { record(it) } }
            else {
                val code = when (e) {
                    is SocketTimeoutException -> "err_timeout"
                    is java.net.ConnectException, is java.net.NoRouteToHostException -> "err_unavailable"
                    is javax.net.ssl.SSLHandshakeException -> if (job.target.fp != null) "err_pairing" else "err_network"
                    else -> "err_network"
                }
                fail(code, code)
            }
        } finally {
            currentSocket = null; runCatching { sock?.close() }; syncServer()
        }
    }

    private suspend fun handleReceive(sock: SSLSocket, fp: String) {
        val inp = DataInputStream(sock.getInputStream().buffered(cfg.chunkSize()))
        val out = DataOutputStream(sock.getOutputStream().buffered(cfg.chunkSize()))
        var currentDest: ReceiverStore.Dest? = null
        try {
            val hello = Proto.read<Msg>(inp)
            if (hello.type != "HELLO" || hello.v != Proto.VERSION) { Proto.write(out, Msg("ACC", ok = false, reason = "err_invalid")); return }
            val known = devices.byFp(fp)
            if (known?.blocked == true) { Proto.write(out, Msg("ACC", ok = false, reason = "err_blocked")); return }
            val viaToken = hello.token?.let { tokens.consume(it) } == true
            Proto.write(out, Msg("HELLO", id = identity.id, name = identity.name(cfg.deviceName), model = identity.model))
            val peerName = hello.name ?: "?"
            if (!ensureKnown(fp, hello.id ?: "", peerName, hello.model ?: "", viaToken)) {
                Proto.write(out, Msg("ACC", ok = false, reason = "err_blocked")); return
            }
            val req = Proto.read<Msg>(inp)
            val files = req.files
            if (req.type != "REQ" || files == null || files.isEmpty() || files.size > 5000 ||
                files.any { PathGuard.sanitizeRelative(it.path) == null || it.size < 0 }) {
                Proto.write(out, Msg("ACC", ok = false, reason = "err_invalid")); err("invalid_manifest"); return
            }
            val tid = req.transferId ?: UUID.randomUUID().toString()
            val resumeDone = req.resumeDone ?: emptyList()
            val resumed = pausedReceives.remove(tid)
            if (resumeDone.isNotEmpty() && resumed == null) { Proto.write(out, Msg("ACC", ok = false, reason = "resume_unavailable")); return }
            val busy = _active.value?.let { !it.terminal && it.state != TState.Paused } == true
            if (busy) { Proto.write(out, Msg("ACC", ok = false, reason = "err_busy")); return }
            val total = files.filter { it.id !in resumeDone }.sumOf { it.size }
            val free = store.free()
            if (total > free) { Proto.write(out, Msg("ACC", ok = false, reason = "storage_low")); err("storage_low"); return }
            if (!(known?.trusted == true && cfg.autoAcceptTrusted)) {
                val d = CompletableDeferred<Boolean>()
                _incoming.value = Incoming(tid, peerName, hello.model ?: "", fp, files, total, total > free * 9 / 10, d)
                TransferService.sync(ctx)
                val ok = withTimeoutOrNull(60_000) { d.await() } ?: false
                _incoming.value = null
                if (!ok) { Proto.write(out, Msg("ACC", ok = false, reason = "err_declined")); return }
            }
            Proto.write(out, Msg("ACC", ok = true))
            lastBytes = 0
            _active.value = Session(tid, Dir.Receive, peerName, null, null, TState.Transferring,
                fileCount = files.size, totalBytes = total, doneIds = resumeDone)
            TransferService.sync(ctx)
            val buf = ByteArray(cfg.chunkSize())
            val results = ArrayList<ReceivedFile>()
            val done = resumeDone.toMutableList()
            var idx = 0

            suspend fun receiveFile(id: String) {
                val meta = files.firstOrNull { it.id == id } ?: throw IOException("Unknown file id")
                idx++
                _active.update { it?.copy(fileIndex = idx, fileName = meta.path.substringAfterLast('/')) }
                val d = store.open(meta.path, meta.size, cfg.receiveTreeUri, cfg.conflict)
                currentDest = d
                val md = java.security.MessageDigest.getInstance("SHA-256")
                var left = meta.size
                d.out.use { o ->
                    while (left > 0) {
                        val n = inp.read(buf, 0, minOf(buf.size.toLong(), left).toInt())
                        if (n < 0) throw IOException("Stream truncated")
                        if (!d.skipped) { o.write(buf, 0, n); md.update(buf, 0, n) }
                        left -= n
                        _active.update { s -> s?.copy(doneBytes = (s.doneBytes ?: 0) + n) }
                    }
                }
                setState(TState.Verifying)
                val end = Proto.read<Msg>(inp)
                val ok = end.type == "END" && (d.skipped || Hash.hex(md.digest()).equals(end.sha256 ?: "", true))
                if (!ok) {
                    d.abort(); currentDest = null
                    Proto.write(out, Msg("ACK", id = id, ok = false)); throw IntegrityException()
                }
                d.finalize(); currentDest = null
                if (!d.skipped) results.add(ReceivedFile(meta.path.substringAfterLast('/'), d.uri, store.mimeOf(meta.path), meta.size))
                done.add(id)
                Proto.write(out, Msg("ACK", id = id, ok = true, skipped = d.skipped))
                setState(TState.Transferring)
                _active.update { it?.copy(doneIds = done.toList(), results = results.toList()) }
            }

            while (true) {
                val m = Proto.read<Msg>(inp)
                 (m.type) {
                    "FILE" -> receiveFile(m.id ?: throw IOException("No file id"))
                    "DONE" -> {
                        Proto.write(out, Msg("DONE_ACK", transferId = tid))
                        setState(TState.Completed); record(_active.value!!); Feedback.success(ctx, cfg); return
                    }
                    "PAUSE" -> { pausedReceives[tid] = done.toList(); setState(TState.Paused); return }
                    "CANCEL" -> { setState(TState.Cancelled); record(_active.value!!); return }
                    else -> throw IOException("Bad frame")
                }
            }
        } catch (e: IntegrityException) {
            fail("err_integrity", "integrity")
        } catch (e: Exception) {
            currentDest?.let { d -> if (cfg.cleanupTemp) d.abort() else runCatching { d.finalize() } }
            val s = _active.value
            if (s != null && !s.terminal && s.state != TState.Paused) {
                err("network"); setState(TState.Interrupted, "err_network"); record(s)
            }
        } finally { runCatching { sock.close() }; syncServer() }
    }
}
''')

add(K + "service/TransferService.kt", r'''
package com.aero.share.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.aero.share.AeroApp
import com.aero.share.MainActivity
import com.aero.share.R
import com.aero.share.core.Formats
import com.aero.share.net.Dir
import com.aero.share.net.TState
import kotlinx.coroutines.*

class TransferService : Service() {
    companion object {
        const val CH_TRANSFER = "transfers"; const val CH_INCOMING = "incoming"
        const val N_PROGRESS = 1; const val N_INCOMING = 2
        const val ACTION_CANCEL = "com.aero.share.CANCEL"
        fun createChannels(ctx: Context) {
            val nm = ctx.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(CH_TRANSFER, ctx.getString(R.string.channel_transfers), NotificationManager.IMPORTANCE_LOW))
            nm.createNotificationChannel(NotificationChannel(CH_INCOMING, ctx.getString(R.string.channel_incoming), NotificationManager.IMPORTANCE_HIGH))
        }
        fun sync(ctx: Context) {
            val app = ctx.applicationContext as AeroApp
            val s = app.engine.active.value
            if (app.engine.receiveMode.value || (s != null && !s.terminal))
                ContextCompat.startForegroundService(ctx, Intent(ctx, TransferService::class.java))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var loopJob: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_CANCEL) { (application as AeroApp).engine.cancel(); return START_NOT_STICKY }
        val type = if (Build.VERSION.SDK_INT >= 29) ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0
        ServiceCompat.startForeground(this, N_PROGRESS, buildProgress(), type)
        if (loopJob == null) loopJob = scope.launch {
            val app = application as AeroApp
            var last = 0L
            while (isActive) {
                val s = app.engine.active.value
                val nm = getSystemService(NotificationManager::class.java)
                val now = System.currentTimeMillis()
                if (now - last > 900) {
                    last = now
                    if (app.settingsNow.notifications && app.settingsNow.progressNotif) nm.notify(N_PROGRESS, buildProgress())
                }
                val inc = app.engine.incoming.value
                if (inc != null && app.settingsNow.notifications) {
                    val pi = PendingIntent.getActivity(this@TransferService, 0, Intent(this@TransferService, MainActivity::class.java),
                        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
                    nm.notify(N_INCOMING, NotificationCompat.Builder(this@TransferService, CH_INCOMING)
                        .setSmallIcon(R.drawable.ic_receive).setContentTitle(getString(R.string.incoming_title))
                        .setContentText(getString(R.string.notif_incoming, inc.peerName))
                        .setContentIntent(pi).setAutoCancel(true).build())
                } else nm.cancel(N_INCOMING)
                if (s == null && !app.engine.receiveMode.value) {
                    ServiceCompat.stopForeground(this@TransferService, ServiceCompat.STOP_FOREGROUND_REMOVE)
                    stopSelf(); return@launch
                }
                delay(500)
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() { scope.cancel(); super.onDestroy() }

    private fun buildProgress(): Notification {
        val app = application as AeroApp
        val s = app.engine.active.value
        val title: String; val text: String; var progress = 0; var indet = false
        when {
            s != null && (s.state == TState.Transferring || s.state == TState.Verifying) -> {
                title = getString(if (s.dir == Dir.Send) R.string.notif_sending else R.string.notif_receiving)
                text = "${Formats.bytes(s.doneBytes)} / ${Formats.bytes(s.totalBytes)} · ${Formats.speed(s.speed)}"
                progress = if (s.totalBytes > 0) (s.doneBytes * 1000 / s.totalBytes).toInt() else 0
            }
            s?.state == TState.Completed -> { title = getString(R.string.notif_done); text = s.peerName }
            s?.state == TState.Failed || s?.state == TState.Interrupted -> { title = getString(R.string.notif_failed); text = s.peerName }
            else -> { title = getString(R.string.app_name); text = getString(R.string.notif_waiting); indet = true }
        }
        val pi = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
         cancel = PendingIntent.getService(this, 1, Intent(this, TransferService::class.java).setAction(ACTION_CANCEL),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val b = NotificationCompat.Builder(this, CH_TRANSFER)
            .setSmallIcon(R.drawable.ic_logo).setContentTitle(title).setContentText(text)
            .setContentIntent(pi).setOngoing(true).setOnlyAlertOnce(true)
        if (s != null && !s.terminal) b.addAction(R.drawable.ic_pause, getString(R.string.cancel), cancel)
        if (indet) b.setProgress(0, 0, true) else b.setProgress(1000, progress, false)
        return b.build()
    }
}
''')

# END PART 06/8
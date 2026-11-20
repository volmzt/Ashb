add(K + "net/Protocol.kt", r'''
package com.aero.share.net

import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.IOException

/**
 * AERO wire protocol v1. TLS mutual auth, then length-prefixed JSON control frames
 * (4-byte big-endian length + UTF-8). File bytes stream raw between FILE and END.
 * One Msg type carries every control message; `type` discriminates.
 */
object Proto {
    const val VERSION = 1
    const val MAX_FRAME = 4 shl 20
    val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    inline fun <reified T> write(out: DataOutputStream, msg: T) {
        val b = json.encodeToString(msg).toByteArray(Charsets.UTF_8)
        if (b.size > MAX_FRAME) throw IOException("Frame too large")
        out.writeInt(b.size); out.write(b); out.flush()
    }
    inline fun <reified T> read(inp: DataInputStream): T {
        val n = inp.readInt()
        if (n <= 0 || n > MAX_FRAME) throw IOException("Bad frame size: $n")
        val b = ByteArray(n); inp.readFully(b)
        return json.decodeFromString(String(b, Charsets.UTF_8))
    }
}

@Serializable data class FileMeta(val id: String, val path: String, val size: Long)

@Serializable data class Msg(
    val type: String,
    val v: Int = 1,
    val id: String? = null,
    val name: String? = null,
    val model: String? = null,
    val token: String? = null,
    val transferId: String? = null,
    val files: List<FileMeta>? = null,
    val resumeDone: List<String>? = null,
    val ok: Boolean? = null,
    val reason: String? = null,
    val sha256: String? = null,
    val skipped: Boolean? = null
)
''')

add(K + "net/Pairing.kt", r'''
package com.aero.share.net

import java.security.SecureRandom
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap

class TokenStore(private val clock: () -> Long = System::currentTimeMillis) {
    private data class T(val expires: Long, var used: Boolean)
    private val tokens = ConcurrentHashMap<String, T>()
    private val rnd = SecureRandom()
    fun issue(ttlMs: Long): String {
        val b = ByteArray(16).also { rnd.nextBytes(it) }
        val s = Base64.getUrlEncoder().withoutPadding().encodeToString(b)
        tokens[s] = T(clock() + ttlMs, false)
        tokens.entries.removeIf { it.value.expires < clock() }
        return s
    }
    fun consume(s: String): Boolean {
        val t = tokens[s] ?: return false
        if (t.used || t.expires < clock()) { tokens.remove(s); return false }
        t.used = true; tokens.remove(s); return true
    }
}

data class QrPayload(val host: String, val port: Int, val token: String, val fp: String, val name: String) {
    fun encode(): String = "AERO1:$host:$port:$token:$fp:" +
        Base64.getUrlEncoder().withoutPadding().encodeToString(name.toByteArray(Charsets.UTF_8))
    companion object {
        fun decode(s: String): QrPayload? = runCatching {
            val p = s.trim().split(":")
            if (p.size != 6 || p[0] != "AERO1") return null
            val port = p[2].toInt()
            if (port !in 1..65535 || p[3].isEmpty() || p[4].length != 64) return null
            val name = String(Base64.getUrlDecoder().decode(p[5]), Charsets.UTF_8)
            QrPayload(p[1], port, p[3], p[4], name)
        }.getOrNull()
    }
}
''')

add(K + "net/Qr.kt", r'''
package com.aero.share.net

import android.graphics.Bitmap
import android.graphics.Color
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

object Qr {
    fun bitmap(content: String, size: Int): Bitmap {
        val hints = mapOf(EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M, EncodeHintType.MARGIN to 1)
        val m = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size, hints)
        val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.RGB_565)
        for (x in 0 until size) for (y in 0 until size)
            bmp.setPixel(x, y, if (m[x, y]) Color.BLACK else Color.WHITE)
        return bmp
    }
}
''')

add(K + "net/Tls.kt", r'''
package com.aero.share.net

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import com.aero.share.core.Hash
import org.bouncycastle.asn1.x9.X9ObjectIdentifiers
import org.bouncycastle.asn1.x500.X500Name
import org.bouncycastle.asn1.x509.AlgorithmIdentifier
import org.bouncycastle.asn1.x509.SubjectPublicKeyInfo
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder
import org.bouncycastle.operator.ContentSigner
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.OutputStream
import java.math.BigInteger
import java.net.Socket
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Principal
import java.security.PrivateKey
import java.security.SecureRandom
import java.security.Signature
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.spec.ECGenParameterSpec
import java.util.Base64
import java.util.Date
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509KeyManager
import javax.net.ssl.X509TrustManager

/**
 * Per-device ECDSA P-256 identity. Private key lives in AndroidKeyStore (non-exportable).
 * Self-signed certificate built with BouncyCastle, signed by the KeyStore key.
 * TLS encryption + certificate pinning: QR/manual fingerprint mismatch fails the handshake;
 * discovered devices are confirmed by a short code before any file data is exchanged.
 */
class DeviceTls(private val ctx: Context) {
    companion object { private const val ALIAS = "aero_identity" }
    private val certFile get() = File(ctx.filesDir, "identity.crt")
    val certificate: X509Certificate by lazy { ensure() }
    val fingerprint: String by lazy { Hash.sha256Hex(certificate.encoded) }

    @Synchronized
    private fun ensure(): X509Certificate {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (certFile.exists() && ks.containsAlias(ALIAS)) {
            runCatching {
                val der = Base64.getDecoder().decode(certFile.readText().trim())
                return CertificateFactory.getInstance("X.509")
                    .generateCertificate(der.inputStream()) as X509Certificate
            }
        }
        if (!ks.containsAlias(ALIAS)) {
            KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").apply {
                initialize(
                    KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
                        .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                        .setDigests(KeyProperties.DIGEST_SHA256).build()
                )
            }.generateKeyPair()
        }
        val pub = ks.getCertificate(ALIAS).publicKey
        val priv = ks.getKey(ALIAS, null) as PrivateKey
        val signer = object : ContentSigner {
            val buf = ByteArrayOutputStream()
            override fun getAlgorithmIdentifier(): AlgorithmIdentifier =
                AlgorithmIdentifier(X9ObjectIdentifiers.ecdsa_with_SHA256)
            override fun getOutputStream(): OutputStream = buf
            override fun getSignature(): ByteArray = Signature.getInstance("SHA256withECDSA").run {
                initSign(priv); update(buf.toByteArray()); sign()
            }
        }
        val now = System.currentTimeMillis()
        val subject = X500Name("CN=AERO SHARE Device")
        val holder = JcaX509v3CertificateBuilder(
            subject, BigInteger.valueOf(now), Date(now - 86_400_000L),
            Date(now + 3650L * 86_400_000L), subject, SubjectPublicKeyInfo.getInstance(pub.encoded)
        ).build(signer)
        val cert = JcaX509CertificateConverter().getCertificate(holder)
        certFile.writeText(Base64.getEncoder().encodeToString(cert.encoded))
        return cert
    }

    private fun keyManager() = object : X509KeyManager {
        override fun getClientAliases(keyType: String?, issuers: Array<out Principal>?): Array<String> = arrayOf(ALIAS)
        override fun chooseClientAlias(keyType: Array<out String>?, issuers: Array<out Principal>?, socket: Socket?): String = ALIAS
        override fun getServerAliases(keyType: String?, issuers: Array<out Principal>?): Array<String> = arrayOf(ALIAS)
        override fun chooseServerAlias(keyType: String?, issuers: Array<out Principal>?, socket: Socket?): String = ALIAS
        override fun getCertificateChain(alias: String?): Array<X509Certificate> = arrayOf(certificate)
        override fun getPrivateKey(alias: String?): PrivateKey =
            KeyStore.getInstance("AndroidKeyStore").apply { load(null) }.getKey(ALIAS, null) as PrivateKey
    }

    fun context(expectedFp: String?, captured: AtomicReference<String?>): SSLContext {
        val tm = object : X509TrustManager {
            fun verify(chain: Array<X509Certificate>) {
                val fp = Hash.sha256Hex(chain[0].encoded)
                if (expectedFp != null && !fp.equals(expectedFp, ignoreCase = true))
                    throw CertificateException("Fingerprint mismatch")
                captured.set(fp)
            }
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) = verify(chain)
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) = verify(chain)
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        return SSLContext.getInstance("TLS").apply { init(arrayOf(keyManager()), arrayOf(tm), SecureRandom()) }
    }

    fun applyProtocols(s: SSLSocket) {
        s.enabledProtocols = if (Build.VERSION.SDK_INT >= 29) arrayOf("TLSv1.3", "TLSv1.2") else arrayOf("TLSv1.2")
    }
}
''')

add(K + "net/Discovery.kt", r'''
package com.aero.share.net

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import com.aero.share.core.Identity
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.net.NetworkInterface
import java.util.Base64

/** Real mDNS/DNS-SD discovery via NsdManager. No simulated devices. */
class Discovery(private val ctx: Context, private val identity: Identity, private val scope: CoroutineScope) {
    companion object { const val TYPE = "_aeroshare._tcp." }
    data class Found(val id: String, val name: String, val host: String, val port: Int, val service: String = "")
    enum class Status { IDLE, SEARCHING, NO_WIFI, HIDDEN, ERROR }

    private val nsd = ctx.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifi = ctx.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private var lock: WifiManager.MulticastLock? = null
    private val _devices = MutableStateFlow<List<Found>>(emptyList()); val devices = _devices.asStateFlow()
    private val _status = MutableStateFlow(Status.IDLE); val status = _status.asStateFlow()
    private var reg: NsdManager.RegistrationListener? = null
    private var disc: NsdManager.DiscoveryListener? = null
    private val resolveQueue = ArrayDeque<NsdServiceInfo>()
    @Volatile private var resolving = false
    private var ownName = ""
    private var stopJob: Job? = null

    fun hasLocalNetwork(): Boolean {
        val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = cm.getNetworkCapabilities(cm.activeNetwork)
        if (caps != null && (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))) return true
        return runCatching {
            NetworkInterface.getNetworkInterfaces().toList().any {
                it.isUp && !it.isLoopback && (it.name.startsWith("ap") || it.name.startsWith("wlan") || it.name.startsWith("swlan")) &&
                    it.inetAddresses.toList().any { a -> a.isSiteLocalAddress }
            }
        }.getOrDefault(false)
    }

    fun localAddress(): String? = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }
            .firstOrNull { it.isSiteLocalAddress && it.hostAddress?.contains('.') == true }?.hostAddress
    }.getOrNull()

    fun start(port: Int, deviceName: String, visible: Boolean, savingMode: Boolean) {
        stop()
        if (!visible) { _status.value = Status.HIDDEN; return }
        if (!hasLocalNetwork()) { _status.value = Status.NO_WIFI; return }
        if (port <= 0) { _status.value = Status.ERROR; return }
        lock = wifi.createMulticastLock("aero_discovery").apply { setReferenceCounted(false); acquire() }
        ownName = "AERO-" + identity.id.take(8)
        val info = NsdServiceInfo().apply {
            serviceName = ownName; serviceType = TYPE; setPort(port)
            setAttribute("id", identity.id)
            setAttribute("n", Base64.getEncoder().withoutPadding().encodeToString(deviceName.toByteArray(Charsets.UTF_8)))
        }
        reg = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(i: NsdServiceInfo) { ownName = i.serviceName }
            override fun onRegistrationFailed(i: NsdServiceInfo, e: Int) { _status.value = Status.ERROR }
            override fun onServiceUnregistered(i: NsdServiceInfo) {}
            override fun onUnregistrationFailed(i: NsdServiceInfo, e: Int) {}
        }
        runCatching { nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, reg) }.onFailure { _status.value = Status.ERROR }
        disc = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(t: String) { _status.value = Status.SEARCHING }
            override fun onStartDiscoveryFailed(t: String, e: Int) { _status.value = Status.ERROR }
            override fun onDiscoveryStopped(t: String) {}
            override fun onStopDiscoveryFailed(t: String, e: Int) {}
            override fun onServiceLost(i: NsdServiceInfo) { _devices.update { l -> l.filterNot { it.service == i.serviceName } } }
            override fun onServiceFound(i: NsdServiceInfo) {
                if (i.serviceType.trimEnd('.') != TYPE.trimEnd('.') || i.serviceName == ownName) return
                synchronized(resolveQueue) { resolveQueue.addLast(i); resolveNext() }
            }
        }
        runCatching { nsd.discoverServices(TYPE, NsdManager.PROTOCOL_DNS_SD, disc) }.onFailure { _status.value = Status.ERROR }
        if (savingMode) stopJob = scope.launch { delay(30_000); stop() }
    }

    @Suppress("DEPRECATION")
    private fun resolveNext() {
        if (resolving) return
        val next = synchronized(resolveQueue) { resolveQueue.removeFirstOrNull() } ?: return
        resolving = true
        runCatching {
            nsd.resolveService(next, object : NsdManager.ResolveListener {
                override fun onResolveFailed(i: NsdServiceInfo, e: Int) {
                    resolving = false; synchronized(resolveQueue) { resolveNext() }
                }
                override fun onServiceResolved(i: NsdServiceInfo) {
                    runCatching {
                        val attrs = i.attributes
                        val id = attrs["id"]?.toString(Charsets.UTF_8) ?: ""
                        val name = attrs["n"]?.let { String(Base64.getDecoder().decode(it), Charsets.UTF_8) } ?: i.serviceName
                        val host = i.host?.hostAddress
                        if (id.isNotEmpty() && id != identity.id && host != null) {
                            val f = Found(id, name, host, i.port, i.serviceName)
                            _devices.update { l -> l.filterNot { it.id == id } + f }
                        }
                    }
                    resolving = false; synchronized(resolveQueue) { resolveNext() }
                }
            })
        }.onFailure { resolving = false }
    }

    fun stop() {
        stopJob?.cancel(); stopJob = null
        runCatching { disc?.let { nsd.stopServiceDiscovery(it) } }; disc = null
        runCatching { reg?.let { nsd.unregisterService(it) } }; reg = null
        runCatching { lock?.release() }; lock = null
        synchronized(resolveQueue) { resolveQueue.clear() }
        resolving = false
        _devices.value = emptyList()
        _status.value = Status.IDLE
    }
}
''')

# END PART 05/8
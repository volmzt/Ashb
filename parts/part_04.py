add(K + "storage/Files.kt", r'''
package com.aero.share.storage

import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.documentfile.provider.DocumentFile
import com.aero.share.core.PathGuard
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.util.UUID

data class OutFile(val path: String, val size: Long, val uri: Uri? = null, val file: File? = null) {
    val id: String = UUID.randomUUID().toString()
    fun open(ctx: Context): InputStream =
        uri?.let { ctx.contentResolver.openInputStream(it)!! } ?: FileInputStream(file!!)
}

data class PickItem(val uri: Uri, val name: String, val size: Long, val date: Long, val mime: String)
enum class Cat { RECENT, IMAGES, VIDEOS, AUDIO, DOCS, DOWNLOADS }

object Catalog {
    fun items(ctx: Context, cat: Cat): List<PickItem> {
        val coll = MediaStore.Files.getContentUri("external")
        val proj = arrayOf(
            MediaStore.Files.FileColumns._ID, MediaStore.Files.FileColumns.DISPLAY_NAME,
            MediaStore.Files.FileColumns.SIZE, MediaStore.Files.FileColumns.DATE_MODIFIED,
            MediaStore.Files.FileColumns.MIME_TYPE
        )
        val sel = StringBuilder("${MediaStore.Files.FileColumns.SIZE} > 0")
        when (cat) {
            Cat.IMAGES -> sel.append(" AND ${MediaStore.Files.FileColumns.MEDIA_TYPE} = ${MediaStore.Files.FileColumns.MEDIA_TYPE_IMAGE}")
            Cat.VIDEOS -> sel.append(" AND ${MediaStore.Files.FileColumns.MEDIA_TYPE} = ${MediaStore.Files.FileColumns.MEDIA_TYPE_VIDEO}")
            Cat.AUDIO -> sel.append(" AND ${MediaStore.Files.FileColumns.MEDIA_TYPE} = ${MediaStore.Files.FileColumns.MEDIA_TYPE_AUDIO}")
            Cat.DOCS -> sel.append(" AND (${MediaStore.Files.FileColumns.MIME_TYPE} LIKE 'application/%' OR ${MediaStore.Files.FileColumns.MIME_TYPE} LIKE 'text/%')")
            Cat.DOWNLOADS -> if (Build.VERSION.SDK_INT >= 29)
                sel.append(" AND ${MediaStore.Files.FileColumns.RELATIVE_PATH} LIKE 'Download/%'")
            else
                @Suppress("DEPRECATION")
                sel.append(" AND ${MediaStore.Files.FileColumns.DATA} LIKE '%/Download/%'")
            Cat.RECENT -> {}
        }
        val out = ArrayList<PickItem>()
        runCatching {
            ctx.contentResolver.query(coll, proj, sel.toString(), null,
                "${MediaStore.Files.FileColumns.DATE_MODIFIED} DESC LIMIT 300")?.use { c ->
                val iId = c.getColumnIndexOrThrow(proj[0]); val iN = c.getColumnIndexOrThrow(proj[1])
                val iS = c.getColumnIndexOrThrow(proj[2]); val iD = c.getColumnIndexOrThrow(proj[3])
                val iM = c.getColumnIndexOrThrow(proj[4])
                while (c.moveToNext()) {
                    val uri = Uri.withAppendedPath(coll, c.getLong(iId).toString())
                    out.add(PickItem(uri, c.getString(iN) ?: "file", c.getLong(iS), c.getLong(iD) * 1000, c.getString(iM) ?: ""))
                }
            }
        }
        return out
    }

    fun folderFiles(ctx: Context, tree: Uri): List<OutFile> {
        val root = DocumentFile.fromTreeUri(ctx, tree) ?: return emptyList()
        val rootName = PathGuard.sanitizeRelative(root.name ?: "Folder") ?: "Folder"
        val out = ArrayList<OutFile>()
        fun walk(d: DocumentFile, rel: String) {
            for (f in d.listFiles()) {
                val safe = PathGuard.sanitizeRelative(f.name ?: continue) ?: continue
                val p = "$rel/$safe"
                if (f.isDirectory) walk(f, p)
                else if (f.isFile) out.add(OutFile(p, f.length(), uri = f.uri))
            }
        }
        walk(root, rootName)
        return out
    }
}
''')

add(K + "storage/Apks.kt", r'''
package com.aero.share.storage

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.Drawable
import android.net.Uri
import android.os.Build
import com.aero.share.core.Hash
import com.aero.share.core.PathGuard
import org.json.JSONObject
import java.io.File

data class AppEntry(
    val pkg: String, val label: String, val version: String,
    val size: Long, val icon: Drawable?, val base: File, val splits: List<File>
)
data class ApkInfo(val label: String, val pkg: String, val version: String, val sha256: String, val signer: String?)

object Apks {
    @Suppress("DEPRECATION")
    fun list(ctx: Context): List<AppEntry> {
        val pm = ctx.packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val seen = HashSet<String>()
        val out = ArrayList<AppEntry>()
        for (ri in pm.queryIntentActivities(intent, 0)) {
            val ai = ri.activityInfo?.applicationInfo ?: continue
            if (!seen.add(ai.packageName)) continue
            runCatching {
                val base = File(ai.sourceDir)
                val splits = ai.splitSourceDirs?.map { File(it) } ?: emptyList()
                val pi = pm.getPackageInfo(ai.packageName, 0)
                out.add(AppEntry(ai.packageName, ai.loadLabel(pm).toString(), pi.versionName ?: "",
                    base.length() + splits.sumOf { it.length() }, ai.loadIcon(pm), base, splits))
            }
        }
        return out.sortedBy { it.label.lowercase() }
    }

    fun appFiles(ctx: Context, e: AppEntry): List<OutFile> {
        val dir = PathGuard.sanitizeRelative("${e.label}_${e.version}") ?: e.pkg
        val files = ArrayList<OutFile>()
        files.add(OutFile("$dir/base.apk", e.base.length(), file = e.base))
        e.splits.forEachIndexed { i, f -> files.add(OutFile("$dir/split_$i.apk", f.length(), file = f)) }
        val meta = JSONObject().put("package", e.pkg).put("label", e.label)
            .put("version", e.version).put("splits", e.splits.size).put("format", "aero-apk-v1").toString()
        val tmp = File(ctx.cacheDir, "apk_meta_${e.pkg}.json")
        tmp.writeText(meta)
        files.add(OutFile("$dir/aero-app.json", tmp.length(), file = tmp))
        return files
    }

    @Suppress("DEPRECATION")
    fun archiveInfo(ctx: Context, uri: Uri): ApkInfo? = runCatching {
        val tmp = File(ctx.cacheDir, "inspect.apk")
        ctx.contentResolver.openInputStream(uri)!!.use { i -> tmp.outputStream().use { o -> i.copyTo(o, 256 * 1024) } }
        val pm = ctx.packageManager
        val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
        val pi = pm.getPackageArchiveInfo(tmp.absolutePath, flags)
        val sha = tmp.inputStream().use { Hash.stream(it, ByteArray(256 * 1024)) }
        val signer = if (Build.VERSION.SDK_INT >= 28)
            pi?.signingInfo?.apkContentsSigners?.firstOrNull()?.toByteArray()?.let { Hash.sha256Hex(it) }
        else pi?.signatures?.firstOrNull()?.toByteArray()?.let { Hash.sha256Hex(it) }
        val label = pi?.applicationInfo?.loadLabel(pm)?.toString() ?: tmp.name
        tmp.delete()
        ApkInfo(label, pi?.packageName ?: "?", pi?.versionName ?: "?", sha, signer)
    }.getOrNull()
}
''')

add(K + "storage/Receiver.kt", r'''
package com.aero.share.storage

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import androidx.documentfile.provider.DocumentFile
import com.aero.share.core.PathGuard
import com.aero.share.data.ConflictMode
import java.io.File
import java.io.OutputStream

class ReceiverStore(private val ctx: Context) {
    class Dest(
        val uri: Uri, val out: OutputStream, val skipped: Boolean,
        private val fin: () -> Unit, private val ab: () -> Unit
    ) {
        fun finalize() = fin()
        fun abort() = ab()
    }

    fun free(): Long = StatFs(Environment.getDataDirectory().path).availableBytes

    fun mimeOf(name: String): String =
        MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase())
            ?: "application/octet-stream"

    @Suppress("DEPRECATION")
    private fun existingNames(subDir: String, treeUri: String): Set<String> {
        val names = HashSet<String>()
        if (treeUri.isNotEmpty()) {
            var d = DocumentFile.fromTreeUri(ctx, Uri.parse(treeUri))
            for (p in subDir.split('/').filter { it.isNotEmpty() }) d = d?.findFile(p)
            d?.listFiles()?.forEach { it.name?.let(names::add) }
        } else if (Build.VERSION.SDK_INT >= 29) {
            val rel = Environment.DIRECTORY_DOWNLOADS + "/AERO SHARE/" + if (subDir.isEmpty()) "" else "$subDir/"
            ctx.contentResolver.query(
                MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                arrayOf(MediaStore.Downloads.DISPLAY_NAME),
                "${MediaStore.Downloads.RELATIVE_PATH} = ?", arrayOf(rel), null
            )?.use { c -> while (c.moveToNext()) names.add(c.getString(0)) }
        } else {
            val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "AERO SHARE/$subDir")
            dir.listFiles()?.forEach { names.add(it.name) }
        }
        return names
    }

    @Suppress("DEPRECATION")
    fun open(relPath: String, size: Long, treeUri: String, conflict: ConflictMode): Dest {
        val safe = PathGuard.sanitizeRelative(relPath) ?: throw SecurityException("Bad path")
        val subDir = safe.substringBeforeLast('/', "")
        val rawName = safe.substringAfterLast('/')
        val taken = existingNames(subDir, treeUri)
        if (conflict == ConflictMode.SKIP && rawName in taken) {
            return Dest(Uri.EMPTY, object : OutputStream() { override fun write(b: Int) {} }, true, {}, {})
        }
        val name = PathGuard.uniqueName(rawName, taken)
        val mime = mimeOf(name)
        if (treeUri.isNotEmpty()) {
            var d = DocumentFile.fromTreeUri(ctx, Uri.parse(treeUri))!!
            for (p in subDir.split('/').filter { it.isNotEmpty() })
                d = d.findFile(p)?.takeIf { it.isDirectory } ?: d.createDirectory(p)!!
            val doc = d.createFile(mime, name)!!
            val out = ctx.contentResolver.openOutputStream(doc.uri)!!
            return Dest(doc.uri, out, false, {}, { doc.delete() })
        }
        if (Build.VERSION.SDK_INT >= 29) {
            val rel = Environment.DIRECTORY_DOWNLOADS + "/AERO SHARE/" + if (subDir.isEmpty()) "" else "$subDir/"
            val cv = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mime)
                put(MediaStore.Downloads.RELATIVE_PATH, rel)
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val uri = ctx.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv)!!
            val out = ctx.contentResolver.openOutputStream(uri)!!
            return Dest(uri, out, false, {
                ctx.contentResolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
            }, { ctx.contentResolver.delete(uri, null, null) })
        }
        val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "AERO SHARE/$subDir")
        dir.mkdirs()
        val part = File(dir, "$name.part")
        val fin = File(dir, name)
        return Dest(
            FileProvider.getUriForFile(ctx, ctx.packageName + ".files", fin),
            part.outputStream(), false, { part.renameTo(fin) }, { part.delete() }
        )
    }

    fun destLabel(treeUri: String): String =
        if (treeUri.isEmpty()) "Downloads/AERO SHARE"
        else DocumentFile.fromTreeUri(ctx, Uri.parse(treeUri))?.name ?: "Downloads/AERO SHARE"
}
''')

# END PART 04/8
package com.vmharness.android.data.store

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext

/**
 * Secure storage for the paired desktop's API key and connection details.
 * Backed by Android Keystore + EncryptedSharedPreferences (AES-256-GCM for values,
 * AES-256-SIV for keys).
 */
class PairingStore(
    @ApplicationContext private val context: Context,
) {
    companion object {
        private const val PREFS_NAME = "vmharness_paired_prefs"
        private const val KEY_API_KEY = "api_key"
        private const val KEY_HOST = "host"
        private const val KEY_IP = "ip"
        private const val KEY_TAILNET = "tailnet"
        private const val KEY_MACHINE_ID = "machine_id"
        private const val KEY_DISPLAY_NAME = "display_name"
        private const val KEY_CREATED = "created"
        private const val KEY_EXPIRES = "expires"
        private const val KEY_PORT = "port"
        private const val KEY_DESKTOP_PUBLIC_KEY = "desktop_public_key_pem"
        private const val KEY_PENDING_TOKEN = "pending_token"
    }

    private val masterKey: MasterKey by lazy {
        MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
    }

    @Volatile
    private var prefs: android.content.SharedPreferences? = null

    private fun getPrefs(): android.content.SharedPreferences {
        return prefs ?: EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        ).also { prefs = it }
    }

    // ── API key & connection details ──────────────────────────────────────────

    var apiKey: String?
        get() = getPrefs().getString(KEY_API_KEY, null)
        set(value) = getPrefs().edit().putString(KEY_API_KEY, value).apply()

    var host: String?
        get() = getPrefs().getString(KEY_HOST, null)
        set(value) = getPrefs().edit().putString(KEY_HOST, value).apply()

    var ip: String?
        get() = getPrefs().getString(KEY_IP, null)
        set(value) = getPrefs().edit().putString(KEY_IP, value).apply()

    var port: Int
        get() = getPrefs().getInt(KEY_PORT, 8443)
        set(value) = getPrefs().edit().putInt(KEY_PORT, value).apply()

    var tailnet: String?
        get() = getPrefs().getString(KEY_TAILNET, null)
        set(value) = getPrefs().edit().putString(KEY_TAILNET, value).apply()

    var machineId: String?
        get() = getPrefs().getString(KEY_MACHINE_ID, null)
        set(value) = getPrefs().edit().putString(KEY_MACHINE_ID, value).apply()

    var displayName: String?
        get() = getPrefs().getString(KEY_DISPLAY_NAME, null)
        set(value) = getPrefs().edit().putString(KEY_DISPLAY_NAME, value).apply()

    var created: Long
        get() = getPrefs().getLong(KEY_CREATED, 0)
        set(value) = getPrefs().edit().putLong(KEY_CREATED, value).apply()

    var expires: Long
        get() = getPrefs().getLong(KEY_EXPIRES, 0)
        set(value) = getPrefs().edit().putLong(KEY_EXPIRES, value).apply()

    // ── Desktop public key (PEM) ───────────────────────────────────────────────

    var desktopPublicKeyPem: String?
        get() = getPrefs().getString(KEY_DESKTOP_PUBLIC_KEY, null)
        set(value) = getPrefs().edit().putString(KEY_DESKTOP_PUBLIC_KEY, value).apply()

    // ── Pending token (for QR/manual entry before verification) ───────────────

    var pendingToken: String?
        get() = getPrefs().getString(KEY_PENDING_TOKEN, null)
        set(value) = getPrefs().edit().putString(KEY_PENDING_TOKEN, value).apply()

    // ── Pairing state ──────────────────────────────────────────────────────────

    val isPaired: Boolean
        get() = apiKey != null && host != null

    val isExpired: Boolean
        get() = expires > 0 && expires < System.currentTimeMillis() / 1000

    val serverUrl: String
        get() {
            val targetIp = ip?.let { if (it.startsWith("100.")) it else host } ?: host
            return "http://$targetIp:$port"
        }

    // ── Clear ──────────────────────────────────────────────────────────────────

    fun clear() {
        getPrefs().edit().clear().apply()
    }

    // ── Save pairing from a verified payload ───────────────────────────────────

    fun savePairing(
        host: String,
        ip: String,
        port: Int,
        tailnet: String,
        machineId: String,
        displayName: String,
        apiKey: String,
        created: Long,
        expires: Long,
        desktopPublicKeyPem: String? = null,
    ) {
        this.host = host
        this.ip = ip
        this.port = port
        this.tailnet = tailnet
        this.machineId = machineId
        this.displayName = displayName
        this.apiKey = apiKey
        this.created = created
        this.expires = expires
        if (desktopPublicKeyPem != null) {
            this.desktopPublicKeyPem = desktopPublicKeyPem
        }
        pendingToken = null  // consume the token
    }
}

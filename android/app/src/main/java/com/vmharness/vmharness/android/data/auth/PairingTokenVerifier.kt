package com.vmharness.android.data.auth

import android.util.Base64
import com.google.crypto.tink.subtle.Ed25519Verify
import com.vmharness.android.data.model.PairingPayload
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.data.api.PairingException
import com.vmharness.android.data.api.TailscaleNotRunningException
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.nio.charset.StandardCharsets

/**
 * Ed25519 pairing token verifier.
 *
 * Verifies that a pairing token was signed by the desktop's Ed25519 private key,
 * validates the embedded payload fields, and extracts the API key secret.
 *
 * Uses Tink's Ed25519Verify for cross-version Android support.
 */
class PairingTokenVerifier @Inject constructor(
    private val pairingStore: PairingStore,
) {
    companion object {
        private const val VERSION = "v1"
        private const val PURPOSE = "mobile-pairing"
        private const val TAILSCALE_IP_PREFIX = "100."

        private const val KEY_HEADER = "-----BEGIN PUBLIC KEY-----"
        private const val KEY_FOOTER = "-----END PUBLIC KEY-----"
    }

    suspend fun verify(token: String): PairingPayload {
        val parts = token.split(".")
        if (parts.size != 2 || parts[0].isBlank() || parts[1].isBlank()) {
            throw PairingException(
                "Invalid token format. Expected: signature.payload (two base64url strings separated by a dot).\n\n" +
                "Example: AAAA...base64...xyz.BBBB...base64...abc\n\n" +
                "Copy the full token from the desktop app and paste it exactly."
            )
        }
        val sigB64 = parts[0]
        val payB64 = parts[1]

        val sigBytes = decodeBase64Url(sigB64)
        val payBytes = decodeBase64Url(payB64)

        // Decode payload first to get host for key fetch
        val payloadJson = String(payBytes, StandardCharsets.UTF_8)
        val tempPayload = parsePayloadJson(payloadJson)

        // Fetch public key and verify
        var publicKeyBytes = getPublicKeyBytes()
        if (publicKeyBytes == null) {
            if (tempPayload != null && tempPayload.ip.isNotBlank()) {
                try {
                    fetchPublicKey("http://${tempPayload.ip}:8443")
                    publicKeyBytes = getPublicKeyBytes()
                } catch (_: Exception) {}
            }
            if (publicKeyBytes == null) {
                throw PairingException(
                    "No desktop public key available. Fetch it from the desktop first " +
                    "(GET /api/v1/auth/public-key) or install the app with a baked-in key."
                )
            }
        }

        try {
            val verifier = Ed25519Verify(publicKeyBytes)
            verifier.verify(sigBytes, payBytes)
        } catch (e: Exception) {
            // Key mismatch — fetch fresh key from server and retry
            if (tempPayload != null && tempPayload.ip.isNotBlank()) {
                try {
                    fetchPublicKey("http://${tempPayload.ip}:8443")
                    val freshKey = getPublicKeyBytes()
                    if (freshKey != null) {
                        val verifier = Ed25519Verify(freshKey)
                        verifier.verify(sigBytes, payBytes)
                    } else {
                        throw PairingException("Signature verification failed: ${e.message}")
                    }
                } catch (fetchError: Exception) {
                    // Try localhost (adb reverse) as fallback
                    try {
                        fetchPublicKey("http://localhost:8443")
                        val freshKey = getPublicKeyBytes()
                        if (freshKey != null) {
                            val verifier = Ed25519Verify(freshKey)
                            verifier.verify(sigBytes, payBytes)
                        } else {
                            throw PairingException("Signature verification failed: ${e.message}")
                        }
                    } catch (localhostError: Exception) {
                        throw PairingException("Signature verification failed: ${e.message}")
                    }
                }
            } else {
                throw PairingException("Signature verification failed: ${e.message}")
            }
        }

        val payload = tempPayload ?: throw PairingException("Failed to parse pairing payload JSON")

        validatePayload(payload)
        return payload
    }

    fun tokenToUri(token: String): String = "vmharness://pair?key=$token"

    fun uriToToken(uri: String): String? {
        val u = uri.trim().removePrefix("vmharness://pair?").removePrefix("vmharness://pair")
        val param = u.split("?").getOrNull(1) ?: u
        val keyParam = param.split("&").map { it.split("=") }.find { it.getOrNull(0) == "key" }
        return keyParam?.getOrNull(1)?.takeIf { it.isNotBlank() }
    }

    suspend fun fetchPublicKey(serverUrl: String): String {
        val url = "$serverUrl/api/v1/auth/public-key"
        val client = okhttp3.OkHttpClient.Builder()
            .connectTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
            .build()
        val request = okhttp3.Request.Builder()
            .url(url)
            .header("Accept", "application/x-pem-file")
            .build()
        val response = try {
            withContext(Dispatchers.IO) {
                client.newCall(request).execute()
            }
        } catch (e: Exception) {
            throw TailscaleNotRunningException(
                "Cannot fetch public key from $url — ${e.message ?: e.javaClass.simpleName}. Is the desktop API server running and reachable via Tailscale?"
            )
        }
        if (!response.isSuccessful) {
            throw TailscaleNotRunningException("HTTP ${response.code} from $url")
        }
        val body = response.body?.string() ?: throw TailscaleNotRunningException("Empty response from $url")
        pairingStore.desktopPublicKeyPem = body
        return body
    }

    private fun getPublicKeyBytes(): ByteArray? {
        val pem = pairingStore.desktopPublicKeyPem
        android.util.Log.d("VM-Harness", "getPublicKeyBytes: pem length=${pem?.length}")
        if (pem.isNullOrBlank()) return null
        val cleaned = pem
            .trim()
            .removePrefix(KEY_HEADER)
            .removeSuffix(KEY_FOOTER)
            .replace(Regex("\\s"), "")
        val derBytes = decodeBase64(cleaned)
        android.util.Log.d("VM-Harness", "  derBytes length=${derBytes.size}")

        // Ed25519 SubjectPublicKeyInfo DER format starts with fixed ASN.1 header
        // The raw 32-byte key is at the end of the DER encoding
        // For a 32-byte Ed25519 public key, DER is typically 44 bytes (12 bytes ASN.1 header + 32 key)
        if (derBytes.size == 32) {
            return derBytes
        }
        if (derBytes.size > 32) {
            // Extract the last 32 bytes (raw key from DER)
            return derBytes.copyOfRange(derBytes.size - 32, derBytes.size)
        }
        return null
    }

    private fun decodeBase64Url(s: String): ByteArray {
        val padded = s + "=".repeat((4 - s.length % 4) % 4)
        return Base64.decode(padded, Base64.URL_SAFE)
    }

    private fun decodeBase64(s: String): ByteArray {
        val padded = s + "=".repeat((4 - s.length % 4) % 4)
        return Base64.decode(padded, Base64.DEFAULT)
    }

    private fun parsePayloadJson(json: String): PairingPayload? {
        try {
            val jsonObject = org.json.JSONObject(json)
            return PairingPayload(
                version = jsonObject.optString("v", VERSION),
                purpose = jsonObject.optString("p", PURPOSE),
                host = jsonObject.optString("h", ""),
                ip = jsonObject.optString("i", ""),
                tailnet = jsonObject.optString("t", ""),
                machineId = jsonObject.optString("m", ""),
                displayName = jsonObject.optString("n", ""),
                created = jsonObject.optLong("c", 0),
                expires = jsonObject.optLong("e", 0),
                secret = jsonObject.optString("s", ""),
            )
        } catch (e: Exception) {
            return null
        }
    }

    private fun validatePayload(p: PairingPayload) {
        if (p.version != VERSION) throw PairingException("Unsupported token version: ${p.version}")
        if (p.purpose != PURPOSE) throw PairingException("Invalid token purpose: ${p.purpose}")
        if (p.host.isBlank() || !p.host.contains(".")) throw PairingException("Invalid host: ${p.host}")
        if (!p.host.endsWith(".ts.net") && !p.host.contains(".")) throw PairingException("Host not MagicDNS: ${p.host}")
        if (p.ip.isBlank() || !p.ip.startsWith(TAILSCALE_IP_PREFIX)) throw PairingException("Invalid Tailscale IP: ${p.ip}")
        if (p.secret.isBlank()) throw PairingException("Token missing API key secret")
        if (p.expires > 0 && p.expires < System.currentTimeMillis() / 1000) throw PairingException("Token expired")
        if (p.created > System.currentTimeMillis() / 1000 + 60) throw PairingException("Token from future")
        if (p.machineId.isBlank()) throw PairingException("Token missing machine_id")
        if (p.displayName.isBlank()) throw PairingException("Token missing display_name")
    }
}

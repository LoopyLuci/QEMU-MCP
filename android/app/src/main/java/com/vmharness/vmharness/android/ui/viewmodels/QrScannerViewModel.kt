package com.vmharness.android.ui.viewmodels

import android.util.Base64
import android.util.Log
import androidx.lifecycle.ViewModel
import com.vmharness.android.data.api.PairingException
import com.vmharness.android.data.auth.PairingTokenVerifier
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

@HiltViewModel
class QrScannerViewModel @Inject constructor(
    private val verifier: PairingTokenVerifier,
) : ViewModel() {

    sealed class ScanResult {
        object Idle : ScanResult()
        data class Success(val rawValue: String) : ScanResult()
        data class Error(val msg: String) : ScanResult()
    }

    private var _scanState = MutableStateFlow<ScanResult>(ScanResult.Idle)
    val scanState: StateFlow<ScanResult> = _scanState.asStateFlow()

    fun onBarcodeDetected(rawValue: String) {
        if (_scanState.value is ScanResult.Success) return // already succeeded

        Log.d("QRScan", "Detected: $rawValue")

        // Validate the QR content before accepting
        // The desktop generates vmharness://pair?key=<token>
        // Or it could be a raw pairing token (base64url signature.payload)
        val token = if (rawValue.startsWith("vmharness://") || rawValue.startsWith("http")) {
            // Extract token from URI
            verifier.uriToToken(rawValue)
        } else {
            // Raw token
            rawValue
        }

        if (token.isNullOrBlank()) {
            _scanState = MutableStateFlow(
                ScanResult.Error("Invalid QR code: not a VM-Harness pairing code")
            )
            return
        }

        // Basic format validation (must be two base64url parts separated by '.')
        val parts = token.split(".")
        if (parts.size != 2) {
            _scanState.value = ScanResult.Error(
                "Invalid QR code: expected pairing token (signature.payload).\n" +
                "This doesn't look like a VM-Harness pairing code."
            )
            return
        }

        // Validate base64url decodability
        try {
            val sigB64 = parts[0]
            val payB64 = parts[1]
            val paddedSig = sigB64 + "=".repeat((4 - sigB64.length % 4) % 4)
            val paddedPay = payB64 + "=".repeat((4 - payB64.length % 4) % 4)
            Base64.decode(paddedSig, Base64.URL_SAFE)
            Base64.decode(paddedPay, Base64.URL_SAFE)

            // Also verify JSON payload structure
            val jsonBytes = Base64.decode(paddedPay, Base64.URL_SAFE)
            val json = String(jsonBytes, Charsets.UTF_8)
            if (!json.contains("\"v\"") || !json.contains("\"s\"")) {
                _scanState.value = ScanResult.Error("Invalid pairing payload structure")
                return
            }
        } catch (e: Exception) {
            _scanState.value = ScanResult.Error("Malformed pairing token: ${e.message}")
            return
        }

        _scanState.value = ScanResult.Success(token)
    }

    fun onPermissionDenied() {
        _scanState.value = ScanResult.Error("Camera permission denied")
    }

    fun reset() {
        _scanState.value = ScanResult.Idle
    }
}

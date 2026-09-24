package com.vmharness.android.ui.screens

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Temporary in-memory holder for scanned QR tokens, used to pass data between
 * QrScannerScreen and PairingScreen without SavedStateHandle complexity.
 * Uses a SharedFlow with replay=1 so late subscribers receive the last token.
 */
object QrTokenHolder {
    private val _flow = MutableSharedFlow<String>(replay = 1, extraBufferCapacity = 1)
    val flow: SharedFlow<String> = _flow.asSharedFlow()

    fun set(value: String?) {
        if (!value.isNullOrBlank()) {
            _flow.tryEmit(value)
        }
    }
}

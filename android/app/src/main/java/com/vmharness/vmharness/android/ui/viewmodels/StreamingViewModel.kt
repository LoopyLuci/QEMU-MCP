package com.vmharness.android.ui.viewmodels

import android.app.Application
import android.graphics.Bitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.streaming.ContinuumStreamClient
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class StreamingViewModel @Inject constructor(
    application: Application,
    private val pairingStore: PairingStore,
) : AndroidViewModel(application) {
    
    private val _connectionState = MutableStateFlow(ContinuumStreamClient.ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ContinuumStreamClient.ConnectionState> = _connectionState.asStateFlow()
    
    private val _stats = MutableStateFlow(ContinuumStreamClient.StreamStats())
    val stats: StateFlow<ContinuumStreamClient.StreamStats> = _stats.asStateFlow()
    
    private val _currentFrame = MutableStateFlow<Bitmap?>(null)
    val currentFrame: StateFlow<Bitmap?> = _currentFrame.asStateFlow()
    
    private var client: ContinuumStreamClient? = null
    private var collectionJob: kotlinx.coroutines.Job? = null
    
    fun connect(quality: Int = 85, fps: Int = 60, width: Int = 1920, height: Int = 1080) {
        collectionJob?.cancel()
        collectionJob = viewModelScope.launch {
            // Get server URL from pairing store
            val serverIp = pairingStore.ip.takeIf { !it.isNullOrBlank() } ?: "localhost"
            val wsUrl = "ws://$serverIp:8445"
            
            client = ContinuumStreamClient(
                context = getApplication(),
                serverUrl = wsUrl,
                apiKeyProvider = { pairingStore.apiKey }
            )
            
            launch { client?.connectionState?.collect { _connectionState.value = it } }
            launch { client?.frameFlow?.collect { bitmap ->
                _currentFrame.value?.recycle()
                _currentFrame.value = bitmap
            }}
            launch { client?.stats?.collect { _stats.value = it } }
            
            client?.connect(quality, fps, width, height)
        }
    }
    
    fun disconnect() {
        collectionJob?.cancel()
        client?.disconnect()
        client = null
        _currentFrame.value?.recycle()
        _currentFrame.value = null
    }
    
    fun reconnect() {
        disconnect()
        connect()
    }
    
    fun updateConfig(quality: Int, fps: Int) {
        client?.sendConfig(quality, fps)
    }
    
    fun sendMouseMove(x: Float, y: Float, relative: Boolean = false) {
        client?.sendMouseMove(x, y, relative)
    }
    
    fun sendMouseClick(button: String, pressed: Boolean, x: Float = 0f, y: Float = 0f) {
        client?.sendMouseClick(button, pressed, x, y)
    }
    
    fun sendScroll(dx: Float, dy: Float) {
        client?.sendScroll(dx, dy)
    }
    
    fun sendKey(keyCode: Int, pressed: Boolean) {
        client?.sendKey(keyCode, pressed)
    }
    
    fun showKeyboard() {
        // TODO: Show keyboard overlay
    }
    
    override fun onCleared() {
        super.onCleared()
        disconnect()
    }
}

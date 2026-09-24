package com.vmharness.android.streaming

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Continuum streaming client for Android.
 * Connects to the desktop streaming bridge via WebSocket
 * and receives real-time desktop frames.
 */
class ContinuumStreamClient(
    private val context: Context,
    private val serverUrl: String,
    private val apiKeyProvider: () -> String?,
) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()
    
    private val _frameFlow = MutableSharedFlow<Bitmap>(replay = 1, extraBufferCapacity = 3)
    val frameFlow: SharedFlow<Bitmap> = _frameFlow.asSharedFlow()
    
    private val _stats = MutableStateFlow(StreamStats())
    val stats: StateFlow<StreamStats> = _stats.asStateFlow()
    
    private var frameCount = 0
    private var lastFpsTime = System.currentTimeMillis()
    private var currentFps = 0
    
    enum class ConnectionState {
        DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, ERROR
    }
    
    data class StreamStats(
        val bytesReceived: Long = 0,
        val framesReceived: Long = 0,
        val fps: Int = 0,
        val bitrateKbps: Int = 0,
        val latencyMs: Int = 0,
        val resolution: String = "0x0",
    )
    
    data class MonitorInfo(
        val id: Int,
        val name: String,
        val x: Int,
        val y: Int,
        val width: Int,
        val height: Int,
        val isPrimary: Boolean,
    )
    
    fun connect(quality: Int = 85, fps: Int = 60, width: Int = 1920, height: Int = 1080) {
        if (_connectionState.value == ConnectionState.CONNECTED) return
        
        _connectionState.value = ConnectionState.CONNECTING
        
        val url = "$serverUrl/ws?client_id=${context.packageName}"
        val request = Request.Builder()
            .url(url)
            .addHeader("X-API-Key", apiKeyProvider() ?: "")
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket connected")
                _connectionState.value = ConnectionState.CONNECTED
                
                // Send configuration
                sendConfig(quality, fps, width, height)
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }
            
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                handleFrame(bytes.toByteArray())
            }
            
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closing: $code $reason")
                webSocket.close(1000, null)
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $code $reason")
                _connectionState.value = ConnectionState.DISCONNECTED
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket failure: ${t.message}")
                _connectionState.value = ConnectionState.ERROR
            }
        })
    }
    
    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
    }
    
    fun sendConfig(quality: Int, fps: Int, width: Int = 1920, height: Int = 1080, monitorId: Int = 0) {
        val config = """
            {
                "type": "config",
                "quality": $quality,
                "fps": $fps,
                "width": $width,
                "height": $height,
                "monitor_id": $monitorId,
                "input_enabled": true
            }
        """.trimIndent()
        webSocket?.send(config)
    }
    
    fun sendMouseMove(x: Float, y: Float, relative: Boolean = false) {
        val msg = """
            {
                "type": "input",
                "input_type": "mouse_move",
                "x": $x,
                "y": $y,
                "relative": $relative
            }
        """.trimIndent()
        webSocket?.send(msg)
    }
    
    fun sendMouseClick(button: String, pressed: Boolean, x: Float = 0f, y: Float = 0f) {
        val msg = """
            {
                "type": "input",
                "input_type": "mouse_click",
                "button": "$button",
                "pressed": $pressed,
                "x": $x,
                "y": $y
            }
        """.trimIndent()
        webSocket?.send(msg)
    }
    
    fun sendScroll(dx: Float, dy: Float) {
        val msg = """
            {
                "type": "input",
                "input_type": "scroll",
                "dx": $dx,
                "dy": $dy
            }
        """.trimIndent()
        webSocket?.send(msg)
    }
    
    fun sendKey(keyCode: Int, pressed: Boolean) {
        val msg = """
            {
                "type": "input",
                "input_type": "key",
                "key_code": $keyCode,
                "pressed": $pressed
            }
        """.trimIndent()
        webSocket?.send(msg)
    }
    
    private fun handleFrame(byteArray: ByteArray) {
        try {
            val bitmap = BitmapFactory.decodeByteArray(byteArray, 0, byteArray.size)
            
            if (bitmap != null) {
                _frameFlow.tryEmit(bitmap)
                
                frameCount++
                val now = System.currentTimeMillis()
                if (now - lastFpsTime >= 1000) {
                    currentFps = frameCount
                    frameCount = 0
                    lastFpsTime = now
                    
                    _stats.value = _stats.value.copy(
                        framesReceived = _stats.value.framesReceived + 1,
                        fps = currentFps,
                        resolution = "${bitmap.width}x${bitmap.height}",
                    )
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Frame decode error: ${e.message}")
        }
    }
    
    private fun handleMessage(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.optString("type")
            
            when (type) {
                "config_ack" -> {
                    Log.d(TAG, "Config acknowledged")
                }
                "stats" -> {
                    _stats.value = _stats.value.copy(
                        bytesReceived = json.optLong("bytes_received", 0),
                        framesReceived = json.optLong("frames_received", 0),
                    )
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Message parse error: ${e.message}")
        }
    }
    
    companion object {
        private const val TAG = "ContinuumStream"
    }
}

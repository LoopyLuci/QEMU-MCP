package com.vmharness.android.ui.screens

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.input.pointer.*
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vmharness.android.streaming.ContinuumStreamClient
import com.vmharness.android.ui.viewmodels.StreamingViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * High-performance streaming screen with input forwarding.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StreamingScreen(
    vmName: String,
    onBack: () -> Unit,
    viewModel: StreamingViewModel = hiltViewModel(),
) {
    val connectionState by viewModel.connectionState.collectAsState()
    val stats by viewModel.stats.collectAsState()
    val currentFrame by viewModel.currentFrame.collectAsState()
    
    var showControls by remember { mutableStateOf(true) }
    var relativeMode by remember { mutableStateOf(true) }
    var quality by remember { mutableStateOf(85) }
    var fps by remember { mutableStateOf(60) }
    
    val scope = rememberCoroutineScope()
    
    // Auto-hide controls after 5 seconds of no interaction
    LaunchedEffect(showControls) {
        if (showControls && connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
            delay(5000)
            showControls = false
        }
    }
    
    // Connect when screen opens
    LaunchedEffect(Unit) {
        viewModel.connect(quality = quality, fps = fps)
    }
    
    // Cleanup on dispose
    DisposableEffect(Unit) {
        onDispose {
            viewModel.disconnect()
        }
    }
    
    Scaffold(
        topBar = {
            if (showControls) {
                TopAppBar(
                    title = { Text(vmName) },
                    navigationIcon = {
                        IconButton(onClick = onBack) {
                            Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                        }
                    },
                    actions = {
                        // Connection status
                        val statusColor = when (connectionState) {
                            ContinuumStreamClient.ConnectionState.CONNECTED -> Color.Green
                            ContinuumStreamClient.ConnectionState.CONNECTING -> Color.Yellow
                            ContinuumStreamClient.ConnectionState.RECONNECTING -> Color.Yellow
                            ContinuumStreamClient.ConnectionState.ERROR -> Color.Red
                            else -> Color.Gray
                        }
                        Box(
                            modifier = Modifier
                                .size(12.dp)
                                .background(statusColor, RoundedCornerShape(6.dp))
                        )
                        Spacer(Modifier.width(8.dp))
                        
                        // Stats
                        if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                            Text(
                                "${stats.fps}fps · ${stats.bitrateKbps}kbps",
                                style = MaterialTheme.typography.bodySmall,
                            )
                            Spacer(Modifier.width(8.dp))
                        }
                        
                        // Mouse mode toggle
                        IconButton(onClick = { relativeMode = !relativeMode }) {
                            Icon(
                                if (relativeMode) Icons.Default.Mouse else Icons.Default.TouchApp,
                                contentDescription = if (relativeMode) "Relative" else "Absolute",
                            )
                        }
                        
                        // Quality dropdown
                        var expanded by remember { mutableStateOf(false) }
                        Box {
                            IconButton(onClick = { expanded = true }) {
                                Icon(Icons.Default.Settings, contentDescription = "Settings")
                            }
                            DropdownMenu(
                                expanded = expanded,
                                onDismissRequest = { expanded = false },
                            ) {
                                DropdownMenuItem(
                                    text = { Text("Quality: $quality%") },
                                    onClick = {},
                                    enabled = false,
                                )
                                Slider(
                                    value = quality.toFloat(),
                                    onValueChange = {
                                        quality = it.toInt()
                                        viewModel.updateConfig(quality, fps)
                                    },
                                    valueRange = 10f..100f,
                                )
                                DropdownMenuItem(
                                    text = { Text("FPS: $fps") },
                                    onClick = {},
                                    enabled = false,
                                )
                                Slider(
                                    value = fps.toFloat(),
                                    onValueChange = {
                                        fps = it.toInt()
                                        viewModel.updateConfig(quality, fps)
                                    },
                                    valueRange = 1f..60f,
                                )
                            }
                        }
                    },
                )
            }
        },
        floatingActionButton = {
            if (showControls) {
                Column {
                    // Keyboard button
                    FloatingActionButton(
                        onClick = { viewModel.showKeyboard() },
                        modifier = Modifier.padding(bottom = 8.dp),
                    ) {
                        Icon(Icons.Default.Keyboard, contentDescription = "Keyboard")
                    }
                    // Disconnect button
                    FloatingActionButton(
                        onClick = {
                            viewModel.disconnect()
                            onBack()
                        },
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ) {
                        Icon(Icons.Default.CallEnd, contentDescription = "Disconnect")
                    }
                }
            }
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color.Black)
                .pointerInput(connectionState, relativeMode) {
                    detectTapGestures(
                        onTap = { offset ->
                            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                                val x = offset.x * 1920f / size.width
                                val y = offset.y * 1080f / size.height
                                viewModel.sendMouseClick("left", true, x, y)
                                viewModel.sendMouseClick("left", false, x, y)
                            }
                        },
                        onDoubleTap = { offset ->
                            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                                val x = offset.x * 1920f / size.width
                                val y = offset.y * 1080f / size.height
                                viewModel.sendMouseClick("left", true, x, y)
                                viewModel.sendMouseClick("left", false, x, y)
                                viewModel.sendMouseClick("left", true, x, y)
                                viewModel.sendMouseClick("left", false, x, y)
                            }
                        },
                        onLongPress = { offset ->
                            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                                val x = offset.x * 1920f / size.width
                                val y = offset.y * 1080f / size.height
                                viewModel.sendMouseClick("right", true, x, y)
                                viewModel.sendMouseClick("right", false, x, y)
                            }
                        },
                    )
                }
                .pointerInput(connectionState, relativeMode) {
                    detectDragGestures(
                        onDragStart = { offset ->
                            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                                val x = offset.x * 1920f / size.width
                                val y = offset.y * 1080f / size.height
                                viewModel.sendMouseClick("left", true, x, y)
                            }
                        },
                        onDrag = { change, dragAmount ->
                            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                                if (relativeMode) {
                                    val dx = dragAmount.x * 1920f / size.width
                                    val dy = dragAmount.y * 1080f / size.height
                                    viewModel.sendMouseMove(dx, dy, relative = true)
                                } else {
                                    val x = change.position.x * 1920f / size.width
                                    val y = change.position.y * 1080f / size.height
                                    viewModel.sendMouseMove(x, y, relative = false)
                                }
                            }
                        },
                        onDragEnd = {
                            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                                viewModel.sendMouseClick("left", false)
                            }
                        },
                    )
                }
                .pointerInput(connectionState) {
                    detectVerticalDragGestures { change, dragAmount ->
                        if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                            viewModel.sendScroll(0f, -dragAmount / 120f)
                        }
                    }
                }
                .pointerInput(Unit) {
                    detectTransformGestures { centroid, pan, zoom, rotation ->
                        if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED && zoom != 1f) {
                            // Pinch to zoom - could be sent as Ctrl+scroll
                        }
                    }
                },
        ) {
            // Video frame display
            currentFrame?.let { bitmap ->
                val imageBitmap = remember(bitmap) {
                    bitmap.asImageBitmap()
                }
                
                Canvas(
                    modifier = Modifier.fillMaxSize(),
                ) {
                    // Maintain aspect ratio
                    val imageRatio = bitmap.width.toFloat() / bitmap.height.toFloat()
                    val canvasRatio = size.width / size.height
                    
                    val drawWidth: Float
                    val drawHeight: Float
                    val offsetX: Float
                    val offsetY: Float
                    
                    if (imageRatio > canvasRatio) {
                        drawWidth = size.width
                        drawHeight = size.width / imageRatio
                        offsetX = 0f
                        offsetY = (size.height - drawHeight) / 2f
                    } else {
                        drawHeight = size.height
                        drawWidth = size.height * imageRatio
                        offsetX = (size.width - drawWidth) / 2f
                        offsetY = 0f
                    }
                    
                    drawImage(
                        image = imageBitmap,
                        dstOffset = androidx.compose.ui.unit.IntOffset(offsetX.toInt(), offsetY.toInt()),
                        dstSize = androidx.compose.ui.unit.IntSize(drawWidth.toInt(), drawHeight.toInt()),
                    )
                }
            }
            
            // Connection state overlay
            when (connectionState) {
                ContinuumStreamClient.ConnectionState.CONNECTING -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator()
                            Spacer(Modifier.height(16.dp))
                            Text("Connecting to $vmName...", color = Color.White)
                        }
                    }
                }
                ContinuumStreamClient.ConnectionState.RECONNECTING -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator()
                            Spacer(Modifier.height(16.dp))
                            Text("Reconnecting...", color = Color.Yellow)
                        }
                    }
                }
                ContinuumStreamClient.ConnectionState.ERROR -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                imageVector = Icons.Default.ErrorOutline,
                                contentDescription = "Error",
                                modifier = Modifier.size(48.dp),
                                tint = Color.Red,
                            )
                            Spacer(Modifier.height(16.dp))
                            Text("Connection failed", color = Color.White)
                            Button(onClick = { viewModel.reconnect() }) {
                                Text("Retry")
                            }
                        }
                    }
                }
                else -> {}
            }
            
            // Fullscreen toggle
            if (connectionState == ContinuumStreamClient.ConnectionState.CONNECTED) {
                IconButton(
                    onClick = { showControls = !showControls },
                    modifier = Modifier.align(Alignment.TopEnd).padding(16.dp),
                ) {
                    Icon(
                        if (showControls) Icons.Default.FullscreenExit else Icons.Default.Fullscreen,
                        contentDescription = "Toggle fullscreen",
                        tint = Color.White.copy(alpha = 0.5f),
                    )
                }
            }
        }
    }
}

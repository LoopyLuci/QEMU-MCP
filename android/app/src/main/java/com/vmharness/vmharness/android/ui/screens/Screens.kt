package com.vmharness.android.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vmharness.android.data.model.*
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.ui.viewmodels.*
import com.vmharness.android.ui.components.StatusCodeChip

// ── Common components ──────────────────────────────────────────────────────────

@Composable
fun LoadingScreen(message: String = "Loading...") {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator()
            Spacer(modifier = Modifier.height(8.dp))
            Text(message, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun ErrorScreen(message: String, onRetry: () -> Unit) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                imageVector = Icons.Default.ErrorOutline,
                contentDescription = "Error",
                modifier = Modifier.size(48.dp),
                tint = MaterialTheme.colorScheme.error,
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(message, style = MaterialTheme.typography.bodyLarge, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
            Spacer(modifier = Modifier.height(16.dp))
            Button(onClick = onRetry) {
                Text("Retry")
            }
        }
    }
}

// ── Pairing Screen ──────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PairingScreen(
    viewModel: PairingViewModel,
    pairingStore: PairingStore,
    onPaired: () -> Unit,
    onScanQr: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    // Observe scanned token from QR scanner or deep link
    LaunchedEffect(Unit) {
        // First check QrTokenHolder flow (for QR scanner)
        QrTokenHolder.flow.collect { token ->
            viewModel.setPendingToken(token)
            pairingStore.pendingToken = null
        }
    }

    // Check for pending token from deep link (may arrive before flow collector starts)
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(100)
        val pending = pairingStore.pendingToken
        if (!pending.isNullOrBlank()) {
            viewModel.setPendingToken(pending)
            pairingStore.pendingToken = null
        }
    }

    LaunchedEffect(state.status) {
        if (state.status is UiState.Success) {
            onPaired()
        }
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
        ) {
            Text(
                text = "VM-Harness",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Mobile Companion",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(24.dp))

            when (val s = state.status) {
                is UiState.Loading -> LoadingScreen("Pairing...")
                is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.reset() })
                is UiState.Success -> {
                    onPaired()
                    Box(Modifier.fillMaxSize())
                }
                UiState.Idle -> {
                    Column {
                        // Tailscale status
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = if (state.tailscaleRunning) Icons.Default.CheckCircle else Icons.Default.Warning,
                                contentDescription = null,
                                tint = if (state.tailscaleRunning) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = if (state.tailscaleRunning) "Tailscale is running" else "Tailscale not detected",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                        Spacer(modifier = Modifier.height(24.dp))

                        Text(
                            text = "Pair with your desktop",
                            style = MaterialTheme.typography.titleLarge,
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Open VM-Harness on your desktop, go to Settings → Pair Mobile Device, then scan the QR code or enter the pairing key below.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(modifier = Modifier.height(24.dp))

                        // Manual entry field
                        OutlinedTextField(
                            value = state.pendingToken ?: "",
                            onValueChange = { viewModel.setPendingToken(it) },
                            label = { Text("Pairing key or URI") },
                            placeholder = { Text("vmharness://pair?key=... or paste the full URI") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            shape = RoundedCornerShape(8.dp),
                        )
                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                val token = state.pendingToken
                                android.util.Log.d("VM-Harness", "Pair with Desktop clicked, token=$token, status=${state.status}")
                                if (!token.isNullOrBlank()) {
                                    viewModel.pairFromToken(token)
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !state.pendingToken.isNullOrBlank() && state.status is UiState.Idle,
                        ) {
                            Text("Pair with Desktop")
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        // QR Scan button
                        OutlinedButton(
                            onClick = onScanQr,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(
                                imageVector = Icons.Default.QrCodeScanner,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Scan QR Code")
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        // Info box
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                            ),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("How-to", style = MaterialTheme.typography.titleSmall)
                                Spacer(modifier = Modifier.height(8.dp))
                                Text("1. On desktop: Settings → Pair Mobile Device", style = MaterialTheme.typography.bodySmall)
                                Text("2. Scan the QR code with your camera, or copy the pairing key", style = MaterialTheme.typography.bodySmall)
                                Text("3. Paste it above and tap 'Pair with Desktop'", style = MaterialTheme.typography.bodySmall)
                                Text("4. Make sure Tailscale is running on both devices", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
        }
    }
}

// ── Dashboard Screen ────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel = hiltViewModel(),
    onVmClick: (String) -> Unit,
    onTerminalClick: (String) -> Unit,
    onSecurityClick: () -> Unit,
    onLogsClick: () -> Unit,
    onVmCreate: () -> Unit = {},
    onKubeClick: () -> Unit = {},
    onFederationClick: () -> Unit = {},
) {
    val state by viewModel.state.collectAsState()
    var showCreateDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("VM-Harness Dashboard") },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                    IconButton(onClick = onSecurityClick) {
                        Icon(Icons.Default.Security, contentDescription = "Security")
                    }
                    IconButton(onClick = onLogsClick) {
                        Icon(Icons.Default.List, contentDescription = "Logs")
                    }
                    IconButton(onClick = onKubeClick) {
                        Icon(Icons.Default.Cloud, contentDescription = "Kubernetes")
                    }
                    IconButton(onClick = onFederationClick) {
                        Icon(Icons.Default.Hub, contentDescription = "Federation")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onVmCreate) {
                Icon(Icons.Default.Add, contentDescription = "Create VM")
            }
        },
    ) { padding ->
        when (val s = state.status) {
            is UiState.Loading -> LoadingScreen("Loading dashboard...")
            is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.refresh() })
            is UiState.Success -> {
                val data = s.data
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                ) {
                    // Desktop info
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Desktop: ${data.displayName ?: "Unknown"}", fontWeight = FontWeight.Medium)
                            if (data.tailscaleIp.isNotBlank()) {
                                Text("IP: ${data.tailscaleIp}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Text("Machine: ${data.machineId}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // VM list
                    Text("Virtual Machines", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    if (data.vms.isEmpty()) {
                        Text("No VMs found", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        LazyColumn(
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.weight(1f),
                        ) {
                            items(data.vms) { vm ->
                                VmCard(
                                    vm = vm,
                                    onClick = { onVmClick(vm.name) },
                                    onTerminal = { onTerminalClick(vm.name) },
                                )
                            }
                        }
                    }
                }
            }
            UiState.Idle -> LoadingScreen()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VmCard(
    vm: VmSummary,
    onClick: () -> Unit,
    onTerminal: () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(vm.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.width(8.dp))
                    StatusCodeChip(vm.status)
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text("${vm.ram} GB RAM · ${vm.vcpus} vCPUs · ${vm.disk} GB disk", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                val showUptime = vm.uptime.isNotBlank() && vm.uptime != "0s" && vm.uptime != "N/A" && !vm.uptime.startsWith("0")
                if (showUptime) {
                    Text("Uptime: ${vm.uptime}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Row {
                IconButton(onClick = onTerminal) {
                    Icon(Icons.Default.Terminal, contentDescription = "Open Terminal", tint = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }
}

// ── VM Control Screen ───────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VmControlScreen(
    vmName: String,
    viewModel: VmControlViewModel = hiltViewModel(),
    onBack: () -> Unit,
    onTerminal: () -> Unit,
    onStream: () -> Unit,
    onDashboard: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(vmName) {
        viewModel.loadVm(vmName)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(vmName) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = onStream) {
                        Icon(Icons.Default.ScreenShare, contentDescription = "Stream")
                    }
                    IconButton(onClick = onTerminal) {
                        Icon(Icons.Default.Terminal, contentDescription = "Terminal")
                    }
                    IconButton(onClick = onDashboard) {
                        Icon(Icons.Default.Dashboard, contentDescription = "Dashboard")
                    }
                },
            )
        },
        bottomBar = {
            if (state.actionInProgress) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
        },
    ) { padding ->
        when (val s = state.status) {
            is UiState.Loading -> LoadingScreen("Loading VM details...")
            is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadVm(vmName) })
            is UiState.Success -> {
                val vm = s.data
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                ) {
                    // Status
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        StatusCodeChip(vm.status)
                        Spacer(modifier = Modifier.weight(1f))
                        Text(
                            "Uptime: ${vm.config["uptime"] ?: "N/A"}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // Quick actions
                    Text("Quick Actions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        IconButton(onClick = { viewModel.startVm() }) {
                            Icon(Icons.Default.PlayArrow, contentDescription = "Start", tint = MaterialTheme.colorScheme.primary)
                        }
                        IconButton(onClick = { viewModel.stopVm() }) {
                            Icon(Icons.Default.Stop, contentDescription = "Stop", tint = MaterialTheme.colorScheme.error)
                        }
                        IconButton(onClick = { viewModel.resetVm() }) {
                            Icon(Icons.Default.Replay, contentDescription = "Reset", tint = MaterialTheme.colorScheme.secondary)
                        }
                        IconButton(onClick = { viewModel.powerdownVm() }) {
                            Icon(Icons.Default.PowerOff, contentDescription = "Power Down")
                        }
                        IconButton(onClick = { viewModel.pauseVm() }) {
                            Icon(Icons.Default.Pause, contentDescription = "Pause")
                        }
                        IconButton(onClick = { viewModel.resumeVm() }) {
                            Icon(Icons.Default.PlayArrow, contentDescription = "Resume")
                        }
                        IconButton(onClick = { viewModel.ejectCdrom() }) {
                            Icon(Icons.Default.Eject, contentDescription = "Eject CD-ROM")
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // Last action result
                    state.lastAction?.let { action ->
                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = if (action.status == "ok") MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                                else MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f),
                            ),
                        ) {
                            Text(
                                "Action: ${action.action} → ${action.status}",
                                modifier = Modifier.padding(8.dp),
                                color = if (action.status == "ok") MaterialTheme.colorScheme.onPrimaryContainer
                                else MaterialTheme.colorScheme.onErrorContainer,
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }

                    // Details
                    Text("Details", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            vm.config.forEach { (key, value) ->
                                if (key !in setOf("name", "status")) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                    ) {
                                        Text(key, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text(value.toString(), style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            UiState.Idle -> LoadingScreen()
        }
    }
}

// ── Guest Terminal Screen ───────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GuestTerminalScreen(
    vmName: String,
    viewModel: GuestTerminalViewModel = hiltViewModel(),
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(vmName) {
        viewModel.setVmName(vmName)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Guest Terminal · $vmName") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            // Output area
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(8.dp),
                contentAlignment = Alignment.TopStart,
            ) {
                if (state.output.isBlank()) {
                    Text(
                        "Terminal output will appear here...",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    Text(
                        state.output,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
                if (state.commandInProgress) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text("...", color = MaterialTheme.colorScheme.primary)
                }
            }

            // Command input
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = "",
                    onValueChange = { },
                    placeholder = { Text("Enter command...") },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    shape = RoundedCornerShape(8.dp),
                    enabled = !state.commandInProgress,
                )
                Spacer(modifier = Modifier.width(8.dp))
                IconButton(
                    onClick = { },
                    enabled = !state.commandInProgress,
                ) {
                    Icon(Icons.Default.Send, contentDescription = "Send")
                }
            }
        }
    }
}

// ── Telemetry Screen ────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TelemetryScreen(
    viewModel: TelemetryViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    var autoRefresh by remember { mutableStateOf(true) }

    LaunchedEffect(autoRefresh) {
        if (autoRefresh) {
            viewModel.startAutoRefresh()
        } else {
            viewModel.stopAutoRefresh()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Telemetry") },
                actions = {
                    IconButton(onClick = { autoRefresh = !autoRefresh }) {
                        Icon(
                            imageVector = if (autoRefresh) Icons.Default.Refresh else Icons.Default.Pause,
                            contentDescription = if (autoRefresh) "Pause auto-refresh" else "Resume auto-refresh",
                        )
                    }
                },
            )
        },
    ) { padding ->
        when (val s = state.status) {
            is UiState.Loading -> LoadingScreen("Loading metrics...")
            is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadMetrics() })
            is UiState.Success -> {
                val metrics = s.data
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                ) {
                    // CPU
                    TelemetryCard(
                        title = "CPU Usage",
                        value = "${metrics.cpuPercent.toInt()}%",
                        icon = Icons.Default.Tv,
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    // RAM
                    TelemetryCard(
                        title = "RAM",
                        value = "${metrics.ramUsed.toInt()} / ${metrics.ramTotal.toInt()} GB",
                        icon = Icons.Default.Memory,
                        subtitle = "(${(metrics.ramUsed / metrics.ramTotal * 100).toInt()}%)",
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    // Disk
                    TelemetryCard(
                        title = "Disk",
                        value = "${metrics.diskUsed.toInt()} / ${metrics.diskTotal.toInt()} GB",
                        icon = Icons.Default.Storage,
                        subtitle = "(${(metrics.diskUsed / metrics.diskTotal * 100).toInt()}%)",
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    // Network
                    TelemetryCard(
                        title = "Network",
                        value = "↓ ${metrics.networkRx.toInt()} MB/s · ↑ ${metrics.networkTx.toInt()} MB/s",
                        icon = Icons.Default.Wifi,
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    // Timestamp
                    Text(
                        "Updated: ${java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(
                            java.util.Date(metrics.timestamp * 1000)
                        )}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            UiState.Idle -> LoadingScreen()
        }
    }
}

@Composable
fun TelemetryCard(
    title: String,
    value: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    subtitle: String? = null,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Medium)
                subtitle?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

// ── Settings Screen ─────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel = hiltViewModel(),
    onSecurityClick: () -> Unit,
    onLogsClick: () -> Unit,
    onKubeClick: () -> Unit = {},
    onFederationClick: () -> Unit = {},
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                actions = {
                    IconButton(onClick = onSecurityClick) {
                        Icon(Icons.Default.Security, contentDescription = "Security")
                    }
                    IconButton(onClick = onLogsClick) {
                        Icon(Icons.Default.List, contentDescription = "Logs")
                    }
                    IconButton(onClick = onKubeClick) {
                        Icon(Icons.Default.Cloud, contentDescription = "Kubernetes")
                    }
                    IconButton(onClick = onFederationClick) {
                        Icon(Icons.Default.Hub, contentDescription = "Federation")
                    }
                },
            )
        },
    ) { padding ->
        when (val s = state.status) {
            is UiState.Loading -> LoadingScreen("Loading settings...")
            is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadSettings() })
            is UiState.Success -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                ) {
                    // Connection status
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)),
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Link, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    if (state.isPaired) "Connected to ${state.displayName ?: "Desktop"}"
                                    else "Not connected",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Medium,
                                )
                            }
                            if (state.tailscaleIp?.isNotBlank() == true) {
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("Tailscale IP: ${state.tailscaleIp}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (!state.isPaired) {
                                Spacer(modifier = Modifier.height(8.dp))
                                TextButton(onClick = { }) {
                                    Text("Pair Device")
                                }
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // App settings
                    Text("App Settings", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text("Theme", style = MaterialTheme.typography.bodyMedium)
                                Text("Dark", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                            }
                            Divider(modifier = Modifier.padding(vertical = 8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text("Refresh interval", style = MaterialTheme.typography.bodyMedium)
                                Text("5 seconds", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                            }
                            Divider(modifier = Modifier.padding(vertical = 8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text("Biometric lock", style = MaterialTheme.typography.bodyMedium)
                                Text("Off", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // About
                    Text("About", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("App", style = MaterialTheme.typography.bodyMedium)
                                Text("VM-Harness Android Companion", style = MaterialTheme.typography.bodyMedium)
                            }
                            Divider(modifier = Modifier.padding(vertical = 8.dp))
                            Row(horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Version", style = MaterialTheme.typography.bodyMedium)
                                Text("1.0.0", style = MaterialTheme.typography.bodyMedium)
                            }
                            Divider(modifier = Modifier.padding(vertical = 8.dp))
                            Row(horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Desktop version", style = MaterialTheme.typography.bodyMedium)
                                Text(state.settings?.version ?: "N/A", style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // Danger zone
                    Text("Danger Zone", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium, color = MaterialTheme.colorScheme.error)
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = { viewModel.revokePairing() },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
                    ) {
                        Text("Revoke Pairing")
                    }
                }
            }
            UiState.Idle -> LoadingScreen()
        }
    }
}

// ── Security Screen ─────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SecurityScreen(
    viewModel: SecurityViewModel = hiltViewModel(),
    onBack: () -> Unit,
    onAuditClick: () -> Unit,
    showAudit: Boolean = false,
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (showAudit) "Audit Log" else "Security") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
        ) {
            if (showAudit) {
                // Audit log view
                when (val s = state.auditLogStatus) {
                    is UiState.Loading -> LoadingScreen("Loading audit log...")
                    is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadAuditLog() })
                    is UiState.Success -> {
                        if (state.auditLog.isEmpty()) {
                            Text("No audit entries found", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        } else {
                            LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                items(state.auditLog) { entry ->
                                    AuditEntryRow(entry = entry)
                                }
                            }
                        }
                    }
                    UiState.Idle -> {}
                }
            } else {
                // Credentials view
                when (val s = state.credentialsStatus) {
                    is UiState.Loading -> LoadingScreen("Loading credentials...")
                    is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadCredentials() })
                    is UiState.Success -> {
                        Column {
                            Text("Credentials (${state.credentials.size})", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                            Spacer(modifier = Modifier.height(8.dp))
                            Row {
                                IconButton(onClick = onAuditClick) {
                                    Icon(Icons.Default.History, contentDescription = "Audit Log", tint = MaterialTheme.colorScheme.primary)
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("Audit Log", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                                }
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                items(state.credentials) { cred ->
                                    CredentialRow(
                                        cred = cred,
                                        onClick = { viewModel.selectCredential(cred.name) },
                                        isSelected = state.selectedCredential?.name == cred.name,
                                        showValue = state.showCredentialValue && state.selectedCredential?.name == cred.name,
                                    )
                                }
                            }
                        }
                    }
                    UiState.Idle -> {}
                }

                // Credential detail panel
                state.selectedCredential?.let { cred ->
                    Spacer(modifier = Modifier.height(16.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text("Credential: ${cred.name}", fontWeight = FontWeight.Medium)
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("Type: ${cred.type}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("Description: ${cred.description}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("Created: ${cred.created}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            if (state.showCredentialValue) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Divider()
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    "Value: ${cred.value}",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            Button(onClick = { viewModel.clearSelection() }) {
                                Text("Close")
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun CredentialRow(
    cred: CredentialInfo,
    onClick: () -> Unit,
    isSelected: Boolean,
    showValue: Boolean,
) {
@OptIn(ExperimentalMaterial3Api::class)
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
            else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(cred.name, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                Text(cred.type, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (showValue) {
                Text((cred.value?.take(8) ?: "") + "...", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.width(80.dp))
            } else {
                Text("••••••••", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(80.dp))
            }
        }
    }
}

@Composable
fun AuditEntryRow(entry: AuditEntry) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(entry.event, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                Text(entry.details.take(100), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(entry.timestamp, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(entry.status, style = MaterialTheme.typography.bodySmall, color = if (entry.status == "ok") MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
            }
        }
    }
}

// ── Logs Screen ─────────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LogsScreen(
    viewModel: LogsViewModel = hiltViewModel(),
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Logs") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
    ) { padding ->
        when (val s = state.status) {
            is UiState.Loading -> LoadingScreen("Loading logs...")
            is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.refresh() })
            is UiState.Success -> {
                if (state.logs.isEmpty()) {
                    Text("No log entries", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .padding(horizontal = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        items(state.logs.size.coerceAtMost(200)) { i ->
                            LogEntryRow(entry = state.logs[i])
                        }
                    }
                }
            }
            UiState.Idle -> LoadingScreen()
        }
    }
}

@Composable
fun LogEntryRow(entry: LogEntry) {
    val color = when (entry.level.lowercase()) {
        "error" -> MaterialTheme.colorScheme.error
        "warning" -> Color(0xFFFFA500)
        "debug" -> MaterialTheme.colorScheme.onSurfaceVariant
        else -> MaterialTheme.colorScheme.onSurface
    }
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(entry.level, style = MaterialTheme.typography.labelSmall, color = color, modifier = Modifier.width(60.dp))
        Text(entry.timestamp, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(80.dp))
        Text(entry.message, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
    }
}

package com.vmharness.android.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vmharness.android.data.model.*
import com.vmharness.android.ui.components.StatusCodeChip
import com.vmharness.android.ui.viewmodels.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContainerDetailScreen(
    containerId: String,
    onBack: () -> Unit,
    viewModel: ContainerDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    var selectedTab by remember { mutableIntStateOf(0) }
    var commandInput by remember { mutableStateOf("") }

    LaunchedEffect(containerId) {
        viewModel.setContainerId(containerId)
        viewModel.loadLogs()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.container?.name ?: containerId) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadContainer(); viewModel.loadLogs() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when (val s = state.status) {
                is UiState.Loading -> LoadingScreen("Loading container...")
                is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadContainer() })
                is UiState.Success -> {
                    Column(modifier = Modifier.fillMaxSize()) {
                        // Status bar
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 8.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(state.container?.name ?: "", fontWeight = FontWeight.Medium)
                                    Spacer(modifier = Modifier.width(8.dp))
                                    StatusCodeChip(state.container?.status ?: "unknown")
                                }
                                Text(
                                    state.container?.image ?: "",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }

                        // Tabs
                        TabRow(selectedTabIndex = selectedTab) {
                            Tab(
                                selected = selectedTab == 0,
                                onClick = { selectedTab = 0 },
                                text = { Text("Overview") },
                            )
                            Tab(
                                selected = selectedTab == 1,
                                onClick = { selectedTab = 1 },
                                text = { Text("Logs") },
                            )
                            Tab(
                                selected = selectedTab == 2,
                                onClick = { selectedTab = 2 },
                                text = { Text("Exec") },
                            )
                        }

                        // Tab content
                        when (selectedTab) {
                            0 -> ContainerOverviewTab(state = state, viewModel = viewModel)
                            1 -> ContainerLogsTab(state = state, viewModel = viewModel)
                            2 -> ContainerExecTab(
                                state = state,
                                viewModel = viewModel,
                                commandInput = commandInput,
                                onCommandInputChange = { commandInput = it },
                            )
                        }
                    }
                }
                UiState.Idle -> LoadingScreen()
            }
        }
    }
}

@Composable
private fun ContainerOverviewTab(
    state: ContainerDetailUiState,
    viewModel: ContainerDetailViewModel,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        // Quick Actions
        item {
            Text("Actions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalButton(
                    onClick = { viewModel.startContainer() },
                    enabled = !state.actionInProgress,
                ) {
                    Icon(Icons.Default.PlayArrow, contentDescription = "Start", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Start")
                }
                FilledTonalButton(
                    onClick = { viewModel.stopContainer() },
                    enabled = !state.actionInProgress,
                ) {
                    Icon(Icons.Default.Stop, contentDescription = "Stop", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Stop")
                }
                FilledTonalButton(
                    onClick = { viewModel.restartContainer() },
                    enabled = !state.actionInProgress,
                ) {
                    Icon(Icons.Default.Replay, contentDescription = "Restart", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Restart")
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { viewModel.pauseContainer() },
                    enabled = !state.actionInProgress,
                ) {
                    Icon(Icons.Default.Pause, contentDescription = "Pause", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Pause")
                }
                OutlinedButton(
                    onClick = { viewModel.unpauseContainer() },
                    enabled = !state.actionInProgress,
                ) {
                    Icon(Icons.Default.PlayArrow, contentDescription = "Unpause", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Unpause")
                }
                OutlinedButton(
                    onClick = { viewModel.killContainer() },
                    enabled = !state.actionInProgress,
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) {
                    Icon(Icons.Default.Close, contentDescription = "Kill", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Kill")
                }
            }
        }

        // Stats
        item {
            Spacer(modifier = Modifier.height(8.dp))
            state.stats?.let { stats ->
                Text("Stats", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(8.dp))
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        StatRow("CPU", "${stats.cpuPercent.toInt()}%")
                        StatRow("Memory", "${formatBytes(stats.memUsage)} / ${formatBytes(stats.memLimit)}")
                        StatRow("Network", "↓ ${formatBytes(stats.netRx)} · ↑ ${formatBytes(stats.netTx)}")
                        StatRow("Block I/O", "↓ ${formatBytes(stats.blockRead)} · ↑ ${formatBytes(stats.blockWrite)}")
                        StatRow("PIDs", "${stats.pids}")
                    }
                }
            }
        }

        // Details
        item {
            Spacer(modifier = Modifier.height(8.dp))
            Text("Details", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            Spacer(modifier = Modifier.height(8.dp))
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    state.container?.let { container ->
                        DetailRow("ID", container.id.take(12))
                        DetailRow("Image", container.image)
                        DetailRow("Created", container.created)
                        if (container.ports.isNotBlank()) DetailRow("Ports", container.ports)
                        if (container.command.isNotBlank()) DetailRow("Command", container.command)
                        if (container.mounts.isNotBlank()) DetailRow("Mounts", container.mounts)
                    }
                }
            }
        }

        // Last action result
        state.lastAction?.let { action ->
            item {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = if (action.status == "ok")
                            MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                        else
                            MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f),
                    ),
                ) {
                    Text(
                        "Action: ${action.action} → ${action.status}",
                        modifier = Modifier.padding(12.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun ContainerLogsTab(
    state: ContainerDetailUiState,
    viewModel: ContainerDetailViewModel,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Logs", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            IconButton(onClick = { viewModel.loadLogs() }) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh logs")
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF1E1E1E), RoundedCornerShape(8.dp))
                .padding(12.dp),
        ) {
            if (state.logs.isBlank()) {
                Text(
                    "No logs available",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                )
            } else {
                LazyColumn {
                    items(state.logs.lines()) { line ->
                        Text(
                            line,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFD4D4D4),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ContainerExecTab(
    state: ContainerDetailUiState,
    viewModel: ContainerDetailViewModel,
    commandInput: String,
    onCommandInputChange: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Exec", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            IconButton(onClick = { viewModel.clearTerminal() }) {
                Icon(Icons.Default.Clear, contentDescription = "Clear")
            }
        }
        Spacer(modifier = Modifier.height(8.dp))

        // Terminal output
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(Color(0xFF1E1E1E), RoundedCornerShape(8.dp))
                .padding(12.dp),
        ) {
            if (state.terminalOutput.isBlank()) {
                Text(
                    "Enter a command below to execute in the container...",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray,
                )
            } else {
                LazyColumn {
                    items(state.terminalOutput.lines()) { line ->
                        Text(
                            line,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFD4D4D4),
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Command input
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = commandInput,
                onValueChange = onCommandInputChange,
                placeholder = { Text("Enter command...") },
                modifier = Modifier.weight(1f),
                singleLine = true,
                shape = RoundedCornerShape(8.dp),
                enabled = !state.commandInProgress,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(
                    onSend = {
                        viewModel.executeCommand(commandInput)
                        onCommandInputChange("")
                    }
                ),
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = {
                    viewModel.executeCommand(commandInput)
                    onCommandInputChange("")
                },
                enabled = !state.commandInProgress && commandInput.isNotBlank(),
            ) {
                Icon(Icons.Default.Send, contentDescription = "Send")
            }
        }
    }
}

@Composable
private fun StatRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            value.take(60),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f).wrapContentWidth(Alignment.End),
        )
    }
}

private fun formatBytes(bytes: Long): String {
    if (bytes <= 0) return "0 B"
    val units = arrayOf("B", "KB", "MB", "GB", "TB")
    var size = bytes.toDouble()
    var unitIndex = 0
    while (size >= 1024 && unitIndex < units.size - 1) {
        size /= 1024
        unitIndex++
    }
    return "%.1f %s".format(size, units[unitIndex])
}

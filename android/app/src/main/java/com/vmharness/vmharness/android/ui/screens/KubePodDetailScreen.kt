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
fun KubePodDetailScreen(
    podName: String,
    namespace: String,
    onBack: () -> Unit,
    viewModel: KubePodDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    var selectedTab by remember { mutableIntStateOf(0) }
    var commandInput by remember { mutableStateOf("") }
    var showContainerMenu by remember { mutableStateOf(false) }

    LaunchedEffect(podName, namespace) {
        viewModel.setPod(podName, namespace)
        viewModel.loadLogs()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(podName) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadPodDetail(); viewModel.loadLogs() }) {
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
                is UiState.Loading -> LoadingScreen("Loading pod details...")
                is UiState.Error -> ErrorScreen(s.message, onRetry = { viewModel.loadPodDetail() })
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
                                Column {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(podName, fontWeight = FontWeight.Medium)
                                        Spacer(modifier = Modifier.width(8.dp))
                                        StatusCodeChip(state.pod?.status ?: "unknown")
                                    }
                                    Text(
                                        "ns: ${state.namespace} · ${state.pod?.podIp ?: ""} · ${state.pod?.node ?: ""}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                // Container selector
                                if ((state.pod?.containers?.size ?: 0) > 1) {
                                    Box {
                                        TextButton(onClick = { showContainerMenu = true }) {
                                            Text(state.selectedContainer.take(20))
                                            Icon(Icons.Default.ArrowDropDown, contentDescription = "Select container")
                                        }
                                        DropdownMenu(
                                            expanded = showContainerMenu,
                                            onDismissRequest = { showContainerMenu = false },
                                        ) {
                                            state.pod?.containers?.forEach { container ->
                                                DropdownMenuItem(
                                                    text = { Text(container.name) },
                                                    onClick = {
                                                        viewModel.selectContainer(container.name)
                                                        showContainerMenu = false
                                                    },
                                                )
                                            }
                                        }
                                    }
                                }
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
                            0 -> KubePodOverviewTab(
                                state = state,
                                viewModel = viewModel,
                            )
                            1 -> KubePodLogsTab(
                                state = state,
                                viewModel = viewModel,
                            )
                            2 -> KubePodExecTab(
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
private fun KubePodOverviewTab(
    state: KubePodDetailUiState,
    viewModel: KubePodDetailViewModel,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        // Actions
        item {
            Text("Actions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { viewModel.deletePod() },
                    enabled = !state.actionInProgress,
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) {
                    Icon(Icons.Default.Delete, contentDescription = "Delete", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Delete")
                }
                OutlinedButton(
                    onClick = { viewModel.loadPodDetail() },
                    enabled = !state.actionInProgress,
                ) {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Refresh")
                }
            }
        }

        // Conditions
        state.pod?.conditions?.let { conditions ->
            if (conditions.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Conditions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            conditions.forEach { condition ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                ) {
                                    Text(
                                        condition.type,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    Text(
                                        condition.status,
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.Medium,
                                        color = if (condition.status == "True")
                                            MaterialTheme.colorScheme.primary
                                        else
                                            MaterialTheme.colorScheme.error,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // Containers
        state.pod?.containers?.let { containers ->
            if (containers.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Containers", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    containers.forEach { container ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                ) {
                                    Text(container.name, fontWeight = FontWeight.Medium)
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            if (container.ready) "Ready" else "Not Ready",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = if (container.ready)
                                                MaterialTheme.colorScheme.primary
                                            else
                                                MaterialTheme.colorScheme.error,
                                        )
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Text(
                                            "${container.restartCount} restarts",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                                Text(
                                    container.image,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Text(
                                    "${container.state}${if (container.stateReason.isNotBlank()) " - ${container.stateReason}" else ""}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }

        // Labels
        state.pod?.labels?.let { labels ->
            if (labels.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Labels", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            labels.forEach { (key, value) ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 2.dp),
                                ) {
                                    Text(
                                        "$key: ",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    Text(
                                        value,
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // Events
        state.pod?.events?.let { events ->
            if (events.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Events", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            events.take(10).forEach { event ->
                                Text(
                                    event,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun KubePodLogsTab(
    state: KubePodDetailUiState,
    viewModel: KubePodDetailViewModel,
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
            Text(
                "Logs (${state.selectedContainer})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium,
            )
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
private fun KubePodExecTab(
    state: KubePodDetailUiState,
    viewModel: KubePodDetailViewModel,
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
            Text("Exec (${state.selectedContainer})", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
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

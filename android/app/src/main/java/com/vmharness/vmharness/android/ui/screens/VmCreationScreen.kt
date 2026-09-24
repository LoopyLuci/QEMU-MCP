package com.vmharness.android.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vmharness.android.ui.viewmodels.QmpConsoleViewModel
import com.vmharness.android.ui.viewmodels.SnapshotViewModel
import com.vmharness.android.ui.viewmodels.UiState
import com.vmharness.android.ui.viewmodels.VmCreationViewModel

// ── VM Creation Screen ─────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VmCreationScreen(
    onBack: () -> Unit,
    onCreated: (String) -> Unit,
    viewModel: VmCreationViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state.status) {
        if (state.status is UiState.Success) {
            onCreated(state.name)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Create VM") },
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
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            OutlinedTextField(
                value = state.name,
                onValueChange = { viewModel.updateName(it) },
                label = { Text("VM Name") },
                placeholder = { Text("my-new-vm") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = state.ramMb.toString(),
                onValueChange = { it.toIntOrNull()?.let { ram -> viewModel.updateRam(ram) } },
                label = { Text("RAM (MB)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = state.cpus.toString(),
                onValueChange = { it.toIntOrNull()?.let { cpus -> viewModel.updateCpus(cpus) } },
                label = { Text("CPUs") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = state.diskSizeGb.toString(),
                onValueChange = { it.toIntOrNull()?.let { size -> viewModel.updateDiskSize(size) } },
                label = { Text("Disk Size (GB)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = state.isoPath,
                onValueChange = { viewModel.updateIsoPath(it) },
                label = { Text("ISO Path (optional)") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = state.networkMode,
                onValueChange = { viewModel.updateNetworkMode(it) },
                label = { Text("Network Mode") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(24.dp))

            Button(
                onClick = { viewModel.createVm() },
                modifier = Modifier.fillMaxWidth(),
                enabled = state.name.isNotBlank() && !state.isCreating,
            ) {
                if (state.isCreating) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                }
                Text("Create VM")
            }

            state.error?.let { error ->
                Text(
                    text = "Error: $error",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
        }
    }
}

// ── Snapshot Screen ────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SnapshotScreen(
    vmName: String,
    onBack: () -> Unit,
    viewModel: SnapshotViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(vmName) {
        viewModel.setVmName(vmName)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Snapshots: $vmName") },
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
            OutlinedTextField(
                value = state.newName,
                onValueChange = { viewModel.updateNewName(it) },
                label = { Text("Snapshot Name") },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = { viewModel.createSnapshot() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Create Snapshot")
            }
            Spacer(Modifier.height(16.dp))

            Text("Existing Snapshots", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))

            if (state.snapshots.isEmpty()) {
                Text("No snapshots found", style = MaterialTheme.typography.bodyMedium)
            } else {
                state.snapshots.forEach { snap ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(snap.name, style = MaterialTheme.typography.bodyLarge)
                                if (snap.created.isNotBlank()) {
                                    Text(snap.created, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                            Button(
                                onClick = { viewModel.restoreSnapshot(snap.name) },
                            ) {
                                Text("Restore")
                            }
                        }
                    }
                }
            }
        }
    }
}

// ── QMP Console Screen ─────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QmpConsoleScreen(
    vmName: String,
    onBack: () -> Unit,
    viewModel: QmpConsoleViewModel = hiltViewModel(),
) {
    var command by remember { mutableStateOf("") }
    val state by viewModel.state.collectAsState()

    LaunchedEffect(vmName) {
        viewModel.setVmName(vmName)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("QMP Console: $vmName") },
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedTextField(
                    value = command,
                    onValueChange = { command = it },
                    label = { Text("QMP Command") },
                    placeholder = { Text("{\"execute\": \"query-status\"}") },
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                Button(
                    onClick = {
                        if (command.isNotBlank()) {
                            viewModel.executeQmpCommand(command.trim())
                            command = ""
                        }
                    },
                ) {
                    Text("Send")
                }
            }
            Spacer(Modifier.height(16.dp))

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
            ) {
                Text(
                    text = state.output.ifBlank { "No commands executed yet" },
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(8.dp)
                        .verticalScroll(rememberScrollState()),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

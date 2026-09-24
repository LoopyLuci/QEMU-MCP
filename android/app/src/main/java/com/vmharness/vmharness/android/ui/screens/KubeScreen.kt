package com.vmharness.android.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vmharness.android.data.model.*
import com.vmharness.android.ui.components.StatusCodeChip
import com.vmharness.android.ui.viewmodels.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KubeScreen(
    onBack: () -> Unit,
    onPodClick: (String, String) -> Unit,
    viewModel: KubeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    var selectedTab by remember { mutableIntStateOf(0) }
    var showNamespaceMenu by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Kubernetes") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    // Namespace selector
                    Box {
                        TextButton(onClick = { showNamespaceMenu = true }) {
                            Text(state.selectedNamespace)
                            Icon(Icons.Default.ArrowDropDown, contentDescription = "Select namespace")
                        }
                        DropdownMenu(
                            expanded = showNamespaceMenu,
                            onDismissRequest = { showNamespaceMenu = false },
                        ) {
                            state.namespaces.forEach { ns ->
                                DropdownMenuItem(
                                    text = { Text(ns.name) },
                                    onClick = {
                                        viewModel.selectNamespace(ns.name)
                                        showNamespaceMenu = false
                                    },
                                )
                            }
                        }
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Cluster info card
            when (val s = state.clusterStatus) {
                is UiState.Loading -> {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
                is UiState.Success -> {
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
                                Text(s.data.name, fontWeight = FontWeight.Medium)
                                Text(
                                    "v${s.data.version} · ${s.data.nodeCount} nodes · ${s.data.podCount} pods",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            StatusCodeChip(s.data.status)
                        }
                    }
                }
                is UiState.Error -> {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                    ) {
                        Text(
                            s.message,
                            modifier = Modifier.padding(12.dp),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                    }
                }
                UiState.Idle -> {}
            }

            // Tabs
            TabRow(selectedTabIndex = selectedTab) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("Pods (${state.pods.size})") },
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("Deployments (${state.deployments.size})") },
                )
                Tab(
                    selected = selectedTab == 2,
                    onClick = { selectedTab = 2 },
                    text = { Text("Services (${state.services.size})") },
                )
            }

            // Tab content
            when (selectedTab) {
                0 -> KubePodsTab(
                    pods = state.pods,
                    podsStatus = state.podsStatus,
                    onPodClick = onPodClick,
                    selectedNamespace = state.selectedNamespace,
                    onRefresh = { viewModel.loadPods(state.selectedNamespace) },
                )
                1 -> KubeDeploymentsTab(
                    deployments = state.deployments,
                    onRefresh = { viewModel.loadDeployments(state.selectedNamespace) },
                )
                2 -> KubeServicesTab(
                    services = state.services,
                    onRefresh = { viewModel.loadServices(state.selectedNamespace) },
                )
            }
        }
    }
}

@Composable
private fun KubePodsTab(
    pods: List<KubePod>,
    podsStatus: UiState<KubePodsResponse>,
    onPodClick: (String, String) -> Unit,
    selectedNamespace: String,
    onRefresh: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        when (podsStatus) {
            is UiState.Loading -> LoadingScreen("Loading pods...")
            is UiState.Error -> ErrorScreen(podsStatus.message, onRetry = onRefresh)
            is UiState.Success -> {
                if (pods.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            "No pods in namespace '$selectedNamespace'",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(pods) { pod ->
                            KubePodCard(
                                pod = pod,
                                onClick = { onPodClick(pod.name, pod.namespace) },
                            )
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
private fun KubePodCard(
    pod: KubePod,
    onClick: () -> Unit,
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
                    Text(pod.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.width(8.dp))
                    StatusCodeChip(pod.status)
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    "${pod.readyContainers}/${pod.totalContainers} ready · ${pod.restarts} restarts",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (pod.ip.isNotBlank()) {
                    Text(
                        "IP: ${pod.ip} · Node: ${pod.node}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    pod.age,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Icon(
                Icons.Default.ChevronRight,
                contentDescription = "View details",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun KubeDeploymentsTab(
    deployments: List<KubeDeployment>,
    onRefresh: () -> Unit,
) {
    if (deployments.isEmpty()) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "No deployments",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedButton(onClick = onRefresh) {
                    Text("Refresh")
                }
            }
        }
    } else {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(deployments) { deployment ->
                KubeDeploymentCard(deployment = deployment)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun KubeDeploymentCard(
    deployment: KubeDeployment,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(deployment.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                Text(deployment.age, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                "${deployment.readyReplicas}/${deployment.replicas} ready · ${deployment.updatedReplicas} updated",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                deployment.image,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun KubeServicesTab(
    services: List<KubeService>,
    onRefresh: () -> Unit,
) {
    if (services.isEmpty()) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "No services",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedButton(onClick = onRefresh) {
                    Text("Refresh")
                }
            }
        }
    } else {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(services) { service ->
                KubeServiceCard(service = service)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun KubeServiceCard(
    service: KubeService,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(service.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                Text(service.type, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                "Cluster IP: ${service.clusterIp}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (service.externalIp.isNotBlank()) {
                Text(
                    "External IP: ${service.externalIp}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                "Ports: ${service.ports}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

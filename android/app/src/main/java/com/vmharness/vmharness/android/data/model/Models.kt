package com.vmharness.android.data.model

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

// Auth & pairing

@Serializable
data class PairingPayload(
    val version: String = "v1",
    val purpose: String = "mobile-pairing",
    val host: String = "",
    val ip: String = "",
    val tailnet: String = "",
    val machineId: String = "",
    val displayName: String = "",
    val created: Long = 0,
    val expires: Long = 0,
    val secret: String = "",
)

@Serializable
data class PairingResponse(
    val paired: Boolean = false,
    val keyId: String = "",
    val host: String = "",
    val ip: String = "",
    val tailnet: String = "",
    val machineId: String = "",
    val displayName: String = "",
    val created: Long = 0,
    val expires: Long = 0,
)

@Serializable
data class VerifyResponse(
    val valid: Boolean = false,
    val desktopVersion: String = "",
    val tailscaleIp: String = "",
    val machineId: String = "",
    val displayName: String = "",
)

@Serializable
data class PublickeyResponse(
    val pem: String = "",
)


// Dashboard & VMs

@Serializable
data class DashboardResponse(
    val vms: List<VmSummary> = emptyList(),
    val metrics: Map<String, JsonElement> = emptyMap(),
    val tailscaleIp: String = "",
    val machineId: String = "",
    val displayName: String = "",
)

@Serializable
data class VmSummary(
    val name: String = "",
    val status: String = "",
    val qmpUri: String = "",
    val sshUri: String = "",
    val ram: Int = 0,
    val vcpus: Int = 0,
    val disk: Int = 0,
    val uptime: String = "",
    val lastStarted: String = "",
)

@Serializable
data class VmDetail(
    val name: String = "",
    val status: String = "",
    val config: Map<String, String> = emptyMap(),
    val networkInterfaces: List<Map<String, String>> = emptyList(),
    val blockDevices: List<Map<String, String>> = emptyList(),
    val qmpUri: String = "",
    val sshUri: String = "",
)

@Serializable
data class VmActionResponse(
    val vm: String = "",
    val action: String = "",
    val status: String = "",
    val detail: String = "",
)


// SSH

@Serializable
data class SshCommandRequest(
    val command: String = "",
    val timeout: Int = 30,
)

@Serializable
data class SshCommandResponse(
    val vm: String = "",
    val command: String = "",
    val output: String = "",
    val exitCode: Int = 0,
)

@Serializable
data class FileEntry(
    val name: String = "",
    val path: String = "",
    val isDirectory: Boolean = false,
    val size: Long = 0,
    val modified: String = "",
    val permissions: String = "",
)


// Metrics & telemetry

@Serializable
data class MetricsResponse(
    val cpuPercent: Double = 0.0,
    val ramUsed: Double = 0.0,
    val ramTotal: Double = 0.0,
    val diskUsed: Double = 0.0,
    val diskTotal: Double = 0.0,
    val networkRx: Double = 0.0,
    val networkTx: Double = 0.0,
    val timestamp: Long = 0,
)

@Serializable
data class VmMetricsResponse(
    val vmName: String = "",
    val vcpuUsage: Double = 0.0,
    val ramUsed: Double = 0.0,
    val ramTotal: Double = 0.0,
    val diskReadBytes: Double = 0.0,
    val diskWriteBytes: Double = 0.0,
    val netRxBytes: Double = 0.0,
    val netTxBytes: Double = 0.0,
    val timestamp: Long = 0,
)

@Serializable
data class Alert(
    val id: String = "",
    val level: String = "",
    val message: String = "",
    val source: String = "",
    val timestamp: Long = 0,
    val acknowledged: Boolean = false,
)

@Serializable
data class TelemetryHistoryEntry(
    val timestamp: Long = 0,
    val cpuPercent: Double = 0.0,
    val ramUsed: Double = 0.0,
    val ramTotal: Double = 0.0,
    val diskUsed: Double = 0.0,
    val diskTotal: Double = 0.0,
)


// Settings

@Serializable
data class SettingsResponse(
    val version: String = "",
    val tailscaleIp: String = "",
    val machineId: String = "",
    val displayName: String = "",
    val qmpPort: Int = 4444,
    val sshPort: Int = 2222,
    val defaultVm: String = "",
    val refreshIntervalSeconds: Int = 5,
)

@Serializable
data class SettingsUpdateRequest(
    val key: String = "",
    val value: String = "",
)

@Serializable
data class SettingsUpdateResponse(
    val updated: List<String> = emptyList(),
)


// Credentials

@Serializable
data class CredentialInfo(
    val name: String = "",
    val type: String = "",
    val value: String = "",
    val description: String = "",
    val created: String = "",
    val lastUsed: String = "",
)

@Serializable
data class CredentialDetail(
    val name: String = "",
    val type: String = "",
    val description: String = "",
    val created: String = "",
    val lastUsed: String = "",
    val value: String = "",
)


// Audit log

@Serializable
data class AuditEntry(
    val id: Long = 0,
    val timestamp: String = "",
    val event: String = "",
    val details: String = "",
    val sourceIp: String = "",
    val user: String = "",
    val vmName: String = "",
    val status: String = "",
    val error: String = "",
)


// Logs

@Serializable
data class LogsResponse(
    val logs: List<LogEntry> = emptyList(),
    val hasMore: Boolean = false,
)

@Serializable
data class LogEntry(
    val level: String = "",
    val timestamp: String = "",
    val logger: String = "",
    val message: String = "",
)


// Multi-VM

@Serializable
data class MultiVmState(
    val activeVm: String = "",
    val mode: String = "switch",
    val vms: List<VmSummary> = emptyList(),
)


// Snapshots

@Serializable
data class SnapshotInfo(
    val name: String = "",
    val vmName: String = "",
    val created: String = "",
    val sizeBytes: Long = 0,
)

@Serializable
data class CreateVmRequest(
    val name: String = "",
    val ramMb: Int = 4096,
    val cpus: Int = 2,
    val diskSizeGb: Int = 40,
    val isoPath: String = "",
    val networkMode: String = "nat",
    val qemuBinary: String = "",
    val display: String = "none",
)

@Serializable
data class QmpResponse(
    val vm: String = "",
    val command: String = "",
    val output: String = "",
    val returnCode: Int = 0,
)

@Serializable
data class Snapshot(
    val name: String = "",
    val vmName: String = "",
    val created: String = "",
    val sizeBytes: Long = 0,
)

@Serializable
data class SnapshotSchedule(
    val id: String = "",
    val vmName: String = "",
    val name: String = "",
    val schedule: String = "",
    val keepCount: Int = 5,
    val createdAt: String = "",
)


// ISO

@Serializable
data class IsoEntry(
    val name: String = "",
    val path: String = "",
    val sizeBytes: Long = 0,
    val lastModified: String = "",
    val inUseBy: List<String> = emptyList(),
)


// Network / Storage / System

@Serializable
data class NetworkInfo(
    val interfaces: List<Map<String, String>> = emptyList(),
    val routing: List<Map<String, String>> = emptyList(),
    val dnsServers: List<String> = emptyList(),
    val openPorts: List<Map<String, String>> = emptyList(),
)

@Serializable
data class StorageInfo(
    val mounts: List<Map<String, String>> = emptyList(),
    val totalUsedBytes: Long = 0,
    val totalCapacityBytes: Long = 0,
)

@Serializable
data class SystemInfo(
    val hostname: String = "",
    val os: String = "",
    val architecture: String = "",
    val cpuCores: Int = 0,
    val totalRamBytes: Long = 0,
    val qemuVersion: String = "",
    val tailscaleIp: String = "",
    val machineId: String = "",
    val desktopVersion: String = "",
)

// Containers

@Serializable
data class Container(
    val id: String = "",
    val name: String = "",
    val image: String = "",
    val status: String = "",
    val created: String = "",
    val ports: String = "",
    val command: String = "",
    val mounts: String = "",
    val env: String = "",
    val cpuPercent: Double = 0.0,
    val memUsage: Long = 0,
    val memLimit: Long = 0,
    val netIo: String = "",
    val pids: Int = 0,
)

@Serializable
data class ContainerStats(
    val containerId: String = "",
    val cpuPercent: Double = 0.0,
    val memUsage: Long = 0,
    val memLimit: Long = 0,
    val memPercent: Double = 0.0,
    val netRx: Long = 0,
    val netTx: Long = 0,
    val blockRead: Long = 0,
    val blockWrite: Long = 0,
    val pids: Int = 0,
    val timestamp: Long = 0,
)

@Serializable
data class ContainerLogsResponse(
    val containerId: String = "",
    val logs: String = "",
    val hasMore: Boolean = false,
)

@Serializable
data class ContainerExecRequest(
    val containerId: String = "",
    val command: String = "",
    val tty: Boolean = true,
)

@Serializable
data class ContainerActionResponse(
    val containerId: String = "",
    val action: String = "",
    val status: String = "",
    val detail: String = "",
)

// Kubernetes

@Serializable
data class KubeCluster(
    val name: String = "",
    val status: String = "",
    val version: String = "",
    val apiServer: String = "",
    val nodeCount: Int = 0,
    val namespaceCount: Int = 0,
    val podCount: Int = 0,
    val deploymentCount: Int = 0,
)

@Serializable
data class KubePod(
    val name: String = "",
    val namespace: String = "",
    val status: String = "",
    val restarts: Int = 0,
    val age: String = "",
    val ip: String = "",
    val node: String = "",
    val containers: List<String> = emptyList(),
    val readyContainers: Int = 0,
    val totalContainers: Int = 0,
)

@Serializable
data class KubePodDetail(
    val name: String = "",
    val namespace: String = "",
    val status: String = "",
    val podIp: String = "",
    val node: String = "",
    val startTime: String = "",
    val labels: Map<String, String> = emptyMap(),
    val annotations: Map<String, String> = emptyMap(),
    val containers: List<KubeContainerInfo> = emptyList(),
    val conditions: List<KubeCondition> = emptyList(),
    val events: List<String> = emptyList(),
)

@Serializable
data class KubeContainerInfo(
    val name: String = "",
    val image: String = "",
    val ready: Boolean = false,
    val restartCount: Int = 0,
    val state: String = "",
    val stateReason: String = "",
)

@Serializable
data class KubeCondition(
    val type: String = "",
    val status: String = "",
    val reason: String = "",
    val message: String = "",
    val lastTransition: String = "",
)

@Serializable
data class KubeDeployment(
    val name: String = "",
    val namespace: String = "",
    val replicas: Int = 0,
    val readyReplicas: Int = 0,
    val updatedReplicas: Int = 0,
    val availableReplicas: Int = 0,
    val age: String = "",
    val strategy: String = "",
    val image: String = "",
)

@Serializable
data class KubeService(
    val name: String = "",
    val namespace: String = "",
    val type: String = "",
    val clusterIp: String = "",
    val externalIp: String = "",
    val ports: String = "",
    val age: String = "",
)

@Serializable
data class KubePodsResponse(
    val pods: List<KubePod> = emptyList(),
    val namespace: String = "default",
)

@Serializable
data class KubeDeploymentsResponse(
    val deployments: List<KubeDeployment> = emptyList(),
    val namespace: String = "default",
)

@Serializable
data class KubeServicesResponse(
    val services: List<KubeService> = emptyList(),
    val namespace: String = "default",
)

@Serializable
data class KubePodLogsResponse(
    val podName: String = "",
    val namespace: String = "",
    val container: String = "",
    val logs: String = "",
    val hasMore: Boolean = false,
)

@Serializable
data class KubeExecRequest(
    val podName: String = "",
    val namespace: String = "",
    val container: String = "",
    val command: String = "",
    val tty: Boolean = true,
)

@Serializable
data class KubePodActionResponse(
    val podName: String = "",
    val action: String = "",
    val status: String = "",
    val detail: String = "",
)

@Serializable
data class KubeNamespace(
    val name: String = "",
    val status: String = "",
    val age: String = "",
)

// Federation

@Serializable
data class FederatedNode(
    val id: String = "",
    val name: String = "",
    val status: String = "",
    val region: String = "",
    val ip: String = "",
    val version: String = "",
    val lastSeen: String = "",
    val containersCount: Int = 0,
    val podsCount: Int = 0,
    val cpuPercent: Double = 0.0,
    val memPercent: Double = 0.0,
    val diskPercent: Double = 0.0,
    val uptime: String = "",
    val labels: Map<String, String> = emptyMap(),
    val capabilities: List<String> = emptyList(),
)

@Serializable
data class FederationStatus(
    val clusterName: String = "",
    val totalNodes: Int = 0,
    val healthyNodes: Int = 0,
    val leaderId: String = "",
    val consensusState: String = "",
    val lastUpdated: String = "",
)

@Serializable
data class FederatedNodesResponse(
    val nodes: List<FederatedNode> = emptyList(),
    val status: FederationStatus? = null,
)

@Serializable
data class FederatedNodeDetail(
    val node: FederatedNode = FederatedNode(),
    val containers: List<Container> = emptyList(),
    val pods: List<KubePod> = emptyList(),
    val deployments: List<KubeDeployment> = emptyList(),
    val services: List<KubeService> = emptyList(),
)

@Serializable
data class FederationActionResponse(
    val nodeId: String = "",
    val action: String = "",
    val status: String = "",
    val detail: String = "",
)

package com.vmharness.android.data.repository

import com.vmharness.android.data.api.*
import com.vmharness.android.data.auth.PairingTokenVerifier
import com.vmharness.android.data.model.*
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.data.api.DesktopUnreachableException
import com.vmharness.android.data.api.ApiException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DesktopRepository @Inject constructor(
    private val apiClient: VMHarnessApiClient,
    private val pairingStore: PairingStore,
    private val verifier: PairingTokenVerifier,
) {
    // ── Pairing ───────────────────────────────────────────────────────────────

    suspend fun pair(token: String): PairingResponse {
        val payload = verifier.verify(token)
        pairingStore.savePairing(
            host = payload.host,
            ip = payload.ip,
            port = 8443,
            tailnet = payload.tailnet,
            machineId = payload.machineId,
            displayName = payload.displayName,
            apiKey = payload.secret,
            created = payload.created,
            expires = payload.expires,
        )
        // Register on the desktop
        return apiClient.pair(token)
    }

    suspend fun verifyPairing(): VerifyResponse {
        if (!pairingStore.isPaired) throw NotPairedException()
        return apiClient.verify()
    }

    suspend fun revokeCurrentKey() {
        if (!pairingStore.isPaired) throw NotPairedException()
        apiClient.revoke()
        pairingStore.clear()
    }

    suspend fun fetchDesktopPublicKey(): String {
        if (!pairingStore.isPaired) throw NotPairedException()
        return apiClient.getPublicKey()
    }

    // ── Dashboard & VMs ───────────────────────────────────────────────────────

    suspend fun getDashboard(): DashboardResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            try {
                apiClient.dashboard()
            } catch (e: DesktopUnreachableException) {
                throw e
            } catch (e: ApiException) {
                throw e
            }
        }
    }

    suspend fun listVms(): List<VmSummary> {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.listVms()
        }
    }

    suspend fun getVm(name: String): VmDetail {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.getVm(name)
        }
    }

    suspend fun startVm(name: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "start")
        }
    }

    suspend fun stopVm(name: String, graceful: Boolean = true): VmActionResponse {
        // graceful param via query string — the server handles it
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "stop")
        }
    }

    suspend fun resetVm(name: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "reset")
        }
    }

    suspend fun powerdownVm(name: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "powerdown")
        }
    }

    suspend fun pauseVm(name: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "pause")
        }
    }

    suspend fun resumeVm(name: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "resume")
        }
    }

    suspend fun ejectCdrom(name: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.vmAction(name, "eject")
        }
    }

    // ── VM Creation ─────────────────────────────────────────────────────────────

    suspend fun createVm(
        name: String,
        ramMb: Int,
        cpus: Int,
        diskSizeGb: Int,
        isoPath: String,
        networkMode: String,
    ): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.createVm(name, ramMb, cpus, diskSizeGb, isoPath, networkMode)
        }
    }

    // ── Snapshots ───────────────────────────────────────────────────────────────

    suspend fun listSnapshots(vmName: String): List<SnapshotInfo> {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.listSnapshots(vmName)
        }
    }

    suspend fun createSnapshot(vmName: String, snapshotName: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.createSnapshot(vmName, snapshotName)
        }
    }

    suspend fun restoreSnapshot(vmName: String, snapshotName: String): VmActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.restoreSnapshot(vmName, snapshotName)
        }
    }

    // ── QMP Console ─────────────────────────────────────────────────────────────

    suspend fun executeQmpCommand(vmName: String, command: String): SshCommandResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.executeQmpCommand(vmName, command)
        }
    }

    // ── SSH ────────────────────────────────────────────────────────────────────

    suspend fun sshCommand(vmName: String, command: String, timeout: Int = 30): SshCommandResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.sshCommand(vmName, command, timeout)
        }
    }

    // ── Metrics ────────────────────────────────────────────────────────────────

    suspend fun getMetrics(): MetricsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.metrics()
        }
    }

    // ── Settings ───────────────────────────────────────────────────────────────

    suspend fun getSettings(): SettingsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.settings()
        }
    }

    suspend fun updateSetting(key: String, value: String): SettingsUpdateResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.updateSetting(key, value)
        }
    }

    // ── Credentials ────────────────────────────────────────────────────────────

    suspend fun listCredentials(): List<CredentialInfo> {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.listCredentials()
        }
    }

    suspend fun getCredential(name: String): CredentialDetail {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.getCredential(name)
        }
    }

    // ── Audit log ──────────────────────────────────────────────────────────────

    suspend fun getAuditLog(): List<AuditEntry> {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.auditLog()
        }
    }

    // ── Logs ───────────────────────────────────────────────────────────────────

    suspend fun getLogs(): LogsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.logs()
        }
    }

    // ── Health ─────────────────────────────────────────────────────────────────

    suspend fun healthCheck(): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                apiClient.healthCheck()
                true
            } catch (_: Exception) {
                false
            }
        }
    }


    // ── Containers ───────────────────────────────────────────────────────────────

    suspend fun listContainers(): List<Container> {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.listContainers()
        }
    }

    suspend fun getContainer(containerId: String): Container {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.getContainer(containerId)
        }
    }

    suspend fun containerStats(containerId: String): ContainerStats {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.containerStats(containerId)
        }
    }

    suspend fun containerLogs(containerId: String, tail: Int = 100): ContainerLogsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.containerLogs(containerId, tail)
        }
    }

    suspend fun containerExec(containerId: String, command: String): SshCommandResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.containerExec(containerId, command)
        }
    }

    suspend fun containerAction(containerId: String, action: String): ContainerActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.containerAction(containerId, action)
        }
    }


    // ── Kubernetes ───────────────────────────────────────────────────────────────

    suspend fun kubeCluster(): KubeCluster {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubeCluster()
        }
    }

    suspend fun kubeNamespaces(): List<KubeNamespace> {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubeNamespaces()
        }
    }

    suspend fun kubePods(namespace: String = "default"): KubePodsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubePods(namespace)
        }
    }

    suspend fun kubePodDetail(podName: String, namespace: String = "default"): KubePodDetail {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubePodDetail(podName, namespace)
        }
    }

    suspend fun kubePodLogs(podName: String, namespace: String = "default", container: String = "", tail: Int = 100): KubePodLogsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubePodLogs(podName, namespace, container, tail)
        }
    }

    suspend fun kubePodExec(podName: String, namespace: String, container: String, command: String): SshCommandResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubePodExec(podName, namespace, container, command)
        }
    }

    suspend fun kubeDeployments(namespace: String = "default"): KubeDeploymentsResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubeDeployments(namespace)
        }
    }

    suspend fun kubeServices(namespace: String = "default"): KubeServicesResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubeServices(namespace)
        }
    }

    suspend fun kubePodAction(podName: String, namespace: String, action: String): KubePodActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.kubePodAction(podName, namespace, action)
        }
    }


    // ── Federation ───────────────────────────────────────────────────────────────

    suspend fun federationNodes(): FederatedNodesResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.federationNodes()
        }
    }

    suspend fun federationNodeDetail(nodeId: String): FederatedNodeDetail {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.federationNodeDetail(nodeId)
        }
    }

    suspend fun federationAction(nodeId: String, action: String): FederationActionResponse {
        return withContext(Dispatchers.IO) {
            if (!pairingStore.isPaired) throw NotPairedException()
            apiClient.federationAction(nodeId, action)
        }
    }

}

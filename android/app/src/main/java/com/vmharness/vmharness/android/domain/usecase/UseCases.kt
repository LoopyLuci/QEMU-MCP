package com.vmharness.android.domain.usecase

import com.vmharness.android.data.api.*
import com.vmharness.android.data.auth.PairingTokenVerifier
import com.vmharness.android.data.model.*
import com.vmharness.android.data.repository.DesktopRepository
import com.vmharness.android.data.store.PairingStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject

/**
 * Use cases for the VM-Harness Android app.
 * Each use case encapsulates a specific business operation.
 * All use cases are Hilt-injected via @Injects.
 */

class PairingUseCase @Inject constructor(
    private val repository: DesktopRepository,
    private val pairingStore: PairingStore,
    private val verifier: PairingTokenVerifier,
) {
    suspend fun pairFromToken(token: String): PairingResponse {
        // Extract host from token payload to fetch public key if needed
        val payload = try {
            verifier.verify(token)
        } catch (e: Exception) {
            if (e.message?.contains("No desktop public key") == true) {
                val host = extractHostFromToken(token) ?: throw PairingException(
                    "Cannot extract host from token"
                )
                try {
                    verifier.fetchPublicKey("http://$host:8443")
                } catch (fetchError: Exception) {
                    throw PairingException(
                        "Failed to fetch public key from $host: ${fetchError.message}"
                    )
                }
                verifier.verify(token)
            } else {
                throw e
            }
        }
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
        return try {
            // Register the key on the server
            val response = repository.pair(token)
            response
        } catch (e: Exception) {
            PairingResponse(paired = true, displayName = payload.displayName, host = payload.host, ip = payload.ip)
        }
    }

    private fun extractHostFromToken(token: String): String? {
        return try {
            val parts = token.split(".")
            if (parts.size != 2) return null
            val payB64 = parts[1]
            val padded = payB64 + "=".repeat((4 - payB64.length % 4) % 4)
            val jsonBytes = android.util.Base64.decode(padded, android.util.Base64.URL_SAFE)
            val json = org.json.JSONObject(String(jsonBytes, Charsets.UTF_8))
            json.optString("i", null) ?: json.optString("h", null)
        } catch (e: Exception) {
            null
        }
    }

    suspend fun verify(): VerifyResponse = withContext(Dispatchers.IO) {
        repository.verifyPairing()
    }

    suspend fun revoke() = withContext(Dispatchers.IO) {
        repository.revokeCurrentKey()
    }

    fun isPaired(): Boolean = pairingStore.isPaired
    fun isExpired(): Boolean = pairingStore.isExpired
    fun getServerUrl(): String = pairingStore.serverUrl
    fun getDisplayName(): String? = pairingStore.displayName
    fun getTailnet(): String? = pairingStore.tailnet
}

class DashboardUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getDashboard() = repository.getDashboard()
    suspend fun listVms() = repository.listVms()
    suspend fun getVm(name: String) = repository.getVm(name)
}

class VmControlUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getVm(name: String) = repository.getVm(name)
    suspend fun startVm(name: String) = repository.startVm(name)
    suspend fun stopVm(name: String, graceful: Boolean = true) = repository.stopVm(name, graceful)
    suspend fun resetVm(name: String) = repository.resetVm(name)
    suspend fun powerdownVm(name: String) = repository.powerdownVm(name)
    suspend fun pauseVm(name: String) = repository.pauseVm(name)
    suspend fun resumeVm(name: String) = repository.resumeVm(name)
    suspend fun ejectCdrom(name: String) = repository.ejectCdrom(name)
    suspend fun executeCommand(vmName: String, command: String) = repository.sshCommand(vmName, command)
    suspend fun createVm(
        name: String,
        ramMb: Int,
        cpus: Int,
        diskSizeGb: Int,
        isoPath: String,
        networkMode: String,
    ) = repository.createVm(name, ramMb, cpus, diskSizeGb, isoPath, networkMode)
    suspend fun listSnapshots(vmName: String) = repository.listSnapshots(vmName)
    suspend fun createSnapshot(vmName: String, snapshotName: String) = repository.createSnapshot(vmName, snapshotName)
    suspend fun restoreSnapshot(vmName: String, snapshotName: String) = repository.restoreSnapshot(vmName, snapshotName)
    suspend fun executeQmpCommand(vmName: String, command: String) = repository.executeQmpCommand(vmName, command)
}

class TelemetryUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getMetrics() = repository.getMetrics()
}

class SecurityUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun listCredentials() = repository.listCredentials()
    suspend fun getCredential(name: String) = repository.getCredential(name)
    suspend fun getAuditLog() = repository.getAuditLog()
}

class LogsUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getLogs() = repository.getLogs()
}

class SettingsUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getSettings() = repository.getSettings()
    suspend fun updateSetting(key: String, value: String) = repository.updateSetting(key, value)
}

class ContainerDetailUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun listContainers() = repository.listContainers()
    suspend fun getContainer(containerId: String) = repository.getContainer(containerId)
    suspend fun containerStats(containerId: String) = repository.containerStats(containerId)
    suspend fun containerLogs(containerId: String, tail: Int = 100) = repository.containerLogs(containerId, tail)
    suspend fun containerExec(containerId: String, command: String) = repository.containerExec(containerId, command)
    suspend fun containerStart(containerId: String) = repository.containerAction(containerId, "start")
    suspend fun containerStop(containerId: String) = repository.containerAction(containerId, "stop")
    suspend fun containerRestart(containerId: String) = repository.containerAction(containerId, "restart")
    suspend fun containerPause(containerId: String) = repository.containerAction(containerId, "pause")
    suspend fun containerUnpause(containerId: String) = repository.containerAction(containerId, "unpause")
    suspend fun containerKill(containerId: String) = repository.containerAction(containerId, "kill")
    suspend fun containerRemove(containerId: String) = repository.containerAction(containerId, "remove")
    suspend fun containerAction(containerId: String, action: String) = repository.containerAction(containerId, action)
}

class KubeUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getCluster() = repository.kubeCluster()
    suspend fun listNamespaces() = repository.kubeNamespaces()
    suspend fun listPods(namespace: String = "default") = repository.kubePods(namespace)
    suspend fun getPodDetail(podName: String, namespace: String = "default") = repository.kubePodDetail(podName, namespace)
    suspend fun getPodLogs(podName: String, namespace: String = "default", container: String = "", tail: Int = 100) = repository.kubePodLogs(podName, namespace, container, tail)
    suspend fun podExec(podName: String, namespace: String, container: String, command: String) = repository.kubePodExec(podName, namespace, container, command)
    suspend fun listDeployments(namespace: String = "default") = repository.kubeDeployments(namespace)
    suspend fun listServices(namespace: String = "default") = repository.kubeServices(namespace)
    suspend fun podDelete(podName: String, namespace: String = "default") = repository.kubePodAction(podName, namespace, "delete")
    suspend fun podRestart(podName: String, namespace: String = "default") = repository.kubePodAction(podName, namespace, "restart")
}

class KubePodDetailUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun getPodDetail(podName: String, namespace: String = "default") = repository.kubePodDetail(podName, namespace)
    suspend fun getPodLogs(podName: String, namespace: String = "default", container: String = "", tail: Int = 100) = repository.kubePodLogs(podName, namespace, container, tail)
    suspend fun podExec(podName: String, namespace: String, container: String, command: String) = repository.kubePodExec(podName, namespace, container, command)
    suspend fun podDelete(podName: String, namespace: String = "default") = repository.kubePodAction(podName, namespace, "delete")
    suspend fun podRestart(podName: String, namespace: String = "default") = repository.kubePodAction(podName, namespace, "restart")
}

class FederationUseCase @Inject constructor(
    private val repository: DesktopRepository,
) {
    suspend fun listNodes() = repository.federationNodes()
    suspend fun getNodeDetail(nodeId: String) = repository.federationNodeDetail(nodeId)
    suspend fun nodeAction(nodeId: String, action: String) = repository.federationAction(nodeId, action)
}

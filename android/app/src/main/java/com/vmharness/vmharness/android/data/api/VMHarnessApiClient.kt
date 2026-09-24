package com.vmharness.android.data.api

import com.vmharness.android.data.model.*
import com.vmharness.android.data.store.PairingStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject

// ── Exception types ────────────────────────────────────────────────────────────

open class ApiException(
    override val message: String,
    val statusCode: Int = 0,
    val body: String = "",
) : Exception(message)

class PairingException(msg: String) : ApiException(msg, 0, msg)

class NotPairedException : Exception("Device not paired — run pairing flow first")

open class TailscaleNotRunningException(msg: String) : Exception(msg)

class DesktopUnreachableException(host: String) : Exception(
    "Cannot reach desktop at $host. Is Tailscale running and the desktop API server online?",
)

// ── API key provider ────────────────────────────────────────────────────────────

interface ApiKeyProvider {
    fun getApiKey(): String?
    fun getHost(): String?
    fun getPort(): Int
    fun isPaired(): Boolean
}

class DefaultApiKeyProvider(
    private val pairingStore: PairingStore,
) : ApiKeyProvider {
    override fun getApiKey(): String? = pairingStore.apiKey
    override fun getHost(): String? = pairingStore.ip.takeIf { !it.isNullOrBlank() } ?: pairingStore.host
    override fun getPort(): Int = pairingStore.port
    override fun isPaired(): Boolean = pairingStore.isPaired
}

// ── JSON ────────────────────────────────────────────────────────────────────────

private val json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    encodeDefaults = true
}

// ── OkHttp Authenticator ────────────────────────────────────────────────────────

class ApiKeyAuthenticator(
    private val apiKeyProvider: ApiKeyProvider,
    private val pairingStore: PairingStore,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.code == 401 && apiKeyProvider.isPaired()) {
            val key = apiKeyProvider.getApiKey()
            if (key != null) {
                return response.request.newBuilder()
                    .header("X-API-Key", key)
                    .build()
            }
        }
        if (response.code == 401) {
            pairingStore.clear()
        }
        return null
    }
}

// ── API client ──────────────────────────────────────────────────────────────────

class VMHarnessApiClient(
    private val okHttp: OkHttpClient,
    private val apiKeyProvider: ApiKeyProvider,
) {

    private val baseUrl: String
        get() {
            val host = apiKeyProvider.getHost() ?: return "http://localhost"
            val port = apiKeyProvider.getPort()
            return "http://$host:$port"
        }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }

    private fun jsonBody(): MediaType = JSON_MEDIA_TYPE

    private fun parseError(response: Response): ApiException {
        val body = response.body?.string() ?: ""
        val statusCode = response.code
        val msg = try {
            val parsed = json.decodeFromString<Map<String, String>>(body)
            parsed["error"] ?: parsed["detail"] ?: body
        } catch (_: Exception) {
            body
        }
        return ApiException(msg.take(500), statusCode, body)
    }

    private suspend fun <T> execute(
        requestBuilder: () -> Request.Builder,
        parse: (ResponseBody) -> T,
    ): T {
        val request = requestBuilder()
            .header("X-API-Key", apiKeyProvider.getApiKey() ?: "")
            .build()
        val response = okHttp.newCall(request).execute()
        if (!response.isSuccessful) {
            throw parseError(response)
        }
        return parse(response.body!!)
    }

    // ── Auth endpoints ──────────────────────────────────────────────────────────

    suspend fun pair(token: String): PairingResponse {
        val body = buildJsonObject { put("token", JsonPrimitive(token)) }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/auth/pair").post(body) },
            { resp -> json.decodeFromString<PairingResponse>(resp.string()) },
        )
    }

    suspend fun verify(): VerifyResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/auth/verify").get() },
            { resp -> json.decodeFromString<VerifyResponse>(resp.string()) },
        )
    }

    suspend fun revoke(): Map<String, Any> {
        val body = "{}".toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/auth/revoke").post(body) },
            { resp -> json.decodeFromString<Map<String, Any>>(resp.string()) },
        )
    }

    suspend fun getPublicKey(): String {
        val response = okHttp.newCall(
            Request.Builder().url("$baseUrl/api/v1/auth/public-key").get().build(),
        ).execute()
        if (!response.isSuccessful) throw parseError(response)
        return response.body!!.string()
    }

    // ── Dashboard & VMs ─────────────────────────────────────────────────────────

    suspend fun dashboard(): DashboardResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/").get() },
            { resp -> json.decodeFromString<DashboardResponse>(resp.string()) },
        )
    }

    suspend fun listVms(): List<VmSummary> {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms").get() },
            { resp -> json.decodeFromString<List<VmSummary>>(resp.string()) },
        )
    }

    suspend fun getVm(name: String): VmDetail {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$name").get() },
            { resp -> json.decodeFromString<VmDetail>(resp.string()) },
        )
    }

    suspend fun vmAction(vmName: String, action: String): VmActionResponse {
        val body = "{}".toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$vmName/$action").post(body) },
            { resp -> json.decodeFromString<VmActionResponse>(resp.string()) },
        )
    }

    // ── SSH ──────────────────────────────────────────────────────────────────────

    suspend fun sshCommand(
        vmName: String,
        command: String,
        timeout: Int = 30,
    ): SshCommandResponse {
        val body = buildJsonObject {
            put("command", JsonPrimitive(command))
            put("timeout", JsonPrimitive(timeout))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$vmName/ssh/command").post(body) },
            { resp -> json.decodeFromString<SshCommandResponse>(resp.string()) },
        )
    }

    // ── Metrics ──────────────────────────────────────────────────────────────────

    suspend fun metrics(): MetricsResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/metrics").get() },
            { resp -> json.decodeFromString<MetricsResponse>(resp.string()) },
        )
    }

    // ── Settings ─────────────────────────────────────────────────────────────────

    suspend fun settings(): SettingsResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/settings").get() },
            { resp -> json.decodeFromString<SettingsResponse>(resp.string()) },
        )
    }

    suspend fun updateSetting(key: String, value: String): SettingsUpdateResponse {
        val body = buildJsonObject {
            put("key", JsonPrimitive(key))
            put("value", JsonPrimitive(value))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/settings").put(body) },
            { resp -> json.decodeFromString<SettingsUpdateResponse>(resp.string()) },
        )
    }

    // ── Credentials ──────────────────────────────────────────────────────────────

    suspend fun listCredentials(): List<CredentialInfo> {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/credentials").get() },
            { resp -> json.decodeFromString<List<CredentialInfo>>(resp.string()) },
        )
    }

    suspend fun getCredential(name: String): CredentialDetail {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/credentials/$name").get() },
            { resp -> json.decodeFromString<CredentialDetail>(resp.string()) },
        )
    }

    // ── Audit log ────────────────────────────────────────────────────────────────

    suspend fun auditLog(): List<AuditEntry> {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/security/audit").get() },
            { resp -> json.decodeFromString<List<AuditEntry>>(resp.string()) },
        )
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
        val body = buildJsonObject {
            put("name", kotlinx.serialization.json.JsonPrimitive(name))
            put("ram_mb", kotlinx.serialization.json.JsonPrimitive(ramMb))
            put("cpus", kotlinx.serialization.json.JsonPrimitive(cpus))
            put("disk_size_gb", kotlinx.serialization.json.JsonPrimitive(diskSizeGb))
            put("iso_path", kotlinx.serialization.json.JsonPrimitive(isoPath))
            put("network_mode", kotlinx.serialization.json.JsonPrimitive(networkMode))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms").post(body) },
            { resp -> json.decodeFromString<VmActionResponse>(resp.string()) },
        )
    }

    // ── Snapshots ───────────────────────────────────────────────────────────────

    suspend fun listSnapshots(vmName: String): List<SnapshotInfo> {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$vmName/snapshots").get() },
            { resp -> json.decodeFromString<List<SnapshotInfo>>(resp.string()) },
        )
    }

    suspend fun createSnapshot(vmName: String, snapshotName: String): VmActionResponse {
        val body = buildJsonObject {
            put("name", kotlinx.serialization.json.JsonPrimitive(snapshotName))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$vmName/snapshots").post(body) },
            { resp -> json.decodeFromString<VmActionResponse>(resp.string()) },
        )
    }

    suspend fun restoreSnapshot(vmName: String, snapshotName: String): VmActionResponse {
        val body = buildJsonObject {
            put("name", kotlinx.serialization.json.JsonPrimitive(snapshotName))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$vmName/snapshots/$snapshotName/restore").post(body) },
            { resp -> json.decodeFromString<VmActionResponse>(resp.string()) },
        )
    }

    // ── QMP Console ─────────────────────────────────────────────────────────────

    suspend fun executeQmpCommand(vmName: String, command: String): SshCommandResponse {
        val body = buildJsonObject {
            put("command", kotlinx.serialization.json.JsonPrimitive(command))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/vms/$vmName/qmp").post(body) },
            { resp -> json.decodeFromString<SshCommandResponse>(resp.string()) },
        )
    }

    // ── Logs ─────────────────────────────────────────────────────────────────────

    suspend fun logs(hasMore: Boolean = false): LogsResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/logs").get() },
            { resp -> json.decodeFromString<LogsResponse>(resp.string()) },
        )
    }

    // ── Health check ─────────────────────────────────────────────────────────────

    suspend fun healthCheck(): Map<String, Any> {
        val response = okHttp.newCall(
            Request.Builder().url("$baseUrl/health").get().build(),
        ).execute()
        if (!response.isSuccessful) {
            throw DesktopUnreachableException("$baseUrl")
        }
        return json.decodeFromString<Map<String, Any>>(response.body!!.string())
    }

    // ── WebSocket ────────────────────────────────────────────────────────────────

    fun wsUrl(path: String): String = "$baseUrl$path"

    // ── Stream helpers ───────────────────────────────────────────────────────────

    fun metricsStream(intervalMs: Long = 5000): Flow<MetricsResponse> = flow {
        while (true) {
            try {
                emit(metrics())
            } catch (_: Exception) {
                break
            }
            kotlinx.coroutines.delay(intervalMs)
        }
    }

    fun vmMetricsStream(vmName: String, intervalMs: Long = 5000): Flow<VmMetricsResponse> = flow {
        while (true) {
            try {
                val m = metrics()
                emit(VmMetricsResponse(
                    vmName = vmName,
                    vcpuUsage = m.cpuPercent,
                    ramUsed = m.ramUsed,
                    ramTotal = m.ramTotal,
                    diskReadBytes = m.diskUsed,
                    diskWriteBytes = 0.0,
                    netRxBytes = m.networkRx,
                    netTxBytes = m.networkTx,
                    timestamp = m.timestamp,
                ))
            } catch (_: Exception) {
                break
            }
            kotlinx.coroutines.delay(intervalMs)
        }
    }


    // ── Containers ───────────────────────────────────────────────────────────────

    suspend fun listContainers(): List<Container> {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/containers").get() },
            { resp -> json.decodeFromString<List<Container>>(resp.string()) },
        )
    }

    suspend fun getContainer(containerId: String): Container {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/containers/$containerId").get() },
            { resp -> json.decodeFromString<Container>(resp.string()) },
        )
    }

    suspend fun containerStats(containerId: String): ContainerStats {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/containers/$containerId/stats").get() },
            { resp -> json.decodeFromString<ContainerStats>(resp.string()) },
        )
    }

    suspend fun containerLogs(containerId: String, tail: Int = 100): ContainerLogsResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/containers/$containerId/logs?tail=$tail").get() },
            { resp -> json.decodeFromString<ContainerLogsResponse>(resp.string()) },
        )
    }

    suspend fun containerExec(containerId: String, command: String): SshCommandResponse {
        val body = buildJsonObject {
            put("command", JsonPrimitive(command))
            put("tty", JsonPrimitive(true))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/containers/$containerId/exec").post(body) },
            { resp -> json.decodeFromString<SshCommandResponse>(resp.string()) },
        )
    }

    suspend fun containerAction(containerId: String, action: String): ContainerActionResponse {
        val body = "{}".toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/containers/$containerId/$action").post(body) },
            { resp -> json.decodeFromString<ContainerActionResponse>(resp.string()) },
        )
    }


    // ── Kubernetes ───────────────────────────────────────────────────────────────

    suspend fun kubeCluster(): KubeCluster {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/cluster").get() },
            { resp -> json.decodeFromString<KubeCluster>(resp.string()) },
        )
    }

    suspend fun kubeNamespaces(): List<KubeNamespace> {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces").get() },
            { resp -> json.decodeFromString<List<KubeNamespace>>(resp.string()) },
        )
    }

    suspend fun kubePods(namespace: String = "default"): KubePodsResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces/$namespace/pods").get() },
            { resp -> json.decodeFromString<KubePodsResponse>(resp.string()) },
        )
    }

    suspend fun kubePodDetail(podName: String, namespace: String = "default"): KubePodDetail {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces/$namespace/pods/$podName").get() },
            { resp -> json.decodeFromString<KubePodDetail>(resp.string()) },
        )
    }

    suspend fun kubePodLogs(podName: String, namespace: String = "default", container: String = "", tail: Int = 100): KubePodLogsResponse {
        val url = if (container.isNotBlank()) {
            "$baseUrl/api/v1/k8s/namespaces/$namespace/pods/$podName/logs?container=$container&tail=$tail"
        } else {
            "$baseUrl/api/v1/k8s/namespaces/$namespace/pods/$podName/logs?tail=$tail"
        }
        return execute(
            { Request.Builder().url(url).get() },
            { resp -> json.decodeFromString<KubePodLogsResponse>(resp.string()) },
        )
    }

    suspend fun kubePodExec(podName: String, namespace: String, container: String, command: String): SshCommandResponse {
        val body = buildJsonObject {
            put("command", JsonPrimitive(command))
            put("container", JsonPrimitive(container))
            put("tty", JsonPrimitive(true))
        }.toString().toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces/$namespace/pods/$podName/exec").post(body) },
            { resp -> json.decodeFromString<SshCommandResponse>(resp.string()) },
        )
    }

    suspend fun kubeDeployments(namespace: String = "default"): KubeDeploymentsResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces/$namespace/deployments").get() },
            { resp -> json.decodeFromString<KubeDeploymentsResponse>(resp.string()) },
        )
    }

    suspend fun kubeServices(namespace: String = "default"): KubeServicesResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces/$namespace/services").get() },
            { resp -> json.decodeFromString<KubeServicesResponse>(resp.string()) },
        )
    }

    suspend fun kubePodAction(podName: String, namespace: String, action: String): KubePodActionResponse {
        val body = "{}".toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/k8s/namespaces/$namespace/pods/$podName/$action").post(body) },
            { resp -> json.decodeFromString<KubePodActionResponse>(resp.string()) },
        )
    }


    // ── Federation ───────────────────────────────────────────────────────────────

    suspend fun federationNodes(): FederatedNodesResponse {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/federation/nodes").get() },
            { resp -> json.decodeFromString<FederatedNodesResponse>(resp.string()) },
        )
    }

    suspend fun federationNodeDetail(nodeId: String): FederatedNodeDetail {
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/federation/nodes/$nodeId").get() },
            { resp -> json.decodeFromString<FederatedNodeDetail>(resp.string()) },
        )
    }

    suspend fun federationAction(nodeId: String, action: String): FederationActionResponse {
        val body = "{}".toRequestBody(jsonBody())
        return execute(
            { Request.Builder().url("$baseUrl/api/v1/federation/nodes/$nodeId/$action").post(body) },
            { resp -> json.decodeFromString<FederationActionResponse>(resp.string()) },
        )
    }

}

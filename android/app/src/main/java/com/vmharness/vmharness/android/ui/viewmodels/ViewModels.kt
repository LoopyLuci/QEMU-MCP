package com.vmharness.android.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vmharness.android.data.api.NotPairedException
import com.vmharness.android.data.model.*
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.domain.usecase.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import javax.inject.Inject

// ── UI state wrappers ──────────────────────────────────────────────────────────

sealed class UiState<out T> {
    object Idle : UiState<Nothing>()
    object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val message: String) : UiState<Nothing>()
}

// ── Pairing ────────────────────────────────────────────────────────────────────

data class PairingUiState(
    val status: UiState<Unit> = UiState.Idle,
    val pendingToken: String? = null,
    val tailscaleInstalled: Boolean = false,
    val tailscaleRunning: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class PairingViewModel @Inject constructor(
    private val pairingUseCase: PairingUseCase,
    private val pairingStore: PairingStore,
) : ViewModel() {

    private val _state = MutableStateFlow(PairingUiState())
    val state: StateFlow<PairingUiState> = _state.asStateFlow()

    init {
        checkPaired()
        val pending = pairingStore.pendingToken
        if (!pending.isNullOrBlank()) {
            setPendingToken(pending)
            pairingStore.pendingToken = null
        }
    }

    private fun checkPaired() {
        if (pairingUseCase.isPaired()) {
            viewModelScope.launch {
                _state.value = _state.value.copy(
                    status = try {
                        val verify = pairingUseCase.verify()
                        UiState.Success(Unit)
                    } catch (e: Exception) {
                        UiState.Error(e.message ?: "Pairing invalid — please re-pair")
                    },
                )
            }
        }
    }

    fun setPendingToken(token: String) {
        android.util.Log.d("VM-Harness", "setPendingToken called, token length=${token.length}")
        _state.value = _state.value.copy(pendingToken = token)
    }

    fun pairFromToken(token: String) {
        android.util.Log.d("VM-Harness", "pairFromToken called, token length=${token.length} status=${_state.value.status}")
        viewModelScope.launch(Dispatchers.IO) {
            _state.value = _state.value.copy(status = UiState.Loading)
            android.util.Log.d("VM-Harness", "pairFromToken: state set to Loading")
            try {
                val response = pairingUseCase.pairFromToken(token)
                android.util.Log.d("VM-Harness", "pairFromToken: use case returned response=${response.paired}, setting Success")
                _state.value = _state.value.copy(
                    status = UiState.Success(Unit),
                    pendingToken = null,
                )
                android.util.Log.d("VM-Harness", "pairFromToken: state set to Success")
            } catch (e: Exception) {
                android.util.Log.e("VM-Harness", "pairFromToken failed: ${e.message}", e)
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Pairing failed"),
                    error = e.message,
                )
            }
        }
    }

    fun setIsPaired(isPaired: Boolean) {}

    fun reset() {
        _state.value = PairingUiState()
    }
}

// ── Dashboard ──────────────────────────────────────────────────────────────────

data class DashboardUiState(
    val status: UiState<DashboardResponse> = UiState.Idle,
    val vms: List<VmSummary> = emptyList(),
    val metrics: Map<String, Any> = emptyMap(),
    val tailscaleIp: String = "",
    val machineId: String = "",
    val isRefreshing: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val dashboardUseCase: DashboardUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(DashboardUiState())
    val state: StateFlow<DashboardUiState> = _state.asStateFlow()

    private var autoRefreshJob: Job? = null

    init {
        loadDashboard()
        startAutoRefresh()
    }

    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }

    fun startAutoRefresh(intervalMs: Long = 10000) {
        autoRefreshJob?.cancel()
        autoRefreshJob = viewModelScope.launch {
            while (true) {
                delay(intervalMs)
                loadDashboard(silent = true)
            }
        }
    }

    fun stopAutoRefresh() {
        autoRefreshJob?.cancel()
    }

    fun loadDashboard(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _state.value = _state.value.copy(status = UiState.Loading)
            } else {
                _state.value = _state.value.copy(isRefreshing = true)
            }
            try {
                val dashboard = dashboardUseCase.getDashboard()
                _state.value = _state.value.copy(
                    status = UiState.Success(dashboard),
                    vms = dashboard.vms,
                    metrics = dashboard.metrics,
                    tailscaleIp = dashboard.tailscaleIp,
                    machineId = dashboard.machineId,
                    isRefreshing = false,
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = if (_state.value.vms.isEmpty()) UiState.Error(e.message ?: "Failed to load dashboard") else _state.value.status,
                    isRefreshing = false,
                    error = if (_state.value.vms.isEmpty()) e.message else null,
                )
            }
        }
    }

    fun refresh() {
        loadDashboard()
    }
}

// ── VM Control ─────────────────────────────────────────────────────────────────

data class VmControlUiState(
    val status: UiState<VmDetail> = UiState.Idle,
    val vmName: String = "",
    val isLoading: Boolean = false,
    val actionInProgress: Boolean = false,
    val lastAction: VmActionResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class VmControlViewModel @Inject constructor(
    private val vmControlUseCase: VmControlUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(VmControlUiState())
    val state: StateFlow<VmControlUiState> = _state.asStateFlow()

    private var autoRefreshJob: Job? = null

    fun loadVm(vmName: String) {
        _state.value = VmControlUiState(vmName = vmName, status = UiState.Loading)
        startAutoRefresh()
    }

    private fun startAutoRefresh(intervalMs: Long = 5000) {
        autoRefreshJob?.cancel()
        autoRefreshJob = viewModelScope.launch {
            while (true) {
                delay(intervalMs)
                if (_state.value.vmName.isNotBlank() && !_state.value.actionInProgress) {
                    refreshSilently()
                }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }

    private suspend fun refreshSilently() {
        try {
            val vmName = _state.value.vmName
            if (vmName.isBlank()) return
            val detail = vmControlUseCase.getVm(vmName)
            _state.value = _state.value.copy(
                status = UiState.Success(detail),
                isLoading = false,
            )
        } catch (_: Exception) {}
    }

    fun startVm() { performAction("start") }
    fun stopVm(graceful: Boolean = true) { performAction("stop") }
    fun resetVm() { performAction("reset") }
    fun powerdownVm() { performAction("powerdown") }
    fun pauseVm() { performAction("pause") }
    fun resumeVm() { performAction("resume") }
    fun ejectCdrom() { performAction("eject") }

    private fun performAction(action: String) {
        val vmName = _state.value.vmName
        if (vmName.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = true)
            try {
                val result = when (action) {
                    "start" -> vmControlUseCase.startVm(vmName)
                    "stop" -> vmControlUseCase.stopVm(vmName)
                    "reset" -> vmControlUseCase.resetVm(vmName)
                    "powerdown" -> vmControlUseCase.powerdownVm(vmName)
                    "pause" -> vmControlUseCase.pauseVm(vmName)
                    "resume" -> vmControlUseCase.resumeVm(vmName)
                    "eject" -> vmControlUseCase.ejectCdrom(vmName)
                    else -> throw IllegalArgumentException("Unknown action: $action")
                }
                _state.value = _state.value.copy(
                    lastAction = result,
                    actionInProgress = false,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    actionInProgress = false,
                    error = e.message,
                )
            }
        }
    }
}

// ── Guest Terminal ─────────────────────────────────────────────────────────────

data class TerminalUiState(
    val vmName: String = "",
    val output: String = "",
    val isLoading: Boolean = false,
    val commandInProgress: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class GuestTerminalViewModel @Inject constructor(
    private val vmControlUseCase: VmControlUseCase,
    private val pairingStore: PairingStore,
) : ViewModel() {

    private val _state = MutableStateFlow(TerminalUiState())
    val state: StateFlow<TerminalUiState> = _state.asStateFlow()

    fun setVmName(vmName: String) {
        _state.value = _state.value.copy(vmName = vmName, output = "Connected to $vmName\n")
    }

    fun executeCommand(command: String) {
        val vmName = _state.value.vmName
        if (vmName.isBlank() || command.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(
                commandInProgress = true,
                output = _state.value.output + "$ $command\n",
            )
            try {
                val result = vmControlUseCase.executeCommand(vmName, command)
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    output = _state.value.output + result.output + "\n",
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    output = _state.value.output + "Error: ${e.message}\n",
                    error = e.message,
                )
            }
        }
    }

    fun clearOutput() {
        _state.value = _state.value.copy(output = "")
    }
}

// ── VM Creation ────────────────────────────────────────────────────────────────

data class VmCreationUiState(
    val status: UiState<Unit> = UiState.Idle,
    val name: String = "",
    val ramMb: Int = 4096,
    val cpus: Int = 2,
    val diskSizeGb: Int = 40,
    val isoPath: String = "",
    val networkMode: String = "nat",
    val isCreating: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class VmCreationViewModel @Inject constructor(
    private val vmControlUseCase: VmControlUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(VmCreationUiState())
    val state: StateFlow<VmCreationUiState> = _state.asStateFlow()

    fun updateName(name: String) { _state.value = _state.value.copy(name = name) }
    fun updateRam(ram: Int) { _state.value = _state.value.copy(ramMb = ram) }
    fun updateCpus(cpus: Int) { _state.value = _state.value.copy(cpus = cpus) }
    fun updateDiskSize(size: Int) { _state.value = _state.value.copy(diskSizeGb = size) }
    fun updateIsoPath(path: String) { _state.value = _state.value.copy(isoPath = path) }
    fun updateNetworkMode(mode: String) { _state.value = _state.value.copy(networkMode = mode) }

    fun createVm() {
        val s = _state.value
        if (s.name.isBlank()) {
            _state.value = s.copy(error = "VM name cannot be empty")
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(isCreating = true, error = null)
            try {
                vmControlUseCase.createVm(
                    name = s.name,
                    ramMb = s.ramMb,
                    cpus = s.cpus,
                    diskSizeGb = s.diskSizeGb,
                    isoPath = s.isoPath,
                    networkMode = s.networkMode,
                )
                _state.value = _state.value.copy(
                    status = UiState.Success(Unit),
                    isCreating = false,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isCreating = false,
                    error = e.message,
                )
            }
        }
    }

    fun reset() {
        _state.value = VmCreationUiState()
    }
}

// ── Snapshots ──────────────────────────────────────────────────────────────────

data class SnapshotUiState(
    val vmName: String = "",
    val snapshots: List<SnapshotInfo> = emptyList(),
    val status: UiState<Unit> = UiState.Idle,
    val isCreating: Boolean = false,
    val isRestoring: Boolean = false,
    val newName: String = "",
    val error: String? = null,
)

@HiltViewModel
class SnapshotViewModel @Inject constructor(
    private val vmControlUseCase: VmControlUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(SnapshotUiState())
    val state: StateFlow<SnapshotUiState> = _state.asStateFlow()

    fun setVmName(vmName: String) {
        _state.value = _state.value.copy(vmName = vmName)
        loadSnapshots()
    }

    fun loadSnapshots() {
        val vmName = _state.value.vmName
        if (vmName.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(status = UiState.Loading)
            try {
                val result = vmControlUseCase.listSnapshots(vmName)
                _state.value = _state.value.copy(
                    snapshots = result,
                    status = UiState.Success(Unit),
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load snapshots"),
                    error = e.message,
                )
            }
        }
    }

    fun updateNewName(name: String) {
        _state.value = _state.value.copy(newName = name)
    }

    fun createSnapshot() {
        val vmName = _state.value.vmName
        val snapName = _state.value.newName.ifBlank { "snapshot-${System.currentTimeMillis()}" }
        if (vmName.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isCreating = true)
            try {
                vmControlUseCase.createSnapshot(vmName, snapName)
                _state.value = _state.value.copy(isCreating = false, newName = "")
                loadSnapshots()
            } catch (e: Exception) {
                _state.value = _state.value.copy(isCreating = false, error = e.message)
            }
        }
    }

    fun restoreSnapshot(snapshotName: String) {
        val vmName = _state.value.vmName
        if (vmName.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isRestoring = true)
            try {
                vmControlUseCase.restoreSnapshot(vmName, snapshotName)
                _state.value = _state.value.copy(isRestoring = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(isRestoring = false, error = e.message)
            }
        }
    }
}

// ── QMP Console ────────────────────────────────────────────────────────────────

data class QmpConsoleUiState(
    val vmName: String = "",
    val output: String = "",
    val isConnected: Boolean = false,
    val commandInProgress: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class QmpConsoleViewModel @Inject constructor(
    private val vmControlUseCase: VmControlUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(QmpConsoleUiState())
    val state: StateFlow<QmpConsoleUiState> = _state.asStateFlow()

    fun setVmName(vmName: String) {
        _state.value = _state.value.copy(vmName = vmName, output = "QMP Console: $vmName\n")
    }

    fun executeQmpCommand(command: String) {
        val vmName = _state.value.vmName
        if (vmName.isBlank() || command.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(
                commandInProgress = true,
                output = _state.value.output + " > $command\n",
            )
            try {
                val result = vmControlUseCase.executeQmpCommand(vmName, command)
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    output = _state.value.output + result.output + "\n",
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    output = _state.value.output + "Error: ${e.message}\n",
                )
            }
        }
    }

    fun clearOutput() {
        _state.value = _state.value.copy(output = "")
    }
}

// ── Telemetry ──────────────────────────────────────────────────────────────────

data class TelemetryUiState(
    val status: UiState<MetricsResponse> = UiState.Idle,
    val metrics: MetricsResponse? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class TelemetryViewModel @Inject constructor(
    private val telemetryUseCase: TelemetryUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(TelemetryUiState())
    val state: StateFlow<TelemetryUiState> = _state.asStateFlow()

    init {
        loadMetrics()
    }

    private var refreshJob: Job? = null

    fun startAutoRefresh(intervalMs: Long = 5000) {
        refreshJob?.cancel()
        refreshJob = viewModelScope.launch {
            while (true) {
                loadMetrics()
                delay(intervalMs)
            }
        }
    }

    fun stopAutoRefresh() {
        refreshJob?.cancel()
    }

    fun loadMetrics() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            try {
                val metrics = telemetryUseCase.getMetrics()
                _state.value = _state.value.copy(
                    status = UiState.Success(metrics),
                    metrics = metrics,
                    isLoading = false,
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load metrics"),
                    isLoading = false,
                    error = e.message,
                )
            }
        }
    }
}

// ── Settings ────────────────────────────────────────────────────────────────────

data class SettingsUiState(
    val status: UiState<SettingsResponse> = UiState.Idle,
    val settings: SettingsResponse? = null,
    val isPaired: Boolean = false,
    val displayName: String? = null,
    val tailscaleIp: String? = null,
    val error: String? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsUseCase: SettingsUseCase,
    private val pairingUseCase: PairingUseCase,
    private val pairingStore: PairingStore,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        loadSettings()
    }

    internal fun loadSettings() {
        viewModelScope.launch {
            _state.value = _state.value.copy(status = UiState.Loading)
            try {
                val settings = settingsUseCase.getSettings()
                _state.value = _state.value.copy(
                    status = UiState.Success(settings),
                    settings = settings,
                    isPaired = pairingUseCase.isPaired(),
                    displayName = pairingStore.displayName,
                    tailscaleIp = pairingStore.ip,
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load settings"),
                    error = e.message,
                )
            }
        }
    }

    fun revokePairing() {
        viewModelScope.launch {
            try {
                pairingUseCase.revoke()
                _state.value = _state.value.copy(
                    isPaired = false,
                    displayName = null,
                    tailscaleIp = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }
}

// ── Security ────────────────────────────────────────────────────────────────────

data class SecurityUiState(
    val credentials: List<CredentialInfo> = emptyList(),
    val credentialsStatus: UiState<Unit> = UiState.Idle,
    val auditLog: List<AuditEntry> = emptyList(),
    val auditLogStatus: UiState<Unit> = UiState.Idle,
    val selectedCredential: CredentialDetail? = null,
    val showCredentialValue: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class SecurityViewModel @Inject constructor(
    private val securityUseCase: SecurityUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(SecurityUiState())
    val state: StateFlow<SecurityUiState> = _state.asStateFlow()

    init {
        loadCredentials()
        loadAuditLog()
    }

    fun loadCredentials() {
        viewModelScope.launch {
            _state.value = _state.value.copy(credentialsStatus = UiState.Loading)
            try {
                val creds = securityUseCase.listCredentials()
                _state.value = _state.value.copy(
                    credentials = creds,
                    credentialsStatus = UiState.Success(Unit),
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    credentialsStatus = UiState.Error(e.message ?: "Failed to load credentials"),
                    error = e.message,
                )
            }
        }
    }

    fun loadAuditLog() {
        viewModelScope.launch {
            _state.value = _state.value.copy(auditLogStatus = UiState.Loading)
            try {
                val audit = securityUseCase.getAuditLog()
                _state.value = _state.value.copy(
                    auditLog = audit,
                    auditLogStatus = UiState.Success(Unit),
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    auditLogStatus = UiState.Error(e.message ?: "Failed to load audit log"),
                    error = e.message,
                )
            }
        }
    }

    fun selectCredential(name: String) {
        viewModelScope.launch {
            try {
                val detail = securityUseCase.getCredential(name)
                _state.value = _state.value.copy(selectedCredential = detail)
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }

    fun toggleShowCredentialValue() {
        _state.value = _state.value.copy(showCredentialValue = !_state.value.showCredentialValue)
    }

    fun clearSelection() {
        _state.value = _state.value.copy(selectedCredential = null, showCredentialValue = false)
    }
}

// ── Logs ────────────────────────────────────────────────────────────────────────

data class LogsUiState(
    val logs: List<LogEntry> = emptyList(),
    val status: UiState<Unit> = UiState.Idle,
    val error: String? = null,
)

@HiltViewModel
class LogsViewModel @Inject constructor(
    private val logsUseCase: LogsUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(LogsUiState())
    val state: StateFlow<LogsUiState> = _state.asStateFlow()

    init {
        loadLogs()
    }

    fun loadLogs() {
        viewModelScope.launch {
            _state.value = _state.value.copy(status = UiState.Loading)
            try {
                val logs = logsUseCase.getLogs()
                _state.value = _state.value.copy(
                    logs = logs.logs,
                    status = UiState.Success(Unit),
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load logs"),
                    error = e.message,
                )
            }
        }
    }

    fun refresh() {
        loadLogs()
    }
}


// ── Container Detail ────────────────────────────────────────────────────────────

data class ContainerDetailUiState(
    val status: UiState<Container> = UiState.Idle,
    val container: Container? = null,
    val stats: ContainerStats? = null,
    val logs: String = "",
    val terminalOutput: String = "",
    val isLoading: Boolean = false,
    val actionInProgress: Boolean = false,
    val commandInProgress: Boolean = false,
    val lastAction: ContainerActionResponse? = null,
    val error: String? = null,
)

@HiltViewModel
class ContainerDetailViewModel @Inject constructor(
    private val containerDetailUseCase: ContainerDetailUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(ContainerDetailUiState())
    val state: StateFlow<ContainerDetailUiState> = _state.asStateFlow()

    private var containerId: String = ""
    private var autoRefreshJob: Job? = null

    fun setContainerId(id: String) {
        containerId = id
        loadContainer()
        startAutoRefresh()
    }

    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }

    private fun startAutoRefresh(intervalMs: Long = 5000) {
        autoRefreshJob?.cancel()
        autoRefreshJob = viewModelScope.launch {
            while (true) {
                delay(intervalMs)
                if (containerId.isNotBlank()) {
                    refreshSilently()
                }
            }
        }
    }

    private suspend fun refreshSilently() {
        try {
            val container = containerDetailUseCase.getContainer(containerId)
            val stats = containerDetailUseCase.containerStats(containerId)
            _state.value = _state.value.copy(
                status = UiState.Success(container),
                container = container,
                stats = stats,
            )
        } catch (_: Exception) {}
    }

    fun loadContainer() {
        viewModelScope.launch {
            _state.value = _state.value.copy(status = UiState.Loading)
            try {
                val container = containerDetailUseCase.getContainer(containerId)
                _state.value = _state.value.copy(
                    status = UiState.Success(container),
                    container = container,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load container"),
                    error = e.message,
                )
            }
        }
    }

    fun loadLogs(tail: Int = 100) {
        viewModelScope.launch {
            try {
                val logs = containerDetailUseCase.containerLogs(containerId, tail)
                _state.value = _state.value.copy(logs = logs.logs)
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }

    fun startContainer() { performAction("start") }
    fun stopContainer() { performAction("stop") }
    fun restartContainer() { performAction("restart") }
    fun pauseContainer() { performAction("pause") }
    fun unpauseContainer() { performAction("unpause") }
    fun killContainer() { performAction("kill") }
    fun removeContainer() { performAction("remove") }

    private fun performAction(action: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = true)
            try {
                val result = containerDetailUseCase.containerAction(containerId, action)
                _state.value = _state.value.copy(
                    lastAction = result,
                    actionInProgress = false,
                )
                loadContainer()
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    actionInProgress = false,
                    error = e.message,
                )
            }
        }
    }

    fun executeCommand(command: String) {
        if (command.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(
                commandInProgress = true,
                terminalOutput = _state.value.terminalOutput + "$ " + command + "\n",
            )
            try {
                val result = containerDetailUseCase.containerExec(containerId, command)
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    terminalOutput = _state.value.terminalOutput + result.output + "\n",
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    terminalOutput = _state.value.terminalOutput + "Error: " + (e.message ?: "Unknown") + "\n",
                    error = e.message,
                )
            }
        }
    }

    fun clearTerminal() {
        _state.value = _state.value.copy(terminalOutput = "")
    }
}


// ── Kube Overview ──────────────────────────────────────────────────────────────

data class KubeUiState(
    val clusterStatus: UiState<KubeCluster> = UiState.Idle,
    val cluster: KubeCluster? = null,
    val podsStatus: UiState<KubePodsResponse> = UiState.Idle,
    val pods: List<KubePod> = emptyList(),
    val deployments: List<KubeDeployment> = emptyList(),
    val services: List<KubeService> = emptyList(),
    val namespaces: List<KubeNamespace> = emptyList(),
    val selectedNamespace: String = "default",
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class KubeViewModel @Inject constructor(
    private val kubeUseCase: KubeUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(KubeUiState())
    val state: StateFlow<KubeUiState> = _state.asStateFlow()

    private var autoRefreshJob: Job? = null

    init {
        loadCluster()
        loadNamespaces()
        loadPods()
        loadDeployments()
        loadServices()
        startAutoRefresh()
    }

    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }

    fun startAutoRefresh(intervalMs: Long = 5000) {
        autoRefreshJob?.cancel()
        autoRefreshJob = viewModelScope.launch {
            while (true) {
                delay(intervalMs)
                refreshSilently()
            }
        }
    }

    fun stopAutoRefresh() {
        autoRefreshJob?.cancel()
    }

    private suspend fun refreshSilently() {
        try {
            val namespace = _state.value.selectedNamespace
            val cluster = kubeUseCase.getCluster()
            val pods = kubeUseCase.listPods(namespace)
            _state.value = _state.value.copy(
                cluster = cluster,
                clusterStatus = UiState.Success(cluster),
                pods = pods.pods,
                podsStatus = UiState.Success(pods),
            )
        } catch (_: Exception) {}
    }

    fun loadCluster() {
        viewModelScope.launch {
            _state.value = _state.value.copy(clusterStatus = UiState.Loading)
            try {
                val cluster = kubeUseCase.getCluster()
                _state.value = _state.value.copy(
                    cluster = cluster,
                    clusterStatus = UiState.Success(cluster),
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    clusterStatus = UiState.Error(e.message ?: "Failed to load cluster"),
                    error = e.message,
                )
            }
        }
    }

    fun loadNamespaces() {
        viewModelScope.launch {
            try {
                val namespaces = kubeUseCase.listNamespaces()
                _state.value = _state.value.copy(namespaces = namespaces)
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }

    fun loadPods(namespace: String = "default") {
        _state.value = _state.value.copy(selectedNamespace = namespace)
        viewModelScope.launch {
            _state.value = _state.value.copy(podsStatus = UiState.Loading)
            try {
                val pods = kubeUseCase.listPods(namespace)
                _state.value = _state.value.copy(
                    pods = pods.pods,
                    podsStatus = UiState.Success(pods),
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    podsStatus = UiState.Error(e.message ?: "Failed to load pods"),
                    error = e.message,
                )
            }
        }
    }

    fun loadDeployments(namespace: String = "default") {
        viewModelScope.launch {
            try {
                val deployments = kubeUseCase.listDeployments(namespace)
                _state.value = _state.value.copy(deployments = deployments.deployments)
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }

    fun loadServices(namespace: String = "default") {
        viewModelScope.launch {
            try {
                val services = kubeUseCase.listServices(namespace)
                _state.value = _state.value.copy(services = services.services)
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }

    fun selectNamespace(namespace: String) {
        _state.value = _state.value.copy(selectedNamespace = namespace)
        loadPods(namespace)
        loadDeployments(namespace)
        loadServices(namespace)
    }

    fun refresh() {
        loadCluster()
        loadNamespaces()
        loadPods(_state.value.selectedNamespace)
        loadDeployments(_state.value.selectedNamespace)
        loadServices(_state.value.selectedNamespace)
    }
}


// ── Kube Pod Detail ────────────────────────────────────────────────────────────

data class KubePodDetailUiState(
    val status: UiState<KubePodDetail> = UiState.Idle,
    val pod: KubePodDetail? = null,
    val podName: String = "",
    val namespace: String = "",
    val selectedContainer: String = "",
    val logs: String = "",
    val terminalOutput: String = "",
    val isLoading: Boolean = false,
    val actionInProgress: Boolean = false,
    val commandInProgress: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class KubePodDetailViewModel @Inject constructor(
    private val kubePodDetailUseCase: KubePodDetailUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(KubePodDetailUiState())
    val state: StateFlow<KubePodDetailUiState> = _state.asStateFlow()

    private var autoRefreshJob: Job? = null

    fun setPod(podName: String, namespace: String) {
        _state.value = _state.value.copy(podName = podName, namespace = namespace)
        loadPodDetail()
        startAutoRefresh()
    }

    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }

    private fun startAutoRefresh(intervalMs: Long = 5000) {
        autoRefreshJob?.cancel()
        autoRefreshJob = viewModelScope.launch {
            while (true) {
                delay(intervalMs)
                refreshSilently()
            }
        }
    }

    private suspend fun refreshSilently() {
        val podName = _state.value.podName
        val namespace = _state.value.namespace
        if (podName.isBlank()) return
        try {
            val pod = kubePodDetailUseCase.getPodDetail(podName, namespace)
            _state.value = _state.value.copy(
                status = UiState.Success(pod),
                pod = pod,
            )
        } catch (_: Exception) {}
    }

    fun loadPodDetail() {
        val podName = _state.value.podName
        val namespace = _state.value.namespace
        if (podName.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(status = UiState.Loading)
            try {
                val pod = kubePodDetailUseCase.getPodDetail(podName, namespace)
                val selectedContainer = if (_state.value.selectedContainer.isBlank() && pod.containers.isNotEmpty()) {
                    pod.containers.first().name
                } else {
                    _state.value.selectedContainer
                }
                _state.value = _state.value.copy(
                    status = UiState.Success(pod),
                    pod = pod,
                    selectedContainer = selectedContainer,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load pod detail"),
                    error = e.message,
                )
            }
        }
    }

    fun loadLogs(tail: Int = 100) {
        val podName = _state.value.podName
        val namespace = _state.value.namespace
        val container = _state.value.selectedContainer
        if (podName.isBlank()) return
        viewModelScope.launch {
            try {
                val logs = kubePodDetailUseCase.getPodLogs(podName, namespace, container, tail)
                _state.value = _state.value.copy(logs = logs.logs)
            } catch (e: Exception) {
                _state.value = _state.value.copy(error = e.message)
            }
        }
    }

    fun selectContainer(container: String) {
        _state.value = _state.value.copy(selectedContainer = container)
        loadLogs()
    }

    fun executeCommand(command: String) {
        val podName = _state.value.podName
        val namespace = _state.value.namespace
        val container = _state.value.selectedContainer
        if (podName.isBlank() || command.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(
                commandInProgress = true,
                terminalOutput = _state.value.terminalOutput + "$ " + command + "\n",
            )
            try {
                val result = kubePodDetailUseCase.podExec(podName, namespace, container, command)
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    terminalOutput = _state.value.terminalOutput + result.output + "\n",
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    commandInProgress = false,
                    terminalOutput = _state.value.terminalOutput + "Error: " + (e.message ?: "Unknown") + "\n",
                    error = e.message,
                )
            }
        }
    }

    fun deletePod() {
        val podName = _state.value.podName
        val namespace = _state.value.namespace
        if (podName.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = true)
            try {
                kubePodDetailUseCase.podDelete(podName, namespace)
                _state.value = _state.value.copy(actionInProgress = false)
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    actionInProgress = false,
                    error = e.message,
                )
            }
        }
    }

    fun clearTerminal() {
        _state.value = _state.value.copy(terminalOutput = "")
    }
}


// ── Federation ──────────────────────────────────────────────────────────────────

data class FederationUiState(
    val status: UiState<FederatedNodesResponse> = UiState.Idle,
    val nodes: List<FederatedNode> = emptyList(),
    val federationStatus: FederationStatus? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class FederationViewModel @Inject constructor(
    private val federationUseCase: FederationUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(FederationUiState())
    val state: StateFlow<FederationUiState> = _state.asStateFlow()

    private var autoRefreshJob: Job? = null

    init {
        loadNodes()
        startAutoRefresh()
    }

    override fun onCleared() {
        super.onCleared()
        autoRefreshJob?.cancel()
    }

    fun startAutoRefresh(intervalMs: Long = 10000) {
        autoRefreshJob?.cancel()
        autoRefreshJob = viewModelScope.launch {
            while (true) {
                delay(intervalMs)
                refreshSilently()
            }
        }
    }

    fun stopAutoRefresh() {
        autoRefreshJob?.cancel()
    }

    private suspend fun refreshSilently() {
        try {
            val response = federationUseCase.listNodes()
            _state.value = _state.value.copy(
                status = UiState.Success(response),
                nodes = response.nodes,
                federationStatus = response.status,
            )
        } catch (_: Exception) {}
    }

    fun loadNodes() {
        viewModelScope.launch {
            _state.value = _state.value.copy(status = UiState.Loading)
            try {
                val response = federationUseCase.listNodes()
                _state.value = _state.value.copy(
                    status = UiState.Success(response),
                    nodes = response.nodes,
                    federationStatus = response.status,
                    error = null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    status = UiState.Error(e.message ?: "Failed to load federation nodes"),
                    error = e.message,
                )
            }
        }
    }

    fun refresh() {
        loadNodes()
    }

    fun performNodeAction(nodeId: String, action: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            try {
                federationUseCase.nodeAction(nodeId, action)
                loadNodes()
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = e.message,
                )
            }
        }
    }
}

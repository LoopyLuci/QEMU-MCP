package com.vmharness.android.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.vmharness.android.data.api.NotPairedException
import com.vmharness.android.data.auth.PairingTokenVerifier
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.ui.screens.*
import com.vmharness.android.ui.viewmodels.*
import com.vmharness.android.ui.viewmodels.UiState
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.first
import javax.inject.Inject

sealed class Screen(val route: String) {
    object Pairing : Screen("pairing")
    object Dashboard : Screen("dashboard")
    object VmControl : Screen("vm_control/{vmName}") {
        fun createRoute(vmName: String) = "vm_control/$vmName"
    }
    object GuestTerminal : Screen("terminal/{vmName}") {
        fun createRoute(vmName: String) = "terminal/$vmName"
    }
    object VmCreation : Screen("vm_creation")
    object Snapshots : Screen("snapshots/{vmName}") {
        fun createRoute(vmName: String) = "snapshots/$vmName"
    }
    object QmpConsole : Screen("qmp_console/{vmName}") {
        fun createRoute(vmName: String) = "qmp_console/$vmName"
    }
    object Streaming : Screen("streaming/{vmName}") {
        fun createRoute(vmName: String) = "streaming/$vmName"
    }
    object Telemetry : Screen("telemetry")
    object Settings : Screen("settings")
    object Security : Screen("security")
    object Logs : Screen("logs")
    object SecurityAudit : Screen("security_audit")
    object QrScanner : Screen("qr_scanner")
    object ContainerDetail : Screen("container_detail/{containerId}") {
        fun createRoute(containerId: String) = "container_detail/$containerId"
    }
    object KubeOverview : Screen("kube_overview")
    object KubePodDetail : Screen("kube_pod_detail/{podName}/{namespace}") {
        fun createRoute(podName: String, namespace: String) = "kube_pod_detail/$podName/$namespace"
    }
    object Federation : Screen("federation")
}

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var pairingStore: PairingStore
    @Inject lateinit var pairingVerifier: PairingTokenVerifier

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        handleDeepLink(intent)

        setContent {
            VMHarnessAndroidTheme {
                MainScreen(pairingStore = pairingStore)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent) {
        val uri = intent.data
        if (uri != null && uri.scheme == "vmharness" && uri.host == "pair") {
            val keyParam = uri.getQueryParameter("key")
            if (!keyParam.isNullOrBlank()) {
                pairingStore.pendingToken = keyParam
            }
        }
    }
}

@Composable
fun VMHarnessAndroidTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(),
        typography = VMHarnessTypography,
        content = content,
    )
}

val VMHarnessTypography = Typography(
    bodyLarge = TextStyle(
        fontWeight = FontWeight.Normal,
        lineHeight = 24.sp,
        fontSize = 16.sp,
    ),
    bodyMedium = TextStyle(
        fontWeight = FontWeight.Normal,
        lineHeight = 22.sp,
        fontSize = 14.sp,
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        lineHeight = 20.sp,
        fontSize = 16.sp,
    ),
    titleLarge = TextStyle(
        fontWeight = FontWeight.Medium,
        lineHeight = 19.sp,
        fontSize = 22.sp,
    ),
)

@Composable
fun MainScreen(
    pairingStore: PairingStore,
) {
    val navController = rememberNavController()
    val pairingViewModel: PairingViewModel = hiltViewModel()
    val dashboardViewModel: DashboardViewModel = hiltViewModel()
    val vmControlViewModel: VmControlViewModel = hiltViewModel()
    val guestTerminalViewModel: GuestTerminalViewModel = hiltViewModel()
    val telemetryViewModel: TelemetryViewModel = hiltViewModel()
    val settingsViewModel: SettingsViewModel = hiltViewModel()
    val securityViewModel: SecurityViewModel = hiltViewModel()
    val logsViewModel: LogsViewModel = hiltViewModel()
    val vmCreationViewModel: VmCreationViewModel = hiltViewModel()
    val snapshotViewModel: SnapshotViewModel = hiltViewModel()
    val qmpConsoleViewModel: QmpConsoleViewModel = hiltViewModel()
    val containerDetailViewModel: ContainerDetailViewModel = hiltViewModel()
    val kubeViewModel: KubeViewModel = hiltViewModel()
    val kubePodDetailViewModel: KubePodDetailViewModel = hiltViewModel()
    val federationViewModel: FederationViewModel = hiltViewModel()

    // Check for pending token from deep link
    LaunchedEffect(Unit) {
        val pending = pairingStore.pendingToken
        if (!pending.isNullOrBlank()) {
            pairingViewModel.setPendingToken(pending)
            pairingStore.pendingToken = null
        }
    }

    // Observe pairing state and navigate on success
    val pairingState by pairingViewModel.state.collectAsState()
    LaunchedEffect(pairingState.status) {
        if (pairingState.status is UiState.Success) {
            navController.navigate(Screen.Dashboard.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    NavHost(
        navController = navController,
        startDestination = Screen.Pairing.route,
    ) {
        composable(Screen.Pairing.route) {
            PairingScreen(
                viewModel = pairingViewModel,
                pairingStore = pairingStore,
                onPaired = {
                    navController.navigate(Screen.Dashboard.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onScanQr = {
                    navController.navigate(Screen.QrScanner.route)
                },
            )
        }

        composable(Screen.QrScanner.route) {
            QrScannerScreen(
                onBack = { navController.popBackStack() },
                onCodeScanned = { token ->
                    pairingViewModel.setPendingToken(token)
                    navController.popBackStack()
                },
            )
        }

        composable(Screen.Dashboard.route) {
            DashboardScreen(
                onVmClick = { vmName ->
                    navController.navigate(Screen.VmControl.createRoute(vmName))
                },
                onTerminalClick = { vmName ->
                    navController.navigate(Screen.GuestTerminal.createRoute(vmName))
                },
                onSecurityClick = {
                    navController.navigate(Screen.Security.route)
                },
                onLogsClick = {
                    navController.navigate(Screen.Logs.route)
                },
                onVmCreate = {
                    navController.navigate(Screen.VmCreation.route)
                },
                onKubeClick = {
                    navController.navigate(Screen.KubeOverview.route)
                },
                onFederationClick = {
                    navController.navigate(Screen.Federation.route)
                },
            )
        }

        composable(
            route = Screen.VmControl.route,
            arguments = listOf(navArgument("vmName") { type = NavType.StringType }),
        ) { backStackEntry ->
            val vmName = backStackEntry.arguments?.getString("vmName") ?: ""
            VmControlScreen(
                vmName = vmName,
                onBack = { navController.popBackStack() },
                onTerminal = { navController.navigate(Screen.GuestTerminal.createRoute(vmName)) },
                onDashboard = { navController.navigate(Screen.Dashboard.route) },
                onStream = { navController.navigate(Screen.Streaming.createRoute(vmName)) },
            )
        }

        composable(
            route = Screen.QmpConsole.route,
            arguments = listOf(navArgument("vmName") { type = NavType.StringType }),
        ) { backStackEntry ->
            val vmName = backStackEntry.arguments?.getString("vmName") ?: ""
            QmpConsoleScreen(
                vmName = vmName,
                onBack = { navController.popBackStack() },
            )
        }

        composable(
            route = Screen.Streaming.route,
            arguments = listOf(navArgument("vmName") { type = NavType.StringType }),
        ) { backStackEntry ->
            val vmName = backStackEntry.arguments?.getString("vmName") ?: ""
            StreamingScreen(
                vmName = vmName,
                onBack = { navController.popBackStack() },
            )
        }

        composable(Screen.Telemetry.route) { TelemetryScreen() }

        composable(Screen.Settings.route) {
            SettingsScreen(
                onSecurityClick = { navController.navigate(Screen.Security.route) },
                onLogsClick = { navController.navigate(Screen.Logs.route) },
            )
        }

        composable(Screen.Security.route) {
            SecurityScreen(
                onBack = { navController.popBackStack() },
                onAuditClick = { navController.navigate(Screen.SecurityAudit.route) },
            )
        }

        composable(Screen.Logs.route) { LogsScreen(onBack = { navController.popBackStack() }) }

        composable(Screen.SecurityAudit.route) {
            SecurityScreen(onBack = { navController.popBackStack() }, showAudit = true, onAuditClick = {})
        }

        composable(Screen.VmCreation.route) {
            VmCreationScreen(
                onBack = { navController.popBackStack() },
                onCreated = { vmName ->
                    navController.popBackStack()
                    navController.navigate(Screen.VmControl.createRoute(vmName))
                },
            )
        }

        composable(
            route = Screen.Snapshots.route,
            arguments = listOf(navArgument("vmName") { type = NavType.StringType }),
        ) { backStackEntry ->
            val vmName = backStackEntry.arguments?.getString("vmName") ?: ""
            SnapshotScreen(
                vmName = vmName,
                onBack = { navController.popBackStack() },
            )
        }

        composable(
            route = Screen.QmpConsole.route,
            arguments = listOf(navArgument("vmName") { type = NavType.StringType }),
        ) { backStackEntry ->
            val vmName = backStackEntry.arguments?.getString("vmName") ?: ""
            QmpConsoleScreen(
                vmName = vmName,
                onBack = { navController.popBackStack() },
            )
        }

        composable(
            route = Screen.ContainerDetail.route,
            arguments = listOf(navArgument("containerId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val containerId = backStackEntry.arguments?.getString("containerId") ?: ""
            ContainerDetailScreen(
                containerId = containerId,
                onBack = { navController.popBackStack() },
            )
        }

        composable(Screen.KubeOverview.route) {
            KubeScreen(
                onBack = { navController.popBackStack() },
                onPodClick = { podName, namespace ->
                    navController.navigate(Screen.KubePodDetail.createRoute(podName, namespace))
                },
            )
        }

        composable(
            route = Screen.KubePodDetail.route,
            arguments = listOf(
                navArgument("podName") { type = NavType.StringType },
                navArgument("namespace") { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val podName = backStackEntry.arguments?.getString("podName") ?: ""
            val namespace = backStackEntry.arguments?.getString("namespace") ?: "default"
            KubePodDetailScreen(
                podName = podName,
                namespace = namespace,
                onBack = { navController.popBackStack() },
            )
        }

        composable(Screen.Federation.route) {
            FederationScreen(
                onBack = { navController.popBackStack() },
                onNodeClick = { nodeId ->
                    // Navigate to node detail or show details
                },
            )
        }

    }
}

private fun Intent.getQueryParameter(name: String): String? {
    val data = data
    if (data == null) return null
    val params = data.getQueryParameterNames()
    for (param in params) {
        if (param.equals(name, ignoreCase = true)) {
            return data.getQueryParameter(param)
        }
    }
    return null
}

private fun Uri.getQueryParameterNames(): List<String> {
    val query = query
    if (query.isNullOrEmpty()) return emptyList()
    return query.split("&").map { it.split("=").firstOrNull() ?: "" }
}

private fun Uri.getQueryParameter(name: String): String? {
    val query = query
    if (query.isNullOrEmpty()) return null
    val params = query.split("&")
    for (param in params) {
        val parts = param.split("=")
        if (parts.firstOrNull()?.equals(name, ignoreCase = true) == true) {
            return parts.getOrNull(1)?.decodeURIComponent()
        }
    }
    return null
}

private fun String.decodeURIComponent(): String {
    return android.net.Uri.decode(this)
}

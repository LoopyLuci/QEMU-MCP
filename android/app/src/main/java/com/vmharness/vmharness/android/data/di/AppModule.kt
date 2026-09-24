package com.vmharness.android.data.di

import android.content.Context
import com.vmharness.android.data.api.*
import com.vmharness.android.data.auth.PairingTokenVerifier
import com.vmharness.android.data.repository.DesktopRepository
import com.vmharness.android.data.store.PairingStore
import com.vmharness.android.domain.usecase.*
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun providePairingStore(@ApplicationContext context: Context): PairingStore {
        return PairingStore(context)
    }

    @Provides
    @Singleton
    fun provideApiKeyProvider(pairingStore: PairingStore): ApiKeyProvider {
        return DefaultApiKeyProvider(pairingStore)
    }

    @Provides
    @Singleton
    fun providePairingTokenVerifier(pairingStore: PairingStore): PairingTokenVerifier {
        return PairingTokenVerifier(pairingStore)
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        apiKeyProvider: ApiKeyProvider,
        pairingStore: PairingStore,
    ): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        return OkHttpClient.Builder()
            .addInterceptor(logging)
            .authenticator(ApiKeyAuthenticator(apiKeyProvider, pairingStore))
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideVMHarnessApiClient(
        okHttp: OkHttpClient,
        apiKeyProvider: ApiKeyProvider,
    ): VMHarnessApiClient {
        return VMHarnessApiClient(okHttp, apiKeyProvider)
    }

    @Provides
    @Singleton
    fun provideDesktopRepository(
        apiClient: VMHarnessApiClient,
        pairingStore: PairingStore,
        verifier: PairingTokenVerifier,
    ): DesktopRepository {
        return DesktopRepository(apiClient, pairingStore, verifier)
    }

    @Provides
    @Singleton
    fun providePairingUseCase(
        desktopRepository: DesktopRepository,
        pairingStore: PairingStore,
        pairingTokenVerifier: PairingTokenVerifier,
    ): PairingUseCase {
        return PairingUseCase(desktopRepository, pairingStore, pairingTokenVerifier)
    }

    @Provides
    @Singleton
    fun provideDashboardUseCase(desktopRepository: DesktopRepository): DashboardUseCase {
        return DashboardUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideVmControlUseCase(desktopRepository: DesktopRepository): VmControlUseCase {
        return VmControlUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideTelemetryUseCase(desktopRepository: DesktopRepository): TelemetryUseCase {
        return TelemetryUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideSecurityUseCase(desktopRepository: DesktopRepository): SecurityUseCase {
        return SecurityUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideLogsUseCase(desktopRepository: DesktopRepository): LogsUseCase {
        return LogsUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideSettingsUseCase(desktopRepository: DesktopRepository): SettingsUseCase {
        return SettingsUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideContainerDetailUseCase(desktopRepository: DesktopRepository): ContainerDetailUseCase {
        return ContainerDetailUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideKubeUseCase(desktopRepository: DesktopRepository): KubeUseCase {
        return KubeUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideKubePodDetailUseCase(desktopRepository: DesktopRepository): KubePodDetailUseCase {
        return KubePodDetailUseCase(desktopRepository)
    }

    @Provides
    @Singleton
    fun provideFederationUseCase(desktopRepository: DesktopRepository): FederationUseCase {
        return FederationUseCase(desktopRepository)
    }

}

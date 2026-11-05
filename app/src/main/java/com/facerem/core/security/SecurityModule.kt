package com.facerem.core.security

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class SecurityModule {

    @Binds
    @Singleton
    abstract fun bindDeviceCredentialStore(
        impl: KeystoreDeviceCredentialStore,
    ): DeviceCredentialStore
}


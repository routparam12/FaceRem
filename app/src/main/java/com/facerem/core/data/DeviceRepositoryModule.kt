package com.facerem.core.data

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class DeviceRepositoryModule {

    @Binds
    @Singleton
    abstract fun bindDeviceEnrollmentRepository(
        impl: DeviceEnrollmentRepositoryImpl,
    ): DeviceEnrollmentRepository
}


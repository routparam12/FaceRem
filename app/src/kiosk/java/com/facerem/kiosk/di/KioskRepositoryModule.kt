package com.facerem.kiosk.di

import com.facerem.feature.attendance.data.RemoteAttendanceRepository
import com.facerem.feature.attendance.domain.AttendanceRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class KioskRepositoryModule {

    @Binds
    @Singleton
    abstract fun bindAttendanceRepository(
        impl: RemoteAttendanceRepository,
    ): AttendanceRepository
}


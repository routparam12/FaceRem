package com.facerem.core.data

import com.facerem.core.session.SessionManager
import com.facerem.feature.attendance.data.DemoAttendanceRepository
import com.facerem.feature.attendance.data.RemoteAttendanceRepository
import com.facerem.feature.attendance.domain.AttendanceRepository
import com.facerem.feature.auth.data.AuthRepositoryImpl
import com.facerem.feature.auth.domain.AuthRepository
import com.facerem.feature.dashboard.data.DemoDashboardRepository
import com.facerem.feature.dashboard.data.RemoteDashboardRepository
import com.facerem.feature.dashboard.domain.DashboardRepository
import com.facerem.feature.employees.data.DemoEmployeeRepository
import com.facerem.feature.employees.data.RemoteEmployeeRepository
import com.facerem.feature.employees.domain.EmployeeRepository
import com.facerem.feature.reports.data.DemoReportRepository
import com.facerem.feature.reports.domain.ReportRepository
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Repository wiring.
 *
 * Each data repository is a dispatcher: a guest session reads the local sample data, a real
 * session talks to the backend. The choice is made per call because a guest can leave guest
 * mode and sign in without the app restarting.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindAuthRepository(impl: AuthRepositoryImpl): AuthRepository

    @Binds
    @Singleton
    abstract fun bindReportRepository(impl: DemoReportRepository): ReportRepository

    companion object {
        @Provides
        @Singleton
        fun provideDashboardRepository(
            remote: RemoteDashboardRepository,
            demo: DemoDashboardRepository,
            session: SessionManager,
        ): DashboardRepository = DispatchingDashboardRepository(remote, demo, session)

        @Provides
        @Singleton
        fun provideEmployeeRepository(
            remote: RemoteEmployeeRepository,
            demo: DemoEmployeeRepository,
            session: SessionManager,
        ): EmployeeRepository = DispatchingEmployeeRepository(remote, demo, session)

        @Provides
        @Singleton
        fun provideAttendanceRepository(
            remote: RemoteAttendanceRepository,
            demo: DemoAttendanceRepository,
            session: SessionManager,
        ): AttendanceRepository = DispatchingAttendanceRepository(remote, demo, session)
    }
}

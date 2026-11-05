package com.facerem.feature.settings.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.data.demo.DemoDataStore
import com.facerem.core.model.User
import com.facerem.core.session.SessionManager
import com.facerem.core.session.SessionState
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ProfileUiState(
    val user: User? = null,
    val isGuest: Boolean = false,
    val organizationName: String = "",
    val planLabel: String = "",
    val branchCount: Int = 0,
    val timeZone: String = "",
)

@HiltViewModel
class ProfileViewModel @Inject constructor(
    demoDataStore: DemoDataStore,
    sessionManager: SessionManager,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(ProfileUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        val organization = demoDataStore.organization
        viewModelScope.launch {
            sessionManager.state.collect { session ->
                val authenticated = session as? SessionState.Authenticated
                mutableUiState.update {
                    it.copy(
                        user = authenticated?.user,
                        isGuest = authenticated?.isGuest == true,
                        organizationName = authenticated?.user?.organizationName.orEmpty()
                            .ifBlank { organization.name },
                        planLabel = "${organization.plan.displayName} plan",
                        branchCount = organization.branchCount,
                        timeZone = organization.timeZone,
                    )
                }
            }
        }
    }
}

package com.facerem.core.common

sealed interface AppResult<out T> {
    data class Success<T>(val data: T) : AppResult<T>
    data class Error(val error: AppError) : AppResult<Nothing>
    data object Loading : AppResult<Nothing>
}

sealed interface AppError {
    val userMessage: String

    data class Api(
        val code: String,
        override val userMessage: String,
        val httpStatus: Int? = null,
    ) : AppError

    data object NoInternet : AppError {
        override val userMessage = "Check your internet connection and try again."
    }

    data class ServerUnreachable(
        override val userMessage: String = "Unable to connect to backend server. Please check your server IP address and port configuration.",
    ) : AppError

    data object Timeout : AppError {
        override val userMessage = "The request timed out. Please try again."
    }

    data object Unknown : AppError {
        override val userMessage = "Something went wrong. Please try again."
    }
}

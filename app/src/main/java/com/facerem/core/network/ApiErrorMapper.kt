package com.facerem.core.network

import android.os.Build
import com.facerem.core.common.AppError
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import retrofit2.HttpException

class ApiErrorMapper {
    fun map(throwable: Throwable): AppError = when (throwable) {
        is HttpException -> mapHttpStatus(throwable.code())
        is SocketTimeoutException -> AppError.Timeout
        is ConnectException -> {
            val msg = throwable.message.orEmpty()
            if (msg.contains("10.0.2.2") || isPhysicalDevice()) {
                AppError.ServerUnreachable(
                    "Cannot reach backend server. If running on a physical device, ensure the backend server is running on your PC and specify your PC's IP address (e.g. ./gradlew assembleAdminDebug -Pfaceattend.apiHost=<YOUR_PC_IP>).",
                )
            } else {
                AppError.ServerUnreachable("Connection refused by backend server. Please check that the server is running.")
            }
        }
        is UnknownHostException -> AppError.NoInternet
        is IOException -> {
            val msg = throwable.message.orEmpty()
            if (msg.contains("10.0.2.2") && isPhysicalDevice()) {
                AppError.ServerUnreachable(
                    "Cannot reach 10.0.2.2 from a physical device. Build with -Pfaceattend.apiHost=<YOUR_PC_IP>.",
                )
            } else {
                AppError.NoInternet
            }
        }
        else -> AppError.Unknown
    }

    private fun isPhysicalDevice(): Boolean {
        return runCatching {
            val fingerprint = Build.FINGERPRINT.orEmpty()
            val model = Build.MODEL.orEmpty()
            val hardware = Build.HARDWARE.orEmpty()
            val brand = Build.BRAND.orEmpty()
            !(fingerprint.startsWith("generic") ||
                fingerprint.startsWith("unknown") ||
                model.contains("google_sdk") ||
                model.contains("Emulator") ||
                model.contains("Android SDK built for x86") ||
                hardware.contains("goldfish") ||
                hardware.contains("ranchu") ||
                brand.startsWith("generic"))
        }.getOrDefault(true)
    }

    fun mapHttpStatus(statusCode: Int): AppError = when (statusCode) {
        400 -> AppError.Api("BAD_REQUEST", "The request could not be processed.", statusCode)
        401 -> AppError.Api("UNAUTHORIZED", "Your session has expired. Please sign in again.", statusCode)
        403 -> AppError.Api("FORBIDDEN", "You do not have permission to perform this action.", statusCode)
        404 -> AppError.Api("NOT_FOUND", "The requested item was not found.", statusCode)
        409 -> AppError.Api("CONFLICT", "This action conflicts with existing data.", statusCode)
        422 -> AppError.Api("VALIDATION_ERROR", "Please check the information and try again.", statusCode)
        429 -> AppError.Api("RATE_LIMITED", "Too many requests. Please try again shortly.", statusCode)
        in 500..599 -> AppError.Api("SERVER_ERROR", "Our server is unavailable. Please try again later.", statusCode)
        else -> AppError.Api("HTTP_ERROR", "The request could not be completed.", statusCode)
    }
}

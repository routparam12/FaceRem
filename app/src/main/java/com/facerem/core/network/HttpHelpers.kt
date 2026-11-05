package com.facerem.core.network

import com.facerem.core.common.AppResult
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

val TEXT = "text/plain".toMediaType()

fun ByteArray.asImagePart(name: String = "image"): MultipartBody.Part =
    MultipartBody.Part.createFormData(
        name,
        "$name.jpg",
        toRequestBody("image/jpeg".toMediaType()),
    )

inline fun <T, R> AppResult<T>.map(transform: (T) -> R): AppResult<R> = when (this) {
    is AppResult.Success -> AppResult.Success(transform(data))
    is AppResult.Error -> AppResult.Error(error)
    AppResult.Loading -> AppResult.Loading
}


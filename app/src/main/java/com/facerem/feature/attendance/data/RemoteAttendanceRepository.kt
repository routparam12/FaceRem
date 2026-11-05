package com.facerem.feature.attendance.data

import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.LivenessChallenge
import com.facerem.core.model.RecognitionOutcome
import com.facerem.core.network.ApiCall
import com.facerem.core.network.TEXT
import com.facerem.core.network.api.FaceAttendApi
import com.facerem.core.network.asImagePart
import com.facerem.core.network.map
import com.facerem.core.network.mapper.toOutcome
import com.facerem.core.network.mapper.toRecord
import com.facerem.feature.attendance.domain.AttendanceRepository
import javax.inject.Inject
import javax.inject.Singleton
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

@Singleton
class RemoteAttendanceRepository @Inject constructor(
    private val api: FaceAttendApi,
    private val apiCall: ApiCall,
) : AttendanceRepository {

    override suspend fun requestChallenge(): AppResult<LivenessChallenge> =
        apiCall.invoke { api.challenge() }.map {
            LivenessChallenge(
                challengeId = it.challengeId,
                nonce = it.nonce,
                actions = it.actions,
            )
        }

    override suspend fun recognize(
        image: ByteArray,
        challengeId: String?,
        nonce: String?,
        burstFrames: List<ByteArray>,
        deviceLabel: String,
    ): AppResult<RecognitionOutcome> {
        val burstParts = burstFrames.mapIndexed { idx, bytes ->
            MultipartBody.Part.createFormData(
                "burst",
                "burst_$idx.jpg",
                bytes.toRequestBody("image/jpeg".toMediaType()),
            )
        }
        val result = apiCall.invoke {
            api.recognize(
                image = image.asImagePart(),
                challengeId = challengeId?.toRequestBody(TEXT),
                nonce = nonce?.toRequestBody(TEXT),
                burst = burstParts,
                deviceLabel = deviceLabel.toRequestBody(TEXT),
            )
        }
        return when (result) {
            is AppResult.Success -> AppResult.Success(result.data.toOutcome())
            // An unknown face is a normal outcome at a gate, not a failure to report as one.
            is AppResult.Error -> when ((result.error as? AppError.Api)?.code) {
                "FACE_NOT_RECOGNIZED" ->
                    AppResult.Success(RecognitionOutcome.NotRecognized(result.error.userMessage))

                "LIVENESS_FAILED", "MULTIPLE_FACES", "FACE_NOT_FOUND", "FACE_QUALITY_LOW" ->
                    AppResult.Success(
                        RecognitionOutcome.Rejected(
                            code = result.error.code,
                            message = result.error.userMessage,
                        ),
                    )

                else -> result
            }

            AppResult.Loading -> AppResult.Loading
        }
    }

    override suspend fun history(): AppResult<List<AttendanceRecord>> =
        apiCall.invoke { api.attendance() }.map { rows -> rows.map { it.toRecord() } }
}

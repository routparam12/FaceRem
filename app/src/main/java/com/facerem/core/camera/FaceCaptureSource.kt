package com.facerem.core.camera

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Normalized quality metrics produced on-device (e.g. by ML Kit) for UX guidance only.
 * Server remains the sole authority for recognition, liveness, and attendance decisions.
 */
data class FaceCaptureQuality(
    val brightness: Float = 1.0f,
    val isCentered: Boolean = true,
    val isBlurry: Boolean = false,
    val yawDegrees: Float = 0f,
    val rollDegrees: Float = 0f,
    val faceAreaRatio: Float = 0.25f,
    val hasSingleFace: Boolean = true,
)

/**
 * Camera-independent capture observation emitted by [FaceCaptureSource].
 * Decoupled from CameraX, ML Kit, RTSP, and hardware camera details.
 */
data class FaceCaptureObservation(
    val observationId: String,
    val timestampMs: Long,
    val primaryImageJpeg: ByteArray,
    val quality: FaceCaptureQuality,
    val trackId: Int? = null,
    val burstFramesJpeg: List<ByteArray> = emptyList(),
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is FaceCaptureObservation) return false
        return observationId == other.observationId &&
            timestampMs == other.timestampMs &&
            primaryImageJpeg.contentEquals(other.primaryImageJpeg) &&
            quality == other.quality &&
            trackId == other.trackId
    }

    override fun hashCode(): Int {
        var result = observationId.hashCode()
        result = 31 * result + timestampMs.hashCode()
        result = 31 * result + primaryImageJpeg.contentHashCode()
        result = 31 * result + quality.hashCode()
        result = 31 * result + (trackId ?: 0)
        return result
    }
}

/**
 * Camera-independent abstraction producing face capture observations.
 * Implementation can be CameraX + ML Kit, an edge RTSP ingest, or a test fake.
 */
interface FaceCaptureSource {
    val observations: Flow<FaceCaptureObservation>

    suspend fun startCapture()
    suspend fun stopCapture()
}

/**
 * Test fake implementation of [FaceCaptureSource] used in unit tests.
 */
class FakeFaceCaptureSource : FaceCaptureSource {
    private val _observations = MutableSharedFlow<FaceCaptureObservation>(extraBufferCapacity = 16)
    override val observations: Flow<FaceCaptureObservation> = _observations.asSharedFlow()

    var isCapturing: Boolean = false
        private set

    override suspend fun startCapture() {
        isCapturing = true
    }

    override suspend fun stopCapture() {
        isCapturing = false
    }

    fun emitObservation(observation: FaceCaptureObservation) {
        _observations.tryEmit(observation)
    }
}


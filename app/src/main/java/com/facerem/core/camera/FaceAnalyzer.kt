package com.facerem.core.camera

import androidx.annotation.OptIn
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetector

/**
 * Runs ML Kit face detection on the latest camera frame and reports a quality verdict.
 *
 * Detection and quality scoring only: identity is never decided on the device. Frames are not
 * retained, and nothing leaves this class except the verdict.
 */
class FaceAnalyzer(
    private val detector: FaceDetector,
    private val poseProvider: () -> FaceQualityEvaluator.HeadPose,
    private val onQuality: (FaceQualityStatus) -> Unit,
    private val onFacesDetected: ((faces: List<Face>, imageWidth: Int, imageHeight: Int) -> Unit)? = null,
) : ImageAnalysis.Analyzer {

    @OptIn(ExperimentalGetImage::class)
    override fun analyze(imageProxy: ImageProxy) {
        val mediaImage = imageProxy.image
        if (mediaImage == null) {
            imageProxy.close()
            return
        }

        val rotation = imageProxy.imageInfo.rotationDegrees
        val inputImage = InputImage.fromMediaImage(mediaImage, rotation)
        val luminance = imageProxy.averageLuminance()
        val uprightWidth = if (rotation == 90 || rotation == 270) imageProxy.height else imageProxy.width
        val uprightHeight = if (rotation == 90 || rotation == 270) imageProxy.width else imageProxy.height

        detector.process(inputImage)
            .addOnSuccessListener { faces ->
                onFacesDetected?.invoke(faces, uprightWidth, uprightHeight)
                onQuality(
                    FaceQualityEvaluator.evaluate(
                        faces = faces,
                        imageWidth = uprightWidth,
                        imageHeight = uprightHeight,
                        averageLuminance = luminance,
                        requirePose = poseProvider(),
                    ),
                )
            }
            .addOnFailureListener {
                onFacesDetected?.invoke(emptyList(), uprightWidth, uprightHeight)
                onQuality(FaceQualityStatus.NO_FACE)
            }
            .addOnCompleteListener { imageProxy.close() }
    }
}

/** Mean luma sampled from the Y plane; enough to detect an unusably dark frame. */
private fun ImageProxy.averageLuminance(): Int {
    val plane = planes.firstOrNull() ?: return -1
    val buffer = plane.buffer
    buffer.rewind()
    val step = (buffer.remaining() / 2_048).coerceAtLeast(1)
    var total = 0L
    var samples = 0
    var index = 0
    while (index < buffer.remaining()) {
        total += buffer.get(index).toInt() and 0xFF
        samples++
        index += step
    }
    buffer.rewind()
    return if (samples == 0) -1 else (total / samples).toInt()
}

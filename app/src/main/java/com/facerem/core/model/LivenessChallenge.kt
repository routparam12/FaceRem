package com.facerem.core.model

data class LivenessChallenge(
    val challengeId: String,
    val nonce: String,
    val actions: List<String> = emptyList(),
)


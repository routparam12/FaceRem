package com.facerem.feature.attendance.presentation

import android.graphics.Rect as AndroidRect
import com.facerem.core.camera.FaceQualityStatus
import com.facerem.core.model.AttendanceEventType
import com.facerem.core.model.AttendanceStatus
import com.facerem.core.model.RecognitionOutcome
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TrackOverlayMappingTest {

    // -------------------------------------------------------------------------
    // 1. ANALYZING (white)
    // -------------------------------------------------------------------------

    @Test
    fun analyzing_primary_face_produces_white_with_analyzing_text() {
        val overlay = mapToTrackOverlayState(
            serverOutcome = null,
            isPrimary = true,
            challengePrompt = null,
            clientQuality = FaceQualityStatus.VALID,
        )

        assertEquals(TrackOverlayStatus.ANALYZING, overlay.status)
        assertEquals(OverlayColor.WHITE, overlay.color)
        assertEquals(OverlayIconType.SEARCH, overlay.iconType)
        assertEquals("Analyzing…", overlay.primaryText)
        assertNull(overlay.secondaryText)
        assertFalse(overlay.showPinFallbackButton)
    }

    @Test
    fun analyzing_non_primary_face_produces_white_with_one_person_at_a_time() {
        val overlay = mapToTrackOverlayState(
            serverOutcome = null,
            isPrimary = false,
            challengePrompt = null,
            clientQuality = FaceQualityStatus.VALID,
        )

        assertEquals(TrackOverlayStatus.ANALYZING, overlay.status)
        assertEquals(OverlayColor.WHITE, overlay.color)
        assertEquals(OverlayIconType.SEARCH, overlay.iconType)
        assertEquals("One person at a time", overlay.primaryText)
        assertNull(overlay.secondaryText)
        assertFalse(overlay.showPinFallbackButton)
    }

    // -------------------------------------------------------------------------
    // 2. CHALLENGE (blue)
    // -------------------------------------------------------------------------

    @Test
    fun challenge_action_produces_blue_with_action_text() {
        val overlay = mapToTrackOverlayState(
            serverOutcome = null,
            isPrimary = true,
            challengePrompt = "Please blink",
        )

        assertEquals(TrackOverlayStatus.CHALLENGE, overlay.status)
        assertEquals(OverlayColor.BLUE, overlay.color)
        assertEquals(OverlayIconType.EYE, overlay.iconType)
        assertEquals("Please blink", overlay.primaryText)
        assertNull(overlay.secondaryText)
        assertFalse(overlay.showPinFallbackButton)
    }

    // -------------------------------------------------------------------------
    // 3. RECOGNIZED (green)
    // -------------------------------------------------------------------------

    @Test
    fun recognized_produces_green_with_check_icon_name_and_event_details() {
        val outcome = RecognitionOutcome.Recognized(
            employeeId = "emp-1",
            employeeName = "Sarah Connor",
            employeeCode = "EMP001",
            department = "Engineering",
            eventType = AttendanceEventType.CHECK_IN,
            timeLabel = "9:05 AM",
            confidence = 0.95f,
            status = AttendanceStatus.PRESENT,
            lateMinutes = 0,
        )

        val overlay = mapToTrackOverlayState(
            serverOutcome = outcome,
            isPrimary = true,
            nameStyle = NameDisplayStyle.FULL_NAME,
        )

        assertEquals(TrackOverlayStatus.RECOGNIZED, overlay.status)
        assertEquals(OverlayColor.GREEN, overlay.color)
        assertEquals(OverlayIconType.CHECK, overlay.iconType)
        assertEquals("Sarah Connor", overlay.primaryText)
        assertEquals("Checked in 9:05 AM", overlay.secondaryText)
        assertEquals("VERIFIED", overlay.badgeText)
        assertFalse(overlay.showPinFallbackButton)
    }

    @Test
    fun recognized_with_late_minutes_includes_late_detail() {
        val outcome = RecognitionOutcome.Recognized(
            employeeId = "emp-2",
            employeeName = "John Smith",
            employeeCode = "EMP002",
            department = "Operations",
            eventType = AttendanceEventType.CHECK_IN,
            timeLabel = "9:25 AM",
            confidence = 0.92f,
            status = AttendanceStatus.LATE,
            lateMinutes = 25,
        )

        val overlay = mapToTrackOverlayState(
            serverOutcome = outcome,
            isPrimary = true,
            nameStyle = NameDisplayStyle.FIRST_NAME_LAST_INITIAL,
        )

        assertEquals(TrackOverlayStatus.RECOGNIZED, overlay.status)
        assertEquals(OverlayColor.GREEN, overlay.color)
        assertEquals(OverlayIconType.CHECK, overlay.iconType)
        assertEquals("John S.", overlay.primaryText)
        assertTrue(overlay.secondaryText?.contains("25m late") == true)
        assertEquals("VERIFIED", overlay.badgeText)
    }

    // -------------------------------------------------------------------------
    // 4. ALREADY_PRESENT (green)
    // -------------------------------------------------------------------------

    @Test
    fun already_present_produces_green_with_already_checked_in_label() {
        val outcome = RecognitionOutcome.Recognized(
            employeeId = "emp-3",
            employeeName = "Marcus Wright",
            employeeCode = "EMP003",
            department = "Security",
            eventType = AttendanceEventType.ALREADY_PRESENT,
            timeLabel = "9:00 AM",
            confidence = 0.98f,
            status = AttendanceStatus.PRESENT,
            lateMinutes = 0,
            checkInLabel = "9:00 AM",
        )

        val overlay = mapToTrackOverlayState(
            serverOutcome = outcome,
            isPrimary = true,
            nameStyle = NameDisplayStyle.FULL_NAME,
        )

        assertEquals(TrackOverlayStatus.ALREADY_PRESENT, overlay.status)
        assertEquals(OverlayColor.GREEN, overlay.color)
        assertEquals(OverlayIconType.CHECK, overlay.iconType)
        assertEquals("Already checked in 9:00 AM", overlay.primaryText)
        assertEquals("Marcus Wright", overlay.secondaryText)
        assertEquals("VERIFIED", overlay.badgeText)
        assertFalse(overlay.showPinFallbackButton)
    }

    // -------------------------------------------------------------------------
    // 5. NOT_RECOGNIZED (red)
    // -------------------------------------------------------------------------

    @Test
    fun not_recognized_produces_red_cross_and_visible_pin_button() {
        val outcome = RecognitionOutcome.NotRecognized("Face not recognized.")

        val overlay = mapToTrackOverlayState(
            serverOutcome = outcome,
            isPrimary = true,
        )

        assertEquals(TrackOverlayStatus.NOT_RECOGNIZED, overlay.status)
        assertEquals(OverlayColor.RED, overlay.color)
        assertEquals(OverlayIconType.CROSS, overlay.iconType)
        assertEquals("Not recognized", overlay.primaryText)
        assertTrue(overlay.showPinFallbackButton)
        assertNull(overlay.badgeText)
    }

    // -------------------------------------------------------------------------
    // 6. LIVENESS_FAILED & QUALITY (amber)
    // -------------------------------------------------------------------------

    @Test
    fun server_liveness_failed_produces_amber_with_try_again_hint() {
        val outcome = RecognitionOutcome.Rejected(
            code = "LIVENESS_FAILED",
            message = "Liveness check failed",
        )

        val overlay = mapToTrackOverlayState(
            serverOutcome = outcome,
            isPrimary = true,
        )

        assertEquals(TrackOverlayStatus.LIVENESS_FAILED, overlay.status)
        assertEquals(OverlayColor.AMBER, overlay.color)
        assertEquals(OverlayIconType.WARNING, overlay.iconType)
        assertEquals("Try again", overlay.primaryText)
        assertEquals("Liveness check failed", overlay.secondaryText)
        assertFalse(overlay.showPinFallbackButton)
    }

    @Test
    fun server_quality_rejection_produces_amber_with_try_again_hint() {
        val outcome = RecognitionOutcome.Rejected(
            code = "FACE_QUALITY_LOW",
            message = "Image too blurry",
        )

        val overlay = mapToTrackOverlayState(
            serverOutcome = outcome,
            isPrimary = true,
        )

        assertEquals(TrackOverlayStatus.QUALITY, overlay.status)
        assertEquals(OverlayColor.AMBER, overlay.color)
        assertEquals(OverlayIconType.WARNING, overlay.iconType)
        assertEquals("Try again", overlay.primaryText)
        assertEquals("Image too blurry", overlay.secondaryText)
        assertFalse(overlay.showPinFallbackButton)
    }

    @Test
    fun client_side_quality_issue_produces_amber_coaching_never_red() {
        val qualityIssues = listOf(
            FaceQualityStatus.TOO_FAR,
            FaceQualityStatus.TOO_CLOSE,
            FaceQualityStatus.OFF_CENTER,
            FaceQualityStatus.LOOK_STRAIGHT,
            FaceQualityStatus.TOO_DARK,
            FaceQualityStatus.EYES_CLOSED,
            FaceQualityStatus.MULTIPLE_FACES,
        )

        for (issue in qualityIssues) {
            val overlay = mapToTrackOverlayState(
                serverOutcome = null,
                isPrimary = true,
                clientQuality = issue,
            )

            assertEquals("Quality issue $issue should be QUALITY status", TrackOverlayStatus.QUALITY, overlay.status)
            assertEquals("Quality issue $issue should be AMBER", OverlayColor.AMBER, overlay.color)
            assertEquals(OverlayIconType.WARNING, overlay.iconType)
            assertEquals("Try again", overlay.primaryText)
            assertEquals(issue.guidance, overlay.secondaryText)
            assertNotEquals("Client quality issue must NEVER produce RED", OverlayColor.RED, overlay.color)
            assertFalse(overlay.showPinFallbackButton)
        }
    }

    // -------------------------------------------------------------------------
    // 7. INVARIANT: Red is NEVER produced without server NotRecognized
    // -------------------------------------------------------------------------

    @Test
    fun red_is_strictly_never_produced_without_server_not_recognized() {
        // Test all possible combinations without server NotRecognized
        val outcomes: List<RecognitionOutcome?> = listOf(
            null,
            RecognitionOutcome.Recognized("1", "User", "E1", "Dept", AttendanceEventType.CHECK_IN, "9:00", 0.9f, AttendanceStatus.PRESENT, 0),
            RecognitionOutcome.Recognized("1", "User", "E1", "Dept", AttendanceEventType.CHECK_OUT, "17:00", 0.9f, AttendanceStatus.PRESENT, 0),
            RecognitionOutcome.Recognized("1", "User", "E1", "Dept", AttendanceEventType.ALREADY_PRESENT, "9:00", 0.9f, AttendanceStatus.PRESENT, 0),
            RecognitionOutcome.Rejected("LIVENESS_FAILED", "Blink not detected"),
            RecognitionOutcome.Rejected("FACE_QUALITY_LOW", "Frame too dim"),
            RecognitionOutcome.Rejected("FACE_NOT_FOUND", "No face detected in crop"),
            RecognitionOutcome.Rejected("MULTIPLE_FACES", "Multiple faces present"),
        )

        val booleanOptions = listOf(true, false)
        val prompts = listOf(null, "Please blink", "Turn slightly left")
        val qualities = FaceQualityStatus.entries

        for (outcome in outcomes) {
            for (isPrimary in booleanOptions) {
                for (prompt in prompts) {
                    for (quality in qualities) {
                        val state = mapToTrackOverlayState(
                            serverOutcome = outcome,
                            isPrimary = isPrimary,
                            challengePrompt = prompt,
                            clientQuality = quality,
                        )

                        assertNotEquals(
                            "Invariant violated: state produced RED for non-NotRecognized outcome ($outcome, primary=$isPrimary, quality=$quality)",
                            OverlayColor.RED,
                            state.color,
                        )
                    }
                }
            }
        }

        // And verify that NotRecognized DOES produce RED
        val notRecognizedState = mapToTrackOverlayState(
            serverOutcome = RecognitionOutcome.NotRecognized("Unknown"),
            isPrimary = true,
        )
        assertEquals(OverlayColor.RED, notRecognizedState.color)
    }

    // -------------------------------------------------------------------------
    // 8. Name Display Style Tests
    // -------------------------------------------------------------------------

    @Test
    fun name_display_style_formatting() {
        val fullName = "Sarah Jean Connor"

        assertEquals("Sarah Jean Connor", formatEmployeeName(fullName, NameDisplayStyle.FULL_NAME))
        assertEquals("Sarah C.", formatEmployeeName(fullName, NameDisplayStyle.FIRST_NAME_LAST_INITIAL))
        assertEquals("S. J. C.", formatEmployeeName(fullName, NameDisplayStyle.INITIALS))

        // Single word name handles gracefully
        assertEquals("Admin", formatEmployeeName("Admin", NameDisplayStyle.FULL_NAME))
        assertEquals("Admin", formatEmployeeName("Admin", NameDisplayStyle.FIRST_NAME_LAST_INITIAL))
        assertEquals("A.", formatEmployeeName("Admin", NameDisplayStyle.INITIALS))

        // Blank name
        assertEquals("", formatEmployeeName("", NameDisplayStyle.FULL_NAME))
    }

    // -------------------------------------------------------------------------
    // 9. Coordinate Transform & Mirroring Tests
    // -------------------------------------------------------------------------

    @Test
    fun map_face_bounds_to_view_mirrors_front_camera_and_centers() {
        val imageWidth = 1000
        val imageHeight = 1000
        val viewWidth = 1000f
        val viewHeight = 1000f

        // Face centered horizontally: left = 400, right = 600 (width = 200, center = 500)
        val faceRect = AndroidRect(400, 200, 600, 500)

        val mappedFront = mapFaceBoundsToView(
            faceRect = faceRect,
            imageWidth = imageWidth,
            imageHeight = imageHeight,
            viewWidth = viewWidth,
            viewHeight = viewHeight,
            isFrontCamera = true,
        )

        // Mirrored center should remain exactly 500
        val frontCenterX = (mappedFront.left + mappedFront.right) / 2f
        assertEquals(500f, frontCenterX, 1f)

        // Face on image left: left = 100, right = 300 (center = 200)
        val leftFace = AndroidRect(100, 200, 300, 500)
        val mappedLeft = mapFaceBoundsToView(
            faceRect = leftFace,
            imageWidth = imageWidth,
            imageHeight = imageHeight,
            viewWidth = viewWidth,
            viewHeight = viewHeight,
            isFrontCamera = true,
        )

        // Front-camera horizontal mirroring should flip x=200 to x=800
        val mirroredCenterX = (mappedLeft.left + mappedLeft.right) / 2f
        assertEquals(800f, mirroredCenterX, 1f)
    }
}


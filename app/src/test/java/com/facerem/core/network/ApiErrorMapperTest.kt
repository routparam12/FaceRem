package com.facerem.core.network

import com.facerem.core.common.AppError
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import org.junit.Assert.assertEquals
import org.junit.Test
import java.net.ConnectException

class ApiErrorMapperTest {
    private val mapper = ApiErrorMapper()

    @Test
    fun `maps supported HTTP statuses to stable error codes`() {
        assertEquals("BAD_REQUEST", mapper.mapHttpStatus(400).code)
        assertEquals("UNAUTHORIZED", mapper.mapHttpStatus(401).code)
        assertEquals("FORBIDDEN", mapper.mapHttpStatus(403).code)
        assertEquals("NOT_FOUND", mapper.mapHttpStatus(404).code)
        assertEquals("CONFLICT", mapper.mapHttpStatus(409).code)
        assertEquals("VALIDATION_ERROR", mapper.mapHttpStatus(422).code)
        assertEquals("RATE_LIMITED", mapper.mapHttpStatus(429).code)
        assertEquals("SERVER_ERROR", mapper.mapHttpStatus(503).code)
    }

    @Test
    fun `maps offline and timeout failures`() {
        assertEquals(AppError.NoInternet, mapper.map(UnknownHostException()))
        assertEquals(AppError.Timeout, mapper.map(SocketTimeoutException()))
        val connectErr = mapper.map(ConnectException("Failed to connect to 10.0.2.2:8000"))
        assert(connectErr is AppError.ServerUnreachable)
    }

    private val AppError.code: String
        get() = (this as AppError.Api).code
}

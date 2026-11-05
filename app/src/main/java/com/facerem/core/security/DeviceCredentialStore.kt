package com.facerem.core.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import dagger.hilt.android.qualifiers.ApplicationContext
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class DeviceCredentials(
    val deviceId: String,
    val organizationId: String,
    val name: String,
    val mode: String,
    val accessToken: String,
)

interface DeviceCredentialStore {
    val credentials: StateFlow<DeviceCredentials?>
    val revocationEvents: SharedFlow<String>

    fun getCredentials(): DeviceCredentials?
    suspend fun saveCredentials(credentials: DeviceCredentials)
    suspend fun wipe()
    fun notifyRevoked(reason: String = "This device was removed. Ask an admin for a new code.")
}

/**
 * Keystore-backed AES-GCM secure storage for kiosk device credentials.
 *
 * Avoids androidx.security EncryptedSharedPreferences (which has deprecation warnings,
 * key-corruption bugs across Android vendor ROMs, and heavy overhead).
 *
 * Uses native AndroidKeyStore with hardware-backed AES-256 GCM authenticated encryption.
 * The encryption key never leaves the hardware TEE / StrongBox, and wipe() irreversibly
 * deletes both the ciphertext and the key from KeyStore.
 */
@Singleton
class KeystoreDeviceCredentialStore @Inject constructor(
    @param:ApplicationContext private val context: Context,
) : DeviceCredentialStore {

    private val json = Json { ignoreUnknownKeys = true }
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val _credentials = MutableStateFlow<DeviceCredentials?>(null)
    override val credentials: StateFlow<DeviceCredentials?> = _credentials.asStateFlow()

    private val _revocationEvents = MutableSharedFlow<String>(extraBufferCapacity = 1)
    override val revocationEvents: SharedFlow<String> = _revocationEvents.asSharedFlow()

    init {
        _credentials.value = loadFromKeystore()
    }

    override fun getCredentials(): DeviceCredentials? = _credentials.value

    override suspend fun saveCredentials(credentials: DeviceCredentials) {
        val serialized = json.encodeToString(DeviceCredentials.serializer(), credentials)
        val encryptedBase64 = encrypt(serialized.toByteArray(Charsets.UTF_8))
        prefs.edit().putString(KEY_CIPHERTEXT, encryptedBase64).apply()
        _credentials.value = credentials
    }

    override suspend fun wipe() {
        prefs.edit().clear().apply()
        try {
            val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
            if (keyStore.containsAlias(KEY_ALIAS)) {
                keyStore.deleteEntry(KEY_ALIAS)
            }
        } catch (_: Exception) {
            // Best effort keystore cleanup
        }
        _credentials.value = null
    }

    override fun notifyRevoked(reason: String) {
        _credentials.value = null
        prefs.edit().clear().apply()
        _revocationEvents.tryEmit(reason)
    }

    private fun loadFromKeystore(): DeviceCredentials? {
        val encryptedBase64 = prefs.getString(KEY_CIPHERTEXT, null) ?: return null
        return try {
            val decryptedBytes = decrypt(encryptedBase64)
            val jsonString = String(decryptedBytes, Charsets.UTF_8)
            json.decodeFromString(DeviceCredentials.serializer(), jsonString)
        } catch (_: Exception) {
            // If decryption fails due to key tampering or corrupted storage, wipe stale data
            prefs.edit().clear().apply()
            null
        }
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        val existing = keyStore.getKey(KEY_ALIAS, null) as? SecretKey
        if (existing != null) return existing

        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        val keyGenSpec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        keyGenerator.init(keyGenSpec)
        return keyGenerator.generateKey()
    }

    private fun encrypt(plaintext: ByteArray): String {
        val key = getOrCreateKey()
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val iv = cipher.iv // 12-byte GCM IV
        val ciphertext = cipher.doFinal(plaintext)
        val combined = ByteArray(iv.size + ciphertext.size)
        System.arraycopy(iv, 0, combined, 0, iv.size)
        System.arraycopy(ciphertext, 0, combined, iv.size, ciphertext.size)
        return Base64.encodeToString(combined, Base64.NO_WRAP)
    }

    private fun decrypt(encryptedBase64: String): ByteArray {
        val combined = Base64.decode(encryptedBase64, Base64.NO_WRAP)
        require(combined.size > GCM_IV_LENGTH) { "Invalid payload size" }
        val iv = combined.copyOfRange(0, GCM_IV_LENGTH)
        val ciphertext = combined.copyOfRange(GCM_IV_LENGTH, combined.size)

        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        val key = keyStore.getKey(KEY_ALIAS, null) as SecretKey
        val cipher = Cipher.getInstance(TRANSFORMATION)
        val spec = GCMParameterSpec(GCM_TAG_LENGTH, iv)
        cipher.init(Cipher.DECRYPT_MODE, key, spec)
        return cipher.doFinal(ciphertext)
    }

    companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val KEY_ALIAS = "FaceAttendKioskDeviceMasterKey"
        private const val PREFS_NAME = "facerem_kiosk_device_credentials"
        private const val KEY_CIPHERTEXT = "device_credentials_encrypted"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val GCM_IV_LENGTH = 12
        private const val GCM_TAG_LENGTH = 128
    }
}

/**
 * Fake implementation for unit testing.
 */
class FakeDeviceCredentialStore(
    initial: DeviceCredentials? = null,
) : DeviceCredentialStore {
    private val _credentials = MutableStateFlow(initial)
    override val credentials: StateFlow<DeviceCredentials?> = _credentials.asStateFlow()

    private val _revocationEvents = MutableSharedFlow<String>(extraBufferCapacity = 1)
    override val revocationEvents: SharedFlow<String> = _revocationEvents.asSharedFlow()

    override fun getCredentials(): DeviceCredentials? = _credentials.value

    override suspend fun saveCredentials(credentials: DeviceCredentials) {
        _credentials.value = credentials
    }

    override suspend fun wipe() {
        _credentials.value = null
    }

    override fun notifyRevoked(reason: String) {
        _credentials.value = null
        _revocationEvents.tryEmit(reason)
    }
}


import "server-only";

/**
 * Where the Android APK lives, and what to say about it.
 *
 * The URL is configuration rather than a committed file: a 60 MB binary does not belong in
 * a git repo, and the build that people install should be the one your release process
 * produced, not whatever happened to be checked in.
 *
 * Two ways to set it:
 *   ANDROID_APK_URL=https://releases.example.com/faceattend-1.0.apk   (a CDN or release page)
 *   ANDROID_APK_URL=/downloads/faceattend.apk                         (dropped in public/)
 */
export interface AndroidBuild {
  url: string | null;
  version: string | null;
  sizeLabel: string | null;
  minAndroid: string;
}

export function androidBuild(): AndroidBuild {
  const url = process.env.ANDROID_APK_URL?.trim();
  return {
    url: url && url.length > 0 ? url : null,
    version: process.env.ANDROID_APK_VERSION?.trim() || null,
    sizeLabel: process.env.ANDROID_APK_SIZE?.trim() || null,
    // Matches minSdk 23 in app/build.gradle.kts.
    minAndroid: "6.0",
  };
}


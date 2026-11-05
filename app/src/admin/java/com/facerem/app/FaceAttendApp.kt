package com.facerem.app

import androidx.compose.runtime.Composable
import androidx.navigation.compose.rememberNavController
import com.facerem.app.navigation.AppNavHost

@Composable
fun FaceAttendApp() {
    AppNavHost(navController = rememberNavController())
}

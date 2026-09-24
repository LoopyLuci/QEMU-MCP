package com.vmharness.android

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class VMHarnessAndroidApp : Application() {
    override fun onCreate() {
        super.onCreate()
    }
}

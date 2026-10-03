package com.teja.gemmmobile.assistant

import android.accessibilityservice.AccessibilityService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.TextUtils
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

private const val TAG = "GemmaA11y"

class GemmaAccessibilityService : AccessibilityService() {

    companion object {
        private var instance: GemmaAccessibilityService? = null

        private val _lastSentStatus = MutableStateFlow<String?>(null)
        val lastSentStatus: StateFlow<String?> = _lastSentStatus.asStateFlow()

        @Volatile
        var isAutoSendPending: Boolean = false
            private set

        @Volatile
        private var pendingTargetPhone: String = ""

        @Volatile
        private var pendingTimestamp: Long = 0L

        /**
         * Queues an auto-send trigger for WhatsApp.
         */
        fun armAutoSend(phone: String) {
            isAutoSendPending = true
            pendingTargetPhone = phone
            pendingTimestamp = System.currentTimeMillis()
            _lastSentStatus.value = "Sending in WhatsApp..."
        }

        fun disarmAutoSend() {
            isAutoSendPending = false
            pendingTargetPhone = ""
        }

        /**
         * Checks whether Gemma's AccessibilityService is actively enabled by the user in Android Settings.
         */
        fun isAccessibilityEnabled(context: Context): Boolean {
            val expectedComponentName = ComponentName(context, GemmaAccessibilityService::class.java)
            val enabledServices = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false

            val colonSplitter = TextUtils.SimpleStringSplitter(':')
            colonSplitter.setString(enabledServices)

            while (colonSplitter.hasNext()) {
                val componentNameString = colonSplitter.next()
                val enabledComponent = ComponentName.unflattenFromString(componentNameString)
                if (enabledComponent != null && enabledComponent == expectedComponentName) {
                    return true
                }
            }
            return false
        }

        /**
         * Intent to open the Accessibility Settings page directly so user can toggle Gemma with 1 tap.
         */
        fun getAccessibilitySettingsIntent(): Intent {
            return Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "[$TAG] GemmaAccessibilityService connected successfully")
    }

    override fun onDestroy() {
        super.onDestroy()
        if (instance == this) instance = null
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        val pkg = event.packageName?.toString() ?: return

        // Only monitor WhatsApp packages
        if (pkg != "com.whatsapp" && pkg != "com.whatsapp.w4b") return

        if (!isAutoSendPending) return

        // Timeout check: auto-send window is valid for 10 seconds max
        if (System.currentTimeMillis() - pendingTimestamp > 10_000L) {
            isAutoSendPending = false
            return
        }

        val rootNode = rootInActiveWindow ?: return
        try {
            val sendNode = findSendButton(rootNode)
            if (sendNode != null && sendNode.isEnabled) {
                Log.d(TAG, "[$TAG] Found WhatsApp Send button! Clicking to send directly...")
                val clicked = sendNode.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                if (clicked) {
                    isAutoSendPending = false
                    _lastSentStatus.value = "Sent successfully!"
                    Log.d(TAG, "[$TAG] Send button clicked successfully. Dismissing WhatsApp instantly...")

                    // Immediately dismiss WhatsApp so it doesn't linger on screen
                    Handler(Looper.getMainLooper()).postDelayed({
                        try {
                            performGlobalAction(GLOBAL_ACTION_BACK)
                        } catch (_: Exception) {}
                    }, 50L)

                    Handler(Looper.getMainLooper()).postDelayed({
                        try {
                            performGlobalAction(GLOBAL_ACTION_BACK)
                        } catch (_: Exception) {}
                    }, 160L)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error clicking send button", e)
        }
    }

    /**
     * Recursively traverses accessibility hierarchy to find the WhatsApp Send button.
     */
    private fun findSendButton(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        // 1. By exact WhatsApp View ID
        val byId = node.findAccessibilityNodeInfosByViewId("com.whatsapp:id/send")
        if (!byId.isNullOrEmpty()) {
            return byId.firstOrNull { it.isClickable && it.isEnabled } ?: byId.first()
        }

        // 2. Check current node content description
        val desc = node.contentDescription?.toString()?.lowercase() ?: ""
        if (node.isClickable && (desc == "send" || desc == "పంపు" || desc == "भेजें" || desc.contains("send"))) {
            return node
        }

        // 3. Search children
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val found = findSendButton(child)
            if (found != null) return found
        }
        return null
    }

    override fun onInterrupt() {
        Log.w(TAG, "[$TAG] Accessibility service interrupted")
    }
}

package com.teja.gemmmobile.ui

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.layout.offset
import androidx.compose.ui.text.AnnotatedString
import com.teja.gemmmobile.ocr.DocumentOcrHelper
import com.teja.gemmmobile.ocr.ExtractedDocument
import com.teja.gemmmobile.search.SearchResult
import com.teja.gemmmobile.search.ProfileAvatarLoader
import com.teja.gemmmobile.util.ExportHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import android.Manifest
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import androidx.compose.ui.graphics.Brush
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.RepeatMode

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.togetherWith
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.imeNestedScroll
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.runtime.derivedStateOf
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.DriveFileRenameOutline
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.border
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.BottomSheetDefaults
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.teja.gemmmobile.search.SearchImage
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.style.TextAlign
import com.teja.gemmmobile.storage.ChatSession
import kotlinx.coroutines.launch
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.teja.gemmmobile.ai.BackendType
import com.teja.gemmmobile.ai.EngineState
import com.teja.gemmmobile.ai.GemmaConfig
import com.teja.gemmmobile.model.ModelInstallState

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    modifier: Modifier = Modifier
) {
    val installState by viewModel.installState.collectAsState()
    val engineState by viewModel.engineState.collectAsState()
    val messages by viewModel.messages.collectAsState()
    val inputText by viewModel.inputText.collectAsState()
    val isGenerating by viewModel.isGenerating.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()
    val config by viewModel.config.collectAsState()
    val memories by viewModel.memories.collectAsState()
    val memoryUpdatedEvent by viewModel.memoryUpdatedEvent.collectAsState()
    val isWebSearchEnabled by viewModel.isWebSearchEnabled.collectAsState()

    var showSettingsPage by remember { mutableStateOf(false) }
    var showMemoryDialog by remember { mutableStateOf(false) }
    var showDeleteConfirmDialog by remember { mutableStateOf(false) }
    var showRenameDialog by remember { mutableStateOf(false) }
    var renameText by remember { mutableStateOf("") }
    var showAttachmentDialog by remember { mutableStateOf(false) }
    var showAttachmentMenu by remember { mutableStateOf(false) }
    var isOcrProcessing by remember { mutableStateOf(false) }
    var editingMessageId by remember { mutableStateOf<String?>(null) }
    var activeUserMenuMessage by remember { mutableStateOf<ChatMessage?>(null) }
    var showCameraOverlay by remember { mutableStateOf(false) }
    var showAddFilesSheet by remember { mutableStateOf(false) }

    val haptic = LocalHapticFeedback.current
    val keyboardController = LocalSoftwareKeyboardController.current
    val focusManager = LocalFocusManager.current
    val isImeVisible = WindowInsets.isImeVisible

    val sessions by viewModel.sessions.collectAsState()
    val currentSessionId by viewModel.currentSessionId.collectAsState()
    val activeGeneratingSessionId by viewModel.activeGeneratingSessionId.collectAsState()
    val isSpeaking by viewModel.isSpeaking.collectAsState()
    val currentlySpeakingId by viewModel.currentlySpeakingId.collectAsState()
    val attachedDocument by viewModel.attachedDocument.collectAsState()
    val recentFiles by viewModel.recentFiles.collectAsState()
    val storageUsageText by viewModel.storageUsageText.collectAsState()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)

    val contactsPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            Toast.makeText(context, "Contacts permission enabled", Toast.LENGTH_SHORT).show()
        }
    }

    LaunchedEffect(Unit) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            contactsPermissionLauncher.launch(Manifest.permission.READ_CONTACTS)
        }
    }

    LaunchedEffect(memoryUpdatedEvent) {
        if (memoryUpdatedEvent != null) {
            kotlinx.coroutines.delay(3500L)
            viewModel.clearMemoryUpdatedEvent()
        }
    }

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let { viewModel.importModel(it) }
    }

    // Voice Input Launcher (Native SpeechRecognizer Intent)
    val voiceLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val spoken = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
            if (!spoken.isNullOrBlank()) {
                val current = viewModel.inputText.value
                val combined = if (current.isBlank()) spoken else "$current $spoken"
                viewModel.onInputTextChanged(combined)
            }
        }
    }

    // Document Picker Launcher (PDF & TXT)
    val docPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch(Dispatchers.IO) {
                isOcrProcessing = true
                try {
                    val mime = context.contentResolver.getType(it) ?: ""
                    val doc = if (mime == "application/pdf" || it.toString().endsWith(".pdf", ignoreCase = true)) {
                        DocumentOcrHelper.processPdfUri(context, it)
                    } else if (mime.startsWith("image/")) {
                        DocumentOcrHelper.processImageUri(context, it)
                    } else {
                        DocumentOcrHelper.processTextUri(context, it)
                    }
                    viewModel.attachDocument(doc)
                    val info = if (doc.isImage) "" else " (${doc.wordCount} words)"
                    withContext(Dispatchers.Main) {
                        Toast.makeText(context, "Attached ${doc.fileName}$info", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(context, "Error reading file: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                } finally {
                    isOcrProcessing = false
                }
            }
        }
    }

    // Camera Capture Launcher — pure native multimodal vision
    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap: Bitmap? ->
        bitmap?.let {
            scope.launch(Dispatchers.IO) {
                try {
                    val name = "Photo_${System.currentTimeMillis() % 10000}.jpg"
                    val doc = DocumentOcrHelper.processImageBitmap(it, name)
                    viewModel.attachDocument(doc)
                    withContext(Dispatchers.Main) {
                        Toast.makeText(context, "📷 Photo attached", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(context, "Failed to attach photo: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    // Image Picker Launcher — pure native multimodal vision
    val imagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch(Dispatchers.IO) {
                try {
                    val doc = DocumentOcrHelper.processImageUri(context, it)
                    viewModel.attachDocument(doc)
                    withContext(Dispatchers.Main) {
                        Toast.makeText(context, "🖼️ Image attached", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(context, "Failed to read image: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }


    val listState = rememberLazyListState()
    val canScrollForward by remember { derivedStateOf { listState.canScrollForward } }
    var isScrollToBottomVisible by remember { mutableStateOf(false) }

    // Floating Scroll Down Button Auto-Hide (ChatGPT style):
    // Appears on scroll interaction, stays for 2 seconds, then smoothly auto-hides.
    // Reappears on new scroll touch, and immediately hides when reaching the bottom.
    LaunchedEffect(listState.isScrollInProgress, canScrollForward) {
        if (!canScrollForward) {
            isScrollToBottomVisible = false
        } else if (listState.isScrollInProgress) {
            isScrollToBottomVisible = true
        } else if (isScrollToBottomVisible) {
            kotlinx.coroutines.delay(2000L)
            isScrollToBottomVisible = false
        }
    }

    // When user scrolls messages, dismiss keyboard if it was open (never opens on scroll!)
    LaunchedEffect(listState.isScrollInProgress) {
        if (listState.isScrollInProgress && isImeVisible) {
            keyboardController?.hide()
            focusManager.clearFocus()
        }
    }

    // Haptic feedback when generation completes
    var prevGenerating by remember { mutableStateOf(false) }
    LaunchedEffect(isGenerating) {
        if (prevGenerating && !isGenerating) {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        }
        prevGenerating = isGenerating
    }

    // When a new message is added, animate to bottom (use lastIndex, not size, to stay in bounds)
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            // +1 for bottom_anchor spacer item after the messages list
            val target = messages.size // points to follow_up_chips or bottom_anchor
            listState.animateScrollToItem(target)
        }
    }

    // While generating: auto-scroll token-by-token ONLY if user hasn't scrolled up manually
    LaunchedEffect(messages.lastOrNull()?.text?.length, messages.lastOrNull()?.thoughtText?.length) {
        if (messages.isNotEmpty() && isGenerating && !listState.isScrollInProgress) {
            val totalItems = listState.layoutInfo.totalItemsCount
            val lastVisible = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            // Only auto-scroll when within 3 items of the bottom
            if (totalItems > 0 && lastVisible >= totalItems - 3) {
                listState.scrollToItem(messages.size)
            }
        }
    }

    // After generation finishes: always scroll to bottom so the full response is visible
    LaunchedEffect(isGenerating) {
        if (!isGenerating && messages.isNotEmpty()) {
            kotlinx.coroutines.delay(80L) // let Compose layout settle
            listState.animateScrollToItem(messages.size)
        }
    }

    // User Message Options Dialog (Edit / Copy)
    if (activeUserMenuMessage != null) {
        val userMsg = activeUserMenuMessage!!
        AlertDialog(
            onDismissRequest = { activeUserMenuMessage = null },
            containerColor = Color(0xFF171717),
            title = { Text("Message Options", fontWeight = FontWeight.Bold, color = Color.White) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = Color(0xFF212121),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                viewModel.onInputTextChanged(userMsg.text)
                                editingMessageId = userMsg.id
                                activeUserMenuMessage = null
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Edit, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(10.dp))
                            Text("Edit message", fontWeight = FontWeight.Medium, color = Color.White)
                        }
                    }
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = Color(0xFF212121),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                val cm = (context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager)
                                cm.setPrimaryClip(android.content.ClipData.newPlainText("user_msg", userMsg.text))
                                Toast.makeText(context, "Copied prompt to clipboard", Toast.LENGTH_SHORT).show()
                                activeUserMenuMessage = null
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.ContentCopy, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(10.dp))
                            Text("Copy prompt", fontWeight = FontWeight.Medium, color = Color.White)
                        }
                    }
                }
            },
            confirmButton = {},
            dismissButton = {
                OutlinedButton(onClick = { activeUserMenuMessage = null }) {
                    Text("Close", color = Color.White)
                }
            }
        )
    }

    val activity = LocalContext.current as? Activity
    BackHandler(enabled = !showSettingsPage && !drawerState.isOpen) {
        activity?.moveTaskToBack(true)
    }

    if (showSettingsPage) {
        LaunchedEffect(Unit) {
            viewModel.refreshStorageUsage()
        }
        SettingsScreen(
            currentConfig = config,
            isWebSearchEnabled = isWebSearchEnabled,
            memories = memories,
            onDeleteMemory = { viewModel.removeMemory(it) },
            onClearAllMemories = { viewModel.clearMemories() },
            storageUsageText = storageUsageText,
            onClearCache = { onComplete ->
                viewModel.clearCacheAndTempFiles(onComplete)
            },
            onToggleWebSearch = { viewModel.toggleWebSearch() },
            onApplyConfig = { newConfig ->
                viewModel.updateConfig(newConfig)
                showSettingsPage = false
            },
            onResetDefaults = { viewModel.resetConfig() },
            onBack = {
                scope.launch { drawerState.snapTo(androidx.compose.material3.DrawerValue.Closed) }
                showSettingsPage = false
            }
        )
        return
    }

    if (showMemoryDialog) {
        MemoryDialog(
            memories = memories,
            onAddMemory = { viewModel.addMemory(it) },
            onDeleteMemory = { viewModel.removeMemory(it) },
            onClearAll = { viewModel.clearMemories() },
            onDismiss = { showMemoryDialog = false }
        )
    }

    if (showAttachmentDialog) {
        AttachmentDialog(
            onDismiss = { showAttachmentDialog = false },
            onTakePhoto = { cameraLauncher.launch(null) },
            onPickImage = { imagePickerLauncher.launch("image/*") },
            onPickDocument = { docPickerLauncher.launch(arrayOf("application/pdf", "text/*")) },
            isWebSearchEnabled = isWebSearchEnabled,
            onToggleWebSearch = { viewModel.toggleWebSearch() }
        )
    }

    if (showDeleteConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirmDialog = false },
            title = { Text("Delete Conversation?", fontWeight = FontWeight.Bold) },
            text = { Text("This will permanently remove this conversation from your history.") },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.deleteCurrentChat()
                        showDeleteConfirmDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Delete", color = MaterialTheme.colorScheme.onError)
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showDeleteConfirmDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    if (showRenameDialog) {
        AlertDialog(
            onDismissRequest = { showRenameDialog = false },
            title = { Text("Rename Chat", fontWeight = FontWeight.Bold) },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    singleLine = true,
                    label = { Text("Chat Title") },
                    modifier = Modifier.fillMaxWidth()
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (renameText.isNotBlank()) {
                            viewModel.renameCurrentChat(renameText.trim())
                        }
                        showRenameDialog = false
                    }
                ) {
                    Text("Save")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showRenameDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    Box(modifier = Modifier.fillMaxSize()) {
        ModalNavigationDrawer(
        drawerState = drawerState,
        gesturesEnabled = true,
        drawerContent = {
            ModalDrawerSheet(
                modifier = Modifier
                    .width(320.dp)
                    .fillMaxHeight(),
                drawerContainerColor = Color(0xFF171717)
            ) {
                RecentChatsDrawer(
                    sessions = sessions,
                    currentSessionId = currentSessionId,
                    activeGeneratingSessionId = activeGeneratingSessionId,
                    isWebSearchEnabled = isWebSearchEnabled,
                    onNewChat = {
                        viewModel.createNewChat()
                        scope.launch { drawerState.close() }
                    },
                    onSelectSession = { id ->
                        viewModel.selectSession(id)
                        scope.launch { drawerState.close() }
                    },
                    onDeleteSession = { id ->
                        viewModel.deleteSession(id)
                    },
                    onShareSession = { session ->
                        ExportHelper.shareSession(context, session)
                    },
                    onClearAll = {
                        viewModel.clearAllChats()
                        scope.launch { drawerState.close() }
                    },
                    onOpenVision = {
                        scope.launch { drawerState.close() }
                        imagePickerLauncher.launch("image/*")
                    },
                    onToggleWebSearch = {
                        viewModel.toggleWebSearch()
                    },
                    onOpenSettings = {
                        scope.launch { drawerState.close() }
                        showSettingsPage = true
                    },
                    onOpenMemory = {
                        showMemoryDialog = true
                    },
                    onLaunchVoice = {
                        scope.launch { drawerState.close() }
                        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Gemma…")
                        }
                        voiceLauncher.launch(intent)
                    },
                    onCloseDrawer = {
                        scope.launch { drawerState.close() }
                    }
                )
            }
        }
    ) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            // Main content depending on engine & install state
            when {
                installState !is ModelInstallState.Installed -> {
                    ModelManagementSection(
                        installState = installState,
                        onImportClick = {
                            filePickerLauncher.launch(arrayOf("*/*"))
                        },
                        onRetryCheck = { viewModel.checkModel() },
                        viewModel = viewModel
                    )
                }

                engineState is EngineState.Uninitialized || engineState is EngineState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                            modifier = Modifier.padding(24.dp)
                        ) {
                            Text("✨", fontSize = 48.sp)
                            Spacer(modifier = Modifier.height(20.dp))
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = if (engineState is EngineState.Loading) (engineState as EngineState.Loading).message else "Loading Gemma 4…",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Private • On-device • No internet needed",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.outline
                            )
                        }
                    }
                }

                engineState is EngineState.Error -> {
                    val errorState = engineState as EngineState.Error
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Card(
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.35f)
                            ),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(
                                modifier = Modifier.padding(24.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text("⚠️", fontSize = 44.sp)
                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    text = "Model Loading Failed",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.error
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = errorState.message,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    textAlign = TextAlign.Center
                                )
                                Spacer(modifier = Modifier.height(20.dp))
                                Row(
                                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                                ) {
                                    Button(
                                        onClick = { viewModel.initializeEngine() }
                                    ) {
                                        Text("Retry")
                                    }
                                    OutlinedButton(
                                        onClick = {
                                            viewModel.deleteModel()
                                            viewModel.checkModel()
                                        }
                                    ) {
                                        Text("Delete & Re-Download")
                                    }
                                }
                            }
                        }
                    }
                }

                else -> {
                    // Chat Interface - Full-Page Edge-to-Edge with Vignette Transparency
                    if (messages.isEmpty()) {
                        EmptyChatHero(
                            onPromptSelected = { prompt ->
                                viewModel.onInputTextChanged(prompt)
                                viewModel.sendMessage()
                            },
                            onExamineSelected = {
                                imagePickerLauncher.launch("image/*")
                            }
                        )
                    } else {
                        LazyColumn(
                            state = listState,
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(
                                start = 16.dp,
                                end = 16.dp,
                                top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding() + 58.dp,
                                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 92.dp
                            ),
                            verticalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            items(messages, key = { it.id }) { message ->
                                MessageBubble(
                                    message = message,
                                    isSpeaking = isSpeaking && currentlySpeakingId == message.id,
                                    onSpeak = { viewModel.toggleSpeak(message.id, if (message.text.isNotBlank()) message.text else message.thoughtText) },
                                    onShare = { ExportHelper.shareMessage(context, if (message.text.isNotBlank()) message.text else message.thoughtText) },
                                    onRegenerate = { viewModel.regenerateLastResponse() },
                                    onLongPressUserMessage = { activeUserMenuMessage = it }
                                )
                            }

                            val lastMsg = messages.lastOrNull()
                            val lastContent = (if (lastMsg?.text?.isNotBlank() == true) lastMsg.text else lastMsg?.thoughtText.orEmpty()).trim()
                            if (!isGenerating && lastMsg?.role == MessageRole.ASSISTANT && lastContent.isNotBlank()) {
                                item(key = "follow_up_chips") {
                                    val followUps = remember(lastMsg.id, lastContent) {
                                        extractFollowUpSuggestions(lastContent)
                                    }
                                    if (followUps.isNotEmpty()) {
                                        LazyRow(
                                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(vertical = 4.dp)
                                        ) {
                                            items(followUps) { chip ->
                                                ChatGptSurfaceButton(
                                                    onClick = {
                                                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                        val promptToSend = if (chip.equals("Continue generating", ignoreCase = true)) {
                                                            "Continue from where you left off"
                                                        } else {
                                                            chip
                                                        }
                                                        viewModel.onInputTextChanged(promptToSend)
                                                        viewModel.sendMessage()
                                                    },
                                                    shape = RoundedCornerShape(16.dp),
                                                    color = Color(0xFF212121),
                                                    border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
                                                    shadowElevation = 1.dp
                                                ) {
                                                    Text(
                                                        text = chip,
                                                        style = MaterialTheme.typography.labelMedium,
                                                        color = Color(0xFFECECEC),
                                                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            item(key = "bottom_anchor") {
                                Spacer(modifier = Modifier.height(16.dp))
                            }
                        }
                    }
                }
            }



            // Top Vignette & Floating Controls Header (Edge-to-Edge ChatGPT style)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
            ) {
                // Top Vignette Gradient: Smooth feathering from status bar into chat
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(WindowInsets.statusBars.asPaddingValues().calculateTopPadding() + 68.dp)
                        .background(
                            Brush.verticalGradient(
                                0.0f to Color.Black,
                                0.45f to Color.Black.copy(alpha = 0.85f),
                                0.75f to Color.Black.copy(alpha = 0.40f),
                                1.0f to Color.Transparent
                            )
                        )
                )

                // Floating Action Bar Row
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .statusBarsPadding()
                        .padding(horizontal = 14.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Left: Translucent Circular Hamburger Button ( = )
                    Surface(
                        shape = CircleShape,
                        color = Color(0x99242428),
                        border = BorderStroke(0.5.dp, Color(0x33FFFFFF)),
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .clickable {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                scope.launch { drawerState.open() }
                            }
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.Menu,
                                contentDescription = "Open drawer",
                                tint = Color(0xFFECECEC),
                                modifier = Modifier.size(19.dp)
                            )
                        }
                    }

                    // Center: Subtle Gemma title & status badge
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Text(
                            text = "Gemma",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFFECECEC)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        BackendBadge(engineState = engineState)
                    }

                    // Right: Floating Pill Container [ ✎  |  ⋮ ]
                    var showTopMenu by remember { mutableStateOf(false) }
                    Box {
                        Surface(
                            shape = RoundedCornerShape(20.dp),
                            color = Color(0x99242428),
                            border = BorderStroke(0.5.dp, Color(0x33FFFFFF)),
                            modifier = Modifier.height(38.dp)
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(horizontal = 4.dp)
                            ) {
                                // New Chat Pencil Icon
                                Box(
                                    modifier = Modifier
                                        .size(34.dp)
                                        .clip(CircleShape)
                                        .clickable {
                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                            viewModel.createNewChat()
                                        },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Edit,
                                        contentDescription = "New chat",
                                        tint = Color(0xFFECECEC),
                                        modifier = Modifier.size(17.dp)
                                    )
                                }

                                Spacer(modifier = Modifier.width(2.dp))
                                Box(
                                    modifier = Modifier
                                        .width(1.dp)
                                        .height(16.dp)
                                        .background(Color(0x33FFFFFF))
                                )
                                Spacer(modifier = Modifier.width(2.dp))

                                // 3-Dots More Options Icon
                                Box(
                                    modifier = Modifier
                                        .size(34.dp)
                                        .clip(CircleShape)
                                        .clickable {
                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                            showTopMenu = true
                                        },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.MoreVert,
                                        contentDescription = "More options",
                                        tint = Color(0xFFECECEC),
                                        modifier = Modifier.size(19.dp)
                                    )
                                }
                            }
                        }

                        // Floating dropdown menu anchored directly to the pill
                        DropdownMenu(
                            expanded = showTopMenu,
                            onDismissRequest = { showTopMenu = false },
                            modifier = Modifier
                                .background(Color(0xFF262626))
                                .border(0.5.dp, Color(0xFF383838), RoundedCornerShape(12.dp))
                        ) {
                            DropdownMenuItem(
                                text = { Text("Settings", color = Color.White, fontWeight = FontWeight.Medium) },
                                leadingIcon = {
                                    Icon(Icons.Default.Settings, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                                },
                                onClick = {
                                    showTopMenu = false
                                    showSettingsPage = true
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Memories", color = Color.White) },
                                leadingIcon = {
                                    Icon(Icons.Default.Psychology, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                                },
                                onClick = {
                                    showTopMenu = false
                                    showMemoryDialog = true
                                }
                            )
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        if (isWebSearchEnabled) "Web Search (ON)" else "Web Search (OFF)",
                                        color = if (isWebSearchEnabled) Color(0xFF10A37F) else Color.White
                                    )
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.Language,
                                        contentDescription = null,
                                        tint = if (isWebSearchEnabled) Color(0xFF10A37F) else Color.White,
                                        modifier = Modifier.size(18.dp)
                                    )
                                },
                                onClick = {
                                    showTopMenu = false
                                    viewModel.toggleWebSearch()
                                }
                            )
                            if (messages.isNotEmpty()) {
                                HorizontalDivider(color = Color(0xFF383838), thickness = 0.5.dp)
                                DropdownMenuItem(
                                    text = { Text("Share conversation", color = Color.White) },
                                    leadingIcon = {
                                        Icon(Icons.Default.Share, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                                    },
                                    onClick = {
                                        showTopMenu = false
                                        viewModel.getCurrentSession()?.let { session ->
                                            ExportHelper.shareSession(context, session)
                                        }
                                    }
                                )
                                DropdownMenuItem(
                                    text = { Text("Rename", color = Color.White) },
                                    leadingIcon = {
                                        Icon(Icons.Default.DriveFileRenameOutline, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                                    },
                                    onClick = {
                                        showTopMenu = false
                                        renameText = viewModel.getCurrentSession()?.title ?: ""
                                        showRenameDialog = true
                                    }
                                )
                                DropdownMenuItem(
                                    text = { Text("Delete conversation", color = MaterialTheme.colorScheme.error) },
                                    leadingIcon = {
                                        Icon(Icons.Default.Delete, contentDescription = null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(18.dp))
                                    },
                                    onClick = {
                                        showTopMenu = false
                                        showDeleteConfirmDialog = true
                                    }
                                )
                            }
                        }
                    }
                }
            }

            // Top Error Banner (floating under top bar)
            AnimatedVisibility(
                visible = errorMessage != null,
                enter = fadeIn(),
                exit = fadeOut(),
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding() + 54.dp)
            ) {
                errorMessage?.let { error ->
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 4.dp),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = error,
                                color = MaterialTheme.colorScheme.onErrorContainer,
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.weight(1f)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            TextButton(onClick = { viewModel.dismissError() }) {
                                Text("Dismiss", color = MaterialTheme.colorScheme.onErrorContainer)
                            }
                        }
                    }
                }
            }

            // Bottom Vignette & Floating Input Dock
            if (installState is ModelInstallState.Installed && (engineState is EngineState.Ready || engineState is EngineState.Generating)) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .align(Alignment.BottomCenter)
                        .imePadding()
                ) {
                    // Smooth Bottom Vignette Gradient (Transparent -> AMOLED Black)
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 96.dp)
                            .background(
                                Brush.verticalGradient(
                                    0.0f to Color.Transparent,
                                    0.25f to Color.Black.copy(alpha = 0.40f),
                                    0.65f to Color.Black.copy(alpha = 0.90f),
                                    1.0f to Color.Black
                                )
                            )
                            .align(Alignment.BottomCenter)
                    )

                    // Input Dock Column
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .navigationBarsPadding()
                            .padding(bottom = 4.dp)
                    ) {
                        // Attached Document / Image Preview (ChatGPT Floating Thumbnail Style)
                        if (attachedDocument != null) {
                            val doc = attachedDocument!!
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 16.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                if (doc.isImage && doc.previewBitmap != null) {
                                    Box(
                                        modifier = Modifier.size(58.dp)
                                    ) {
                                        androidx.compose.foundation.Image(
                                            painter = androidx.compose.ui.graphics.painter.BitmapPainter(doc.previewBitmap!!.asImageBitmap()),
                                            contentDescription = "Image preview",
                                            modifier = Modifier
                                                .size(54.dp)
                                                .align(Alignment.BottomStart)
                                                .clip(RoundedCornerShape(12.dp))
                                                .background(Color(0xFF212121)),
                                            contentScale = ContentScale.Crop
                                        )
                                        Surface(
                                            shape = CircleShape,
                                            color = Color(0xFF212121),
                                            border = BorderStroke(1.dp, Color(0xFF383838)),
                                            modifier = Modifier
                                                .size(20.dp)
                                                .align(Alignment.TopEnd)
                                                .clickable { viewModel.clearAttachedDocument() }
                                        ) {
                                            Box(contentAlignment = Alignment.Center) {
                                                Icon(
                                                    imageVector = Icons.Default.Close,
                                                    contentDescription = "Remove image",
                                                    tint = Color.White,
                                                    modifier = Modifier.size(11.dp)
                                                )
                                            }
                                        }
                                    }
                                } else {
                                    val isPdf = doc.fileName.endsWith(".pdf", ignoreCase = true)
                                    Surface(
                                        shape = RoundedCornerShape(16.dp),
                                        color = Color(0xFF1C1C20),
                                        border = BorderStroke(1.dp, Color(0xFF2C2C34))
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                                        ) {
                                            Box(
                                                modifier = Modifier
                                                    .size(34.dp)
                                                    .clip(RoundedCornerShape(8.dp))
                                                    .background(if (isPdf) Color(0xFF381515) else Color(0xFF132824)),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                Icon(
                                                    imageVector = if (isPdf) Icons.Default.PictureAsPdf else Icons.Default.Description,
                                                    contentDescription = "File",
                                                    tint = if (isPdf) Color(0xFFFF857D) else Color(0xFF66D9B8),
                                                    modifier = Modifier.size(18.dp)
                                                )
                                            }
                                            Column(modifier = Modifier.widthIn(max = 210.dp)) {
                                                Text(
                                                    text = doc.fileName,
                                                    style = MaterialTheme.typography.labelMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                    color = Color.White,
                                                    maxLines = 1,
                                                    overflow = TextOverflow.Ellipsis
                                                )
                                                val details = if (doc.pageCount > 1) {
                                                    "${doc.pageCount} pages • ${doc.wordCount} words"
                                                } else {
                                                    "${doc.wordCount} words"
                                                }
                                                Text(
                                                    text = details,
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = Color(0xFFAAAAAA),
                                                    fontSize = 11.sp
                                                )
                                            }
                                            Box(
                                                modifier = Modifier
                                                    .size(24.dp)
                                                    .clip(CircleShape)
                                                    .background(Color(0xFF2A2A30))
                                                    .clickable { viewModel.clearAttachedDocument() },
                                                contentAlignment = Alignment.Center
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.Close,
                                                    contentDescription = "Remove",
                                                    tint = Color(0xFFCCCCCC),
                                                    modifier = Modifier.size(14.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }

                            if (!doc.isImage) {
                                androidx.compose.foundation.lazy.LazyRow(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(start = 16.dp, end = 16.dp, top = 2.dp, bottom = 4.dp),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    val docChips = listOf(
                                        Pair("📑 Summarize document", "Summarize this document"),
                                        Pair("📚 Extract all topics", "Extract all topics and sections"),
                                        Pair("🎯 Key takeaways", "Key takeaways and findings"),
                                        Pair("❓ Ask a question", "")
                                    )
                                    items(docChips) { (chipLabel, actionPrompt) ->
                                        Surface(
                                            shape = RoundedCornerShape(12.dp),
                                            color = Color(0xFF1E1E24),
                                            border = BorderStroke(1.dp, Color(0xFF33333E)),
                                            modifier = Modifier.clickable {
                                                if (actionPrompt.isNotBlank()) {
                                                    viewModel.onInputTextChanged(actionPrompt)
                                                    viewModel.sendMessage()
                                                } else {
                                                    keyboardController?.show()
                                                }
                                            }
                                        ) {
                                            Text(
                                                text = chipLabel,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = Color(0xFFD6D6E0),
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp)
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        // Editing message pill (ChatGPT style)
                        if (editingMessageId != null) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(start = 16.dp, end = 16.dp, bottom = 4.dp)
                            ) {
                                Surface(
                                    shape = RoundedCornerShape(14.dp),
                                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.7f),
                                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
                                ) {
                                    Row(
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Edit,
                                            contentDescription = null,
                                            tint = MaterialTheme.colorScheme.onSecondaryContainer,
                                            modifier = Modifier.size(13.dp)
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(
                                            text = "Editing message",
                                            style = MaterialTheme.typography.labelSmall,
                                            fontWeight = FontWeight.Medium,
                                            color = MaterialTheme.colorScheme.onSecondaryContainer
                                        )
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Icon(
                                            imageVector = Icons.Default.Close,
                                            contentDescription = "Cancel edit",
                                            tint = MaterialTheme.colorScheme.onSecondaryContainer,
                                            modifier = Modifier
                                                .size(14.dp)
                                                .clip(CircleShape)
                                                .clickable {
                                                    editingMessageId = null
                                                    viewModel.onInputTextChanged("")
                                                }
                                        )
                                    }
                                }
                            }
                        }

                        // Floating ChatGPT style Memory Updated Notification
                        AnimatedVisibility(
                            visible = memoryUpdatedEvent != null,
                            enter = fadeIn() + slideInVertically { it / 2 },
                            exit = fadeOut() + slideOutVertically { it / 2 },
                            modifier = Modifier
                                .align(Alignment.CenterHorizontally)
                                .padding(bottom = 6.dp)
                        ) {
                            Surface(
                                shape = RoundedCornerShape(20.dp),
                                color = Color(0xFF1E1E1E),
                                border = BorderStroke(1.dp, Color(0xFF333333)),
                                modifier = Modifier
                                    .clip(RoundedCornerShape(20.dp))
                                    .clickable { showMemoryDialog = true }
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 7.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "🧠",
                                        fontSize = 13.sp
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = memoryUpdatedEvent ?: "Memory updated",
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Medium,
                                        color = Color(0xFFECECEC),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Icon(
                                        imageVector = Icons.Default.Close,
                                        contentDescription = "Dismiss memory notification",
                                        tint = Color(0xFF8E8E93),
                                        modifier = Modifier
                                            .size(13.dp)
                                            .clickable { viewModel.clearMemoryUpdatedEvent() }
                                    )
                                }
                            }
                        }

                        // Scroll-to-Bottom Button — anchored just above input bar (always correct position)
                        AnimatedVisibility(
                            visible = isScrollToBottomVisible && canScrollForward,
                            enter = fadeIn(tween(180)) + scaleIn(tween(180), initialScale = 0.85f),
                            exit = fadeOut(tween(220)) + scaleOut(tween(220), targetScale = 0.85f),
                            modifier = Modifier
                                .align(Alignment.CenterHorizontally)
                                .padding(bottom = 6.dp)
                        ) {
                            Surface(
                                shape = CircleShape,
                                color = Color(0xFF212121),
                                shadowElevation = 4.dp,
                                border = BorderStroke(1.dp, Color(0xFF383838)),
                                modifier = Modifier
                                    .size(36.dp)
                                    .clip(CircleShape)
                                    .clickable {
                                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                        scope.launch {
                                            listState.animateScrollToItem(messages.size)
                                        }
                                    }
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Default.KeyboardArrowDown,
                                        contentDescription = "Scroll to bottom",
                                        tint = Color.White,
                                        modifier = Modifier.size(22.dp)
                                    )
                                }
                            }
                        }

                        // Floating ChatGPT style Input Bar
                        ChatInputBar(
                            inputText = inputText,

                            onTextChanged = { viewModel.onInputTextChanged(it) },
                            onSend = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                if (editingMessageId != null) {
                                    val targetId = editingMessageId!!
                                    editingMessageId = null
                                    viewModel.editAndResendMessage(targetId, inputText)
                                    viewModel.onInputTextChanged("")
                                } else {
                                    viewModel.sendMessage()
                                    viewModel.onInputTextChanged("")
                                }
                            },
                            onStop = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                viewModel.stopGeneration()
                            },
                            isGenerating = isGenerating,
                            isWebSearchEnabled = isWebSearchEnabled,
                            onToggleWebSearch = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                viewModel.toggleWebSearch()
                            },
                            isEnabled = engineState is EngineState.Ready || engineState is EngineState.Generating,
                            onVoiceInput = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                    putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Gemma…")
                                }
                                voiceLauncher.launch(intent)
                            },
                            onVoiceAssistant = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                    putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Gemma…")
                                }
                                voiceLauncher.launch(intent)
                            },
                            onAttach = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                showAttachmentMenu = !showAttachmentMenu
                            },
                            hasAttachment = attachedDocument != null
                        )
                    }
                }
            }
        }
    }
}

    // Floating Attachment Popup Menu (matching ChatGPT AMOLED pure dark screenshot)
    if (showAttachmentMenu) {
        // Scrim using pointerInput so it NEVER steals focus from the text field
        Box(
            modifier = Modifier
                .fillMaxSize()
                .pointerInput(Unit) {
                    detectTapGestures {
                        showAttachmentMenu = false
                    }
                }
        )
    }

    AnimatedVisibility(
        visible = showAttachmentMenu,
        enter = fadeIn(tween(140)) + scaleIn(tween(140), initialScale = 0.92f),
        exit = fadeOut(tween(100)) + scaleOut(tween(100), targetScale = 0.92f)
    ) {
        // Floating Dark Card anchored directly above the + button with imePadding so it stays above keyboard!
        Box(
            modifier = Modifier
                .fillMaxSize()
                .imePadding()
                .navigationBarsPadding()
                .padding(start = 20.dp, bottom = 72.dp),
            contentAlignment = Alignment.BottomStart
        ) {
            Surface(
                shape = RoundedCornerShape(22.dp),
                color = Color(0xFF262626),
                border = BorderStroke(1.dp, Color(0xFF383838)),
                shadowElevation = 10.dp,
                modifier = Modifier
                    .width(260.dp)
                    .clip(RoundedCornerShape(22.dp))
            ) {
                Column(
                    modifier = Modifier.padding(vertical = 8.dp, horizontal = 6.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    FloatingMenuItem(
                        icon = Icons.Default.CameraAlt,
                        label = "Camera",
                        onClick = {
                            showAttachmentMenu = false
                            showCameraOverlay = true
                        }
                    )
                    FloatingMenuItem(
                        icon = Icons.Default.Image,
                        label = "Photos",
                        onClick = {
                            showAttachmentMenu = false
                            imagePickerLauncher.launch("image/*")
                        }
                    )
                    FloatingMenuItem(
                        icon = Icons.Default.AttachFile,
                        label = "Files",
                        onClick = {
                            showAttachmentMenu = false
                            showAddFilesSheet = true
                        }
                    )
                    HorizontalDivider(
                        color = Color(0xFF383838),
                        thickness = 0.5.dp,
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                    FloatingMenuItemWithToggle(
                        icon = Icons.Default.Language,
                        label = "Web search",
                        isChecked = isWebSearchEnabled,
                        onToggle = {
                            viewModel.toggleWebSearch()
                        }
                    )
                    FloatingMenuItemWithToggle(
                        icon = Icons.Default.Psychology,
                        label = "Think harder",
                        isChecked = config.enableThinking,
                        onToggle = {
                            viewModel.updateConfig(config.copy(enableThinking = !config.enableThinking))
                        }
                    )
                }
            }
        }
    }

    // In-Chat Camera Viewfinder Overlay (matching media_1791398963414.jpg)
    InChatCameraOverlay(
        visible = showCameraOverlay,
        onDismiss = { showCameraOverlay = false },
        onPhotoCaptured = { doc ->
            showCameraOverlay = false
            viewModel.attachDocument(doc)
            Toast.makeText(context, "📷 Photo attached", Toast.LENGTH_SHORT).show()
        }
    )

    // AMOLED Dark "Add files" Modal Page (matching media_1791398949494.jpg)
    AddFilesSheet(
        visible = showAddFilesSheet,
        onDismiss = { showAddFilesSheet = false },
        onUploadFiles = {
            docPickerLauncher.launch(arrayOf("*/*"))
        },
        onFileSelected = { doc ->
            viewModel.attachDocument(doc)
            Toast.makeText(context, "Attached ${doc.fileName}", Toast.LENGTH_SHORT).show()
        },
        recentFiles = recentFiles
    )
}

@Composable
fun RecentChatsDrawer(
    sessions: List<ChatSession>,
    currentSessionId: String,
    activeGeneratingSessionId: String? = null,
    isWebSearchEnabled: Boolean = false,
    onNewChat: () -> Unit,
    onSelectSession: (String) -> Unit,
    onDeleteSession: (String) -> Unit,
    onShareSession: (ChatSession) -> Unit,
    onClearAll: () -> Unit,
    onOpenVision: () -> Unit = {},
    onToggleWebSearch: () -> Unit = {},
    onOpenSettings: () -> Unit,
    onOpenMemory: () -> Unit,
    onLaunchVoice: () -> Unit = {},
    onCloseDrawer: () -> Unit
) {
    var showClearAllConfirm by remember { mutableStateOf(false) }

    if (showClearAllConfirm) {
        AlertDialog(
            onDismissRequest = { showClearAllConfirm = false },
            containerColor = Color(0xFF212121),
            title = { Text("Clear All Chats?", fontWeight = FontWeight.SemiBold, color = Color.White) },
            text = { Text("Are you sure you want to delete all saved conversations? This cannot be undone.", color = Color(0xFFB0B0B0)) },
            confirmButton = {
                Button(
                    onClick = {
                        showClearAllConfirm = false
                        onClearAll()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Clear All", color = MaterialTheme.colorScheme.onError)
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showClearAllConfirm = false }) {
                    Text("Cancel", color = Color.White)
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .background(Color(0xFF171717))
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        // Top Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Gemma",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            IconButton(onClick = onCloseDrawer, modifier = Modifier.size(32.dp)) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Close drawer",
                    tint = Color(0xFFAAAAAA),
                    modifier = Modifier.size(20.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        // Search chats (ChatGPT capsule)
        var searchQuery by remember { mutableStateOf("") }
        val filteredSessions = remember(sessions, searchQuery) {
            if (searchQuery.isBlank()) sessions
            else sessions.filter {
                it.title.contains(searchQuery, ignoreCase = true) ||
                it.messages.any { m -> m.text.contains(searchQuery, ignoreCase = true) }
            }
        }

        Surface(
            shape = RoundedCornerShape(12.dp),
            color = Color(0xFF212121),
            border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
            modifier = Modifier
                .fillMaxWidth()
                .height(40.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Search,
                    contentDescription = null,
                    tint = Color(0xFF8E8E93),
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                BasicTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    singleLine = true,
                    textStyle = TextStyle(fontSize = 14.sp, color = Color.White),
                    cursorBrush = SolidColor(Color.White),
                    modifier = Modifier.weight(1f),
                    decorationBox = { innerTextField ->
                        if (searchQuery.isEmpty()) {
                            Text(
                                text = "Search chats...",
                                style = MaterialTheme.typography.bodyMedium.copy(
                                    fontSize = 14.sp,
                                    color = Color(0xFF8E8E93)
                                )
                            )
                        }
                        innerTextField()
                    }
                )
                if (searchQuery.isNotEmpty()) {
                    IconButton(
                        onClick = { searchQuery = "" },
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Clear search",
                            tint = Color(0xFF8E8E93),
                            modifier = Modifier.size(14.dp)
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Quick feature shortcuts (matching Screenshot 3)
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            DrawerShortcutRow(
                icon = Icons.Default.CameraAlt,
                label = "Vision & OCR",
                onClick = onOpenVision
            )
            DrawerShortcutRow(
                icon = Icons.Default.Psychology,
                label = "Memories",
                onClick = { onOpenMemory(); onCloseDrawer() }
            )
            DrawerShortcutRow(
                icon = Icons.Default.Language,
                label = if (isWebSearchEnabled) "Web Search (ON)" else "Web Search",
                tint = if (isWebSearchEnabled) Color(0xFF10A37F) else Color(0xFFB0B0B0),
                onClick = onToggleWebSearch
            )
            DrawerShortcutRow(
                icon = Icons.Default.Settings,
                label = "Settings",
                onClick = { onOpenSettings(); onCloseDrawer() }
            )
        }

        Spacer(modifier = Modifier.height(10.dp))
        HorizontalDivider(color = Color(0xFF282828), thickness = 0.5.dp)
        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Recent chats",
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF8E8E93),
            modifier = Modifier.padding(start = 4.dp, bottom = 6.dp)
        )

        // Session list
        if (filteredSessions.isEmpty()) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (searchQuery.isNotBlank()) "No matching chats found" else "No recent chats yet",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF8E8E93)
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                items(filteredSessions, key = { it.id }) { session ->
                    val isSelected = session.id == currentSessionId
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        color = if (isSelected) Color(0xFF262626) else Color.Transparent,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .clickable { onSelectSession(session.id) }
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 10.dp, vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(
                                modifier = Modifier.weight(1f),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = session.title,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                                    color = Color.White,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f, fill = false)
                                )
                                if (session.id == activeGeneratingSessionId) {
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = "Writing…",
                                        style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp),
                                        color = Color(0xFF10A37F),
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(
                                    onClick = { onShareSession(session) },
                                    modifier = Modifier.size(26.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Share,
                                        contentDescription = "Share chat",
                                        tint = Color(0xFF8E8E93),
                                        modifier = Modifier.size(15.dp)
                                    )
                                }
                                IconButton(
                                    onClick = { onDeleteSession(session.id) },
                                    modifier = Modifier.size(26.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Delete,
                                        contentDescription = "Delete chat",
                                        tint = Color(0xFF8E8E93),
                                        modifier = Modifier.size(15.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
        HorizontalDivider(color = Color(0xFF282828), thickness = 0.5.dp)
        Spacer(modifier = Modifier.height(10.dp))

        // Bottom pinned bar (matching Screenshot 3: Coral Pink Chat button + avatar "TP" + Voice button)
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            // Coral Pink "+ Chat" pill button
            Surface(
                shape = RoundedCornerShape(22.dp),
                color = Color(0xFFF43F5E),
                modifier = Modifier
                    .clip(RoundedCornerShape(22.dp))
                    .clickable { onNewChat() }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = "New chat",
                        tint = Color.White,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Chat",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // User Avatar "TP" (Teja Pampana) -> Opens Settings on click (ChatGPT style)
                Surface(
                    shape = CircleShape,
                    color = Color(0xFF2E2E2E),
                    border = BorderStroke(1.dp, Color(0xFF383838)),
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .clickable { onOpenSettings() }
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            text = "TP",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                }

                // Voice assistant button
                Surface(
                    shape = CircleShape,
                    color = Color(0xFF212121),
                    border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .clickable { onLaunchVoice() }
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.GraphicEq,
                            contentDescription = "Voice assistant",
                            tint = Color(0xFFF43F5E),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DrawerShortcutRow(
    icon: ImageVector,
    label: String,
    tint: Color = Color(0xFFB0B0B0),
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = Color.Transparent,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = tint,
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = if (tint != Color(0xFFB0B0B0)) tint else Color.White
            )
        }
    }
}

@Composable
fun EmptyChatHero(
    onPromptSelected: (String) -> Unit,
    onExamineSelected: () -> Unit = {}
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 24.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // Centered subtle greeting / logo
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Surface(
                shape = CircleShape,
                color = Color(0xFF212121),
                border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
                modifier = Modifier.size(60.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(text = "✦", fontSize = 28.sp, color = Color(0xFF10A37F))
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            Text(
                text = "What can I help with?",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                color = Color.White
            )

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = "On-device • 100% Private • Multimodal",
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF8E8E93)
            )
        }

        // Minimal ChatGPT-style bottom suggestion pills (matching Screenshot 1 & 2)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Suggestion 1: Examine image or document
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFF212121),
                border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .clickable { onExamineSelected() }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 11.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Image,
                        contentDescription = null,
                        tint = Color(0xFF8E8E93),
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = "Examine image or document",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White
                    )
                }
            }

            // Suggestion 2: Write, explain or code
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFF212121),
                border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .clickable { onPromptSelected("Explain how quantum computing works with a simple analogy") }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 11.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Edit,
                        contentDescription = null,
                        tint = Color(0xFF8E8E93),
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = "Write, explain or code",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White
                    )
                }
            }
        }
    }
}

@Composable
fun BackendBadge(engineState: EngineState) {
    val (label, bg, fg) = when (engineState) {
        is EngineState.Ready -> {
            when (engineState.backend) {
                BackendType.GPU -> Triple("GPU", Color(0xFF1E3A2F), Color(0xFF10A37F))
                BackendType.CPU_FALLBACK -> Triple("CPU fallback", Color(0xFF3E2D1A), Color(0xFFFFB74D))
                BackendType.CPU -> Triple("CPU", Color(0xFF262629), Color(0xFFA0A0A5))
            }
        }
        is EngineState.Generating -> {
            Triple("Generating...", Color(0xFF1A2A3A), Color(0xFF58A6FF))
        }
        is EngineState.Loading -> {
            Triple("Loading...", Color(0xFF2A1F3D), Color(0xFFB39DDB))
        }
        else -> {
            Triple("Offline", Color(0xFF262629), Color(0xFF8E8E93))
        }
    }

    AnimatedContent(
        targetState = Triple(label, bg, fg),
        transitionSpec = { fadeIn(tween(200)).togetherWith(fadeOut(tween(180))) },
        label = "backendBadgeTransition"
    ) { (curLabel, curBg, curFg) ->
        Surface(
            color = curBg,
            shape = RoundedCornerShape(12.dp)
        ) {
            Text(
                text = curLabel,
                color = curFg,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun MessageBubble(
    message: ChatMessage,
    isSpeaking: Boolean = false,
    onSpeak: () -> Unit = {},
    onShare: () -> Unit = {},
    onRegenerate: () -> Unit = {},
    onLongPressUserMessage: (ChatMessage) -> Unit = {}
) {
    val isUser = message.role == MessageRole.USER
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current
    val haptic = LocalHapticFeedback.current

    val displayBitmap = remember(message.id, message.imageBitmap, message.imagePath) {
        message.imageBitmap ?: message.imagePath?.let { path ->
            try { android.graphics.BitmapFactory.decodeFile(path) } catch (_: Exception) { null }
        }
    }

    if (isUser) {
        // ── USER bubble: dark charcoal pill, right-aligned, no avatar ──────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.Bottom
        ) {
            IconButton(
                onClick = {
                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                    onLongPressUserMessage(message)
                },
                modifier = Modifier
                    .size(28.dp)
                    .padding(end = 4.dp, bottom = 2.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Edit,
                    contentDescription = "Edit prompt",
                    tint = Color(0xFFAAAAAA),
                    modifier = Modifier.size(15.dp)
                )
            }

            Surface(
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFF381024), // ChatGPT dark burgundy/plum bubble (matching media_1791402016025.jpg)
                modifier = Modifier
                    .widthIn(max = 295.dp)
                    .clip(RoundedCornerShape(20.dp))
                    .combinedClickable(
                        onClick = {
                            onLongPressUserMessage(message)
                        },
                        onLongClick = {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            onLongPressUserMessage(message)
                        }
                    )
            ) {
                Column(
                    modifier = Modifier.padding(
                        if (displayBitmap != null && message.text.isBlank()) 4.dp
                        else 12.dp
                    )
                ) {
                    if (displayBitmap != null) {
                        androidx.compose.foundation.Image(
                            painter = androidx.compose.ui.graphics.painter.BitmapPainter(displayBitmap.asImageBitmap()),
                            contentDescription = "User uploaded photo",
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 240.dp)
                                .clip(RoundedCornerShape(14.dp)),
                            contentScale = ContentScale.Crop
                        )
                        if (message.text.isNotBlank()) {
                            Spacer(modifier = Modifier.height(8.dp))
                        }
                    }
                    if (message.text.isNotBlank()) {
                        if (message.text.startsWith("📄 **[")) {
                            val parts = message.text.split("\n\n", limit = 2)
                            val header = parts.getOrNull(0) ?: ""
                            val userPrompt = parts.getOrNull(1) ?: ""

                            // Google AI Edge / NotebookLM Source Card
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = Color(0xFF2A0D1B),
                                border = BorderStroke(1.dp, Color(0xFF4A1731)),
                                modifier = Modifier.padding(bottom = 6.dp)
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Description,
                                        contentDescription = "Source",
                                        tint = Color(0xFFFFB4AB),
                                        modifier = Modifier.size(14.dp)
                                    )
                                    Text(
                                        text = header.removePrefix("📄 ").replace("**", ""),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Color(0xFFE6E0E9),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                            }
                            if (userPrompt.isNotBlank()) {
                                Text(
                                    text = userPrompt,
                                    style = MaterialTheme.typography.bodyMedium.copy(
                                        color = Color.White,
                                        lineHeight = 22.sp
                                    )
                                )
                            }
                        } else {
                            Text(
                                text = message.text,
                                style = MaterialTheme.typography.bodyMedium.copy(
                                    color = Color.White,
                                    lineHeight = 22.sp
                                )
                            )
                        }
                    }
                }
            }
        }
    } else {
        // ── ASSISTANT: clean ChatGPT style (no avatar header, pure text aligned to left) ──
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 4.dp),
            horizontalAlignment = Alignment.Start
        ) {

            val effectiveText = when {
                message.text.isNotEmpty() -> message.text
                !message.isStreaming && message.thoughtText.isNotEmpty() -> message.thoughtText
                else -> ""
            }

            // Thinking card: shown while streaming thoughts OR if thoughtText exists alongside body text
            if (message.thoughtText.isNotEmpty() && (message.text.isNotEmpty() || message.isStreaming)) {
                ThinkingCard(
                    thoughtText = message.thoughtText,
                    isThinking = message.isThinking,
                    isStreaming = message.isStreaming
                )
                if (effectiveText.isNotEmpty() && message.text.isNotEmpty()) Spacer(modifier = Modifier.height(8.dp))
            }

            // Autonomous tool execution indicator
            if (message.isExecutingTool) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = Color(0xFF1C1C20),
                    border = BorderStroke(1.dp, Color(0xFF2E2E36)),
                    modifier = Modifier.padding(vertical = 4.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(12.dp),
                            color = Color(0xFF10A37F),
                            strokeWidth = 1.5.dp
                        )
                        Text(
                            text = message.toolExecutionStatus ?: "Executing tool...",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFE5E5E5),
                            fontSize = 11.5.sp
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            // ChatGPT "Searched N sites" collapsible accordion (matching media_1791402016025.jpg)
            if (message.isSearchingWeb) {
                ChatGptSearchingWebPill()
                Spacer(modifier = Modifier.height(10.dp))
            } else if (message.searchResults.isNotEmpty()) {
                ChatGptSearchedSitesPill(
                    searchResults = message.searchResults
                )
                Spacer(modifier = Modifier.height(10.dp))
            }

            // Minimal subtle pulsing dot while waiting for first token (ChatGPT style)
            if (effectiveText.isEmpty() && message.isStreaming && message.thoughtText.isEmpty()) {
                val infiniteTransition = rememberInfiniteTransition(label = "cursorBlink")
                val alpha by infiniteTransition.animateFloat(
                    initialValue = 0.2f,
                    targetValue = 1f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(400),
                        repeatMode = RepeatMode.Reverse
                    ),
                    label = "cursorAlpha"
                )
                Box(
                    modifier = Modifier
                        .padding(vertical = 6.dp)
                        .size(10.dp)
                        .graphicsLayer { this.alpha = alpha }
                        .background(Color.White, CircleShape)
                )
            } else if (effectiveText.isNotEmpty()) {
                val emailDraft = if (!message.isStreaming && effectiveText.contains("Subject:", ignoreCase = true)) {
                    remember(effectiveText) { extractEmailDraft(effectiveText) }
                } else null
                if (emailDraft != null) {
                    val (preamble, body) = emailDraft
                    if (preamble != null) {
                        MarkdownText(text = preamble, isUser = false, searchResults = message.searchResults)
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                    EmailDraftBox(draftText = body)
                } else {
                    MarkdownText(text = effectiveText, isUser = false, searchResults = message.searchResults)
                }
            }

                // Search Images Carousel & In-App Preview (ChatGPT style)
                var previewImage by remember { mutableStateOf<SearchImage?>(null) }
                if (message.searchImages.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    SearchImagesCarousel(
                        images = message.searchImages,
                        onImageClick = { img ->
                            previewImage = img
                        }
                    )
                }
                if (previewImage != null) {
                    InAppImagePreviewDialog(
                        image = previewImage!!,
                        onDismiss = { previewImage = null }
                    )
                }

                // Profile & Link Cards (ChatGPT interactive cards with Open Profile action)
                if (!message.isStreaming && effectiveText.isNotEmpty() && message.searchResults.isNotEmpty()) {
                    val profileCards = remember(message.searchResults) { extractProfileCards(message.searchResults) }
                    if (profileCards.isNotEmpty()) {
                        ProfileCardsRow(cards = profileCards)
                    }
                }

                // Document Citations Badge (Google AI Edge Gallery / NotebookLM style)
                if (!message.isStreaming && message.citedPages.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = Color(0xFF16161A),
                        border = BorderStroke(1.dp, Color(0xFF28282E))
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.MenuBook,
                                contentDescription = "Sources",
                                tint = Color(0xFF8AB4F8),
                                modifier = Modifier.size(13.dp)
                            )
                            val docName = message.sourceFileName?.let { "$it • " } ?: ""
                            val pagesText = message.citedPages.joinToString(", ") { "Page $it" }
                            Text(
                                text = "Sources: $docName$pagesText",
                                style = MaterialTheme.typography.labelSmall,
                                color = Color(0xFFC4C7C5)
                            )
                        }
                    }
                }

                // Action bar — only after streaming done (matching media_1791402016025.jpg)
                if (!message.isStreaming && effectiveText.isNotEmpty()) {
                    var showSourcesSheet by remember { mutableStateOf(false) }
                    Spacer(modifier = Modifier.height(10.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        // Left icons (Copy, Like, Dislike, Speaker, Share, Regenerate)
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(2.dp)
                        ) {
                            // Copy
                            IconButton(
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    clipboardManager.setText(AnnotatedString(effectiveText))
                                    Toast.makeText(context, "Copied", Toast.LENGTH_SHORT).show()
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.ContentCopy,
                                    contentDescription = "Copy",
                                    tint = Color(0xFF8E8E93),
                                    modifier = Modifier.size(15.dp)
                                )
                            }
                            // Like
                            IconButton(
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    Toast.makeText(context, "Good response", Toast.LENGTH_SHORT).show()
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.ThumbUp,
                                    contentDescription = "Good response",
                                    tint = Color(0xFF8E8E93),
                                    modifier = Modifier.size(15.dp)
                                )
                            }
                            // Dislike
                            IconButton(
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    Toast.makeText(context, "Bad response", Toast.LENGTH_SHORT).show()
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.ThumbDown,
                                    contentDescription = "Bad response",
                                    tint = Color(0xFF8E8E93),
                                    modifier = Modifier.size(15.dp)
                                )
                            }
                            // Speak / stop
                            IconButton(
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    onSpeak()
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = if (isSpeaking) Icons.Default.Stop else Icons.Default.VolumeUp,
                                    contentDescription = if (isSpeaking) "Stop reading" else "Read aloud",
                                    tint = Color(0xFF8E8E93),
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                            // Share
                            IconButton(
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    onShare()
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Share,
                                    contentDescription = "Share",
                                    tint = Color(0xFF8E8E93),
                                    modifier = Modifier.size(15.dp)
                                )
                            }
                            // Regenerate
                            IconButton(
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    onRegenerate()
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Refresh,
                                    contentDescription = "Regenerate response",
                                    tint = Color(0xFF8E8E93),
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        }

                        // Right: [in] [in] [S] Sources button (matching media_1791402016025.jpg)
                        if (message.searchResults.isNotEmpty()) {
                            ChatGptSourcesPill(
                                searchResults = message.searchResults,
                                onClick = {
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    showSourcesSheet = true
                                }
                            )
                            SourcesBottomSheet(
                                visible = showSourcesSheet,
                                searchResults = message.searchResults,
                                onDismiss = { showSourcesSheet = false }
                            )
                        }
                    }
                }
            }
        }
    }

// Dynamic, alive ChatGPT-style working indicator (never feels stuck)
@Composable
fun DynamicWorkingIndicator(
    isImage: Boolean = false,
    isWebSearch: Boolean = false
) {
    val statusMessages = remember(isImage, isWebSearch) {
        when {
            isImage -> listOf(
                "Analyzing image…",
                "Examining visual details…",
                "Reading content…",
                "Formulating answer…"
            )
            isWebSearch -> listOf(
                "Searching the web…",
                "Reading live web sources…",
                "Synthesizing answer…"
            )
            else -> listOf(
                "Thinking…",
                "Working on response…",
                "Formulating answer…"
            )
        }
    }

    var currentIndex by remember { mutableStateOf(0) }

    LaunchedEffect(statusMessages) {
        while (true) {
            kotlinx.coroutines.delay(1800)
            currentIndex = (currentIndex + 1) % statusMessages.size
        }
    }

    Row(
        modifier = Modifier.padding(top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(13.dp),
            strokeWidth = 1.8.dp,
            color = Color(0xFF10A37F)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = statusMessages[currentIndex],
            style = MaterialTheme.typography.bodyMedium.copy(fontSize = 13.5.sp),
            color = Color(0xFFAAAAAA),
            fontWeight = FontWeight.Medium
        )
    }
}


/**
 * Detects whether the text contains an email draft and returns (preamble, emailContent).
 */
fun extractEmailDraft(text: String): Pair<String?, String>? {
    val t = text.trim()

    // Pattern 1: Code block containing email content
    val codeBlockMatch = Regex("""```(?:email|markdown|text)?\s*([\s\S]*?)```""", RegexOption.IGNORE_CASE).find(t)
    if (codeBlockMatch != null) {
        val block = codeBlockMatch.groupValues[1].trim()
        if (block.contains("Subject:", ignoreCase = true) || block.contains("Dear ", ignoreCase = true)) {
            val pre = t.substring(0, codeBlockMatch.range.first).trim()
            return Pair(if (pre.isNotBlank()) pre else null, block)
        }
    }

    // Pattern 2: Raw email with "Subject:"
    val subjectIdx = t.indexOf("Subject:", ignoreCase = true)
    if (subjectIdx != -1) {
        val subjectAndRest = t.substring(subjectIdx).trim()
        val lower = subjectAndRest.lowercase()
        val looksLikeEmail = lower.contains("dear ") || lower.contains("hi ") || 
                             lower.contains("sincerely") || lower.contains("regards") || 
                             lower.contains("respectfully") || lower.contains("thank you") || 
                             lower.contains("thanks") || lower.contains("leave")
        if (looksLikeEmail && subjectAndRest.length > 35) {
            val pre = t.substring(0, subjectIdx).trim()
            return Pair(if (pre.isNotBlank()) pre else null, subjectAndRest)
        }
    }

    // Pattern 3: Email starting with "Dear ..." or "To: ..."
    if (t.startsWith("To:", ignoreCase = true) || t.startsWith("Dear ", ignoreCase = true)) {
        val lower = t.lowercase()
        val looksLikeEmail = lower.contains("sincerely") || lower.contains("regards") || 
                             lower.contains("respectfully") || lower.contains("thank you")
        if (looksLikeEmail && t.length > 50) {
            return Pair(null, t)
        }
    }

    return null
}

@Composable
fun EmailDraftBox(
    draftText: String,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current

    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0xFF212121),
        border = BorderStroke(
            1.dp,
            Color(0xFF2E2E2E)
        ),
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header Bar with Copy button
            Surface(
                color = Color(0xFF282828),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 9.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Email,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Email Draft",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }

                    // ChatGPT style Copy Button
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = Color(0xFF383838),
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .clickable {
                                clipboardManager.setText(AnnotatedString(draftText))
                                Toast.makeText(context, "Email draft copied to clipboard", Toast.LENGTH_SHORT).show()
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.ContentCopy,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(13.dp)
                            )
                            Spacer(modifier = Modifier.width(5.dp))
                            Text(
                                text = "Copy",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                }
            }

            HorizontalDivider(
                color = Color(0xFF2E2E2E),
                thickness = 0.5.dp
            )

            // Draft Body
            Box(modifier = Modifier.padding(14.dp)) {
                MarkdownText(
                    text = draftText,
                    isUser = false
                )
            }
        }
    }
}

@Composable
fun ThinkingCard(
    thoughtText: String,
    isThinking: Boolean,
    isStreaming: Boolean
) {
    var userToggledState by remember { mutableStateOf<Boolean?>(null) }
    val isExpanded = userToggledState ?: (isThinking && isStreaming)

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E1E1E),
        border = BorderStroke(
            1.dp,
            Color(0xFF2E2E2E)
        ),
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 8.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        userToggledState = !isExpanded
                    },
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Psychology,
                    contentDescription = null,
                    tint = if (isThinking && isStreaming) Color(0xFF10A37F) else Color(0xFFB0B0B0),
                    modifier = Modifier.size(17.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = if (isThinking && isStreaming) "Thinking live..." else "Thought process",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = if (isThinking && isStreaming) Color(0xFF10A37F) else Color(0xFFB0B0B0)
                )
                if (isThinking && isStreaming) {
                    Spacer(modifier = Modifier.width(6.dp))
                    CircularProgressIndicator(
                        modifier = Modifier.size(10.dp),
                        strokeWidth = 1.5.dp,
                        color = Color(0xFF10A37F)
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                Text(
                    text = if (isExpanded) "Collapse" else "Expand",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF8E8E93),
                    modifier = Modifier.padding(end = 2.dp)
                )
                Icon(
                    imageVector = Icons.Default.ArrowDropDown,
                    contentDescription = if (isExpanded) "Collapse" else "Expand",
                    tint = Color(0xFF8E8E93),
                    modifier = Modifier
                        .size(18.dp)
                        .graphicsLayer(rotationZ = if (isExpanded) 180f else 0f)
                )
            }

            AnimatedVisibility(visible = isExpanded) {
                Column(modifier = Modifier.padding(top = 6.dp)) {
                    HorizontalDivider(
                        color = Color(0xFF2E2E2E),
                        thickness = 0.5.dp,
                        modifier = Modifier.padding(bottom = 6.dp)
                    )
                    Text(
                        text = thoughtText,
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp,
                            lineHeight = 16.sp
                        ),
                        color = Color(0xFFCCCCCC)
                    )
                }
            }
        }
    }
}

fun extractDomain(url: String): String {
    return try {
        val uri = Uri.parse(url)
        var host = uri.host ?: ""
        if (host.startsWith("www.")) {
            host = host.substring(4)
        }
        host
    } catch (_: Exception) {
        ""
    }
}

@Composable
fun ChatGptSurfaceButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: androidx.compose.ui.graphics.Shape = CircleShape,
    color: Color = Color.Transparent,
    border: BorderStroke? = null,
    shadowElevation: androidx.compose.ui.unit.Dp = 0.dp,
    content: @Composable () -> Unit
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.92f else 1f,
        animationSpec = tween(durationMillis = 80),
        label = "pressScale"
    )

    Box(
        modifier = modifier
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .clip(shape)
            .background(color)
            .then(if (border != null) Modifier.border(border, shape) else Modifier)
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                enabled = enabled,
                onClick = onClick
            ),
        contentAlignment = Alignment.Center
    ) {
        content()
    }
}

@Composable
fun DomainFaviconBadge(
    url: String,
    modifier: Modifier = Modifier,
    size: androidx.compose.ui.unit.Dp = 16.dp
) {
    val host = remember(url) {
        try { java.net.URI(url).host?.removePrefix("www.")?.lowercase() ?: "" } catch (_: Exception) { "" }
    }
    var faviconBmp by remember(url) { mutableStateOf(com.teja.gemmmobile.search.FaviconLoader.getCached(url)) }

    LaunchedEffect(url) {
        if (faviconBmp == null) {
            val bmp = com.teja.gemmmobile.search.FaviconLoader.loadFavicon(url)
            if (bmp != null) {
                faviconBmp = bmp
            }
        }
    }

    val isLinkedIn = host.contains("linkedin")
    val isGitHub = host.contains("github")
    val isWikipedia = host.contains("wikipedia")
    val isTwitter = host.contains("twitter") || host.contains("x.com")
    val isYoutube = host.contains("youtube") || host.contains("youtu.be")
    val isFacebook = host.contains("facebook") || host.contains("fb.com")
    val isInstagram = host.contains("instagram")
    val isSrm = host.contains("srm")

    val bg = when {
        isLinkedIn -> Color(0xFF0A66C2)
        isGitHub -> Color(0xFF24292E)
        isWikipedia -> Color(0xFF636466)
        isTwitter -> Color(0xFF1D9BF0)
        isYoutube -> Color(0xFFFF0000)
        isFacebook -> Color(0xFF1877F2)
        isInstagram -> Color(0xFFE1306C)
        isSrm -> Color(0xFF0F9D58)
        else -> Color(0xFF2A2A2E)
    }

    val label = when {
        isLinkedIn -> "in"
        isGitHub -> "gh"
        isWikipedia -> "W"
        isTwitter -> "𝕏"
        isYoutube -> "▶"
        isFacebook -> "f"
        isInstagram -> "📷"
        isSrm -> "S"
        host.isNotEmpty() -> host.first().uppercase()
        else -> "🌐"
    }

    // Circular favicon badge (exact ChatGPT style)
    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(if (faviconBmp != null) Color(0xFF1E1E22) else bg),
        contentAlignment = Alignment.Center
    ) {
        val bmp = faviconBmp
        if (bmp != null) {
            androidx.compose.foundation.Image(
                bitmap = bmp.asImageBitmap(),
                contentDescription = host,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(1.dp)
                    .clip(CircleShape),
                contentScale = androidx.compose.ui.layout.ContentScale.Fit
            )
        } else {
            Text(
                text = label,
                fontSize = (size.value * 0.52f).sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }
    }
}

/**
 * Data structure for rich interactive profile cards (LinkedIn, GitHub, Portfolio).
 */
data class ProfileCardData(
    val title: String,
    val subtitle: String,
    val url: String,
    val brand: String,
    val iconColor: Color,
    val badgeLetter: String
)

fun extractProfileCards(results: List<SearchResult>): List<ProfileCardData> {
    val cards = mutableListOf<ProfileCardData>()
    for (res in results) {
        val url = res.url.lowercase()
        val title = res.title
        when {
            url.contains("linkedin.com/in/") || url.contains("linkedin.com/posts/") -> {
                val isPost = url.contains("/posts/")
                val cleanName = title.substringBefore("-").substringBefore("|").substringBefore("·").trim()
                cards.add(
                    ProfileCardData(
                        title = if (cleanName.isNotBlank() && cleanName.length < 35) cleanName else "LinkedIn Profile",
                        subtitle = if (isPost) "LinkedIn Activity" else "LinkedIn Profile • in.linkedin.com",
                        url = res.url,
                        brand = "LinkedIn",
                        iconColor = Color(0xFF0A66C2),
                        badgeLetter = "in"
                    )
                )
            }
            url.contains("github.com/") && !url.contains("/issues") && !url.contains("/pull") -> {
                val cleanTitle = title.substringBefore("-").substringBefore("|").trim()
                cards.add(
                    ProfileCardData(
                        title = cleanTitle.ifBlank { "GitHub Profile" },
                        subtitle = "GitHub • Code & Projects",
                        url = res.url,
                        brand = "GitHub",
                        iconColor = Color(0xFF8B5CF6),
                        badgeLetter = "gh"
                    )
                )
            }
            url.contains("twitter.com/") || url.contains("x.com/") -> {
                val handle = url.substringAfter("twitter.com/").substringAfter("x.com/").substringBefore("/").substringBefore("?").trim()
                val cleanTitle = title.substringBefore("-").substringBefore("|").trim()
                cards.add(
                    ProfileCardData(
                        title = cleanTitle.ifBlank { "@$handle" },
                        subtitle = "X (Twitter) • Profile",
                        url = res.url,
                        brand = "X",
                        iconColor = Color(0xFF1D9BF0),
                        badgeLetter = "𝕏"
                    )
                )
            }
            url.contains("youtube.com/") || url.contains("youtu.be/") -> {
                val cleanTitle = title.substringBefore("-").substringBefore("|").trim()
                cards.add(
                    ProfileCardData(
                        title = cleanTitle.ifBlank { "YouTube Channel" },
                        subtitle = "YouTube • Media",
                        url = res.url,
                        brand = "YouTube",
                        iconColor = Color(0xFFFF0000),
                        badgeLetter = "▶"
                    )
                )
            }
            url.contains("huggingface.co/") -> {
                val cleanTitle = title.substringBefore("-").substringBefore("(").trim()
                cards.add(
                    ProfileCardData(
                        title = cleanTitle.ifBlank { "Hugging Face" },
                        subtitle = "Hugging Face • Models & Profile",
                        url = res.url,
                        brand = "Hugging Face",
                        iconColor = Color(0xFFFFD21E),
                        badgeLetter = "🤗"
                    )
                )
            }
            url.contains("srmist.edu") || url.contains("srmap.edu") || title.contains("SRM University", ignoreCase = true) -> {
                cards.add(
                    ProfileCardData(
                        title = "SRM University-AP",
                        subtitle = "Academic Portal & University",
                        url = res.url,
                        brand = "SRM",
                        iconColor = Color(0xFF0F9D58),
                        badgeLetter = "S"
                    )
                )
            }
        }
    }
    return cards.distinctBy { it.brand }.take(3)
}

@Composable
fun ProfileAvatarBadge(
    url: String,
    brand: String,
    modifier: Modifier = Modifier,
    size: androidx.compose.ui.unit.Dp = 38.dp
) {
    var avatarBmp by remember(url) {
        mutableStateOf(ProfileAvatarLoader.getCached(url))
    }

    LaunchedEffect(url) {
        if (avatarBmp == null) {
            val bmp = ProfileAvatarLoader.loadAvatar(url)
            if (bmp != null) {
                avatarBmp = bmp
            }
        }
    }

    Box(
        modifier = modifier.size(size),
        contentAlignment = Alignment.Center
    ) {
        val currentBmp = avatarBmp
        if (currentBmp != null) {
            androidx.compose.foundation.Image(
                bitmap = currentBmp.asImageBitmap(),
                contentDescription = brand,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxSize()
                    .clip(CircleShape)
                    .border(1.dp, Color(0x33FFFFFF), CircleShape)
            )
            // Tiny bottom-right corner brand badge
            Box(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .offset(x = 2.dp, y = 2.dp)
                    .size(13.dp)
                    .clip(CircleShape)
                    .background(Color(0xFF18181B))
                    .border(0.8.dp, Color(0xFF3E3E48), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                DomainFaviconBadge(
                    url = url,
                    size = 10.dp
                )
            }
        } else {
            DomainFaviconBadge(
                url = url,
                size = size
            )
        }
    }
}

@Composable
fun ProfileCardsRow(
    cards: List<ProfileCardData>,
    modifier: Modifier = Modifier
) {
    if (cards.isEmpty()) return
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(top = 8.dp, bottom = 4.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Text(
            text = "PROFILES & LINKS",
            style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
            fontWeight = FontWeight.Bold,
            color = Color(0xFF8E8E93),
            letterSpacing = 0.5.sp
        )
        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(cards) { card ->
                Surface(
                    shape = RoundedCornerShape(13.dp),
                    color = Color(0xFF1E1E22),
                    border = BorderStroke(1.dp, Color(0xFF323238)),
                    modifier = Modifier
                        .clip(RoundedCornerShape(13.dp))
                        .clickable {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            try {
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(card.url))
                                context.startActivity(intent)
                            } catch (_: Exception) {}
                        }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        ProfileAvatarBadge(
                            url = card.url,
                            brand = card.brand,
                            size = 38.dp
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = card.title,
                                style = MaterialTheme.typography.bodyMedium.copy(fontSize = 12.5.sp),
                                fontWeight = FontWeight.SemiBold,
                                color = Color.White,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            Text(
                                text = card.subtitle,
                                style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                color = Color(0xFF9E9EA4),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        Spacer(modifier = Modifier.width(10.dp))
                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = Color(0xFF2C2C32),
                            border = BorderStroke(0.8.dp, Color(0xFF44444C))
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.5.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Open profile",
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                    fontWeight = FontWeight.Medium,
                                    color = Color(0xFFE2E2E8)
                                )
                                Spacer(modifier = Modifier.width(3.dp))
                                Icon(
                                    imageVector = Icons.Default.ArrowUpward,
                                    contentDescription = "Open",
                                    tint = Color(0xFF10A37F),
                                    modifier = Modifier
                                        .size(10.dp)
                                        .graphicsLayer { rotationZ = 45f }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChatGptSearchingWebPill() {
    val infiniteTransition = rememberInfiniteTransition(label = "pulseGlobe")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.45f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(650),
            repeatMode = RepeatMode.Reverse
        ),
        label = "globeAlpha"
    )

    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0xFF1B1B1E),
        border = BorderStroke(1.dp, Color(0xFF2C2C30)),
        modifier = Modifier.padding(vertical = 2.dp)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.Language,
                contentDescription = null,
                tint = Color(0xFF10A37F),
                modifier = Modifier
                    .size(14.dp)
                    .graphicsLayer { this.alpha = alpha }
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "Searching the web…",
                style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.5.sp),
                fontWeight = FontWeight.Medium,
                color = Color(0xFFD1D1D6)
            )
        }
    }
}

@Composable
fun ChatGptSearchedSitesPill(
    searchResults: List<SearchResult>
) {
    var expanded by remember { mutableStateOf(false) }
    val context = LocalContext.current

    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0xFF1A1A1D),
        border = BorderStroke(1.dp, Color(0xFF2B2B30)),
        modifier = Modifier
            .clip(RoundedCornerShape(14.dp))
            .clickable { expanded = !expanded }
            .padding(vertical = 2.dp)
    ) {
        Column(
            modifier = Modifier.animateContentSize(tween(180))
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Circular domain favicons row (overlapping like ChatGPT)
                val topFavicons = searchResults.take(3)
                if (topFavicons.isNotEmpty()) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(end = 4.dp)
                    ) {
                        topFavicons.forEachIndexed { index, res ->
                            Box(
                                modifier = Modifier
                                    .offset(x = (-3 * index).dp)
                                    .clip(CircleShape)
                                    .border(1.dp, Color(0xFF1A1A1D), CircleShape)
                            ) {
                                DomainFaviconBadge(url = res.url, size = 15.dp)
                            }
                        }
                    }
                } else {
                    Icon(
                        imageVector = Icons.Default.Language,
                        contentDescription = null,
                        tint = Color(0xFF10A37F),
                        modifier = Modifier.size(14.dp)
                    )
                }
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = "Searched ${searchResults.size} sites",
                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.5.sp),
                    fontWeight = FontWeight.Medium,
                    color = Color(0xFFE2E2E6)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Icon(
                    imageVector = if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    tint = Color(0xFF8E8E93),
                    modifier = Modifier.size(15.dp)
                )
            }
            if (expanded) {
                HorizontalDivider(color = Color(0xFF26262A), thickness = 0.8.dp)
                Column(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    for (res in searchResults) {
                        val host = remember(res.url) { extractDomain(res.url) }
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .clickable {
                                    try {
                                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(res.url))
                                        context.startActivity(intent)
                                    } catch (_: Exception) {}
                                }
                                .padding(horizontal = 6.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            DomainFaviconBadge(url = res.url, size = 18.dp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = host.ifBlank { res.title },
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp),
                                    color = Color.White,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                                if (res.title.isNotBlank()) {
                                    Text(
                                        text = res.title,
                                        style = MaterialTheme.typography.bodySmall.copy(fontSize = 10.sp),
                                        color = Color(0xFF8E8E93),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.width(4.dp))
                            Icon(
                                imageVector = Icons.Default.Language,
                                contentDescription = "Open",
                                tint = Color(0xFF8E8E93),
                                modifier = Modifier.size(12.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChatGptSourcesPill(
    searchResults: List<SearchResult>,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0xFF1E1E1E),
        border = BorderStroke(1.dp, Color(0xFF2E2E2E)),
        modifier = Modifier
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            val topSources = searchResults.take(3)
            for (res in topSources) {
                DomainFaviconBadge(url = res.url)
            }
            Spacer(modifier = Modifier.width(2.dp))
            Text(
                text = "Sources",
                style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.5.sp),
                fontWeight = FontWeight.Medium,
                color = Color(0xFFD1D1D6)
            )
        }
    }
}

// ==========================================
// ChatGPT-Style Web Search Images & Carousel
// ==========================================

@Composable
fun SearchImagesCarousel(
    images: List<SearchImage>,
    onImageClick: (SearchImage) -> Unit
) {
    if (images.isEmpty()) return
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(bottom = 6.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Image,
                contentDescription = null,
                tint = Color(0xFF9E9EA4),
                modifier = Modifier.size(13.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "Images (${images.size})",
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFF9E9EA4)
            )
        }

        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = PaddingValues(vertical = 2.dp)
        ) {
            items(images) { img ->
                SearchImageThumbnail(
                    image = img,
                    onClick = { onImageClick(img) }
                )
            }
        }
    }
}

@Composable
fun SearchImageThumbnail(
    image: SearchImage,
    onClick: () -> Unit
) {
    var thumbBitmap by remember(image.imageUrl) {
        mutableStateOf<Bitmap?>(ProfileAvatarLoader.getCachedImage(image.imageUrl))
    }
    LaunchedEffect(image.imageUrl) {
        if (thumbBitmap == null) {
            withContext(Dispatchers.IO) {
                val bmp = ProfileAvatarLoader.loadImage(image.imageUrl)
                thumbBitmap = bmp
            }
        }
    }

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF212124),
        border = BorderStroke(0.8.dp, Color(0xFF323238)),
        modifier = Modifier
            .width(155.dp)
            .height(105.dp)
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
            if (thumbBitmap != null) {
                androidx.compose.foundation.Image(
                    bitmap = thumbBitmap!!.asImageBitmap(),
                    contentDescription = image.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize()
                )
            } else {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(
                        color = Color(0xFF555558),
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }

            // Bottom gradient overlay with source domain
            Box(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            listOf(Color.Transparent, Color(0xCC000000))
                        )
                    )
                    .padding(horizontal = 6.dp, vertical = 4.dp)
            ) {
                val domain = remember(image.sourceDomain, image.sourceUrl) {
                    image.sourceDomain.ifBlank { extractDomain(image.sourceUrl) }
                }
                Text(
                    text = domain.ifBlank { image.title },
                    color = Color.White,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

// ==========================================
// In-App Image Preview Dialog (ChatGPT Style)
// ==========================================

@Composable
fun InAppImagePreviewDialog(
    image: SearchImage,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    var fullBitmap by remember(image.imageUrl) {
        mutableStateOf<Bitmap?>(ProfileAvatarLoader.getCachedImage(image.imageUrl))
    }
    var isLoading by remember(image.imageUrl) { mutableStateOf(fullBitmap == null) }

    LaunchedEffect(image.imageUrl) {
        if (fullBitmap == null) {
            withContext(Dispatchers.IO) {
                val bmp = ProfileAvatarLoader.downloadBitmap(image.imageUrl, maxDimension = 1280)
                fullBitmap = bmp
                isLoading = false
            }
        }
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            dismissOnBackPress = true,
            dismissOnClickOutside = true
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF0F0F11))
                .statusBarsPadding()
                .navigationBarsPadding()
        ) {
            // Top Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier
                        .size(36.dp)
                        .background(Color(0xFF212124), CircleShape)
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close preview",
                        tint = Color.White,
                        modifier = Modifier.size(18.dp)
                    )
                }

                val domain = remember(image.sourceUrl, image.sourceDomain) {
                    image.sourceDomain.ifBlank { extractDomain(image.sourceUrl) }
                }
                if (domain.isNotBlank()) {
                    Surface(
                        shape = RoundedCornerShape(16.dp),
                        color = Color(0xFF212124),
                        border = BorderStroke(0.8.dp, Color(0xFF333336))
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            DomainFaviconBadge(url = image.sourceUrl, size = 16.dp)
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = domain,
                                color = Color.White,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
            }

            // Image Content
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(top = 64.dp, bottom = 90.dp, start = 12.dp, end = 12.dp),
                contentAlignment = Alignment.Center
            ) {
                if (fullBitmap != null) {
                    androidx.compose.foundation.Image(
                        bitmap = fullBitmap!!.asImageBitmap(),
                        contentDescription = image.title,
                        contentScale = ContentScale.Fit,
                        modifier = Modifier
                            .fillMaxSize()
                            .clip(RoundedCornerShape(12.dp))
                    )
                } else if (isLoading) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        CircularProgressIndicator(
                            color = Color.White,
                            strokeWidth = 2.5.dp,
                            modifier = Modifier.size(36.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "Loading high-resolution image...",
                            color = Color(0xFF8E8E93),
                            fontSize = 13.sp
                        )
                    }
                } else {
                    Text(
                        text = "Unable to load preview",
                        color = Color(0xFF8E8E93),
                        fontSize = 13.sp
                    )
                }
            }

            // Bottom Caption Bar
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(Color(0xFF18181A))
                    .padding(horizontal = 20.dp, vertical = 14.dp)
            ) {
                if (image.title.isNotBlank()) {
                    Text(
                        text = image.title,
                        color = Color.White,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                }
                if (image.sourceUrl.isNotBlank()) {
                    Text(
                        text = image.sourceUrl,
                        color = Color(0xFF8E8E93),
                        fontSize = 11.5.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

// ==========================================
// ChatGPT Sources ModalBottomSheet
// Matching media_1791441433580.jpg AMOLED overlay
// ==========================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SourcesBottomSheet(
    visible: Boolean,
    searchResults: List<SearchResult>,
    onDismiss: () -> Unit
) {
    if (!visible) return
    val context = LocalContext.current
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = Color(0xFF212124),
        dragHandle = {
            BottomSheetDefaults.DragHandle(
                color = Color(0xFF555558),
                width = 36.dp,
                height = 4.dp
            )
        },
        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
        ) {
            // Header: "Sources" with Close Button
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Sources",
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                    fontSize = 18.sp
                )
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.size(32.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close",
                        tint = Color(0xFF8E8E93),
                        modifier = Modifier.size(18.dp)
                    )
                }
            }

            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                val primary = searchResults.firstOrNull()
                if (primary != null) {
                    item {
                        val primaryDomain = remember(primary.url) { extractDomain(primary.url).ifBlank { primary.title } }
                        Surface(
                            shape = RoundedCornerShape(14.dp),
                            color = Color(0xFF2A2A2E),
                            border = BorderStroke(0.8.dp, Color(0xFF38383E)),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .clickable {
                                    try {
                                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(primary.url))
                                        context.startActivity(intent)
                                    } catch (_: Exception) {}
                                }
                        ) {
                            Column(
                                modifier = Modifier.padding(14.dp)
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    DomainFaviconBadge(url = primary.url, size = 22.dp)
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = primaryDomain,
                                        color = Color(0xFF9E9EA4),
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Medium,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = primary.title.ifBlank { primaryDomain },
                                    fontWeight = FontWeight.SemiBold,
                                    color = Color.White,
                                    fontSize = 14.5.sp,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                                if (primary.snippet.isNotBlank()) {
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        text = primary.snippet,
                                        color = Color(0xFFB0B0B8),
                                        fontSize = 12.5.sp,
                                        lineHeight = 17.sp,
                                        maxLines = 3,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                            }
                        }
                    }
                }

                val moreResults = if (searchResults.size > 1) searchResults.drop(1) else emptyList()
                if (moreResults.isNotEmpty()) {
                    item {
                        HorizontalDivider(
                            color = Color(0xFF333338),
                            thickness = 0.6.dp,
                            modifier = Modifier.padding(vertical = 4.dp)
                        )
                        Text(
                            text = "More",
                            color = Color(0xFF8E8E93),
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(start = 4.dp, top = 2.dp, bottom = 4.dp)
                        )
                    }

                    items(moreResults) { res ->
                        val domain = remember(res.url) { extractDomain(res.url).ifBlank { res.title } }
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFF242427),
                            border = BorderStroke(0.6.dp, Color(0xFF303036)),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .clickable {
                                    try {
                                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(res.url))
                                        context.startActivity(intent)
                                    } catch (_: Exception) {}
                                }
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.Top
                            ) {
                                DomainFaviconBadge(url = res.url, size = 20.dp)
                                Spacer(modifier = Modifier.width(10.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = domain,
                                        color = Color(0xFF8E8E93),
                                        fontSize = 11.5.sp,
                                        fontWeight = FontWeight.Medium
                                    )
                                    Text(
                                        text = res.title.ifBlank { domain },
                                        fontWeight = FontWeight.SemiBold,
                                        color = Color.White,
                                        fontSize = 13.sp,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis,
                                        modifier = Modifier.padding(top = 2.dp)
                                    )
                                    if (res.snippet.isNotBlank()) {
                                        Text(
                                            text = res.snippet,
                                            color = Color(0xFF9E9EA4),
                                            fontSize = 11.5.sp,
                                            maxLines = 2,
                                            overflow = TextOverflow.Ellipsis,
                                            modifier = Modifier.padding(top = 3.dp)
                                        )
                                    }
                                }
                            }
                        }
                    }
                }

                item {
                    Spacer(modifier = Modifier.height(20.dp))
                }
            }
        }
    }
}

private enum class ActionButtonState {
    MIC,
    SEND,
    STOP
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun ChatInputBar(
    inputText: String,
    onTextChanged: (String) -> Unit,
    onSend: () -> Unit,
    onStop: () -> Unit,
    isGenerating: Boolean,
    isWebSearchEnabled: Boolean,
    onToggleWebSearch: () -> Unit,
    isEnabled: Boolean,
    onVoiceInput: () -> Unit = {},
    onVoiceAssistant: () -> Unit = {},
    onAttach: () -> Unit = {},
    hasAttachment: Boolean = false
) {
    val focusManager = LocalFocusManager.current
    val isImeVisible = WindowInsets.isImeVisible

    // Whenever keyboard is closed/dismissed, clear focus so cursor and text field reset completely
    LaunchedEffect(isImeVisible) {
        if (!isImeVisible) {
            focusManager.clearFocus()
        }
    }

    // Expand ONLY when keyboard is open (isImeVisible). When closed, returns to normal 80% floating bar.
    val isExpanded = isImeVisible

    // ChatGPT mobile signature floating island behavior:
    // When idle / keyboard closed: ~80% width with 34.dp margins, floating 12.dp above nav bar.
    // When keyboard open: smoothly expands to ~94% width with 10.dp margins, docking right above keyboard.
    val horizontalPadding by animateDpAsState(
        targetValue = if (isExpanded) 10.dp else 34.dp,
        animationSpec = spring(
            dampingRatio = 0.82f,
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "inputHorizontalPadding"
    )

    val bottomPadding by animateDpAsState(
        targetValue = if (isExpanded) 4.dp else 12.dp,
        animationSpec = spring(
            dampingRatio = 0.82f,
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "inputBottomPadding"
    )

    // Floating Pill Island Container (ChatGPT AMOLED pure dark style)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .then(
                if (!isImeVisible) Modifier.navigationBarsPadding() else Modifier
            )
            .padding(start = horizontalPadding, end = horizontalPadding, top = 2.dp, bottom = bottomPadding),
        contentAlignment = Alignment.Center
    ) {
        Surface(
            shape = RoundedCornerShape(32.dp),
            color = Color(0xFF212121),
            border = BorderStroke(1.dp, Color(0xFF2C2C2C)),
            shadowElevation = 6.dp,
            modifier = Modifier
                .fillMaxWidth()
                .animateContentSize(
                    animationSpec = tween(durationMillis = 150)
                )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 6.dp, vertical = 6.dp),
                verticalAlignment = Alignment.Bottom
            ) {
                // 1. Left Plus (+) Action Button
                ChatGptSurfaceButton(
                    onClick = onAttach,
                    shape = CircleShape,
                    color = Color(0xFF2E2E2E),
                    modifier = Modifier
                        .size(38.dp)
                        .padding(2.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = "Add attachment",
                        modifier = Modifier.size(20.dp),
                        tint = Color.White
                    )
                }

                Spacer(modifier = Modifier.width(4.dp))

                // 2. Center Text & Tools Section
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Web Search Toggle inside the bar
                    if (isWebSearchEnabled) {
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFF10A37F).copy(alpha = 0.2f),
                            border = BorderStroke(1.dp, Color(0xFF10A37F).copy(alpha = 0.4f)),
                            modifier = Modifier
                                .height(28.dp)
                                .padding(end = 6.dp)
                                .clip(RoundedCornerShape(12.dp))
                                .clickable { onToggleWebSearch() }
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 7.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Language,
                                    contentDescription = "Search the web",
                                    modifier = Modifier.size(13.dp),
                                    tint = Color(0xFF10A37F)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = "Web",
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp),
                                    fontWeight = FontWeight.SemiBold,
                                    color = Color(0xFF10A37F)
                                )
                            }
                        }
                    }

                    // Multi-line Expanding BasicTextField with focus listener
                    BasicTextField(
                        value = inputText,
                        onValueChange = onTextChanged,
                        enabled = isEnabled && !isGenerating,
                        textStyle = TextStyle(
                            fontSize = 15.5.sp,
                            color = Color.White,
                            lineHeight = 21.sp,
                            fontFamily = FontFamily.Default
                        ),
                        cursorBrush = SolidColor(Color.White),
                        maxLines = 6,
                        modifier = Modifier
                            .weight(1f)
                            .padding(horizontal = 4.dp, vertical = 4.dp),
                        decorationBox = { innerTextField ->
                            Box(
                                modifier = Modifier.fillMaxWidth(),
                                contentAlignment = Alignment.CenterStart
                            ) {
                                if (inputText.isEmpty()) {
                                    Text(
                                        text = when {
                                            isWebSearchEnabled -> "Search with Gemma..."
                                            hasAttachment -> "Ask about this..."
                                            else -> "Ask Gemma..."
                                        },
                                        style = MaterialTheme.typography.bodyMedium.copy(
                                            fontSize = 15.5.sp,
                                            color = Color(0xFF8E8E93)
                                        )
                                    )
                                }
                                innerTextField()
                            }
                        }
                    )
                }

                Spacer(modifier = Modifier.width(4.dp))

                // 3. Right Animated Action Button (Mic/Voice ⇄ Send ⇄ Stop)
                AnimatedContent(
                    targetState = when {
                        isGenerating -> ActionButtonState.STOP
                        inputText.isNotBlank() || hasAttachment -> ActionButtonState.SEND
                        else -> ActionButtonState.MIC
                    },
                    transitionSpec = {
                        (scaleIn(tween(140)) + fadeIn(tween(140)))
                            .togetherWith(scaleOut(tween(110)) + fadeOut(tween(110)))
                    },
                    label = "chatActionTransition"
                ) { state ->
                    when (state) {
                        ActionButtonState.STOP -> {
                            // Coral Pink Circle with White Stop Square
                            ChatGptSurfaceButton(
                                onClick = onStop,
                                shape = CircleShape,
                                color = Color(0xFFF43F5E),
                                modifier = Modifier
                                    .size(38.dp)
                                    .padding(2.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Stop,
                                    contentDescription = "Stop generating",
                                    tint = Color.White,
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        }

                        ActionButtonState.SEND -> {
                            // Solid White Circle with Crisp Black Up Arrow
                            val canSend = isEnabled && !isGenerating
                            ChatGptSurfaceButton(
                                onClick = onSend,
                                enabled = canSend,
                                shape = CircleShape,
                                color = if (canSend) Color.White else Color(0xFF3A3A3C),
                                modifier = Modifier
                                    .size(38.dp)
                                    .padding(2.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.ArrowUpward,
                                    contentDescription = "Send",
                                    tint = if (canSend) Color.Black else Color(0xFF8E8E93),
                                    modifier = Modifier.size(19.dp)
                                )
                            }
                        }

                        ActionButtonState.MIC -> {
                            // ChatGPT Layout: White Mic icon + Coral Pink circular Voice Assistant soundwave button
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                ChatGptSurfaceButton(
                                    onClick = onVoiceInput,
                                    shape = CircleShape,
                                    color = Color.Transparent,
                                    modifier = Modifier.size(36.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Mic,
                                        contentDescription = "Voice input",
                                        tint = Color.White,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }

                                ChatGptSurfaceButton(
                                    onClick = onVoiceAssistant,
                                    shape = CircleShape,
                                    color = Color(0xFFF43F5E),
                                    modifier = Modifier
                                        .size(38.dp)
                                        .padding(2.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.GraphicEq,
                                        contentDescription = "Voice assistant",
                                        tint = Color.White,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun FloatingMenuItem(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color.Transparent,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(14.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = Color.White
            )
        }
    }
}

@Composable
fun FloatingMenuItemWithToggle(
    icon: ImageVector,
    label: String,
    isChecked: Boolean,
    onToggle: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color.Transparent,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onToggle)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = if (isChecked) Color(0xFF10A37F) else Color.White,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(14.dp))
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    color = if (isChecked) Color(0xFF10A37F) else Color.White
                )
            }
            Switch(
                checked = isChecked,
                onCheckedChange = { onToggle() },
                colors = SwitchDefaults.colors(
                    checkedThumbColor = Color.White,
                    checkedTrackColor = Color(0xFF10A37F),
                    uncheckedThumbColor = Color(0xFF8E8E93),
                    uncheckedTrackColor = Color(0xFF383838)
                ),
                modifier = Modifier.graphicsLayer(scaleX = 0.8f, scaleY = 0.8f)
            )
        }
    }
}

@Composable
fun AttachmentDialog(
    onDismiss: () -> Unit,
    onTakePhoto: () -> Unit,
    onPickImage: () -> Unit,
    onPickDocument: () -> Unit,
    isWebSearchEnabled: Boolean = false,
    onToggleWebSearch: () -> Unit = {}
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Color(0xFF212121),
        title = { Text("Add to chat", fontWeight = FontWeight.Bold, color = Color.White) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                AttachOption(emoji = "📷", label = "Camera", desc = "Take a photo for Gemma to examine") {
                    onTakePhoto(); onDismiss()
                }
                AttachOption(emoji = "🖼️", label = "Photos", desc = "Choose an image from gallery") {
                    onPickImage(); onDismiss()
                }
                AttachOption(emoji = "📄", label = "Document", desc = "Attach PDF or text document") {
                    onPickDocument(); onDismiss()
                }
                AttachOption(
                    emoji = "🌐",
                    label = if (isWebSearchEnabled) "Web Search (Active)" else "Web Search",
                    desc = if (isWebSearchEnabled) "Web search is currently ON — tap to disable" else "Search live web for real-time information"
                ) {
                    onToggleWebSearch(); onDismiss()
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel", color = Color.White) }
        }
    )
}

@Composable
private fun AttachOption(
    emoji: String,
    label: String,
    desc: String,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF2E2E2E),
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(emoji, fontSize = 22.sp)
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, color = Color.White)
                Text(desc, style = MaterialTheme.typography.bodySmall, color = Color(0xFF8E8E93))
            }
        }
    }
}


@Composable
fun ModelManagementSection(
    installState: ModelInstallState,
    onImportClick: () -> Unit,
    onRetryCheck: () -> Unit,
    viewModel: ChatViewModel
) {
    val hfToken by viewModel.hfToken.collectAsState()
    var tokenInput by remember(hfToken) { mutableStateOf(hfToken) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
            )
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Gemma 4 E2B IT",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "100% Local On-Device AI • 2.58 GB",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                val availableBytes = viewModel.modelManager.getAvailableStorageBytes()
                if (availableBytes > 0) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Available Storage: ${viewModel.modelManager.formatSize(availableBytes)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                when (installState) {
                    is ModelInstallState.Installing -> {
                        Column(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            LinearProgressIndicator(
                                progress = { installState.progress },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(10.dp)
                                    .clip(RoundedCornerShape(5.dp))
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            val pct = (installState.progress * 100).toInt()
                            Text(
                                text = "Downloading to App Storage... $pct%",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "${viewModel.modelManager.formatSize(installState.transferredBytes)} / ${viewModel.modelManager.formatSize(installState.totalBytes)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.outline
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            OutlinedButton(
                                onClick = { viewModel.cancelDownload() },
                                colors = ButtonDefaults.outlinedButtonColors(
                                    contentColor = MaterialTheme.colorScheme.error
                                )
                            ) {
                                Text("Cancel Download")
                            }
                        }
                    }

                    is ModelInstallState.Checking -> {
                        CircularProgressIndicator(modifier = Modifier.size(32.dp))
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(text = installState.message, style = MaterialTheme.typography.bodySmall)
                    }

                    else -> {
                        // Direct In-App Download UI
                        OutlinedTextField(
                            value = tokenInput,
                            onValueChange = {
                                tokenInput = it
                                viewModel.onHfTokenChanged(it)
                            },
                            label = { Text("Hugging Face Access Token") },
                            placeholder = { Text("hf_...") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp),
                            textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace)
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "Token saved locally in app for authorized direct download",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.outline
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                viewModel.onHfTokenChanged(tokenInput)
                                viewModel.downloadModel()
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(
                                text = "⚡ Download Model Directly in App",
                                fontWeight = FontWeight.Bold,
                                fontSize = 15.sp
                            )
                        }

                        Spacer(modifier = Modifier.height(10.dp))

                        FilledTonalButton(
                            onClick = onImportClick,
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("Import Model from File Picker (SAF)")
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedButton(
                    onClick = onRetryCheck,
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("Check Model Status")
                }
            }
        }
    }
}

@Composable
fun ModelReadySection(
    installState: ModelInstallState.Installed,
    onStartChat: () -> Unit,
    onDeleteModel: () -> Unit,
    onOpenConfig: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
            )
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Gemma 4 E2B",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "✓ Gemma 4 E2B Installed in App",
                        style = MaterialTheme.typography.bodyLarge,
                        color = Color(0xFF2E7D32),
                        fontWeight = FontWeight.Bold
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Location: Internal Storage (${installState.modelFile.name})",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline
                )

                Spacer(modifier = Modifier.height(24.dp))

                Button(
                    onClick = onStartChat,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    Text(
                        text = "Start Chat",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedButton(
                    onClick = onOpenConfig,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("⚙️ Adjust Parameters (temp, tokens, top-p, etc.)")
                }

                Spacer(modifier = Modifier.height(8.dp))

                TextButton(
                    onClick = onDeleteModel
                ) {
                    Text(
                        text = "Delete & Re-download",
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}

/**
 * Intelligent ChatGPT-style follow-up suggestion extractor.
 * Detects cut-off responses, parses Gemma's proactive questions/options,
 * and adds context-aware prompt chips.
 */
fun extractFollowUpSuggestions(text: String): List<String> {
    val trimmed = text.trim()
    if (trimmed.isBlank()) return emptyList()

    val suggestions = mutableListOf<String>()

    val seemsCutOff = !trimmed.endsWith(".") && !trimmed.endsWith("?") &&
            !trimmed.endsWith("!") && !trimmed.endsWith("```") &&
            !trimmed.endsWith("\"") && !trimmed.endsWith(")") &&
            !trimmed.endsWith(":") && trimmed.length > 50

    if (seemsCutOff) {
        suggestions.add("Continue generating")
    }

    // Try extracting from explicit closing questions:
    // e.g. "Would you like to explore Supervised Learning next, or see a hands-on Python example?"
    val lastQuestionMatch = Regex(
        """(?:Would you like to|Do you want to|Should we)\s+([^?\n]+)\?""",
        RegexOption.IGNORE_CASE
    ).findAll(trimmed).lastOrNull()

    if (lastQuestionMatch != null) {
        val questionBody = lastQuestionMatch.groupValues[1].trim()
        if (questionBody.contains(" or ", ignoreCase = true)) {
            val parts = questionBody.split(Regex("""\s+or\s+""", RegexOption.IGNORE_CASE))
            for (p in parts) {
                val cleaned = p.replace(Regex("""^(explore|learn about|see|check out)\s+""", RegexOption.IGNORE_CASE), "")
                    .replace(Regex("""\s+next$""", RegexOption.IGNORE_CASE), "")
                    .replace(Regex("""[*_`"]"""), "")
                    .trim()
                if (cleaned.isNotBlank() && cleaned.length in 3..40) {
                    suggestions.add(cleaned.replaceFirstChar { it.uppercase() })
                }
            }
        } else {
            val cleaned = questionBody.replace(Regex("""[*_`"]"""), "").trim()
            if (cleaned.isNotBlank() && cleaned.length in 4..45) {
                suggestions.add(cleaned.replaceFirstChar { it.uppercase() })
            }
        }
    }

    // Context-aware defaults based on topic if fewer than 3 suggestions
    val lower = trimmed.lowercase()
    if (lower.contains("machine learning") || lower.contains("deep learning") || lower.contains("supervised learning")) {
        if (!suggestions.any { it.contains("supervised", ignoreCase = true) }) {
            suggestions.add("Explain Supervised Learning")
        }
        if (!suggestions.any { it.contains("example", ignoreCase = true) }) {
            suggestions.add("Practical Python example")
        }
    } else if (lower.contains("python") || lower.contains("kotlin") || lower.contains("java") || lower.contains("```")) {
        if (!suggestions.any { it.contains("code", ignoreCase = true) }) {
            suggestions.add("Explain how this code works")
        }
        if (!suggestions.any { it.contains("error", ignoreCase = true) }) {
            suggestions.add("Add error handling & tests")
        }
    }

    // Standard high-value ChatGPT-style follow-up actions
    val fallbacks = listOf(
        "Explain in simpler terms",
        "Give real-world examples",
        "Summarize key takeaways"
    )
    for (f in fallbacks) {
        if (suggestions.size >= 4) break
        if (!suggestions.any { it.equals(f, ignoreCase = true) }) {
            suggestions.add(f)
        }
    }

    return suggestions.distinct().take(4)
}

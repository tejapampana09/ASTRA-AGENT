package com.teja.gemmmobile.ui

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import com.teja.gemmmobile.ocr.DocumentOcrHelper
import com.teja.gemmmobile.ocr.ExtractedDocument
import com.teja.gemmmobile.search.SearchResult
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
import com.teja.gemmmobile.assistant.WhatsAppAction
import com.teja.gemmmobile.assistant.WhatsAppStatus
import com.teja.gemmmobile.assistant.WhatsAppActionCard
import com.teja.gemmmobile.assistant.ContactMatch
import com.teja.gemmmobile.assistant.CallAction
import com.teja.gemmmobile.assistant.CallActionCard
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.runtime.derivedStateOf
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.DriveFileRenameOutline
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.KeyboardArrowDown
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
import androidx.compose.material.icons.filled.VolumeUp
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
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.text.style.TextOverflow
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

@OptIn(ExperimentalMaterial3Api::class)
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
    val isWebSearchEnabled by viewModel.isWebSearchEnabled.collectAsState()

    var showConfigDialog by remember { mutableStateOf(false) }
    var showMemoryDialog by remember { mutableStateOf(false) }
    var showDeleteConfirmDialog by remember { mutableStateOf(false) }
    var showRenameDialog by remember { mutableStateOf(false) }
    var renameText by remember { mutableStateOf("") }
    var showAttachmentDialog by remember { mutableStateOf(false) }
    var isOcrProcessing by remember { mutableStateOf(false) }
    var editingMessageId by remember { mutableStateOf<String?>(null) }
    var activeUserMenuMessage by remember { mutableStateOf<ChatMessage?>(null) }

    val haptic = LocalHapticFeedback.current
    val keyboardController = LocalSoftwareKeyboardController.current

    val sessions by viewModel.sessions.collectAsState()
    val currentSessionId by viewModel.currentSessionId.collectAsState()
    val activeGeneratingSessionId by viewModel.activeGeneratingSessionId.collectAsState()
    val isSpeaking by viewModel.isSpeaking.collectAsState()
    val currentlySpeakingId by viewModel.currentlySpeakingId.collectAsState()
    val attachedDocument by viewModel.attachedDocument.collectAsState()
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
            scope.launch {
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
                    Toast.makeText(context, "Attached ${doc.fileName} (${doc.wordCount} words)", Toast.LENGTH_SHORT).show()
                } catch (e: Exception) {
                    Toast.makeText(context, "Error reading file: ${e.message}", Toast.LENGTH_LONG).show()
                } finally {
                    isOcrProcessing = false
                }
            }
        }
    }

    // Camera Capture Launcher — pure native multimodal (no OCR)
    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap: Bitmap? ->
        bitmap?.let {
            scope.launch(Dispatchers.IO) {
                try {
                    val stream = java.io.ByteArrayOutputStream()
                    it.compress(Bitmap.CompressFormat.JPEG, 90, stream)
                    val bytes = stream.toByteArray()
                    val name = "Photo_${System.currentTimeMillis() % 10000}.jpg"
                    val doc = ExtractedDocument(
                        fileName = name,
                        text = "",
                        wordCount = 0,
                        previewBitmap = it,
                        isImage = true,
                        imageBytes = bytes
                    )
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

    // Image Picker Launcher — pure native multimodal (no OCR)
    val imagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch(Dispatchers.IO) {
                try {
                    val bytes = context.contentResolver.openInputStream(it)?.use { s -> s.readBytes() }
                    val previewBmp = if (bytes != null) {
                        android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    } else null
                    val name = DocumentOcrHelper.getFileName(context, it) ?: "Image.jpg"
                    val doc = ExtractedDocument(
                        fileName = name,
                        text = "",
                        wordCount = 0,
                        previewBitmap = previewBmp,
                        isImage = true,
                        imageUri = it,
                        imageBytes = bytes
                    )
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
    val showScrollToBottom by remember { derivedStateOf { listState.canScrollForward } }

    // Dismiss keyboard on scroll
    LaunchedEffect(listState.isScrollInProgress) {
        if (listState.isScrollInProgress) {
            keyboardController?.hide()
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

    // When a new message is added, scroll to bottom anchor
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.scrollToItem(messages.size)
        }
    }

    // While generating: auto-scroll to the bottom anchor on every token or thought update if near bottom
    LaunchedEffect(messages.lastOrNull()?.text, messages.lastOrNull()?.thoughtText) {
        if (messages.isNotEmpty() && isGenerating && !listState.isScrollInProgress) {
            val lastVisible = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            if (lastVisible >= messages.size - 2) {
                listState.scrollToItem(messages.size)
            }
        }
    }

    // User Message Options Dialog (Edit / Copy)
    if (activeUserMenuMessage != null) {
        val userMsg = activeUserMenuMessage!!
        AlertDialog(
            onDismissRequest = { activeUserMenuMessage = null },
            title = { Text("Message Options", fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = Color(0xFFF4F4F4),
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
                            Icon(Icons.Default.Edit, contentDescription = null, tint = Color(0xFF0D0D0D), modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(10.dp))
                            Text("Edit message", fontWeight = FontWeight.Medium, color = Color(0xFF0D0D0D))
                        }
                    }
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = Color(0xFFF4F4F4),
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
                            Icon(Icons.Default.ContentCopy, contentDescription = null, tint = Color(0xFF0D0D0D), modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(10.dp))
                            Text("Copy prompt", fontWeight = FontWeight.Medium, color = Color(0xFF0D0D0D))
                        }
                    }
                }
            },
            confirmButton = {},
            dismissButton = {
                OutlinedButton(onClick = { activeUserMenuMessage = null }) {
                    Text("Close")
                }
            }
        )
    }

    if (showConfigDialog) {
        ConfigDialog(
            currentConfig = config,
            onDismiss = { showConfigDialog = false },
            onApply = { viewModel.updateConfig(it) },
            onResetDefaults = { viewModel.resetConfig() }
        )
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
                drawerContainerColor = MaterialTheme.colorScheme.surface
            ) {
                RecentChatsDrawer(
                    sessions = sessions,
                    currentSessionId = currentSessionId,
                    activeGeneratingSessionId = activeGeneratingSessionId,
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
                    onOpenSettings = {
                        showConfigDialog = true
                    },
                    onOpenMemory = {
                        showMemoryDialog = true
                    },
                    onCloseDrawer = {
                        scope.launch { drawerState.close() }
                    }
                )
            }
        }
    ) {
        Scaffold(
            modifier = modifier.fillMaxSize(),
            contentWindowInsets = WindowInsets(0, 0, 0, 0),
            topBar = {
                TopAppBar(
                    navigationIcon = {
                        IconButton(
                            onClick = { scope.launch { drawerState.open() } }
                        ) {
                            Icon(
                                imageVector = Icons.Default.Menu,
                                contentDescription = "Open drawer",
                                tint = Color(0xFF2E2E2E),
                                modifier = Modifier.size(24.dp)
                            )
                        }
                    },
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "Gemma",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = Color(0xFF0D0D0D)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            BackendBadge(engineState = engineState)
                        }
                    },
                    actions = {
                        IconButton(
                            onClick = { viewModel.createNewChat() }
                        ) {
                            Icon(
                                imageVector = Icons.Default.Edit,
                                contentDescription = "New chat",
                                tint = Color(0xFF2E2E2E),
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        if (messages.isNotEmpty()) {
                            var showMenu by remember { mutableStateOf(false) }
                            Box {
                                IconButton(onClick = { showMenu = true }) {
                                    Icon(
                                        imageVector = Icons.Default.MoreVert,
                                        contentDescription = "Chat options",
                                        tint = Color(0xFF2E2E2E),
                                        modifier = Modifier.size(22.dp)
                                    )
                                }
                                DropdownMenu(
                                    expanded = showMenu,
                                    onDismissRequest = { showMenu = false }
                                ) {
                                    DropdownMenuItem(
                                        text = { Text("Share conversation") },
                                        leadingIcon = {
                                            Icon(
                                                imageVector = Icons.Default.Share,
                                                contentDescription = null,
                                                modifier = Modifier.size(18.dp)
                                            )
                                        },
                                        onClick = {
                                            showMenu = false
                                            viewModel.getCurrentSession()?.let { session ->
                                                ExportHelper.shareSession(context, session)
                                            }
                                        }
                                    )
                                    DropdownMenuItem(
                                        text = { Text("Rename") },
                                        leadingIcon = {
                                            Icon(
                                                imageVector = Icons.Default.DriveFileRenameOutline,
                                                contentDescription = null,
                                                modifier = Modifier.size(18.dp)
                                            )
                                        },
                                        onClick = {
                                            showMenu = false
                                            renameText = viewModel.getCurrentSession()?.title ?: ""
                                            showRenameDialog = true
                                        }
                                    )
                                    DropdownMenuItem(
                                        text = { Text("Delete conversation", color = MaterialTheme.colorScheme.error) },
                                        leadingIcon = {
                                            Icon(
                                                imageVector = Icons.Default.Delete,
                                                contentDescription = null,
                                                tint = MaterialTheme.colorScheme.error,
                                                modifier = Modifier.size(18.dp)
                                            )
                                        },
                                        onClick = {
                                            showMenu = false
                                            showDeleteConfirmDialog = true
                                        }
                                    )
                                }
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.White
                    )
                )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(top = innerPadding.calculateTopPadding())
                .imePadding()
        ) {
            // Error banner
            AnimatedVisibility(
                visible = errorMessage != null,
                enter = fadeIn(),
                exit = fadeOut()
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

            // Decide main content based on installation & engine state
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

                else -> {
                    // Chat Interface
                    Box(modifier = Modifier.weight(1f)) {
                        if (messages.isEmpty()) {
                            EmptyChatHero(
                                onPromptSelected = { prompt ->
                                    viewModel.onInputTextChanged(prompt)
                                    viewModel.sendMessage()
                                }
                            )
                        } else {
                            LazyColumn(
                                state = listState,
                                modifier = Modifier.fillMaxSize(),
                                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                                verticalArrangement = Arrangement.spacedBy(16.dp)
                            ) {
                                items(messages, key = { it.id }) { message ->
                                    MessageBubble(
                                        message = message,
                                        isSpeaking = isSpeaking && currentlySpeakingId == message.id,
                                        onSpeak = { viewModel.toggleSpeak(message.id, message.text) },
                                        onShare = { ExportHelper.shareMessage(context, message.text) },
                                        onRegenerate = { viewModel.regenerateLastResponse() },
                                        onLongPressUserMessage = { activeUserMenuMessage = it },
                                        onConfirmWhatsApp = { action -> viewModel.confirmAndSendWhatsAppAction(action) },
                                        onCancelWhatsApp = { action -> viewModel.cancelWhatsAppAction(action) },
                                        onSelectWhatsAppCandidate = { candidate, action -> viewModel.selectWhatsAppCandidate(candidate, action) },
                                        onWhatsAppSendAgain = { action -> viewModel.executeWhatsAppAction(action) },
                                        onOpenA11ySettings = { viewModel.openAccessibilitySettings() }
                                    )
                                }

                                if (!isGenerating && messages.isNotEmpty() && messages.last().role == MessageRole.ASSISTANT && messages.last().text.isNotBlank()) {
                                    item(key = "follow_up_chips") {
                                        val followUps = listOf(
                                            "Explain in simpler terms",
                                            "Give real-world examples",
                                            "Summarize key takeaways"
                                        )
                                        LazyRow(
                                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(start = 30.dp, top = 4.dp, bottom = 4.dp)
                                        ) {
                                            items(followUps) { chip ->
                                                Surface(
                                                    shape = RoundedCornerShape(16.dp),
                                                    color = Color(0xFFF7F7F8),
                                                    border = BorderStroke(1.dp, Color(0xFFE5E5E5)),
                                                    modifier = Modifier
                                                        .clip(RoundedCornerShape(16.dp))
                                                        .clickable {
                                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                            viewModel.onInputTextChanged(chip)
                                                            viewModel.sendMessage()
                                                        }
                                                ) {
                                                    Text(
                                                        text = chip,
                                                        style = MaterialTheme.typography.labelMedium,
                                                        color = Color(0xFF333333),
                                                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }

                                item(key = "bottom_anchor") {
                                    Spacer(modifier = Modifier.height(8.dp))
                                }
                            }
                        }

                        // Floating Scroll-to-Bottom Button (ChatGPT style)
                        androidx.compose.animation.AnimatedVisibility(
                            visible = showScrollToBottom,
                            enter = fadeIn() + scaleIn(),
                            exit = fadeOut() + scaleOut(),
                            modifier = Modifier
                                .align(Alignment.BottomCenter)
                                .padding(bottom = 12.dp)
                        ) {
                            Surface(
                                shape = CircleShape,
                                color = Color.White,
                                shadowElevation = 4.dp,
                                border = BorderStroke(1.dp, Color(0xFFE5E5E5)),
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
                                        tint = Color(0xFF4A4A4A),
                                        modifier = Modifier.size(22.dp)
                                    )
                                }
                            }
                        }
                    }

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
                                    modifier = Modifier
                                        .size(58.dp)
                                ) {
                                    androidx.compose.foundation.Image(
                                        painter = androidx.compose.ui.graphics.painter.BitmapPainter(doc.previewBitmap!!.asImageBitmap()),
                                        contentDescription = "Image preview",
                                        modifier = Modifier
                                            .size(54.dp)
                                            .align(Alignment.BottomStart)
                                            .clip(RoundedCornerShape(12.dp))
                                            .background(MaterialTheme.colorScheme.surfaceVariant),
                                        contentScale = ContentScale.Crop
                                    )
                                    // Circular Close Button floating at top right of image
                                    Surface(
                                        shape = CircleShape,
                                        color = Color.Black.copy(alpha = 0.75f),
                                        modifier = Modifier
                                            .size(18.dp)
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
                                Surface(
                                    shape = RoundedCornerShape(14.dp),
                                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
                                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))
                                ) {
                                    Row(
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Description,
                                            contentDescription = "File",
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.size(16.dp)
                                        )
                                        Text(
                                            text = doc.fileName,
                                            style = MaterialTheme.typography.labelMedium,
                                            fontWeight = FontWeight.Medium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                            modifier = Modifier.widthIn(max = 200.dp)
                                        )
                                        Icon(
                                            imageVector = Icons.Default.Close,
                                            contentDescription = "Remove",
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                                            modifier = Modifier
                                                .size(16.dp)
                                                .clip(CircleShape)
                                                .clickable { viewModel.clearAttachedDocument() }
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // Active Web Search Chip (ChatGPT Style)
                    if (isWebSearchEnabled) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(start = 16.dp, end = 16.dp, bottom = 4.dp)
                        ) {
                            Surface(
                                shape = RoundedCornerShape(16.dp),
                                color = Color(0xFF10A37F).copy(alpha = 0.12f),
                                border = BorderStroke(1.dp, Color(0xFF10A37F).copy(alpha = 0.25f))
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Language,
                                        contentDescription = null,
                                        tint = Color(0xFF10A37F),
                                        modifier = Modifier.size(13.dp)
                                    )
                                    Spacer(modifier = Modifier.width(5.dp))
                                    Text(
                                        text = "Search the web",
                                        style = MaterialTheme.typography.labelSmall,
                                        fontWeight = FontWeight.Medium,
                                        color = Color(0xFF10A37F)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Icon(
                                        imageVector = Icons.Default.Close,
                                        contentDescription = "Remove search",
                                        tint = Color(0xFF10A37F),
                                        modifier = Modifier
                                            .size(13.dp)
                                            .clip(CircleShape)
                                            .clickable { viewModel.toggleWebSearch() }
                                    )
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
                        isEnabled = engineState is EngineState.Ready,
                        onVoiceInput = {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Gemma…")
                            }
                            voiceLauncher.launch(intent)
                        },
                        onAttach = {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            showAttachmentDialog = true
                        },
                        hasAttachment = attachedDocument != null
                    )
                }
            }
        }
    }
}
}
}

@Composable
fun RecentChatsDrawer(
    sessions: List<ChatSession>,
    currentSessionId: String,
    activeGeneratingSessionId: String? = null,
    onNewChat: () -> Unit,
    onSelectSession: (String) -> Unit,
    onDeleteSession: (String) -> Unit,
    onShareSession: (ChatSession) -> Unit,
    onClearAll: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenMemory: () -> Unit,
    onCloseDrawer: () -> Unit
) {
    var showClearAllConfirm by remember { mutableStateOf(false) }

    if (showClearAllConfirm) {
        AlertDialog(
            onDismissRequest = { showClearAllConfirm = false },
            title = { Text("Clear All Chats?", fontWeight = FontWeight.SemiBold) },
            text = { Text("Are you sure you want to delete all saved conversations? This cannot be undone.") },
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
                    Text("Cancel")
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .background(Color.White)
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
                color = Color(0xFF0D0D0D)
            )
            IconButton(onClick = onCloseDrawer, modifier = Modifier.size(32.dp)) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Close drawer",
                    tint = Color(0xFF6B6B6B),
                    modifier = Modifier.size(20.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        // + New Chat capsule button (ChatGPT style)
        Surface(
            shape = RoundedCornerShape(22.dp),
            color = Color(0xFFF4F4F4),
            border = BorderStroke(1.dp, Color(0xFFE5E5E5)),
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(22.dp))
                .clickable { onNewChat() }
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 11.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Edit,
                    contentDescription = null,
                    tint = Color(0xFF0D0D0D),
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = "New chat",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF0D0D0D)
                )
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        var searchQuery by remember { mutableStateOf("") }
        val filteredSessions = remember(sessions, searchQuery) {
            if (searchQuery.isBlank()) sessions
            else sessions.filter {
                it.title.contains(searchQuery, ignoreCase = true) ||
                it.messages.any { m -> m.text.contains(searchQuery, ignoreCase = true) }
            }
        }

        // Search chats (ChatGPT style)
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = Color(0xFFF4F4F4),
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
                    textStyle = TextStyle(fontSize = 14.sp, color = Color(0xFF0D0D0D)),
                    cursorBrush = SolidColor(Color(0xFF0D0D0D)),
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

        Spacer(modifier = Modifier.height(14.dp))

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
                        color = if (isSelected) Color(0xFFF0F0F0) else Color.Transparent,
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
                                    color = Color(0xFF0D0D0D),
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
        HorizontalDivider(color = Color(0xFFE5E5E5), thickness = 0.5.dp)
        Spacer(modifier = Modifier.height(6.dp))

        // Bottom section: Memory, Settings & Clear (True ChatGPT layout)
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            // Memory item
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = Color.Transparent,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onOpenMemory(); onCloseDrawer() }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Psychology,
                        contentDescription = null,
                        tint = Color(0xFF4A4A4A),
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Memory",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFF0D0D0D)
                    )
                }
            }

            // Settings item
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = Color.Transparent,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onOpenSettings(); onCloseDrawer() }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Settings,
                        contentDescription = null,
                        tint = Color(0xFF4A4A4A),
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Settings",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFF0D0D0D)
                    )
                }
            }

            // Clear all chats button
            if (sessions.isNotEmpty()) {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = Color.Transparent,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { showClearAllConfirm = true }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.DeleteSweep,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "Clear all chats",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun EmptyChatHero(
    onPromptSelected: (String) -> Unit
) {
    val promptChips = listOf(
        Triple("✍️", "Draft a leave email", "draft a professional leave application email"),
        Triple("💡", "Explain quantum computing", "explain quantum computing in simple terms"),
        Triple("🌐", "SRM University AP portal", "now search SRM University AP student portal"),
        Triple("🏏", "Virat Kohli records", "tell me about Virat Kohli cricket records")
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Clean ChatGPT-style icon
        Surface(
            shape = CircleShape,
            color = Color(0xFFF4F4F4),
            modifier = Modifier.size(56.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(text = "✦", fontSize = 24.sp, color = Color(0xFF10A37F))
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        Text(
            text = "What can I help with?",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF0D0D0D)
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = "On-device • 100% Private • Multimodal",
            style = MaterialTheme.typography.bodySmall,
            color = Color(0xFF8E8E93)
        )

        Spacer(modifier = Modifier.height(24.dp))

        // 2x2 grid of clean suggestion chips
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            promptChips.chunked(2).forEach { row ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    row.forEach { (emoji, label, prompt) ->
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFFF9F9F9),
                            border = BorderStroke(1.dp, Color(0xFFE5E5E5)),
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(12.dp))
                                .clickable { onPromptSelected(prompt) }
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 12.dp, vertical = 10.dp)
                            ) {
                                Text(emoji, fontSize = 16.sp)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = label,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = FontWeight.Normal,
                                    color = Color(0xFF343434),
                                    maxLines = 2
                                )
                            }
                        }
                    }
                    if (row.size == 1) Spacer(modifier = Modifier.weight(1f))
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
                BackendType.GPU -> Triple("GPU available", Color(0xFFE8F5E9), Color(0xFF2E7D32))
                BackendType.CPU_FALLBACK -> Triple("CPU fallback", Color(0xFFFFF3E0), Color(0xFFE65100))
                BackendType.CPU -> Triple("CPU", Color(0xFFF5F5F5), Color(0xFF616161))
            }
        }
        is EngineState.Generating -> {
            Triple("Generating...", Color(0xFFE3F2FD), Color(0xFF1565C0))
        }
        is EngineState.Loading -> {
            Triple("Loading...", Color(0xFFEDE7F6), Color(0xFF512DA8))
        }
        else -> {
            Triple("Offline", Color(0xFFEEEEEE), Color(0xFF9E9E9E))
        }
    }

    Surface(
        color = bg,
        shape = RoundedCornerShape(12.dp)
    ) {
        Text(
            text = label,
            color = fg,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
        )
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
    onLongPressUserMessage: (ChatMessage) -> Unit = {},
    onConfirmWhatsApp: (WhatsAppAction) -> Unit = {},
    onCancelWhatsApp: (WhatsAppAction) -> Unit = {},
    onSelectWhatsAppCandidate: (ContactMatch, WhatsAppAction) -> Unit = { _, _ -> },
    onWhatsAppSendAgain: (WhatsAppAction) -> Unit = {},
    onOpenA11ySettings: () -> Unit = {}
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
        // ── USER bubble: gray pill, right-aligned, no avatar ──────────────────
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
                    tint = Color(0xFF9E9E9E),
                    modifier = Modifier.size(15.dp)
                )
            }

            Surface(
                shape = RoundedCornerShape(
                    topStart = 18.dp, topEnd = 18.dp,
                    bottomStart = 18.dp, bottomEnd = 4.dp
                ),
                color = Color(0xFFF4F4F4),
                modifier = Modifier
                    .widthIn(max = 290.dp)
                    .clip(
                        RoundedCornerShape(
                            topStart = 18.dp, topEnd = 18.dp,
                            bottomStart = 18.dp, bottomEnd = 4.dp
                        )
                    )
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
                        Text(
                            text = message.text,
                            style = MaterialTheme.typography.bodyMedium.copy(
                                color = Color(0xFF0D0D0D),
                                lineHeight = 22.sp
                            )
                        )
                    }
                }
            }
        }
    } else {
        // ── ASSISTANT: no bubble, white background, small avatar + bold name ──
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 6.dp),
            horizontalAlignment = Alignment.Start
        ) {
            // Avatar row
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 4.dp)
            ) {
                // Small circular avatar
                Surface(
                    shape = CircleShape,
                    color = Color(0xFF10A37F),
                    modifier = Modifier.size(22.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text("✦", fontSize = 10.sp, color = Color.White)
                    }
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Gemma",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF0D0D0D)
                )
            }

            // Message body — indented under avatar
            Column(modifier = Modifier.padding(start = 30.dp)) {

                // WhatsApp Direct Action Card
                if (message.whatsAppAction != null) {
                    WhatsAppActionCard(
                        action = message.whatsAppAction,
                        onConfirmSend = onConfirmWhatsApp,
                        onCancel = onCancelWhatsApp,
                        onSelectCandidate = onSelectWhatsAppCandidate,
                        onSendAgain = onWhatsAppSendAgain,
                        onOpenA11ySettings = onOpenA11ySettings
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }

                // Phone Call Action Card
                if (message.callAction != null) {
                    CallActionCard(
                        action = message.callAction
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }


                // Web search sources
                if (message.searchResults.isNotEmpty()) {
                    SourcesCard(searchResults = message.searchResults)
                }

                // Thinking card
                if (message.thoughtText.isNotEmpty()) {
                    ThinkingCard(
                        thoughtText = message.thoughtText,
                        isThinking = message.isThinking,
                        isStreaming = message.isStreaming
                    )
                    if (message.text.isNotEmpty()) Spacer(modifier = Modifier.height(8.dp))
                }

                // Dynamic ChatGPT-style working indicator while waiting for first token
                if (message.text.isEmpty() && message.isStreaming && message.thoughtText.isEmpty()) {
                    DynamicWorkingIndicator(isImage = message.isImageAnalysis, isWebSearch = message.isSearchingWeb)
                } else if (message.text.isNotEmpty()) {
                    val emailDraft = remember(message.text) { extractEmailDraft(message.text) }
                    if (emailDraft != null) {
                        val (preamble, body) = emailDraft
                        if (preamble != null) {
                            MarkdownText(text = preamble, isUser = false)
                            Spacer(modifier = Modifier.height(8.dp))
                        }
                        EmailDraftBox(draftText = body)
                    } else {
                        MarkdownText(text = message.text, isUser = false)
                    }
                }

                // Action bar — only after streaming done
                if (!message.isStreaming && message.text.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        // Copy
                        IconButton(
                            onClick = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                clipboardManager.setText(AnnotatedString(message.text))
                                Toast.makeText(context, "Copied", Toast.LENGTH_SHORT).show()
                            },
                            modifier = Modifier.size(30.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.ContentCopy,
                                contentDescription = "Copy",
                                tint = Color(0xFF6B6B6B),
                                modifier = Modifier.size(16.dp)
                            )
                        }
                        // Speak / stop
                        IconButton(
                            onClick = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                onSpeak()
                            },
                            modifier = Modifier.size(30.dp)
                        ) {
                            Icon(
                                imageVector = if (isSpeaking) Icons.Default.Stop else Icons.Default.VolumeUp,
                                contentDescription = if (isSpeaking) "Stop reading" else "Read aloud",
                                tint = Color(0xFF6B6B6B),
                                modifier = Modifier.size(17.dp)
                            )
                        }
                        // Regenerate
                        IconButton(
                            onClick = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                onRegenerate()
                            },
                            modifier = Modifier.size(30.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = "Regenerate response",
                                tint = Color(0xFF6B6B6B),
                                modifier = Modifier.size(17.dp)
                            )
                        }
                        // Share
                        IconButton(
                            onClick = {
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                onShare()
                            },
                            modifier = Modifier.size(30.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Share,
                                contentDescription = "Share",
                                tint = Color(0xFF6B6B6B),
                                modifier = Modifier.size(16.dp)
                            )
                        }
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
            color = Color(0xFF6B6B6B),
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
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.7f)
        ),
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header Bar with Copy button
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.85f),
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
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Email Draft",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }

                    // ChatGPT style Copy Button
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.primaryContainer,
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
                                tint = MaterialTheme.colorScheme.onPrimaryContainer,
                                modifier = Modifier.size(13.dp)
                            )
                            Spacer(modifier = Modifier.width(5.dp))
                            Text(
                                text = "Copy",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        }
                    }
                }
            }

            HorizontalDivider(
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f),
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
    // While thinking actively: expanded by default.
    // Once thinking ends (response begins or stream completes): collapses automatically.
    // User can tap header at any time to toggle expand/collapse manually.
    var userToggledState by remember { mutableStateOf<Boolean?>(null) }
    val isExpanded = userToggledState ?: (isThinking && isStreaming)

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.85f),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
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
                    tint = if (isThinking && isStreaming) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(17.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = if (isThinking && isStreaming) "Thinking live..." else "Thought process",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = if (isThinking && isStreaming) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (isThinking && isStreaming) {
                    Spacer(modifier = Modifier.width(6.dp))
                    CircularProgressIndicator(
                        modifier = Modifier.size(10.dp),
                        strokeWidth = 1.5.dp,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                Text(
                    text = if (isExpanded) "Collapse" else "Expand",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(end = 2.dp)
                )
                Icon(
                    imageVector = Icons.Default.ArrowDropDown,
                    contentDescription = if (isExpanded) "Collapse" else "Expand",
                    tint = MaterialTheme.colorScheme.outline,
                    modifier = Modifier
                        .size(18.dp)
                        .graphicsLayer(rotationZ = if (isExpanded) 180f else 0f)
                )
            }

            AnimatedVisibility(visible = isExpanded) {
                Column(modifier = Modifier.padding(top = 6.dp)) {
                    HorizontalDivider(
                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f),
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
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.85f)
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
fun SourcesCard(searchResults: List<SearchResult>) {
    val context = LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 6.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(bottom = 4.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Language,
                contentDescription = null,
                modifier = Modifier.size(13.dp),
                tint = Color(0xFF6B6B6B)
            )
            Spacer(modifier = Modifier.width(5.dp))
            Text(
                text = "Searched ${searchResults.size} sites",
                style = MaterialTheme.typography.labelSmall.copy(fontSize = 12.sp),
                fontWeight = FontWeight.Medium,
                color = Color(0xFF6B6B6B)
            )
        }

        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            contentPadding = PaddingValues(vertical = 2.dp)
        ) {
            items(searchResults) { res ->
                val domain = remember(res.url) { extractDomain(res.url).ifBlank { res.title } }
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.35f)),
                    modifier = Modifier
                        .clip(RoundedCornerShape(14.dp))
                        .clickable {
                            try {
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(res.url))
                                context.startActivity(intent)
                            } catch (_: Exception) {}
                        }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("🌐", fontSize = 11.sp)
                        Spacer(modifier = Modifier.width(5.dp))
                        Text(
                            text = domain,
                            style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.5.sp),
                            fontWeight = FontWeight.Medium,
                            color = MaterialTheme.colorScheme.onSurface,
                            maxLines = 1
                        )
                    }
                }
            }
        }
    }
}

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
    onAttach: () -> Unit = {},
    hasAttachment: Boolean = false
) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier
            .fillMaxWidth()
            .navigationBarsPadding()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 12.dp, end = 12.dp, bottom = 8.dp, top = 4.dp),
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // 1. Left circular '+' action button (ChatGPT style)
            Surface(
                shape = CircleShape,
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.65f),
                modifier = Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .clickable(onClick = onAttach)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = "Add attachment",
                        modifier = Modifier.size(22.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // 2. Center Pill (Message TextField + subtle Web search toggle)
            Surface(
                shape = RoundedCornerShape(24.dp),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
                modifier = Modifier
                    .weight(1f)
                    .defaultMinSize(minHeight = 42.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Clean ChatGPT globe search toggle button
                    Box(
                        modifier = Modifier
                            .size(28.dp)
                            .clip(CircleShape)
                            .clickable { onToggleWebSearch() }
                            .background(
                                if (isWebSearchEnabled) Color(0xFF10A37F).copy(alpha = 0.15f)
                                else Color.Transparent
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Language,
                            contentDescription = "Search the web",
                            modifier = Modifier.size(18.dp),
                            tint = if (isWebSearchEnabled) Color(0xFF10A37F) else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                        )
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    // BasicTextField - zero extra paddings or weird borders
                    BasicTextField(
                        value = inputText,
                        onValueChange = onTextChanged,
                        enabled = isEnabled && !isGenerating,
                        textStyle = TextStyle(
                            fontSize = 15.sp,
                            color = MaterialTheme.colorScheme.onSurface,
                            lineHeight = 20.sp
                        ),
                        cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                        maxLines = 5,
                        modifier = Modifier.weight(1f),
                        decorationBox = { innerTextField ->
                            Box(
                                modifier = Modifier.fillMaxWidth(),
                                contentAlignment = Alignment.CenterStart
                            ) {
                                if (inputText.isEmpty()) {
                                    Text(
                                        text = if (isWebSearchEnabled) "Search with Gemma..." else if (hasAttachment) "Ask about this..." else "Message",
                                        style = MaterialTheme.typography.bodyMedium.copy(
                                            fontSize = 15.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)
                                        )
                                    )
                                }
                                innerTextField()
                            }
                        }
                    )
                }
            }

            // 3. Right Action Button (Mic when idle, solid high-contrast Circle with Up Arrow when typing/attachment, Stop square when generating)
            if (isGenerating) {
                // Solid Stop Button (ChatGPT black circle with white stop square)
                Surface(
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .clickable { onStop() }
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.Stop,
                            contentDescription = "Stop generating",
                            tint = MaterialTheme.colorScheme.surface,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            } else if (inputText.isNotBlank() || hasAttachment) {
                // Solid Send Button (ChatGPT black circle with crisp white Up arrow)
                val canSend = isEnabled
                Surface(
                    shape = CircleShape,
                    color = if (canSend) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.surfaceVariant,
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .clickable(enabled = canSend) { onSend() }
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.ArrowUpward,
                            contentDescription = "Send",
                            tint = if (canSend) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.outline.copy(alpha = 0.5f),
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            } else {
                // Voice Mic Button (ChatGPT circular mic)
                Surface(
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.65f),
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .clickable(onClick = onVoiceInput)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.Mic,
                            contentDescription = "Voice input",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }
            }
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
        title = { Text("Add to chat", fontWeight = FontWeight.Bold) },
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
            TextButton(onClick = onDismiss) { Text("Cancel") }
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
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
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
                Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                Text(desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
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

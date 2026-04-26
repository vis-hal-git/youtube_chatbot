/**
 * VidMind — app.js
 * Single-Page Application logic for the YouTube Video Chatbot frontend.
 * All API calls are clearly marked and structured for easy backend wiring.
 */

'use strict';

/* ═══════════════════════════════════════════════════════════
   APPLICATION STATE
═══════════════════════════════════════════════════════════ */
const State = {
  sessions: [],
  currentSession: { id: null, name: 'New Session' },
  videos: [],
  chatTarget: 'all', // 'all' | video.id
  messages: [],
  bookmarks: [],
  notes: [],
  activeNote: null,
  currentView: 'chat',
  isLoading: false,
};

/* ═══════════════════════════════════════════════════════════
   API LAYER — Wire these to your FastAPI backend
═══════════════════════════════════════════════════════════ */
const API_BASE = '/api'; // Change to your FastAPI base URL

const API = {
  /**
   * POST /api/session
   * Create a new chat session
   */
  async createSession() {
    return await fetch(`${API_BASE}/session`, { method: 'POST' }).then(r => r.json());
  },

  /**
   * POST /api/session/{id}/save
   * Persist current session to database
   */
  async saveSession(sessionId) {
    return await fetch(`${API_BASE}/session/${sessionId}/save`, { method: 'POST' }).then(r => r.json());
  },

  /**
   * GET /api/session/{id}
   * Load a session by ID
   */
  async loadSession(sessionId) {
    const res = await fetch(`${API_BASE}/session/${sessionId}`);
    if (!res.ok) return null;
    return await res.json();
  },

  /**
   * POST /api/video
   * Add a YouTube video and process it (transcript extraction, FAISS indexing)
   * @param {string} url - YouTube URL
   */
  async addVideo(url) {
    const res = await fetch(`${API_BASE}/video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, session_id: State.currentSession.id })
    });
    if (!res.ok) throw new Error("Failed to add video");
    return await res.json();
  },

  /**
   * DELETE /api/video/{id}
   * Remove a video from the current session
   */
  async removeVideo(videoId) {
    return await fetch(`${API_BASE}/video/${videoId}?session_id=${State.currentSession.id}`, { method: 'DELETE' }).then(r => r.json());
  },

  /**
   * POST /api/chat
   * Send a user message and get an AI response via RAG
   * @param {string} message - User's question
   * @param {string} target - 'all' or specific video ID
   */
  async sendMessage(message, target) {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        target,
        session_id: State.currentSession.id,
      })
    });
    if(!res.ok) throw new Error("Failed to get chat response");
    return await res.json();
  },

  /**
   * GET /api/sessions/history
   * Fetch past sessions for the History view
   */
  async getSessionHistory() {
    return await fetch(`${API_BASE}/sessions/history`).then(r => r.json());
  },

  /**
   * GET /api/search?q=query
   * Search across all session messages
   */
  async searchHistory(query) {
    return await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`).then(r => r.json());
  },

  /**
   * POST /api/export
   * Export chat data in specified format
   */
  async exportChat(format) {
    return await fetch(`${API_BASE}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format, session_id: State.currentSession.id })
    }).then(r => r.blob());
  },
};

/* ═══════════════════════════════════════════════════════════
   DOM REFERENCES
═══════════════════════════════════════════════════════════ */
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

const els = {
  // Sidebar
  sidebar:           $('sidebar'),
  sidebarToggle:     $('sidebarToggle'),
  sessionSelect:     $('sessionSelect'),
  newSessionBtn:     $('newSessionBtn'),
  saveSessionBtn:    $('saveSessionBtn'),
  videoUrlInput:     $('videoUrlInput'),
  addVideoBtn:       $('addVideoBtn'),
  loadingBar:        $('loadingBar'),
  videoList:         $('videoList'),
  chatTargetGroup:   $('chatTargetGroup'),
  statusText:        $('statusText'),
  // Nav
  navTabs:           $('navTabs'),
  activeSessionLabel: $('activeSessionLabel'),
  bookmarkBadge:     $('bookmarkBadge'),
  // Chat
  chatMessages:      $('chatMessages'),
  chatWelcome:       $('chatWelcome'),
  chatInput:         $('chatInput'),
  sendBtn:           $('sendBtn'),
  typingIndicator:   $('typingIndicator'),
  inputContextPill:  $('inputContextPill'),
  inputContextLabel: $('inputContextLabel'),
  // Bookmarks
  bookmarksList:     $('bookmarksList'),
  bookmarkTitle:     $('bookmarkTitle'),
  bookmarkNote:      $('bookmarkNote'),
  bookmarkVideo:     $('bookmarkVideo'),
  addBookmarkBtn:    $('addBookmarkBtn'),
  // Notes
  notesList:         $('notesList'),
  noteEditorBody:    $('noteEditorBody'),
  noteTitleInput:    $('noteTitleInput'),
  noteVideoSelect:   $('noteVideoSelect'),
  saveNoteBtn:       $('saveNoteBtn'),
  deleteNoteBtn:     $('deleteNoteBtn'),
  newNoteBtn:        $('newNoteBtn'),
  // History
  historySearch:     $('historySearch'),
  historySessionsList: $('historySessionsList'),
  historyDetailPanel:  $('historyDetailPanel'),
  // Export buttons
  exportBtns:        $$('.btn-export'),
  // Modal
  modalOverlay:      $('modalOverlay'),
  modalTitle:        $('modalTitle'),
  modalBody:         $('modalBody'),
  modalConfirm:      $('modalConfirm'),
  modalCancel:       $('modalCancel'),
  // Toast
  toastContainer:    $('toastContainer'),
};

/* ═══════════════════════════════════════════════════════════
   NAVIGATION / VIEW MANAGEMENT
═══════════════════════════════════════════════════════════ */
function switchView(view) {
  State.currentView = view;
  $$('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `view${capitalize(view)}`));

  if (view === 'history') renderHistorySessions();
}

els.navTabs.addEventListener('click', e => {
  const tab = e.target.closest('.nav-tab');
  if (tab) switchView(tab.dataset.view);
});

/* ═══════════════════════════════════════════════════════════
   SIDEBAR TOGGLE
═══════════════════════════════════════════════════════════ */
els.sidebarToggle.addEventListener('click', () => {
  const isMobile = window.innerWidth <= 700;
  if (isMobile) {
    els.sidebar.classList.toggle('mobile-open');
  } else {
    els.sidebar.classList.toggle('collapsed');
  }
});

/* ═══════════════════════════════════════════════════════════
   SESSION MANAGEMENT
═══════════════════════════════════════════════════════════ */
els.newSessionBtn.addEventListener('click', async () => {
  if (State.messages.length > 0) {
    const confirmed = await confirm_modal(
      'Start New Session',
      'Starting a new session will clear the current chat. Unsaved messages will be lost.'
    );
    if (!confirmed) return;
  }
  const session = await API.createSession();
  State.currentSession = session;
  State.messages = [];
  State.videos = [];
  State.chatTarget = 'all';
  renderVideoList();
  renderChatMessages();
  updateSessionLabel();
  toast('New session started', 'success');
});

els.saveSessionBtn.addEventListener('click', async () => {
  setStatus('Saving…', 'loading');
  await API.saveSession(State.currentSession.id);
  setStatus('Saved', 'success');
  toast('Session saved successfully', 'success');
  setTimeout(() => setStatus('Ready'), 2000);
});

els.sessionSelect.addEventListener('change', async e => {
  const id = e.target.value;
  if (!id) return;
  const session = await API.loadSession(id);
  if (session) {
    State.currentSession = session;
    updateSessionLabel(session.name);
    toast(`Loaded: ${session.name}`, 'info');
  }
  e.target.value = '';
});

function updateSessionLabel(name) {
  const label = els.activeSessionLabel.querySelector('span');
  if (label) label.textContent = name || State.currentSession.name || 'New Session';
}

/* ═══════════════════════════════════════════════════════════
   VIDEO MANAGEMENT
═══════════════════════════════════════════════════════════ */
async function addVideo(url) {
  if (!url || !url.includes('youtube.com') && !url.includes('youtu.be')) {
    toast('Please enter a valid YouTube URL', 'error');
    return;
  }
  if (State.videos.find(v => v.url === url)) {
    toast('This video is already loaded', 'warning');
    return;
  }

  els.loadingBar.classList.remove('hidden');
  els.addVideoBtn.classList.add('loading');
  setStatus('Processing video…', 'loading');

  try {
    const video = await API.addVideo(url);
    State.videos.push(video);
    if (video.sessionName) {
      State.currentSession.name = video.sessionName;
      updateSessionLabel(video.sessionName);
    }
    renderVideoList();
    syncVideoSelects();
    els.videoUrlInput.value = '';
    toast(`Video added: ${video.title}`, 'success');
    setStatus('Ready');
  } catch (err) {
    toast('Failed to add video. Check the URL and try again.', 'error');
    setStatus('Error', 'error');
    setTimeout(() => setStatus('Ready'), 3000);
  } finally {
    els.loadingBar.classList.add('hidden');
    els.addVideoBtn.classList.remove('loading');
  }
}

els.addVideoBtn.addEventListener('click', () => addVideo(els.videoUrlInput.value.trim()));
els.videoUrlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') addVideo(els.videoUrlInput.value.trim());
});

async function removeVideo(id) {
  const video = State.videos.find(v => v.id === id);
  if (!video) return;
  const confirmed = await confirm_modal('Remove Video', `Remove "${video.title}" from this session?`);
  if (!confirmed) return;
  await API.removeVideo(id);
  State.videos = State.videos.filter(v => v.id !== id);
  if (State.chatTarget === id) State.chatTarget = 'all';
  renderVideoList();
  syncVideoSelects();
  toast('Video removed', 'info');
}

function renderVideoList() {
  const list = els.videoList;
  const targetGroup = els.chatTargetGroup;

  if (State.videos.length === 0) {
    list.innerHTML = `<div style="font-size:0.72rem;color:var(--text-muted);text-align:center;padding:10px 0;">No videos loaded yet</div>`;
    targetGroup.innerHTML = `<button class="target-btn active" data-target="all"><i class="fa-solid fa-layer-group"></i> All Videos</button>`;
    return;
  }

  list.innerHTML = State.videos.map(v => `
    <div class="video-item ${State.chatTarget === v.id ? 'active' : ''}" data-id="${v.id}">
      <div class="video-thumb">
        ${v.thumb
          ? `<img src="${v.thumb}" alt="" onerror="this.parentElement.innerHTML='<i class=\\"fa-brands fa-youtube\\"></i>'" />`
          : `<i class="fa-brands fa-youtube"></i>`}
      </div>
      <div class="video-info">
        <div class="video-title" title="${escapeHtml(v.title)}">${escapeHtml(v.title)}</div>
        <div class="video-meta">${v.channel ? escapeHtml(v.channel) : v.videoId.substring(0, 10) + '…'}</div>
      </div>
      <button class="video-remove-btn" data-id="${v.id}" title="Remove video">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
  `).join('');

  // Target selector
  targetGroup.innerHTML = `
    <button class="target-btn ${State.chatTarget === 'all' ? 'active' : ''}" data-target="all">
      <i class="fa-solid fa-layer-group"></i> All
    </button>
    ${State.videos.map(v => `
      <button class="target-btn ${State.chatTarget === v.id ? 'active' : ''}" data-target="${v.id}" title="${escapeHtml(v.title)}">
        <i class="fa-brands fa-youtube"></i>
        <span style="max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:middle">
          ${escapeHtml(v.title.split(':')[0] || v.title.split(' ')[0])}
        </span>
      </button>
    `).join('')}
  `;

  // Events for remove buttons
  list.querySelectorAll('.video-remove-btn').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); removeVideo(btn.dataset.id); });
  });

  // Target selection
  targetGroup.querySelectorAll('.target-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      State.chatTarget = btn.dataset.target;
      renderVideoList(); // re-render to update active states
      updateInputContext();
    });
  });

  updateInputContext();
}

function updateInputContext() {
  const label = State.chatTarget === 'all'
    ? 'All Videos'
    : State.videos.find(v => v.id === State.chatTarget)?.title?.split(':')[0] ?? 'Video';
  els.inputContextLabel.textContent = label;

  const icon = State.chatTarget === 'all'
    ? 'fa-layer-group'
    : 'fa-brands fa-youtube';
  els.inputContextPill.querySelector('i').className = `fa-solid ${icon}`;
}

/* ═══════════════════════════════════════════════════════════
   CHAT
═══════════════════════════════════════════════════════════ */
function renderChatMessages() {
  const container = els.chatMessages;

  if (State.messages.length === 0) {
    container.innerHTML = '';
    const welcome = document.createElement('div');
    welcome.className = 'chat-welcome';
    welcome.id = 'chatWelcome';
    welcome.innerHTML = `
      <div class="welcome-icon"><i class="fa-solid fa-satellite-dish"></i></div>
      <h2 class="welcome-title">Start a Conversation</h2>
      <p class="welcome-subtitle">Add YouTube videos in the sidebar, then ask anything about their content.</p>
      <div class="welcome-suggestions">
        <button class="suggestion-chip" data-prompt="Summarize all loaded videos for me.">
          <i class="fa-solid fa-list-ul"></i> Summarize videos
        </button>
        <button class="suggestion-chip" data-prompt="What are the key topics covered?">
          <i class="fa-solid fa-tags"></i> Key topics
        </button>
        <button class="suggestion-chip" data-prompt="Compare the main ideas across all videos.">
          <i class="fa-solid fa-code-compare"></i> Compare ideas
        </button>
      </div>`;
    container.appendChild(welcome);
    attachSuggestionChips();
    return;
  }

  container.innerHTML = State.messages.map(renderMessageHTML).join('');
  attachMessageActions();
  scrollToBottom();
}

function renderMessageHTML(msg) {
  const isUser = msg.role === 'user';
  const time = formatTime(msg.timestamp);
  const videoTag = msg.videoTarget && msg.videoTarget !== 'all'
    ? State.videos.find(v => v.id === msg.videoTarget)?.title?.split(':')[0]
    : null;

  return `
    <div class="message ${isUser ? 'user-message' : 'ai-message'}" data-id="${msg.id}">
      <div class="message-avatar">
        <i class="fa-solid ${isUser ? 'fa-user' : 'fa-brain'}"></i>
      </div>
      <div class="message-body">
        <div class="message-meta">
          <span class="message-sender">${isUser ? 'You' : 'VidMind AI'}</span>
          <span class="message-time">${time}</span>
          ${videoTag ? `<span class="message-video-tag"><i class="fa-brands fa-youtube"></i> ${escapeHtml(videoTag)}</span>` : ''}
        </div>
        <div class="message-bubble">
          ${isUser ? `<p>${escapeHtml(msg.content)}</p>` : msg.content}
        </div>
        ${!isUser ? `
          <div class="message-actions">
            <button class="msg-action-btn bookmark-btn ${msg.bookmarked ? 'bookmarked' : ''}" data-id="${msg.id}">
              <i class="fa-solid fa-bookmark"></i>
              ${msg.bookmarked ? 'Bookmarked' : 'Bookmark'}
            </button>
            <button class="msg-action-btn copy-btn" data-id="${msg.id}">
              <i class="fa-solid fa-copy"></i> Copy
            </button>
          </div>
        ` : ''}
      </div>
    </div>`;
}

function appendMessage(msg) {
  // Remove welcome screen if present
  const welcome = document.getElementById('chatWelcome');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.innerHTML = renderMessageHTML(msg);
  const node = div.firstElementChild;
  els.chatMessages.appendChild(node);
  attachMessageActionsTo(node);
  scrollToBottom();
}

function attachSuggestionChips() {
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      els.chatInput.value = chip.dataset.prompt;
      els.chatInput.focus();
      autoResizeTextarea(els.chatInput);
    });
  });
}

function attachMessageActions() {
  els.chatMessages.querySelectorAll('.message').forEach(node => attachMessageActionsTo(node));
}

function attachMessageActionsTo(node) {
  node.querySelector('.bookmark-btn')?.addEventListener('click', e => {
    const id = e.currentTarget.dataset.id;
    quickBookmark(id);
  });
  node.querySelector('.copy-btn')?.addEventListener('click', e => {
    const id = e.currentTarget.dataset.id;
    const msg = State.messages.find(m => m.id === id);
    if (msg) {
      const text = msg.content.replace(/<[^>]+>/g, '');
      navigator.clipboard.writeText(text);
      toast('Copied to clipboard', 'success');
    }
  });
}

function quickBookmark(messageId) {
  const msg = State.messages.find(m => m.id === messageId);
  if (!msg) return;

  msg.bookmarked = !msg.bookmarked;
  const btn = els.chatMessages.querySelector(`.bookmark-btn[data-id="${messageId}"]`);
  if (btn) {
    btn.classList.toggle('bookmarked', msg.bookmarked);
    btn.innerHTML = `<i class="fa-solid fa-bookmark"></i> ${msg.bookmarked ? 'Bookmarked' : 'Bookmark'}`;
  }

  if (msg.bookmarked) {
    const bk = {
      id: `bk_${Date.now()}`,
      title: `AI Response — ${formatTime(msg.timestamp)}`,
      note: msg.content.replace(/<[^>]+>/g, '').substring(0, 300),
      videoId: msg.videoTarget,
      createdAt: new Date(),
    };
    State.bookmarks.push(bk);
    updateBookmarkBadge();
    toast('Message bookmarked', 'success');
  } else {
    toast('Bookmark removed', 'info');
  }
}

async function sendMessage() {
  const text = els.chatInput.value.trim();
  if (!text || State.isLoading) return;

  if (State.videos.length === 0) {
    toast('Add at least one YouTube video before chatting', 'warning');
    return;
  }

  // Add user message
  const userMsg = {
    id: `m_${Date.now()}`,
    role: 'user',
    content: text,
    timestamp: new Date(),
    videoTarget: State.chatTarget,
  };
  State.messages.push(userMsg);
  appendMessage(userMsg);

  // Clear input
  els.chatInput.value = '';
  autoResizeTextarea(els.chatInput);

  // Show typing
  State.isLoading = true;
  els.sendBtn.disabled = true;
  els.typingIndicator.classList.remove('hidden');
  setStatus('Thinking…', 'loading');
  scrollToBottom();

  try {
    const aiResponse = await API.sendMessage(text, State.chatTarget);
    const aiMsg = { ...aiResponse, bookmarked: false };
    State.messages.push(aiMsg);
    els.typingIndicator.classList.add('hidden');
    appendMessage(aiMsg);
    setStatus('Ready');
  } catch (err) {
    els.typingIndicator.classList.add('hidden');
    toast('Failed to get a response. Check your connection.', 'error');
    setStatus('Error', 'error');
    setTimeout(() => setStatus('Ready'), 3000);
  } finally {
    State.isLoading = false;
    els.sendBtn.disabled = false;
  }
}

els.sendBtn.addEventListener('click', sendMessage);
els.chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
els.chatInput.addEventListener('input', () => autoResizeTextarea(els.chatInput));

/* ═══════════════════════════════════════════════════════════
   BOOKMARKS
═══════════════════════════════════════════════════════════ */
function renderBookmarks() {
  const container = els.bookmarksList;
  if (State.bookmarks.length === 0) {
    container.innerHTML = `<div class="bookmarks-empty">
      <i class="fa-solid fa-bookmark"></i>
      <p>No bookmarks yet. Bookmark AI responses from the chat or add custom ones here.</p>
    </div>`;
    return;
  }

  container.innerHTML = State.bookmarks.map(bk => {
    const video = State.videos.find(v => v.id === bk.videoId);
    return `
      <div class="bookmark-card" data-id="${bk.id}">
        <div class="bookmark-card-header">
          <div class="bookmark-card-title">${escapeHtml(bk.title)}</div>
          <button class="bookmark-delete-btn" data-id="${bk.id}" title="Delete bookmark">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
        ${bk.note ? `<div class="bookmark-note">${escapeHtml(bk.note)}</div>` : ''}
        ${video ? `<span class="bookmark-video-tag"><i class="fa-brands fa-youtube"></i> ${escapeHtml(video.title.substring(0, 30))}</span>` : ''}
        <div class="bookmark-time">${formatDate(bk.createdAt)}</div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.bookmark-delete-btn').forEach(btn => {
    btn.addEventListener('click', async e => {
      const id = e.currentTarget.dataset.id;
      const confirmed = await confirm_modal('Delete Bookmark', 'Are you sure you want to delete this bookmark?');
      if (confirmed) {
        State.bookmarks = State.bookmarks.filter(b => b.id !== id);
        renderBookmarks();
        updateBookmarkBadge();
        toast('Bookmark deleted', 'info');
      }
    });
  });
}

els.addBookmarkBtn.addEventListener('click', () => {
  const title = els.bookmarkTitle.value.trim();
  const note  = els.bookmarkNote.value.trim();
  if (!title) { toast('Please enter a bookmark title', 'warning'); return; }

  const bk = {
    id: `bk_${Date.now()}`,
    title,
    note,
    videoId: els.bookmarkVideo.value || null,
    createdAt: new Date(),
  };
  State.bookmarks.push(bk);
  els.bookmarkTitle.value = '';
  els.bookmarkNote.value = '';
  els.bookmarkVideo.value = '';
  renderBookmarks();
  updateBookmarkBadge();
  toast('Bookmark saved', 'success');
});

function updateBookmarkBadge() {
  const count = State.bookmarks.length;
  els.bookmarkBadge.textContent = count || '';
}

/* ═══════════════════════════════════════════════════════════
   NOTES
═══════════════════════════════════════════════════════════ */
function renderNotesList() {
  const list = els.notesList;
  if (State.notes.length === 0) {
    list.innerHTML = `<div style="font-size:0.72rem;color:var(--text-muted);text-align:center;padding:16px;">No notes yet</div>`;
    return;
  }
  list.innerHTML = State.notes.map(n => `
    <div class="note-list-item ${State.activeNote?.id === n.id ? 'active' : ''}" data-id="${n.id}">
      <div class="note-list-title">${escapeHtml(n.title || 'Untitled Note')}</div>
      <div class="note-list-meta">${formatDate(n.updatedAt)}</div>
    </div>
  `).join('');
  list.querySelectorAll('.note-list-item').forEach(item => {
    item.addEventListener('click', () => loadNoteInEditor(item.dataset.id));
  });
}

function loadNoteInEditor(id) {
  const note = State.notes.find(n => n.id === id);
  if (!note) return;
  State.activeNote = note;
  els.noteTitleInput.value = note.title;
  els.noteEditorBody.innerHTML = note.content;
  els.noteVideoSelect.value = note.videoId || '';
  renderNotesList();
}

els.newNoteBtn.addEventListener('click', () => {
  const note = {
    id: `n_${Date.now()}`,
    title: 'New Note',
    content: '',
    videoId: null,
    updatedAt: new Date(),
  };
  State.notes.unshift(note);
  loadNoteInEditor(note.id);
  renderNotesList();
  els.noteTitleInput.focus();
  els.noteTitleInput.select();
});

els.saveNoteBtn.addEventListener('click', () => {
  if (!State.activeNote) return;
  const note = State.notes.find(n => n.id === State.activeNote.id);
  if (!note) return;
  note.title   = els.noteTitleInput.value.trim() || 'Untitled Note';
  note.content = els.noteEditorBody.innerHTML;
  note.videoId = els.noteVideoSelect.value || null;
  note.updatedAt = new Date();
  renderNotesList();
  toast('Note saved', 'success');
});

els.deleteNoteBtn.addEventListener('click', async () => {
  if (!State.activeNote) return;
  const confirmed = await confirm_modal('Delete Note', 'Are you sure you want to delete this note?');
  if (!confirmed) return;
  State.notes = State.notes.filter(n => n.id !== State.activeNote.id);
  State.activeNote = null;
  els.noteTitleInput.value = '';
  els.noteEditorBody.innerHTML = '';
  renderNotesList();
  toast('Note deleted', 'info');
});

// Note toolbar
document.querySelectorAll('.toolbar-btn').forEach(btn => {
  btn.addEventListener('click', e => {
    e.preventDefault();
    const cmd = btn.dataset.cmd;
    if (cmd.includes('|')) {
      const [command, value] = cmd.split('|');
      document.execCommand(command, false, value);
    } else {
      document.execCommand(cmd, false, null);
    }
    els.noteEditorBody.focus();
  });
});

/* ═══════════════════════════════════════════════════════════
   HISTORY
═══════════════════════════════════════════════════════════ */
async function renderHistorySessions() {
  const history = await API.getSessionHistory();
  const list = els.historySessionsList;
  list.innerHTML = history.map(s => `
    <div class="history-session-item" data-id="${s.id}">
      <div class="history-session-name">${escapeHtml(s.name)}</div>
      <div class="history-session-meta">
        <span><i class="fa-solid fa-calendar"></i> ${s.createdAt}</span>
        <span><i class="fa-solid fa-message"></i> ${s.messageCount ?? s.messages?.length ?? 0}</span>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.history-session-item').forEach((item, i) => {
    item.addEventListener('click', () => {
      list.querySelectorAll('.history-session-item').forEach(x => x.classList.remove('active'));
      item.classList.add('active');
      renderHistoryDetail(history[i]);
    });
  });
}

function renderHistoryDetail(session) {
  const panel = els.historyDetailPanel;
  if (!session.messages || session.messages.length === 0) {
    panel.innerHTML = `<div class="history-empty"><i class="fa-solid fa-inbox"></i><p>No messages in this session</p></div>`;
    return;
  }
  panel.innerHTML = session.messages.map(msg => `
    <div class="history-message ${msg.role === 'user' ? 'user-msg' : 'ai-msg'}">
      <div class="history-msg-header">
        <span class="history-msg-sender ${msg.role === 'user' ? 'user' : 'ai'}">
          ${msg.role === 'user' ? 'You' : 'VidMind AI'}
        </span>
        <span class="history-msg-time">${formatTime(msg.timestamp)}</span>
      </div>
      <div class="history-msg-text">${escapeHtml(msg.content.replace(/<[^>]+>/g, ''))}</div>
    </div>
  `).join('');
}

let historySearchDebounce;
els.historySearch.addEventListener('input', () => {
  clearTimeout(historySearchDebounce);
  historySearchDebounce = setTimeout(async () => {
    const q = els.historySearch.value.trim();
    if (!q) { renderHistorySessions(); return; }
    const results = await API.searchHistory(q);
    // Render search results — wire up to backend for real filtering
  }, 300);
});

/* ═══════════════════════════════════════════════════════════
   EXPORT
═══════════════════════════════════════════════════════════ */
els.exportBtns.forEach(btn => {
  btn.addEventListener('click', async () => {
    const format = btn.dataset.format;
    setStatus(`Exporting ${format}…`, 'loading');
    try {
      if (format === 'markdown') {
        const md = generateMarkdownExport();
        downloadBlob(md, 'text/markdown', 'vidmind-chat.md');
      } else if (format === 'text') {
        const txt = generateTextExport();
        downloadBlob(txt, 'text/plain', 'vidmind-chat.txt');
      } else if (format === 'pdf') {
        toast('Generating PDF...', 'info');
        const blob = await API.exportChat('pdf');
        downloadBlob(blob, 'application/pdf', 'vidmind-chat.pdf');
      }
      toast(`Exported as ${format.toUpperCase()}`, 'success');
    } catch (err) {
      toast('Export failed', 'error');
    } finally {
      setStatus('Ready');
    }
  });
});

function generateMarkdownExport() {
  const lines = [`# VidMind Chat Export\n`, `**Session:** ${State.currentSession.name}\n`, `**Date:** ${new Date().toLocaleDateString()}\n\n---\n`];
  State.messages.forEach(msg => {
    lines.push(`### ${msg.role === 'user' ? '👤 You' : '🤖 VidMind AI'}`);
    lines.push(`*${formatTime(msg.timestamp)}*\n`);
    lines.push(msg.content.replace(/<[^>]+>/g, '') + '\n\n---\n');
  });
  return lines.join('\n');
}

function generateTextExport() {
  return State.messages.map(msg => {
    const sender = msg.role === 'user' ? 'You' : 'VidMind AI';
    return `[${formatTime(msg.timestamp)}] ${sender}:\n${msg.content.replace(/<[^>]+>/g, '')}\n`;
  }).join('\n---\n\n');
}

function downloadBlob(content, type, filename) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/* ═══════════════════════════════════════════════════════════
   SYNC: VIDEO SELECTS
═══════════════════════════════════════════════════════════ */
function syncVideoSelects() {
  const options = `<option value="">— None —</option>` +
    State.videos.map(v => `<option value="${v.id}">${escapeHtml(v.title)}</option>`).join('');
  els.bookmarkVideo.innerHTML = options;
  els.noteVideoSelect.innerHTML = `<option value="">— No video linked —</option>` +
    State.videos.map(v => `<option value="${v.id}">${escapeHtml(v.title)}</option>`).join('');
}

/* ═══════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
═══════════════════════════════════════════════════════════ */
const TOAST_ICONS = {
  success: 'fa-circle-check',
  error:   'fa-circle-xmark',
  info:    'fa-circle-info',
  warning: 'fa-triangle-exclamation',
};

function toast(message, type = 'info', duration = 3500) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<i class="toast-icon fa-solid ${TOAST_ICONS[type]}"></i><span>${escapeHtml(message)}</span>`;
  els.toastContainer.appendChild(el);
  setTimeout(() => {
    el.classList.add('exit');
    setTimeout(() => el.remove(), 350);
  }, duration);
}

/* ═══════════════════════════════════════════════════════════
   CONFIRM MODAL
═══════════════════════════════════════════════════════════ */
function confirm_modal(title, body) {
  return new Promise(resolve => {
    els.modalTitle.textContent = title;
    els.modalBody.textContent  = body;
    els.modalOverlay.classList.remove('hidden');

    const cleanup = () => {
      els.modalOverlay.classList.add('hidden');
      els.modalConfirm.removeEventListener('click', onConfirm);
      els.modalCancel.removeEventListener('click', onCancel);
    };
    const onConfirm = () => { cleanup(); resolve(true);  };
    const onCancel  = () => { cleanup(); resolve(false); };

    els.modalConfirm.addEventListener('click', onConfirm);
    els.modalCancel.addEventListener('click',  onCancel);
  });
}

els.modalOverlay.addEventListener('click', e => {
  if (e.target === els.modalOverlay) els.modalCancel.click();
});

/* ═══════════════════════════════════════════════════════════
   STATUS BAR
═══════════════════════════════════════════════════════════ */
function setStatus(text, type = 'success') {
  els.statusText.textContent = text;
  const dot = els.statusText.previousElementSibling;
  dot.className = 'status-dot' + (type !== 'success' ? ` ${type}` : '');
}

/* ═══════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════ */
function escapeHtml(str = '') {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatTime(date) {
  if (!date) return '';
  const d = date instanceof Date ? date : new Date(date);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(date) {
  if (!date) return '';
  const d = date instanceof Date ? date : new Date(date);
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function randomId() {
  return Math.random().toString(36).substring(2, 10);
}

function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
  });
}

/* ═══════════════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════════════ */
async function init() {
  // Fetch session history from backend
  try {
    const history = await API.getSessionHistory();
    if (history && Array.isArray(history)) {
      State.sessions = history;
    }
  } catch(e) {
    console.warn("Could not load session history", e);
  }

  // If there are sessions, load the most recent one automatically? 
  // Let's just create a new session if none is loaded.
  try {
    const newSession = await API.createSession();
    State.currentSession = newSession;
  } catch(e) {
    console.warn("Could not create initial session", e);
  }

  // Render initial state
  renderVideoList();
  renderChatMessages();
  renderBookmarks();
  renderNotesList();
  syncVideoSelects();
  updateBookmarkBadge();
  updateSessionLabel();
  updateInputContext();

  // Load first note if available
  if (State.notes.length > 0) loadNoteInEditor(State.notes[0].id);

  // Populate history session select
  els.sessionSelect.innerHTML = '<option value="">Load a session…</option>' +
    State.sessions.map(s => `<option value="${s.id}">${s.name}</option>`).join('');

  // Keyboard shortcut: Ctrl/Cmd+K → focus chat input
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      switchView('chat');
      els.chatInput.focus();
    }
  });

  console.log('%c VidMind AI initialized ', 'background:#00d4ff;color:#060a0f;font-family:monospace;font-weight:bold;padding:4px 8px;border-radius:4px;');
}

document.addEventListener('DOMContentLoaded', init);

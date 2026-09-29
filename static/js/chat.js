/* Support chat — real-time messaging, countdown audio player,
 * instant optimistic sending, pause/delete/send recording controls,
 * and 100vh full-height mobile app layout.
 * Shared across Candidate, Employer, and Admin dashboards.
 */
(function () {
  'use strict';

  function threadEl() { return document.getElementById('chat-thread'); }
  function composer() { return document.querySelector('.chat-composer'); }

  function nearBottom(el) {
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 140;
  }

  function scrollToEnd(el) {
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }

  function escapeHtml(str) {
    var d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function deduplicateMessages(el) {
    if (!el) return;
    var seen = {};
    var msgs = el.querySelectorAll('.chat-msg');
    msgs.forEach(function (m) {
      var id = m.id || m.dataset.msgId;
      if (id && !id.startsWith('temp-')) {
        if (seen[id]) {
          m.remove();
        } else {
          seen[id] = true;
        }
      }
    });
  }

  function syncLastId(el) {
    if (!el) return;
    deduplicateMessages(el);
    var msgs = el.querySelectorAll('.chat-msg');
    var maxId = 0;
    msgs.forEach(function (m) {
      var idStr = m.dataset.msgId || (m.id && m.id.replace('msg-', ''));
      if (idStr && !isNaN(idStr)) {
        var num = parseInt(idStr, 10);
        if (num > maxId) maxId = num;
      }
    });
    el.dataset.lastId = String(maxId);
  }

  function refreshUrl(el) {
    if (!el) return;
    var after = el.dataset.lastId || '0';
    var url = el.getAttribute('data-poll-url') || el.getAttribute('hx-get');
    if (!url) return;
    var newUrl = '';
    if (url.indexOf('after=') !== -1) {
      newUrl = url.replace(/after=\d+/, 'after=' + after);
    } else {
      newUrl = url + (url.indexOf('?') === -1 ? '?' : '&') + 'after=' + after;
    }
    if (el.hasAttribute('data-poll-url')) el.setAttribute('data-poll-url', newUrl);
    if (el.hasAttribute('hx-get')) el.setAttribute('hx-get', newUrl);
  }

  function syncEmptyState() {
    var el = document.querySelector('[data-chat-empty]');
    if (!el) return;
    var hasMsgs = !!document.querySelector('#chat-thread .chat-msg');
    el.hidden = hasMsgs;
  }

  /* ── Time Formatter (mm:ss) ───────────────────────────────────────── */
  function fmtTime(sec) {
    if (isNaN(sec) || !isFinite(sec) || sec < 0) sec = 0;
    sec = Math.floor(sec);
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function each(sel, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(sel), fn);
  }

  /* ── Dedicated Real-Time Poller (1.0s interval) ───────────────────── */
  var pollTimer = null;
  var isPolling = false;

  function runPoll() {
    var el = threadEl();
    if (!el || isPolling) return;

    var url = el.getAttribute('data-poll-url') || el.getAttribute('hx-get');
    if (!url) return;

    var after = el.dataset.lastId;
    if (after === undefined || after === null || after === '') {
      syncLastId(el);
      after = el.dataset.lastId || '0';
    }

    var cleanUrl = url;
    if (cleanUrl.indexOf('after=') !== -1) {
      cleanUrl = cleanUrl.replace(/after=\d+/, 'after=' + after);
    } else {
      cleanUrl = cleanUrl + (cleanUrl.indexOf('?') === -1 ? '?' : '&') + 'after=' + after;
    }

    isPolling = true;
    var wasAtBottom = nearBottom(el);

    fetch(cleanUrl, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'HX-Request': 'true'
      }
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Poll status: ' + res.status);
        return res.text();
      })
      .then(function (html) {
        isPolling = false;
        if (!html || !html.trim()) return;

        var temp = document.createElement('div');
        temp.innerHTML = html.trim();
        var newMsgs = temp.querySelectorAll('.chat-msg');

        if (newMsgs && newMsgs.length > 0) {
          var appended = 0;
          newMsgs.forEach(function (msg) {
            var msgId = msg.id || (msg.dataset.msgId ? 'msg-' + msg.dataset.msgId : null);
            // Strict duplicate prevention
            if (!document.getElementById(msgId) && !document.querySelector('[data-msg-id="' + msg.dataset.msgId + '"]')) {
              el.appendChild(msg);
              appended++;
            }
          });

          if (appended > 0) {
            syncLastId(el);
            refreshUrl(el);
            syncEmptyState();
            if (wasAtBottom) {
              scrollToEnd(el);
            }
            initAllAudios(el);
            runSidebarPoll();
          }
        }
      })
      .catch(function () {
        isPolling = false;
      });
  }

  var pollVisibilityBound = false;

  function startRealtimePolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(runPoll, 650); // Ultra-fast 650ms polling for instant delivery

    if (pollVisibilityBound) return;
    pollVisibilityBound = true;

    /* A backgrounded tab gains nothing from 650ms polling — browsers throttle
       the timer anyway, so the requests just burn server capacity and land in
       a burst on return. Pause while hidden, then poll once immediately on
       regaining visibility so the transcript is current when it is looked at. */
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      } else if (!pollTimer) {
        runPoll();
        startRealtimePolling();
      }
    });
  }

  /* ── Admin Sidebar Inbox Real-Time Updates ────────────────────────── */
  var sidebarTimer = null;
  var isSidebarPolling = false;

  function filterInbox() {
    var searchInput = document.querySelector('[data-inbox-search]');
    var emptyMsg = document.querySelector('[data-search-empty]');
    var query = (searchInput ? searchInput.value : '').toLowerCase().trim();
    var activeFilterBtn = document.querySelector('.adm-filter-pill.is-active');
    var filterRole = activeFilterBtn ? activeFilterBtn.getAttribute('data-filter') : 'all';

    var visibleCount = 0;
    each('.chat-inbox-row', function (row) {
      var name = (row.getAttribute('data-name') || '').toLowerCase();
      var role = (row.getAttribute('data-role') || '').toLowerCase();
      var unread = parseInt(row.getAttribute('data-unread') || '0', 10);

      var matchesQuery = !query || name.indexOf(query) !== -1;
      var matchesFilter = true;

      if (filterRole === 'candidate') matchesFilter = (role === 'candidate');
      else if (filterRole === 'employer') matchesFilter = (role === 'employer');
      else if (filterRole === 'unread') matchesFilter = (unread > 0 || row.classList.contains('is-active'));

      if (matchesQuery && matchesFilter) {
        row.style.display = 'grid';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    });

    if (emptyMsg) {
      emptyMsg.hidden = (visibleCount > 0);
    }
  }

  function runSidebarPoll() {
    var list = document.getElementById('admInboxList');
    if (!list || isSidebarPolling) return;

    var searchInput = document.querySelector('[data-inbox-search]');
    var isSearching = searchInput && searchInput.value && searchInput.value.trim().length > 0;
    if (isSearching) return;

    var panel = document.getElementById('admActivePanel');
    var activeThreadId = panel ? panel.getAttribute('data-active-thread-id') : null;

    var activePill = document.querySelector('.adm-filter-pill.is-active');
    var activeFilter = activePill ? (activePill.getAttribute('data-filter') || 'all') : 'all';

    var pollUrl = '/dashboard/admin/support/?inbox_partial=1&filter=' + encodeURIComponent(activeFilter);
    if (activeThreadId) {
      pollUrl += '&thread=' + encodeURIComponent(activeThreadId);
    }

    isSidebarPolling = true;
    fetch(pollUrl, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'HX-Request': 'true'
      }
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Sidebar status: ' + res.status);
        return res.text();
      })
      .then(function (html) {
        isSidebarPolling = false;
        if (!html || !html.trim()) return;
        var trimmed = html.trim();

        var temp = document.createElement('div');
        temp.innerHTML = trimmed;

        // Pre-apply current filter & active state so rows never flicker on render
        var currPill = document.querySelector('.adm-filter-pill.is-active');
        var currFilter = currPill ? (currPill.getAttribute('data-filter') || 'all') : 'all';
        var currentActive = document.querySelector('.chat-inbox-row.is-active');
        var currId = activeThreadId || (currentActive ? currentActive.getAttribute('data-thread-id') : null);

        temp.querySelectorAll('.chat-inbox-row').forEach(function (row) {
          var role = (row.getAttribute('data-role') || '').toLowerCase();
          var unread = parseInt(row.getAttribute('data-unread') || '0', 10);
          var rowId = row.getAttribute('data-thread-id');
          if (currId && rowId === String(currId)) {
            row.classList.add('is-active');
          }
          if (currFilter === 'candidate') {
            row.style.display = (role === 'candidate') ? 'grid' : 'none';
          } else if (currFilter === 'employer') {
            row.style.display = (role === 'employer') ? 'grid' : 'none';
          } else if (currFilter === 'unread') {
            row.style.display = (unread > 0 || (currId && rowId === String(currId))) ? 'grid' : 'none';
          } else {
            row.style.display = 'grid';
          }
        });

        // Fast check: if the list HTML is already matching, avoid rebuilding DOM
        if (list.innerHTML.trim() === temp.innerHTML.trim()) {
          return;
        }

        list.innerHTML = temp.innerHTML;

        if (currId) {
          updateActiveInboxRow(currId);
        }

        filterInbox();

        if (window.htmx) {
          window.htmx.process(list);
        }
      })
      .catch(function () {
        isSidebarPolling = false;
      });
  }

  function startAdminSidebarPolling() {
    if (sidebarTimer) clearInterval(sidebarTimer);
    var list = document.getElementById('admInboxList');
    if (list) {
      sidebarTimer = setInterval(runSidebarPoll, 3500);
    }
  }

  /* ── Mobile Layout Activation & Composer Visibility ─────────────── */
  function enableMobileAppLayout() {
    if (document.querySelector('.chat-page') || document.querySelector('.adm-chat-page')) {
      document.body.classList.add('has-chat-app-view');
      document.documentElement.classList.add('has-chat-app-view');
    }
  }

  function init() {
    enableMobileAppLayout();
    var el = threadEl();
    if (el) {
      syncLastId(el);
      refreshUrl(el);
      syncEmptyState();
      scrollToEnd(el);
      startRealtimePolling();
    }
    initAllAudios();
    initAdminLayout();
    startAdminSidebarPolling();
  }

  document.addEventListener('DOMContentLoaded', init);

  /* ── HTMX Lifecycle Listeners ─────────────────────────────────────── */
  document.addEventListener('htmx:afterSwap', function (evt) {
    var el = evt.detail && evt.detail.target;
    if (!el) return;

    if (el.id === 'chat-thread') {
      syncLastId(el);
      refreshUrl(el);
      syncEmptyState();
      scrollToEnd(el);
      initAllAudios(el);
    }

    if (el.id === 'admChatMain') {
      var panel = el.querySelector('#admActivePanel');
      if (panel) {
        var threadId = panel.getAttribute('data-active-thread-id');
        if (threadId) {
          updateActiveInboxRow(threadId);
        }
      }
      var newThread = threadEl();
      if (newThread) {
        syncLastId(newThread);
        refreshUrl(newThread);
        syncEmptyState();
        scrollToEnd(newThread);
        startRealtimePolling();
        initAllAudios(newThread);
      }
      if (window.innerWidth <= 860) {
        var layout = document.getElementById('admChatLayout');
        if (layout) {
          layout.classList.add('show-chat-view');
          layout.classList.remove('show-inbox-view');
          updateMobileTabActive('chat');
        }
      }
    }
  });

  document.addEventListener('htmx:afterSettle', function (evt) {
    var el = evt.detail && evt.detail.target;
    if (!el || el.id !== 'chat-thread') return;
    syncLastId(el);
    refreshUrl(el);
    syncEmptyState();
    scrollToEnd(el);
  });

  /* ── Quick Topic & Canned Reply Chips ─────────────────────────────── */
  document.addEventListener('click', function (evt) {
    var chip = evt.target.closest('.chat-chip[data-prompt]');
    if (!chip) return;
    evt.preventDefault();
    var prompt = chip.getAttribute('data-prompt');
    var form = composer();
    var input = form && form.querySelector('[data-chat-input]');
    if (!input || !prompt) return;
    input.value = prompt;
    resizeChatInput(input);
    input.focus();
  });

  /* ── Manual Refresh Button ────────────────────────────────────────── */
  document.addEventListener('click', function (evt) {
    var btn = evt.target.closest('[data-chat-refresh]');
    if (!btn) return;
    evt.preventDefault();
    btn.style.transform = 'rotate(180deg)';
    setTimeout(function () { btn.style.transform = ''; }, 400);
    runPoll();
  });

  /* ── Composer Form Interactions & Optimistic Send ─────────────────── */
  /* Counts sends that are still in flight. A single boolean used to block all
     overlap; the counter lets a voice note go out while a text message is
     still uploading instead of throwing the recording away. */
  var sendInFlight = 0;
  var lastErrorNote = null;

  /* The File produced by the most recent recording, attached to the next
     outgoing FormData. Declared here (rather than inside the recorder) so the
     sender can reach it. */
  var pendingAudioFile = null;

  function markSendDone() {
    sendInFlight = Math.max(0, sendInFlight - 1);
  }

  function resizeChatInput(ta) {
    if (!ta) return;
    ta.style.height = 'auto';
    var maxH = 140;
    if (ta.scrollHeight > maxH) {
      ta.style.height = maxH + 'px';
      ta.classList.add('is-scrolling');
    } else {
      ta.style.height = Math.max(40, ta.scrollHeight) + 'px';
      ta.classList.remove('is-scrolling');
    }
  }

  document.addEventListener('input', function (evt) {
    var ta = evt.target;
    if (!ta.classList || !ta.classList.contains('chat-input')) return;
    resizeChatInput(ta);
  });

  /* Enter to send, Shift+Enter for newline */
  document.addEventListener('keydown', function (evt) {
    var ta = evt.target;
    if (!ta.classList || !ta.classList.contains('chat-input')) return;
    if (evt.key === 'Enter' && !evt.shiftKey && !evt.isComposing) {
      evt.preventDefault();
      var form = ta.closest('form');
      if (form) sendFormMessage(form);
    }
  });

  /* Optimistic Form Submitter */
  function sendFormMessage(form) {
    // NOTE: this used to bail out with `if (isSubmitting) return;`, which
    // silently DISCARDED a finished recording whenever a previous send was
    // still in flight — the blob was already built and the UI had already
    // reset, so the voice note vanished with no error. Sends are now allowed
    // to overlap; each carries its own snapshot of the payload.
    var pendingSend = sendInFlight + 1;
    sendInFlight = pendingSend;

    var input = form.querySelector('[data-chat-input]');
    var audioInput = form.querySelector('[data-audio-input]');
    var text = input ? input.value.trim() : '';

    // A freshly recorded clip is held in `pendingAudioFile` and attached to
    // the FormData directly. Going through the hidden <input type=file> needs
    // the DataTransfer constructor, which iOS Safari does not support — on
    // those devices the file silently never attached and the voice note was
    // posted with an empty body, so the server dropped it.
    var audioFile = pendingAudioFile;
    var hasAudio = !!audioFile ||
      (audioInput && audioInput.files && audioInput.files.length > 0);

    if (!text && !hasAudio) {
      markSendDone();
      return;
    }

    var targetUrl = form.getAttribute('action') || form.getAttribute('hx-post');
    if (!targetUrl) {
      var isAdmin = !!document.getElementById('admChatLayout');
      targetUrl = isAdmin ? '/dashboard/admin/support/send/' : '/dashboard/support/chat/send/';
    }

    // 1. Build FormData with the actual values BEFORE clearing the input
    var formData = new FormData(form);
    if (text) {
      formData.set('body', text);
    }
    // Attach the recording explicitly under the field name the view reads.
    if (audioFile) {
      formData.set('audio', audioFile, audioFile.name || 'voice.webm');
    }
    // Ensure thread ID is present for admin replies
    if (!formData.has('thread')) {
      var panel = document.getElementById('admActivePanel');
      var threadId = panel ? panel.getAttribute('data-active-thread-id') : null;
      if (threadId) formData.set('thread', threadId);
    }

    var thread = threadEl();
    var tempId = 'temp-' + Date.now();
    var tempBubble = null;

    // 2. Optimistic preview in thread
    if (text && thread) {
      tempBubble = document.createElement('div');
      tempBubble.className = 'chat-msg chat-msg--out is-pending';
      tempBubble.id = tempId;
      var nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      tempBubble.innerHTML =
        '<div class="chat-bubble">' + escapeHtml(text).replace(/\n/g, '<br>') + '</div>' +
        '<div class="chat-meta">' +
          '<time class="chat-time">' + nowTime + '</time>' +
          '<span class="chat-ticks" title="Sending...">✓</span>' +
        '</div>';
      thread.appendChild(tempBubble);
      scrollToEnd(thread);
      syncEmptyState();
    } else if (hasAudio && thread) {
      tempBubble = document.createElement('div');
      tempBubble.className = 'chat-msg chat-msg--out is-pending';
      tempBubble.id = tempId;
      var nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      tempBubble.innerHTML =
        '<div class="chat-bubble"><em>Sending voice note…</em></div>' +
        '<div class="chat-meta">' +
          '<time class="chat-time">' + nowTime + '</time>' +
          '<span class="chat-ticks" title="Uploading...">✓</span>' +
        '</div>';
      thread.appendChild(tempBubble);
      scrollToEnd(thread);
      syncEmptyState();
    }

    // 3. Clear text input AFTER capturing formData
    if (input) {
      input.value = '';
      input.style.height = 'auto';
      input.classList.remove('is-scrolling');
    }

    var btn = form.querySelector('.chat-send');
    if (btn) btn.disabled = true;

    fetch(targetUrl, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'HX-Request': 'true'
      }
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Send status: ' + res.status);
        return res.text();
      })
      .then(function (html) {
        markSendDone();
        // Only re-enable the button once the LAST overlapping send lands, so a
        // fast typist isn't locked out by an earlier request finishing first.
        if (sendInFlight === 0 && btn) btn.disabled = false;
        if (audioInput) audioInput.value = '';
        if (audioFile) pendingAudioFile = null;

        if (!html || !html.trim()) {
          if (tempBubble) {
            tempBubble.classList.remove('is-pending');
            tempBubble.style.opacity = '0.5';
            var ticks = tempBubble.querySelector('.chat-ticks');
            if (ticks) ticks.textContent = '⚠️';
          }
          return;
        }

        var temp = document.createElement('div');
        temp.innerHTML = html.trim();
        var serverMsg = temp.querySelector('.chat-msg');

        if (serverMsg && thread) {
          if (tempBubble && tempBubble.parentNode) {
            tempBubble.replaceWith(serverMsg);
          } else {
            if (!document.getElementById(serverMsg.id)) {
              thread.appendChild(serverMsg);
            }
          }

          syncLastId(thread);
          refreshUrl(thread);
          syncEmptyState();
          scrollToEnd(thread);
          initAllAudios(thread);
        }

        setTimeout(runPoll, 150);
        setTimeout(runSidebarPoll, 150);
      })
      .catch(function () {
        markSendDone();
        if (sendInFlight === 0 && btn) btn.disabled = false;
        if (audioFile) pendingAudioFile = null;
        if (tempBubble) {
          tempBubble.classList.remove('is-pending');
          tempBubble.style.opacity = '0.5';
          var ticks = tempBubble.querySelector('.chat-ticks');
          if (ticks) ticks.textContent = '⚠️';
        }
      });
  }

  document.addEventListener('submit', function (evt) {
    var form = evt.target;
    if (form && form.classList && form.classList.contains('chat-composer')) {
      evt.preventDefault();
      evt.stopPropagation();
      sendFormMessage(form);
    }
  }, true);

  /* ── VOICE RECORDER WITH PAUSE, DELETE, AND DIRECT SEND ───────────── */
  var recorder = null;
  var audioStream = null;
  var chunks = [];
  var recTimer = null;
  var recStart = 0;
  var recElapsed = 0;
  var isPaused = false;
  var recMime = '';

  function pickMime() {
    var opts = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
    for (var i = 0; i < opts.length; i++) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(opts[i])) return opts[i];
    }
    return '';
  }

  function resetRecordUI() {
    var bar = document.querySelector('[data-recording-bar]');
    if (bar) bar.hidden = true;
    var comp = composer();
    if (comp) comp.style.display = '';

    each('[data-mic]', function (b) { b.classList.remove('is-recording'); });

    // Reset buttons and icons
    var pauseBtn = document.querySelector('[data-rec-pause]');
    if (pauseBtn) {
      pauseBtn.classList.remove('is-paused');
      var pauseIcon = pauseBtn.querySelector('.chat-rec-icon-pause');
      var resumeIcon = pauseBtn.querySelector('.chat-rec-icon-resume');
      if (pauseIcon) pauseIcon.style.display = '';
      if (resumeIcon) resumeIcon.style.display = 'none';
    }

    var wave = document.querySelector('[data-rec-wave]');
    if (wave) wave.classList.remove('is-paused');

    var dot = document.querySelector('[data-rec-dot]');
    if (dot) dot.classList.remove('is-paused');

    var badge = document.querySelector('[data-rec-badge]');
    if (badge) {
      badge.textContent = badge.getAttribute('data-default-text') || 'Recording';
      badge.classList.remove('is-paused');
    }

    var timeEl = document.querySelector('[data-rec-time]');
    if (timeEl) timeEl.textContent = '0:00';
  }

  function stopMediaStream() {
    if (audioStream) {
      audioStream.getTracks().forEach(function (t) { t.stop(); });
      audioStream = null;
    }
  }

  function cancelRecording() {
    if (recTimer) { clearInterval(recTimer); recTimer = null; }
    if (recorder) {
      try { recorder.stop(); } catch (e) {}
      recorder = null;
    }
    stopMediaStream();
    chunks = [];
    recElapsed = 0;
    isPaused = false;
    resetRecordUI();
  }

  function startRecording() {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      window.alert('Voice notes are not supported on this browser or device.');
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      audioStream = stream;
      recMime = pickMime();
      chunks = [];
      recorder = new MediaRecorder(stream, recMime ? { mimeType: recMime } : undefined);

      recorder.ondataavailable = function (e) {
        if (e.data && e.data.size) chunks.push(e.data);
      };

      recorder.start(100);
      recStart = Date.now();
      recElapsed = 0;
      isPaused = false;

      var bar = document.querySelector('[data-recording-bar]');
      if (bar) bar.hidden = false;
      var comp = composer();
      if (comp) comp.style.display = 'none';

      each('[data-mic]', function (b) { b.classList.add('is-recording'); });

      var badge = document.querySelector('[data-rec-badge]');
      if (badge && !badge.getAttribute('data-default-text')) {
        badge.setAttribute('data-default-text', badge.textContent || 'Recording');
      }

      var timeEl = document.querySelector('[data-rec-time]');
      if (recTimer) clearInterval(recTimer);
      recTimer = setInterval(function () {
        if (!isPaused) {
          recElapsed = (Date.now() - recStart) / 1000;
          if (timeEl) timeEl.textContent = fmtTime(recElapsed);
        }
      }, 250);
    }).catch(function () {
      window.alert('Microphone access was denied. Please allow microphone permissions in your browser settings.');
    });
  }

  function togglePauseRecording() {
    if (!recorder) return;

    var pauseBtn = document.querySelector('[data-rec-pause]');
    var pauseIcon = pauseBtn && pauseBtn.querySelector('.chat-rec-icon-pause');
    var resumeIcon = pauseBtn && pauseBtn.querySelector('.chat-rec-icon-resume');
    var wave = document.querySelector('[data-rec-wave]');
    var dot = document.querySelector('[data-rec-dot]');
    var badge = document.querySelector('[data-rec-badge]');

    if (recorder.state === 'recording') {
      try { recorder.pause(); } catch (e) {}
      isPaused = true;
      if (pauseBtn) pauseBtn.classList.add('is-paused');
      if (pauseIcon) pauseIcon.style.display = 'none';
      if (resumeIcon) resumeIcon.style.display = 'block';
      if (wave) wave.classList.add('is-paused');
      if (dot) dot.classList.add('is-paused');
      if (badge) {
        badge.textContent = 'Paused';
        badge.classList.add('is-paused');
      }
    } else if (recorder.state === 'paused') {
      try { recorder.resume(); } catch (e) {}
      isPaused = false;
      recStart = Date.now() - (recElapsed * 1000);
      if (pauseBtn) pauseBtn.classList.remove('is-paused');
      if (pauseIcon) pauseIcon.style.display = '';
      if (resumeIcon) resumeIcon.style.display = 'none';
      if (wave) wave.classList.remove('is-paused');
      if (dot) dot.classList.remove('is-paused');
      if (badge) {
        badge.textContent = badge.getAttribute('data-default-text') || 'Recording';
        badge.classList.remove('is-paused');
      }
    }
  }

  function finishAndSendRecording() {
    if (!recorder) return;
    if (recTimer) { clearInterval(recTimer); recTimer = null; }

    recorder.onstop = function () {
      stopMediaStream();
      var type = (recorder && recorder.mimeType) || recMime || 'audio/webm';
      var blob = new Blob(chunks, { type: type });
      recorder = null;
      resetRecordUI();

      if (!blob.size || recElapsed < 0.5) return;

      var form = composer();
      if (!form) return;

      var ext = type.indexOf('mp4') !== -1 ? 'm4a' : 'webm';
      var file = new File([blob], 'voice.' + ext, { type: type });

      // Hand the clip to the sender, which attaches it to the FormData under
      // the "audio" field the view reads. The previous approach assigned the
      // file via `new DataTransfer()`, which throws on iOS Safari — so on
      // iPhones the voice note was never sent at all.
      pendingAudioFile = file;

      // Best-effort mirror into the hidden input so a non-JS/no-FormData
      // fallback path still sees a file. Wrapped because DataTransfer may be
      // unavailable; the pendingAudioFile path above is the one that counts.
      var audioInput = form.querySelector('[data-audio-input]');
      if (audioInput && typeof DataTransfer === 'function') {
        try {
          var dt = new DataTransfer();
          dt.items.add(file);
          audioInput.files = dt.files;
        } catch (e) { /* unsupported — pendingAudioFile carries it instead */ }
      }

      sendFormMessage(form);
    };

    try { recorder.stop(); } catch (e) { cancelRecording(); }
  }

  document.addEventListener('click', function (evt) {
    var mic = evt.target.closest('[data-mic]');
    if (mic) {
      evt.preventDefault();
      startRecording();
      return;
    }

    var delBtn = evt.target.closest('[data-rec-delete]') || evt.target.closest('[data-rec-cancel]');
    if (delBtn) {
      evt.preventDefault();
      cancelRecording();
      return;
    }

    var pauseBtn = evt.target.closest('[data-rec-pause]');
    if (pauseBtn) {
      evt.preventDefault();
      togglePauseRecording();
      return;
    }

    var sendBtn = evt.target.closest('[data-rec-send]');
    if (sendBtn) {
      evt.preventDefault();
      finishAndSendRecording();
      return;
    }
  });

  /* ── AUDIO PLAYER: WAVEFORM + SPEED + COUNTDOWN ──────────────────── */
  /* CRITICAL: this uses an OfflineAudioContext, deliberately.
     An OfflineAudioContext runs the identical decodeAudioData() algorithm but
     has NO output device and NO real-time render thread. Using a live
     AudioContext here made the browser re-open the system audio output and
     start a second render thread; that contention starved the <audio>
     element's own output and produced audible crackling/stuttering, worst
     on phones. Decoding peaks is an offline job, so it should not touch the
     audio hardware at all. */
  var decodeCtx = null;
  function getDecodeCtx() {
    try {
      if (!decodeCtx) {
        var Ctx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
        if (Ctx) decodeCtx = new Ctx(1, 1, 44100);
      }
    } catch (_) {}
    return decodeCtx;
  }

  /* Decoded results are cached by URL. initAllAudios re-runs after every poll
     tick, so without this each tick would re-download and re-decode every
     recording in the transcript. */
  var peakCache = {};

  /* Bar count for the waveform. ~40 fills the 230–320px player without
     turning into a barcode, and matches WhatsApp's density. */
  var WAVE_BARS = 40;

  /* Speech-like placeholder so the player is never an empty grey box while
     the real audio is still downloading/decoding. */
  function placeholderPeaks() {
    var out = [];
    for (var i = 0; i < WAVE_BARS; i++) {
      out.push(0.30 + 0.42 * Math.abs(Math.sin(i * 0.7) * Math.cos(i * 0.31)));
    }
    return out;
  }

  /* Reduce the decoded PCM to WAVE_BARS normalised peak amplitudes. */
  function computePeaks(decoded, bars) {
    var channel = decoded.getChannelData(0);
    var block = Math.floor(channel.length / bars) || 1;
    var peaks = [];
    var max = 0.0001;
    for (var i = 0; i < bars; i++) {
      var start = i * block;
      var end = Math.min(channel.length, start + block);
      var peak = 0;
      for (var j = start; j < end; j++) {
        var a = channel[j] < 0 ? -channel[j] : channel[j];
        if (a > peak) peak = a;
      }
      peaks.push(peak);
      if (peak > max) max = peak;
    }
    // Normalise against the loudest bar, then floor so silence still shows a
    // visible stub instead of collapsing the row to nothing.
    for (var k = 0; k < peaks.length; k++) {
      peaks[k] = Math.max(0.12, Math.min(1, peaks[k] / max));
    }
    return peaks;
  }

  function waveColors(wrap) {
    var mine = wrap.getAttribute('data-audio-is-mine') === '1';
    return mine
      ? { played: 'rgba(255,255,255,0.98)', rest: 'rgba(255,255,255,0.34)', head: '#ffffff' }
      : { played: '#d90429',              rest: 'rgba(15,23,42,0.18)',   head: '#0f172a' };
  }

  /* Paint the bars, filling in the ones already played. */
  function drawWaveform(audio, progress) {
    var wrap = audio.closest('.chat-audio');
    if (!wrap) return;
    var canvas = wrap.querySelector('[data-waveform-canvas]');
    if (!canvas) return;

    var peaks = audio.__peaks || placeholderPeaks();
    var cssW = canvas.clientWidth || wrap.clientWidth || 240;
    var cssH = canvas.clientHeight || 32;
    if (!cssW || !cssH) return;

    // Back the canvas with device pixels so bars stay sharp on retina screens.
    var dpr = window.devicePixelRatio || 1;
    var wantW = Math.round(cssW * dpr);
    var wantH = Math.round(cssH * dpr);
    if (canvas.width !== wantW || canvas.height !== wantH) {
      canvas.width = wantW;
      canvas.height = wantH;
    }

    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    var n = peaks.length;
    var gap = 1.5;
    var barW = Math.max(1.5, (cssW - (n - 1) * gap) / n);
    var mid = cssH / 2;
    var maxH = cssH - 2;
    var colors = waveColors(wrap);
    var cut = progress * n;

    for (var i = 0; i < n; i++) {
      var h = Math.max(2, peaks[i] * maxH);
      var x = i * (barW + gap);
      var y = mid - h / 2;
      ctx.fillStyle = i < cut ? colors.played : colors.rest;
      if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(x, y, barW, h, barW / 2);
        ctx.fill();
      } else {
        ctx.fillRect(x, y, barW, h);
      }
    }

    /* A 1px playhead at the exact play position. Without it the boundary
       between filled and unfilled bars falls between two bars, so it is hard
       to see precisely where playback has reached. */
    if (progress > 0 && progress < 1) {
      var px = Math.round(progress * cssW) + 0.5;
      ctx.fillStyle = colors.head;
      ctx.fillRect(px - 0.5, 1, 1, cssH - 2);
    }
  }

  /* Decode a recording once; cache and reuse both duration and peaks. */
  function loadAudioData(audio, onReady) {
    var src = audio.currentSrc || audio.src;
    if (!src) return;

    var cached = peakCache[src];
    if (cached) {
      audio.__peaks = cached.peaks;
      audio.__hasPeaks = true;
      if (onReady) onReady(cached.duration, cached.peaks);
      return;
    }

    var ctx = getDecodeCtx();
    if (!ctx) return;

    fetch(src)
      .then(function (res) {
        if (!res.ok) throw new Error('Fetch failed');
        return res.arrayBuffer();
      })
      .then(function (buf) { return ctx.decodeAudioData(buf); })
      .then(function (decoded) {
        if (!decoded || !isFinite(decoded.duration) || decoded.duration <= 0) return;
        var duration = decoded.duration;
        var peaks = computePeaks(decoded, WAVE_BARS);
        peakCache[src] = { duration: duration, peaks: peaks };
        audio.__peaks = peaks;
        audio.__hasPeaks = true;
        if (onReady) onReady(duration, peaks);
      })
      .catch(function () {});
  }

  function getAudioDuration(audio) {
    if (audio.__exactDur && isFinite(audio.__exactDur) && audio.__exactDur > 0) {
      return audio.__exactDur;
    }
    if (isFinite(audio.duration) && audio.duration > 0) {
      audio.__exactDur = audio.duration;
      return audio.duration;
    }
    return 0;
  }

  function audioProgress(audio) {
    var dur = getAudioDuration(audio);
    if (!dur || !isFinite(dur)) return 0;
    return Math.max(0, Math.min(1, (audio.currentTime || 0) / dur));
  }

  function updateAudioDisplay(audio, cur, dur) {
    var wrap = audio.closest('.chat-audio');
    if (!wrap) return;
    var timeEl = wrap.querySelector('[data-audio-time]');
    var fillEl = wrap.querySelector('.chat-audio-fill');

    if (timeEl) {
      if (dur > 0 && isFinite(dur)) {
        var remaining = Math.max(0, dur - cur);
        timeEl.textContent = fmtTime(remaining);
      } else {
        timeEl.textContent = fmtTime(cur);
      }
    }

    if (fillEl && dur > 0 && isFinite(dur)) {
      var pct = Math.min(100, Math.max(0, (cur / dur) * 100));
      fillEl.style.width = pct + '%';
    }

    // Fill in the waveform bars that have already played.
    drawWaveform(audio, dur > 0 && isFinite(dur)
      ? Math.max(0, Math.min(1, cur / dur))
      : 0);
  }

  function initAudioItem(audio) {
    if (!audio) return;
    var wrap = audio.closest('.chat-audio');
    if (!wrap) return;
    var timeEl = wrap.querySelector('[data-audio-time]');

    var applyDur = function (d, peaks) {
      if (peaks) {
        audio.__peaks = peaks;
        audio.__hasPeaks = true;
      }
      if (timeEl && audio.paused && (!audio.currentTime || audio.currentTime === 0)) {
        timeEl.textContent = fmtTime(d);
      }
      drawWaveform(audio, audioProgress(audio));
      // Peaks are in, so drop the decoding shimmer and any ring.
      setAudioLoading(audio, false);
    };

    /* Show the ring only if the clip genuinely cannot play yet. Checking
       readyState avoids spinning on an already-buffered/cached clip, where
       `canplay` may well have fired before this initialisation ran. */
    if (!audio.__hasPeaks) setAudioLoading(audio, audio.readyState < 3);

    // Draw the placeholder immediately so the player is never blank.
    if (!audio.__peaks) drawWaveform(audio, 0);

    if (isFinite(audio.duration) && audio.duration > 0) {
      audio.__exactDur = audio.duration;
      applyDur(audio.duration);
    } else {
      // `once` matters here: initAllAudios re-runs on every poll tick, and a
      // persistent listener would pile up one more listener per tick.
      audio.addEventListener('loadedmetadata', function handler() {
        if (isFinite(audio.duration) && audio.duration > 0) {
          audio.__exactDur = audio.duration;
          applyDur(audio.duration);
        }
      }, { once: true });
      loadAudioData(audio, applyDur);
    }
  }

  function initAllAudios(root) {
    var container = root || document;
    var audios = container.querySelectorAll('[data-audio-el]');
    Array.prototype.forEach.call(audios, initAudioItem);
  }

  /* Bars are sized to the canvas width in CSS pixels, so they must be
     repainted whenever that width changes (resize, orientation flip). */
  var waveResizeTimer = null;
  window.addEventListener('resize', function () {
    if (waveResizeTimer) clearTimeout(waveResizeTimer);
    waveResizeTimer = setTimeout(function () {
      each('[data-audio-el]', function (a) { drawWaveform(a, audioProgress(a)); });
    }, 150);
  });

  /* ── Loading / buffering state ────────────────────────────────────── */
  /* Two INDEPENDENT states, deliberately kept separate:
       is-loading  — the media cannot play yet (bytes still arriving).
                     Drives the busy ring in the play button.
       is-decoding — the waveform peaks have not been decoded yet.
                     Drives the dimmed/sweeping waveform.
     They were previously conflated, which left the ring spinning for the
     whole decode of a long clip even though the audio was already playing
     audibly. The ring must track playability only. */
  function setAudioLoading(audio, isLoading) {
    var wrap = audio && audio.closest('.chat-audio');
    if (!wrap) return;
    wrap.classList.toggle('is-loading', !!isLoading);
    wrap.classList.toggle('is-decoding', !audio.__hasPeaks);
  }

  function audioEvents(fn) {
    return function (e) {
      if (e.target && e.target.matches && e.target.matches('[data-audio-el]')) {
        fn(e.target);
      }
    };
  }

  // Buffering begins: show the ring.
  document.addEventListener('loadstart', audioEvents(function (a) {
    setAudioLoading(a, true);
  }), true);
  document.addEventListener('waiting', audioEvents(function (a) {
    setAudioLoading(a, true);
  }), true);
  document.addEventListener('stalled', audioEvents(function (a) {
    setAudioLoading(a, true);
  }), true);

  // Playable again: hide the ring.
  document.addEventListener('canplay', audioEvents(function (a) {
    setAudioLoading(a, false);
  }), true);
  document.addEventListener('canplaythrough', audioEvents(function (a) {
    setAudioLoading(a, false);
  }), true);
  document.addEventListener('playing', audioEvents(function (a) {
    setAudioLoading(a, false);
  }), true);
  document.addEventListener('suspend', audioEvents(function (a) {
    setAudioLoading(a, false);
  }), true);
  // A media error must clear the ring, or the bubble spins forever.
  document.addEventListener('error', audioEvents(function (a) {
    setAudioLoading(a, false);
    a.__hasPeaks = true;   // stop the waveform shimmer as well
    setAudioLoading(a, false);
    // 404 / decode failure = the file is gone from media storage.
    a.__missing = true;
    var missingWrap = a.closest && a.closest('.chat-audio');
    if (missingWrap) markAudioMissing(missingWrap, a);
  }), true);

  /* Flag a bubble whose clip no longer exists on the server: grey out the
     play button, hide the timer, and show the "file missing" note. */
  function markAudioMissing(wrap, audio) {
    if (!wrap || wrap.classList.contains('is-missing')) return;
    wrap.classList.add('is-missing');
    wrap.classList.remove('is-loading', 'is-playing');
    try { audio.pause(); } catch (e) {}
    var play = wrap.querySelector('[data-audio-toggle]');
    if (play) {
      play.disabled = true;
      play.setAttribute('aria-disabled', 'true');
      play.style.opacity = '0.45';
    }
    var missing = wrap.querySelector('[data-audio-missing]');
    if (missing) missing.hidden = false;
    var timeEl = wrap.querySelector('[data-audio-time]');
    if (timeEl) timeEl.style.display = 'none';
  }

  document.addEventListener('click', function (evt) {
    var btn = evt.target.closest('[data-audio-toggle]');
    if (btn) {
      evt.preventDefault();
      evt.stopPropagation();
      var wrap = btn.closest('.chat-audio');
      var audio = wrap && wrap.querySelector('[data-audio-el]');
      if (!audio) return;

      /* A clip whose file is gone from storage (old pre-disk recordings)
         will 404 — mark the bubble once instead of spinning forever. */
      if (wrap.classList.contains('is-missing')) return;
      if (audio.__missing) {
        markAudioMissing(wrap, audio);
        return;
      }

      if (audio.paused) {
        var p = audio.play();
        if (p && p.catch) p.catch(function () {
          if (audio.__missing) markAudioMissing(wrap, audio);
        });
      } else {
        audio.pause();
      }
      return;
    }

    /* Speed cycle: 1x -> 1.25x -> 1.5x -> 2x -> 1x (WhatsApp's ladder). */
    var speedBtn = evt.target.closest('[data-audio-speed]');
    if (speedBtn) {
      evt.preventDefault();
      evt.stopPropagation();
      var sWrap = speedBtn.closest('.chat-audio');
      var sAudio = sWrap && sWrap.querySelector('[data-audio-el]');
      if (!sAudio) return;

      var rates = [1, 1.25, 1.5, 2];
      var cur = sAudio.__rate || 1;
      var next = rates[(rates.indexOf(cur) + 1) % rates.length];

      sAudio.__rate = next;
      sAudio.playbackRate = next;
      // Keep the pitch natural at 1.5x/2x instead of the chipmunk default.
      if ('preservesPitch' in sAudio) sAudio.preservesPitch = true;
      if ('mozPreservesPitch' in sAudio) sAudio.mozPreservesPitch = true;

      speedBtn.textContent = (next === 1 ? '1' : String(next)) + '×';
      sWrap.classList.toggle('is-fast', next > 1);
      return;
    }

    /* Tap anywhere on the waveform to seek to that point. */
    var wave = evt.target.closest('.chat-audio-waveform');
    if (wave) {
      evt.preventDefault();
      evt.stopPropagation();
      var wWrap = wave.closest('.chat-audio');
      var wAudio = wWrap && wWrap.querySelector('[data-audio-el]');
      if (!wAudio) return;
      var dur = getAudioDuration(wAudio);
      if (!dur || !isFinite(dur)) return;

      var r = wave.getBoundingClientRect();
      var ratio = Math.max(0, Math.min(1, (evt.clientX - r.left) / r.width));
      wAudio.currentTime = ratio * dur;
      updateAudioDisplay(wAudio, wAudio.currentTime || 0, dur);
    }
  });

  document.addEventListener('play', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var wrap = audio.closest('.chat-audio');
    if (wrap) wrap.classList.add('is-playing');

    // Re-apply the speed chosen for this bubble. It lives on the element
    // rather than in a module variable so it survives the poll re-rendering
    // the transcript around it.
    if (audio.__rate) audio.playbackRate = audio.__rate;

    each('[data-audio-el]', function (other) {
      if (other !== audio && !other.paused) other.pause();
    });

    var cur = audio.currentTime || 0;
    var dur = getAudioDuration(audio);
    updateAudioDisplay(audio, cur, dur);
  }, true);

  document.addEventListener('pause', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var wrap = audio.closest('.chat-audio');
    if (wrap) wrap.classList.remove('is-playing');
  }, true);

  // COUNTS DOWN SECONDS & MINUTES AS AUDIO PLAYS, AND FILLS THE WAVEFORM.
  //
  // CRITICAL: media events do NOT bubble. The `play`/`pause` listeners above
  // register with `true` (capture) so the event is caught on the way down to
  // the <audio> element. These two were registered WITHOUT capture, so the
  // bubble phase never reached `document` and the handler never ran at all —
  // which is why the waveform stayed empty while the clip was audibly playing
  // and the timer never counted down. Keep the `true` on all four.
  document.addEventListener('timeupdate', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var cur = audio.currentTime || 0;
    var dur = getAudioDuration(audio);
    updateAudioDisplay(audio, cur, dur);
  }, true);

  document.addEventListener('ended', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var wrap = audio.closest('.chat-audio');
    if (wrap) wrap.classList.remove('is-playing');

    var dur = getAudioDuration(audio);
    var fillEl = wrap && wrap.querySelector('.chat-audio-fill');
    var timeEl = wrap && wrap.querySelector('[data-audio-time]');
    if (fillEl) fillEl.style.width = '0%';
    if (timeEl) {
      timeEl.textContent = dur > 0 ? fmtTime(dur) : '0:00';
    }
    audio.currentTime = 0;
    // Reset the waveform so a replay starts filling from the left again.
    drawWaveform(audio, 0);
    setAudioLoading(audio, false);
  }, true);

  /* ── Admin Support Inbox Filter, Search & Real-Time Switching ─────── */
  function updateActiveInboxRow(threadId) {
    each('.chat-inbox-row', function (row) {
      if (row.getAttribute('data-thread-id') === String(threadId)) {
        row.classList.add('is-active');
        var badge = row.querySelector('.chat-inbox-badge');
        if (badge) badge.remove();
        row.setAttribute('data-unread', '0');
      } else {
        row.classList.remove('is-active');
      }
    });
  }

  function initAdminLayout() {
    var layout = document.getElementById('admChatLayout');
    if (!layout) return;

    var hasThread = !!document.querySelector('.adm-chat-main .adm-chat-panel .chat-head');
    if (window.innerWidth <= 860) {
      if (hasThread) {
        layout.classList.add('show-chat-view');
        layout.classList.remove('show-inbox-view');
        updateMobileTabActive('chat');
      } else {
        layout.classList.add('show-inbox-view');
        layout.classList.remove('show-chat-view');
        updateMobileTabActive('inbox');
      }
    }

    each('[data-view-target]', function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var target = btn.getAttribute('data-view-target');
        if (target === 'inbox') {
          layout.classList.add('show-inbox-view');
          layout.classList.remove('show-chat-view');
          updateMobileTabActive('inbox');
        } else {
          layout.classList.add('show-chat-view');
          layout.classList.remove('show-inbox-view');
          updateMobileTabActive('chat');
          var el = threadEl();
          if (el) scrollToEnd(el);
        }
      });
    });

    var searchInput = document.querySelector('[data-inbox-search]');

    if (searchInput) {
      searchInput.addEventListener('input', filterInbox);
    }

    each('.adm-filter-pill', function (pill) {
      pill.addEventListener('click', function (e) {
        e.preventDefault();
        each('.adm-filter-pill', function (p) { p.classList.remove('is-active'); });
        pill.classList.add('is-active');
        var f = pill.getAttribute('data-filter') || 'all';
        try {
          var u = new URL(window.location.href);
          if (f === 'all') {
            u.searchParams.delete('filter');
          } else {
            u.searchParams.set('filter', f);
          }
          window.history.replaceState({}, '', u.toString());
        } catch (_) {}
        filterInbox();
      });
    });

    filterInbox();
  }

  function updateMobileTabActive(view) {
    each('.adm-tab-btn', function (tab) {
      if (tab.getAttribute('data-view-target') === view) {
        tab.classList.add('is-active');
      } else {
        tab.classList.remove('is-active');
      }
    });
  }

  window.addEventListener('resize', function () {
    var layout = document.getElementById('admChatLayout');
    if (!layout) return;
    if (window.innerWidth > 860) {
      layout.classList.remove('show-inbox-view', 'show-chat-view');
    }
  });

})();

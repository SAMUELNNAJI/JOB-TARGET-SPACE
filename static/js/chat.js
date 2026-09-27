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
    var url = el.getAttribute('hx-get');
    if (!url) return;
    if (url.indexOf('after=') !== -1) {
      el.setAttribute('hx-get', url.replace(/after=\d+/, 'after=' + after));
    } else {
      el.setAttribute('hx-get', url + (url.indexOf('?') === -1 ? '?' : '&') + 'after=' + after);
    }
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

    var url = el.getAttribute('hx-get');
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

  function startRealtimePolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(runPoll, 1000); // 1.0 second fast poll for instant delivery
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
  var isSubmitting = false;

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
    if (isSubmitting) return;

    var input = form.querySelector('[data-chat-input]');
    var audioInput = form.querySelector('[data-audio-input]');
    var text = input ? input.value.trim() : '';
    var hasAudio = audioInput && audioInput.files && audioInput.files.length > 0;

    if (!text && !hasAudio) return;

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

    isSubmitting = true;
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
        isSubmitting = false;
        if (btn) btn.disabled = false;
        if (audioInput) audioInput.value = '';

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
        isSubmitting = false;
        if (btn) btn.disabled = false;
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
      var audioInput = form.querySelector('[data-audio-input]');
      if (!audioInput) return;

      var dt = new DataTransfer();
      dt.items.add(file);
      audioInput.files = dt.files;

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

  /* ── AUDIO PLAYER WITH COUNTDOWN PLAYBACK ─────────────────────────── */
  function probeWebmDuration(audio, onReady) {
    if (isFinite(audio.duration) && audio.duration > 0) {
      audio.__lastDur = audio.duration;
      if (onReady) onReady(audio.duration);
      return;
    }
    if (audio.duration === Infinity) {
      var prev = audio.currentTime;
      var handled = false;
      var onTime = function () {
        if (handled) return;
        handled = true;
        audio.removeEventListener('timeupdate', onTime);
        if (isFinite(audio.duration) && audio.duration > 0) {
          audio.__lastDur = audio.duration;
          if (onReady) onReady(audio.duration);
        }
        audio.currentTime = prev;
      };
      audio.addEventListener('timeupdate', onTime);
      audio.currentTime = 1e101;
    }
  }

  function getAudioDuration(audio) {
    if (isFinite(audio.duration) && audio.duration > 0) {
      audio.__lastDur = audio.duration;
      return audio.duration;
    }
    if (audio.__lastDur && audio.__lastDur > 0) {
      return audio.__lastDur;
    }
    if (audio.duration === Infinity) {
      probeWebmDuration(audio);
    }
    return 0;
  }

  function updateAudioDisplay(audio, remainingTime, dur) {
    var wrap = audio.closest('.chat-audio');
    if (!wrap) return;
    var timeEl = wrap.querySelector('[data-audio-time]');
    var fillEl = wrap.querySelector('.chat-audio-fill');

    if (timeEl && remainingTime !== undefined) {
      timeEl.textContent = fmtTime(remainingTime);
    }
    if (fillEl && dur > 0) {
      var pct = Math.min(100, Math.max(0, (audio.currentTime / dur) * 100));
      fillEl.style.width = pct + '%';
    }
  }

  function initAudioItem(audio) {
    if (!audio) return;
    var wrap = audio.closest('.chat-audio');
    if (!wrap) return;
    var timeEl = wrap.querySelector('[data-audio-time]');

    var applyDur = function (d) {
      if (timeEl && audio.paused && (!audio.currentTime || audio.currentTime === 0)) {
        timeEl.textContent = fmtTime(d);
      }
    };

    if (isFinite(audio.duration) && audio.duration > 0) {
      applyDur(audio.duration);
    } else if (audio.duration === Infinity) {
      probeWebmDuration(audio, applyDur);
    } else {
      audio.addEventListener('loadedmetadata', function () {
        if (isFinite(audio.duration) && audio.duration > 0) {
          applyDur(audio.duration);
        } else if (audio.duration === Infinity) {
          probeWebmDuration(audio, applyDur);
        }
      }, { once: true });
      if (audio.readyState === 0) {
        try { audio.load(); } catch (e) {}
      }
    }
  }

  function initAllAudios(root) {
    var container = root || document;
    var audios = container.querySelectorAll('[data-audio-el]');
    Array.prototype.forEach.call(audios, initAudioItem);
  }

  document.addEventListener('click', function (evt) {
    var btn = evt.target.closest('[data-audio-toggle]');
    if (!btn) return;
    evt.preventDefault();
    var wrap = btn.closest('.chat-audio');
    var audio = wrap && wrap.querySelector('[data-audio-el]');
    if (!audio) return;
    if (audio.paused) {
      audio.play();
    } else {
      audio.pause();
    }
  });

  document.addEventListener('play', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var wrap = audio.closest('.chat-audio');
    if (wrap) wrap.classList.add('is-playing');

    each('[data-audio-el]', function (other) {
      if (other !== audio && !other.paused) other.pause();
    });

    var dur = getAudioDuration(audio);
    var remaining = dur > 0 ? Math.max(0, dur - audio.currentTime) : 0;
    updateAudioDisplay(audio, remaining, dur);
  }, true);

  document.addEventListener('pause', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var wrap = audio.closest('.chat-audio');
    if (wrap) wrap.classList.remove('is-playing');
  }, true);

  // COUNTS DOWN SECONDS & MINUTES AS AUDIO PLAYS
  document.addEventListener('timeupdate', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var dur = getAudioDuration(audio);
    var remaining = dur > 0 ? Math.max(0, dur - audio.currentTime) : 0;
    updateAudioDisplay(audio, remaining, dur);
  });

  document.addEventListener('ended', function (evt) {
    var audio = evt.target;
    if (!audio.matches || !audio.matches('[data-audio-el]')) return;
    var wrap = audio.closest('.chat-audio');
    if (wrap) wrap.classList.remove('is-playing');

    var dur = getAudioDuration(audio);
    var fillEl = wrap && wrap.querySelector('.chat-audio-fill');
    var timeEl = wrap && wrap.querySelector('[data-audio-time]');
    if (fillEl) fillEl.style.width = '0%';
    if (timeEl) timeEl.textContent = fmtTime(dur);
  });

  document.addEventListener('click', function (evt) {
    var track = evt.target.closest('.chat-audio-track');
    if (!track) return;
    var wrap = track.closest('.chat-audio');
    var audio = wrap && wrap.querySelector('[data-audio-el]');
    if (!audio) return;
    var dur = getAudioDuration(audio);
    if (!dur) return;

    var r = track.getBoundingClientRect();
    var ratio = Math.max(0, Math.min(1, (evt.clientX - r.left) / r.width));
    audio.currentTime = ratio * dur;

    var remaining = Math.max(0, dur - audio.currentTime);
    updateAudioDisplay(audio, remaining, dur);
  });

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

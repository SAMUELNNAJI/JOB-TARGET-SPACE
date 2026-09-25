/* ============================================================
   Profile Wizard — JobSPACE candidate dashboard
   ============================================================ */

(function () {
  'use strict';

  /* ── DOM refs ── */
  const form        = document.getElementById('pfForm');
  const panes       = [...document.querySelectorAll('.pf-pane')];
  const stepBubbles = [...document.querySelectorAll('[data-step-label]')];
  const progressBar = document.getElementById('pfProgressFill');
  const btnBack     = document.getElementById('pfBack');
  const btnNext     = document.getElementById('pfNext');
  const btnSave     = document.getElementById('pfSave');
  const counterEl   = document.getElementById('pfCurrentStep');
  const ringFill    = document.getElementById('pfRingFill');
  const ringPct     = document.getElementById('pfRingPct');

  /* Completion ring (from server-rendered attribute) */
  const serverPct   = parseInt(ringFill?.dataset.pct ?? '0', 10);
  const CIRCUMFERENCE = 213.6;

  let currentStep = 1;
  const TOTAL     = panes.length;   /* 4 */

  /* ─────────────────────────────────────────────
     Ring initialisation
  ───────────────────────────────────────────── */
  function setRing(pct) {
    if (!ringFill) return;
    const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
    ringFill.style.strokeDashoffset = offset;
    if (ringPct) ringPct.textContent = pct;
  }
  /* Animate ring on load */
  setTimeout(() => setRing(serverPct), 150);

  /* ─────────────────────────────────────────────
     Progress bar
  ───────────────────────────────────────────── */
  function updateProgress(step) {
    if (!progressBar) return;
    progressBar.style.width = ((step - 1) / (TOTAL - 1) * 100) + '%';
  }

  /* ─────────────────────────────────────────────
     Step labels (bubbles)
  ───────────────────────────────────────────── */
  function updateStepLabels(step) {
    stepBubbles.forEach(el => {
      const n = parseInt(el.dataset.stepLabel, 10);
      el.classList.toggle('active',    n === step);
      el.classList.toggle('complete',  n < step);
      el.classList.toggle('upcoming',  n > step);
    });
  }

  /* ─────────────────────────────────────────────
     Show a step
  ───────────────────────────────────────────── */
  let exitTimer  = null;
  let enterTimer = null;

  function showStep(step) {
    /* Cancel any in-flight transition (rapid double-clicks on Continue/Back)
       and finalise panes left mid-exit so two panes never show at once. */
    if (exitTimer)  { clearTimeout(exitTimer);  exitTimer  = null; }
    if (enterTimer) { clearTimeout(enterTimer); enterTimer = null; }
    panes.forEach(p => {
      if (p.classList.contains('pf-pane--exit')) p.classList.remove('active', 'pf-pane--exit');
    });

    /* Animate out current pane — skip when re-showing the same step
       (e.g. initial call), otherwise the pane would remove its own
       'active' class and the form would close */
    if (step !== currentStep) {
      const outPane = panes.find(p => parseInt(p.dataset.step, 10) === currentStep);
      if (outPane && outPane.classList.contains('active')) {
        outPane.classList.add('pf-pane--exit');
        exitTimer = setTimeout(() => {
          outPane.classList.remove('active', 'pf-pane--exit');
          exitTimer = null;
        }, 280);
      }
    }

    currentStep = step;

    /* Animate in new pane */
    const inPane = panes.find(p => parseInt(p.dataset.step, 10) === step);
    if (inPane) {
      inPane.classList.remove('pf-pane--exit');
      enterTimer = setTimeout(() => {
        inPane.classList.add('active');
        enterTimer = null;
      }, 30);
    }

    /* Buttons */
    btnBack.hidden = step === 1;
    btnNext.hidden = step === TOTAL;
    btnSave.hidden = step !== TOTAL;

    /* Counter */
    if (counterEl) counterEl.textContent = step;

    updateStepLabels(step);
    updateProgress(step);

    /* Scroll to top of card */
    document.getElementById('pfCard')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ─────────────────────────────────────────────
     Inline validation before advancing
  ───────────────────────────────────────────── */
  function markInvalid(input) {
    if (!input) return;
    input.classList.add('pf-input--invalid');
    const clear = () => input.classList.remove('pf-input--invalid');
    input.addEventListener('input', clear, { once: true });
    input.addEventListener('change', clear, { once: true });
  }

  function setPaneError(pane, message) {
    if (!pane) return;
    let banner = pane.querySelector('.pf-js-error');
    if (!banner) {
      banner = document.createElement('div');
      banner.className = 'pf-error-banner pf-js-error';
      banner.setAttribute('role', 'alert');
      banner.innerHTML = '<div class="pf-error-banner-icon">!</div><div class="pf-error-banner-copy"><strong>Incomplete step</strong><span></span></div>';
      const head = pane.querySelector('.pf-pane-head');
      if (head) head.after(banner);
      else pane.prepend(banner);
    }
    banner.querySelector('.pf-error-banner-copy span').textContent = message;
    banner.style.display = 'flex';
  }

  function clearPaneError(pane) {
    const b = pane ? pane.querySelector('.pf-js-error') : null;
    if (b) b.remove();
  }

  function validateStep(step) {
    const pane = panes.find(p => parseInt(p.dataset.step, 10) === step);
    if (!pane) return true;
    clearPaneError(pane);
    const missing = [];
    const requireField = (name, label) => {
      const el = form.querySelector('[name="' + name + '"]');
      if (!el || !(el.value || '').trim()) { markInvalid(el); missing.push(label); }
    };
    if (step === 1) {
      requireField('legal_name', 'Full legal name');
      requireField('email', 'Email address');
      requireField('phone', 'Phone number');
      requireField('address', 'Residential address');
      const emailEl = form.querySelector('[name="email"]');
      if (emailEl && emailEl.value.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailEl.value.trim())) {
        markInvalid(emailEl); missing.push('Valid email address');
      }
    }
    if (step === 2) {
      const checked = form.querySelectorAll('input[name="specializations"]:checked').length;
      const cIn = document.getElementById('pfCustomSpecInput');
      const fIn = document.getElementById('pfCustomSpecFallback');
      const customVal = ((cIn && cIn.value) || '').trim() || ((fIn && fIn.value) || '').trim();
      if (!checked && !customVal) {
        missing.push('At least one specialization');
        const grid = document.getElementById('pfSpecGrid');
        if (grid) { grid.classList.add('pf-input--invalid'); setTimeout(() => grid.classList.remove('pf-input--invalid'), 1600); }
      }
    }
    if (step === 3) {
      requireField('primary_degree', 'Primary degree');
      requireField('certifications', 'Professional certifications');
      requireField('software_competencies', 'Software competencies');
    }
    return finishStepValidation(step, pane, missing);
  } /* end validateStep */

  function finishStepValidation(step, pane, missing) {
    if (step === 4) {
      const pitchEl = form.querySelector('[name="professional_pitch"]');
      const pitch = (pitchEl ? pitchEl.value : '').trim();
      if (!pitch) { markInvalid(pitchEl); missing.push('Professional pitch'); }
      else if (pitch.length < 30) { markInvalid(pitchEl); missing.push('Professional pitch (min 30 characters)'); }
      const salEl = form.querySelector('[name="expected_salary"]');
      if (!salEl || !(salEl.value || '').trim()) { markInvalid(salEl); missing.push('Expected salary'); }
      else if (!(parseFloat(salEl.value) > 0)) { markInvalid(salEl); missing.push('Valid expected salary'); }
      const avEl = form.querySelector('[name="availability"]');
      if (!avEl || !(avEl.value || '').trim()) { markInvalid(avEl); missing.push('Availability'); }
      const fileInput = document.querySelector('input[type="file"][name="file"]');
      const hasExistingDocs = !!document.querySelector('.pf-doc-row');
      const hasNewFile = !!(fileInput && fileInput.files && fileInput.files.length);
      if (!hasExistingDocs && !hasNewFile) {
        missing.push('CV upload (PDF or DOCX, max 5 MB)');
        const dz = document.getElementById('pfDropzone');
        if (dz) { dz.classList.add('pf-input--invalid'); setTimeout(() => dz.classList.remove('pf-input--invalid'), 1600); }
      }
    }
    if (missing.length) {
      setPaneError(pane, 'Please fill in the required field(s) to continue: ' + missing.join(', ') + '.');
      const firstInvalid = pane.querySelector('.pf-input--invalid');
      if (firstInvalid && firstInvalid.focus) { try { firstInvalid.focus(); } catch (e) {} }
      const btn = step === TOTAL ? btnSave : btnNext;
      if (btn) {
        btn.classList.remove('pf-btn--shake');
        void btn.offsetWidth;
        btn.classList.add('pf-btn--shake');
        setTimeout(() => btn.classList.remove('pf-btn--shake'), 500);
      }
      return false;
    }
    return true;
  }

  function validateCurrentPane() {
    return validateStep(currentStep);
  }

  /* Clear invalid state on user input */
  form?.addEventListener('input', e => {
    if (e.target.value.trim()) e.target.classList.remove('pf-input--invalid');
  });

  /* ─────────────────────────────────────────────
     Navigation handlers
  ───────────────────────────────────────────── */
  /* Server-rendered notices — the red "Step X needs attention" banner and
     the flash alerts — describe the LAST failed submission. They are stale
     the moment the user starts navigating again, so dismiss them on EVERY
     Continue/Back click (even when validation fails). Otherwise an old
     "Step 2" notice competes with fresh inline feedback on step 1. */
  function dismissStaleNotices() {
    document.getElementById('pfErrorBanner')?.remove();
    document.querySelectorAll('.pf-alert').forEach(el => el.remove());
  }

  /* Ignore rapid repeat clicks while a step transition (~280ms) is running.
     Without this lock a second click validates/advances the NEXT step before
     its pane is visible — surfacing that step's error or skipping ahead. */
  let isNavigating = false;
  function lockNavigation() {
    isNavigating = true;
    setTimeout(() => { isNavigating = false; }, 320);
  }

  btnNext?.addEventListener('click', () => {
    dismissStaleNotices();
    if (isNavigating) return;
    if (currentStep < TOTAL && validateCurrentPane()) {
      lockNavigation();
      showStep(currentStep + 1);
    }
  });

  btnBack?.addEventListener('click', () => {
    dismissStaleNotices();
    if (isNavigating) return;
    if (currentStep > 1) {
      const pane = panes.find(p => parseInt(p.dataset.step, 10) === currentStep);
      clearPaneError(pane);
      lockNavigation();
      showStep(currentStep - 1);
    }
  });

  /* Prevent accidental Enter-to-submit */
  form?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') e.preventDefault();
  });

  /* ─────────────────────────────────────────────
     Character counter for professional pitch
  ───────────────────────────────────────────── */
  const pitchField   = document.getElementById('id_professional_pitch');
  const pitchCounter = document.getElementById('pitchCounter');
  const PITCH_MAX    = 500;

  function updatePitchCounter() {
    if (!pitchField || !pitchCounter) return;
    const len  = pitchField.value.length;
    pitchCounter.textContent = `${len} / ${PITCH_MAX}`;
    pitchCounter.style.color = len > PITCH_MAX ? '#d90429' : '';
  }
  pitchField?.addEventListener('input', updatePitchCounter);
  updatePitchCounter();

  /* ─────────────────────────────────────────────
     Drag-and-drop CV upload zone
  ───────────────────────────────────────────── */
  const dropzone     = document.getElementById('pfDropzone');
  const fileInput    = dropzone?.querySelector('input[type="file"]');
  const dropInner    = document.getElementById('pfDropzoneInner');

  function setDropzoneFile(file) {
    if (!dropInner) return;
    dropInner.querySelector('.pf-dropzone-text').innerHTML =
      `<strong>${file.name}</strong>`;
    dropInner.querySelector('.pf-dropzone-hint').textContent =
      `${(file.size / 1024).toFixed(0)} KB · ready to upload`;
    dropzone.classList.add('pf-dropzone--selected');
  }

  fileInput?.addEventListener('change', () => {
    if (fileInput.files[0]) setDropzoneFile(fileInput.files[0]);
  });

  dropzone?.addEventListener('dragover', e => {
    e.preventDefault();
    dropzone.classList.add('pf-dropzone--drag');
  });
  dropzone?.addEventListener('dragleave', () => {
    dropzone.classList.remove('pf-dropzone--drag');
  });
  dropzone?.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('pf-dropzone--drag');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    /* Assign to file input */
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    setDropzoneFile(file);
  });

  /* ─────────────────────────────────────────────
     Custom specialization adder (AJAX)
  ───────────────────────────────────────────── */
  const customInput  = document.getElementById('pfCustomSpecInput');
  const customBtn    = document.getElementById('pfCustomSpecBtn');
  const specHint     = document.getElementById('pfSpecHint');
  const specChips    = document.getElementById('pfSpecChips');
  const specGrid     = document.getElementById('pfSpecGrid');
  const fallbackInput = document.getElementById('pfCustomSpecFallback');

  function showHint(msg, isError) {
    if (!specHint) return;
    specHint.textContent = msg;
    specHint.className = 'pf-spec-adder-hint ' + (isError ? 'pf-spec-adder-hint--error' : 'pf-spec-adder-hint--ok');
    setTimeout(() => { specHint.textContent = ''; specHint.className = 'pf-spec-adder-hint'; }, 3500);
  }

  function addChip(name, id) {
    if (!specChips) return;
    /* Avoid duplicates */
    if (specChips.querySelector(`[data-spec-id="${id}"]`)) return;

    const chip = document.createElement('span');
    chip.className = 'pf-spec-chip';
    chip.dataset.specId = id;
    chip.innerHTML = `
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
      ${name}
    `;
    specChips.appendChild(chip);
  }

  function injectCheckbox(id, name) {
    if (!specGrid) return;
    /* If a checkbox for this id already exists don't add again */
    if (specGrid.querySelector(`input[value="${id}"]`)) {
      /* Just ensure it's checked */
      specGrid.querySelector(`input[value="${id}"]`).checked = true;
      return;
    }
    const ul = specGrid.querySelector('ul') || specGrid;
    const li = document.createElement('li');
    li.className = 'pf-spec-item--checked';
    li.innerHTML = `
      <input type="checkbox" name="specializations" value="${id}" checked
             id="id_specializations_custom_${id}">
      <label for="id_specializations_custom_${id}" style="cursor:pointer">${name}</label>
    `;
    /* sync card highlight on toggle */
    li.querySelector('input').addEventListener('change', function() {
      li.classList.toggle('pf-spec-item--checked', this.checked);
    });
    ul.appendChild(li);
  }

  async function submitCustomSpec() {
    const name = customInput?.value.trim();
    if (!name) { showHint('Please enter a specialization name.', true); return; }
    if (name.length > 120) { showHint('Name is too long (max 120 characters).', true); return; }

    customBtn.disabled = true;
    customBtn.textContent = '…';

    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ?? '';
      const res = await fetch('/dashboard/candidate/specialization/add/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrfToken },
        body: `name=${encodeURIComponent(name)}`,
      });
      const data = await res.json();

      if (data.ok) {
        injectCheckbox(data.id, data.name);
        addChip(data.name, data.id);
        showHint(`"${data.name}" added and selected!`, false);
        customInput.value = '';
        if (fallbackInput) fallbackInput.value = '';  /* clear fallback */
      } else {
        showHint(data.error || 'Could not add specialization.', true);
      }
    } catch (e) {
      /* Network error → use fallback hidden field so it submits with the form */
      if (fallbackInput) fallbackInput.value = name;
      showHint('Saved locally — will be added when you save the profile.', false);
    } finally {
      customBtn.disabled = false;
      customBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add`;
    }
  }

  customBtn?.addEventListener('click', submitCustomSpec);
  customInput?.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); submitCustomSpec(); }
  });
  document.querySelectorAll('.pf-spec-grid input[type="checkbox"]').forEach(cb => {
    function syncCard() {
      const li = cb.closest('li');
      if (li) li.classList.toggle('pf-spec-item--checked', cb.checked);
    }
    syncCard();
    cb.addEventListener('change', syncCard);
  });

   /* ─────────────────────────────────────────────
     Server round-trip: jump to error step / modal controls
  ───────────────────────────────────────────── */
  const serverErrorBanner = document.getElementById('pfErrorBanner');
  let serverErrStep = 0;
  if (serverErrorBanner) {
    serverErrStep = parseInt(serverErrorBanner.dataset.errorStep || '1', 10);
    document.getElementById('pfErrorGo')?.addEventListener('click', () => {
      showStep(serverErrStep);
      document.getElementById('pfCard')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  const successModal = document.getElementById('pfSuccessModal');
  function closeSuccessModal() {
    if (!successModal) return;
    successModal.classList.add('pf-modal--hide');
    setTimeout(() => successModal.remove(), 220);
    /* Clean ?completed=1 from URL without reloading */
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('completed');
      window.history.replaceState({}, '', url.toString());
    } catch (e) {}
  }
  document.getElementById('pfModalClose')?.addEventListener('click', closeSuccessModal);
  successModal?.addEventListener('click', (e) => {
    if (e.target === successModal) closeSuccessModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('pfSuccessModal')) closeSuccessModal();
  });

  /* ─────────────────────────────────────────────
     Init (single call — server error step wins, else step 1)
  ───────────────────────────────────────────── */
  const initialStep = serverErrStep || 1;
  showStep(initialStep >= 1 && initialStep <= TOTAL ? initialStep : 1);
  updateProgress(initialStep >= 1 && initialStep <= TOTAL ? initialStep : 1);

}());

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
  function showStep(step) {
    /* Animate out current pane */
    const outPane = panes.find(p => parseInt(p.dataset.step, 10) === currentStep);
    if (outPane) {
      outPane.classList.add('pf-pane--exit');
      setTimeout(() => {
        outPane.classList.remove('active', 'pf-pane--exit');
      }, 280);
    }

    currentStep = step;

    /* Animate in new pane */
    const inPane = panes.find(p => parseInt(p.dataset.step, 10) === step);
    if (inPane) {
      setTimeout(() => {
        inPane.classList.add('active');
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
  function validateCurrentPane() {
    const pane = panes.find(p => parseInt(p.dataset.step, 10) === currentStep);
    if (!pane) return true;

    let valid = true;
    /* Check required inputs in this pane only */
    pane.querySelectorAll('input[required], textarea[required], select[required]').forEach(input => {
      if (!input.value.trim()) {
        input.classList.add('pf-input--invalid');
        valid = false;
      } else {
        input.classList.remove('pf-input--invalid');
      }
    });

    if (!valid) {
      /* Shake the Next button */
      btnNext.classList.add('pf-btn--shake');
      setTimeout(() => btnNext.classList.remove('pf-btn--shake'), 500);
    }
    return valid;
  }

  /* Clear invalid state on user input */
  form?.addEventListener('input', e => {
    if (e.target.value.trim()) e.target.classList.remove('pf-input--invalid');
  });

  /* ─────────────────────────────────────────────
     Navigation handlers
  ───────────────────────────────────────────── */
  btnNext?.addEventListener('click', () => {
    if (currentStep < TOTAL) showStep(currentStep + 1);
  });

  btnBack?.addEventListener('click', () => {
    if (currentStep > 1) showStep(currentStep - 1);
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
     Init
  ───────────────────────────────────────────── */
  showStep(1);
  updateProgress(1);

}());

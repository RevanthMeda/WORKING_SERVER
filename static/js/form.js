// Wrapped in an IIFE to prevent global scope pollution
(function() {
  // Track current step
  let currentStep = 1;
  let purposeEditorEl = null;
  let purposeTextareaEl = null;
  let scopeEditorEl = null;
  let scopeTextareaEl = null;

  // Define functions first so they can be used
  function goToStep(step) {
    const currentFs = document.getElementById(`step-${currentStep}`);

    // Clear previous validation states
    if (currentFs) {
      currentFs.classList.remove('invalid');
      currentFs.querySelectorAll('.error').forEach(el => el.style.display = 'none');

      if (step > currentStep) {
        if (!currentFs.checkValidity()) {
          currentFs.classList.add('invalid');

          // Show error messages
          currentFs.querySelectorAll(':invalid').forEach(field => {
            const errorEl = field.nextElementSibling;
            if (errorEl && errorEl.classList.contains('error')) {
              errorEl.style.display = 'inline-block';
            }
          });

          currentFs.querySelector(':invalid')?.focus();
          return;
        }
      }
    }

    currentStep = step;

    for (let i = 1; i <= 10; i++) {
      const stepEl = document.getElementById(`step-${i}`);
      const progEl = document.getElementById(`prog-${i}`);
      if (stepEl) stepEl.classList.toggle('active', i === step);
      if (progEl) {
        progEl.classList.toggle('active', i === step);
        progEl.classList.toggle('disabled', i !== step);
      }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
    saveState();
  }

  // Define startProcess function
  function startProcess() {
    document.getElementById('welcomePage').style.display = 'none';
    document.getElementById('reportTypePage').style.display = 'block';
  }

  // Function to show SAT form
  function showSATForm() {
    window.location.href = '/reports/new/sat/full';
  }

  // Function to go back to welcome
  function backToWelcome() {
    document.getElementById('reportTypePage').style.display = 'none';
    document.getElementById('welcomePage').style.display = 'block';
  }

  // LOCALSTORAGE STATE PERSISTENCE
  const FORM_KEY = 'satFormState';
  function saveState() {
    const form = document.getElementById('satForm');
    if (!form) return;

    const data = {};
    Array.from(form.elements).forEach(el => {
      if (!el.name || el.type === 'file') return;
      if ((el.type === 'checkbox' || el.type === 'radio') && !el.checked) return;
      data[el.name] = el.value;
    });
    localStorage.setItem(FORM_KEY, JSON.stringify(data));
  }

  function loadState() {
    const stored = localStorage.getItem(FORM_KEY);
    if (!stored) return;

    const data = JSON.parse(stored);
    const form = document.getElementById('satForm');
    if (!form) return;

    Object.entries(data).forEach(([name, val]) => {
      const el = form.elements[name];
      if (el) el.value = val;
    });
  }

  function removeRow(button) {
    const row = button.closest('tr');
    if (row) row.remove();
    saveState();
  }

  function addRow(templateId, tbodyId) {
    console.log(`Adding row: template=${templateId}, tbody=${tbodyId}`);

    // Prevent rapid double-clicks
    if (addRow._processing) {
      console.log('AddRow already processing, skipping...');
      return;
    }
    addRow._processing = true;

    setTimeout(() => {
      addRow._processing = false;
    }, 300);

    // Get the tbody element
    const tbody = document.getElementById(tbodyId);
    if (!tbody) {
      console.error(`tbody not found: ${tbodyId}`);
      addRow._processing = false;
      return;
    }

    // Get the template element
    const template = document.getElementById(templateId);
    if (!template) {
      console.error(`template not found: ${templateId}`);
      addRow._processing = false;
      return;
    }

    // Clone the template content
    const clone = template.content.cloneNode(true);
    const row = clone.querySelector('tr');

    if (row) {
      row.classList.add('fade-in');
      console.log('Row cloned successfully');
    } else {
      console.error('No tr element found in template');
      addRow._processing = false;
      return;
    }

    // Clear any text nodes that might interfere
    Array.from(tbody.childNodes).forEach(node => {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() === '') {
        tbody.removeChild(node);
      }
    });

    // Append the new row
    tbody.appendChild(clone);
    console.log('Row added successfully');

    // Save state after adding
    saveState();
  }

  function setupEventHandlers() {
    // Wire up progress nav clicks
    document.querySelectorAll('.progress-step').forEach(el => {
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => {
        const step = Number(el.id.split('-')[1]);
        goToStep(step);
      });
    });

    // Setup report type selection handlers
    document.addEventListener('click', (e) => {
      // Handle SAT report selection
      if (e.target.closest('[data-report-type="sat"]')) {
        showSATForm();
      }

      // Handle back to welcome button
      if (e.target.closest('#backToWelcomeButton')) {
        backToWelcome();
      }
    });

    setupAddButtons();

    // Setup navigation buttons with delegation
    document.addEventListener('click', (e) => {
      // Next step
      if (e.target.closest('[data-next-step]')) {
        const btn = e.target.closest('[data-next-step]');
        goToStep(parseInt(btn.dataset.nextStep));
      }
      // Previous step
      if (e.target.closest('[data-prev-step]')) {
        const btn = e.target.closest('[data-prev-step]');
        goToStep(parseInt(btn.dataset.prevStep));
      }
      // Remove row
      if (e.target.closest('.remove-row-btn')) {
        const btn = e.target.closest('.remove-row-btn');
        removeRow(btn);
      }
    });

    // Setup file uploads
    setupFileInputs();

    // Save on input change
    document.getElementById('satForm')?.addEventListener('input', saveState);
  }

  function setupAddButtons() {
    // Use single event delegation for all add buttons
    document.addEventListener('click', function(e) {
      // Prevent multiple handlers by checking if we've already handled this event
      if (e.defaultPrevented) return;
      
      // Check if clicked element is an add button
      const addButton = e.target.closest('.btn-add');
      if (addButton) {
        e.preventDefault();
        e.stopPropagation();

        // Get the onclick attribute and extract the function call
        const onclickAttr = addButton.getAttribute('onclick');
        if (onclickAttr) {
          // Extract template and tbody IDs from onclick
          const matches = onclickAttr.match(/addRow\('([^']+)',\s*'([^']+)'\)/);
          if (matches) {
            const templateId = matches[1];
            const tbodyId = matches[2];
            addRow(templateId, tbodyId);
          }
        } else {
          // Handle specific button IDs for backward compatibility
          const buttonMappings = [
            { btnId: 'add-related-doc-btn', tmplId: 'tmpl-related-doc', tbodyId: 'related-documents-body' },
            { btnId: 'add-pre-approval-btn', tmplId: 'tmpl-pre-approval', tbodyId: 'pre-approvals-body' },
            { btnId: 'add-post-approval-btn', tmplId: 'tmpl-post-approval', tbodyId: 'post-approvals-body' },
            { btnId: 'add-pretest-btn', tmplId: 'tmpl-pretest', tbodyId: 'pretest-body' },
            { btnId: 'add-keycomp-btn', tmplId: 'tmpl-keycomp', tbodyId: 'key-components-body' },
            { btnId: 'add-iprecord-btn', tmplId: 'tmpl-iprecord', tbodyId: 'ip-records-body' },
            { btnId: 'add-digital-signal-btn', tmplId: 'tmpl-digital-signal', tbodyId: 'digital-signals-body' },
            { btnId: 'add-digital-output-btn', tmplId: 'tmpl-digital-output', tbodyId: 'digital-outputs-body' },
            { btnId: 'add-analogue-input-btn', tmplId: 'tmpl-analogue-input', tbodyId: 'analogue-inputs-body' },
            { btnId: 'add-analogue-output-btn', tmplId: 'tmpl-analogue-output', tbodyId: 'analogue-outputs-body' },
            { btnId: 'add-modbus-digital-btn', tmplId: 'tmpl-modbus-digital', tbodyId: 'modbus-digital-body' },
            { btnId: 'add-modbus-analogue-btn', tmplId: 'tmpl-modbus-analogue', tbodyId: 'modbus-analogue-body' },
            { btnId: 'add-process-test-btn', tmplId: 'tmpl-process-test', tbodyId: 'process-test-body' },
            { btnId: 'add-scada-ver-btn', tmplId: 'tmpl-scada-verification', tbodyId: 'scada-verification-body' },
            { btnId: 'add-trends-testing-btn', tmplId: 'tmpl-trends-testing', tbodyId: 'trends-testing-body' },
            { btnId: 'add-alarm-list-btn', tmplId: 'tmpl-alarm-list', tbodyId: 'alarm-body' }
          ];

          const mapping = buttonMappings.find(m => 
            addButton.id === m.btnId || addButton.closest(`#${m.btnId}`)
          );
          
          if (mapping) {
            addRow(mapping.tmplId, mapping.tbodyId);
          }
        }
        return;
      }
    });
  }

  function setupFileInputs() {
    // Setup file inputs with image preview
    setupFileInput('scada-input', 'scada-file-list');
    setupFileInput('trends-input', 'trends-file-list');
    setupFileInput('alarm-input', 'alarm-file-list');
  }

  function setupFileInput(inputId, listId) {
    const input = document.getElementById(inputId);
    const listEl = document.getElementById(listId);
    if (!input || !listEl) return;

    // Store files in a custom property to maintain them across selections
    if (!input._accumulatedFiles) {
      input._accumulatedFiles = [];
    }

    input.addEventListener('change', (e) => {
      // Get newly selected files
      const newFiles = Array.from(e.target.files);

      // Add new files to accumulated files (avoid duplicates by name)
      newFiles.forEach(newFile => {
        const exists = input._accumulatedFiles.some(existingFile => 
          existingFile.name === newFile.name && existingFile.size === newFile.size
        );
        if (!exists) {
          input._accumulatedFiles.push(newFile);
        }
      });

      // Update the input's files property with accumulated files
      const dt = new DataTransfer();
      input._accumulatedFiles.forEach(file => {
        dt.items.add(file);
      });
      input.files = dt.files;

      // Update the display
      updateFileList(input, listEl);
      saveState();
    });
  }

  function updateFileList(input, listEl) {
    // Clear the display list
    listEl.innerHTML = '';

    // Re-populate with current files in the input
    Array.from(input.files).forEach((file, idx) => {
      const li = document.createElement('li');
      li.dataset.fileIndex = idx; // Store the file index for removal

      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = () => {
          const img = document.createElement('img');
          img.src = reader.result;
          img.alt = file.name;
          img.classList.add('preview-thumb');
          li.appendChild(img);
          addFileDetails(li, file, idx);
        };
        reader.readAsDataURL(file);
      } else {
        addFileDetails(li, file, idx);
      }
      listEl.appendChild(li);
    });
  }

  function addFileDetails(li, file, idx) {
    const span = document.createElement('span');
    span.textContent = file.name;
    span.classList.add('file-name');
    li.appendChild(span);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Remove';
    btn.classList.add('remove-file-btn');
    btn.addEventListener('click', () => {
      const input = li.closest('ul').previousElementSibling;
      const fileIndex = parseInt(li.dataset.fileIndex);
      removeFile(input, fileIndex);
    });

    li.appendChild(btn);
  }

  function removeFile(input, removeIndex) {
    try {
      // Remove from accumulated files array
      if (input._accumulatedFiles && input._accumulatedFiles[removeIndex]) {
        input._accumulatedFiles.splice(removeIndex, 1);
      }

      // Update the input's files property
      const dt = new DataTransfer();
      if (input._accumulatedFiles) {
        input._accumulatedFiles.forEach(file => {
          dt.items.add(file);
        });
      } else {
        // Fallback to current files if accumulated files not available
        Array.from(input.files).forEach((file, i) => {
          if (i !== removeIndex) {
            dt.items.add(file);
          }
        });
      }

      // Update the input's files
      input.files = dt.files;

      // Update the display
      const listEl = input.nextElementSibling;
      if (listEl && listEl.classList.contains('file-list')) {
        updateFileList(input, listEl);
      }

      // Save state after removal
      saveState();

    } catch (error) {
      console.error('Error removing file:', error);
      // Fallback: trigger change event to refresh the list
      input.dispatchEvent(new Event('change'));
    }
  }

  // Initialize the form
  window.addEventListener('DOMContentLoaded', () => {
    loadState();
    goToStep(1);
    setupEventHandlers();
    setupFileInputs();

    // Initialize rich text editors
    setTimeout(() => {
      setupRichTextEditor();
      setupAISuggestions();
    }, 500);
  });

  // Expose public methods
  window.startProcess = startProcess;
  window.showSATForm = showSATForm;
  window.backToWelcome = backToWelcome;
  window.goToStep = goToStep;
  window.addRow = addRow;
  window.removeRow = removeRow;
  window.handleFormSubmit = handleFormSubmit;

  // Utility function for debouncing
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // Handle form submission with AJAX
  function handleFormSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);
    
    // Show loading state
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Generating Report...';
    }
    
    // Clear previous alerts
    document.querySelectorAll('.alert').forEach(alert => alert.remove());
    
    fetch(form.action, {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Show success message
        showAlert(data.message, 'success');
        
        // Clear localStorage to prevent auto-population
        localStorage.removeItem('satFormState');
        
        // Redirect to status page after short delay
        setTimeout(() => {
          window.location.href = data.redirect_url;
        }, 1500);
      } else {
        throw new Error(data.message || 'Generation failed');
      }
    })
    .catch(error => {
      console.error('Form submission error:', error);
      showAlert('Error generating report: ' + error.message, 'error');
    })
    .finally(() => {
      // Restore button state
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa fa-check"></i> Generate SAT Report';
      }
    });
    
    return false;
  }
  
  // Show alert messages
  function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
      <i class="fa fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'}"></i>
      ${message}
    `;
    
    // Insert at top of form
    const form = document.getElementById('satForm');
    if (form) {
      form.insertBefore(alertDiv, form.firstChild);
      
      // Auto-remove after 5 seconds for success messages
      if (type === 'success') {
        setTimeout(() => alertDiv.remove(), 5000);
      }
    }
  }

  // Rich text editor setup
  function getSatContextForAI() {
    const context = {};
    const docTitle = document.getElementById('document_title');
    const clientInput = document.getElementById('client_name');
    const projectRef = document.getElementById('project_reference');
    if (docTitle && docTitle.value) context.document_title = docTitle.value.trim();
    if (clientInput && clientInput.value) context.client_name = clientInput.value.trim();
    if (projectRef && projectRef.value) context.project_reference = projectRef.value.trim();
    if (purposeEditorEl) context.current_purpose = purposeEditorEl.innerText.trim();
    if (scopeEditorEl) context.current_scope = scopeEditorEl.innerText.trim();
    return context;
  }

  function convertTextToHtml(text) {
    const trimmed = text.trim();
    if (!trimmed) {
      return '<p><br></p>';
    }
    const paragraphs = trimmed.split(/\n{2,}/).map(part => part.trim()).filter(Boolean);
    return paragraphs.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
  }

  function applyAISuggestion(field, suggestion) {
    const html = convertTextToHtml(suggestion);
    if (field === 'purpose' && purposeEditorEl && purposeTextareaEl) {
      purposeEditorEl.innerHTML = html;
      purposeTextareaEl.value = purposeEditorEl.innerHTML;
      purposeEditorEl.dispatchEvent(new Event('input'));
    } else if (field === 'scope' && scopeEditorEl && scopeTextareaEl) {
      scopeEditorEl.innerHTML = html;
      scopeTextareaEl.value = scopeEditorEl.innerHTML;
      scopeEditorEl.dispatchEvent(new Event('input'));
    }
  }

  async function requestAISuggestion(field, button) {
    const feedback = document.querySelector(`.ai-feedback[data-field="${field}"]`);
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : null;
    const context = getSatContextForAI();
    const payload = { field, context };

    if (button) {
      button.disabled = true;
      button.classList.add('loading');
    }
    if (feedback) {
      feedback.textContent = 'Generating suggestion...';
    }

    try {
      const response = await fetch('/ai/sat/suggest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json();
      if (!response.ok || !result.suggestion) {
        throw new Error(result.error || 'AI request failed');
      }

      applyAISuggestion(field, result.suggestion);
      if (feedback) {
        feedback.textContent = 'Suggestion applied';
        setTimeout(() => (feedback.textContent = ''), 4000);
      }
    } catch (error) {
      console.error('AI suggestion error', error);
      if (feedback) {
        feedback.textContent = error.message || 'AI request failed';
      }
    } finally {
      if (button) {
        button.disabled = false;
        button.classList.remove('loading');
      }
    }
  }

  function setupAISuggestions() {
    const buttons = document.querySelectorAll('.ai-suggest-btn');
    if (!buttons.length) {
      return;
    }
    buttons.forEach((button) => {
      button.addEventListener('click', () => {
        const field = button.dataset.field;
        if (!field) {
          return;
        }
        requestAISuggestion(field.toLowerCase(), button);
      });
    });
  }

  function setupRichTextEditor() {
    console.log('Setting up rich text editors...');

    // Set up Purpose editor
    purposeEditorEl = document.getElementById('purpose-editor');
    purposeTextareaEl = document.getElementById('purpose');
        const purposeToolbar = document.querySelector('[data-target="purpose-editor"]');

    if (purposeEditorEl && purposeTextareaEl) {
      console.log('Initializing Purpose editor');
      initializeEditor(purposeEditorEl, purposeTextareaEl, purposeToolbar);
    }

    // Set up Scope editor
    scopeEditorEl = document.getElementById('scope-editor');
    scopeTextareaEl = document.getElementById('scope');
    const scopeToolbar = document.querySelector('[data-target="scope-editor"]');

    if (scopeEditorEl && scopeTextareaEl) {
      console.log('Initializing Scope editor');
      initializeEditor(scopeEditorEl, scopeTextareaEl, scopeToolbar);
    }
  }

  function initializeEditor(editor, textarea, toolbar) {
    // Make editor contenteditable
    editor.contentEditable = true;
    editor.style.outline = 'none';

    // Load initial content
    if (textarea.value) {
      editor.innerHTML = textarea.value;
    } else {
      editor.innerHTML = '<p><br></p>';
    }

    // Set up toolbar if it exists
    if (toolbar) {
      setupEditorToolbar(toolbar, editor, textarea);
    }

    // Sync content changes
    editor.addEventListener('input', () => {
      textarea.value = editor.innerHTML;
    });

    // Handle paste events
    editor.addEventListener('paste', (e) => {
      e.preventDefault();
      const text = (e.originalEvent || e).clipboardData.getData('text/plain');
      document.execCommand('insertText', false, text);
      textarea.value = editor.innerHTML;
    });
  }

  function setupEditorToolbar(toolbar, editor, textarea) {
    // Handle toolbar button clicks
    toolbar.addEventListener('click', (e) => {
      e.preventDefault();
      const button = e.target.closest('.toolbar-btn');
      if (!button) return;

      const command = button.dataset.command;
      const value = button.dataset.value;

      editor.focus();

      try {
        if (command === 'formatBlock') {
          document.execCommand(command, false, value);
        } else if (command === 'foreColor' || command === 'hiliteColor') {
          const color = value || button.dataset.value;
          document.execCommand(command, false, color);
        } else {
          document.execCommand(command, false, value);
        }

        // Update textarea
        textarea.value = editor.innerHTML;

        // Update button states
        updateToolbarButtons(toolbar);

      } catch (error) {
        console.error('Command failed:', command, error);
      }
    });

    // Handle color picker changes
    const colorPickers = toolbar.querySelectorAll('.color-picker');
    colorPickers.forEach(picker => {
      picker.addEventListener('change', (e) => {
        editor.focus();
        const command = picker.dataset.command;
        document.execCommand(command, false, e.target.value);
        textarea.value = editor.innerHTML;
      });
    });

  }

})();


    // Global variables
    let currentStep = 1;
    const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000;
    let heartbeatTimer = null;

    function getCsrfToken() {
      const csrfInput = document.querySelector('input[name=\"csrf_token\"]');
      return csrfInput ? csrfInput.value : '';
    }

    function startSessionHeartbeat() {
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
      }
      sendSessionHeartbeat();
      heartbeatTimer = setInterval(sendSessionHeartbeat, HEARTBEAT_INTERVAL_MS);
    }

    async function sendSessionHeartbeat() {
      try {
        const headers = {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        };
        const csrfToken = getCsrfToken();
        if (csrfToken) {
          headers['X-CSRFToken'] = csrfToken;
        }

        const response = await fetch('/auth/session/heartbeat', {
          method: 'POST',
          credentials: 'same-origin',
          headers,
          body: JSON.stringify({ timestamp: Date.now() })
        });

        if (response.status === 401) {
          window.location.href = '/login';
        }
      } catch (error) {
        console.warn('Session heartbeat failed', error);
      }
    }

    // Initialize the application
    document.addEventListener('DOMContentLoaded', function() {
      console.log('SAT Report Generator initialized');
      initializeForm();
      setupFileInputs(); // Call setupFileInputs here
      startSessionHeartbeat();
    });

    // Refresh CSRF token when user returns to page
    document.addEventListener('visibilitychange', function() {
      if (!document.hidden) {
        refreshCSRFToken();
          sendSessionHeartbeat();
      }
    });

    // Step navigation with enhanced progress states
    function goToStep(step) {
      // Auto-save progress before navigating to ensure data isn't lost
      autoSaveProgress();
      
      sendSessionHeartbeat();
      
      // Hide current step
      document.getElementById(`step-${currentStep}`).classList.remove('active');

      // Show new step
      currentStep = step;
      document.getElementById(`step-${currentStep}`).classList.add('active');

      // Update progress steps with completed/active/disabled states
      for (let i = 1; i <= 10; i++) {
        const progStep = document.getElementById(`prog-${i}`);
        if (progStep) {
          // Remove all state classes
          progStep.classList.remove('active', 'completed', 'disabled');

          // Add appropriate state class
          if (i < step) {
            progStep.classList.add('completed');
          } else if (i === step) {
            progStep.classList.add('active');
          } else {
            progStep.classList.add('disabled');
          }
        }
      }

      // Update progress connector line
      updateProgressLine(step);

      // Scroll to top smoothly
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Event delegation for progress step clicks
    document.addEventListener('click', function(e) {
      const progressStep = e.target.closest('.progress-step');
      if (progressStep && progressStep.dataset.step) {
        const step = parseInt(progressStep.dataset.step, 10);
        if (!progressStep.classList.contains('disabled')) {
          goToStep(step);
        }
      }
    });

    // Update the progress connector line based on completion
    function updateProgressLine(currentStep) {
      const progressNav = document.querySelector('.progress-nav');
      if (progressNav) {
        const completionPercentage = ((currentStep - 1) / 9) * 100; // 9 is max steps - 1
        progressNav.style.setProperty('--progress-completion', `${completionPercentage}%`);
      }
    }

    // Form functionality
    function initializeForm() {
      // Check if this is a new report vs editing an existing one
      const formModeData = document.getElementById('form-mode-data');
      if (formModeData) {
        const isNewReport = JSON.parse(formModeData.getAttribute('data-is-new-report') || 'true');
        const currentSubmissionId = formModeData.getAttribute('data-submission-id') || '';
        
        if (isNewReport) {
          // Clear localStorage for new reports to ensure clean state
          console.log('New report detected - clearing localStorage');
          localStorage.removeItem('satFormProgress');
          localStorage.removeItem('satFormSubmissionId');
        } else {
          // For existing reports, check if localStorage is from a different report
          const storedSubmissionId = localStorage.getItem('satFormSubmissionId');
          // Clear localStorage if no stored ID (legacy case) or if it doesn't match current report
          if (!storedSubmissionId || storedSubmissionId !== currentSubmissionId) {
            console.log('Different or legacy report detected - clearing stale localStorage');
            localStorage.removeItem('satFormProgress');
            localStorage.removeItem('satFormSubmissionId');
          }
          // Store current submission ID for future reference
          if (currentSubmissionId) {
            localStorage.setItem('satFormSubmissionId', currentSubmissionId);
          }
          console.log('Editing existing report:', currentSubmissionId);
        }
      }
      
      // Initialize signature pad if available
      if (typeof SignaturePad !== 'undefined') {
        const canvas = document.getElementById('fixed_signature_canvas');
        if (canvas) {
          window.signaturePadInstance = new SignaturePad(canvas, {
            minWidth: 1,
            maxWidth: 2.5,
            penColor: "black",
            backgroundColor: "rgba(255, 255, 255, 0)"
          });

          document.getElementById('fixed_clear_btn').addEventListener('click', function() {
            window.signaturePadInstance.clear();
          });
        }
      }

      // Initialize rich text editors
      initializeRichTextEditors();

      // Initialize approval dropdowns
      initializeApprovalDropdowns();
      
      // Populate approver display fields when editing
      const approver1Email = document.getElementById('approver_1_email');
      const approver2Email = document.getElementById('approver_2_email');
      
      if (approver1Email && approver1Email.value) {
        const display1 = document.getElementById('approver_1_email_display');
        if (display1) {
          display1.value = approver1Email.value;
          display1.style.backgroundColor = '#fff';
        }
      }
      
      if (approver2Email && approver2Email.value) {
        const display2 = document.getElementById('approver_2_email_display');
        if (display2) {
          display2.value = approver2Email.value;
          display2.style.backgroundColor = '#fff';
        }
      }

      // Auto-refresh CSRF token every 10 minutes (more frequent)
      setInterval(refreshCSRFToken, 10 * 60 * 1000);

      // Refresh CSRF token when user interacts with the form after being idle
      let lastInteraction = Date.now();
      document.addEventListener('click', function() {
        const now = Date.now();
        // If user was idle for more than 5 minutes, refresh token
        if (now - lastInteraction > 5 * 60 * 1000) {
          refreshCSRFToken().catch(error => {
            console.warn('Background CSRF refresh failed:', error);
          });
        }
        lastInteraction = now;
      });

      // Form submission handler with CSRF error handling
      document.getElementById('satForm').addEventListener('submit', async function(e) {
        e.preventDefault(); // Always prevent default submission first

        if (currentStep === 10 && window.signaturePadInstance) {
          if (window.signaturePadInstance.isEmpty()) {
            alert('Please provide your signature before submitting.');
            return;
          }
          document.getElementById('sig_prepared_data').value =
            window.signaturePadInstance.toDataURL('image/png');
        }

        // Show loading state
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating Report...';
        submitBtn.disabled = true;

        try {
          // Refresh CSRF token and wait for completion
          await refreshCSRFToken();
          sendSessionHeartbeat();
          console.log('CSRF token refreshed before submission');

          // Now submit the form
          this.submit();
        } catch (error) {
          console.error('Failed to refresh CSRF token before submission:', error);
          // Reset button state
          submitBtn.innerHTML = originalText;
          submitBtn.disabled = false;
          alert('Session expired. Please refresh the page and try again.');
        }
      });
    }

    // Auto-refresh CSRF token
    async function refreshCSRFToken() {
      try {
        const response = await fetch('/refresh_csrf', {
          method: 'GET',
          credentials: 'same-origin',
          headers: {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.csrf_token) {
          const csrfInput = document.querySelector('input[name="csrf_token"]');
          if (csrfInput) {
            csrfInput.value = data.csrf_token;
            console.log('CSRF token refreshed successfully:', data.csrf_token.substring(0, 20) + '...');
          } else {
            throw new Error('CSRF input field not found');
          }
        } else {
          throw new Error('No CSRF token received from server');
        }
      } catch (error) {
        console.error('Failed to refresh CSRF token:', error);
        throw error; // Re-throw to handle in calling function
      }
    }

    // Initialize rich text editors
    function initializeRichTextEditors() {
      console.log('Initializing rich text editors...');

      // Purpose editor
      const purposeEditor = document.getElementById('purpose-editor');
      const purposeTextarea = document.getElementById('purpose');
      const purposeToolbar = document.querySelector('[data-target="purpose-editor"]');

      // Scope editor
      const scopeEditor = document.getElementById('scope-editor');
      const scopeTextarea = document.getElementById('scope');
      const scopeToolbar = document.querySelector('[data-target="scope-editor"]');

      if (purposeEditor && purposeTextarea) {
        setupRichTextEditor(purposeEditor, purposeTextarea, purposeToolbar);
      }

      if (scopeEditor && scopeTextarea) {
        setupRichTextEditor(scopeEditor, scopeTextarea, scopeToolbar);
      }
    }

    function setupRichTextEditor(editor, textarea, toolbar) {
      // Make editor contenteditable and set outline
      editor.contentEditable = true;
      editor.style.outline = 'none';

      // Initialize with existing content if any
      if (textarea.value && textarea.value.trim() !== '') {
        editor.innerHTML = textarea.value;
      } else {
        editor.innerHTML = '<p><br></p>';
      }

      // Setup toolbar if it exists
      if (toolbar) {
        setupEditorToolbar(toolbar, editor, textarea);
      }

      // Sync editor content to textarea on input
      editor.addEventListener('input', function() {
        textarea.value = editor.innerHTML;
        console.log('Rich text content updated');
      });

      // Handle paste events to preserve formatting
      editor.addEventListener('paste', function(e) {
        e.preventDefault();
        const text = (e.originalEvent || e).clipboardData.getData('text/plain');
        document.execCommand('insertText', false, text);
        textarea.value = editor.innerHTML;
      });

      // Handle key events for better UX
      editor.addEventListener('keydown', function(e) {
        // Handle Enter key to create proper line breaks
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          document.execCommand('insertHTML', false, '<br><br>');
          textarea.value = editor.innerHTML;
        }
      });
    }

    function setupEditorToolbar(toolbar, editor, textarea) {
      // Handle toolbar button clicks via event delegation
      toolbar.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        const button = e.target.closest('.toolbar-btn');
        if (!button) return;

        const command = button.dataset.command;
        const value = button.dataset.value || null;

        // Focus editor first
        editor.focus();

        try {
          // Execute command based on type
          if (command === 'formatBlock' && value) {
            document.execCommand(command, false, value);
          } else if (command === 'foreColor' || command === 'hiliteColor') {
            const color = value || '#000000';
            document.execCommand(command, false, color);
          } else {
            document.execCommand(command, false, value);
          }

          // Update textarea
          textarea.value = editor.innerHTML;

          // Update button states
          updateButtonStates(toolbar, editor);

          console.log(`Command executed: ${command} with value: ${value}`);
        } catch (error) {
          console.error('Command execution failed:', command, error);
        }
      });

      // Color pickers
      const colorPickers = toolbar.querySelectorAll('.color-picker');
      colorPickers.forEach(picker => {
        picker.addEventListener('change', function(e) {
          editor.focus();
          const command = this.dataset.command;
          document.execCommand(command, false, e.target.value);
          textarea.value = editor.innerHTML;
          updateButtonStates(toolbar, editor);
        });
      });

      // Update button states on selection change
      editor.addEventListener('keyup', () => updateButtonStates(toolbar, editor));
      editor.addEventListener('mouseup', () => updateButtonStates(toolbar, editor));
      editor.addEventListener('focus', () => updateButtonStates(toolbar, editor));
    }

    function updateButtonStates(toolbar, editor) {
      const buttons = toolbar.querySelectorAll('.toolbar-btn[data-command]');

      buttons.forEach(button => {
        const command = button.dataset.command;
        button.classList.remove('active');

        try {
          if (document.queryCommandState && document.queryCommandState(command)) {
            button.classList.add('active');
          }
        } catch (e) {
          // Command not supported - ignore
        }
      });
    }



    // Initialize approval dropdowns with name-only selection
    function initializeApprovalDropdowns() {
      console.log('Initializing name-only approval dropdowns...');

      // Load users and populate dropdowns
      fetch('/api/get-users-by-role')
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            console.log('Users loaded successfully:', data.users);

            // Populate Automation Manager dropdown (Automation Manager role) - name only
            const amSelect = document.getElementById('approver_1_name_select');
            if (amSelect && data.users['Automation Manager']) {
              data.users['Automation Manager'].forEach(user => {
                const option = document.createElement('option');
                option.value = user.name;
                option.textContent = user.name;
                option.setAttribute('data-email', user.email);
                amSelect.appendChild(option);
              });
            }

            // Populate Project Manager dropdown (PM role) - name only
            const pmSelect = document.getElementById('approver_2_name_select');
            if (pmSelect && data.users.PM) {
              data.users.PM.forEach(user => {
                const option = document.createElement('option');
                option.value = user.name;
                option.textContent = user.name;
                option.setAttribute('data-email', user.email);
                pmSelect.appendChild(option);
              });
            }

            // Setup event listeners
            setupDropdownListeners();
          }
        })
        .catch(error => {
          console.error('Error loading users:', error);
        });

      console.log('Name-only approval dropdowns initialized successfully');
    }

    function setupDropdownListeners() {
      // Automation Manager selection - name only
      const amSelect = document.getElementById('approver_1_name_select');
      if (amSelect) {
        amSelect.addEventListener('change', function() {
          if (this.value) {
            const selectedOption = this.options[this.selectedIndex];
            const name = selectedOption.value;
            const email = selectedOption.getAttribute('data-email');

            // Update hidden fields
            document.getElementById('approver_1_name').value = name;
            document.getElementById('approver_1_email').value = email;

            // Update email display field
            const emailDisplay = document.getElementById('approver_1_email_display');
            if (emailDisplay) {
              emailDisplay.value = email;
              emailDisplay.style.backgroundColor = '#ffffff';
              emailDisplay.style.cursor = 'text';
            }

            // Update top field
            const topField = document.getElementById('reviewed_by_tech_lead');
            if (topField) {
              topField.value = name;
              topField.style.backgroundColor = '#ffffff';
              topField.style.cursor = 'text';
              topField.removeAttribute('readonly');
            }

            console.log('Updated Automation Manager:', { name, email });
          } else {
            // Clear fields when no selection
            document.getElementById('approver_1_name').value = '';
            document.getElementById('approver_1_email').value = '';

            const emailDisplay = document.getElementById('approver_1_email_display');
            if (emailDisplay) {
              emailDisplay.value = '';
              emailDisplay.placeholder = 'Email will auto-populate when name is selected';
              emailDisplay.style.backgroundColor = '#f8fafc';
              emailDisplay.style.cursor = 'not-allowed';
            }

            const topField = document.getElementById('reviewed_by_tech_lead');
            if (topField) {
              topField.value = '';
              topField.placeholder = 'Will auto-populate from selection below';
              topField.style.backgroundColor = '#f8fafc';
              topField.style.cursor = 'not-allowed';
              topField.setAttribute('readonly', 'readonly');
            }
          }
        });
      }

      // Project Manager selection - name only
      const pmSelect = document.getElementById('approver_2_name_select');
      if (pmSelect) {
        pmSelect.addEventListener('change', function() {
          if (this.value) {
            const selectedOption = this.options[this.selectedIndex];
            const name = selectedOption.value;
            const email = selectedOption.getAttribute('data-email');

            // Update hidden fields
            document.getElementById('approver_2_name').value = name;
            document.getElementById('approver_2_email').value = email;

            // Update email display field
            const emailDisplay = document.getElementById('approver_2_email_display');
            if (emailDisplay) {
              emailDisplay.value = email;
              emailDisplay.style.backgroundColor = '#ffffff';
              emailDisplay.style.cursor = 'text';
            }

            // Update top field
            const topField = document.getElementById('reviewed_by_pm');
            if (topField) {
              topField.value = name;
              topField.style.backgroundColor = '#ffffff';
              topField.style.cursor = 'text';
              topField.removeAttribute('readonly');
            }

            console.log('Updated Project Manager:', { name, email });
          } else {
            // Clear fields when no selection
            document.getElementById('approver_2_name').value = '';
            document.getElementById('approver_2_email').value = '';

            const emailDisplay = document.getElementById('approver_2_email_display');
            if (emailDisplay) {
              emailDisplay.value = '';
              emailDisplay.placeholder = 'Email will auto-populate when name is selected';
              emailDisplay.style.backgroundColor = '#f8fafc';
              emailDisplay.style.cursor = 'not-allowed';
            }

            const topField = document.getElementById('reviewed_by_pm');
            if (topField) {
              topField.value = '';
              topField.placeholder = 'Will auto-populate from selection below';
              topField.style.backgroundColor = '#f8fafc';
              topField.style.cursor = 'not-allowed';
              topField.setAttribute('readonly', 'readonly');
            }
          }
        });
      }
    }

    // Progress save functionality
    function saveProgress() {
      console.log('Saving progress...');

      // Collect form data
      const formData = new FormData(document.getElementById('satForm'));

      // Save to backend
      fetch('/save_progress', {
        method: 'POST',
        body: formData
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          console.log('Progress saved to server:', data);
          
          // Update submission_id field if it was created
          if (data.submission_id) {
            const submissionIdField = document.getElementById('submission_id');
            if (submissionIdField) {
              submissionIdField.value = data.submission_id;
            }
            // Track submission_id in localStorage to prevent cross-report contamination
            localStorage.setItem('satFormSubmissionId', data.submission_id);
          }
          
          // Also save to localStorage as backup (including the submission_id)
          const backupData = {};
          for (let [key, value] of formData.entries()) {
            if (key !== 'csrf_token') {
              backupData[key] = value;
            }
          }
          // Ensure backup includes the latest submission_id
          if (data.submission_id) {
            backupData.submission_id = data.submission_id;
          }
          localStorage.setItem('satFormProgress', JSON.stringify(backupData));

          sendSessionHeartbeat();
          
          alert('Progress saved successfully!');
        } else {
          console.error('Save failed:', data.message);
          alert('Error saving progress: ' + data.message);
        }
      })
      .catch(error => {
        console.error('Error saving progress:', error);
        alert('Error saving progress. Please try again.');
      });
    }

    function autoSaveProgress() {
      const formData = new FormData(document.getElementById('satForm'));
      fetch('/auto_save_progress', {
        method: 'POST',
        body: formData
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          console.log('Auto-saved progress at:', data.timestamp);

          sendSessionHeartbeat();
          
          // Update submission_id field if it was created
          if (data.submission_id) {
            const submissionIdField = document.getElementById('submission_id');
            if (submissionIdField && !submissionIdField.value) {
              submissionIdField.value = data.submission_id;
              // Track submission_id in localStorage to prevent cross-report contamination
              localStorage.setItem('satFormSubmissionId', data.submission_id);
              console.log('Updated submission_id:', data.submission_id);
            }
          }
          
          // Optionally update a UI element to show the last saved time
        } else {
          console.error('Auto-save failed:', data.message);
        }
      })
      .catch(error => {
        console.error('Error during auto-save:', error);
      });
    }

    // Add missing functions that are referenced in the HTML
    function addRow(templateId, tbodyId) {
      console.log(`Adding row: template=${templateId}, tbody=${tbodyId}`);

      const tbody = document.getElementById(tbodyId);
      const template = document.getElementById(templateId);

      if (!tbody || !template) {
        console.error(`Missing elements: tbody=${!!tbody}, template=${!!template}`);
        return;
      }

      const clone = template.content.cloneNode(true);
      tbody.appendChild(clone);
    }

    function removeRow(button) {
      const row = button.closest('tr');
      if (row) {
        row.remove();
      }
    }

    // I/O Builder functions
    let configuredModules = [];
    let currentModuleSpec = null;

    async function lookupModule() {
      const company = document.getElementById('module_company').value;
      const model = document.getElementById('module_model').value;

      if (!company || !model) {
        showStatusMessage('Please select a company and enter a module model', 'warning');
        return;
      }

      const lookupBtn = document.getElementById('lookup_module_btn');
      const originalText = lookupBtn.innerHTML;
      lookupBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Searching...';
      lookupBtn.disabled = true;

      try {
        showStatusMessage(`Searching for ${company} ${model} specifications...`, 'info');

        const response = await fetch('/io-builder/api/module-lookup', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
          },
          body: JSON.stringify({ 
            company: company, 
            model: model 
          })
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Module lookup response:', data);

        if (data.success && data.module) {
          // Store module spec with company and model info
          currentModuleSpec = {
            ...data.module,
            company: company,
            model: model
          };
          displayModuleSpecs(data.module);

          let message = `Found ${company} ${model} specifications`;
          if (data.source === 'database') {
            message += ' in database';
          } else if (data.source === 'web') {
            message += ' online';
          }

          const totalChannels = (data.module.digital_inputs || 0) + (data.module.digital_outputs || 0) + 
                               (data.module.analog_inputs || 0) + (data.module.analog_outputs || 0);

          if (totalChannels > 0) {
            message += ` | DI: ${data.module.digital_inputs || 0}, DO: ${data.module.digital_outputs || 0}, AI: ${data.module.analog_inputs || 0}, AO: ${data.module.analog_outputs || 0}`;
          }

          showStatusMessage(message, 'success');
          document.getElementById('add_module_btn').disabled = false;
        } else {
          showStatusMessage('Module not found. Please enter specifications manually.', 'warning');
          showManualOverride();
        }
      } catch (error) {
        console.error('Module lookup error:', error);
        showStatusMessage('Network error. Please try again or enter specifications manually.', 'error');
        showManualOverride();
      } finally {
        lookupBtn.innerHTML = originalText;
        lookupBtn.disabled = false;
      }
    }

    function displayModuleSpecs(module) {
      // Display the specifications
      document.getElementById('spec_description').textContent = module.description || 'No description';
      document.getElementById('spec_di').textContent = module.digital_inputs || 0;
      document.getElementById('spec_do').textContent = module.digital_outputs || 0;
      document.getElementById('spec_ai').textContent = module.analog_inputs || 0;
      document.getElementById('spec_ao').textContent = module.analog_outputs || 0;

      const total = (module.digital_inputs || 0) + (module.digital_outputs || 0) + 
                   (module.analog_inputs || 0) + (module.analog_outputs || 0);
      document.getElementById('spec_total').textContent = total;

      // Also populate the manual input fields for user convenience
      document.getElementById('manual_di').value = module.digital_inputs || 0;
      document.getElementById('manual_do').value = module.digital_outputs || 0;
      document.getElementById('manual_ai').value = module.analog_inputs || 0;
      document.getElementById('manual_ao').value = module.analog_outputs || 0;

      // Show both the spec display and manual override section
      document.getElementById('module_spec_display').classList.remove('hidden');
      document.getElementById('manual_override').classList.remove('hidden');
    }

    function showManualOverride() {
      document.getElementById('manual_override').classList.remove('hidden');
      document.getElementById('add_module_btn').disabled = false;
    }

    function addModule() {
      const company = document.getElementById('module_company').value;
      const model = document.getElementById('module_model').value;
      const rackNo = parseInt(document.getElementById('module_rack').value) || 0;
      const slotNo = parseInt(document.getElementById('module_position').value) || 1;
      const startSno = parseInt(document.getElementById('module_starting_sno').value) || 1;

      if (!company || !model) {
        showStatusMessage('Please select a company and enter a module model', 'warning');
        return;
      }

      // Always use the values from manual input fields (they may have been edited)
      let moduleSpec = {
        company: company,
        model: model,
        digital_inputs: parseInt(document.getElementById('manual_di').value) || 0,
        digital_outputs: parseInt(document.getElementById('manual_do').value) || 0,
        analog_inputs: parseInt(document.getElementById('manual_ai').value) || 0,
        analog_outputs: parseInt(document.getElementById('manual_ao').value) || 0,
        description: currentModuleSpec ? currentModuleSpec.description : `${company} ${model} - Manual Entry`,
        voltage_range: currentModuleSpec ? currentModuleSpec.voltage_range : '24 VDC',
        current_range: currentModuleSpec ? currentModuleSpec.current_range : '4-20mA'
      };

      const moduleConfig = {
        ...moduleSpec,
        company: company,
        model: model,
        rack_no: rackNo,
        position: slotNo,  // API expects 'position' not 'slot_no'
        start_sno: startSno,
        id: Date.now()
      };

      configuredModules.push(moduleConfig);
      updateModulesList();
      clearModuleForm();

      const total = (moduleSpec.digital_inputs || 0) + (moduleSpec.digital_outputs || 0) + 
                   (moduleSpec.analog_inputs || 0) + (moduleSpec.analog_outputs || 0);

      showStatusMessage(`Module ${company} ${model} added with ${total} I/O points`, 'success');
      document.getElementById('generate_tables_btn').disabled = false;
    }

    function updateModulesList() {
      const container = document.getElementById('modules_container');

      if (configuredModules.length === 0) {
        container.innerHTML = '';
        return;
      }

      let html = '<div class="modules-list"><div class="modules-list-header">Configured Modules</div>';

      configuredModules.forEach((module, index) => {
        const total = (module.digital_inputs || 0) + (module.digital_outputs || 0) + 
                     (module.analog_inputs || 0) + (module.analog_outputs || 0);

        html += `
          <div class="module-item">
            <div class="module-info">
              <div class="module-name">${module.company} ${module.model}</div>
              <div class="module-details">Rack ${module.rack_no}, Slot ${module.slot_no} | Start S.No: ${module.start_sno}</div>
            </div>
            <div class="module-stats">
              <span>DI: ${module.digital_inputs || 0}</span>
              <span>DO: ${module.digital_outputs || 0}</span>
              <span>AI: ${module.analog_inputs || 0}</span>
              <span>AO: ${module.analog_outputs || 0}</span>
              <span>Total: ${total}</span>
            </div>
            <button onclick="removeModule(${index})" class="btn-remove">
              <i class="fa fa-trash"></i>
            </button>
          </div>
        `;
      });

      html += '</div>';
      container.innerHTML = html;

      // Update statistics
      updateModuleStats();
    }

    function removeModule(index) {
      if (confirm('Remove this module?')) {
        configuredModules.splice(index, 1);
        updateModulesList();
        if (configuredModules.length === 0) {
          document.getElementById('generate_tables_btn').disabled = true;
        }
      }
    }

    function updateModuleStats() {
      const totalModules = configuredModules.length;
      let digitalModules = 0, analogModules = 0, mixedModules = 0;

      configuredModules.forEach(module => {
        const hasDigital = (module.digital_inputs || 0) + (module.digital_outputs || 0) > 0;
        const hasAnalog = (module.analog_inputs || 0) + (module.analog_outputs || 0) > 0;

        if (hasDigital && hasAnalog) mixedModules++;
        else if (hasDigital) digitalModules++;
        else if (hasAnalog) analogModules++;
      });

      document.getElementById('total_modules').value = totalModules;
      document.getElementById('digital_modules').value = digitalModules;
      document.getElementById('analog_modules').value = analogModules;
      document.getElementById('mixed_modules').value = mixedModules;

      document.querySelector('.module-stats').classList.toggle('hidden', totalModules === 0);
    }

    function clearModuleForm() {
      document.getElementById('module_company').value = '';
      document.getElementById('module_model').value = '';
      document.getElementById('module_spec_display').classList.add('hidden');
      document.getElementById('manual_override').classList.add('hidden');
      currentModuleSpec = null;
      document.getElementById('add_module_btn').disabled = true;
    }

    async function generateIOTables() {
      if (configuredModules.length === 0) {
        showStatusMessage('Please add at least one module before generating tables', 'warning');
        return;
      }

      const generateBtn = document.getElementById('generate_tables_btn');
      const originalText = generateBtn.innerHTML;
      generateBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Generating...';
      generateBtn.disabled = true;

      try {
        showStatusMessage('Generating I/O testing tables...', 'info');

        const response = await fetch('/io-builder/api/generate-io-table', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
          },
          body: JSON.stringify({ 
            modules: configuredModules 
          })
        });

        const data = await response.json();

        if (data.success) {
          populateIOTables(data.tables);
          showStatusMessage(`Generated ${data.summary.total_points} I/O testing points successfully!`, 'success');
        } else {
          showStatusMessage('Error generating tables: ' + (data.error || 'Unknown error'), 'error');
        }
      } catch (error) {
        console.error('Generation error:', error);
        showStatusMessage('Network error during table generation. Please try again.', 'error');
      } finally {
        generateBtn.innerHTML = originalText;
        generateBtn.disabled = false;
      }
    }

    function populateIOTables(tables) {
      // Populate Digital Inputs
      if (tables.digital_inputs) {
        populateTableSection('digital-signals-body', tables.digital_inputs, 'digital');
      }

      // Populate Digital Outputs  
      if (tables.digital_outputs) {
        populateTableSection('digital-outputs-body', tables.digital_outputs, 'digital_output');
      }

      // Populate Analog Inputs
      if (tables.analog_inputs) {
        populateTableSection('analogue-inputs-body', tables.analog_inputs, 'analogue_input');
      }

      // Populate Analog Outputs
      if (tables.analog_outputs) {
        populateTableSection('analogue-outputs-body', tables.analog_outputs, 'analogue_output');
      }

      if (tables.data_validation) {
        populateTableSection('data-validation-body', tables.data_validation, 'data_validation');
      }

      showStatusMessage('I/O tables populated in Step 8. You can now continue to testing.', 'success');
    }

    function populateTableSection(tbodyId, data, prefix) {
      const tbody = document.getElementById(tbodyId);
      if (!tbody) return;

      tbody.innerHTML = '';

      data.forEach(item => {
        const row = document.createElement('tr');

        if (prefix === 'digital') {
          row.innerHTML = `
            <td><input name="${prefix}_s_no[]" value="${item.sno}" readonly></td>
            <td><input name="${prefix}_rack[]" value="${item.rack_no}" readonly></td>
            <td><input name="${prefix}_pos[]" value="${item.module_position || item.slot_no}" readonly></td>
            <td><input name="${prefix}_signal_tag[]" value="${item.signal_tag}" readonly></td>
            <td><input name="${prefix}_description[]" value="${item.signal_description}" readonly></td>
            <td><select name="${prefix}_result[]"><option value="">-</option><option value="Pass">Pass</option><option value="Fail">Fail</option><option value="N/A">N/A</option></select></td>
            <td><input name="${prefix}_punch[]" placeholder="Punch Item"></td>
            <td><input name="${prefix}_verified[]" placeholder="Verified By"></td>
            <td><input name="${prefix}_comment[]" placeholder="Comment"></td>
            <td><button type="button" class="btn-remove" onclick="removeRow(this)"><i class="fas fa-trash"></i></button></td>
          `;
        } else if (prefix === 'data_validation') {
          row.innerHTML = `
            <td><input name="${prefix}_tag[]" value="${item.tag || item.Tag || ''}"></td>
            <td><input name="${prefix}_range[]" value="${item.range || item.Range || ''}"></td>
            <td><input name="${prefix}_scada_value[]" value="${item.scada_value || item['SCADA Value'] || ''}"></td>
            <td><input name="${prefix}_hmi_value[]" value="${item.hmi_value || item['HMI Value'] || ''}"></td>
            <td><button type="button" class="btn-remove" onclick="removeRow(this)"><i class="fas fa-trash"></i></button></td>
          `;
        } else {
          row.innerHTML = `
            <td><input name="${prefix}_s_no[]" value="${item.sno}" readonly></td>
            <td><input name="${prefix}_rack_no[]" value="${item.rack_no}" readonly></td>
            <td><input name="${prefix}_module_position[]" value="${item.module_position || item.slot_no}" readonly></td>
            <td><input name="${prefix}_signal_tag[]" value="${item.signal_tag}" readonly></td>
            <td><input name="${prefix}_description[]" value="${item.signal_description}" readonly></td>
            <td><select name="${prefix}_result[]"><option value="">-</option><option value="Pass">Pass</option><option value="Fail">Fail</option><option value="N/A">N/A</option></select></td>
            <td><input name="${prefix}_punch_item[]" placeholder="Punch Item"></td>
            <td><input name="${prefix}_verified_by[]" placeholder="Verified By"></td>
            <td><input name="${prefix}_comment[]" placeholder="Comment"></td>
            <td><button type="button" class="btn-remove" onclick="removeRow(this)"><i class="fas fa-trash"></i></button></td>
          `;
        }

        tbody.appendChild(row);
      });
    }

    function addModbusRange() {
      console.log('Adding Modbus range...');
      // Modbus range addition logic would go here
    }

    function previewTables() {
      if (configuredModules.length === 0) {
        showStatusMessage('Please add at least one module first', 'warning');
        return;
      }
      console.log('Preview configured modules:', configuredModules);
    }

    function generateIOTablesFromBuilder() {
      generateIOTables();
    }

    function showStatusMessage(message, type = 'info') {
      // Create or update status message in the generation status div
      const statusDiv = document.getElementById('generation_status');
      const statusText = document.getElementById('status_text');

      if (statusDiv && statusText) {
        statusText.textContent = message;
        statusDiv.className = `generation-status status-${type}`;
        statusDiv.classList.remove('hidden');

        // Auto-hide after 5 seconds for non-error messages
        if (type !== 'error') {
          setTimeout(() => {
            statusDiv.classList.add('hidden');
          }, 5000);
        }
      } else {
        // Fallback to alert if status div not found
        console.log(`${type.toUpperCase()}: ${message}`);
      }
    }

    function getCSRFToken() {
      const metaToken = document.querySelector('meta[name=csrf-token]');
      if (metaToken) {
        return metaToken.getAttribute('content');
      }

      const hiddenToken = document.querySelector('input[name=csrf_token]');
      if (hiddenToken) {
        return hiddenToken.value;
      }

      console.warn('CSRF token not found');
      return '';
    }

    const uploadManagers = {};

    // Setup file input handlers and previews
    function setupFileInputs() {
      const configs = [
        { scope: 'scada', inputId: 'scada-input', previewContainerId: 'scada-file-list', queueContainerId: 'scada-queue' },
        { scope: 'trends', inputId: 'trends-input', previewContainerId: 'trends-file-list', queueContainerId: 'trends-queue' },
        { scope: 'alarm', inputId: 'alarm-input', previewContainerId: 'alarm-file-list', queueContainerId: 'alarm-queue' }
      ];

      configs.forEach((config) => {
        const manager = createUploadManager(config);
        if (manager) {
          uploadManagers[config.scope] = manager;
        }
      });
    }

    function createUploadManager({ scope, inputId, previewContainerId, queueContainerId }) {
      const input = document.getElementById(inputId);
      const previewContainer = document.getElementById(previewContainerId);
      const queueContainer = document.getElementById(queueContainerId);
      const dropzone = document.querySelector(`[data-dropzone-for="${inputId}"]`);

      if (!input || !previewContainer || !queueContainer) {
        console.warn(`Upload manager skipped for ${scope}: missing required elements.`);
        return null;
      }

      const items = [];
      const supportsDataTransfer = typeof window.DataTransfer !== 'undefined';
      const existingWrapper = previewContainer.querySelector('[data-existing-previews]');
      if (existingWrapper && !existingWrapper.children.length) {
        existingWrapper.setAttribute('hidden', '');
      }

      function addFiles(list) {
        const files = Array.from(list || []);
        if (!files.length) {
          return;
        }

        let added = false;
        files.forEach((file) => {
          const signature = createFileSignature(file);
          if (items.some((item) => item.signature === signature)) {
            return;
          }

          const uploadItem = {
            id: (window.crypto && typeof window.crypto.randomUUID === 'function')
              ? window.crypto.randomUUID()
              : `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            file,
            signature,
            status: 'pending',
            progress: 0,
            preview: '',
            error: null,
            createdAt: Date.now()
          };

          items.push(uploadItem);
          readPreview(uploadItem);
          added = true;
        });

        if (added) {
          syncFileInput();
          renderQueue();
        }
      }

      function readPreview(item) {
        const reader = new FileReader();
        reader.onprogress = (event) => {
          if (event.lengthComputable && event.total) {
            const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
            if (percent > item.progress) {
              item.progress = percent;
              if (item.status === 'pending') {
                item.status = 'processing';
              }
              renderQueue();
            }
          }
        };
        reader.onload = () => {
          item.preview = reader.result;
          item.status = 'ready';
          item.progress = 100;
          renderQueue();
        };
        reader.onerror = () => {
          item.error = 'Preview generation failed';
          item.status = 'error';
          item.progress = 0;
          renderQueue();
        };
        reader.readAsDataURL(item.file);
      }

      function renderQueue() {
        queueContainer.innerHTML = '';

        if (!items.length) {
          const emptyState = document.createElement('div');
          emptyState.className = 'file-queue-empty';
          emptyState.textContent = 'No new files added yet.';
          queueContainer.appendChild(emptyState);
          return;
        }

        items.forEach((item) => {
          queueContainer.appendChild(buildQueueItem(item));
        });
      }

      function buildQueueItem(item) {
        const node = document.createElement('div');
        node.className = 'file-queue-item';
        node.dataset.uploadId = item.id;

        const thumb = document.createElement('div');
        thumb.className = 'file-queue-thumb';
        if (item.preview) {
          const img = document.createElement('img');
          img.src = `${item.preview}#${item.createdAt}`;
          img.alt = `${item.file.name} preview`;
          thumb.appendChild(img);
        } else {
          thumb.innerHTML = '<i class="fas fa-image" aria-hidden="true"></i>';
        }

        const meta = document.createElement('div');
        meta.className = 'file-queue-meta';

        const name = document.createElement('span');
        name.className = 'file-queue-name';
        name.textContent = item.file.name;
        meta.appendChild(name);

        const details = document.createElement('span');
        details.className = 'file-queue-details';
        details.textContent = `${formatBytes(item.file.size)} | ${getStatusLabel(item)}`;
        meta.appendChild(details);

        const progressBar = document.createElement('div');
        progressBar.className = 'file-progress';
        progressBar.setAttribute('role', 'progressbar');
        progressBar.setAttribute('aria-valuemin', '0');
        progressBar.setAttribute('aria-valuemax', '100');
        progressBar.setAttribute('aria-valuenow', String(item.progress));
        const progressValue = document.createElement('div');
        progressValue.className = 'file-progress-value';
        progressValue.style.width = `${item.progress}%`;
        progressBar.appendChild(progressValue);
        meta.appendChild(progressBar);

        const status = document.createElement('span');
        status.className = `file-status file-status--${item.status}`;
        status.textContent = getStatusLabel(item);
        meta.appendChild(status);

        if (item.error) {
          const error = document.createElement('span');
          error.className = 'file-error';
          error.textContent = item.error;
          meta.appendChild(error);
        }

        const actions = document.createElement('div');
        actions.className = 'file-queue-actions';

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'file-remove-btn';
        removeBtn.setAttribute('aria-label', `Remove ${item.file.name}`);
        removeBtn.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
        removeBtn.addEventListener('click', () => removeItem(item.id));
        actions.appendChild(removeBtn);

        node.appendChild(thumb);
        node.appendChild(meta);
        node.appendChild(actions);

        return node;
      }

      function removeItem(id) {
        const index = items.findIndex((item) => item.id === id);
        if (index === -1) {
          return;
        }

        items.splice(index, 1);
        syncFileInput();
        renderQueue();
      }

      function syncFileInput() {
        if (!supportsDataTransfer) {
          console.warn('DataTransfer API not supported; multi-select persistence may be limited.');
          return;
        }

        const dataTransfer = new DataTransfer();
        items
          .filter((item) => item.status !== 'error')
          .forEach((item) => {
            dataTransfer.items.add(item.file);
          });
        input.files = dataTransfer.files;
      }

      function handleDragEnter(event) {
        event.preventDefault();
        if (dropzone) {
          dropzone.classList.add('is-dragover');
        }
      }

      function handleDragLeave(event) {
        event.preventDefault();
        if (dropzone) {
          dropzone.classList.remove('is-dragover');
        }
      }

      function handleDrop(event) {
        event.preventDefault();
        if (dropzone) {
          dropzone.classList.remove('is-dragover');
        }
        if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length) {
          addFiles(event.dataTransfer.files);
        }
      }

      input.addEventListener('change', (event) => addFiles(event.target.files));

      if (dropzone) {
        ['dragenter', 'dragover'].forEach((type) => dropzone.addEventListener(type, handleDragEnter));
        ['dragleave', 'dragend'].forEach((type) => dropzone.addEventListener(type, handleDragLeave));
        dropzone.addEventListener('drop', handleDrop);
        dropzone.addEventListener('click', () => input.click());
        dropzone.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            input.click();
          }
        });
      }

      previewContainer.addEventListener('dragover', (event) => event.preventDefault());
      previewContainer.addEventListener('drop', handleDrop);

      renderQueue();

      return {
        add: addFiles,
        remove: removeItem,
        getFiles: () => items.map((item) => item.file),
        clear: () => {
          items.length = 0;
          syncFileInput();
          renderQueue();
        }
      };
    }

    function createFileSignature(file) {
      return [file.name, file.size, file.lastModified].join(':');
    }

    function getStatusLabel(item) {
      if (item.error) {
        return 'Error';
      }

      if (item.status === 'processing') {
        return 'Analyzing';
      }

      if (item.status === 'ready') {
        return 'Ready';
      }

      return 'Pending';
    }

    function formatBytes(bytes) {
      if (bytes === 0) {
        return '0 B';
      }
      if (!bytes) {
        return '0 B';
      }
      const units = ['B', 'KB', 'MB', 'GB'];
      let size = bytes;
      let unitIndex = 0;
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
      }
      const precision = unitIndex === 0 ? 0 : 1;
      return `${size.toFixed(precision)} ${units[unitIndex]}`;
    }


    // Function to remove existing images
    async function removeExistingImage(imageUrl, removedFieldName, evt) {
      const activeEvent = evt || window.event;
      const imagePreview = activeEvent.target.closest('.image-preview');
      const removeButton = activeEvent.target;

      // Disable button to prevent multiple clicks
      removeButton.disabled = true;
      removeButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      try {
        const response = await fetch('/api/v1/files/delete_image', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({
            image_url: imageUrl,
            field_name: removedFieldName
          })
        });

        const data = await response.json();

        if (data.success) {
          // Update the hidden field
          const removedField = document.getElementById(removedFieldName);
          if (removedField) {
            let removedList = removedField.value ? removedField.value.split(',') : [];
            if (!removedList.includes(imageUrl)) {
              removedList.push(imageUrl);
              removedField.value = removedList.join(',');
            }
          }

          // Remove the image preview from the DOM
          if (imagePreview) {
            imagePreview.remove();
            const wrapper = imagePreview.parentElement;
            if (wrapper && wrapper.hasAttribute('data-existing-previews') && !wrapper.querySelector('.image-preview')) {
              wrapper.setAttribute('hidden', '');
            }
          }
          console.log('Image removed successfully:', imageUrl);
        } else {
          throw new Error(data.message || 'Failed to delete image.');
        }
      } catch (error) {
        console.error('Error removing image:', error);
        alert(`Error: ${error.message}`);
        // Re-enable button if deletion fails
        removeButton.disabled = false;
        removeButton.innerHTML = 'X';
      }
    }

    // Helper function to show loading state
    function showLoadingState() {
      const submitBtn = document.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        submitBtn.disabled = true;
      }
    }

    // Helper function to hide loading state
    function hideLoadingState() {
      const submitBtn = document.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Generate Report';
        submitBtn.disabled = false;
      }
    }

    // Helper function to show messages
    function showMessage(message, type) {
      // This function could be enhanced to display messages in a more user-friendly way,
      // e.g., using flash messages or a toast notification system.
      // For now, we'll use alert.
      alert(`${type.toUpperCase()}: ${message}`);
    }

  


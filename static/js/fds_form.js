// Lightweight form controller for the FDS wizard
(function () {
  let currentStep = 1;
  const STORAGE_PREFIX = 'fds-progress-';

  function getTotalSteps() {
    return document.querySelectorAll('.form-step').length;
  }

  function setActiveStep(step) {
    document.querySelectorAll('.form-step').forEach((fieldset, index) => {
      const stepIndex = index + 1;
      fieldset.classList.toggle('active', stepIndex === step);
    });

    document.querySelectorAll('.progress-step').forEach((indicator, index) => {
      const indicatorStep = index + 1;
      indicator.classList.toggle('active', indicatorStep === step);
      indicator.classList.toggle('disabled', indicatorStep > step);
    });
  }

  function validateCurrentStep(targetStep) {
    if (targetStep <= currentStep) {
      return true;
    }

    const currentFieldset = document.getElementById(`step-${currentStep}`);
    if (!currentFieldset) {
      return true;
    }

    if (currentFieldset.checkValidity()) {
      return true;
    }

    currentFieldset.classList.add('invalid');
    const invalidField = currentFieldset.querySelector(':invalid');
    if (invalidField) {
      invalidField.focus();
    }

    return false;
  }

  function goToStep(step) {
    const total = getTotalSteps();
    const target = Number(step);
    if (!target || target < 1 || target > total) {
      return;
    }

    if (!validateCurrentStep(target)) {
      return;
    }

    currentStep = target;
    setActiveStep(currentStep);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function cloneTemplateRow(templateId) {
    const template = document.getElementById(templateId);
    if (!template) {
      return null;
    }

    if (template.content) {
      return template.content.firstElementChild.cloneNode(true);
    }

    // Fallback for browsers without template.content support
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = template.innerHTML.trim();
    return tempDiv.firstElementChild;
  }

  function addRow(templateId, tbodyId) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) {
      return;
    }

    const row = cloneTemplateRow(templateId);
    if (!row) {
      return;
    }

    tbody.appendChild(row);
  }

  function removeRow(button) {
    const row = button?.closest('tr');
    if (row) {
      row.remove();
    }
  }

  function getSubmissionId() {
    return document.querySelector('input[name="submission_id"]')?.value || '';
  }

  function showAlert(message, type) {
    const form = document.getElementById('fdsForm');
    if (!form) {
      return;
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    const icon =
      type === 'success'
        ? 'check-circle'
        : type === 'info'
          ? 'info-circle'
          : 'exclamation-triangle';
    alert.innerHTML = `
      <i class="fa fa-${icon}"></i>
      ${message}
    `;

    const existingAlerts = form.querySelectorAll('.alert');
    existingAlerts.forEach((node) => node.remove());

    form.prepend(alert);
  }

  function saveProgress(showMessage = true) {
    const form = document.getElementById('fdsForm');
    if (!form) {
      return;
    }

    const submissionId = getSubmissionId();
    if (!submissionId) {
      if (showMessage) {
        showAlert('Missing submission identifier. Unable to save progress.', 'error');
      }
      return;
    }

    const data = {};
    const formData = new FormData(form);
    formData.forEach((value, key) => {
      if (data[key]) {
        if (!Array.isArray(data[key])) {
          data[key] = [data[key]];
        }
        data[key].push(value);
      } else {
        data[key] = value;
      }
    });

    try {
      localStorage.setItem(`${STORAGE_PREFIX}${submissionId}`, JSON.stringify(data));
      if (showMessage) {
        showAlert('Progress saved locally on this device.', 'success');
      }
    } catch (error) {
      console.error('Failed to save FDS progress:', error);
      if (showMessage) {
        showAlert('Unable to save progress locally.', 'error');
      }
    }
  }

  function loadProgress() {
    const form = document.getElementById('fdsForm');
    if (!form) {
      return;
    }

    const submissionId = getSubmissionId();
    if (!submissionId) {
      return;
    }

    const stored = localStorage.getItem(`${STORAGE_PREFIX}${submissionId}`);
    if (!stored) {
      return;
    }

    try {
      const data = JSON.parse(stored);
      Object.entries(data).forEach(([key, value]) => {
        const elements = form.elements[key];
        if (!elements) {
          return;
        }

        if (Array.isArray(value)) {
          const elementArray =
            typeof RadioNodeList !== 'undefined' && elements instanceof RadioNodeList
              ? Array.from(elements)
              : Array.isArray(elements)
                ? elements
                : [elements];
          value.forEach((val, index) => {
            const el = elementArray[index];
            if (el && !el.value) {
              el.value = val;
            }
          });
        } else if (!elements.value) {
          elements.value = value;
        }
      });
      showAlert('Restored saved draft from this device.', 'info');
    } catch (error) {
      console.error('Failed to load FDS progress:', error);
      showAlert('Unable to restore saved progress.', 'error');
    }
  }

  function handleFormSubmit(event) {
    event.preventDefault();

    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';
    }

    fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json'
      }
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) {
          throw new Error(data.message || 'Unable to save report');
        }

        const submissionId = getSubmissionId();
        if (submissionId) {
          localStorage.removeItem(`${STORAGE_PREFIX}${submissionId}`);
        }

        showAlert(data.message || 'FDS saved successfully!', 'success');
        if (data.redirect_url) {
          setTimeout(() => {
            window.location.href = data.redirect_url;
          }, 1200);
        }
      })
      .catch((error) => {
        console.error('FDS submission error:', error);
        showAlert(error.message || 'Unable to save report', 'error');
      })
      .finally(() => {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fas fa-save"></i> Save FDS Draft';
        }
      });

    return false;
  }

  function wireProgressSteps() {
    document.querySelectorAll('.progress-step').forEach((indicator) => {
      indicator.addEventListener('click', () => {
        const step = Number(indicator.dataset.step);
        if (Number.isFinite(step)) {
          goToStep(step);
        }
      });
    });
  }

  function setFieldEditable(field, editable) {
    if (!field) {
      return;
    }
    if (editable) {
      field.removeAttribute('readonly');
      field.style.backgroundColor = '#ffffff';
      field.style.cursor = 'text';
    } else {
      field.setAttribute('readonly', 'readonly');
      field.style.backgroundColor = '#f8fafc';
      field.style.cursor = 'not-allowed';
    }
  }

  function updateEmailDisplay(inputId, value) {
    const input = document.getElementById(inputId);
    if (!input) {
      return;
    }
    input.value = value || '';
    if (value) {
      input.style.backgroundColor = '#ffffff';
      input.style.cursor = 'text';
    } else {
      input.placeholder = 'Email will auto-populate when name is selected';
      input.style.backgroundColor = '#f8fafc';
      input.style.cursor = 'not-allowed';
    }
  }

  function hydrateApprovalDisplays() {
    const reviewer1Field = document.getElementById('reviewed_by_tech_lead');
    if (reviewer1Field && reviewer1Field.value) {
      setFieldEditable(reviewer1Field, true);
    }

    const reviewer2Field = document.getElementById('reviewed_by_pm');
    if (reviewer2Field && reviewer2Field.value) {
      setFieldEditable(reviewer2Field, true);
    }

    updateEmailDisplay('reviewer1_email_display', document.getElementById('reviewer1_email')?.value || '');
    updateEmailDisplay('reviewer2_email_display', document.getElementById('reviewer2_email')?.value || '');
    updateEmailDisplay('approver_1_email_display', document.getElementById('approver_1_email')?.value || '');
    updateEmailDisplay('approver_2_email_display', document.getElementById('approver_2_email')?.value || '');
  }

  function handleApproverSelection({
    select,
    hiddenNameId,
    hiddenEmailId,
    emailDisplayId,
    reviewerFieldId
  }) {
    if (!select) {
      return;
    }

    select.addEventListener('change', () => {
      const hiddenName = document.getElementById(hiddenNameId);
      const hiddenEmail = document.getElementById(hiddenEmailId);
      const reviewerField = document.getElementById(reviewerFieldId);

      if (select.value) {
        const option = select.options[select.selectedIndex];
        const name = option.value;
        const email = option.getAttribute('data-email') || '';

        if (hiddenName) {
          hiddenName.value = name;
        }
        if (hiddenEmail) {
          hiddenEmail.value = email;
        }
        if (reviewerField) {
          reviewerField.value = name;
          setFieldEditable(reviewerField, true);
        }

        updateEmailDisplay(emailDisplayId, email);
      } else {
        if (hiddenName) {
          hiddenName.value = '';
        }
        if (hiddenEmail) {
          hiddenEmail.value = '';
        }
        if (reviewerField) {
          reviewerField.value = '';
          setFieldEditable(reviewerField, false);
        }
        updateEmailDisplay(emailDisplayId, '');
      }
    });
  }

  function preselectApprover(select, storedName) {
    if (!select || !storedName) {
      return;
    }
    Array.from(select.options).forEach((option, index) => {
      if (option.value && option.value === storedName) {
        select.selectedIndex = index;
      }
    });
  }

  function setupApprovalDropdownListeners() {
    handleApproverSelection({
      select: document.getElementById('approver_1_name_select'),
      hiddenNameId: 'approver_1_name',
      hiddenEmailId: 'approver_1_email',
      emailDisplayId: 'approver_1_email_display',
      reviewerFieldId: 'reviewed_by_tech_lead'
    });

    handleApproverSelection({
      select: document.getElementById('approver_2_name_select'),
      hiddenNameId: 'approver_2_name',
      hiddenEmailId: 'approver_2_email',
      emailDisplayId: 'approver_2_email_display',
      reviewerFieldId: 'reviewed_by_pm'
    });
  }

  function populateSelect(select, users) {
    if (!select || !Array.isArray(users)) {
      return;
    }
    users.forEach((user) => {
      if (!user?.name) {
        return;
      }
      const option = document.createElement('option');
      option.value = user.name;
      option.textContent = user.name;
      if (user.email) {
        option.setAttribute('data-email', user.email);
      }
      select.appendChild(option);
    });
  }

  function initializeApprovalDropdowns() {
    const amSelect = document.getElementById('approver_1_name_select');
    const pmSelect = document.getElementById('approver_2_name_select');

    if (!amSelect && !pmSelect) {
      return;
    }

    fetch('/api/get-users-by-role')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to fetch approvers');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error(data?.message || 'Unable to load approvers');
        }

        populateSelect(amSelect, data.users?.['Automation Manager'] || []);
        populateSelect(pmSelect, data.users?.PM || []);

        preselectApprover(amSelect, document.getElementById('approver_1_name')?.value || '');
        preselectApprover(pmSelect, document.getElementById('approver_2_name')?.value || '');
      })
      .catch((error) => {
        console.warn('Approval dropdown setup skipped:', error);
      })
      .finally(() => {
        setupApprovalDropdownListeners();
        hydrateApprovalDisplays();
      });
  }

  document.addEventListener('DOMContentLoaded', () => {
    setActiveStep(currentStep);
    wireProgressSteps();
    loadProgress();
    initializeApprovalDropdowns();

    const form = document.getElementById('fdsForm');
    if (form) {
      form.addEventListener('submit', handleFormSubmit);
    }
  });

  window.goToStep = goToStep;
  window.addRow = addRow;
  window.removeRow = removeRow;
  window.handleFormSubmit = handleFormSubmit;
  window.saveProgress = () => saveProgress(true);
})();

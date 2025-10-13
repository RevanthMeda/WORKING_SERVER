// Lightweight form controller for the FDS wizard
(function () {
  let currentStep = 1;

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

  function showAlert(message, type) {
    const form = document.getElementById('fdsForm');
    if (!form) {
      return;
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
      <i class="fa fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'}"></i>
      ${message}
    `;

    const existingAlerts = form.querySelectorAll('.alert');
    existingAlerts.forEach((node) => node.remove());

    form.prepend(alert);
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

  document.addEventListener('DOMContentLoaded', () => {
    setActiveStep(currentStep);
    wireProgressSteps();

    const form = document.getElementById('fdsForm');
    if (form) {
      form.addEventListener('submit', handleFormSubmit);
    }
  });

  window.goToStep = goToStep;
  window.addRow = addRow;
  window.removeRow = removeRow;
  window.handleFormSubmit = handleFormSubmit;
})();

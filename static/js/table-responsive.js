// ========== RESPONSIVE TABLE SYSTEM WITH SMART COLUMN MANAGEMENT ==========
(function() {
  'use strict';

  function initializeResponsiveTables() {
    const tables = document.querySelectorAll('table');

    tables.forEach(table => {
      createMobileCardLayout(table);
      setupColumnPriorities(table);
      setupStickyColumns(table);
      addHeaderTooltips(table);
      implementSmartColumnHiding(table);
    });

    // Handle window resize with debouncing
    window.addEventListener('resize', debounce(handleTableResize, 100));

    // Initial optimization
    optimizeForCurrentScreenSize();
  }

  function implementSmartColumnHiding(table) {
    const headers = table.querySelectorAll('th');
    const rows = table.querySelectorAll('tbody tr');

    // Add column visibility controls
    const tableContainer = table.closest('.table-responsive');
    if (tableContainer) {
      const controlsContainer = document.createElement('div');
      controlsContainer.className = 'table-column-controls';
      controlsContainer.innerHTML = `
        <div class="column-toggle-buttons">
          <button type="button" class="btn-secondary btn-small" onclick="toggleAllColumns(this)">
            <i class="fas fa-columns"></i> Show All Columns
          </button>
          <button type="button" class="btn-secondary btn-small" onclick="toggleEssentialColumns(this)">
            <i class="fas fa-eye"></i> Essential Only
          </button>
        </div>
      `;
      tableContainer.prepend(controlsContainer);
    }
  }

  function optimizeForCurrentScreenSize() {
    const screenWidth = window.innerWidth;

    // Adjust layout based on screen size
    if (screenWidth < 1200) {
      // Reduce padding and margins for more space
      document.documentElement.style.setProperty('--dynamic-padding', '8px');
      document.documentElement.style.setProperty('--dynamic-margin', '4px');

      // Hide non-essential UI elements
      hideNonEssentialElements();
    } else {
      document.documentElement.style.setProperty('--dynamic-padding', '16px');
      document.documentElement.style.setProperty('--dynamic-margin', '12px');

      showAllElements();
    }
  }

  function hideNonEssentialElements() {
    // Hide step descriptions in progress sidebar
    document.querySelectorAll('.step-description').forEach(el => {
      el.style.display = 'none';
    });

    // Collapse form section descriptions
    document.querySelectorAll('.step-description').forEach(el => {
      el.style.display = 'none';
    });

    // Make progress header more compact
    const progressHeader = document.querySelector('.progress-header p');
    if (progressHeader) progressHeader.style.display = 'none';
  }

  function showAllElements() {
    // Show step descriptions
    document.querySelectorAll('.step-description').forEach(el => {
      el.style.display = 'block';
    });

    // Show form section descriptions
    document.querySelectorAll('.step-description').forEach(el => {
      el.style.display = 'block';
    });

    // Show progress header description
    const progressHeader = document.querySelector('.progress-header p');
    if (progressHeader) progressHeader.style.display = 'block';
  }

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

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    initializeResponsiveTables();
  });

})();
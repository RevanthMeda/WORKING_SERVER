(() => {
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB per file
  const groups = [];

  const isPdf = (file) =>
    file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

  const isImage = (file) =>
    file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name);

  const formatBytes = (bytes) => {
    if (!Number.isFinite(bytes) || bytes <= 0) {
      return '';
    }
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / (1024 ** index);
    return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
  };

  const rebuildFileInput = (group) => {
    const transfer = new DataTransfer();
    group.files.forEach(({ file }) => transfer.items.add(file));
    group.input.files = transfer.files;
  };

  const countExistingPreviews = (group) => {
    if (!group.existingContainer) {
      return 0;
    }
    return group.existingContainer.querySelectorAll('.image-preview, .pdf-preview').length;
  };

  const updateEmptyState = (group) => {
    if (!group.empty) {
      return;
    }
    const existingCount = countExistingPreviews(group);
    const total = existingCount + group.files.length;
    group.empty.style.display = total > 0 ? 'none' : 'flex';
  };

  const readPreview = (file) =>
    new Promise((resolve) => {
      if (!isImage(file)) {
        resolve(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = (event) => resolve(event.target.result);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(file);
    });

  const uniqueKeyForFile = (groupId, file) =>
    `${groupId}-${file.name}-${file.size}-${file.lastModified}`;

  const renderQueue = (group) => {
    if (!group.queue) {
      return;
    }
    group.queue.innerHTML = '';

    group.files.forEach((entry) => {
      const wrapper = document.createElement('div');
      const isImageEntry = Boolean(entry.previewUrl);
      wrapper.className = isImageEntry ? 'image-preview' : 'pdf-preview';

      if (isImageEntry) {
        const img = document.createElement('img');
        img.src = entry.previewUrl;
        img.alt = entry.file.name;
        wrapper.appendChild(img);
      } else {
        const icon = document.createElement('i');
        icon.className = 'fas fa-file-pdf';
        icon.setAttribute('aria-hidden', 'true');
        wrapper.appendChild(icon);

        const name = document.createElement('span');
        name.textContent = entry.file.name;
        wrapper.appendChild(name);

        const meta = document.createElement('span');
        meta.className = 'file-size';
        meta.textContent = formatBytes(entry.file.size);
        wrapper.appendChild(meta);
      }

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'remove-image-btn';
      removeBtn.title = 'Remove file';
      removeBtn.innerHTML = '×';
      removeBtn.addEventListener('click', () => {
        const index = group.files.findIndex((item) => item.key === entry.key);
        if (index >= 0) {
          group.files.splice(index, 1);
          rebuildFileInput(group);
          renderQueue(group);
        }
      });

      wrapper.appendChild(removeBtn);
      group.queue.appendChild(wrapper);
    });

    updateEmptyState(group);
  };

  const validateFile = (file, group) => {
    if (file.size > MAX_FILE_SIZE) {
      window.alert(`"${file.name}" exceeds the 10 MB limit and will be skipped.`);
      return false;
    }
    if (isImage(file) && group.allowImages) {
      return true;
    }
    if (isPdf(file) && group.allowDocs) {
      return true;
    }
    window.alert(`"${file.name}" is not an accepted format for this section and will be skipped.`);
    return false;
  };

  const addFilesToGroup = async (group, fileList) => {
    const additions = [];
    const existingKeys = new Set(group.files.map((entry) => entry.key));

    for (const file of fileList) {
      if (!validateFile(file, group)) {
        continue;
      }

      const key = uniqueKeyForFile(group.id, file);
      if (existingKeys.has(key)) {
        continue;
      }

      const previewUrl = group.allowImages ? await readPreview(file) : null;
      additions.push({ key, file, previewUrl });
      existingKeys.add(key);
    }

    if (!additions.length) {
      return;
    }

    group.files.push(...additions);
    rebuildFileInput(group);
    renderQueue(group);
  };

  const bindDropzone = (group) => {
    if (!group.dropzone) {
      return;
    }

    const { dropzone, input } = group;

    dropzone.addEventListener('click', () => input.click());
    dropzone.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        input.click();
      }
    });

    dropzone.addEventListener('dragover', (event) => {
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'copy';
      }
      dropzone.classList.add('is-dragover');
    });

    ['dragleave', 'dragend'].forEach((evt) => {
      dropzone.addEventListener(evt, () => dropzone.classList.remove('is-dragover'));
    });

    dropzone.addEventListener('drop', (event) => {
      event.preventDefault();
      dropzone.classList.remove('is-dragover');
      const { files } = event.dataTransfer || {};
      if (files && files.length) {
        addFilesToGroup(group, Array.from(files));
      }
    });
  };

  const markRemoval = (targetId, url) => {
    const hidden = document.getElementById(targetId);
    if (!hidden || !url) {
      return;
    }
    const existing = hidden.value
      ? hidden.value.split(',').map((value) => value.trim()).filter(Boolean)
      : [];
    if (!existing.includes(url)) {
      existing.push(url);
      hidden.value = existing.join(',');
    }
  };

  const findGroupForElement = (element) =>
    groups.find((group) => group.container === element);

  const initializeGroups = () => {
    document.querySelectorAll('.file-upload-group').forEach((groupEl, index) => {
      const input = groupEl.querySelector('input[type="file"]');
      const dropzone = groupEl.querySelector('.file-upload-dropzone');
      const container = groupEl.querySelector('[data-upload-preview]');
      const existingContainer = groupEl.querySelector('[data-existing-previews]');
      const queue = groupEl.querySelector('[data-upload-queue]');
      const empty = container?.querySelector('.empty-upload-state') || null;

      if (!input || !container || !queue) {
        return;
      }

      const group = {
        id: groupEl.dataset.uploadScope || `upload-group-${index}`,
        container: groupEl,
        input,
        dropzone,
        queue,
        existingContainer,
        empty,
        allowImages: groupEl.dataset.allowImages !== 'false',
        allowDocs: groupEl.dataset.allowDocs === 'true',
        files: [],
      };

      input.addEventListener('change', (event) => {
        const { files } = event.target;
        if (files && files.length) {
          addFilesToGroup(group, Array.from(files));
          input.value = '';
        }
      });

      bindDropzone(group);
      updateEmptyState(group);
      groups.push(group);
    });
  };

  document.addEventListener('DOMContentLoaded', () => {
    initializeGroups();

    document.addEventListener('click', (event) => {
      const existingBtn = event.target.closest('[data-existing-file]');
      if (existingBtn) {
        event.preventDefault();
        const fileUrl = existingBtn.dataset.existingFile;
        const targetId = existingBtn.dataset.removedTarget;
        markRemoval(targetId, fileUrl);
        const preview = existingBtn.closest('.image-preview, .pdf-preview');
        if (preview) {
          const groupElement = existingBtn.closest('.file-upload-group');
          preview.remove();
          const group = findGroupForElement(groupElement);
          if (group) {
            updateEmptyState(group);
          }
        }
        return;
      }
    });
  });
})();

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
    group.store.forEach(({ file }) => transfer.items.add(file));
    group.input.files = transfer.files;
  };

  const updateEmptyState = (group) => {
    if (group.empty) {
      group.empty.style.display = group.store.length ? 'none' : 'flex';
    }
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

  const renderGroup = (group) => {
    if (!group.list) {
      return;
    }

    group.list.innerHTML = '';

    group.store.forEach((entry) => {
      const card = document.createElement('div');
      card.className = 'architecture-upload-card';
      card.dataset.fileKey = entry.key;

      const preview = document.createElement('div');
      preview.className = 'upload-preview';

      if (entry.previewUrl) {
        const img = document.createElement('img');
        img.src = entry.previewUrl;
        img.alt = entry.file.name;
        preview.appendChild(img);
      } else {
        const icon = document.createElement('div');
        icon.className = 'upload-preview-icon';
        icon.innerHTML = isPdf(entry.file)
          ? '<i class="fas fa-file-pdf"></i>'
          : '<i class="fas fa-file"></i>';
        preview.appendChild(icon);
      }

      const details = document.createElement('div');
      details.className = 'upload-details';
      details.innerHTML = `
        <span class="file-name">${entry.file.name}</span>
        <span class="file-size">${formatBytes(entry.file.size)}</span>
      `;

      const captionWrapper = document.createElement('label');
      captionWrapper.className = 'upload-caption';
      captionWrapper.innerHTML = `
        <span>Caption (optional)</span>
        <textarea name="${group.captionName}"
                  rows="2"
                  placeholder="Add a short description...">${entry.caption || ''}</textarea>
      `;

      const textarea = captionWrapper.querySelector('textarea');
      textarea.addEventListener('input', (event) => {
        entry.caption = event.target.value;
      });

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'upload-remove';
      removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
      removeBtn.title = 'Remove this file';
      removeBtn.addEventListener('click', () => {
        const index = group.store.findIndex((item) => item.key === entry.key);
        if (index >= 0) {
          group.store.splice(index, 1);
          rebuildFileInput(group);
          renderGroup(group);
        }
      });

      card.appendChild(preview);
      card.appendChild(details);
      card.appendChild(captionWrapper);
      card.appendChild(removeBtn);
      group.list.appendChild(card);
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

  const handleSelection = async (group, event) => {
    const input = event.target;
    if (!input.files?.length) {
      return;
    }

    const newFiles = Array.from(input.files);
    const existingKeys = new Set(group.store.map((entry) => entry.key));
    const additions = [];

    for (const file of newFiles) {
      if (!validateFile(file, group)) {
        continue;
      }
      const key = uniqueKeyForFile(group.id, file);
      if (existingKeys.has(key)) {
        continue;
      }
      const previewUrl = group.allowImages ? await readPreview(file) : null;
      additions.push({ key, file, caption: '', previewUrl });
      existingKeys.add(key);
    }

    if (!additions.length) {
      rebuildFileInput(group);
      return;
    }

    group.store.push(...additions);
    rebuildFileInput(group);
    renderGroup(group);
  };

  document.addEventListener('DOMContentLoaded', () => {
    const containers = document.querySelectorAll('[data-upload-group]');
    if (!containers.length) {
      return;
    }

    containers.forEach((container, index) => {
      const inputId = container.dataset.inputId;
      const listId = container.dataset.listId;
      const emptyId = container.dataset.emptyId;
      const captionName = container.dataset.captionName || '';
      const allowImages = container.dataset.allowImages !== 'false';
      const allowDocs = container.dataset.allowDocs === 'true';

      const input = document.getElementById(inputId);
      const list = document.getElementById(listId);
      const empty = document.getElementById(emptyId);

      if (!input || !list || !empty) {
        return;
      }

      const group = {
        id: inputId || `upload-group-${index}`,
        input,
        list,
        empty,
        captionName,
        allowImages,
        allowDocs,
        store: [],
      };

      input.addEventListener('change', (event) => handleSelection(group, event));
      groups.push(group);
      updateEmptyState(group);
    });
  });
})();

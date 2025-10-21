(() => {
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
  const SELECTOR = {
    input: 'architecture-image-input',
    list: 'architecture-upload-list',
    empty: 'architecture-empty-upload',
  };

  const fileStore = [];

  const $ = (id) => document.getElementById(id);

  const formatBytes = (bytes) => {
    if (!Number.isFinite(bytes)) {
      return '';
    }
    if (bytes === 0) {
      return '0 B';
    }
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / (1024 ** index);
    return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
  };

  const rebuildFileInput = (input, items) => {
    const transfer = new DataTransfer();
    items.forEach(({ file }) => transfer.items.add(file));
    input.files = transfer.files;
  };

  const updateEmptyState = (listEl, emptyEl) => {
    if (!listEl || !emptyEl) {
      return;
    }
    const hasFiles = fileStore.length > 0;
    emptyEl.style.display = hasFiles ? 'none' : 'flex';
  };

  const handleCaptionChange = (event) => {
    const card = event.target.closest('[data-file-key]');
    if (!card) {
      return;
    }
    const key = card.dataset.fileKey;
    const entry = fileStore.find((item) => item.key === key);
    if (entry) {
      entry.caption = event.target.value;
    }
  };

  const renderList = () => {
    const list = $(SELECTOR.list);
    const emptyState = $(SELECTOR.empty);
    if (!list) {
      return;
    }
    list.innerHTML = '';

    fileStore.forEach((entry) => {
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
        icon.innerHTML = '<i class="fas fa-image"></i>';
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
        <textarea name="architecture_image_captions[]" rows="2" placeholder="Add a short description...">${entry.caption || ''}</textarea>
      `;

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'upload-remove';
      removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
      removeBtn.title = 'Remove this image';
      removeBtn.addEventListener('click', () => {
        const index = fileStore.findIndex((item) => item.key === entry.key);
        if (index >= 0) {
          fileStore.splice(index, 1);
          rebuildFileInput($(SELECTOR.input), fileStore);
          renderList();
        }
      });

      captionWrapper.querySelector('textarea').addEventListener('input', handleCaptionChange);

      card.appendChild(preview);
      card.appendChild(details);
      card.appendChild(captionWrapper);
      card.appendChild(removeBtn);
      list.appendChild(card);
    });

    updateEmptyState(list, emptyState);
  };

  const readPreview = (file) =>
    new Promise((resolve) => {
      if (!file.type.startsWith('image/')) {
        resolve(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = (event) => resolve(event.target.result);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(file);
    });

  const uniqueKeyForFile = (file) => `${file.name}-${file.size}-${file.lastModified}`;

  const handleFileSelection = async (event) => {
    const input = event.target;
    if (!input.files?.length) {
      return;
    }

    const newFiles = Array.from(input.files);
    const existingKeys = new Set(fileStore.map((entry) => entry.key));

    const additions = [];
    for (const file of newFiles) {
      const key = uniqueKeyForFile(file);
      if (existingKeys.has(key)) {
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        window.alert(`"${file.name}" exceeds the 10 MB limit and will be skipped.`);
        continue;
      }
      const previewUrl = await readPreview(file);
      additions.push({ key, file, caption: '', previewUrl });
      existingKeys.add(key);
    }

    if (!additions.length) {
      rebuildFileInput(input, fileStore);
      return;
    }

    fileStore.push(...additions);
    rebuildFileInput(input, fileStore);
    renderList();
  };

  document.addEventListener('DOMContentLoaded', () => {
    const input = $(SELECTOR.input);
    const list = $(SELECTOR.list);
    const emptyState = $(SELECTOR.empty);

    if (!input || !list || !emptyState) {
      return;
    }

    updateEmptyState(list, emptyState);
    input.addEventListener('change', handleFileSelection);
  });
})();

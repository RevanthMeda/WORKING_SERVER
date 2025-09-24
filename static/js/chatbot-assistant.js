(function () {
    const root = document.getElementById('cully-assistant-root');
    if (!root) {
        return;
    }

    const panel = root.querySelector('.assistant-panel');
    const launcher = root.querySelector('.assistant-launcher');
    const statusLabel = root.querySelector('.assistant-status');
    const messagesContainer = root.querySelector('[data-assistant-messages]');
    const form = root.querySelector('[data-assistant-form]');
    const input = form ? form.querySelector('.assistant-input') : null;
    const sendButton = form ? form.querySelector('.assistant-form-button--primary') : null;
    const researchButton = root.querySelector('[data-assistant-research]');
    const dropzoneWrapper = root.querySelector('[data-assistant-dropzone]');
    const dropzone = dropzoneWrapper ? dropzoneWrapper.querySelector('.assistant-file-drop') : null;
    const fileInput = root.querySelector('.assistant-file-input');
    const attachmentsButton = root.querySelector('[data-assistant-attachments]');
    const hintButtons = root.querySelectorAll('[data-assistant-hint]');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    const FIELD_LABELS = {
        DOCUMENT_TITLE: 'document title',
        CLIENT_NAME: 'client organisation',
        PROJECT_REFERENCE: 'project reference',
        PURPOSE: 'purpose',
        SCOPE: 'scope',
        PREPARED_BY: 'prepared by',
        USER_EMAIL: 'prepared by email',
        DOCUMENT_REFERENCE: 'document reference',
        REVISION: 'revision'
    };
    const MAX_SNAPSHOT_ITEMS = 3;

    const endpoints = {
        start: root.dataset.assistantStart,
        message: root.dataset.assistantMessage,
        reset: root.dataset.assistantReset,
        upload: root.dataset.assistantUpload,
        document: root.dataset.assistantDocument
    };

    let conversationBootstrapped = false;
    let busy = false;
    let lastProgressSignature = '';

    function togglePanel(forceOpen) {
        const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : panel.hidden;
        if (shouldOpen) {
            openPanel();
        } else {
            closePanel();
        }
    }

    function openPanel() {
        if (!panel.hidden) {
            return;
        }
        panel.hidden = false;
        requestAnimationFrame(() => {
            panel.classList.add('is-open');
        });
        launcher.setAttribute('aria-expanded', 'true');
        if (!conversationBootstrapped) {
            bootstrapConversation();
        }
    }

    function closePanel() {
        panel.classList.remove('is-open');
        launcher.setAttribute('aria-expanded', 'false');
        setTimeout(() => {
            if (!panel.classList.contains('is-open')) {
                panel.hidden = true;
            }
        }, 260);
    }

    function showToast(message, tone = 'info') {
        const existing = root.querySelector('.assistant-toast');
        if (existing) {
            existing.remove();
        }
        const toast = document.createElement('div');
        toast.className = 'assistant-toast';
        if (tone === 'warning') {
            toast.style.background = 'rgba(255, 193, 7, 0.92)';
            toast.style.color = '#231b02';
        }
        if (tone === 'error') {
            toast.style.background = 'rgba(239, 83, 80, 0.92)';
            toast.style.color = '#ffffff';
        }
        toast.textContent = message;
        root.appendChild(toast);
        setTimeout(() => toast.remove(), 4200);
    }

    function createMessageElement(role, text, options = {}) {
        const wrapper = document.createElement('div');
        wrapper.className = `assistant-message assistant-message--${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'assistant-message-avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const bubble = document.createElement('div');
        bubble.className = 'assistant-message-content';
        if (options.highlight) {
            bubble.style.borderColor = 'rgba(0, 229, 255, 0.45)';
        }
        fillParagraphs(bubble, text);

        if (options.meta && Array.isArray(options.meta)) {
            options.meta.forEach((line) => {
                const metaLine = document.createElement('small');
                metaLine.textContent = line;
                bubble.appendChild(metaLine);
            });
        }

        wrapper.appendChild(avatar);
        wrapper.appendChild(bubble);
        return wrapper;
    }

    function fillParagraphs(container, text) {
        if (typeof text !== 'string') {
            text = String(text || '');
        }
        const parts = text.split(/
{2,}/);
        parts.forEach((block, index) => {
            const paragraph = document.createElement('p');
            block.split('
').forEach((line, lineIndex) => {
                if (lineIndex > 0) {
                    paragraph.appendChild(document.createElement('br'));
                }
                paragraph.appendChild(document.createTextNode(line.trim()));
            });
            container.appendChild(paragraph);
            if (index !== parts.length - 1) {
                container.appendChild(document.createElement('br'));
            }
        });
    }

    function appendMessage(role, text, options) {
        const element = createMessageElement(role, text, options);
        messagesContainer.appendChild(element);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function setBusy(state) {
        busy = state;
        if (!sendButton) {
            return;
        }
        if (state) {
            sendButton.disabled = true;
            sendButton.classList.add('is-loading');
        } else {
            sendButton.disabled = false;
            sendButton.classList.remove('is-loading');
        }
    }

    async function bootstrapConversation() {
        try {
            const payload = await requestJSON(endpoints.start, { method: 'POST' });
            conversationBootstrapped = true;
            renderAssistantPayload(payload, { headline: 'Let's launch your SAT or FAT workflow step by step.' });
        } catch (error) {
            showToast(error.message || 'Failed to initialise assistant.', 'error');
        }
    }

    async function requestJSON(url, options = {}) {
        const headers = Object.assign({}, options.headers || {});
        if (!headers['Content-Type'] && !headers['content-type']) {
            headers['Content-Type'] = 'application/json';
        }
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }
        const fetchOptions = Object.assign({}, options, {
            credentials: 'same-origin',
            headers
        });
        const response = await fetch(url, fetchOptions);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || response.statusText);
        }
        return response.json();
    }

    function renderAssistantPayload(payload, options = {}) {
        if (!payload) {
            return;
        }

        if (options.headline) {
            appendMessage('bot', options.headline);
        }

        if (payload.messages && Array.isArray(payload.messages)) {
            payload.messages.forEach((message) => appendMessage('bot', message));
        }

        if (payload.errors && Array.isArray(payload.errors) && payload.errors.length) {
            payload.errors.forEach((message) => appendMessage('bot', message, { highlight: true }));
            showToast(payload.errors[0], 'error');
        }

        if (payload.warnings && Array.isArray(payload.warnings) && payload.warnings.length) {
            payload.warnings.forEach((warning) => appendMessage('bot', warning));
            showToast(payload.warnings[0], 'warning');
        }

        if (payload.command) {
            handleCommand(payload.command);
        }

        if (payload.completed) {
            appendMessage('bot', 'All SAT essentials are captured. I can generate the report or launch approvals whenever you are ready.');
        } else if (payload.question) {
            const meta = [];
            if (payload.help_text) {
                meta.push(payload.help_text);
            }
            appendMessage('bot', payload.question, { meta });
        }

        if (payload.collected) {
            const snapshot = buildProgressSnapshot(payload);
            if (snapshot && snapshot.signature !== lastProgressSignature) {
                appendMessage('bot', snapshot.text);
                lastProgressSignature = snapshot.signature;
            }
        }

        updateStatus(payload);
    }

    function updateStatus(payload) {
        if (!statusLabel) {
            return;
        }
        const collected = payload.collected || {};
        const capturedKeys = Object.keys(collected).filter((key) => collected[key]);
        const pending = (payload.pending_fields || []).filter(Boolean);
        const total = capturedKeys.length + pending.length;
        if (payload.completed) {
            const denominator = total > 0 ? total : (capturedKeys.length || 0);
            const readyCount = denominator > 0 ? `${capturedKeys.length}/${denominator}` : `${capturedKeys.length}`;
            statusLabel.textContent = `Captured ${readyCount} fields - ready to generate.`;
            return;
        }
        const nextLabel = formatFieldLabel(payload.field);
        let capturedSummary = `Captured ${capturedKeys.length}`;
        if (total > 0) {
            capturedSummary += `/${total}`;
        }
        if (capturedKeys.length) {
            capturedSummary += ` (${capturedKeys.slice(0, 2).map(formatFieldLabel).join(', ')}`;
            if (capturedKeys.length > 2) {
                capturedSummary += ', ...';
            }
            capturedSummary += ')';
        }
        let pendingSummary = `Pending ${pending.length}`;
        if (pending.length) {
            pendingSummary += ` (${pending.slice(0, 2).map(formatFieldLabel).join(', ')}`;
            if (pending.length > 2) {
                pendingSummary += ', ...';
            }
            pendingSummary += ')';
        }
        statusLabel.textContent = `${capturedSummary} | ${pendingSummary} | Next: ${nextLabel}`;
    }

    function formatFieldLabel(field) {
        if (!field) {
            return 'details';
        }
        const key = String(field).trim().toUpperCase();
        if (key && FIELD_LABELS[key]) {
            return FIELD_LABELS[key];
        }
        return key.replace(/_/g, ' ').toLowerCase();
    }

    function buildProgressSnapshot(payload) {
        const collected = payload.collected || {};
        const pending = payload.pending_fields || [];
        const capturedKeys = Object.keys(collected).filter((key) => collected[key]);
        const capturedSorted = capturedKeys.slice().sort();
        const pendingSorted = pending.slice().sort();
        const signature = `${capturedSorted.join('|')}::${pendingSorted.join('|')}::${payload.completed ? '1' : '0'}`;
        const lines = [];

        if (capturedSorted.length) {
            lines.push(`Captured ${capturedSorted.length} field${capturedSorted.length === 1 ? '' : 's'} so far:`);
            capturedSorted.slice(0, MAX_SNAPSHOT_ITEMS).forEach((key) => {
                lines.push(`- ${formatFieldLabel(key)}: ${truncateValue(collected[key])}`);
            });
            if (capturedSorted.length > MAX_SNAPSHOT_ITEMS) {
                lines.push(`- ...and ${capturedSorted.length - MAX_SNAPSHOT_ITEMS} more.`);
            }
        } else {
            lines.push('Captured 0 fields so far.');
        }

        if (pendingSorted.length) {
            lines.push(`Pending ${pendingSorted.length} field${pendingSorted.length === 1 ? '' : 's'}:`);
            pendingSorted.slice(0, MAX_SNAPSHOT_ITEMS).forEach((key) => {
                lines.push(`- ${formatFieldLabel(key)}`);
            });
            if (pendingSorted.length > MAX_SNAPSHOT_ITEMS) {
                lines.push(`- ...and ${pendingSorted.length - MAX_SNAPSHOT_ITEMS} more.`);
            }
        } else {
            lines.push('Pending 0 fields. All required inputs are in.');
        }

        if (payload.completed) {
            lines.push('Ready to generate reports or route approvals.');
        } else if (payload.field) {
            lines.push(`Next prompt: ${formatFieldLabel(payload.field)}.`);
        }

        return {
            signature,
            text: lines.join('\n')
        };

    }

    function truncateValue(value, maxLength = 120) {
        const normalised = String(value || '').replace(/\s+/g, ' ').trim();
        if (!normalised) {
            return '-';
        }
        if (normalised.length > maxLength) {
            return `${normalised.slice(0, maxLength - 3)}...`;
        }
        return normalised;
    }

    function handleCommand(command) {
        if (!command || typeof command !== 'object') {
            return;
        }
        if (command.type === 'document_fetch') {
            if (command.success && command.download_url) {
                appendMessage('bot', 'Download ready. Use the link to open the regenerated report.', {
                    meta: [command.download_url]
                });
            } else if (command.error) {
                showToast(command.error, 'error');
            }
        }
        if (command.type === 'summary') {
            const pending = command.pending_fields || [];
            const text = pending.length
                ? `Still missing ${pending.length} item${pending.length > 1 ? 's' : ''}.`
                : 'Everything is captured.';
            appendMessage('bot', text);
        }
    }

    async function submitMessage(mode = 'default') {
        if (!form || !input) {
            return;
        }
        const raw = (input.value || '').trim();
        if (!raw || busy) {
            return;
        }
        appendMessage('user', raw);
        input.value = '';
        setBusy(true);
        try {
            const payload = await requestJSON(endpoints.message, {
                method: 'POST',
                body: JSON.stringify({ message: raw, mode })
            });
            renderAssistantPayload(payload);
        } catch (error) {
            showToast(error.message || 'Assistant unavailable.', 'error');
        } finally {
            setBusy(false);
        }
    }

    async function resetConversation() {
        setBusy(true);
        try {
            const payload = await requestJSON(endpoints.reset, { method: 'POST' });
            messagesContainer.innerHTML = '';
            appendMessage('bot', 'Starting fresh. Let's re-align on your SAT workflow.');
            lastProgressSignature = '';
            renderAssistantPayload(payload);
        } catch (error) {
            showToast(error.message || 'Unable to reset.', 'error');
        } finally {
            setBusy(false);
        }
    }

    async function uploadFiles(fileList) {
        if (!fileList || !fileList.length || busy) {
            return;
        }
        const files = Array.from(fileList);
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        appendMessage('user', `Uploading ${files.length} file${files.length > 1 ? 's' : ''} for analysis.`);
        setBusy(true);
        try {
            const headers = {};
            if (csrfToken) {
                headers['X-CSRFToken'] = csrfToken;
            }
            const response = await fetch(endpoints.upload, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
                headers
            });
            if (!response.ok) {
                throw new Error('Upload failed.');
            }
            const payload = await response.json();
            renderAssistantPayload(payload);
        } catch (error) {
            showToast(error.message || 'File ingestion failed.', 'error');
        } finally {
            if (fileInput) {
                fileInput.value = '';
            }
            if (dropzoneWrapper) {
                dropzoneWrapper.classList.remove('is-visible');
                dropzoneWrapper.setAttribute('hidden', '');
            }
            attachmentsButton?.classList.remove('is-active');
            setBusy(false);
        }
    }

    function bindEvents() {
        launcher.addEventListener('click', () => togglePanel());
        root.querySelector('[data-assistant-close]')?.addEventListener('click', closePanel);
        root.querySelector('[data-assistant-reset]')?.addEventListener('click', resetConversation);

        form?.addEventListener('submit', (event) => {
            event.preventDefault();
            submitMessage('default');
        });

        researchButton?.addEventListener('click', () => {
            if (!input) {
                return;
            }
            if (!input.value.trim()) {
                input.placeholder = 'Describe what you want me to research...';
                input.focus();
                return;
            }
            submitMessage('research');
        });

        hintButtons.forEach((button) => {
            button.addEventListener('click', () => {
                if (!input) {
                    return;
                }
                input.value = button.dataset.assistantHint || '';
                input.focus();
            });
        });

        if (fileInput) {
            fileInput.addEventListener('change', (event) => {
                const target = event.target;
                if (target.files && target.files.length) {
                    uploadFiles(target.files);
                }
            });
        }

        if (dropzoneWrapper) {
            ['dragenter', 'dragover'].forEach((type) => {
                dropzoneWrapper.addEventListener(type, (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    dropzoneWrapper.classList.add('is-visible');
                    dropzoneWrapper.removeAttribute('hidden');
                    if (attachmentsButton) {
                        attachmentsButton.classList.add('is-active');
                    }
                });
            });
            ['dragleave', 'drop'].forEach((type) => {
                dropzoneWrapper.addEventListener(type, (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    dropzoneWrapper.classList.remove('is-visible');
                    if (!dropzone?.classList.contains('is-active')) {
                        dropzoneWrapper.setAttribute('hidden', '');
                    }
                    if (attachmentsButton) {
                        attachmentsButton.classList.remove('is-active');
                    }
                });
            });
            dropzoneWrapper.addEventListener('drop', (event) => {
                if (event.dataTransfer?.files?.length) {
                    uploadFiles(event.dataTransfer.files);
                }
            });
        }

        if (dropzone) {
            ['dragenter', 'dragover'].forEach((type) => {
                dropzone.addEventListener(type, (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    dropzone.classList.add('is-active');
                });
            });
            ['dragleave', 'drop'].forEach((type) => {
                dropzone.addEventListener(type, (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    dropzone.classList.remove('is-active');
                });
            });
            dropzone.addEventListener('drop', (event) => {
                if (event.dataTransfer?.files?.length) {
                    uploadFiles(event.dataTransfer.files);
                }
            });
        }

        if (attachmentsButton && dropzoneWrapper) {
            attachmentsButton.addEventListener('click', () => {
                const isHidden = dropzoneWrapper.hasAttribute('hidden');
                if (isHidden) {
                    dropzoneWrapper.classList.add('is-visible');
                    dropzoneWrapper.removeAttribute('hidden');
                    attachmentsButton.classList.add('is-active');
                } else {
                    dropzoneWrapper.classList.remove('is-visible');
                    dropzoneWrapper.setAttribute('hidden', '');
                    attachmentsButton.classList.remove('is-active');
                }
            });
        }

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && panel.classList.contains('is-open')) {
                closePanel();
            }
        });
    }
    bindEvents();
})();




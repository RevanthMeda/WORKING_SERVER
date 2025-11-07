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
    const hintsContainer = root.querySelector('[data-assistant-hints]');
    const defaultHintsMarkup = hintsContainer ? hintsContainer.innerHTML : '';
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const satForm = document.getElementById('satForm');
    const rawTableConfig = Array.isArray(window.SAT_TABLE_CONFIG) ? window.SAT_TABLE_CONFIG : [];
    const tableSectionMap = rawTableConfig.reduce((acc, section) => {
        if (!section || !section.ui_section || !section.tbody_id || !section.template_id) {
            return acc;
        }
        const fieldMap = {};
        (section.fields || []).forEach((field) => {
            if (field && field.ui && field.form) {
                fieldMap[field.ui] = field.form;
            }
        });
        acc[section.ui_section] = {
            bodyId: section.tbody_id,
            templateId: section.template_id,
            fieldMap
        };
        return acc;
    }, {});

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
    const FIELD_INPUT_TARGETS = {
        DOCUMENT_TITLE: { selector: '#document_title' },
        CLIENT_NAME: { selector: '#client_name' },
        PROJECT_REFERENCE: { selector: '#project_reference' },
        DOCUMENT_REFERENCE: { selector: '#document_reference' },
        REVISION: { selector: '#revision' },
        PURPOSE: { selector: '#purpose', editorSelector: '#purpose-editor' },
        SCOPE: { selector: '#scope', editorSelector: '#scope-editor' },
        PREPARED_BY: { selector: '#prepared_by' },
        USER_EMAIL: { selector: '#user_email' }
    };

    let conversationBootstrapped = false;
    let busy = false;
    let lastProgressSignature = '';

    function openPanel() {
        panel.classList.add('is-open');
        launcher.setAttribute('aria-expanded', 'true');
        if (!conversationBootstrapped) {
            bootstrapConversation();
        }
    }

    function closePanel() {
        panel.classList.remove('is-open');
        launcher.setAttribute('aria-expanded', 'false');
    }

    function togglePanel() {
        if (panel.classList.contains('is-open')) {
            closePanel();
        } else {
            openPanel();
        }
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
        const parts = text.split(/\n{2,}/);
        parts.forEach((block, index) => {
            const paragraph = document.createElement('p');
            block.split('\n').forEach((line, lineIndex) => {
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

    function formatAgentAction(action) {
        if (!action || typeof action !== 'object') {
            return null;
        }
        const rawLabel = action.label || action.title || action.name || action.summary || action.type;
        const label = rawLabel ? String(rawLabel) : 'Agent action';
        const readable = label.replace(/[_\-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
        const details = [];
        if (action.priority) {
            details.push(`${String(action.priority).toUpperCase()} priority`);
        }
        if (typeof action.confidence === 'number') {
            details.push(`${Math.round(action.confidence * 100)}% confidence`);
        }
        const data = action.data && typeof action.data === 'object' ? action.data : null;
        if (data && data.report_type) {
            details.push(`Report ${String(data.report_type)}`);
        }
        if (data && data.project_reference) {
            details.push(`Project ${String(data.project_reference)}`);
        }
        const suffix = details.length ? ` (${details.join(', ')})` : '';
        return `- ${readable}${suffix}`;
    }

    function renderAgentInsights(payload) {
        if (!payload || typeof payload !== 'object') {
            return;
        }
        const agent = payload.agent && typeof payload.agent === 'object' ? payload.agent : {};
        const actions = Array.isArray(payload.agent_actions)
            ? payload.agent_actions
            : (Array.isArray(agent.actions) ? agent.actions : []);
        const nextSteps = Array.isArray(payload.agent_next_steps)
            ? payload.agent_next_steps
            : (Array.isArray(agent.next_steps) ? agent.next_steps : []);
        const reasoning = payload.agent_reasoning || agent.reasoning;
        const confidenceSource = payload.agent_confidence ?? agent.confidence;
        const confidence = typeof confidenceSource === 'number' ? confidenceSource : null;

        const sections = [];

        if (reasoning) {
            sections.push(`**Agent reasoning:** ${reasoning}`);
        }

        if (confidence !== null) {
            const bounded = Math.max(0, Math.min(1, confidence));
            sections.push(`**Confidence:** ${(bounded * 100).toFixed(1)}%`);
        }

        if (actions.length) {
            const formattedActions = actions.slice(0, 3).map(formatAgentAction).filter(Boolean);
            if (formattedActions.length) {
                sections.push(['**Proposed actions:**', ...formattedActions].join('\n'));
            }
            if (actions.length > 3) {
                sections.push(`(+${actions.length - 3} additional actions available)`);
            }
        }

        if (nextSteps.length) {
            const formattedSteps = nextSteps.slice(0, 5).map((step, index) => `${index + 1}. ${step}`);
            if (formattedSteps.length) {
                sections.push(['**Next steps:**', ...formattedSteps].join('\n'));
            }
        }

        if (!sections.length) {
            return;
        }

        appendMessage('bot', sections.join('\n\n'));
    }

    function applyFormUpdates(payload) {
        if (!satForm || !payload) {
            return;
        }
        if (payload.field_updates && typeof payload.field_updates === 'object') {
            Object.entries(payload.field_updates).forEach(([field, value]) => {
                applyFieldValue(field, value);
            });
        }
        if (payload.table_updates && typeof payload.table_updates === 'object') {
            Object.entries(payload.table_updates).forEach(([section, rows]) => {
                applyTableRows(section, rows);
            });
        }
    }

    function applyFieldValue(field, value) {
        const target = FIELD_INPUT_TARGETS[field];
        if (!target) {
            return;
        }
        const inputEl = target.selector ? document.querySelector(target.selector) : null;
        if (inputEl) {
            setInputValue(inputEl, value);
        }
        if (target.editorSelector) {
            const editor = document.querySelector(target.editorSelector);
            if (editor) {
                const html = escapeHtml(String(value ?? '')).replace(/\n/g, '<br>');
                editor.innerHTML = html;
            }
        }
    }

    function setInputValue(element, value) {
        const nextValue = value == null ? '' : String(value);
        if ('value' in element) {
            if (element.value !== nextValue) {
                element.value = nextValue;
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } else if (element.textContent !== nextValue) {
            element.textContent = nextValue;
        }
    }

    function applyTableRows(section, rows) {
        if (!Array.isArray(rows) || !rows.length) {
            const meta = tableSectionMap[section];
            if (!meta) {
                return;
            }
            const body = document.getElementById(meta.bodyId);
            if (!body) {
                return;
            }
            Array.from(body.querySelectorAll('tr[data-autofill-row=\"true\"]')).forEach((row) => row.remove());
            return;
        }
        const meta = tableSectionMap[section];
        if (!meta) {
            return;
        }
        const body = document.getElementById(meta.bodyId);
        const template = document.getElementById(meta.templateId);
        if (!body || !template) {
            return;
        }
        Array.from(body.querySelectorAll('tr[data-autofill-row=\"true\"]')).forEach((row) => row.remove());

        rows.forEach((rowData) => {
            if (!rowData || typeof rowData !== 'object') {
                return;
            }
            const fragment = template.content.cloneNode(true);
            const tr = fragment.querySelector('tr');
            if (!tr) {
                return;
            }
            tr.dataset.autofillRow = 'true';
            body.appendChild(fragment);
            Object.entries(meta.fieldMap).forEach(([uiKey, formName]) => {
                if (!(uiKey in rowData)) {
                    return;
                }
                const inputEl = tr.querySelector(`[name=\"${formName}\"]`);
                if (inputEl) {
                    setInputValue(inputEl, rowData[uiKey]);
                }
            });
        });
    }

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value;
        return div.innerHTML;
    }

    function extractAgentSuggestions(payload) {
        const suggestions = [];
        if (payload) {
            if (Array.isArray(payload.suggestions)) {
                suggestions.push(...payload.suggestions);
            }
            if (payload.agent && Array.isArray(payload.agent.suggestions)) {
                suggestions.push(...payload.agent.suggestions);
            }
        }
        const seen = new Set();
        return suggestions
            .map((item) => (typeof item === 'string' ? item.trim() : ''))
            .filter((item) => {
                if (!item) {
                    return false;
                }
                const key = item.toLowerCase();
                if (seen.has(key)) {
                    return false;
                }
                seen.add(key);
                return true;
            });
    }

    function bindHintButtons() {
        if (!hintsContainer || !input) {
            return;
        }
        hintsContainer.querySelectorAll('[data-assistant-hint]').forEach((button) => {
            if (button.dataset.hintBound === 'true') {
                return;
            }
            button.addEventListener('click', () => {
                input.value = button.dataset.assistantHint || button.textContent || '';
                input.focus();
            });
            button.dataset.hintBound = 'true';
        });
    }

    function updateDynamicHints(suggestions) {
        if (!hintsContainer) {
            return;
        }
        const nextSuggestions = Array.isArray(suggestions) ? suggestions.filter(Boolean) : [];
        if (!nextSuggestions.length) {
            if (hintsContainer.dataset.dynamicHints === 'true') {
                hintsContainer.innerHTML = defaultHintsMarkup;
                delete hintsContainer.dataset.dynamicHints;
                delete hintsContainer.dataset.hintSignature;
                bindHintButtons();
            }
            return;
        }
        const signature = nextSuggestions.join('||');
        if (hintsContainer.dataset.hintSignature === signature) {
            return;
        }
        hintsContainer.innerHTML = '';
        nextSuggestions.slice(0, 3).forEach((suggestion) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.dataset.assistantHint = suggestion;
            button.textContent = suggestion;
            hintsContainer.appendChild(button);
        });
        hintsContainer.dataset.dynamicHints = 'true';
        hintsContainer.dataset.hintSignature = signature;
        bindHintButtons();
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
            renderAssistantPayload(payload, { headline: 'Let\'s launch your SAT or FAT workflow step by step.' });
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

        renderAgentInsights(payload);
        updateDynamicHints(extractAgentSuggestions(payload));
        updateStatus(payload);
        applyFormUpdates(payload);
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
            appendMessage('bot', 'Starting fresh. Let\'s re-align on your SAT workflow.');
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
        launcher.addEventListener('click', togglePanel);
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

        bindHintButtons();

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
                    dropzone.classList.remove('is-visible');
                    if (!dropzone?.classList.contains('is-active')) {
                        dropzoneWrapper.setAttribute('hidden', '');
                    }
                    if (attachmentsButton) {
                        attachmentsButton.classList.remove('is-active');
                    }
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

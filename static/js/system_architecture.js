(() => {
  const workspace = document.getElementById('architecture-workspace');
  const generateBtn = document.getElementById('btn-generate-architecture');
  const resetBtn = document.getElementById('btn-architecture-reset');
  const saveBtn = document.getElementById('btn-architecture-save');
  const hiddenInput = document.getElementById('system_architecture_layout');
  const emptyState = document.getElementById('architecture-empty-state');
  const submissionIdInput = document.querySelector('input[name="submission_id"]');
  const submissionId = submissionIdInput ? submissionIdInput.value : '';
  const placeholderImage = 'https://dummyimage.com/320x220/dae3f9/1c2545.png&text=Device';

  if (!workspace || !generateBtn || !hiddenInput) {
    return;
  }

  let currentLayout = {
    nodes: [],
    connections: []
  };

  function parseHiddenLayout() {
    if (!hiddenInput || !hiddenInput.value) {
      return null;
    }
    try {
      return JSON.parse(hiddenInput.value);
    } catch (err) {
      console.warn('Invalid architecture layout JSON; ignoring', err);
      return null;
    }
  }

  function updateHiddenInput() {
    if (!hiddenInput) {
      return;
    }
    try {
      hiddenInput.value = JSON.stringify(currentLayout);
    } catch (err) {
      console.warn('Unable to serialise architecture layout', err);
    }
  }

  function collectEquipmentRows() {
    const rows = [];
    const tbody = document.getElementById('equipment-list-body');
    if (!tbody) {
      return rows;
    }
    Array.from(tbody.querySelectorAll('tr')).forEach((row) => {
      const model = row.querySelector('input[name="equipment_model[]"]')?.value?.trim() || '';
      const description = row.querySelector('input[name="equipment_description[]"]')?.value?.trim() || '';
      const quantity = row.querySelector('input[name="equipment_quantity[]"]')?.value?.trim() || '';
      const remarks = row.querySelector('input[name="equipment_remarks[]"]')?.value?.trim() || '';

      if (!model && !description) {
        return;
      }

      rows.push({
        Model: model,
        Description: description,
        Quantity: quantity,
        Remarks: remarks
      });
    });
    return rows;
  }

  function normaliseImagePath(url) {
    if (!url) {
      return placeholderImage;
    }
    if (/^https?:\/\//i.test(url) || url.startsWith('data:')) {
      return url;
    }
    return url.startsWith('/') ? url : `/${url}`;
  }

  function setNodePosition(nodeEl, x, y) {
    nodeEl.style.left = `${x}px`;
    nodeEl.style.top = `${y}px`;
    nodeEl.dataset.posX = String(x);
    nodeEl.dataset.posY = String(y);
  }

  function clampPosition(x, y) {
    const bounds = workspace.getBoundingClientRect();
    const width = workspace.scrollWidth;
    const height = workspace.scrollHeight;

    const maxX = Math.max(0, width - 220);
    const maxY = Math.max(0, height - 200);

    return {
      x: Math.min(Math.max(0, x), maxX),
      y: Math.min(Math.max(0, y), maxY)
    };
  }

  function attachDragHandlers(nodeEl) {
    let pointerId = null;
    let offsetX = 0;
    let offsetY = 0;

    nodeEl.addEventListener('pointerdown', (event) => {
      pointerId = event.pointerId;
      nodeEl.setPointerCapture(pointerId);
      nodeEl.classList.add('dragging');
      offsetX = event.clientX - nodeEl.offsetLeft;
      offsetY = event.clientY - nodeEl.offsetTop;
    });

    nodeEl.addEventListener('pointermove', (event) => {
      if (pointerId !== event.pointerId) {
        return;
      }
      const rawX = event.clientX - offsetX;
      const rawY = event.clientY - offsetY;
      const clamped = clampPosition(rawX, rawY);
      setNodePosition(nodeEl, clamped.x, clamped.y);
    });

    const clearDrag = (event) => {
      if (pointerId !== event.pointerId) {
        return;
      }
      nodeEl.releasePointerCapture(pointerId);
      nodeEl.classList.remove('dragging');
      pointerId = null;
      persistLayoutFromWorkspace();
    };

    nodeEl.addEventListener('pointerup', clearDrag);
    nodeEl.addEventListener('pointercancel', clearDrag);
  }

  function handleImageSwap(nodeEl) {
    const currentUrl = nodeEl.dataset.imageUrl || '';
    const replacement = window.prompt('Enter a new image URL for this equipment:', currentUrl);
    if (!replacement) {
      return;
    }
    const img = nodeEl.querySelector('img');
    img.src = normaliseImagePath(replacement);
    nodeEl.dataset.imageUrl = replacement;
    persistLayoutFromWorkspace();
  }

  function createNodeElement(node) {
    const nodeEl = document.createElement('div');
    nodeEl.className = 'architecture-node';
    nodeEl.dataset.nodeId = node.id;
    nodeEl.dataset.model = node.model || '';
    nodeEl.dataset.description = node.description || '';
    nodeEl.dataset.quantity = node.quantity || '';
    nodeEl.dataset.remarks = node.remarks || '';
    nodeEl.dataset.imageUrl = node.image_url || node.thumbnail_url || '';

    const img = document.createElement('img');
    img.src = normaliseImagePath(node.image_url || node.thumbnail_url);
    img.alt = node.model || 'Equipment';
    img.referrerPolicy = 'no-referrer';
    nodeEl.appendChild(img);

    const label = document.createElement('div');
    label.className = 'arch-label';
    label.textContent = node.model || 'Equipment';
    nodeEl.appendChild(label);

    const meta = document.createElement('div');
    meta.className = 'arch-meta';
    const details = [];
    if (node.description) {
      details.push(node.description);
    }
    if (node.quantity) {
      details.push(`Qty: ${node.quantity}`);
    }
    if (node.remarks) {
      details.push(node.remarks);
    }
    meta.textContent = details.join(' • ');
    nodeEl.appendChild(meta);

    const toolbar = document.createElement('div');
    toolbar.className = 'arch-toolbar';
    const swapButton = document.createElement('button');
    swapButton.type = 'button';
    swapButton.title = 'Replace image';
    swapButton.innerHTML = '<i class="fas fa-image"></i>';
    swapButton.addEventListener('click', (event) => {
      event.stopPropagation();
      handleImageSwap(nodeEl);
    });
    toolbar.appendChild(swapButton);
    nodeEl.appendChild(toolbar);

    const position = node.position || { x: 40, y: 40 };
    setNodePosition(nodeEl, position.x || 0, position.y || 0);

    attachDragHandlers(nodeEl);
    return nodeEl;
  }

  function renderConnections() {
    Array.from(workspace.querySelectorAll('.arch-connection')).forEach((el) => el.remove());
    if (!Array.isArray(currentLayout.connections)) {
      return;
    }

    currentLayout.connections.forEach((connection) => {
      const from = workspace.querySelector(`.architecture-node[data-node-id="${connection.from}"]`);
      const to = workspace.querySelector(`.architecture-node[data-node-id="${connection.to}"]`);
      if (!from || !to) {
        return;
      }
      const line = document.createElement('div');
      line.className = 'arch-connection';
      const x1 = parseFloat(from.dataset.posX || '0') + from.offsetWidth / 2;
      const y1 = parseFloat(from.dataset.posY || '0') + from.offsetHeight / 2;
      const x2 = parseFloat(to.dataset.posX || '0') + to.offsetWidth / 2;
      const y2 = parseFloat(to.dataset.posY || '0') + to.offsetHeight / 2;
      const distance = Math.hypot(x2 - x1, y2 - y1);
      const angle = Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI);
      line.style.width = `${distance}px`;
      line.style.transform = `translate(${x1}px, ${y1}px) rotate(${angle}deg)`;
      workspace.appendChild(line);
    });
  }

  function renderWorkspace() {
    workspace.querySelectorAll('.architecture-node').forEach((node) => node.remove());
    Array.from(workspace.querySelectorAll('.arch-connection')).forEach((conn) => conn.remove());

    if (!currentLayout.nodes || currentLayout.nodes.length === 0) {
      if (emptyState) {
        emptyState.style.display = 'flex';
      }
      return;
    }

    if (emptyState) {
      emptyState.style.display = 'none';
    }

    currentLayout.nodes.forEach((node) => {
      const nodeEl = createNodeElement(node);
      workspace.appendChild(nodeEl);
    });
    renderConnections();
  }

  function persistLayoutFromWorkspace() {
    const nodes = [];
    Array.from(workspace.querySelectorAll('.architecture-node')).forEach((nodeEl) => {
      nodes.push({
        id: nodeEl.dataset.nodeId,
        model: nodeEl.dataset.model,
        description: nodeEl.dataset.description,
        quantity: nodeEl.dataset.quantity,
        remarks: nodeEl.dataset.remarks,
        image_url: nodeEl.dataset.imageUrl,
        position: {
          x: parseFloat(nodeEl.dataset.posX || '0'),
          y: parseFloat(nodeEl.dataset.posY || '0')
        }
      });
    });
    currentLayout = {
      ...currentLayout,
      nodes
    };
    updateHiddenInput();
  }

  function loadLayout(layout) {
    if (!layout || typeof layout !== 'object') {
      currentLayout = { nodes: [], connections: [] };
    } else {
      currentLayout = {
        nodes: Array.isArray(layout.nodes) ? layout.nodes : [],
        connections: Array.isArray(layout.connections) ? layout.connections : []
      };
    }
    updateHiddenInput();
    renderWorkspace();
  }

  function fetchSavedLayout() {
    if (!submissionId) {
      return;
    }
    fetch(`/reports/system-architecture/${submissionId}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          return;
        }
        if (data.payload) {
          loadLayout(data.payload);
        }
      })
      .catch((err) => {
        console.warn('Unable to fetch stored architecture layout', err);
      });
  }

  function handleGenerate() {
    const equipment = collectEquipmentRows();
    if (!equipment.length) {
      window.alert('Add equipment details in Step 4 before generating the architecture.');
      return;
    }
    const body = {
      submission_id: submissionId,
      equipment,
      existing_layout: currentLayout
    };
    fetch('/reports/system-architecture/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Preview request failed (${response.status})`);
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error(data?.message || 'Unable to generate architecture');
        }
        if (data.payload) {
          loadLayout(data.payload);
        }
      })
      .catch((err) => {
        console.error('Architecture preview failed', err);
        window.alert('Unable to generate architecture preview. Please try again or check the console for details.');
      });
  }

  function handleReset() {
    loadLayout({ nodes: [], connections: [] });
  }

  function handleSave() {
    persistLayoutFromWorkspace();
    window.alert('Architecture layout stored in the form. Submit the FDS to persist it in the report.');
  }

  generateBtn.addEventListener('click', handleGenerate);
  if (resetBtn) {
    resetBtn.addEventListener('click', handleReset);
  }
  if (saveBtn) {
    saveBtn.addEventListener('click', handleSave);
  }

  const initial = parseHiddenLayout();
  if (initial) {
    loadLayout(initial);
  } else if (submissionId) {
    fetchSavedLayout();
  }
})(); 

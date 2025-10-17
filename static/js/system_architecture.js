(() => {
  const workspace = document.getElementById('architecture-workspace');
  const canvas = document.getElementById('architecture-canvas');
  const canvasCtx = canvas ? canvas.getContext('2d') : null;
  const generateBtn = document.getElementById('btn-generate-architecture');
  const resetBtn = document.getElementById('btn-architecture-reset');
  const saveBtn = document.getElementById('btn-architecture-save');
  const hiddenInput = document.getElementById('system_architecture_layout');
  const emptyState = document.getElementById('architecture-empty-state');
  const submissionIdInput = document.querySelector('input[name="submission_id"]');
  const submissionId = submissionIdInput ? submissionIdInput.value : '';
  const placeholderImage = 'https://via.placeholder.com/320x200.png?text=Device';
  const NODE_PADDING = 60;

  if (!workspace || !generateBtn || !hiddenInput) {
    return;
  }

  let currentLayout = {
    nodes: [],
    connections: []
  };
  let redrawQueued = false;

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

  function ensureWorkspaceBounds(nodeEl) {
    const posX = parseFloat(nodeEl.dataset.posX || '0');
    const posY = parseFloat(nodeEl.dataset.posY || '0');
    const requiredWidth = posX + nodeEl.offsetWidth + NODE_PADDING;
    const requiredHeight = posY + nodeEl.offsetHeight + NODE_PADDING;

    if (requiredHeight > workspace.clientHeight) {
      workspace.style.height = `${requiredHeight}px`;
    }
    if (requiredWidth > workspace.clientWidth) {
      workspace.style.minWidth = `${requiredWidth}px`;
    }
  }

  function setNodePosition(nodeEl, x, y) {
    nodeEl.style.left = `${x}px`;
    nodeEl.style.top = `${y}px`;
    nodeEl.dataset.posX = String(x);
    nodeEl.dataset.posY = String(y);
    ensureWorkspaceBounds(nodeEl);
    queueRedraw();
  }

  function clampPosition(x, y) {
    const maxX = Math.max(0, (workspace.clientWidth || 0) + 800);
    const maxY = Math.max(0, (workspace.clientHeight || 0) + 600);
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
    meta.textContent = details.join(' | ');
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

  function calculateExtent() {
    let maxWidth = workspace.clientWidth;
    let maxHeight = workspace.clientHeight;

    Array.from(workspace.querySelectorAll('.architecture-node')).forEach((nodeEl) => {
      const width = parseFloat(nodeEl.dataset.posX || '0') + nodeEl.offsetWidth;
      const height = parseFloat(nodeEl.dataset.posY || '0') + nodeEl.offsetHeight;
      if (width > maxWidth) {
        maxWidth = width;
      }
      if (height > maxHeight) {
        maxHeight = height;
      }
    });
    return {
      width: maxWidth + NODE_PADDING,
      height: maxHeight + NODE_PADDING
    };
  }

  function resizeCanvasToFit() {
    if (!canvasCtx) {
      return;
    }
    const extent = calculateExtent();
    const targetWidth = Math.max(extent.width, workspace.clientWidth || 0);
    const targetHeight = Math.max(extent.height, workspace.clientHeight || 420);

    if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      workspace.style.height = `${targetHeight}px`;
      workspace.style.minWidth = `${targetWidth}px`;
    }
  }

  function drawGrid() {
    if (!canvasCtx) {
      return;
    }
    const step = 60;
    canvasCtx.save();
    canvasCtx.strokeStyle = 'rgba(99, 127, 206, 0.15)';
    canvasCtx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += step) {
      canvasCtx.beginPath();
      canvasCtx.moveTo(x, 0);
      canvasCtx.lineTo(x, canvas.height);
      canvasCtx.stroke();
    }
    for (let y = 0; y < canvas.height; y += step) {
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, y);
      canvasCtx.lineTo(canvas.width, y);
      canvasCtx.stroke();
    }
    canvasCtx.restore();
  }

  function buildSequentialConnections(ids) {
    const filtered = ids.filter(Boolean);
    const result = [];
    for (let i = 0; i < filtered.length - 1; i += 1) {
      result.push({ from: filtered[i], to: filtered[i + 1] });
    }
    return result;
  }

  function sanitiseConnections(connections, nodeIds) {
    const valid = new Set(nodeIds);
    return (connections || []).filter((conn) => conn && valid.has(conn.from) && valid.has(conn.to) && conn.from !== conn.to);
  }

  function queueRedraw() {
    if (!canvasCtx) {
      return;
    }
    if (redrawQueued) {
      return;
    }
    redrawQueued = true;
    window.requestAnimationFrame(() => {
      redrawQueued = false;
      drawConnections();
    });
  }

  function drawConnections() {
    if (!canvasCtx) {
      return;
    }
    resizeCanvasToFit();
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    drawGrid();

    const nodeEls = Array.from(workspace.querySelectorAll('.architecture-node'));
    if (!nodeEls.length) {
      return;
    }
    const nodeMap = new Map(nodeEls.map((el) => [el.dataset.nodeId, el]));
    const nodeIds = nodeEls.map((el) => el.dataset.nodeId);
    let connections = sanitiseConnections(currentLayout.connections, nodeIds);
    if (!connections.length) {
      connections = buildSequentialConnections(nodeIds);
    }

    canvasCtx.strokeStyle = '#3a7ff6';
    canvasCtx.lineWidth = 2;
    canvasCtx.fillStyle = '#3a7ff6';

    connections.forEach((connection) => {
      const fromEl = nodeMap.get(connection.from);
      const toEl = nodeMap.get(connection.to);
      if (!fromEl || !toEl) {
        return;
      }
      const startX = parseFloat(fromEl.dataset.posX || '0') + fromEl.offsetWidth / 2;
      const startY = parseFloat(fromEl.dataset.posY || '0') + fromEl.offsetHeight / 2;
      const endX = parseFloat(toEl.dataset.posX || '0') + toEl.offsetWidth / 2;
      const endY = parseFloat(toEl.dataset.posY || '0') + toEl.offsetHeight / 2;

      canvasCtx.beginPath();
      canvasCtx.moveTo(startX, startY);
      canvasCtx.lineTo(endX, endY);
      canvasCtx.stroke();

      const angle = Math.atan2(endY - startY, endX - startX);
      const arrowLength = 12;
      canvasCtx.beginPath();
      canvasCtx.moveTo(endX, endY);
      canvasCtx.lineTo(
        endX - arrowLength * Math.cos(angle - Math.PI / 6),
        endY - arrowLength * Math.sin(angle - Math.PI / 6)
      );
      canvasCtx.lineTo(
        endX - arrowLength * Math.cos(angle + Math.PI / 6),
        endY - arrowLength * Math.sin(angle + Math.PI / 6)
      );
      canvasCtx.closePath();
      canvasCtx.fill();
    });
  }

  function renderWorkspace() {
    workspace.querySelectorAll('.architecture-node').forEach((node) => node.remove());

    if (!currentLayout.nodes || currentLayout.nodes.length === 0) {
      if (emptyState) {
        emptyState.style.display = 'flex';
      }
      if (canvasCtx) {
        canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
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

    queueRedraw();
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
    const nodeIds = nodes.map((node) => node.id);
    let connections = sanitiseConnections(currentLayout.connections, nodeIds);
    if (!connections.length && nodeIds.length > 1) {
      connections = buildSequentialConnections(nodeIds);
    }
    currentLayout = {
      ...currentLayout,
      nodes,
      connections
    };
    updateHiddenInput();
    queueRedraw();
  }

  function loadLayout(layout) {
    if (!layout || typeof layout !== 'object') {
      currentLayout = { nodes: [], connections: [] };
    } else {
      const nodes = Array.isArray(layout.nodes) ? layout.nodes : [];
      const nodeIds = nodes.map((node) => node.id);
      let connections = sanitiseConnections(layout.connections, nodeIds);
      if (!connections.length && nodeIds.length > 1) {
        connections = buildSequentialConnections(nodeIds);
      }
      currentLayout = { nodes, connections };
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
    queueRedraw();
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
  window.addEventListener('resize', queueRedraw);

  const initial = parseHiddenLayout();
  if (initial) {
    loadLayout(initial);
  } else if (submissionId) {
    fetchSavedLayout();
  } else {
    queueRedraw();
  }
})(); 

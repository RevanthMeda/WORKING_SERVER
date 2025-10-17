(() => {
  const PLACEHOLDER_IMAGE = 'https://via.placeholder.com/320x200.png?text=Device';
  const DEFAULT_NODE_SIZE = { width: 240, height: 160 };
  const API_ROUTES = {
    preview: '/reports/system-architecture/preview',
    layout: (id) => `/reports/system-architecture/layout/${id}`,
    saved: (id) => `/reports/system-architecture/${id}`,
    templates: '/reports/system-architecture/templates',
    template: (id) => `/reports/system-architecture/templates/${id}`,
    versions: (id) => `/reports/system-architecture/versions/${id}`,
    version: (submissionId, versionId) => `/reports/system-architecture/versions/${submissionId}/${versionId}`,
    assets: '/reports/system-architecture/assets/library',
    assetUpload: '/reports/system-architecture/assets/upload',
    live: (id) => `/reports/system-architecture/live/${id}`,
  };

  const KEY = {
    CTRL: 17,
    CMD: 91,
    Z: 90,
    Y: 89,
    C: 67,
    V: 86,
    G: 71,
    DELETE: 46,
  };

  const isModifierKey = (event) => event.ctrlKey || event.metaKey;

  const loadImage = (url) =>
    new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'Anonymous';
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = url || PLACEHOLDER_IMAGE;
    });

  const deepClone = (payload) => JSON.parse(JSON.stringify(payload || {}));

  const defaultPorts = (size = DEFAULT_NODE_SIZE) => [
    { id: 'port-top', side: 'top', position: { x: size.width / 2, y: 0 } },
    { id: 'port-right', side: 'right', position: { x: size.width, y: size.height / 2 } },
    { id: 'port-bottom', side: 'bottom', position: { x: size.width / 2, y: size.height } },
    { id: 'port-left', side: 'left', position: { x: 0, y: size.height / 2 } },
  ];

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  class HistoryStack {
    constructor(limit = 40) {
      this.limit = limit;
      this.entries = [];
      this.index = -1;
    }

    push(state) {
      if (this.index >= 0 && JSON.stringify(this.entries[this.index]) === JSON.stringify(state)) {
        return;
      }
      this.entries = this.entries.slice(0, this.index + 1);
      this.entries.push(deepClone(state));
      if (this.entries.length > this.limit) {
        this.entries.shift();
      }
      this.index = this.entries.length - 1;
    }

    canUndo() {
      return this.index > 0;
    }

    canRedo() {
      return this.index < this.entries.length - 1;
    }

    undo() {
      if (!this.canUndo()) {
        return null;
      }
      this.index -= 1;
      return deepClone(this.entries[this.index]);
    }

    redo() {
      if (!this.canRedo()) {
        return null;
      }
      this.index += 1;
      return deepClone(this.entries[this.index]);
    }
  }

  class ArchitectureDesigner {
    constructor() {
      this.stageContainer = document.getElementById('architecture-stage');
      this.stageWrapper = document.getElementById('architecture-stage-wrapper');
      this.minimapContainer = document.getElementById('architecture-minimap');
      this.gridOverlay = document.getElementById('architecture-grid-overlay');
      this.emptyState = document.getElementById('architecture-empty-state');
      this.hiddenInput = document.getElementById('system_architecture_layout');
      this.statusIndicator = document.getElementById('architecture-status-indicator');
      this.assetList = document.getElementById('arch-asset-list');
      this.templateList = document.getElementById('arch-template-list');

      this.toolbar = document.getElementById('architecture-toolbar');
      this.zoomSlider = document.getElementById('arch-zoom-slider');
      this.zoomInBtn = document.getElementById('arch-zoom-in');
      this.zoomOutBtn = document.getElementById('arch-zoom-out');
      this.toggleGrid = document.getElementById('arch-toggle-grid');
      this.toggleSnap = document.getElementById('arch-toggle-snap');

      this.generateBtn = document.getElementById('btn-generate-architecture');
      this.resetBtn = document.getElementById('btn-architecture-reset');
      this.storeBtn = document.getElementById('btn-architecture-save');
      this.syncBtn = document.getElementById('btn-architecture-sync');
      this.templateSaveBtn = document.getElementById('arch-save-template');
      this.templateNameInput = document.getElementById('arch-template-name');
      this.templateRefreshBtn = document.getElementById('arch-refresh-templates');

      this.assetUploadInput = document.getElementById('arch-upload-asset-input');
      this.liveSyncToggle = document.getElementById('arch-live-sync');
      this.collabStatus = document.getElementById('arch-collab-status');
      this.versionSaveBtn = document.getElementById('arch-save-version');
      this.versionSelector = document.getElementById('arch-version-selector');
      this.exportPngBtn = document.getElementById('arch-export-png');
      this.exportPdfBtn = document.getElementById('arch-export-pdf');

      this.inspector = document.getElementById('architecture-inspector');
      this.inspectorCollapse = document.getElementById('inspector-collapse');
      this.inspectorNodeLabel = document.getElementById('inspector-node-label');
      this.inspectorNodeModel = document.getElementById('inspector-node-model');
      this.inspectorNodeNotes = document.getElementById('inspector-node-notes');
      this.inspectorNodeIp = document.getElementById('inspector-node-ip');
      this.inspectorNodeSlot = document.getElementById('inspector-node-slot');
      this.inspectorNodeTags = document.getElementById('inspector-node-tags');
      this.inspectorNodeApply = document.getElementById('inspector-node-apply');
      this.inspectorConnectionLabel = document.getElementById('inspector-connection-label');
      this.inspectorConnectionType = document.getElementById('inspector-connection-type');
      this.inspectorConnectionColor = document.getElementById('inspector-connection-color');
      this.inspectorConnectionWidth = document.getElementById('inspector-connection-width');
      this.inspectorConnectionStyle = document.getElementById('inspector-connection-style');
      this.inspectorConnectionArrowStart = document.getElementById('inspector-connection-arrow-start');
      this.inspectorConnectionArrowEnd = document.getElementById('inspector-connection-arrow-end');
      this.inspectorConnectionNotes = document.getElementById('inspector-connection-notes');
      this.inspectorConnectionApply = document.getElementById('inspector-connection-apply');
      this.inspectorCanvasBackground = document.getElementById('inspector-canvas-background');
      this.inspectorCanvasGridSize = document.getElementById('inspector-canvas-grid-size');
      this.inspectorCanvasApply = document.getElementById('inspector-canvas-apply');

      this.toolButtons = Array.from(document.querySelectorAll('.tool-btn[data-tool]'));
      this.undoBtn = document.getElementById('arch-undo');
      this.redoBtn = document.getElementById('arch-redo');
      this.copyBtn = document.getElementById('arch-tool-copy');
      this.pasteBtn = document.getElementById('arch-tool-paste');
      this.deleteBtn = document.getElementById('arch-tool-delete');
      this.groupBtn = document.getElementById('arch-tool-group');
      this.ungroupBtn = document.getElementById('arch-tool-ungroup');
      this.alignLeftBtn = document.getElementById('arch-align-left');
      this.alignCenterBtn = document.getElementById('arch-align-center');

      this.inspectSections = Array.from(document.querySelectorAll('.inspector-section'));

      this.submissionId = (document.querySelector('input[name="submission_id"]')?.value || '').trim();
      this.currentUserEmail = (document.querySelector('input[name="prepared_by_email"]')?.value || '').trim();

      this.stage = null;
      this.layers = {
        grid: null,
        connections: null,
        nodes: null,
        overlay: null,
      };
      this.transformer = null;
      this.minimapStage = null;
      this.minimapLayer = null;

      this.layout = {
        canvas: {
          width: 1920,
          height: 1080,
          zoom: 1,
          pan: { x: 0, y: 0 },
          grid: { enabled: true, size: 32, snap: true },
          background: '#f5f7fb',
        },
        nodes: [],
        connections: [],
        groups: [],
        metadata: {},
      };

      this.nodes = new Map();
      this.connections = new Map();
      this.selectedNodes = new Set();
      this.selectedConnectionId = null;
      this.clipboard = null;
      this.currentTool = 'select';
      this.snapToPorts = true;
      this.gridEnabled = true;
      this.zoomLevel = 1;
      this.history = new HistoryStack();
      this.isSyncing = false;
      this.isLiveSyncEnabled = false;
      this.liveSyncTimer = null;
      this.lastLiveTimestamp = null;
      this.lastChecksum = null;
      this.draggedAsset = null;
      this.connectorDraft = null;
      this.isDraggingNodesAsGroup = false;
    }

    init() {
      if (!this.stageContainer || typeof Konva === 'undefined') {
        return;
      }
      this.bindUI();
      this.setupStage();
      this.restoreFromHidden();
      this.refreshTemplates();
      this.refreshAssets();
      this.refreshVersions();
    }

    bindUI() {
      window.addEventListener('resize', () => this.resizeStage());

      if (this.toolbar) {
        this.toolbar.addEventListener('click', (event) => {
          const button = event.target.closest('.tool-btn[data-tool]');
          if (!button) {
            return;
          }
          const tool = button.dataset.tool;
          this.activateTool(tool);
        });
      }

      this.zoomSlider?.addEventListener('input', (event) => {
        const value = Number.parseFloat(event.target.value);
        this.setZoom(value);
      });
      this.zoomInBtn?.addEventListener('click', () => this.setZoom(clamp(this.zoomLevel + 0.1, 0.25, 2.5)));
      this.zoomOutBtn?.addEventListener('click', () => this.setZoom(clamp(this.zoomLevel - 0.1, 0.25, 2.5)));
      this.toggleGrid?.addEventListener('change', (event) => this.toggleGridOverlay(event.target.checked));
      this.toggleSnap?.addEventListener('change', (event) => {
        this.snapToPorts = Boolean(event.target.checked);
      });

      this.generateBtn?.addEventListener('click', () => this.generateFromEquipment());
      this.resetBtn?.addEventListener('click', () => this.resetLayout());
      this.storeBtn?.addEventListener('click', () => this.storeLayout());
      this.syncBtn?.addEventListener('click', () => this.persistToServer());
      this.templateSaveBtn?.addEventListener('click', () => this.saveTemplate());
      this.templateRefreshBtn?.addEventListener('click', () => this.refreshTemplates());
      this.assetUploadInput?.addEventListener('change', (event) => this.handleAssetUpload(event));
      this.liveSyncToggle?.addEventListener('change', (event) => this.toggleLiveSync(event.target.checked));
      this.versionSaveBtn?.addEventListener('click', () => this.saveVersionSnapshot());
      this.versionSelector?.addEventListener('change', (event) => this.loadVersion(event.target.value));
      this.exportPngBtn?.addEventListener('click', () => this.exportPNG());
      this.exportPdfBtn?.addEventListener('click', () => this.exportPDF());
      this.inspectorNodeApply?.addEventListener('click', () => this.applyNodeInspector());
      this.inspectorConnectionApply?.addEventListener('click', () => this.applyConnectionInspector());
      this.inspectorCanvasApply?.addEventListener('click', () => this.applyCanvasInspector());
      this.inspectorCollapse?.addEventListener('click', () => this.toggleInspector());

      this.undoBtn?.addEventListener('click', () => this.undo());
      this.redoBtn?.addEventListener('click', () => this.redo());
      this.copyBtn?.addEventListener('click', () => this.copySelection());
      this.pasteBtn?.addEventListener('click', () => this.pasteClipboard());
      this.deleteBtn?.addEventListener('click', () => this.deleteSelection());
      this.groupBtn?.addEventListener('click', () => this.groupSelection());
      this.ungroupBtn?.addEventListener('click', () => this.ungroupSelection());
      this.alignLeftBtn?.addEventListener('click', () => this.alignSelection('left'));
      this.alignCenterBtn?.addEventListener('click', () => this.alignSelection('center'));

      document.addEventListener('keydown', (event) => this.handleKeydown(event));

      if (this.assetList) {
        this.assetList.addEventListener('dragstart', (event) => this.handleAssetDragStart(event));
        this.assetList.addEventListener('dragend', () => this.handleAssetDragEnd());
      }

      if (this.stageContainer) {
        this.stageContainer.addEventListener('dragover', (event) => {
          if (this.draggedAsset) {
            event.preventDefault();
          }
        });
        this.stageContainer.addEventListener('drop', (event) => {
          if (!this.draggedAsset) {
            return;
          }
          event.preventDefault();
          const pointer = this.stage.getPointerPosition() || { x: 0, y: 0 };
          this.handleAssetDrop(pointer, this.draggedAsset);
          this.draggedAsset = null;
        });
      }
    }

    setupStage() {
      const width = this.stageWrapper.clientWidth || 1200;
      const height = Math.max(this.stageWrapper.clientHeight, 520);

      this.stage = new Konva.Stage({
        container: this.stageContainer,
        width,
        height,
        draggable: true,
        dragBoundFunc: (pos) => ({
          x: pos.x,
          y: pos.y,
        }),
      });

      this.layers.grid = new Konva.Layer({ listening: false });
      this.layers.connections = new Konva.Layer();
      this.layers.nodes = new Konva.Layer();
      this.layers.overlay = new Konva.Layer();

      this.stage.add(this.layers.grid);
      this.stage.add(this.layers.connections);
      this.stage.add(this.layers.nodes);
      this.stage.add(this.layers.overlay);

      this.transformer = new Konva.Transformer({
        rotateEnabled: false,
        padding: 10,
        enabledAnchors: ['top-left', 'top-right', 'bottom-left', 'bottom-right'],
        anchorSize: 8,
      });
      this.layers.nodes.add(this.transformer);

      this.stage.on('click tap', (event) => this.handleStageClick(event));
      this.stage.on('dragmove', () => this.updateMinimap());
      this.stage.on('wheel', (event) => this.handleStageWheel(event));

      this.createMinimap();
      this.setZoom(1);
    }
    createMinimap() {
      if (!this.minimapContainer) {
        return;
      }
      this.minimapStage = new Konva.Stage({
        container: this.minimapContainer,
        width: this.minimapContainer.clientWidth,
        height: this.minimapContainer.clientHeight,
        listening: false,
      });
      this.minimapLayer = new Konva.Layer();
      this.minimapStage.add(this.minimapLayer);
    }

    resizeStage() {
      if (!this.stage) {
        return;
      }
      const width = this.stageWrapper.clientWidth || 1200;
      const height = Math.max(this.stageWrapper.clientHeight, 520);
      this.stage.size({ width, height });
      if (this.minimapStage) {
        this.minimapStage.size({
          width: this.minimapContainer.clientWidth,
          height: this.minimapContainer.clientHeight,
        });
      }
      this.updateMinimap();
    }

    handleStageWheel(event) {
      event.evt.preventDefault();
      const delta = -event.evt.deltaY;
      const zoomBy = delta > 0 ? 1.05 : 0.95;
      const newZoom = clamp(this.stage.scaleX() * zoomBy, 0.25, 2.5);
      this.setZoom(newZoom, this.stage.getPointerPosition());
    }

    setZoom(value, centerPoint = null) {
      if (!this.stage) {
        return;
      }
      const zoom = clamp(Number.parseFloat(value) || 1, 0.25, 2.5);
      const oldScale = this.stage.scaleX();
      const mousePoint = centerPoint || { x: this.stage.width() / 2, y: this.stage.height() / 2 };
      const stagePos = this.stage.position();

      const newPos = {
        x: mousePoint.x - ((mousePoint.x - stagePos.x) * zoom) / oldScale,
        y: mousePoint.y - ((mousePoint.y - stagePos.y) * zoom) / oldScale,
      };

      this.stage.scale({ x: zoom, y: zoom });
      this.stage.position(newPos);
      this.stage.batchDraw();

      this.zoomLevel = zoom;
      if (this.zoomSlider) {
        this.zoomSlider.value = zoom.toFixed(2);
      }
      this.layout.canvas.zoom = zoom;
      this.layout.canvas.pan = { x: newPos.x, y: newPos.y };
      this.updateMinimap();
    }

    toggleGridOverlay(enabled) {
      this.gridEnabled = enabled;
      if (this.gridOverlay) {
        this.gridOverlay.classList.toggle('is-visible', enabled);
      }
      this.layout.canvas.grid = this.layout.canvas.grid || {};
      this.layout.canvas.grid.enabled = enabled;
    }

    activateTool(tool) {
      this.currentTool = tool;
      this.toolButtons.forEach((button) => {
        button.classList.toggle('is-active', button.dataset.tool === tool);
      });
      if (tool !== 'connector') {
        this.endConnectorMode();
      } else {
        this.beginConnectorMode();
      }
      if (tool !== 'text') {
        this.cancelAnnotation();
      }
    }

    beginConnectorMode() {
      this.connectorDraft = null;
      this.nodes.forEach((nodeEntry) => {
        nodeEntry.portLayer?.opacity(1);
      });
    }

    endConnectorMode() {
      this.connectorDraft?.destroy();
      this.connectorDraft = null;
      this.nodes.forEach((nodeEntry) => {
        nodeEntry.portLayer?.opacity(0);
      });
    }

    cancelAnnotation() {
      // Placeholder for future inline annotation flow.
    }

    handleStageClick(event) {
      if (event.target === this.stage) {
        this.clearSelection();
      }
    }

    handleKeydown(event) {
      if (event.keyCode === KEY.DELETE) {
        this.deleteSelection();
        return;
      }
      if (event.keyCode === KEY.Z && isModifierKey(event)) {
        event.preventDefault();
        if (event.shiftKey) {
          this.redo();
        } else {
          this.undo();
        }
        return;
      }
      if (event.keyCode === KEY.Y && isModifierKey(event)) {
        event.preventDefault();
        this.redo();
        return;
      }
      if (event.keyCode === KEY.C && isModifierKey(event)) {
        event.preventDefault();
        this.copySelection();
        return;
      }
      if (event.keyCode === KEY.V && isModifierKey(event)) {
        event.preventDefault();
        this.pasteClipboard();
        return;
      }
      if (event.keyCode === KEY.G && isModifierKey(event) && event.shiftKey) {
        event.preventDefault();
        this.ungroupSelection();
        return;
      }
      if (event.keyCode === KEY.G && isModifierKey(event)) {
        event.preventDefault();
        this.groupSelection();
      }
    }

    restoreFromHidden() {
      const rawValue = this.hiddenInput?.value?.trim();
      if (rawValue) {
        try {
          const layout = JSON.parse(rawValue);
          this.loadLayout(layout, { pushHistory: false });
          return;
        } catch (error) {
          console.warn('Invalid stored layout, fetching from server instead', error);
        }
      }
      if (this.submissionId) {
        this.fetchSavedLayout();
      } else {
        this.applyLayoutDefaults();
      }
    }

    applyLayoutDefaults() {
      this.toggleGridOverlay(true);
      this.setZoom(1);
      this.history.push(this.exportLayout());
    }

    fetchSavedLayout() {
      fetch(API_ROUTES.saved(this.submissionId))
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Request failed (${response.status})`);
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Failed to load saved layout');
          }
          const payload = data.payload || {};
          this.loadLayout(payload, { pushHistory: false });
          if (data.equipment) {
            this.layout.metadata = this.layout.metadata || {};
            this.layout.metadata.equipment_rows = data.equipment;
          }
        })
        .catch((error) => {
          console.warn('Unable to load saved layout', error);
          this.applyLayoutDefaults();
        });
    }

    normaliseLayout(rawLayout) {
      let layout = rawLayout;
      if (typeof layout === 'string') {
        try {
          layout = JSON.parse(layout);
        } catch (error) {
          layout = null;
        }
      }
      const base = deepClone(this.layout);
      if (!layout || typeof layout !== 'object') {
        return base;
      }
      if (layout.canvas) {
        base.canvas = {
          ...base.canvas,
          ...layout.canvas,
          pan: { ...base.canvas.pan, ...(layout.canvas.pan || {}) },
          grid: { ...base.canvas.grid, ...(layout.canvas.grid || {}) },
        };
      }
      base.nodes = Array.isArray(layout.nodes)
        ? layout.nodes.map((node, index) => this.normaliseNode(node, index))
        : [];
      base.connections = Array.isArray(layout.connections)
        ? layout.connections.map((connection) => this.normaliseConnection(connection))
        : [];
      base.groups = Array.isArray(layout.groups) ? layout.groups : [];
      base.metadata = {
        ...layout.metadata,
        generated_at: layout.metadata?.generated_at || new Date().toISOString(),
      };
      base.assetLibrary = Array.isArray(layout.assetLibrary) ? layout.assetLibrary : [];
      return base;
    }
    normaliseNode(node, index) {
      const size = {
        width: Number.parseFloat(node?.size?.width) || DEFAULT_NODE_SIZE.width,
        height: Number.parseFloat(node?.size?.height) || DEFAULT_NODE_SIZE.height,
      };
      return {
        id: node.id || `node-${index + 1}`,
        label: node.label || node.model || 'Device',
        model: node.model || '',
        description: node.description || '',
        quantity: node.quantity || '',
        remarks: node.remarks || '',
        position: {
          x: Number.parseFloat(node.position?.x) || 120 + index * 40,
          y: Number.parseFloat(node.position?.y) || 140 + index * 40,
        },
        size,
        rotation: Number.parseFloat(node.rotation) || 0,
        shape: node.shape || 'rectangle',
        style: {
          fill: node.style?.fill || '#ffffff',
          stroke: node.style?.stroke || '#2d80ff',
          strokeWidth: Number.parseFloat(node.style?.strokeWidth) || 2,
          cornerRadius: Number.parseFloat(node.style?.cornerRadius) || 12,
          shadowColor: node.style?.shadowColor || 'rgba(45,128,255,0.25)',
          shadowBlur: Number.parseFloat(node.style?.shadowBlur) || 12,
          shadowOffset: {
            x: Number.parseFloat(node.style?.shadowOffset?.x) || 0,
            y: Number.parseFloat(node.style?.shadowOffset?.y) || 4,
          },
          shadowOpacity: node.style?.shadowOpacity ?? 0.6,
        },
        image: {
          url: node.image?.url || node.image_url || PLACEHOLDER_IMAGE,
          thumbnail: node.image?.thumbnail || node.thumbnail_url || null,
          source: node.image?.source || node.assetSource || 'placeholder',
        },
        ports: Array.isArray(node.ports) && node.ports.length ? node.ports : defaultPorts(size),
        metadata: {
          ip_address: node.metadata?.ip_address || '',
          slot: node.metadata?.slot || '',
          notes: node.metadata?.notes || '',
          tags: Array.isArray(node.metadata?.tags) ? node.metadata.tags : [],
          equipment: node.metadata?.equipment || {},
          asset: node.metadata?.asset || {},
        },
        groupId: node.groupId || null,
        equipmentIndex: Number.isInteger(node.equipmentIndex) ? node.equipmentIndex : null,
      };
    }

    normaliseConnection(connection) {
      const style = connection.style || {};
      return {
        id: connection.id || `conn-${crypto.randomUUID?.() || Date.now()}`,
        from: {
          nodeId: connection.from?.nodeId || connection.source?.nodeId || connection.source || '',
          portId: connection.from?.portId || connection.source?.portId || connection.from?.port || 'port-right',
        },
        to: {
          nodeId: connection.to?.nodeId || connection.target?.nodeId || connection.target || '',
          portId: connection.to?.portId || connection.target?.portId || connection.to?.port || 'port-left',
        },
        label: connection.label || '',
        type: connection.type || 'generic',
        metadata: connection.metadata || {},
        vertices: Array.isArray(connection.vertices) ? connection.vertices : [],
        style: {
          color: style.color || connection.color || '#1f2937',
          width: Number.parseFloat(style.width || connection.width) || 2,
          dash: Array.isArray(style.dash) ? style.dash : [],
          curve: style.curve || connection.curve || 'straight',
          arrowheads: {
            start: style.arrowheads?.start || connection.arrow_start || 'none',
            end: style.arrowheads?.end || connection.arrow_end || 'triangle',
          },
        },
      };
    }

    loadLayout(rawLayout, options = {}) {
      const layout = this.normaliseLayout(rawLayout);
      this.layout = layout;
      this.nodes.clear();
      this.connections.clear();
      this.selectedNodes.clear();
      this.selectedConnectionId = null;
      this.transformer?.nodes([]);
      this.layers.connections.destroyChildren();
      this.layers.nodes.children
        .filter((child) => child !== this.transformer)
        .forEach((child) => child.destroy());

      this.stage.position({
        x: layout.canvas.pan?.x || 0,
        y: layout.canvas.pan?.y || 0,
      });
      this.setZoom(layout.canvas.zoom || 1);
      this.toggleGridOverlay(layout.canvas.grid?.enabled !== false);
      if (this.gridOverlay) {
        const size = layout.canvas.grid?.size || 32;
        this.gridOverlay.style.backgroundSize = `${size}px ${size}px`;
        this.toggleGrid.value = layout.canvas.grid?.enabled ?? true;
      }
      if (this.stageWrapper) {
        this.stageWrapper.style.background = layout.canvas.background || '#f5f7fb';
      }
      (layout.nodes || []).forEach((node) => this.createNode(node));
      (layout.connections || []).forEach((connection) => this.createConnection(connection));

      this.layers.nodes.batchDraw();
      this.layers.connections.batchDraw();
      this.updateMinimap();
      this.refreshInspector();
      this.refreshAssetLibrary(layout.assetLibrary || []);
      this.toggleEmptyState();

      if (options.pushHistory !== false) {
        this.history.push(this.exportLayout());
      }
      this.updateHiddenInput();
      this.lastChecksum = layout.metadata?.checksum || null;
    }

    toggleEmptyState() {
      const hasNodes = this.nodes.size > 0;
      if (this.emptyState) {
        this.emptyState.style.display = hasNodes ? 'none' : 'flex';
      }
    }

    createNode(nodeData) {
      const node = deepClone(nodeData);
      const group = new Konva.Group({
        id: node.id,
        x: node.position.x,
        y: node.position.y,
        draggable: true,
        rotation: node.rotation || 0,
      });

      const background = new Konva.Rect({
        width: node.size.width,
        height: node.size.height,
        fill: node.style.fill,
        stroke: node.style.stroke,
        strokeWidth: node.style.strokeWidth,
        cornerRadius: node.style.cornerRadius,
        shadowColor: node.style.shadowColor,
        shadowBlur: node.style.shadowBlur,
        shadowOffsetX: node.style.shadowOffset.x,
        shadowOffsetY: node.style.shadowOffset.y,
        shadowOpacity: node.style.shadowOpacity,
      });
      group.add(background);

      const imageHolder = new Konva.Rect({
        x: 12,
        y: 12,
        width: node.size.width - 24,
        height: node.size.height - 86,
        cornerRadius: 10,
        fillLinearGradientColorStops: [0, '#ffffff', 1, '#dde5fb'],
        fillLinearGradientStartPoint: { x: 0, y: 0 },
        fillLinearGradientEndPoint: { x: node.size.width - 24, y: node.size.height - 86 },
        stroke: 'rgba(47,74,132,0.18)',
        strokeWidth: 1,
      });
      group.add(imageHolder);

      const imageNode = new Konva.Image({
        x: 18,
        y: 18,
        width: node.size.width - 36,
        height: node.size.height - 98,
        listening: false,
      });
      group.add(imageNode);

      const label = new Konva.Text({
        text: node.label || 'Device',
        width: node.size.width,
        align: 'center',
        fontFamily: 'Montserrat',
        fontSize: 16,
        fontStyle: '600',
        fill: '#1f2d4f',
        y: node.size.height - 70,
      });
      group.add(label);

      const meta = new Konva.Text({
        text: this.buildNodeMetaString(node),
        width: node.size.width,
        align: 'center',
        fontFamily: 'Montserrat',
        fontSize: 12,
        fill: '#5a688f',
        y: node.size.height - 46,
      });
      group.add(meta);

      const portLayer = new Konva.Group({ listening: true, opacity: 0 });
      group.add(portLayer);

      const portMap = new Map();
      node.ports.forEach((port) => {
        const circle = new Konva.Circle({
          x: port.position.x,
          y: port.position.y,
          radius: 7,
          fill: 'rgba(45,128,255,0.15)',
          stroke: 'rgba(45,128,255,0.45)',
          strokeWidth: 1,
        });
        circle.setAttr('portId', port.id);
        circle.on('mouseenter', () => {
          if (this.currentTool === 'connector') {
            circle.scale({ x: 1.2, y: 1.2 });
            this.stage.container().style.cursor = 'crosshair';
          }
        });
        circle.on('mouseleave', () => {
          circle.scale({ x: 1, y: 1 });
          this.stage.container().style.cursor = 'default';
        });
        circle.on('mousedown touchstart', (event) => {
          event.evt.preventDefault();
          if (this.currentTool === 'connector') {
            this.startConnector(node.id, port.id);
          }
        });
        circle.on('mouseup touchend', (event) => {
          event.evt.preventDefault();
          if (this.currentTool === 'connector' && this.connectorDraft) {
            this.finishConnector(node.id, port.id);
          }
        });
        portLayer.add(circle);
        portMap.set(port.id, circle);
      });

      group.on('dragstart', () => this.handleNodeDragStart(node.id));
      group.on('dragmove', () => this.handleNodeDrag(node.id));
      group.on('dragend', () => this.handleNodeDragEnd(node.id));
      group.on('click tap', (event) => this.handleNodeSelection(event, node.id));
      group.on('mouseenter', () => {
        if (this.currentTool !== 'connector') {
          this.stage.container().style.cursor = 'move';
        }
      });
      group.on('mouseleave', () => {
        this.stage.container().style.cursor = 'default';
      });

      this.layers.nodes.add(group);
      this.layers.nodes.batchDraw();

      this.nodes.set(node.id, {
        data: node,
        group,
        background,
        label,
        meta,
        portLayer,
        portMap,
        imageNode,
      });

      loadImage(node.image?.url || PLACEHOLDER_IMAGE)
        .then((img) => {
          imageNode.image(img);
          imageNode.getLayer().batchDraw();
        })
        .catch(() => {});
    }
    buildNodeMetaString(node) {
      const lines = [];
      if (node.model) {
        lines.push(node.model);
      }
      const ip = node.metadata?.ip_address;
      const slot = node.metadata?.slot;
      if (ip) {
        lines.push(`IP: ${ip}`);
      }
      if (slot) {
        lines.push(`Slot: ${slot}`);
      }
      return lines.join('\n');
    }

    handleNodeSelection(event, nodeId) {
      event.cancelBubble = true;
      if (this.currentTool === 'connector') {
        return;
      }
      if (event.evt.shiftKey || event.evt.ctrlKey || event.evt.metaKey) {
        if (this.selectedNodes.has(nodeId)) {
          this.selectedNodes.delete(nodeId);
        } else {
          this.selectedNodes.add(nodeId);
        }
      } else {
        this.selectedNodes = new Set([nodeId]);
      }
      this.selectedConnectionId = null;
      this.applySelectionStyles();
      this.refreshInspector();
      this.recordHistory();
    }

    applySelectionStyles() {
      const selectedGroups = [];
      this.nodes.forEach((entry, id) => {
        const isSelected = this.selectedNodes.has(id);
        entry.background.stroke(isSelected ? '#1f5af1' : entry.data.style.stroke);
        entry.background.strokeWidth(isSelected ? entry.data.style.strokeWidth + 1 : entry.data.style.strokeWidth);
        entry.group.opacity(isSelected ? 1 : 0.97);
        if (isSelected) {
          selectedGroups.push(entry.group);
        }
      });
      if (this.selectedConnectionId) {
        this.connections.forEach((connection, id) => {
          const isSelected = id === this.selectedConnectionId;
          connection.shape.stroke(isSelected ? '#0f766e' : connection.data.style.color);
          connection.shape.strokeWidth(isSelected ? connection.data.style.width + 1 : connection.data.style.width);
        });
      } else {
        this.connections.forEach((connection) => {
          connection.shape.stroke(connection.data.style.color);
          connection.shape.strokeWidth(connection.data.style.width);
        });
      }
      this.transformer.nodes(selectedGroups);
      this.layers.nodes.batchDraw();
      this.layers.connections.batchDraw();
    }

    clearSelection() {
      this.selectedNodes.clear();
      this.selectedConnectionId = null;
      this.applySelectionStyles();
      this.refreshInspector();
    }

    handleNodeDragStart(nodeId) {
      this.isDraggingNodesAsGroup = this.selectedNodes.size > 1 && this.selectedNodes.has(nodeId);
      if (!this.selectedNodes.has(nodeId)) {
        this.selectedNodes = new Set([nodeId]);
        this.applySelectionStyles();
      }
      this.dragStartPositions = {};
      this.selectedNodes.forEach((id) => {
        const entry = this.nodes.get(id);
        this.dragStartPositions[id] = { x: entry.group.x(), y: entry.group.y() };
      });
    }

    handleNodeDrag(nodeId) {
      const entry = this.nodes.get(nodeId);
      if (!entry) {
        return;
      }
      const { x, y } = entry.group.position();
      entry.data.position = { x, y };
      if (this.isDraggingNodesAsGroup) {
        const origin = this.dragStartPositions[nodeId];
        const deltaX = x - origin.x;
        const deltaY = y - origin.y;
        this.selectedNodes.forEach((id) => {
          if (id === nodeId) {
            return;
          }
          const otherEntry = this.nodes.get(id);
          const startPos = this.dragStartPositions[id];
          otherEntry.group.position({ x: startPos.x + deltaX, y: startPos.y + deltaY });
          otherEntry.data.position = { x: otherEntry.group.x(), y: otherEntry.group.y() };
          otherEntry.group.batchDraw();
        });
      }
      this.updateConnectionsForNode(nodeId);
      this.selectedNodes.forEach((id) => this.updateConnectionsForNode(id));
      this.layers.connections.batchDraw();
    }

    handleNodeDragEnd(nodeId) {
      this.handleNodeDrag(nodeId);
      this.recordHistory();
    }

    startConnector(nodeId, portId) {
      const startPoint = this.getPortAbsolutePosition(nodeId, portId);
      if (!startPoint) {
        return;
      }
      this.connectorDraft?.destroy();
      this.connectorDraft = new Konva.Line({
        points: [startPoint.x, startPoint.y, startPoint.x, startPoint.y],
        stroke: '#1f5af1',
        strokeWidth: 2,
        dash: [8, 4],
        listening: false,
      });
      this.layers.overlay.add(this.connectorDraft);
      this.layers.overlay.batchDraw();

      this.connectorState = {
        fromNode: nodeId,
        fromPort: portId,
      };
      this.stage.on('mousemove.connector', (event) => {
        const position = this.stage.getPointerPosition();
        if (!position || !this.connectorDraft) {
          return;
        }
        this.connectorDraft.points([startPoint.x, startPoint.y, position.x, position.y]);
        this.layers.overlay.batchDraw();
      });
    }

    finishConnector(nodeId, portId) {
      if (!this.connectorState || (this.connectorState.fromNode === nodeId && this.connectorState.fromPort === portId)) {
        this.endConnectorMode();
        this.stage.off('mousemove.connector');
        this.layers.overlay.destroyChildren();
        this.layers.overlay.batchDraw();
        return;
      }
      const newConnection = this.normaliseConnection({
        from: { nodeId: this.connectorState.fromNode, portId: this.connectorState.fromPort },
        to: { nodeId, portId },
        style: this.layout.connectionDefaults || {},
      });
      this.layout.connections.push(newConnection);
      this.createConnection(newConnection);
      this.layers.connections.batchDraw();
      this.recordHistory();
      this.stage.off('mousemove.connector');
      this.layers.overlay.destroyChildren();
      this.layers.overlay.batchDraw();
      this.connectorState = null;
      this.connectorDraft = null;
    }

    createConnection(connectionData) {
      const connection = deepClone(connectionData);
      const { from, to } = connection;
      const start = this.getPortAbsolutePosition(from.nodeId, from.portId);
      const end = this.getPortAbsolutePosition(to.nodeId, to.portId);
      if (!start || !end) {
        return;
      }

      const arrow = new Konva.Arrow({
        id: connection.id,
        points: [start.x, start.y, end.x, end.y],
        stroke: connection.style.color,
        fill: connection.style.color,
        strokeWidth: connection.style.width,
        dash: connection.style.dash,
        pointerLength: 12,
        pointerWidth: 12,
        pointerAtBeginning: connection.style.arrowheads.start !== 'none',
        pointerAtEnding: connection.style.arrowheads.end !== 'none',
        tension: connection.style.curve === 'curved' ? 0.4 : 0,
      });

      arrow.on('click tap', (event) => {
        event.cancelBubble = true;
        this.selectedNodes.clear();
        this.selectedConnectionId = connection.id;
        this.applySelectionStyles();
        this.refreshInspector();
      });

      arrow.on('mouseenter', () => {
        this.stage.container().style.cursor = 'pointer';
      });

      arrow.on('mouseleave', () => {
        this.stage.container().style.cursor = 'default';
      });

      this.layers.connections.add(arrow);
      this.connections.set(connection.id, {
        data: connection,
        shape: arrow,
      });
    }

    updateConnectionsForNode(nodeId) {
      this.connections.forEach((entry) => {
        if (entry.data.from.nodeId === nodeId || entry.data.to.nodeId === nodeId) {
          const start = this.getPortAbsolutePosition(entry.data.from.nodeId, entry.data.from.portId);
          const end = this.getPortAbsolutePosition(entry.data.to.nodeId, entry.data.to.portId);
          if (!start || !end) {
            return;
          }
          entry.shape.points([start.x, start.y, end.x, end.y]);
        }
      });
    }

    getPortAbsolutePosition(nodeId, portId) {
      const entry = this.nodes.get(nodeId);
      if (!entry) {
        return null;
      }
      const circle = entry.portMap.get(portId) || Array.from(entry.portMap.values())[0];
      if (!circle) {
        return null;
      }
      const position = circle.getAbsolutePosition();
      return position;
    }

    recordHistory() {
      this.history.push(this.exportLayout());
    }

    undo() {
      const previous = this.history.undo();
      if (!previous) {
        return;
      }
      this.loadLayout(previous, { pushHistory: false });
    }
    redo() {
      const next = this.history.redo();
      if (!next) {
        return;
      }
      this.loadLayout(next, { pushHistory: false });
    }

    copySelection() {
      if (!this.selectedNodes.size) {
        return;
      }
      const layout = this.exportLayout();
      const selectedNodes = layout.nodes.filter((node) => this.selectedNodes.has(node.id));
      const connections = layout.connections.filter(
        (connection) => this.selectedNodes.has(connection.from.nodeId) && this.selectedNodes.has(connection.to.nodeId)
      );
      this.clipboard = { nodes: selectedNodes, connections };
      this.showStatus('Copied selection');
    }

    pasteClipboard() {
      if (!this.clipboard || !this.clipboard.nodes?.length) {
        return;
      }
      const offset = 40;
      const idMap = new Map();
      this.clipboard.nodes.forEach((node) => {
        const newNode = deepClone(node);
        newNode.id = `node-${crypto.randomUUID?.() || Date.now()}`;
        newNode.position = {
          x: node.position.x + offset,
          y: node.position.y + offset,
        };
        newNode.label = `${node.label} Copy`;
        idMap.set(node.id, newNode.id);
        this.layout.nodes.push(newNode);
        this.createNode(newNode);
        this.selectedNodes.add(newNode.id);
      });
      this.clipboard.connections.forEach((connection) => {
        const newConnection = deepClone(connection);
        newConnection.id = `conn-${crypto.randomUUID?.() || Date.now()}`;
        newConnection.from.nodeId = idMap.get(connection.from.nodeId);
        newConnection.to.nodeId = idMap.get(connection.to.nodeId);
        if (newConnection.from.nodeId && newConnection.to.nodeId) {
          this.layout.connections.push(newConnection);
          this.createConnection(newConnection);
        }
      });
      this.applySelectionStyles();
      this.recordHistory();
      this.showStatus('Pasted selection');
    }

    deleteSelection() {
      if (this.selectedConnectionId) {
        this.deleteConnection(this.selectedConnectionId);
        this.selectedConnectionId = null;
        this.refreshInspector();
        this.recordHistory();
        return;
      }
      if (!this.selectedNodes.size) {
        return;
      }
      this.selectedNodes.forEach((nodeId) => this.deleteNode(nodeId));
      this.selectedNodes.clear();
      this.applySelectionStyles();
      this.refreshInspector();
      this.recordHistory();
    }

    deleteNode(nodeId) {
      const entry = this.nodes.get(nodeId);
      if (!entry) {
        return;
      }
      entry.group.destroy();
      this.nodes.delete(nodeId);
      this.layout.nodes = this.layout.nodes.filter((node) => node.id !== nodeId);
      const connectionIds = [];
      this.connections.forEach((connection, id) => {
        if (connection.data.from.nodeId === nodeId || connection.data.to.nodeId === nodeId) {
          connectionIds.push(id);
        }
      });
      connectionIds.forEach((id) => this.deleteConnection(id));
      this.layers.nodes.batchDraw();
      this.layers.connections.batchDraw();
    }

    deleteConnection(connectionId) {
      const entry = this.connections.get(connectionId);
      if (!entry) {
        return;
      }
      entry.shape.destroy();
      this.connections.delete(connectionId);
      this.layout.connections = this.layout.connections.filter((connection) => connection.id !== connectionId);
      this.layers.connections.batchDraw();
    }

    groupSelection() {
      if (this.selectedNodes.size < 2) {
        return;
      }
      const groupId = `group-${crypto.randomUUID?.() || Date.now()}`;
      this.layout.groups = this.layout.groups || [];
      this.layout.groups.push({ id: groupId, nodes: Array.from(this.selectedNodes) });
      this.selectedNodes.forEach((nodeId) => {
        const entry = this.nodes.get(nodeId);
        if (entry) {
          entry.data.groupId = groupId;
        }
      });
      this.showStatus('Grouped devices');
      this.recordHistory();
    }

    ungroupSelection() {
      if (!this.selectedNodes.size) {
        return;
      }
      const groupIds = new Set();
      this.selectedNodes.forEach((nodeId) => {
        const entry = this.nodes.get(nodeId);
        if (entry?.data.groupId) {
          groupIds.add(entry.data.groupId);
          entry.data.groupId = null;
        }
      });
      this.layout.groups = (this.layout.groups || []).filter((group) => !groupIds.has(group.id));
      this.showStatus('Ungrouped devices');
      this.recordHistory();
    }

    alignSelection(mode) {
      if (this.selectedNodes.size < 2) {
        return;
      }
      const nodes = Array.from(this.selectedNodes).map((id) => this.nodes.get(id));
      if (mode === 'left') {
        const minX = Math.min(...nodes.map((entry) => entry.group.x()));
        nodes.forEach((entry) => {
          entry.group.x(minX);
          entry.data.position.x = minX;
        });
      }
      if (mode === 'center') {
        const averageX =
          nodes.reduce((sum, entry) => sum + entry.group.x() + entry.data.size.width / 2, 0) / nodes.length;
        nodes.forEach((entry) => {
          const x = averageX - entry.data.size.width / 2;
          entry.group.x(x);
          entry.data.position.x = x;
        });
      }
      nodes.forEach((entry) => this.updateConnectionsForNode(entry.data.id));
      this.layers.nodes.batchDraw();
      this.layers.connections.batchDraw();
      this.recordHistory();
    }

    refreshInspector() {
      if (!this.inspectSections.length) {
        return;
      }
      this.inspectSections.forEach((section) => section.classList.remove('is-visible'));
      if (this.selectedConnectionId) {
        const connection = this.connections.get(this.selectedConnectionId)?.data;
        if (!connection) {
          return;
        }
        this.inspectorConnectionLabel.value = connection.label || '';
        this.inspectorConnectionType.value = connection.type || '';
        this.inspectorConnectionColor.value = connection.style.color || '#1f2937';
        this.inspectorConnectionWidth.value = connection.style.width || 2;
        this.inspectorConnectionStyle.value = connection.style.curve || 'straight';
        this.inspectorConnectionArrowStart.value = connection.style.arrowheads.start || 'none';
        this.inspectorConnectionArrowEnd.value = connection.style.arrowheads.end || 'triangle';
        this.inspectorConnectionNotes.value = connection.metadata?.notes || '';
        this.showInspectorSection('connection');
        return;
      }
      if (this.selectedNodes.size === 1) {
        const nodeId = Array.from(this.selectedNodes)[0];
        const entry = this.nodes.get(nodeId);
        if (!entry) {
          return;
        }
        const node = entry.data;
        this.inspectorNodeLabel.value = node.label || '';
        this.inspectorNodeModel.value = node.model || '';
        this.inspectorNodeNotes.value = node.metadata?.notes || '';
        this.inspectorNodeIp.value = node.metadata?.ip_address || '';
        this.inspectorNodeSlot.value = node.metadata?.slot || '';
        this.inspectorNodeTags.value = (node.metadata?.tags || []).join(', ');
        this.showInspectorSection('node');
        return;
      }
      this.inspectorCanvasBackground.value = this.layout.canvas.background || '#f5f7fb';
      this.inspectorCanvasGridSize.value = this.layout.canvas.grid?.size || 32;
      this.showInspectorSection('canvas');
    }

    showInspectorSection(view) {
      this.inspectSections.forEach((section) => {
        section.classList.toggle('is-visible', section.dataset.view === view);
      });
    }

    applyNodeInspector() {
      if (this.selectedNodes.size !== 1) {
        return;
      }
      const nodeId = Array.from(this.selectedNodes)[0];
      const entry = this.nodes.get(nodeId);
      if (!entry) {
        return;
      }
      const node = entry.data;
      node.label = this.inspectorNodeLabel.value.trim() || node.label;
      node.model = this.inspectorNodeModel.value.trim();
      node.metadata = node.metadata || {};
      node.metadata.notes = this.inspectorNodeNotes.value.trim();
      node.metadata.ip_address = this.inspectorNodeIp.value.trim();
      node.metadata.slot = this.inspectorNodeSlot.value.trim();
      node.metadata.tags = this.inspectorNodeTags.value
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean);

      entry.label.text(node.label);
      entry.meta.text(this.buildNodeMetaString(node));
      this.layers.nodes.batchDraw();
      this.recordHistory();
      this.showStatus('Updated device details');
    }

    applyConnectionInspector() {
      if (!this.selectedConnectionId) {
        return;
      }
      const entry = this.connections.get(this.selectedConnectionId);
      if (!entry) {
        return;
      }
      const connection = entry.data;
      connection.label = this.inspectorConnectionLabel.value.trim();
      connection.type = this.inspectorConnectionType.value.trim();
      connection.style.color = this.inspectorConnectionColor.value || '#1f2937';
      connection.style.width = Number.parseFloat(this.inspectorConnectionWidth.value) || 2;
      connection.style.curve = this.inspectorConnectionStyle.value || 'straight';
      connection.style.arrowheads.start = this.inspectorConnectionArrowStart.value || 'none';
      connection.style.arrowheads.end = this.inspectorConnectionArrowEnd.value || 'triangle';
      connection.metadata = connection.metadata || {};
      connection.metadata.notes = this.inspectorConnectionNotes.value.trim();

      entry.shape.stroke(connection.style.color);
      entry.shape.fill(connection.style.color);
      entry.shape.strokeWidth(connection.style.width);
      entry.shape.pointerAtBeginning(connection.style.arrowheads.start !== 'none');
      entry.shape.pointerAtEnding(connection.style.arrowheads.end !== 'none');
      entry.shape.dash(connection.style.dash || []);
      entry.shape.tension(connection.style.curve === 'curved' ? 0.4 : 0);
      this.layers.connections.batchDraw();
      this.recordHistory();
      this.showStatus('Updated connection details');
    }

    applyCanvasInspector() {
      const background = this.inspectorCanvasBackground.value || '#f5f7fb';
      const gridSize = Number.parseInt(this.inspectorCanvasGridSize.value, 10) || 32;
      this.layout.canvas.background = background;
      this.layout.canvas.grid = this.layout.canvas.grid || {};
      this.layout.canvas.grid.size = gridSize;
      if (this.stageWrapper) {
        this.stageWrapper.style.background = background;
      }
      if (this.gridOverlay) {
        this.gridOverlay.style.backgroundSize = `${gridSize}px ${gridSize}px`;
      }
      this.recordHistory();
      this.showStatus('Applied canvas settings');
    }

    toggleInspector() {
      this.inspector?.classList.toggle('is-collapsed');
    }

    collectEquipmentRows() {
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
          Remarks: remarks,
        });
      });
      return rows;
    }
    generateFromEquipment() {
      const equipment = this.collectEquipmentRows();
      if (!equipment.length) {
        window.alert('Add equipment details in Step 4 before generating the architecture.');
        return;
      }
      const payload = {
        submission_id: this.submissionId,
        equipment,
        existing_layout: this.exportLayout(),
      };
      this.showStatus('Generating layout from equipment...');
      fetch(API_ROUTES.preview, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
          this.loadLayout(data.payload);
          this.showStatus('Draft architecture generated');
        })
        .catch((error) => {
          console.error('Architecture preview failed', error);
          window.alert('Unable to generate architecture preview. Please try again.');
        });
    }

    resetLayout() {
      if (!window.confirm('Reset the current layout? This cannot be undone.')) {
        return;
      }
      this.layout.nodes = [];
      this.layout.connections = [];
      this.layout.groups = [];
      this.loadLayout(this.layout);
      this.showStatus('Canvas cleared');
    }

    exportLayout() {
      const layout = deepClone(this.layout);
      layout.canvas.pan = { ...this.stage.position() };
      layout.canvas.zoom = this.zoomLevel;
      layout.nodes = Array.from(this.nodes.values()).map((entry) => {
        const node = entry.data;
        return {
          ...node,
          position: {
            x: entry.group.x(),
            y: entry.group.y(),
          },
          rotation: entry.group.rotation(),
        };
      });
      layout.connections = Array.from(this.connections.values()).map((entry) => entry.data);
      return layout;
    }

    storeLayout() {
      const layout = this.exportLayout();
      try {
        if (this.hiddenInput) {
          this.hiddenInput.value = JSON.stringify(layout);
        }
        this.showStatus('Layout stored in form');
      } catch (error) {
        window.alert('Unable to serialise architecture layout.');
      }
    }

    persistToServer() {
      if (!this.submissionId) {
        window.alert('Save the FDS at least once to enable server sync.');
        return;
      }
      const layout = this.exportLayout();
      this.updateStatus('saving', 'Saving...');
      fetch(API_ROUTES.layout(this.submissionId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layout }),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Sync failed (${response.status})`);
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Sync failed');
          }
          this.updateStatus('synced', 'Synced');
          if (data.version) {
            this.lastLiveTimestamp = data.version.created_at;
            this.refreshVersions();
          }
        })
        .catch((error) => {
          console.error('Failed to sync layout', error);
          this.updateStatus('idle', 'Sync failed');
          window.alert('Unable to sync layout. Please try again.');
        });
    }

    updateStatus(state, label) {
      if (!this.statusIndicator) {
        return;
      }
      this.statusIndicator.dataset.state = state;
      this.statusIndicator.querySelector('.status-label').textContent = label;
      if (state !== 'saving') {
        setTimeout(() => {
          this.statusIndicator.dataset.state = 'idle';
          this.statusIndicator.querySelector('.status-label').textContent = 'Idle';
        }, 3000);
      }
    }

    refreshAssetLibrary(assetLibrary = []) {
      if (!this.assetList) {
        return;
      }
      this.assetList.innerHTML = '';
      const assets = assetLibrary.length ? assetLibrary : this.layout.assetLibrary || [];
      if (!assets.length) {
        const empty = document.createElement('p');
        empty.className = 'panel-empty';
        empty.textContent = 'No assets available. Upload or generate from equipment.';
        this.assetList.appendChild(empty);
        return;
      }
      assets.forEach((asset) => {
        const tile = document.createElement('button');
        tile.type = 'button';
        tile.className = 'asset-tile';
        tile.draggable = true;
        tile.dataset.asset = JSON.stringify(asset);
        const img = document.createElement('img');
        img.src = asset.thumbnail_url || asset.image_url || PLACEHOLDER_IMAGE;
        img.alt = asset.display_name || asset.model_key;
        const label = document.createElement('span');
        label.textContent = asset.display_name || asset.model_key;
        tile.appendChild(img);
        tile.appendChild(label);
        tile.addEventListener('click', () => this.addNodeFromAsset(asset));
        this.assetList.appendChild(tile);
      });
    }

    refreshAssets() {
      fetch(API_ROUTES.assets)
        .then((response) => {
          if (!response.ok) {
            throw new Error('Asset fetch failed');
          }
          return response.json();
        })
        .then((data) => {
          if (data?.success && Array.isArray(data.assets)) {
            this.layout.assetLibrary = data.assets;
            this.refreshAssetLibrary(data.assets);
          }
        })
        .catch((error) => {
          console.warn('Unable to load asset library', error);
        });
    }

    handleAssetDragStart(event) {
      const tile = event.target.closest('.asset-tile');
      if (!tile?.dataset.asset) {
        return;
      }
      this.draggedAsset = JSON.parse(tile.dataset.asset);
      event.dataTransfer.effectAllowed = 'copy';
    }

    handleAssetDragEnd() {
      this.draggedAsset = null;
    }

    handleAssetDrop(position, asset) {
      if (!asset) {
        return;
      }
      const shape = this.stage.getIntersection(position);
      if (shape) {
        const nodeGroup = shape.findAncestor('Group');
        if (nodeGroup) {
          const nodeId = nodeGroup.id();
          this.updateNodeImage(nodeId, asset);
          this.recordHistory();
          return;
        }
      }
      this.addNodeFromAsset(asset, position);
    }

    updateNodeImage(nodeId, asset) {
      const entry = this.nodes.get(nodeId);
      if (!entry) {
        return;
      }
      entry.data.image = {
        url: asset.image_url || (asset.local_path ? `/${asset.local_path}` : PLACEHOLDER_IMAGE),
        thumbnail: asset.thumbnail_url || null,
        source: asset.asset_source || 'library',
      };
      entry.data.metadata = entry.data.metadata || {};
      entry.data.metadata.asset = asset;
      loadImage(entry.data.image.url)
        .then((img) => {
          entry.imageNode.image(img);
          entry.imageNode.getLayer().batchDraw();
        })
        .catch(() => {});
      this.showStatus('Updated device image');
    }

    addNodeFromAsset(asset, position = { x: 160, y: 160 }) {
      const id = `node-${crypto.randomUUID?.() || Date.now()}`;
      const node = this.normaliseNode(
        {
          id,
          label: asset.display_name || asset.model_key || 'Device',
          model: asset.display_name || '',
          position,
          image: {
            url: asset.image_url || (asset.local_path ? `/${asset.local_path}` : PLACEHOLDER_IMAGE),
            thumbnail: asset.thumbnail_url,
            source: asset.asset_source || 'library',
          },
          metadata: {
            asset,
          },
        },
        this.layout.nodes.length
      );
      this.layout.nodes.push(node);
      this.createNode(node);
      this.selectedNodes = new Set([node.id]);
      this.applySelectionStyles();
      this.recordHistory();
      this.showStatus('Added device to canvas');
    }

    handleAssetUpload(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      formData.append('model_name', file.name.replace(/\.[^/.]+$/, ''));
      fetch(API_ROUTES.assetUpload, {
        method: 'POST',
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error('Upload failed');
          }
          return response.json();
        })
        .then((data) => {
          if (data?.success && data.asset) {
            this.layout.assetLibrary = this.layout.assetLibrary || [];
            this.layout.assetLibrary.unshift(data.asset);
            this.refreshAssetLibrary(this.layout.assetLibrary);
            this.showStatus('Asset uploaded');
          }
        })
        .catch((error) => {
          console.error('Asset upload failed', error);
          window.alert('Failed to upload asset image. Try a different file.');
        })
        .finally(() => {
          event.target.value = '';
        });
    }

    refreshTemplates() {
      fetch(API_ROUTES.templates)
        .then((response) => {
          if (!response.ok) {
            throw new Error('Template fetch failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Template fetch failed');
          }
          this.renderTemplateList(data.templates || []);
        })
        .catch((error) => {
          console.warn('Unable to load templates', error);
        });
    }

    renderTemplateList(templates) {
      if (!this.templateList) {
        return;
      }
      this.templateList.innerHTML = '';
      if (!templates.length) {
        const empty = document.createElement('p');
        empty.className = 'panel-empty';
        empty.textContent = 'No templates yet.';
        this.templateList.appendChild(empty);
        return;
      }
      templates.forEach((template) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'template-item';
        item.innerHTML = `
          <strong>${template.name}</strong>
          <span>${template.description || 'No description'}</span>
        `;
        item.addEventListener('click', () => this.applyTemplate(template.id));
        this.templateList.appendChild(item);
      });
    }
    saveTemplate() {
      const name = this.templateNameInput?.value?.trim();
      if (!name) {
        window.alert('Provide a name for the template.');
        return;
      }
      const layout = this.exportLayout();
      const payload = {
        name,
        layout,
        description: `Saved on ${new Date().toLocaleString()}`,
        is_shared: true,
      };
      fetch(API_ROUTES.templates, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error('Template save failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Template save failed');
          }
          this.templateNameInput.value = '';
          this.refreshTemplates();
          this.showStatus('Template saved');
        })
        .catch((error) => {
          console.error('Failed to save template', error);
          window.alert('Unable to save template. Please try again.');
        });
    }

    applyTemplate(templateId) {
      fetch(API_ROUTES.template(templateId))
        .then((response) => {
          if (!response.ok) {
            throw new Error('Template fetch failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Template fetch failed');
          }
          if (data.template?.layout) {
            this.loadLayout(data.template.layout);
            this.showStatus(`Template "${data.template.name}" applied`);
          }
        })
        .catch((error) => {
          console.error('Failed to apply template', error);
          window.alert('Unable to load template.');
        });
    }

    refreshVersions() {
      if (!this.submissionId || !this.versionSelector) {
        return;
      }
      fetch(`${API_ROUTES.versions(this.submissionId)}?limit=15`)
        .then((response) => {
          if (!response.ok) {
            throw new Error('Version fetch failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Version fetch failed');
          }
          this.versionSelector.innerHTML = '<option value="">Version history</option>';
          data.versions.forEach((version) => {
            const option = document.createElement('option');
            option.value = version.id;
            option.textContent = `${version.version_label || version.id} • ${new Date(
              version.created_at
            ).toLocaleString()}`;
            this.versionSelector.appendChild(option);
          });
        })
        .catch((error) => {
          console.warn('Unable to load versions', error);
        });
    }

    saveVersionSnapshot() {
      if (!this.submissionId) {
        window.alert('Save the FDS at least once to enable snapshots.');
        return;
      }
      const note = window.prompt('Optional: add a note for this snapshot', '');
      const payload = {
        layout: this.exportLayout(),
        note,
      };
      fetch(API_ROUTES.versions(this.submissionId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error('Snapshot failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            throw new Error('Snapshot failed');
          }
          this.refreshVersions();
          this.showStatus('Snapshot saved');
        })
        .catch((error) => {
          console.error('Unable to save snapshot', error);
          window.alert('Unable to save snapshot. Try again later.');
        });
    }

    loadVersion(versionId) {
      if (!versionId) {
        return;
      }
      fetch(API_ROUTES.version(this.submissionId, versionId))
        .then((response) => {
          if (!response.ok) {
            throw new Error('Version fetch failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success || !data.version?.layout) {
            throw new Error('Version not found');
          }
          if (window.confirm('Load version snapshot? Unsaved changes will be replaced.')) {
            this.loadLayout(data.version.layout);
            this.showStatus('Version loaded');
          } else {
            this.versionSelector.value = '';
          }
        })
        .catch((error) => {
          console.error('Unable to load version', error);
          window.alert('Unable to load version.');
        });
    }

    toggleLiveSync(enabled) {
      this.isLiveSyncEnabled = enabled;
      if (enabled) {
        this.startLivePolling();
        this.collabStatus.innerHTML = '<i class="fas fa-users"></i> Live';
      } else {
        this.stopLivePolling();
        this.collabStatus.innerHTML = '<i class="fas fa-user-slash"></i> Offline';
      }
    }

    startLivePolling() {
      this.stopLivePolling();
      if (!this.submissionId) {
        return;
      }
      this.liveSyncTimer = window.setInterval(() => this.fetchLiveUpdates(), 5000);
      this.fetchLiveUpdates();
    }

    stopLivePolling() {
      if (this.liveSyncTimer) {
        window.clearInterval(this.liveSyncTimer);
        this.liveSyncTimer = null;
      }
    }

    fetchLiveUpdates() {
      if (!this.submissionId) {
        return;
      }
      const params = new URLSearchParams();
      if (this.lastLiveTimestamp) {
        params.set('since', this.lastLiveTimestamp);
      }
      fetch(`${API_ROUTES.live(this.submissionId)}?${params.toString()}`)
        .then((response) => {
          if (!response.ok) {
            throw new Error('Live polling failed');
          }
          return response.json();
        })
        .then((data) => {
          if (!data?.success) {
            return;
          }
          if (Array.isArray(data.updates) && data.updates.length) {
            this.applyLiveUpdates(data.updates);
            this.lastLiveTimestamp = data.timestamp || data.updates[data.updates.length - 1].created_at;
          } else if (data.latest && !this.lastChecksum) {
            this.loadLayout(data.latest, { pushHistory: false });
            this.lastChecksum = data.latest.metadata?.checksum || null;
          }
        })
        .catch((error) => {
          console.warn('Live updates not available', error);
        });
    }

    applyLiveUpdates(updates) {
      const latest = updates[updates.length - 1];
      if (!latest?.layout) {
        return;
      }
      const checksum = latest.checksum;
      if (checksum && checksum === this.lastChecksum) {
        return;
      }
      this.lastChecksum = checksum;
      this.loadLayout(latest.layout, { pushHistory: false });
      this.showStatus('Live update applied');
    }

    exportPNG() {
      this.stage.toDataURL({
        pixelRatio: 2,
        callback: (dataUrl) => {
          const link = document.createElement('a');
          link.download = `fds-architecture-${Date.now()}.png`;
          link.href = dataUrl;
          link.click();
        },
      });
    }

    exportPDF() {
      if (!window.jspdf || !window.jspdf.jsPDF) {
        window.alert('PDF export requires jsPDF (missing dependency).');
        return;
      }
      this.stage.toDataURL({
        pixelRatio: 2,
        callback: (dataUrl) => {
          const pdf = new window.jspdf.jsPDF({
            orientation: 'landscape',
            unit: 'px',
            format: [this.stage.width(), this.stage.height()],
          });
          pdf.addImage(dataUrl, 'PNG', 0, 0, this.stage.width(), this.stage.height());
          pdf.save(`fds-architecture-${Date.now()}.pdf`);
        },
      });
    }

    showStatus(message) {
      if (!this.statusIndicator) {
        return;
      }
      this.statusIndicator.dataset.state = 'saving';
      this.statusIndicator.querySelector('.status-label').textContent = message;
      window.setTimeout(() => {
        this.statusIndicator.dataset.state = 'idle';
        this.statusIndicator.querySelector('.status-label').textContent = 'Idle';
      }, 2500);
    }

    updateHiddenInput() {
      if (!this.hiddenInput) {
        return;
      }
      try {
        this.hiddenInput.value = JSON.stringify(this.exportLayout());
      } catch (error) {
        console.warn('Failed to serialise layout', error);
      }
    }

    updateMinimap() {
      if (!this.minimapStage) {
        return;
      }
      this.minimapLayer.destroyChildren();
      const scaleX = this.minimapStage.width() / this.layout.canvas.width;
      const scaleY = this.minimapStage.height() / this.layout.canvas.height;
      const scale = Math.min(scaleX, scaleY);

      this.nodes.forEach((entry) => {
        const rect = new Konva.Rect({
          x: entry.group.x() * scale,
          y: entry.group.y() * scale,
          width: entry.data.size.width * scale,
          height: entry.data.size.height * scale,
          fill: 'rgba(79,119,255,0.6)',
        });
        this.minimapLayer.add(rect);
      });

      this.minimapLayer.batchDraw();
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const designer = new ArchitectureDesigner();
    designer.init();
  });
})();

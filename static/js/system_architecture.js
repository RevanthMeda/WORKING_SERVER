(() => {
  const PLACEHOLDER_IMAGE = '/static/img/architecture-placeholder.svg';
  const DEFAULT_NODE_SIZE = { width: 240, height: 160 };
  const DEFAULT_NODE_STYLE = {
    fill: '#ffffff',
    stroke: '#2d80ff',
    strokeWidth: 2,
    cornerRadius: 12,
  };

  const goNamespaceMissing = () => {
    window.alert('The diagramming library failed to load. Check your network connection and reload the page.');
  };

  const normaliseImageUrl = (value) => {
    if (!value) {
      return null;
    }
    if (/^(https?:)?\/\//i.test(value) || value.startsWith('data:')) {
      return value;
    }
    let path = value.replace(/\\/g, '/').replace(/^\.\//, '');
    if (!path.startsWith('/')) {
      path = `/${path}`;
    }
    return path;
  };

  const $ = (id) => document.getElementById(id);

  let diagram;
  let hiddenInput;
  let statusIndicator;
  let assetList;
  let templateList;
  let templateNameInput;
  let lastPersistTimeout = null;
  let pendingValidationTimeout = null;
  let assetLibrary = [];
  let submissionId = '';
  let currentUserEmail = '';
  let portsVisible = false;
  let nodeKeySeed = 0;
  let linkKeySeed = 0;
  let layerList;
  let addLayerBtn;
  let layers = [];
  let activeLayer = 'Default';
  let customModules = [];
  let selectedModuleId = '';
  let chatMessages = [];
  let annotationNotes = [];
  let measurementEnabled = false;
  let collaboratorPresence = [];
  let lockedNodes = new Set();
  let lastValidationResults = [];
  let lastSimulationResults = [];
  let moduleList;
  let moduleNameInput;
  let moduleSaveBtn;
  let moduleInsertBtn;
  let moduleRefreshBtn;
  let highContrastToggle;
  let colorblindToggle;
  let layerLockToggle;
  let layerIsolationToggle;
  let shortcutsBtn;
  let toolPanBtn;
  let duplicateBtn;
  let createModuleBtn;
  let distributeHorizontalBtn;
  let distributeVerticalBtn;
  let autoArrangeBtn;
  let autoRouteBtn;
  let highlightFlowBtn;
  let validateToolbarBtn;
  let snapPortsToggle;
  let rulersToggle;
  let measureToggle;
  let validationBtn;
  let autoValidationToggle;
  let validationResultsList;
  let simulationBtn;
  let simulationResultsList;
  let simulationReportBtn;
  let collaboratorList;
  let lockSelectionBtn;
  let chatLog;
  let chatMessageInput;
  let chatSendBtn;
  let annotationList;
  let addStickyBtn;
  let addCalloutBtn;
  let importJsonBtn;
  let importVisioBtn;
  let importDxfBtn;
  let syncPlcBtn;
  let exportSvgBtn;
  let exportReportBtn;
  let stageWrapper;
  let rulerHorizontal;
  let rulerVertical;
  let cursorsLayer;
  let annotationLayer;
  let measureOverlay;
  let toolButtons = [];

  const inspectorFields = {
    label: $('inspector-node-label'),
    model: $('inspector-node-model'),
    notes: $('inspector-node-notes'),
    ip: $('inspector-node-ip'),
    slot: $('inspector-node-slot'),
    tags: $('inspector-node-tags'),
    layer: $('inspector-node-layer'),
    protocol: $('inspector-node-protocol'),
    signalType: $('inspector-node-signal-type'),
    power: $('inspector-node-power'),
    status: $('inspector-node-status'),
    apply: $('inspector-node-apply'),
    container: document.querySelector('.inspector-section[data-view="node"]'),
  };

  const inspectorConnectionFields = {
    label: $('inspector-connection-label'),
    type: $('inspector-connection-type'),
    color: $('inspector-connection-color'),
    width: $('inspector-connection-width'),
    style: $('inspector-connection-style'),
    arrowStart: $('inspector-connection-arrow-start'),
    arrowEnd: $('inspector-connection-arrow-end'),
    badges: $('inspector-connection-badges'),
    notes: $('inspector-connection-notes'),
    apply: $('inspector-connection-apply'),
    container: document.querySelector('.inspector-section[data-view="connection"]'),
  };

  const canvasInspectorFields = {
    background: $('inspector-canvas-background'),
    gridSize: $('inspector-canvas-grid-size'),
    width: $('inspector-canvas-width'),
    height: $('inspector-canvas-height'),
    apply: $('inspector-canvas-apply'),
    container: document.querySelector('.inspector-section[data-view="canvas"]'),
  };

  const bulkInspectorFields = {
    layer: $('inspector-bulk-layer'),
    signal: $('inspector-bulk-signal'),
    color: $('inspector-bulk-color'),
    container: document.querySelector('.inspector-section[data-view="bulk"]'),
  };

  const filterFields = {
    search: $('inspector-filter-search'),
    component: $('inspector-filter-component'),
    status: $('inspector-filter-status'),
    apply: $('inspector-apply-filter'),
    clear: $('inspector-clear-filter'),
    container: document.querySelector('.inspector-section[data-view="filters"]'),
  };

  const emptyState = $('architecture-empty-state');
  const gridToggle = $('arch-toggle-grid');
  const snapToggle = $('arch-toggle-snap');
  const zoomSlider = $('arch-zoom-slider');
  const zoomInBtn = $('arch-zoom-in');
  const zoomOutBtn = $('arch-zoom-out');
  const toolSelectBtn = $('arch-tool-select');
  const toolConnectorBtn = $('arch-tool-connector');
  const toolAnnotationBtn = $('arch-tool-annotation');
  const copyBtn = $('arch-tool-copy');
  const pasteBtn = $('arch-tool-paste');
  const deleteBtn = $('arch-tool-delete');
  const groupBtn = $('arch-tool-group');
  const ungroupBtn = $('arch-tool-ungroup');
  const alignLeftBtn = $('arch-align-left');
  const alignCenterBtn = $('arch-align-center');
  const undoBtn = $('arch-undo');
  const redoBtn = $('arch-redo');
  const generateBtn = $('btn-generate-architecture');
  const resetBtn = $('btn-architecture-reset');
  const storeBtn = $('btn-architecture-save');
  const syncBtn = $('btn-architecture-sync');
  const templateSaveBtn = $('arch-save-template');
  const templateRefreshBtn = $('arch-refresh-templates');
  const assetUploadInput = $('arch-upload-asset-input');
  const exportPngBtn = $('arch-export-png');
  const exportPdfBtn = $('arch-export-pdf');
  const versionSaveBtn = $('arch-save-version');
  const versionSelector = $('arch-version-selector');
  const liveToggle = $('arch-live-sync');
  const collabStatus = $('arch-collab-status');

  const inspectorSections = Array.from(document.querySelectorAll('.inspector-section'));

  const defaultPorts = [
    { id: 'port-top', side: 'Top', spot: 'Top' },
    { id: 'port-right', side: 'Right', spot: 'Right' },
    { id: 'port-bottom', side: 'Bottom', spot: 'Bottom' },
    { id: 'port-left', side: 'Left', spot: 'Left' },
  ];
  const MODULE_STORAGE_KEY = 'fds:modules:v1';
  const LINK_STYLE_DEFAULT = 'curved';

  function normaliseLinkStyle(style) {
    const value = String(style || LINK_STYLE_DEFAULT).toLowerCase();
    if (value === 'straight' || value === 'orthogonal' || value === 'curved') {
      return value;
    }
    return LINK_STYLE_DEFAULT;
  }

  function resolveLinkStyle(style) {
    if (!window.go || !window.go.Link) {
      return { routing: go.Link.AvoidsNodes, curve: go.Link.Curved };
    }
    const value = normaliseLinkStyle(style);
    if (value === 'straight') {
      return { routing: go.Link.Normal, curve: go.Link.None };
    }
    if (value === 'orthogonal') {
      return { routing: go.Link.Orthogonal, curve: go.Link.None };
    }
    return { routing: go.Link.AvoidsNodes, curve: go.Link.Curved };
  }

  function parseBadges(input) {
    if (!input) {
      return [];
    }
    if (Array.isArray(input)) {
      return input.filter(Boolean);
    }
    return String(input)
      .split(',')
      .map((badge) => badge.trim())
      .filter(Boolean);
  }

  function formatBadges(badges) {
    if (!Array.isArray(badges)) {
      return String(badges || '');
    }
    return badges.join(', ');
  }

  function normaliseSignalType(value) {
    if (!value) {
      return '';
    }
    const map = {
      digital: 'digital',
      analogue: 'analog',
      analog: 'analog',
      network: 'network',
      control: 'control',
      safety: 'safety',
    };
    return map[String(value).toLowerCase().trim()] || '';
  }

  function maybeAutoValidate(origin = 'auto') {
    if (!autoValidationToggle || autoValidationToggle.checked === false) {
      return;
    }
    if (pendingValidationTimeout) {
      window.clearTimeout(pendingValidationTimeout);
    }
    pendingValidationTimeout = window.setTimeout(() => {
      runValidation({ silent: true, origin });
    }, 250);
  }

  function schedulePersist() {
    if (lastPersistTimeout) {
      window.clearTimeout(lastPersistTimeout);
    }
    lastPersistTimeout = window.setTimeout(() => {
      updateHiddenInput();
      toggleEmptyDiagramState();
    }, 200);
  }

  function showStatus(message, state = 'saving') {
    if (!statusIndicator) {
      return;
    }
    statusIndicator.dataset.state = state;
    statusIndicator.querySelector('.status-label').textContent = message;
    if (state !== 'saving') {
      window.setTimeout(() => {
        statusIndicator.dataset.state = 'idle';
        statusIndicator.querySelector('.status-label').textContent = 'Idle';
      }, 3000);
    }
  }

  function updateHiddenInput() {
    if (!hiddenInput) {
      return;
    }
    try {
      hiddenInput.value = JSON.stringify(exportLayout());
    } catch (error) {
      console.warn('Unable to serialise layout', error);
    }
  }

  function toggleEmptyDiagramState() {
    if (!emptyState) {
      return;
    }
    const hasNodes = diagram && diagram.model && diagram.model.nodeDataArray.length > 0;
    emptyState.style.display = hasNodes ? 'none' : 'flex';
  }

  function setInspectorView(view) {
    const selectionCount = diagram?.selection?.count || 0;
    inspectorSections.forEach((section) => {
      const targetView = section.dataset.view;
      let isVisible = targetView === view;
      if (targetView === 'filters') {
        isVisible = true;
      } else if (targetView === 'bulk') {
        isVisible = view !== 'canvas' && selectionCount > 1;
      } else if (targetView === 'canvas') {
        isVisible = view === 'canvas';
      }
      section.classList.toggle('is-visible', isVisible);
    });
  }

  function clearInspector() {
    setInspectorView('canvas');
    inspectorFields.label.value = '';
    inspectorFields.model.value = '';
    inspectorFields.notes.value = '';
    inspectorFields.ip.value = '';
    inspectorFields.slot.value = '';
    inspectorFields.tags.value = '';
    inspectorFields.protocol.value = '';
    inspectorFields.signalType.value = '';
    inspectorFields.power.value = '';
    inspectorFields.status.value = 'operational';
    inspectorConnectionFields.label.value = '';
    inspectorConnectionFields.type.value = '';
    inspectorConnectionFields.color.value = '#1f2937';
    inspectorConnectionFields.width.value = 2;
    inspectorConnectionFields.style.value = 'curved';
    inspectorConnectionFields.arrowStart.value = 'none';
    inspectorConnectionFields.arrowEnd.value = 'triangle';
    if (inspectorConnectionFields.badges) {
      inspectorConnectionFields.badges.value = '';
    }
    inspectorConnectionFields.notes.value = '';
    canvasInspectorFields.background.value = '#f5f7fb';
    canvasInspectorFields.gridSize.value = 32;
    if (canvasInspectorFields.width) {
      canvasInspectorFields.width.value = '';
    }
    if (canvasInspectorFields.height) {
      canvasInspectorFields.height.value = '';
    }
  }

  function makePort(name, spot, output, input) {
    const $go = go.GraphObject.make;
    return $go(go.Shape, 'Circle', {
      fill: 'rgba(45,128,255,0.25)',
      stroke: 'rgba(45,128,255,0.6)',
      strokeWidth: 1,
      desiredSize: new go.Size(10, 10),
      alignment: go.Spot[spot],
      alignmentFocus: go.Spot[spot],
      portId: name,
      fromSpot: go.Spot[spot],
      toSpot: go.Spot[spot],
      fromLinkable: output,
      toLinkable: input,
      cursor: 'pointer',
    });
  }

  function updateCursor() {
    if (!diagram) {
      return;
    }
    const container = diagram.div;
    if (!container) {
      return;
    }
    if (portsVisible) {
      container.style.cursor = 'crosshair';
    } else {
      container.style.cursor = 'default';
    }
  }

  function togglePorts(show) {
    if (!diagram) {
      return;
    }
    portsVisible = show;
    diagram.toolManager.draggingTool.isEnabled = !show;
    diagram.toolManager.linkingTool.isEnabled = true;
    diagram.nodes.each((node) => {
      node.ports.each((port) => {
        port.fill = show ? 'rgba(45,128,255,0.25)' : 'transparent';
        port.stroke = show ? 'rgba(45,128,255,0.6)' : 'transparent';
      });
    });
    updateCursor();
  }

  function initDiagram() {
    if (!window.go || !window.go.GraphObject) {
      goNamespaceMissing();
      return;
    }
    const $go = go.GraphObject.make;

    diagram = $go(go.Diagram, 'architecture-stage', {
      'undoManager.isEnabled': true,
      allowDrop: true,
      'grid.visible': true,
      'grid.gridCellSize': new go.Size(32, 32),
      padding: 20,
      minScale: 0.25,
      maxScale: 2.5,
    });

    diagram.toolManager.draggingTool.isGridSnapEnabled = true;
    diagram.toolManager.linkingTool.portGravity = 20;
    diagram.toolManager.relinkingTool.portGravity = 20;
    diagram.toolManager.linkingTool.direction = go.LinkingTool.ForwardsAndBackwards;
    diagram.toolManager.linkingTool.archetypeLinkData = {
      color: '#1f2937',
      width: 2,
      arrow: 'Standard',
      arrowStart: 'none',
      metadata: {},
    };

    diagram.grid = $go(
      go.Panel,
      'Grid',
      $go(go.Shape, 'LineH', { stroke: 'rgba(125, 162, 228, 0.15)', strokeWidth: 1 }),
      $go(go.Shape, 'LineV', { stroke: 'rgba(125, 162, 228, 0.15)', strokeWidth: 1 })
    );

    diagram.model = $go(go.GraphLinksModel, {
      linkKeyProperty: 'id',
      nodeKeyProperty: 'key',
      linkFromPortIdProperty: 'fromPort',
      linkToPortIdProperty: 'toPort',
    });

    addLayer('Default');

    diagram.model.makeUniqueKeyFunction = (model, data) => {
      nodeKeySeed += 1;
      return data.key || `node-${nodeKeySeed}`;
    };
    diagram.model.makeUniqueLinkKeyFunction = (model, data) => {
      linkKeySeed += 1;
      return data.id || `conn-${linkKeySeed}`;
    };

    const nodeTemplate = $go(
      go.Node,
      'Spot',
      {
        locationSpot: go.Spot.Center,
        resizable: true,
        resizeObjectName: 'CARD',
        selectionAdornmentTemplate: $go(
          go.Adornment,
          'Auto',
          $go(go.Shape, 'RoundedRectangle', { fill: null, stroke: '#1f5af1', strokeWidth: 2 }),
          $go(go.Placeholder)
        ),
      },
      new go.Binding('location', 'loc', go.Point.parse).makeTwoWay(go.Point.stringify),
      new go.Binding('layerName', 'layer').makeTwoWay(),
      $go(
        go.Panel,
        'Auto',
        $go(
          go.Shape,
          'RoundedRectangle',
          {
            name: 'CARD',
            fill: DEFAULT_NODE_STYLE.fill,
            stroke: DEFAULT_NODE_STYLE.stroke,
            strokeWidth: DEFAULT_NODE_STYLE.strokeWidth,
            parameter1: DEFAULT_NODE_STYLE.cornerRadius,
            minSize: new go.Size(DEFAULT_NODE_SIZE.width, DEFAULT_NODE_SIZE.height),
          },
          new go.Binding('desiredSize', 'size', (value) => {
            if (!value) {
              return new go.Size(DEFAULT_NODE_SIZE.width, DEFAULT_NODE_SIZE.height);
            }
            if (typeof value === 'string') {
              const parts = value.split(' ');
              return new go.Size(Number.parseFloat(parts[0]) || DEFAULT_NODE_SIZE.width, Number.parseFloat(parts[1]) || DEFAULT_NODE_SIZE.height);
            }
            if (value.width && value.height) {
              return new go.Size(value.width, value.height);
            }
            return new go.Size(DEFAULT_NODE_SIZE.width, DEFAULT_NODE_SIZE.height);
          }).makeTwoWay((size) => (size ? `${Math.round(size.width)} ${Math.round(size.height)}` : `${DEFAULT_NODE_SIZE.width} ${DEFAULT_NODE_SIZE.height}`))
        ),
        $go(
          go.Panel,
          'Vertical',
          { defaultAlignment: go.Spot.Center, stretch: go.GraphObject.Fill },
          $go(
            go.Picture,
            {
              margin: new go.Margin(16, 16, 8, 16),
              desiredSize: new go.Size(160, 92),
              imageStretch: go.GraphObject.Uniform,
            },
            new go.Binding('source', 'image', (src) => normaliseImageUrl(src) || PLACEHOLDER_IMAGE)
          ),
          $go(
            go.TextBlock,
            {
              margin: new go.Margin(4, 12, 4, 12),
              font: '600 14px "Montserrat", sans-serif',
              stroke: '#1f2d4f',
              wrap: go.TextBlock.WrapFit,
              maxLines: 2,
            },
            new go.Binding('text', 'title').makeTwoWay()
          ),
          $go(
            go.TextBlock,
            {
              margin: new go.Margin(0, 12, 16, 12),
              font: '12px "Montserrat", sans-serif',
              stroke: '#58627c',
              wrap: go.TextBlock.WrapFit,
              maxLines: 3,
            },
            new go.Binding('text', 'subtitle').makeTwoWay()
          )
        )
      ),
      ...defaultPorts.map((port) => makePort(port.id, port.spot, true, true))
    );

    diagram.nodeTemplate = nodeTemplate;

    const groupTemplate = $go(
      go.Group,
      'Auto',
      {
        layout: $go(go.GridLayout, {
          wrappingColumn: Infinity,
          spacing: new go.Size(28, 28),
          alignment: go.GridLayout.Position,
        }),
        selectionAdornmentTemplate: $go(
          go.Adornment,
          'Auto',
          $go(go.Shape, 'RoundedRectangle', { fill: null, stroke: '#1f4ad6', strokeWidth: 2, parameter1: 14 }),
          $go(go.Placeholder, { padding: 6 })
        ),
        computesBoundsAfterDrag: true,
        handlesDragDropForMembers: true,
        mouseDrop: (event, group) => {
          if (!(group instanceof go.Group)) {
            return;
          }
          group.addMembers(group.diagram.selection.filter((part) => part instanceof go.Node), true);
        },
      },
      new go.Binding('location', 'loc', go.Point.parse).makeTwoWay(go.Point.stringify),
      $go(
        go.Panel,
        'Auto',
        $go(go.Shape, 'RoundedRectangle', { fill: 'rgba(47,74,132,0.08)', stroke: 'rgba(47,74,132,0.3)', strokeWidth: 1.2, parameter1: 14 }),
        $go(
          go.Panel,
          'Vertical',
          { margin: 12 },
          $go(
            go.TextBlock,
            {
              font: '600 14px "Montserrat", sans-serif',
              stroke: '#1f2d4f',
              editable: true,
            },
            new go.Binding('text', 'text').makeTwoWay()
          ),
          $go(go.Placeholder, { padding: 12 })
        )
      )
    );

    diagram.groupTemplate = groupTemplate;
    diagram.commandHandler.archetypeGroupData = { isGroup: true, text: 'Group', category: '', loc: '0 0' };

    diagram.linkTemplate = $go(
      go.Link,
      {
        routing: go.Link.AvoidsNodes,
        curve: go.Link.Curved,
        corner: 4,
        relinkableFrom: true,
        relinkableTo: true,
        selectable: true,
      },
      new go.Binding('points').makeTwoWay(),
      new go.Binding('routing', 'style', (value) => resolveLinkStyle(value).routing),
      new go.Binding('curve', 'style', (value) => resolveLinkStyle(value).curve),
      $go(go.Shape, { strokeWidth: 2, stroke: '#1f2937' }, new go.Binding('stroke', 'color').makeTwoWay(), new go.Binding('strokeWidth', 'width').makeTwoWay()),
      $go(go.Shape, { toArrow: 'Standard', stroke: null, fill: '#1f2937' }, new go.Binding('toArrow', 'arrow').makeTwoWay()),
      $go(
        go.TextBlock,
        { segmentOffset: new go.Point(0, -10), editable: true, font: '12px "Montserrat", sans-serif', stroke: '#1f2d4f' },
        new go.Binding('text', 'label').makeTwoWay()
      )
    );

    diagram.addDiagramListener('ChangedSelection', () => {
      handleSelectionChanged();
      updateMeasurementOverlay();
    });
    diagram.addDiagramListener('SelectionMoved', () => {
      schedulePersist();
      updateMeasurementOverlay();
      maybeAutoValidate('selection-moved');
    });
    diagram.addDiagramListener('SelectionCopied', () => {
      schedulePersist();
      updateMeasurementOverlay();
    });
    diagram.addDiagramListener('LinkDrawn', () => {
      schedulePersist();
      updateMeasurementOverlay();
      maybeAutoValidate('link-drawn');
      showStatus('Connection created', 'synced');
    });
    diagram.addDiagramListener('LinkRelinked', () => {
      schedulePersist();
      updateMeasurementOverlay();
      maybeAutoValidate('link-relinked');
    });
    diagram.addDiagramListener('PartResized', (event) => {
      const node = event.subject.part;
      if (node && node.data) {
        diagram.model.commit((model) => {
          model.set(node.data, 'size', go.Size.stringify(node.resizeObject.desiredSize));
        }, 'resize');
        schedulePersist();
        updateMeasurementOverlay();
        maybeAutoValidate('resize');
      }
    });
    diagram.addDiagramListener('ViewportBoundsChanged', () => {
      if (zoomSlider) {
        zoomSlider.value = diagram.scale.toFixed(2);
      }
      updateMeasurementOverlay();
      updateRulers();
    });
  }

  function handleSelectionChanged() {
    if (!diagram) {
      return;
    }
    const selection = diagram.selection;
    if (selection.count === 1) {
      const part = selection.first();
      if (part instanceof go.Node && part.data) {
        populateNodeInspector(part.data);
        return;
      }
      if (part instanceof go.Link && part.data) {
        populateConnectionInspector(part.data);
        return;
      }
    }
    populateCanvasInspector();
  }

  function populateNodeInspector(data) {
    setInspectorView('node');
    inspectorFields.label.value = data.title || data.name || '';
    inspectorFields.model.value = data.subtitle || '';
    inspectorFields.notes.value = data.metadata?.notes || '';
    inspectorFields.ip.value = data.metadata?.ip_address || '';
    inspectorFields.slot.value = data.metadata?.slot || '';
    inspectorFields.tags.value = Array.isArray(data.metadata?.tags) ? data.metadata.tags.join(', ') : '';
    inspectorFields.layer.value = data.layer || 'Default';
    inspectorFields.protocol.value = data.metadata?.protocol || '';
    inspectorFields.signalType.value = data.metadata?.signal_type || '';
    inspectorFields.power.value = data.metadata?.power_rating || '';
    inspectorFields.status.value = data.metadata?.status || 'operational';
  }

  function populateConnectionInspector(data) {
    setInspectorView('connection');
    inspectorConnectionFields.label.value = data.label || '';
    inspectorConnectionFields.type.value = data.type || '';
    inspectorConnectionFields.color.value = data.color || '#1f2937';
    inspectorConnectionFields.width.value = data.width || 2;
    inspectorConnectionFields.style.value = normaliseLinkStyle(data.style || data.curve || 'curved');
    inspectorConnectionFields.arrowStart.value = data.arrowStart || 'none';
    inspectorConnectionFields.arrowEnd.value = data.arrow || 'triangle';
    inspectorConnectionFields.badges.value = Array.isArray(data.metadata?.badges) ? data.metadata.badges.join(', ') : data.metadata?.badges || '';
    inspectorConnectionFields.notes.value = data.metadata?.notes || '';
  }

  function populateCanvasInspector() {
    setInspectorView('canvas');
    if (!diagram) {
      return;
    }
    canvasInspectorFields.background.value = rgbToHex(diagram.div?.style?.backgroundColor || '#f5f7fb');
    canvasInspectorFields.gridSize.value = diagram.grid.gridCellSize.width || 32;
    if (canvasInspectorFields.width && stageWrapper) {
      canvasInspectorFields.width.value = Math.round(stageWrapper.clientWidth || 0);
    }
    if (canvasInspectorFields.height && stageWrapper) {
      canvasInspectorFields.height.value = Math.round(stageWrapper.clientHeight || 0);
    }
  }

  function rgbToHex(rgb) {
    if (!rgb) {
      return '#f5f7fb';
    }
    if (rgb.startsWith('#')) {
      return rgb;
    }
    const match = rgb.match(/\d+/g);
    if (!match) {
      return '#f5f7fb';
    }
    const hex = match.slice(0, 3).map((num) => {
      const value = Number(num);
      return value.toString(16).padStart(2, '0');
    });
    return `#${hex.join('')}`;
  }

  function collectEquipmentRows() {
    const rows = [];
    const tableBody = document.getElementById('equipment-list-body');
    if (!tableBody) {
      return rows;
    }
    Array.from(tableBody.querySelectorAll('tr')).forEach((row) => {
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

  function captureSelectionSnapshot() {
    if (!diagram) {
      return null;
    }
    const layout = exportLayout();
    if (!layout?.nodes?.length) {
      return null;
    }
    const selectedKeys = new Set();
    diagram.selection.each((part) => {
      if (part instanceof go.Node && !part.data?.isGroup) {
        selectedKeys.add(part.data.key);
      }
    });
    if (selectedKeys.size === 0) {
      return null;
    }
    const nodes = layout.nodes.filter((node) => selectedKeys.has(node.id));
    const connections = layout.connections.filter(
      (connection) => selectedKeys.has(connection.from.nodeId) && selectedKeys.has(connection.to.nodeId)
    );
    if (!nodes.length) {
      return null;
    }
    return { nodes, connections };
  }

  function saveModulesToStorage() {
    if (!window.localStorage) {
      return;
    }
    try {
      window.localStorage.setItem(MODULE_STORAGE_KEY, JSON.stringify(customModules));
    } catch (error) {
      console.warn('Unable to persist modules', error);
    }
  }

  function loadModulesFromStorage() {
    if (!window.localStorage) {
      renderModuleList();
      return;
    }
    try {
      const raw = window.localStorage.getItem(MODULE_STORAGE_KEY);
      const stored = raw ? JSON.parse(raw) : [];
      if (Array.isArray(stored)) {
        customModules = stored;
      }
    } catch (error) {
      console.warn('Unable to load modules', error);
    }
    renderModuleList();
  }

  function renderModuleList() {
    if (!moduleList) {
      return;
    }
    moduleList.innerHTML = '';
    if (!customModules.length) {
      const empty = document.createElement('p');
      empty.className = 'panel-empty';
      empty.textContent = 'Select equipment and save it here for reuse.';
      moduleList.appendChild(empty);
      selectedModuleId = '';
      return;
    }
    if (!selectedModuleId || !customModules.some((module) => module.id === selectedModuleId)) {
      selectedModuleId = customModules[0].id;
    }
    customModules.forEach((module) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'template-item';
      button.dataset.moduleId = module.id;
      if (module.id === selectedModuleId) {
        button.classList.add('is-active');
      }
      const nodeCount = module.snapshot?.nodes?.length || 0;
      const connectionCount = module.snapshot?.connections?.length || 0;
      button.innerHTML = `<strong>${module.name}</strong><span>${nodeCount} devices · ${connectionCount} links</span>`;
      moduleList.appendChild(button);
    });
  }

  function handleModuleSelect(moduleId) {
    if (!moduleId || moduleId === selectedModuleId) {
      return;
    }
    selectedModuleId = moduleId;
    renderModuleList();
  }

  function handleModuleRefresh() {
    loadModulesFromStorage();
    showStatus('Modules refreshed', 'synced');
  }

  function handleModuleSave(options = {}) {
    const snapshot = captureSelectionSnapshot();
    if (!snapshot) {
      window.alert('Select at least one device to save as a module.');
      return;
    }
    const nameInput = moduleNameInput?.value?.trim();
    const name = nameInput || options.quickName || `Module ${customModules.length + 1}`;
    const moduleId = window.crypto?.randomUUID?.() || `module-${Date.now()}`;
    const moduleRecord = {
      id: moduleId,
      name,
      snapshot,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    customModules = [moduleRecord, ...customModules];
    saveModulesToStorage();
    if (moduleNameInput) {
      moduleNameInput.value = '';
    }
    selectedModuleId = moduleId;
    renderModuleList();
    showStatus(`Module "${name}" saved`, 'synced');
  }

  function handleModuleInsert() {
    if (!diagram) {
      return;
    }
    if (!customModules.length) {
      window.alert('No modules available yet. Save a selection first.');
      return;
    }
    const module = customModules.find((item) => item.id === selectedModuleId) || customModules[0];
    if (!module) {
      window.alert('Select a module to insert.');
      return;
    }
    const dropPoint =
      diagram.lastInput?.documentPoint ||
      diagram.transformViewToDoc(diagram.viewportBounds.center) ||
      new go.Point(0, 0);
    insertModuleSnapshot(module, dropPoint);
  }

  function insertModuleSnapshot(module, dropPoint) {
    if (!diagram || !module?.snapshot) {
      return;
    }
    const modelData = convertLayoutToModel(module.snapshot);
    const keyMap = new Map();
    const basePoint = dropPoint || new go.Point(0, 0);
    diagram.startTransaction('insert module');
    modelData.nodeDataArray.forEach((nodeData, index) => {
      const originalKey = nodeData.key;
      nodeData.key = '';
      const offsetX = basePoint.x + index * 40;
      const offsetY = basePoint.y + index * 20;
      nodeData.loc = `${offsetX} ${offsetY}`;
      nodeData.layer = activeLayer || nodeData.layer || 'Default';
      diagram.model.addNodeData(nodeData);
      keyMap.set(originalKey, nodeData.key);
    });
    modelData.linkDataArray.forEach((linkData) => {
      const fromKey = keyMap.get(linkData.from);
      const toKey = keyMap.get(linkData.to);
      if (!fromKey || !toKey) {
        return;
      }
      const data = {
        ...linkData,
        id: '',
        from: fromKey,
        to: toKey,
        style: normaliseLinkStyle(linkData.style || 'curved'),
      };
      diagram.model.addLinkData(data);
    });
    diagram.commitTransaction('insert module');
    schedulePersist();
    diagram.clearSelection();
    keyMap.forEach((newKey) => {
      const part = diagram.findPartForKey(newKey);
      if (part) {
        part.isSelected = true;
      }
    });
    updateMeasurementOverlay();
    maybeAutoValidate('module-insert');
    showStatus(`Module "${module.name}" inserted`, 'synced');
  }

  function handleBulkLayerAssign() {
    if (!diagram || diagram.selection.count === 0) {
      window.alert('Select at least one device to update the layer.');
      return;
    }
    diagram.startTransaction('bulk-layer');
    diagram.selection.each((part) => {
      if (part instanceof go.Node) {
        diagram.model.setDataProperty(part.data, 'layer', activeLayer || 'Default');
      }
    });
    diagram.commitTransaction('bulk-layer');
    renderLayers();
    schedulePersist();
    updateMeasurementOverlay();
    showStatus(`Layer updated to ${activeLayer}`, 'synced');
  }

  function handleBulkSignalAssign() {
    if (!diagram || diagram.selection.count === 0) {
      window.alert('Select at least one device to assign a signal type.');
      return;
    }
    const type = window.prompt('Enter signal type (digital, analog, network, control, safety)', 'digital');
    const normalised = normaliseSignalType(type);
    if (!normalised) {
      window.alert('Provide a valid signal type.');
      return;
    }
    diagram.startTransaction('bulk-signal');
    diagram.selection.each((part) => {
      if (part instanceof go.Node) {
        const metadata = { ...(part.data.metadata || {}), signal_type: normalised };
        diagram.model.setDataProperty(part.data, 'metadata', metadata);
      }
    });
    diagram.commitTransaction('bulk-signal');
    schedulePersist();
    maybeAutoValidate('bulk-signal');
    showStatus(`Signal type set to ${normalised}`, 'synced');
  }

  function handleBulkColorize() {
    if (!diagram || diagram.selection.count === 0) {
      window.alert('Select at least one connection to colorize.');
      return;
    }
    const color = window.prompt('Enter HEX colour (example: #1f2937)', '#1f2937');
    if (!color) {
      return;
    }
    diagram.startTransaction('bulk-color');
    diagram.selection.each((part) => {
      if (part instanceof go.Link) {
        diagram.model.setDataProperty(part.data, 'color', color);
      }
    });
    diagram.commitTransaction('bulk-color');
    schedulePersist();
    showStatus('Connections updated', 'synced');
  }

  function handleFilterApply() {
    if (!diagram) {
      return;
    }
    const searchTerm = filterFields.search?.value?.trim().toLowerCase();
    const component = filterFields.component?.value;
    const status = filterFields.status?.value;
    diagram.startTransaction('filter-apply');
    diagram.nodes.each((node) => {
      if (!(node instanceof go.Node) || node.data.isGroup) {
        return;
      }
      const data = node.data || {};
      const tags = Array.isArray(data.metadata?.tags) ? data.metadata.tags.map((tag) => tag.toLowerCase()) : [];
      const matchesText =
        !searchTerm ||
        (data.title || '').toLowerCase().includes(searchTerm) ||
        (data.subtitle || '').toLowerCase().includes(searchTerm) ||
        tags.some((tag) => tag.includes(searchTerm));
      const matchesComponent = !component || tags.includes(component);
      const matchesStatus = !status || (data.metadata?.status || 'operational') === status;
      node.visible = matchesText && matchesComponent && matchesStatus;
    });
    diagram.commitTransaction('filter-apply');
    updateMeasurementOverlay();
    showStatus('Filter applied', 'synced');
  }

  function handleFilterClear() {
    if (!diagram) {
      return;
    }
    diagram.startTransaction('filter-clear');
    diagram.nodes.each((node) => {
      if (node instanceof go.Node) {
        node.visible = true;
      }
    });
    diagram.commitTransaction('filter-clear');
    if (filterFields.search) {
      filterFields.search.value = '';
    }
    if (filterFields.component) {
      filterFields.component.value = '';
    }
    if (filterFields.status) {
      filterFields.status.value = '';
    }
    updateMeasurementOverlay();
    showStatus('Filters cleared', 'synced');
  }

  function convertLayoutToModel(layout) {
    const nodeDataArray = [];
    const linkDataArray = [];
    nodeKeySeed = 0;
    linkKeySeed = 0;

    (layout?.nodes || []).forEach((node, index) => {
      const key = node.id || `node-${index + 1}`;
      const idMatch = key.match(/(\d+)$/);
      if (idMatch) {
        nodeKeySeed = Math.max(nodeKeySeed, Number(idMatch[1]));
      }
      const x = Number.parseFloat(node.position?.x) || 0;
      const y = Number.parseFloat(node.position?.y) || 0;
      const size = node.size || {};
      const width = Number.parseFloat(size.width) || DEFAULT_NODE_SIZE.width;
      const height = Number.parseFloat(size.height) || DEFAULT_NODE_SIZE.height;
      const imageUrl =
        normaliseImageUrl(node.image?.url) ||
        normaliseImageUrl(node.image_url) ||
        normaliseImageUrl(node.metadata?.asset?.image_url) ||
        normaliseImageUrl(node.metadata?.asset?.local_path) ||
        '';
      nodeDataArray.push({
        key,
        title: node.label || node.model || 'Device',
        name: node.label || node.model || 'Device',
        subtitle: node.description || node.metadata?.equipment?.description || node.label || '',
        image: imageUrl,
        metadata: {
          ...(node.metadata || {}),
          signal_type: node.metadata?.signal_type || node.signal_type || '',
        },
        loc: `${x} ${y}`,
        size: `${width} ${height}`,
        background: node.style?.fill || DEFAULT_NODE_STYLE.fill,
        layer: node.layer || node.metadata?.layer || 'Default',
      });
    });

    (layout?.connections || []).forEach((connection, index) => {
      const key = connection.id || `conn-${index + 1}`;
      const idMatch = key.match(/(\d+)$/);
      if (idMatch) {
        linkKeySeed = Math.max(linkKeySeed, Number(idMatch[1]));
      }
      linkDataArray.push({
        id: key,
        from: connection.from?.nodeId,
        to: connection.to?.nodeId,
        fromPort: connection.from?.portId || 'port-right',
        toPort: connection.to?.portId || 'port-left',
        label: connection.label || '',
        color: connection.style?.color || '#1f2937',
        width: connection.style?.width || 2,
        arrow: connection.style?.arrowheads?.end || 'Standard',
        arrowStart: connection.style?.arrowheads?.start || 'none',
        style: normaliseLinkStyle(
          connection.style?.layout ||
            connection.style?.curve ||
            connection.style?.type ||
            connection.metadata?.style ||
            connection.type
        ),
        metadata: {
          ...(connection.metadata || {}),
          badges: parseBadges(connection.metadata?.badges),
        },
      });
    });

    if (layout?.assetLibrary) {
      assetLibrary = layout.assetLibrary;
    }

    return { nodeDataArray, linkDataArray };
  }

  function exportLayout() {
    const nodes = [];
    if (diagram) {
      diagram.nodes.each((node) => {
        if (!(node instanceof go.Node) || node.data.isGroup) {
          return;
        }
        const position = node.location;
        const bounds = node.resizeObject?.desiredSize || node.actualBounds;
        const data = node.data || {};
        nodes.push({
          id: data.key,
          label: data.title || data.name || 'Device',
          model: data.subtitle || '',
          position: { x: Number(position.x.toFixed(2)), y: Number(position.y.toFixed(2)) },
          size: { width: Number(bounds.width.toFixed(2)), height: Number(bounds.height.toFixed(2)) },
          image: { url: data.image || '' },
          metadata: data.metadata || {},
          layer: data.layer || 'Default',
          style: { ...DEFAULT_NODE_STYLE },
          ports: defaultPorts.map((port) => ({
            id: port.id,
            side: port.side.toLowerCase(),
            ratio: 0.5,
            position: { x: bounds.width / 2, y: bounds.height / 2 },
          })),
        });
      });
    }

    const connections = [];
    if (diagram) {
      diagram.links.each((link) => {
        const data = link.data || {};
        connections.push({
          id: data.id || `conn-${linkKeySeed + 1}`,
          from: { nodeId: data.from, portId: data.fromPort || 'port-right' },
          to: { nodeId: data.to, portId: data.toPort || 'port-left' },
          label: data.label || '',
          type: data.type || 'generic',
          metadata: data.metadata || {},
          style: {
            color: data.color || '#1f2937',
            width: data.width || 2,
            layout: normaliseLinkStyle(data.style || 'curved'),
            curve: normaliseLinkStyle(data.style || 'curved'),
            arrowheads: {
              start: data.arrowStart || 'none',
              end: data.arrow || 'triangle',
            },
          },
        });
      });
    }

    return {
      canvas: {
        zoom: diagram?.scale || 1,
        pan: diagram ? { x: diagram.position.x, y: diagram.position.y } : { x: 0, y: 0 },
        grid: { enabled: gridToggle?.checked !== false, size: Number(canvasInspectorFields.gridSize.value) || 32, snap: snapToggle?.checked !== false },
        background: canvasInspectorFields.background.value || '#f5f7fb',
      },
      nodes,
      connections,
      assetLibrary,
      metadata: {
        generated_at: new Date().toISOString(),
        source: 'gojs',
      },
    };
  }

  function applyLayout(layout) {
    if (!diagram) {
      return;
    }
    const modelData = convertLayoutToModel(layout);
    diagram.model = go.GraphObject.make(go.GraphLinksModel, {
      linkKeyProperty: 'id',
      nodeKeyProperty: 'key',
      linkFromPortIdProperty: 'fromPort',
      linkToPortIdProperty: 'toPort',
      nodeDataArray: modelData.nodeDataArray,
      linkDataArray: modelData.linkDataArray,
    });
    diagram.model.makeUniqueKeyFunction = (model, data) => {
      nodeKeySeed += 1;
      return data.key || `node-${nodeKeySeed}`;
    };
    diagram.model.makeUniqueLinkKeyFunction = (model, data) => {
      linkKeySeed += 1;
      return data.id || `conn-${linkKeySeed}`;
    };
    renderAssetLibrary(assetLibrary);
    populateCanvasInspector();
    toggleEmptyDiagramState();
    schedulePersist();
  }

  function renderAssetLibrary(items) {
    if (!assetList) {
      return;
    }
    assetList.innerHTML = '';
    if (!items || !items.length) {
      const empty = document.createElement('p');
      empty.className = 'panel-empty';
      empty.textContent = 'Drag assets into the canvas or use templates.';
      assetList.appendChild(empty);
      return;
    }
    items.forEach((asset) => {
      const tile = document.createElement('button');
      tile.type = 'button';
      tile.className = 'asset-tile';
      const image = document.createElement('img');
      image.src = normaliseImageUrl(asset.thumbnail_url) || normaliseImageUrl(asset.image_url) || PLACEHOLDER_IMAGE;
      image.alt = asset.display_name || asset.model_key;
      const label = document.createElement('span');
      label.textContent = asset.display_name || asset.model_key || 'Device';
      tile.appendChild(image);
      tile.appendChild(label);
      tile.addEventListener('click', () => addNodeFromAsset(asset));
      assetList.appendChild(tile);
    });
  }

  function addNodeFromAsset(asset) {
    if (!diagram) {
      return;
    }
    const viewport = diagram.viewportBounds;
    const point = diagram.transformViewToDoc(new go.Point((viewport.width / 2) + viewport.x, (viewport.height / 2) + viewport.y));
    diagram.startTransaction('add node');
    const data = {
      key: '',
      title: asset.display_name || asset.model_key || 'Device',
      name: asset.display_name || asset.model_key || 'Device',
      subtitle: asset.manufacturer || asset.model_key || '',
      image: normaliseImageUrl(asset.image_url) || normaliseImageUrl(asset.local_path) || PLACEHOLDER_IMAGE,
      metadata: {
        assetSource: asset.source || asset.asset_source,
        asset,
      },
      loc: `${point.x} ${point.y}`,
      size: `${DEFAULT_NODE_SIZE.width} ${DEFAULT_NODE_SIZE.height}`,
      layer: activeLayer || 'Default',
    };
    diagram.model.addNodeData(data);
    diagram.commitTransaction('add node');
    schedulePersist();
  }

  function activateTool(button) {
    if (!toolButtons?.length) {
      return;
    }
    toolButtons.forEach((btn) => {
      if (btn) {
        btn.classList.remove('is-active');
      }
    });
    if (button) {
      button.classList.add('is-active');
    }
  }

  function handleToolSelect() {
    activateTool(toolSelectBtn);
    togglePorts(false);
    if (diagram) {
      diagram.toolManager.draggingTool.isEnabled = true;
      diagram.toolManager.panningTool.isEnabled = true;
      updateCursor();
    }
    showStatus('Select tool enabled', 'synced');
  }

  function handleToolConnector() {
    activateTool(toolConnectorBtn);
    togglePorts(true);
    showStatus('Connector tool: drag from a blue port to another device', 'saving');
  }

  function handleToolAnnotation() {
    activateTool(toolAnnotationBtn);
    togglePorts(false);
    showStatus('Select a device or link, then use the annotation panel to add notes.', 'saving');
  }

  function handleToolPan() {
    activateTool(toolPanBtn);
    togglePorts(false);
    if (diagram) {
      diagram.toolManager.draggingTool.isEnabled = false;
      diagram.toolManager.panningTool.isEnabled = true;
      if (diagram.div) {
        diagram.div.style.cursor = 'grab';
      }
    }
    showStatus('Pan mode: drag the canvas to navigate', 'saving');
  }

  function handleCopy() {
    if (!diagram) {
      return;
    }
    diagram.commandHandler.copySelection();
    schedulePersist();
  }

  function handlePaste() {
    if (!diagram) {
      return;
    }
    const point =
      diagram.lastInput?.documentPoint ||
      diagram.toolManager.contextMenuTool.mouseDownPoint ||
      diagram.firstInput?.documentPoint ||
      new go.Point(0, 0);
    diagram.commandHandler.pasteSelection(point);
    schedulePersist();
  }

  function handleDelete() {
    diagram?.commandHandler.deleteSelection();
    schedulePersist();
  }

  function handleGroup() {
    if (!diagram) {
      return;
    }
    if (!diagram.commandHandler.canGroupSelection()) {
      window.alert('Select two or more items to group.');
      return;
    }
    diagram.commandHandler.groupSelection();
    schedulePersist();
    showStatus('Group created', 'synced');
  }

  function handleUngroup() {
    if (!diagram) {
      return;
    }
    if (!diagram.commandHandler.canUngroupSelection()) {
      window.alert('Select an existing group to ungroup.');
      return;
    }
    diagram.commandHandler.ungroupSelection();
    schedulePersist();
    showStatus('Group released', 'synced');
  }

  function alignSelection(mode) {
    if (!diagram) {
      return;
    }
    const nodes = diagram.selection.filter((part) => part instanceof go.Node).toArray();
    if (nodes.length < 2) {
      window.alert('Select at least two devices to align.');
      return;
    }
    diagram.startTransaction('align');
    if (mode === 'left') {
      const minX = Math.min(...nodes.map((node) => node.location.x));
      nodes.forEach((node) => node.location = new go.Point(minX, node.location.y));
    } else if (mode === 'center') {
      const average = nodes.reduce((sum, node) => sum + node.location.x, 0) / nodes.length;
      nodes.forEach((node) => node.location = new go.Point(average, node.location.y));
    }
    diagram.commitTransaction('align');
    schedulePersist();
    showStatus('Devices aligned', 'synced');
  }

  function handleUndo() {
    diagram?.commandHandler.undo();
  }

  function handleRedo() {
    diagram?.commandHandler.redo();
  }

  function handleZoom(value) {
    if (!diagram) {
      return;
    }
    const parsed = Number.parseFloat(value);
    if (Number.isNaN(parsed)) {
      return;
    }
    diagram.scale = Math.min(Math.max(parsed, 0.25), 2.5);
  }

  function handleZoomDelta(delta) {
    if (!diagram) {
      return;
    }
    const next = (diagram.scale + delta).toFixed(2);
    handleZoom(next);
    if (zoomSlider) {
      zoomSlider.value = diagram.scale.toFixed(2);
    }
  }

  function handleGridToggle(force) {
    if (!diagram) {
      return;
    }
    const enabled = typeof force === 'boolean' ? force : gridToggle?.checked !== false;
    diagram.grid.visible = enabled;
    schedulePersist();
  }

  function handleSnapToggle(force) {
    if (!diagram) {
      return;
    }
    const enabled = typeof force === 'boolean' ? force : snapToggle?.checked !== false;
    diagram.toolManager.draggingTool.isGridSnapEnabled = enabled;
    schedulePersist();
  }

  function handleNodeInspectorApply() {
    if (!diagram || diagram.selection.count !== 1) {
      return;
    }
    const node = diagram.selection.first();
    if (!(node instanceof go.Node)) {
      return;
    }
    diagram.model.commit((model) => {
      model.set(node.data, 'title', inspectorFields.label.value.trim());
      model.set(node.data, 'name', inspectorFields.label.value.trim());
      model.set(node.data, 'subtitle', inspectorFields.model.value.trim());
      model.set(node.data, 'layer', inspectorFields.layer.value || 'Default');
      model.set(node.data, 'metadata', {
        ...(node.data.metadata || {}),
        notes: inspectorFields.notes.value.trim(),
        ip_address: inspectorFields.ip.value.trim(),
        slot: inspectorFields.slot.value.trim(),
        protocol: inspectorFields.protocol.value.trim(),
        signal_type: inspectorFields.signalType.value || '',
        power_rating: inspectorFields.power.value.trim(),
        status: inspectorFields.status.value || 'operational',
        tags: inspectorFields.tags.value
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
    }, 'update-node');
    schedulePersist();
    renderLayers();
    updateMeasurementOverlay();
    maybeAutoValidate('node-inspector');
    showStatus('Device updated', 'synced');
  }

  function handleConnectionInspectorApply() {
    if (!diagram || diagram.selection.count !== 1) {
      return;
    }
    const link = diagram.selection.first();
    if (!(link instanceof go.Link)) {
      return;
    }
    const styleValue = normaliseLinkStyle(inspectorConnectionFields.style.value);
    const badges = parseBadges(inspectorConnectionFields.badges.value);
    diagram.model.commit((model) => {
      model.set(link.data, 'label', inspectorConnectionFields.label.value.trim());
      model.set(link.data, 'type', inspectorConnectionFields.type.value.trim());
      model.set(link.data, 'color', inspectorConnectionFields.color.value || '#1f2937');
      model.set(link.data, 'width', Number.parseFloat(inspectorConnectionFields.width.value) || 2);
      model.set(link.data, 'style', styleValue);
      model.set(link.data, 'arrow', inspectorConnectionFields.arrowEnd.value || 'Standard');
      model.set(link.data, 'arrowStart', inspectorConnectionFields.arrowStart.value || 'none');
      model.set(link.data, 'metadata', {
        ...(link.data.metadata || {}),
        notes: inspectorConnectionFields.notes.value.trim(),
        badges,
      });
    }, 'update-link');
    schedulePersist();
    updateMeasurementOverlay();
    maybeAutoValidate('connection-inspector');
    showStatus('Connection updated', 'synced');
  }

  function handleCanvasInspectorApply() {
    if (!diagram) {
      return;
    }
    const size = Number.parseInt(canvasInspectorFields.gridSize.value, 10) || 32;
    diagram.grid.gridCellSize = new go.Size(size, size);
    const background = canvasInspectorFields.background.value || '#f5f7fb';
    diagram.div.style.background = background;
    if (stageWrapper) {
      stageWrapper.style.background = background;
      const width = Number.parseInt(canvasInspectorFields.width?.value || '', 10);
      const height = Number.parseInt(canvasInspectorFields.height?.value || '', 10);
      if (!Number.isNaN(width) && width > 0) {
        stageWrapper.style.minWidth = `${Math.max(width, 640)}px`;
      }
      if (!Number.isNaN(height) && height > 0) {
        stageWrapper.style.minHeight = `${Math.max(height, 480)}px`;
      }
    }
    applyThemeState();
    schedulePersist();
    updateMeasurementOverlay();
    showStatus('Canvas updated', 'synced');
  }

  function handleGenerate() {
    const equipment = collectEquipmentRows();
    if (!equipment.length) {
      window.alert('Add equipment in Step 4 before generating the architecture.');
      return;
    }
    const payload = {
      submission_id: submissionId,
      equipment,
      existing_layout: exportLayout(),
    };
    showStatus('Generating layout...', 'saving');
    fetch('/reports/system-architecture/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Preview failed (${response.status})`);
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error(data?.message || 'Unable to generate architecture');
        }
        applyLayout(data.payload || {});
        showStatus('Draft generated', 'synced');
      })
      .catch((error) => {
        console.error('Architecture preview failed', error);
        window.alert('Unable to generate a draft layout. Please try again.');
        showStatus('Idle', 'idle');
      });
  }

  function handleReset() {
    if (!diagram) {
      return;
    }
    if (!window.confirm('Reset the layout? Unsaved changes will be lost.')) {
      return;
    }
    diagram.model = go.GraphObject.make(go.GraphLinksModel, {
      linkKeyProperty: 'id',
      nodeKeyProperty: 'key',
      linkFromPortIdProperty: 'fromPort',
      linkToPortIdProperty: 'toPort',
    });
    togglePorts(false);
    toggleEmptyDiagramState();
    schedulePersist();
    updateMeasurementOverlay();
    maybeAutoValidate('reset');
    showStatus('Canvas cleared', 'synced');
  }

  function handleStore() {
    updateHiddenInput();
    window.alert('Layout stored in the form. Submit the FDS to persist it.');
  }

  function handleSync() {
    if (!submissionId) {
      window.alert('Save the FDS at least once before syncing the architecture.');
      return;
    }
    showStatus('Syncing...', 'saving');
    fetch(`/reports/system-architecture/layout/${submissionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layout: exportLayout() }),
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
        showStatus('Layout synced', 'synced');
        if (data.version) {
          refreshVersions();
        }
      })
      .catch((error) => {
        console.error('Layout sync failed', error);
        window.alert('Unable to sync the layout. Try again later.');
        showStatus('Idle', 'idle');
      });
  }

  function handleTemplateSave() {
    const name = templateNameInput?.value?.trim();
    if (!name) {
      window.alert('Enter a template name before saving.');
      return;
    }
    fetch('/reports/system-architecture/templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        layout: exportLayout(),
        description: `Saved on ${new Date().toLocaleString()}`,
        is_shared: true,
      }),
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
        templateNameInput.value = '';
        refreshTemplates();
        showStatus('Template saved', 'synced');
      })
      .catch((error) => {
        console.error('Template save failed', error);
        window.alert('Unable to save template. Try again later.');
      });
  }

  function refreshTemplates() {
    fetch('/reports/system-architecture/templates')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load templates');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error('Failed to load templates');
        }
        renderTemplateList(data.templates || []);
      })
      .catch((error) => {
        console.warn('Unable to load templates', error);
      });
  }

  function renderTemplateList(templates) {
    if (!templateList) {
      return;
    }
    templateList.innerHTML = '';
    if (!templates.length) {
      const empty = document.createElement('p');
      empty.className = 'panel-empty';
      empty.textContent = 'No templates yet. Save one from the current layout.';
      templateList.appendChild(empty);
      return;
    }
    templates.forEach((template) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'template-item';
      button.innerHTML = `<strong>${template.name}</strong><span>${template.description || 'Shared template'}</span>`;
      button.addEventListener('click', () => loadTemplate(template.id));
      templateList.appendChild(button);
    });
  }

  function loadTemplate(templateId) {
    fetch(`/reports/system-architecture/templates/${templateId}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Template fetch failed');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success || !data.template) {
          throw new Error('Template not found');
        }
        applyLayout(data.template.layout || {});
        showStatus(`Template \"${data.template.name}\" applied`, 'synced');
      })
      .catch((error) => {
        console.error('Template load failed', error);
        window.alert('Unable to load template. Please try again.');
      });
  }

  function refreshAssets() {
    fetch('/reports/system-architecture/assets/library')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load assets');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error('Failed to load assets');
        }
        assetLibrary = data.assets || [];
        renderAssetLibrary(assetLibrary);
      })
      .catch((error) => {
        console.warn('Asset library unavailable', error);
      });
  }

  function handleAssetUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_name', file.name.replace(/\\.[^/.]+$/, ''));
    fetch('/reports/system-architecture/assets/upload', {
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
        if (!data?.success || !data.asset) {
          throw new Error('Upload failed');
        }
        assetLibrary = [data.asset, ...(assetLibrary || [])];
        renderAssetLibrary(assetLibrary);
        showStatus('Asset uploaded', 'synced');
      })
      .catch((error) => {
        console.error('Asset upload failed', error);
        window.alert('Unable to upload asset image. Try a different file.');
      })
      .finally(() => {
        event.target.value = '';
      });
  }

  function handleExportPng() {
    if (!diagram) {
      return;
    }
    const img = diagram.makeImageData({ scale: 1.5, background: canvasInspectorFields.background.value || '#f5f7fb' });
    const link = document.createElement('a');
    link.href = img;
    link.download = `fds-architecture-${Date.now()}.png`;
    link.click();
  }

  function handleExportPdf() {
    if (!diagram) {
      return;
    }
    if (!window.jspdf || !window.jspdf.jsPDF) {
      window.alert('PDF export requires jsPDF. Add jsPDF to the page to enable this feature.');
      return;
    }
    const img = diagram.makeImageData({ scale: 1.2, background: canvasInspectorFields.background.value || '#f5f7fb' });
    const pdf = new window.jspdf.jsPDF('landscape', 'pt', [diagram.viewportBounds.width, diagram.viewportBounds.height]);
    pdf.addImage(img, 'PNG', 0, 0, diagram.viewportBounds.width, diagram.viewportBounds.height);
    pdf.save(`fds-architecture-${Date.now()}.pdf`);
  }

  function updateValidationList(results) {
    if (!validationResultsList) {
      return;
    }
    validationResultsList.innerHTML = '';
    if (!results.length) {
      const item = document.createElement('li');
      item.className = 'is-success';
      item.textContent = 'No validation issues detected.';
      validationResultsList.appendChild(item);
      return;
    }
    results.forEach((result) => {
      const item = document.createElement('li');
      if (result.severity === 'error') {
        item.classList.add('is-error');
      } else if (result.severity === 'warning') {
        item.classList.add('is-warning');
      } else if (result.severity === 'success') {
        item.classList.add('is-success');
      }
      item.textContent = result.message;
      validationResultsList.appendChild(item);
    });
  }

  function runValidation({ silent = false, origin = 'manual' } = {}) {
    if (!diagram || !validationResultsList) {
      return [];
    }
    const nodes = diagram.model?.nodeDataArray || [];
    const links = diagram.model?.linkDataArray || [];
    const nodeMap = new Map();
    const inbound = new Map();
    const outbound = new Map();
    nodes.forEach((node) => {
      nodeMap.set(node.key, node);
      inbound.set(node.key, 0);
      outbound.set(node.key, 0);
    });
    const results = [];
    links.forEach((link) => {
      if (!nodeMap.has(link.from) || !nodeMap.has(link.to)) {
        results.push({ severity: 'error', message: `Link "${link.label || link.id}" references a missing device.` });
        return;
      }
      outbound.set(link.from, (outbound.get(link.from) || 0) + 1);
      inbound.set(link.to, (inbound.get(link.to) || 0) + 1);
      const connectionType = normaliseSignalType(link.type);
      if (connectionType) {
        const fromType = normaliseSignalType(nodeMap.get(link.from)?.metadata?.signal_type);
        const toType = normaliseSignalType(nodeMap.get(link.to)?.metadata?.signal_type);
        if (fromType && fromType !== connectionType) {
          results.push({
            severity: 'warning',
            message: `Signal mismatch: ${(nodeMap.get(link.from)?.title || link.from)} outputs ${fromType.toUpperCase()} into a ${connectionType.toUpperCase()} link.`,
          });
        }
        if (toType && toType !== connectionType) {
          results.push({
            severity: 'warning',
            message: `Signal mismatch: ${(nodeMap.get(link.to)?.title || link.to)} expects ${toType.toUpperCase()} but receives ${connectionType.toUpperCase()}.`,
          });
        }
      }
    });
    nodes.forEach((node) => {
      if (!node.layer) {
        results.push({ severity: 'warning', message: `${node.title || node.name || node.key} is not assigned to a layer.` });
      }
      const status = node.metadata?.status || 'operational';
      if (status === 'operational') {
        const inboundCount = inbound.get(node.key) || 0;
        const outboundCount = outbound.get(node.key) || 0;
        if (inboundCount === 0) {
          results.push({ severity: 'warning', message: `${node.title || node.key} has no incoming links.` });
        }
        if (outboundCount === 0) {
          results.push({ severity: 'warning', message: `${node.title || node.key} has no outgoing links.` });
        }
      }
    });
    lastValidationResults = results;
    updateValidationList(results);
    if (!silent) {
      showStatus(results.length ? 'Validation completed (see findings)' : 'Validation passed', results.length ? 'saving' : 'synced');
    }
    return results;
  }

  function updateSimulationList(results) {
    if (!simulationResultsList) {
      return;
    }
    simulationResultsList.innerHTML = '';
    if (!results.length) {
      const item = document.createElement('li');
      item.className = 'is-success';
      item.textContent = 'Simulation passed without warnings.';
      simulationResultsList.appendChild(item);
      return;
    }
    results.forEach((result) => {
      const item = document.createElement('li');
      if (result.severity === 'error') {
        item.classList.add('is-error');
      } else if (result.severity === 'warning') {
        item.classList.add('is-warning');
      }
      item.textContent = result.message;
      simulationResultsList.appendChild(item);
    });
  }

  function runSimulation({ silent = false } = {}) {
    if (!diagram || !simulationResultsList) {
      return [];
    }
    const nodes = diagram.model?.nodeDataArray || [];
    const links = diagram.model?.linkDataArray || [];
    const adjacency = new Map();
    const reverseAdjacency = new Map();
    nodes.forEach((node) => {
      adjacency.set(node.key, []);
      reverseAdjacency.set(node.key, []);
    });
    links.forEach((link) => {
      if (adjacency.has(link.from)) {
        adjacency.get(link.from).push(link.to);
      }
      if (reverseAdjacency.has(link.to)) {
        reverseAdjacency.get(link.to).push(link.from);
      }
    });
    const startNodes = nodes.filter((node) => (reverseAdjacency.get(node.key) || []).length === 0);
    const queue = startNodes.map((node) => node.key);
    const visited = new Set(queue);
    while (queue.length) {
      const current = queue.shift();
      (adjacency.get(current) || []).forEach((next) => {
        if (!visited.has(next)) {
          visited.add(next);
          queue.push(next);
        }
      });
    }
    const results = [];
    nodes.forEach((node) => {
      if (!visited.has(node.key)) {
        results.push({ severity: 'warning', message: `${node.title || node.name || node.key} is unreachable in simulation.` });
      }
      const outbound = (adjacency.get(node.key) || []).length;
      if ((node.metadata?.status || 'operational') === 'operational' && outbound === 0) {
        results.push({ severity: 'warning', message: `${node.title || node.key} terminates the flow.` });
      }
    });
    if (!startNodes.length) {
      results.push({ severity: 'info', message: 'Simulation: no start devices detected.' });
    }
    lastSimulationResults = results;
    updateSimulationList(results);
    if (!silent) {
      showStatus('Simulation completed', results.length ? 'saving' : 'synced');
    }
    return results;
  }

  function exportSimulationResults() {
    if (!lastSimulationResults.length) {
      window.alert('Run a simulation before exporting the test log.');
      return;
    }
    const lines = [
      'Simulation Results',
      `Generated: ${new Date().toLocaleString()}`,
      '',
      ...lastSimulationResults.map((result) => `- [${result.severity || 'info'}] ${result.message}`),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `fds-simulation-${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function handleLockSelection() {
    if (!diagram || diagram.selection.count === 0) {
      window.alert('Select at least one item to lock.');
      return;
    }
    diagram.startTransaction('toggle-lock');
    diagram.selection.each((part) => {
      if (!(part instanceof go.Node) && !(part instanceof go.Link)) {
        return;
      }
      const key = part.data?.key || part.data?.id;
      const isLocked = lockedNodes.has(key);
      const nextState = !isLocked;
      if (nextState) {
        lockedNodes.add(key);
      } else {
        lockedNodes.delete(key);
      }
      part.selectable = !nextState;
      part.movable = !nextState;
      if (part instanceof go.Node) {
        part.resizable = !nextState;
      }
      const metadata = { ...(part.data.metadata || {}), locked: nextState, locked_by: nextState ? currentUserEmail : null };
      diagram.model.setDataProperty(part.data, 'metadata', metadata);
      if (nextState) {
        part.isSelected = false;
      }
    });
    diagram.commitTransaction('toggle-lock');
    schedulePersist();
    showStatus('Lock status updated', 'synced');
  }

  function initialiseCollaborators() {
    collaboratorPresence = [];
    if (currentUserEmail) {
      collaboratorPresence.push({
        id: 'self',
        name: currentUserEmail.split('@')[0],
        role: 'You',
        color: '#2d80ff',
      });
    }
    renderCollaborators();
  }

  function renderCollaborators() {
    if (!collaboratorList) {
      return;
    }
    collaboratorList.innerHTML = '';
    if (!collaboratorPresence.length) {
      const muted = document.createElement('span');
      muted.className = 'badge badge-muted';
      muted.textContent = 'Offline';
      collaboratorList.appendChild(muted);
      if (collabStatus) {
        collabStatus.innerHTML = '<i class="fas fa-user-slash"></i> Offline';
      }
      return;
    }
    collaboratorPresence.forEach((person) => {
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = person.name;
      collaboratorList.appendChild(badge);
    });
    if (collabStatus) {
      collabStatus.innerHTML = collaboratorPresence.length
        ? `<i class="fas fa-users"></i> ${collaboratorPresence.length} online`
        : '<i class="fas fa-user-slash"></i> Offline';
    }
  }

  function renderChatMessages() {
    if (!chatLog) {
      return;
    }
    chatLog.innerHTML = '';
    if (!chatMessages.length) {
      const empty = document.createElement('p');
      empty.className = 'chat-empty';
      empty.textContent = 'Start a thread to discuss layout changes.';
      chatLog.appendChild(empty);
      return;
    }
    chatMessages.forEach((message) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'chat-message';
      if (message.isSelf) {
        wrapper.classList.add('me');
      }
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.textContent = `${message.author} · ${new Date(message.timestamp).toLocaleTimeString()}`;
      const body = document.createElement('div');
      body.textContent = message.content;
      wrapper.appendChild(meta);
      wrapper.appendChild(body);
      chatLog.appendChild(wrapper);
    });
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function handleChatSend() {
    if (!chatMessageInput) {
      return;
    }
    const value = chatMessageInput.value.trim();
    if (!value) {
      return;
    }
    const author = currentUserEmail ? currentUserEmail.split('@')[0] : 'You';
    chatMessages = [
      ...chatMessages,
      {
        id: window.crypto?.randomUUID?.() || `msg-${Date.now()}`,
        author,
        content: value,
        timestamp: Date.now(),
        isSelf: true,
      },
    ];
    chatMessageInput.value = '';
    renderChatMessages();
  }

  function handleAnnotationCreate(kind) {
    if (!diagram) {
      return;
    }
    const selection = diagram.selection.first();
    if (!selection) {
      window.alert('Select a device or connection to annotate.');
      return;
    }
    const promptText = kind === 'callout' ? 'Enter callout text' : 'Enter note text';
    const value = window.prompt(promptText, '');
    if (!value) {
      return;
    }
    const targetType = selection instanceof go.Link ? 'connection' : 'device';
    const targetId = selection.data?.id || selection.data?.key;
    annotationNotes = [
      {
        id: window.crypto?.randomUUID?.() || `note-${Date.now()}`,
        type: kind,
        text: value.trim(),
        targetType,
        targetId,
        createdAt: new Date().toISOString(),
      },
      ...annotationNotes,
    ];
    renderAnnotations();
    showStatus('Annotation added', 'synced');
  }

  function renderAnnotations() {
    if (!annotationList) {
      return;
    }
    annotationList.innerHTML = '';
    if (!annotationNotes.length) {
      const empty = document.createElement('li');
      empty.className = 'utility-hint';
      empty.textContent = 'No annotations yet.';
      annotationList.appendChild(empty);
      return;
    }
    annotationNotes.forEach((note) => {
      const item = document.createElement('li');
      item.textContent = `[${note.type}] ${note.text}`;
      annotationList.appendChild(item);
    });
  }

  function handleImportJson() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      const reader = new FileReader();
      reader.onload = (loadEvent) => {
        try {
          const data = JSON.parse(loadEvent.target.result);
          applyLayout(data);
          showStatus('Layout imported', 'synced');
        } catch (error) {
          console.error('Import failed', error);
          window.alert('Unable to import the selected file.');
        }
      };
      reader.readAsText(file);
    });
    input.click();
  }

  function handleExportSvg() {
    if (!diagram) {
      return;
    }
    const svg = diagram.makeSvg({ scale: 1, background: canvasInspectorFields.background.value || '#f5f7fb' });
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);
    const blob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `fds-architecture-${Date.now()}.svg`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function handleExportReport() {
    const layout = exportLayout();
    const lines = [
      'Signal Mapping Summary',
      `Generated: ${new Date().toLocaleString()}`,
      '',
      'Devices:',
      ...layout.nodes.map((node, index) => `${index + 1}. ${node.label} (${node.metadata?.signal_type || 'unspecified'})`),
      '',
      'Connections:',
      ...layout.connections.map(
        (connection, index) =>
          `${index + 1}. ${connection.from.nodeId} -> ${connection.to.nodeId} (${connection.type || 'generic'})`
      ),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `fds-signal-map-${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function applyThemeState() {
    if (!stageWrapper) {
      return;
    }
    const highContrastEnabled = Boolean(highContrastToggle?.checked);
    const colorSafeEnabled = Boolean(colorblindToggle?.checked);
    stageWrapper.classList.toggle('is-high-contrast', highContrastEnabled);
    stageWrapper.classList.toggle('is-colorblind', colorSafeEnabled);
    const background = highContrastEnabled ? '#0f172a' : canvasInspectorFields.background.value || '#f5f7fb';
    stageWrapper.style.background = background;
    if (diagram?.div) {
      diagram.div.style.background = background;
    }
  }

  function updateRulers() {
    const visible = rulersToggle?.checked !== false;
    if (rulerHorizontal) {
      rulerHorizontal.classList.toggle('is-visible', visible);
    }
    if (rulerVertical) {
      rulerVertical.classList.toggle('is-visible', visible);
    }
  }

  function updateMeasurementOverlay() {
    if (!measureOverlay) {
      return;
    }
    if (!measurementEnabled || !diagram || diagram.selection.count === 0) {
      measureOverlay.classList.remove('is-visible');
      measureOverlay.style.transform = 'translate(-9999px, -9999px)';
      measureOverlay.style.width = '0';
      measureOverlay.style.height = '0';
      measureOverlay.textContent = '';
      return;
    }
    const bounds = diagram.computePartsBounds(diagram.selection);
    if (!bounds) {
      measureOverlay.classList.remove('is-visible');
      return;
    }
    const topLeft = diagram.transformDocToView(bounds.position);
    const bottomRight = diagram.transformDocToView(new go.Point(bounds.right, bounds.bottom));
    const width = Math.max(bottomRight.x - topLeft.x, 0);
    const height = Math.max(bottomRight.y - topLeft.y, 0);
    measureOverlay.classList.add('is-visible');
    measureOverlay.style.transform = `translate(${topLeft.x}px, ${topLeft.y}px)`;
    measureOverlay.style.width = `${width}px`;
    measureOverlay.style.height = `${height}px`;
    measureOverlay.textContent = `${Math.round(width)}px × ${Math.round(height)}px`;
  }

  function handleSnapPortsToggle() {
    if (!diagram || !snapPortsToggle) {
      return;
    }
    const enabled = snapPortsToggle.checked !== false;
    diagram.toolManager.linkingTool.portGravity = enabled ? 20 : 0;
    diagram.toolManager.relinkingTool.portGravity = enabled ? 20 : 0;
  }

  function distributeSelection(axis) {
    if (!diagram) {
      return;
    }
    const nodes = diagram.selection.filter((part) => part instanceof go.Node).toArray();
    if (nodes.length < 3) {
      window.alert('Select at least three devices to distribute evenly.');
      return;
    }
    nodes.sort((a, b) => (axis === 'horizontal' ? a.location.x - b.location.x : a.location.y - b.location.y));
    const first = nodes[0].location.copy();
    const last = nodes[nodes.length - 1].location.copy();
    const span = axis === 'horizontal' ? last.x - first.x : last.y - first.y;
    if (Math.abs(span) < 1) {
      return;
    }
    const step = span / (nodes.length - 1);
    diagram.startTransaction('distribute');
    nodes.forEach((node, index) => {
      const point = node.location.copy();
      if (axis === 'horizontal') {
        node.location = new go.Point(first.x + step * index, point.y);
      } else {
        node.location = new go.Point(point.x, first.y + step * index);
      }
    });
    diagram.commitTransaction('distribute');
    schedulePersist();
    updateMeasurementOverlay();
    showStatus('Devices distributed', 'synced');
  }

  function handleAutoArrange() {
    if (!diagram) {
      return;
    }
    diagram.startTransaction('auto-arrange');
    const layout = go.GraphObject.make(go.LayeredDigraphLayout, { layerSpacing: 80, columnSpacing: 80 });
    layout.diagram = diagram;
    layout.doLayout(diagram);
    diagram.commitTransaction('auto-arrange');
    schedulePersist();
    updateMeasurementOverlay();
    showStatus('Auto arrangement complete', 'synced');
  }

  function handleAutoRoute() {
    if (!diagram) {
      return;
    }
    diagram.startTransaction('auto-route');
    diagram.model.linkDataArray.forEach((linkData) => {
      diagram.model.setDataProperty(linkData, 'style', 'orthogonal');
    });
    diagram.commitTransaction('auto-route');
    schedulePersist();
    maybeAutoValidate('auto-route');
    showStatus('Auto-routing applied', 'synced');
  }

  function highlightFlowFrom(startKey) {
    if (!diagram) {
      return;
    }
    diagram.clearHighlighteds();
    const queue = [startKey];
    const visited = new Set();
    while (queue.length) {
      const key = queue.shift();
      if (visited.has(key)) {
        continue;
      }
      visited.add(key);
      const node = diagram.findPartForKey(key);
      if (node) {
        node.isHighlighted = true;
        diagram.findLinksOutOf(node).each((link) => {
          link.isHighlighted = true;
          const nextKey = link.toNode?.data?.key;
          if (nextKey && !visited.has(nextKey)) {
            queue.push(nextKey);
          }
        });
      }
    }
  }

  function handleHighlightFlow() {
    if (!diagram) {
      return;
    }
    const selection = diagram.selection.first();
    let startKey = null;
    if (selection instanceof go.Node) {
      startKey = selection.data?.key;
    } else if (selection instanceof go.Link) {
      startKey = selection.data?.from;
    }
    if (!startKey) {
      window.alert('Select a device to highlight the downstream flow.');
      return;
    }
    highlightFlowFrom(startKey);
    showStatus('Flow highlighted', 'synced');
  }

  function handleDuplicate() {
    if (!diagram || diagram.selection.count === 0) {
      window.alert('Select an item to duplicate.');
      return;
    }
    const offsetPoint =
      diagram.lastInput?.documentPoint?.copy() ||
      diagram.transformViewToDoc(diagram.viewportBounds.center) ||
      new go.Point(20, 20);
    offsetPoint.offset(24, 24);
    diagram.startTransaction('duplicate');
    diagram.commandHandler.copySelection();
    diagram.commandHandler.pasteSelection(offsetPoint);
    diagram.commitTransaction('duplicate');
    schedulePersist();
    updateMeasurementOverlay();
    showStatus('Selection duplicated', 'synced');
  }

  function showShortcutSheet() {
    window.alert(
      [
        'Keyboard Shortcuts',
        '',
        'Ctrl + C / Ctrl + V — Copy / Paste',
        'Ctrl + D — Duplicate selection',
        'Delete — Remove selection',
        'Ctrl + G / Ctrl + Shift + G — Group / Ungroup',
        'Ctrl + Z / Ctrl + Y — Undo / Redo',
        'Space — Temporarily pan the canvas',
      ].join('\n')
    );
  }

  function applyLayerIsolation() {
    if (!diagram) {
      return;
    }
    const isolate = layerIsolationToggle?.checked;
    if (!isolate) {
      layers.forEach((layer) => toggleLayerVisibility(layer.name, true, true));
      renderLayers();
      schedulePersist();
      return;
    }
    layers.forEach((layer) => toggleLayerVisibility(layer.name, layer.name === activeLayer, true));
    renderLayers();
    schedulePersist();
  }

  function handleActiveLayerLockToggle() {
    if (!layerLockToggle) {
      return;
    }
    toggleLayerLock(activeLayer, layerLockToggle.checked, true);
    renderLayers();
    schedulePersist();
  }

  function handleLayerIsolationToggle() {
    applyLayerIsolation();
  }

  function refreshVersions() {
    if (!submissionId || !versionSelector) {
      return;
    }
    fetch(`/reports/system-architecture/versions/${submissionId}?limit=10`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load versions');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error('Failed to load versions');
        }
        versionSelector.innerHTML = '<option value=\"\">Version history</option>';
        (data.versions || []).forEach((version) => {
          const option = document.createElement('option');
          option.value = version.id;
          option.textContent = `${version.version_label || version.id} • ${new Date(version.created_at).toLocaleString()}`;
          versionSelector.appendChild(option);
        });
      })
      .catch((error) => {
        console.warn('Unable to load version history', error);
      });
  }

  function handleVersionLoad(event) {
    const versionId = event.target.value;
    if (!versionId || !submissionId) {
      return;
    }
    fetch(`/reports/system-architecture/versions/${submissionId}/${versionId}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to fetch version');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success || !data.version) {
          throw new Error('Version not found');
        }
        if (window.confirm('Load this snapshot? Unsaved changes will be replaced.')) {
          applyLayout(data.version.layout || {});
          showStatus('Snapshot loaded', 'synced');
        } else {
          versionSelector.value = '';
        }
      })
      .catch((error) => {
        console.error('Unable to load snapshot', error);
        window.alert('Unable to load the selected version.');
      });
  }

  function handleVersionSave() {
    if (!submissionId) {
      window.alert('Save the FDS at least once before storing snapshots.');
      return;
    }
    const note = window.prompt('Optional note for this snapshot', '');
    fetch(`/reports/system-architecture/versions/${submissionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layout: exportLayout(), note }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Snapshot save failed');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.success) {
          throw new Error('Snapshot save failed');
        }
        refreshVersions();
        showStatus('Snapshot saved', 'synced');
      })
      .catch((error) => {
        console.error('Snapshot save failed', error);
        window.alert('Unable to save snapshot. Try again later.');
      });
  }

  function refreshLayoutFromServer() {
    if (!submissionId) {
      schedulePersist();
      return;
    }
    fetch(`/reports/system-architecture/${submissionId}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to fetch layout');
        }
        return response.json();
      })
      .then((data) => {
        if (data?.success && data.payload) {
          applyLayout(data.payload);
        }
        if (data?.payload?.assetLibrary) {
          assetLibrary = data.payload.assetLibrary;
          renderAssetLibrary(assetLibrary);
        }
        toggleEmptyDiagramState();
      })
      .catch((error) => {
        console.warn('Unable to fetch stored layout', error);
        toggleEmptyDiagramState();
        schedulePersist();
      });
  }

  function restoreInitialLayout() {
    if (!hiddenInput) {
      return;
    }
    if (hiddenInput.value) {
      try {
        const layout = JSON.parse(hiddenInput.value);
        applyLayout(layout || {});
        return;
      } catch (error) {
        console.warn('Stored layout is invalid JSON. Falling back to server copy.', error);
      }
    }
    refreshLayoutFromServer();
  }

  function initCollaboration() {
    if (!liveToggle || !submissionId) {
      return;
    }
    liveToggle.addEventListener('change', (event) => {
      const enabled = event.target.checked;
      if (!enabled) {
        collabStatus.innerHTML = '<i class=\"fas fa-user-slash\"></i> Offline';
        return;
      }
      window.alert('Live co-editing will be available soon. This toggle is reserved for future updates.');
      event.target.checked = false;
    });
  }

  function bindEvents() {
    addLayerBtn?.addEventListener('click', handleAddLayer);
    toolSelectBtn?.addEventListener('click', handleToolSelect);
    toolConnectorBtn?.addEventListener('click', handleToolConnector);
    toolAnnotationBtn?.addEventListener('click', handleToolAnnotation);
    copyBtn?.addEventListener('click', handleCopy);
    pasteBtn?.addEventListener('click', handlePaste);
    deleteBtn?.addEventListener('click', handleDelete);
    groupBtn?.addEventListener('click', handleGroup);
    ungroupBtn?.addEventListener('click', handleUngroup);
    alignLeftBtn?.addEventListener('click', () => alignSelection('left'));
    alignCenterBtn?.addEventListener('click', () => alignSelection('center'));
    undoBtn?.addEventListener('click', handleUndo);
    redoBtn?.addEventListener('click', handleRedo);
    zoomSlider?.addEventListener('input', (event) => handleZoom(event.target.value));
    zoomInBtn?.addEventListener('click', () => handleZoomDelta(0.1));
    zoomOutBtn?.addEventListener('click', () => handleZoomDelta(-0.1));
    gridToggle?.addEventListener('change', () => handleGridToggle());
    snapToggle?.addEventListener('change', () => handleSnapToggle());
    inspectorFields.apply?.addEventListener('click', handleNodeInspectorApply);
    inspectorConnectionFields.apply?.addEventListener('click', handleConnectionInspectorApply);
    canvasInspectorFields.apply?.addEventListener('click', handleCanvasInspectorApply);
    generateBtn?.addEventListener('click', handleGenerate);
    resetBtn?.addEventListener('click', handleReset);
    storeBtn?.addEventListener('click', handleStore);
    syncBtn?.addEventListener('click', handleSync);
    templateSaveBtn?.addEventListener('click', handleTemplateSave);
    templateRefreshBtn?.addEventListener('click', refreshTemplates);
    assetUploadInput?.addEventListener('change', handleAssetUpload);
    exportPngBtn?.addEventListener('click', handleExportPng);
    exportPdfBtn?.addEventListener('click', handleExportPdf);
    exportSvgBtn?.addEventListener('click', handleExportSvg);
    exportReportBtn?.addEventListener('click', handleExportReport);
    versionSelector?.addEventListener('change', handleVersionLoad);
    versionSaveBtn?.addEventListener('click', handleVersionSave);
    moduleSaveBtn?.addEventListener('click', () => handleModuleSave({ quickName: moduleNameInput?.value?.trim() }));
    moduleInsertBtn?.addEventListener('click', handleModuleInsert);
    moduleRefreshBtn?.addEventListener('click', handleModuleRefresh);
    moduleList?.addEventListener('click', (event) => {
      const target = event.target.closest('[data-module-id]');
      if (target) {
        handleModuleSelect(target.dataset.moduleId);
      }
    });
    highContrastToggle?.addEventListener('change', applyThemeState);
    colorblindToggle?.addEventListener('change', applyThemeState);
    shortcutsBtn?.addEventListener('click', showShortcutSheet);
    toolPanBtn?.addEventListener('click', handleToolPan);
    duplicateBtn?.addEventListener('click', handleDuplicate);
    createModuleBtn?.addEventListener('click', () => handleModuleSave({ quickName: `Quick Module ${customModules.length + 1}` }));
    distributeHorizontalBtn?.addEventListener('click', () => distributeSelection('horizontal'));
    distributeVerticalBtn?.addEventListener('click', () => distributeSelection('vertical'));
    autoArrangeBtn?.addEventListener('click', handleAutoArrange);
    autoRouteBtn?.addEventListener('click', handleAutoRoute);
    highlightFlowBtn?.addEventListener('click', handleHighlightFlow);
    validateToolbarBtn?.addEventListener('click', () => runValidation({ origin: 'toolbar' }));
    snapPortsToggle?.addEventListener('change', handleSnapPortsToggle);
    rulersToggle?.addEventListener('change', updateRulers);
    measureToggle?.addEventListener('change', (event) => {
      measurementEnabled = event.target.checked;
      updateMeasurementOverlay();
    });
    validationBtn?.addEventListener('click', () => runValidation({ origin: 'utility' }));
    autoValidationToggle?.addEventListener('change', () => maybeAutoValidate('toggle'));
    simulationBtn?.addEventListener('click', () => runSimulation({ silent: false }));
    simulationReportBtn?.addEventListener('click', exportSimulationResults);
    lockSelectionBtn?.addEventListener('click', handleLockSelection);
    chatSendBtn?.addEventListener('click', handleChatSend);
    chatMessageInput?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleChatSend();
      }
    });
    addStickyBtn?.addEventListener('click', () => handleAnnotationCreate('sticky'));
    addCalloutBtn?.addEventListener('click', () => handleAnnotationCreate('callout'));
    importJsonBtn?.addEventListener('click', handleImportJson);
    importVisioBtn?.addEventListener('click', () => window.alert('Visio import will be available soon. Export as JSON to import today.'));
    importDxfBtn?.addEventListener('click', () => window.alert('DXF / DWG import requires the desktop agent. Coming soon!'));
    syncPlcBtn?.addEventListener('click', () => window.alert('PLC synchronisation will be enabled in the upcoming release.'));
    bulkInspectorFields.layer?.addEventListener('click', handleBulkLayerAssign);
    bulkInspectorFields.signal?.addEventListener('click', handleBulkSignalAssign);
    bulkInspectorFields.color?.addEventListener('click', handleBulkColorize);
    filterFields.apply?.addEventListener('click', handleFilterApply);
    filterFields.clear?.addEventListener('click', handleFilterClear);
    layerLockToggle?.addEventListener('change', handleActiveLayerLockToggle);
    layerIsolationToggle?.addEventListener('change', handleLayerIsolationToggle);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Delete') {
        handleDelete();
      }
    });
  }

  function rejuvenateCanvasBackground() {
    const stage = document.getElementById('architecture-stage-wrapper');
    if (stage) {
      stage.style.background = 'linear-gradient(135deg, rgba(245,247,255,0.9), rgba(255,255,255,0.9))';
    }
  }

  function handleAddLayer() {
    const name = window.prompt('Enter a name for the new layer:', `Layer ${layers.length + 1}`);
    if (name) {
        addLayer(name);
    }
  }

  function addLayer(name, isVisible = true, isLocked = false) {
    const layerName = name.trim();
    if (!layerName || layers.find(l => l.name === layerName)) {
        window.alert('Layer name must be unique.');
        return;
    }

    diagram.startTransaction('add layer');
    diagram.addLayer(layerName);
    diagram.commitTransaction('add layer');

    layers.push({ name: layerName, isVisible, isLocked });
    renderLayers();
    setActiveLayer(layerName);
    schedulePersist();
  }

  function renderLayers() {
    if (!layerList) return;
    layerList.innerHTML = '';

    if (layers.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'panel-empty';
      empty.textContent = 'Create layers to organize your diagram.';
      layerList.appendChild(empty);
      return;
    }

    layers.forEach((layer) => {
      const item = document.createElement('div');
      item.className = 'layer-item';
      if (layer.name === activeLayer) {
        item.classList.add('is-active');
      }
      item.dataset.layerName = layer.name;

      const nameSpan = document.createElement('span');
      nameSpan.textContent = layer.name;
      nameSpan.className = 'layer-name';
      nameSpan.onclick = () => setActiveLayer(layer.name);

      const actions = document.createElement('div');
      actions.className = 'layer-actions';

      const visibilityBtn = document.createElement('button');
      visibilityBtn.className = 'icon-btn';
      visibilityBtn.innerHTML = `<i class="fas ${layer.isVisible ? 'fa-eye' : 'fa-eye-slash'}"></i>`;
      visibilityBtn.title = layer.isVisible ? 'Hide Layer' : 'Show Layer';
      visibilityBtn.onclick = () => toggleLayerVisibility(layer.name);

      const lockBtn = document.createElement('button');
      lockBtn.className = 'icon-btn';
      lockBtn.innerHTML = `<i class="fas ${layer.isLocked ? 'fa-lock' : 'fa-lock-open'}"></i>`;
      lockBtn.title = layer.isLocked ? 'Unlock Layer' : 'Lock Layer';
      lockBtn.onclick = () => toggleLayerLock(layer.name);

      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'icon-btn';
      deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
      deleteBtn.title = 'Delete Layer';
      deleteBtn.onclick = () => deleteLayer(layer.name);

      actions.appendChild(visibilityBtn);
      actions.appendChild(lockBtn);
      if (layer.name !== 'Default') {
        actions.appendChild(deleteBtn);
      }

      item.appendChild(nameSpan);
      item.appendChild(actions);
      layerList.appendChild(item);
    });

    if (layerLockToggle) {
      const current = layers.find((layer) => layer.name === activeLayer);
      layerLockToggle.checked = Boolean(current?.isLocked);
    }
  }

  function setActiveLayer(layerName) {
    activeLayer = layerName;
    renderLayers();
    if (layerIsolationToggle?.checked) {
      applyLayerIsolation();
    }
  }

  function toggleLayerVisibility(layerName, forceValue, skipRender = false) {
    const layer = layers.find((l) => l.name === layerName);
    if (!layer) {
      return;
    }
    if (typeof forceValue === 'boolean') {
      layer.isVisible = forceValue;
    } else {
      layer.isVisible = !layer.isVisible;
    }
    const goLayer = diagram?.findLayer(layerName);
    if (goLayer) {
      goLayer.visible = layer.isVisible;
    }
    if (!skipRender) {
      renderLayers();
      schedulePersist();
    }
  }

  function toggleLayerLock(layerName, forceValue, skipRender = false) {
    const layer = layers.find((l) => l.name === layerName);
    if (!layer) {
      return;
    }
    if (typeof forceValue === 'boolean') {
      layer.isLocked = forceValue;
    } else {
      layer.isLocked = !layer.isLocked;
    }
    const goLayer = diagram?.findLayer(layerName);
    if (goLayer) {
      goLayer.parts.each((part) => {
        part.selectable = !layer.isLocked;
        part.movable = !layer.isLocked;
      });
    }
    if (!skipRender) {
      renderLayers();
      schedulePersist();
    }
  }

  function deleteLayer(layerName) {
    if (layerName === 'Default') {
        window.alert('The Default layer cannot be deleted.');
        return;
    }
    if (!window.confirm(`Are you sure you want to delete the "${layerName}" layer? All items on this layer will be moved to the Default layer.`)) {
        return;
    }

    diagram.startTransaction('delete layer');
    const layer = diagram.findLayer(layerName);
    if (layer) {
        layer.parts.each(part => {
            part.layerName = 'Default';
        });
        diagram.removeLayer(layer);
    }
    diagram.commitTransaction('delete layer');

    layers = layers.filter(l => l.name !== layerName);
    if (activeLayer === layerName) {
        setActiveLayer('Default');
    }
    renderLayers();
    schedulePersist();
  }

  function init() {
    hiddenInput = $('system_architecture_layout');
    statusIndicator = $('architecture-status-indicator');
    assetList = $('arch-asset-list');
    templateList = $('arch-template-list');
    templateNameInput = $('arch-template-name');
    layerList = $('arch-layer-list');
    addLayerBtn = $('arch-add-layer');
    moduleList = $('arch-module-list');
    moduleNameInput = $('arch-module-name');
    moduleSaveBtn = $('arch-save-module');
    moduleInsertBtn = $('arch-insert-module');
    moduleRefreshBtn = $('arch-refresh-modules');
    highContrastToggle = $('arch-toggle-high-contrast');
    colorblindToggle = $('arch-toggle-colorblind');
    layerLockToggle = $('arch-toggle-active-layer-lock');
    layerIsolationToggle = $('arch-toggle-layer-isolation');
    shortcutsBtn = $('arch-shortcuts');
    toolPanBtn = $('arch-tool-pan');
    duplicateBtn = $('arch-tool-duplicate');
    createModuleBtn = $('arch-tool-create-module');
    distributeHorizontalBtn = $('arch-distribute-horizontal');
    distributeVerticalBtn = $('arch-distribute-vertical');
    autoArrangeBtn = $('arch-auto-arrange');
    autoRouteBtn = $('arch-tool-autoroute');
    highlightFlowBtn = $('arch-tool-highlight-flow');
    validateToolbarBtn = $('arch-tool-validate');
    snapPortsToggle = $('arch-toggle-snap-ports');
    rulersToggle = $('arch-toggle-rulers');
    measureToggle = $('arch-toggle-measure');
    validationBtn = $('arch-run-validation');
    autoValidationToggle = $('arch-toggle-auto-validation');
    validationResultsList = $('arch-validation-results');
    simulationBtn = $('arch-run-simulation');
    simulationResultsList = $('arch-simulation-results');
    simulationReportBtn = $('arch-generate-test-report');
    collaboratorList = $('arch-collaborator-list');
    lockSelectionBtn = $('arch-lock-selection');
    chatLog = $('arch-chat-log');
    chatMessageInput = $('arch-chat-message');
    chatSendBtn = $('arch-chat-send');
    annotationList = $('arch-annotation-thread');
    addStickyBtn = $('arch-add-sticky');
    addCalloutBtn = $('arch-add-callout');
    importJsonBtn = $('arch-import-json');
    importVisioBtn = $('arch-import-visio');
    importDxfBtn = $('arch-import-dxf');
    syncPlcBtn = $('arch-sync-plc');
    exportSvgBtn = $('arch-export-svg');
    exportReportBtn = $('arch-export-report');
    stageWrapper = $('architecture-stage-wrapper');
    rulerHorizontal = $('architecture-ruler-horizontal');
    rulerVertical = $('architecture-ruler-vertical');
    cursorsLayer = $('architecture-cursors');
    annotationLayer = $('architecture-annotation-layer');
    measureOverlay = $('architecture-measure-overlay');
    toolButtons = Array.from(document.querySelectorAll('.architecture-toolbar [data-tool]'));
    submissionId = document.querySelector('input[name="submission_id"]')?.value?.trim() || '';
    currentUserEmail = document.querySelector('input[name="prepared_by_email"]')?.value?.trim() || '';

    initDiagram();
    bindEvents();
    activateTool(toolSelectBtn);
    rejuvenateCanvasBackground();
    restoreInitialLayout();
    refreshTemplates();
    refreshAssets();
    refreshVersions();
    initCollaboration();
    populateCanvasInspector();
    loadModulesFromStorage();
    renderChatMessages();
    renderAnnotations();
    initialiseCollaborators();
    applyThemeState();
    updateRulers();
    measurementEnabled = measureToggle?.checked || false;
    maybeAutoValidate('init');
    togglePorts(false);
    toggleEmptyDiagramState();
  }

  document.addEventListener('DOMContentLoaded', init);
})();





(() => {
  const PLACEHOLDER_IMAGE = 'https://via.placeholder.com/320x200.png?text=Device';
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
  let assetLibrary = [];
  let submissionId = '';
  let currentUserEmail = '';
  let portsVisible = false;
  let nodeKeySeed = 0;
  let linkKeySeed = 0;

  const inspectorFields = {
    label: $('inspector-node-label'),
    model: $('inspector-node-model'),
    notes: $('inspector-node-notes'),
    ip: $('inspector-node-ip'),
    slot: $('inspector-node-slot'),
    tags: $('inspector-node-tags'),
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
    notes: $('inspector-connection-notes'),
    apply: $('inspector-connection-apply'),
    container: document.querySelector('.inspector-section[data-view="connection"]'),
  };

  const canvasInspectorFields = {
    background: $('inspector-canvas-background'),
    gridSize: $('inspector-canvas-grid-size'),
    apply: $('inspector-canvas-apply'),
    container: document.querySelector('.inspector-section[data-view="canvas"]'),
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
    inspectorSections.forEach((section) => {
      section.classList.toggle('is-visible', section.dataset.view === view);
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
    inspectorConnectionFields.label.value = '';
    inspectorConnectionFields.type.value = '';
    inspectorConnectionFields.color.value = '#1f2937';
    inspectorConnectionFields.width.value = 2;
    inspectorConnectionFields.style.value = 'orthogonal';
    inspectorConnectionFields.arrowStart.value = 'none';
    inspectorConnectionFields.arrowEnd.value = 'triangle';
    inspectorConnectionFields.notes.value = '';
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
    diagram.toolManager.linkingTool.direction = go.LinkingTool.ForwardsOnly;
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
      $go(go.Shape, { strokeWidth: 2, stroke: '#1f2937' }, new go.Binding('stroke', 'color').makeTwoWay(), new go.Binding('strokeWidth', 'width').makeTwoWay()),
      $go(go.Shape, { toArrow: 'Standard', stroke: null, fill: '#1f2937' }, new go.Binding('toArrow', 'arrow').makeTwoWay()),
      $go(
        go.TextBlock,
        { segmentOffset: new go.Point(0, -10), editable: true, font: '12px "Montserrat", sans-serif', stroke: '#1f2d4f' },
        new go.Binding('text', 'label').makeTwoWay()
      )
    );

    diagram.addDiagramListener('ChangedSelection', () => handleSelectionChanged());
    diagram.addDiagramListener('SelectionMoved', () => schedulePersist());
    diagram.addDiagramListener('SelectionCopied', () => schedulePersist());
    diagram.addDiagramListener('LinkDrawn', () => {
      schedulePersist();
      showStatus('Connection created', 'synced');
    });
    diagram.addDiagramListener('LinkRelinked', () => schedulePersist());
    diagram.addDiagramListener('PartResized', (event) => {
      const node = event.subject.part;
      if (node && node.data) {
        diagram.model.commit((model) => {
          model.set(node.data, 'size', go.Size.stringify(node.resizeObject.desiredSize));
        }, 'resize');
        schedulePersist();
      }
    });
    diagram.addDiagramListener('ViewportBoundsChanged', () => {
      if (zoomSlider) {
        zoomSlider.value = diagram.scale.toFixed(2);
      }
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
  }

  function populateConnectionInspector(data) {
    setInspectorView('connection');
    inspectorConnectionFields.label.value = data.label || '';
    inspectorConnectionFields.type.value = data.type || '';
    inspectorConnectionFields.color.value = data.color || '#1f2937';
    inspectorConnectionFields.width.value = data.width || 2;
    inspectorConnectionFields.style.value = data.curve || 'curved';
    inspectorConnectionFields.arrowStart.value = data.arrowStart || 'none';
    inspectorConnectionFields.arrowEnd.value = data.arrow || 'triangle';
    inspectorConnectionFields.notes.value = data.metadata?.notes || '';
  }

  function populateCanvasInspector() {
    setInspectorView('canvas');
    if (!diagram) {
      return;
    }
    canvasInspectorFields.background.value = rgbToHex(diagram.div?.style?.backgroundColor || '#f5f7fb');
    canvasInspectorFields.gridSize.value = diagram.grid.gridCellSize.width || 32;
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
        metadata: node.metadata || {},
        loc: `${x} ${y}`,
        size: `${width} ${height}`,
        background: node.style?.fill || DEFAULT_NODE_STYLE.fill,
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
        metadata: connection.metadata || {},
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
            curve: data.curve || 'curved',
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
    };
    diagram.model.addNodeData(data);
    diagram.commitTransaction('add node');
    schedulePersist();
  }

  function handleToolSelect() {
    togglePorts(false);
    showStatus('Select tool enabled', 'synced');
  }

  function handleToolConnector() {
    togglePorts(true);
    showStatus('Connector tool: drag from a blue port to another device', 'saving');
  }

  function handleToolAnnotation() {
    window.alert('Annotations will be available in a future update. For now, use the connector tool to describe links.');
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
      model.set(node.data, 'metadata', {
        ...(node.data.metadata || {}),
        notes: inspectorFields.notes.value.trim(),
        ip_address: inspectorFields.ip.value.trim(),
        slot: inspectorFields.slot.value.trim(),
        tags: inspectorFields.tags.value
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
    }, 'update-node');
    schedulePersist();
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
    diagram.model.commit((model) => {
      model.set(link.data, 'label', inspectorConnectionFields.label.value.trim());
      model.set(link.data, 'type', inspectorConnectionFields.type.value.trim());
      model.set(link.data, 'color', inspectorConnectionFields.color.value || '#1f2937');
      model.set(link.data, 'width', Number.parseFloat(inspectorConnectionFields.width.value) || 2);
      model.set(link.data, 'arrow', inspectorConnectionFields.arrowEnd.value || 'Standard');
      model.set(link.data, 'arrowStart', inspectorConnectionFields.arrowStart.value || 'none');
      model.set(link.data, 'metadata', {
        ...(link.data.metadata || {}),
        notes: inspectorConnectionFields.notes.value.trim(),
      });
    }, 'update-link');
    schedulePersist();
    showStatus('Connection updated', 'synced');
  }

  function handleCanvasInspectorApply() {
    if (!diagram) {
      return;
    }
    const size = Number.parseInt(canvasInspectorFields.gridSize.value, 10) || 32;
    diagram.grid.gridCellSize = new go.Size(size, size);
    diagram.div.style.background = canvasInspectorFields.background.value || '#f5f7fb';
    schedulePersist();
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
    versionSelector?.addEventListener('change', handleVersionLoad);
    versionSaveBtn?.addEventListener('click', handleVersionSave);
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

  function init() {
    hiddenInput = $('system_architecture_layout');
    statusIndicator = $('architecture-status-indicator');
    assetList = $('arch-asset-list');
    templateList = $('arch-template-list');
    templateNameInput = $('arch-template-name');
    submissionId = document.querySelector('input[name=\"submission_id\"]')?.value?.trim() || '';
    currentUserEmail = document.querySelector('input[name=\"prepared_by_email\"]')?.value?.trim() || '';

    initDiagram();
    bindEvents();
    rejuvenateCanvasBackground();
    restoreInitialLayout();
    refreshTemplates();
    refreshAssets();
    refreshVersions();
    initCollaboration();
    populateCanvasInspector();
    togglePorts(false);
    toggleEmptyDiagramState();
  }

  document.addEventListener('DOMContentLoaded', init);
})();

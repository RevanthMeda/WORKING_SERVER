import copy
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

from models import (
    db,
    FDSReport,
    Report,
    SystemArchitectureTemplate,
    SystemArchitectureVersion,
)

DEFAULT_CANVAS_SETTINGS: Dict = {
    "width": 1920,
    "height": 1080,
    "zoom": 1.0,
    "pan": {"x": 0, "y": 0},
    "grid": {"enabled": True, "size": 32, "snap": True},
    "background": "#f5f7fb",
    "show_minimap": True,
}

DEFAULT_NODE_SIZE = {"width": 240, "height": 160}
DEFAULT_NODE_STYLE = {
    "fill": "#ffffff",
    "stroke": "#2d80ff",
    "strokeWidth": 2,
    "cornerRadius": 12,
    "shadowColor": "rgba(45,128,255,0.25)",
    "shadowBlur": 12,
    "shadowOffset": {"x": 0, "y": 4},
    "shadowOpacity": 0.6,
    "backgroundPanel": None,
}

DEFAULT_CONNECTION_STYLE = {
    "color": "#1f2937",
    "width": 2,
    "curve": "straight",
    "dash": [],
    "arrowheads": {"start": "none", "end": "triangle"},
    "labelPosition": 0.5,
}

DEFAULT_METADATA_KEYS = {
    "ip_address": "",
    "slot": "",
    "notes": "",
    "tags": [],
    "linkedEquipmentIndex": None,
}

DEFAULT_PORTS = (
    ("port-top", "top", 0.5),
    ("port-right", "right", 0.5),
    ("port-bottom", "bottom", 0.5),
    ("port-left", "left", 0.5),
)


def _create_default_ports(size: Dict) -> List[Dict]:
    width = size.get("width", DEFAULT_NODE_SIZE["width"])
    height = size.get("height", DEFAULT_NODE_SIZE["height"])
    ports = []
    for port_id, side, ratio in DEFAULT_PORTS:
        ports.append(
            {
                "id": port_id,
                "side": side,
                "ratio": ratio,
                "position": {
                    "x": width * (ratio if side in ("top", "bottom") else (1 if side == "right" else 0)),
                    "y": height * (ratio if side in ("left", "right") else (1 if side == "bottom" else 0)),
                },
            }
        )
    return ports


def default_node_size() -> Dict:
    return copy.deepcopy(DEFAULT_NODE_SIZE)


def default_node_style() -> Dict:
    return copy.deepcopy(DEFAULT_NODE_STYLE)


def default_connection_style() -> Dict:
    return copy.deepcopy(DEFAULT_CONNECTION_STYLE)


def default_node_metadata() -> Dict:
    return copy.deepcopy(DEFAULT_METADATA_KEYS)


def default_ports_for_size(size: Optional[Dict] = None) -> List[Dict]:
    return _create_default_ports(size or DEFAULT_NODE_SIZE)


def _upgrade_legacy_node(raw: Dict, default_node: Optional[Dict] = None, fallback_id: Optional[str] = None) -> Dict:
    base = copy.deepcopy(default_node or {})
    node_id = raw.get("id") or base.get("id") or fallback_id or f"node-{datetime.utcnow().timestamp()}"
    position = raw.get("position") or {
        "x": float(raw.get("x") or base.get("position", {}).get("x", 120)),
        "y": float(raw.get("y") or base.get("position", {}).get("y", 120)),
    }
    size = copy.deepcopy(base.get("size") or DEFAULT_NODE_SIZE)
    for key in ("width", "height"):
        if isinstance(raw.get(key), (int, float)):
            size[key] = float(raw[key])

    metadata = copy.deepcopy(base.get("metadata") or DEFAULT_METADATA_KEYS)
    legacy_metadata = {
        "model": raw.get("model") or base.get("model"),
        "description": raw.get("description") or base.get("description"),
        "quantity": raw.get("quantity") or base.get("quantity"),
        "remarks": raw.get("remarks") or base.get("remarks"),
        "ip_address": raw.get("ip_address"),
        "slot": raw.get("slot"),
        "notes": raw.get("notes"),
    }
    metadata.update({k: v for k, v in legacy_metadata.items() if v is not None})

    ports = raw.get("ports") or base.get("ports")
    if not ports:
        ports = _create_default_ports(size)

    style = copy.deepcopy(DEFAULT_NODE_STYLE)
    style.update(base.get("style") or {})
    style.update(raw.get("style") or {})

    image = copy.deepcopy(base.get("image") or {})
    if raw.get("image"):
        image.update(raw["image"])
    else:
        for key in ("image_url", "imageUrl", "thumbnail_url", "thumbnailUrl"):
            if raw.get(key):
                target_key = key.replace("Url", "_url").replace("url", "_url")
                image[target_key] = raw[key]

    label = raw.get("label") or base.get("label") or raw.get("model") or base.get("model")

    node_payload = {
        "id": node_id,
        "label": label,
        "model": raw.get("model") or base.get("model"),
        "description": raw.get("description") or base.get("description"),
        "quantity": raw.get("quantity") or base.get("quantity"),
        "remarks": raw.get("remarks") or base.get("remarks"),
        "position": position,
        "size": size,
        "rotation": float(raw.get("rotation") or base.get("rotation") or 0),
        "shape": raw.get("shape") or base.get("shape") or "rectangle",
        "image": image,
        "style": style,
        "ports": ports,
        "metadata": metadata,
        "background": raw.get("background") or base.get("background"),
        "equipmentIndex": raw.get("equipmentIndex", base.get("equipmentIndex")),
        "assetSource": raw.get("asset_source") or base.get("assetSource"),
    }
    return node_payload


def _upgrade_legacy_connection(raw: Dict) -> Dict:
    if not raw:
        return {}

    def _normalise_endpoint(endpoint: Dict, default_key: str) -> Dict:
        if not isinstance(endpoint, dict):
            return {"nodeId": endpoint}
        payload = {**endpoint}
        if "node" in payload and "nodeId" not in payload:
            payload["nodeId"] = payload["node"]
        if "port" in payload and "portId" not in payload:
            payload["portId"] = payload["port"]
        if "nodeId" not in payload:
            payload["nodeId"] = endpoint.get(default_key)
        return payload

    style = copy.deepcopy(DEFAULT_CONNECTION_STYLE)
    if isinstance(raw.get("style"), dict):
        style.update(raw["style"])

    color = raw.get("color") or raw.get("stroke") or style.get("color")
    if color:
        style["color"] = color
    width = raw.get("width") or raw.get("strokeWidth")
    if width:
        style["width"] = float(width)

    arrowheads = raw.get("arrowheads") or {}
    if raw.get("arrow_start"):
        arrowheads["start"] = raw["arrow_start"]
    if raw.get("arrow_end"):
        arrowheads["end"] = raw["arrow_end"]
    if arrowheads:
        style["arrowheads"] = {**style.get("arrowheads", {}), **arrowheads}

    connection_payload = {
        "id": raw.get("id") or f"conn-{datetime.utcnow().timestamp()}",
        "from": _normalise_endpoint(raw.get("from") or raw.get("source"), "source"),
        "to": _normalise_endpoint(raw.get("to") or raw.get("target"), "target"),
        "label": raw.get("label"),
        "type": raw.get("type") or "generic",
        "metadata": raw.get("metadata") or {},
        "style": style,
        "vertices": raw.get("vertices") or raw.get("points") or [],
    }
    return connection_payload


def ensure_layout(
    layout: Optional[Dict],
    default_nodes: Optional[List[Dict]] = None,
    equipment_rows: Optional[List[Dict]] = None,
) -> Dict:
    """
    Normalise layout payload into the new schema expected by the upgraded canvas.
    """
    base_layout = {
        "canvas": copy.deepcopy(DEFAULT_CANVAS_SETTINGS),
        "nodes": [],
        "connections": [],
        "groups": [],
        "selection": [],
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "source": "auto",
        },
    }

    if isinstance(layout, str):
        try:
            layout = json.loads(layout)
        except Exception:
            layout = {}
    elif not isinstance(layout, dict):
        layout = {}

    canvas = layout.get("canvas")
    if isinstance(canvas, dict):
        merged_canvas = copy.deepcopy(DEFAULT_CANVAS_SETTINGS)
        merged_canvas.update(canvas)
        base_layout["canvas"] = merged_canvas

    default_nodes_map = {node.get("id"): node for node in (default_nodes or []) if node.get("id")}

    nodes = layout.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        nodes = list(default_nodes_map.values())

    normalised_nodes = []
    for index, raw_node in enumerate(nodes):
        fallback = default_nodes_map.get(raw_node.get("id")) if isinstance(raw_node, dict) else None
        if not isinstance(raw_node, dict):
            continue
        node_payload = _upgrade_legacy_node(raw_node, fallback, fallback_id=f"node-autogen-{index}")
        if equipment_rows and isinstance(node_payload.get("equipmentIndex"), int):
            idx = node_payload["equipmentIndex"]
            if 0 <= idx < len(equipment_rows):
                node_payload.setdefault("metadata", {}).setdefault("equipment", equipment_rows[idx])
        normalised_nodes.append(node_payload)

    # Include default nodes not present in layout (regression for auto placements)
    existing_ids = {node["id"] for node in normalised_nodes}
    for node_id, default_node in default_nodes_map.items():
        if node_id not in existing_ids:
            normalised_nodes.append(copy.deepcopy(default_node))

    connections = []
    raw_connections = layout.get("connections") or layout.get("links") or []
    if isinstance(raw_connections, list):
        for raw_connection in raw_connections:
            if not isinstance(raw_connection, dict):
                continue
            connections.append(_upgrade_legacy_connection(raw_connection))

    base_layout["nodes"] = normalised_nodes
    base_layout["connections"] = connections
    base_layout["groups"] = layout.get("groups") or layout.get("clusters") or []
    if "metadata" in layout and isinstance(layout["metadata"], dict):
        base_layout["metadata"].update(layout["metadata"])

    if equipment_rows:
        base_layout["metadata"]["equipment_rows"] = equipment_rows

    return base_layout


def serialise_layout(layout: Dict) -> str:
    return json.dumps(layout or {}, separators=(',', ':'))


def persist_layout(
    report: Report,
    layout: Dict,
    *,
    created_by: Optional[str] = None,
    note: Optional[str] = None,
    version_label: Optional[str] = None,
) -> None:
    if not report or not layout:
        return

    fds_report: Optional[FDSReport] = report.fds_report
    if not fds_report:
        fds_report = FDSReport(report_id=report.id, data_json="{}")
        db.session.add(fds_report)
        report.fds_report = fds_report

    fds_report.set_system_architecture(layout)
    fds_report.record_architecture_version(
        layout,
        created_by=created_by,
        note=note,
        version_label=version_label,
    )
    db.session.commit()


def list_templates(*, include_shared: bool = True, owned_by: Optional[str] = None) -> List[Dict]:
    query = SystemArchitectureTemplate.query
    if owned_by:
        query = query.filter(
            (SystemArchitectureTemplate.is_shared == True)  # noqa: E712
            | (SystemArchitectureTemplate.created_by == owned_by)
            | (SystemArchitectureTemplate.updated_by == owned_by)
        )
    elif include_shared:
        query = query.filter(SystemArchitectureTemplate.is_shared == True)  # noqa: E712
    else:
        # When include_shared is False and no owner is provided, return empty list.
        return []
    templates = query.order_by(SystemArchitectureTemplate.created_at.desc()).all()
    return [template.to_dict(include_layout=False) for template in templates]


def fetch_template(template_id: int, include_layout: bool = True) -> Optional[Dict]:
    template = SystemArchitectureTemplate.query.filter_by(id=template_id).first()
    if not template:
        return None
    payload = template.to_dict(include_layout=include_layout)
    if include_layout and "layout" not in payload and "layout_raw" in payload:
        try:
            payload["layout"] = json.loads(payload["layout_raw"])
        except Exception:
            payload["layout"] = {}
    return payload


def save_template(
    *,
    name: str,
    layout: Dict,
    user_email: Optional[str],
    description: Optional[str] = None,
    category: Optional[str] = None,
    is_shared: bool = True,
    template_id: Optional[int] = None,
) -> SystemArchitectureTemplate:
    if not name:
        raise ValueError("Template name is required")
    if not layout:
        raise ValueError("Layout payload is required")

    slug = SystemArchitectureTemplate.slugify(name)
    layout_serialized = serialise_layout(layout)

    if template_id:
        template = SystemArchitectureTemplate.query.filter_by(id=template_id).first()
        if not template:
            raise ValueError("Template not found")
    else:
        template = SystemArchitectureTemplate.query.filter_by(slug=slug).first()
        if not template:
            template = SystemArchitectureTemplate(slug=slug)
            db.session.add(template)

    if template.slug != slug:
        conflict = (
            SystemArchitectureTemplate.query.filter(
                SystemArchitectureTemplate.slug == slug,
                SystemArchitectureTemplate.id != template.id,
            ).first()
        )
        if conflict:
            slug = f"{slug}-{template.id or int(datetime.utcnow().timestamp())}"

    template.name = name
    template.slug = slug
    template.description = description
    template.category = category
    template.layout_json = layout_serialized
    template.is_shared = is_shared
    template.updated_by = user_email
    if not template.created_by:
        template.created_by = user_email

    db.session.commit()
    return template


def delete_template(template_id: int) -> bool:
    template = SystemArchitectureTemplate.query.filter_by(id=template_id).first()
    if not template:
        return False
    db.session.delete(template)
    db.session.commit()
    return True


def list_versions(report_id: str, limit: int = 20) -> List[Dict]:
    query = (
        SystemArchitectureVersion.query
        .filter_by(report_id=report_id)
        .order_by(SystemArchitectureVersion.created_at.desc())
    )
    if limit:
        query = query.limit(limit)
    versions = query.all()
    return [version.to_dict(include_layout=False) for version in versions]


def fetch_version(version_id: int) -> Optional[Dict]:
    version = SystemArchitectureVersion.query.filter_by(id=version_id).first()
    if not version:
        return None
    return version.to_dict(include_layout=True)


def record_version_snapshot(
    report_id: str,
    layout: Dict,
    *,
    created_by: Optional[str] = None,
    note: Optional[str] = None,
    version_label: Optional[str] = None,
) -> Optional[SystemArchitectureVersion]:
    report = Report.query.filter_by(id=report_id).first()
    if not report:
        return None
    fds_report = report.fds_report
    if not fds_report:
        fds_report = FDSReport(report_id=report_id, data_json="{}")
        report.fds_report = fds_report
        db.session.add(fds_report)
    snapshot = fds_report.record_architecture_version(
        layout,
        created_by=created_by,
        note=note,
        version_label=version_label,
    )
    db.session.commit()
    return snapshot


def compute_layout_checksum(layout: Dict) -> str:
    serialised = serialise_layout(layout)
    return hashlib.sha256(serialised.encode('utf-8')).hexdigest()

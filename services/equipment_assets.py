import copy
import json
import os
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
from flask import current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from models import db, EquipmentAsset
from services.system_architecture import (
    default_connection_style,
    default_node_metadata,
    default_node_size,
    default_node_style,
    default_ports_for_size,
    ensure_layout,
)

DEFAULT_CACHE_TTL_DAYS = 45
LOCAL_STORAGE_SUBDIR = "static/equipment_assets"
USER_AGENT = "CullyFDSBot/1.0 (+https://cullyautomation.com)"


def _normalise_asset_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://") or path.startswith("data:"):
        return path
    normalised = path.replace("\\", "/")
    if not normalised.startswith("/"):
        normalised = f"/{normalised}"
    return normalised


def _get_storage_root() -> str:
    root = current_app.config.get("EQUIPMENT_ASSET_STORAGE_ROOT", LOCAL_STORAGE_SUBDIR)
    if not os.path.isabs(root):
        root = os.path.join(current_app.root_path, root)
    os.makedirs(root, exist_ok=True)
    return root


def _should_refresh(asset: EquipmentAsset, ttl_days: Optional[int] = None) -> bool:
    if not asset:
        return True
    if asset.is_user_override:
        return False
    ttl = ttl_days or current_app.config.get("EQUIPMENT_ASSET_CACHE_DAYS", DEFAULT_CACHE_TTL_DAYS)
    if not asset.image_url:
        return True
    if not asset.fetched_at:
        return True
    return asset.fetched_at <= datetime.utcnow() - timedelta(days=ttl)


def _download_asset(model_key: str, url: str) -> Optional[str]:
    """
    Download remote image to local storage. Returns relative path or None.
    """
    if not url:
        return None
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None

        extension = content_type.split("/")[-1] or "jpg"
        filename = f"{model_key}-{int(datetime.utcnow().timestamp())}.{extension}"
        storage_root = _get_storage_root()
        destination = os.path.join(storage_root, filename)

        with open(destination, "wb") as file:
            file.write(response.content)

        # Persist relative path for static serving
        rel_path = os.path.relpath(destination, current_app.root_path)
        return rel_path.replace("\\", "/")
    except Exception as exc:
        current_app.logger.warning("Failed to download asset for %s: %s", model_key, exc)
        return None


def _build_placeholder_result(query: str) -> Dict:
    safe_query = quote_plus(query or "Device")
    return {
        "image_url": f"https://via.placeholder.com/320x200.png?text={safe_query}",
        "thumbnail_url": None,
        "source": "placeholder",
        "confidence": 0.0,
        "metadata": {"provider": "placeholder"}
    }


def _search_remote_image(query: str, description: Optional[str] = None) -> Optional[Dict]:
    """
    Search for an equipment image using configured provider.
    """
    if not query:
        return _build_placeholder_result("Device")

    api_key = current_app.config.get("IMAGE_SEARCH_API_KEY")
    endpoint = current_app.config.get("IMAGE_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/images/search")

    search_terms = query
    if description:
        search_terms = f"{query} {description}"

    headers = {"User-Agent": USER_AGENT}
    params = {
        "q": search_terms,
        "count": 10,
        "safeSearch": "Strict",
        "imageType": "Photo",
    }

    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key
    else:
        # Without an API key, fall back to a deterministic placeholder to avoid remote 503s.
        return _build_placeholder_result(search_terms)

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("value") or []
        if not results:
            return _build_placeholder_result(search_terms)
        best = results[0]
        return {
            "image_url": best.get("contentUrl"),
            "thumbnail_url": best.get("thumbnailUrl"),
            "source": payload.get("_type", "bing"),
            "confidence": best.get("confidenceScore") or 0.75,
            "metadata": {
                "width": best.get("width"),
                "height": best.get("height"),
                "encoding_format": best.get("encodingFormat"),
                "host_page_url": best.get("hostPageUrl"),
                "name": best.get("name"),
                "content_size": best.get("contentSize"),
            },
        }
    except Exception as exc:
        current_app.logger.warning("Image search failed for %s: %s", query, exc)
        return _build_placeholder_result(search_terms)


def ensure_asset_for_model(model_name: str, description: Optional[str] = None) -> Optional[EquipmentAsset]:
    """
    Retrieve or fetch an EquipmentAsset for a given model.
    """
    if not model_name:
        return None

    model_key = EquipmentAsset.normalize_model_key(model_name)
    if not model_key:
        return None

    asset = EquipmentAsset.query.filter_by(model_key=model_key).first()
    is_new_asset = False

    if not asset:
        asset = EquipmentAsset(model_key=model_key, display_name=model_name or model_key.upper())
        db.session.add(asset)
        is_new_asset = True

    should_lookup = not asset.is_user_override and (is_new_asset or _should_refresh(asset))
    search_result = None

    if should_lookup:
        search_result = _search_remote_image(model_name or model_key, description)
        if search_result:
            asset.image_url = search_result.get("image_url")
            asset.thumbnail_url = search_result.get("thumbnail_url")
            asset.asset_source = search_result.get("source")
            asset.confidence = search_result.get("confidence")
            metadata = search_result.get("metadata")
            asset.metadata_json = json.dumps(metadata) if metadata else None
            asset.fetched_at = datetime.utcnow()

            if search_result.get("source") != "placeholder":
                local_path = _download_asset(model_key, asset.image_url)
            else:
                local_path = None
            asset.local_path = local_path
        else:
            asset.asset_source = "unavailable"
            asset.fetched_at = datetime.utcnow()

    if not asset.display_name and model_name:
        asset.display_name = model_name

    asset.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        asset = EquipmentAsset.query.filter_by(model_key=model_key).first()

    return asset


def bulk_ensure_assets(equipment_rows: List[Dict]) -> List[Dict]:
    """
    Ensure assets for the provided equipment rows and return enriched payload.
    """
    enriched = []
    for row in equipment_rows or []:
        model = (row.get("Model") or row.get("model") or "").strip()
        description = (row.get("Description") or row.get("description") or "").strip()
        if not model:
            continue
        asset = ensure_asset_for_model(model, description)
        serialized = asset.to_dict() if asset else {}
        enriched.append(
            {
                "raw": row,
                "model_key": serialized.get("model_key"),
                "asset": serialized,
            }
        )
    return enriched


def prepare_layout_nodes(enriched_assets: List[Dict]) -> List[Dict]:
    """
    Convert enriched asset data into layout nodes with default positioning.
    """
    nodes = []
    if not enriched_assets:
        return nodes

    columns = max(1, int(math.ceil(math.sqrt(len(enriched_assets)))))
    spacing_x = current_app.config.get("ARCHITECTURE_NODE_SPACING_X", 260)
    spacing_y = current_app.config.get("ARCHITECTURE_NODE_SPACING_Y", 220)
    start_x = 120
    start_y = 120

    for index, payload in enumerate(enriched_assets):
        row_idx = index // columns
        col_idx = index % columns
        x = start_x + col_idx * spacing_x
        y = start_y + row_idx * spacing_y
        raw = payload.get("raw") or {}
        asset = payload.get("asset") or {}

        node_id = f"node-{payload.get('model_key') or index}"
        size = default_node_size()
        style = default_node_style()
        metadata = default_node_metadata()
        metadata.update(
            {
                "equipment": {
                    "model": raw.get("Model"),
                    "description": raw.get("Description"),
                    "quantity": raw.get("Quantity"),
                    "remarks": raw.get("Remarks"),
                },
                "asset": asset,
                "linkedEquipmentIndex": index,
            }
        )

        image_payload = {
            "url": _normalise_asset_url(asset.get("local_path")) or _normalise_asset_url(asset.get("image_url")),
            "thumbnail": _normalise_asset_url(asset.get("thumbnail_url")),
            "source": asset.get("asset_source"),
            "placeholder": (asset.get("asset_source") or "placeholder") == "placeholder",
        }

        nodes.append(
            {
                "id": node_id,
                "label": asset.get("display_name") or raw.get("Model") or "Device",
                "model": raw.get("Model"),
                "description": raw.get("Description"),
                "quantity": raw.get("Quantity"),
                "remarks": raw.get("Remarks"),
                "position": {"x": x, "y": y},
                "size": size,
                "rotation": 0,
                "shape": "rectangle",
                "image": image_payload,
                "style": style,
                "ports": default_ports_for_size(size),
                "metadata": metadata,
                "equipmentIndex": index,
                "assetSource": asset.get("asset_source"),
            }
        )
    return nodes


def build_architecture_payload(equipment_rows: List[Dict], existing_layout: Optional[Dict] = None) -> Dict:
    """
    Build the architecture payload combining cached assets and existing layout overrides.
    """
    enriched_assets = bulk_ensure_assets(equipment_rows)
    default_nodes = prepare_layout_nodes(enriched_assets)

    layout = ensure_layout(existing_layout, default_nodes, equipment_rows)

    asset_library_index = {}
    for payload in enriched_assets:
        asset = payload.get("asset") or {}
        model_key = payload.get("model_key")
        if not model_key or not asset:
            continue
        asset_library_index[model_key] = {
            "model_key": model_key,
            "display_name": asset.get("display_name") or model_key,
            "manufacturer": asset.get("manufacturer"),
            "image_url": _normalise_asset_url(asset.get("local_path")) or _normalise_asset_url(asset.get("image_url")),
            "thumbnail_url": _normalise_asset_url(asset.get("thumbnail_url")),
            "source": asset.get("asset_source"),
            "confidence": asset.get("confidence"),
            "metadata": asset.get("metadata"),
            "is_user_override": asset.get("is_user_override"),
        }

    layout.setdefault("metadata", {})
    layout["metadata"].update(
        {
            "generated_at": datetime.utcnow().isoformat(),
            "equipment_count": len(equipment_rows or []),
        }
    )
    layout["assetLibrary"] = list(asset_library_index.values())
    layout["connectionDefaults"] = default_connection_style()
    return layout


def save_user_asset_image(model_name: str, storage, user_email: Optional[str] = None) -> Dict:
    """
    Persist a user-uploaded asset image and mark the asset as an override.
    """
    if not storage:
        raise ValueError("File storage payload is required")

    filename = secure_filename(storage.filename or "")
    if not filename:
        filename = f"{model_name or 'device'}-{int(datetime.utcnow().timestamp())}.png"

    model_key = EquipmentAsset.normalize_model_key(model_name or filename)
    if not model_key:
        raise ValueError("Unable to derive model key for asset storage")

    asset = EquipmentAsset.query.filter_by(model_key=model_key).first()
    if not asset:
        asset = EquipmentAsset(model_key=model_key, display_name=model_name or model_key.upper())
        db.session.add(asset)

    storage_root = _get_storage_root()
    user_dir = os.path.join(storage_root, "user")
    os.makedirs(user_dir, exist_ok=True)

    base_name, ext = os.path.splitext(filename)
    ext = ext or ".png"
    unique_name = f"{model_key}-{int(datetime.utcnow().timestamp())}{ext}"
    destination = os.path.join(user_dir, unique_name)

    storage.save(destination)

    rel_path = os.path.relpath(destination, current_app.root_path).replace("\\", "/")
    if not rel_path.startswith("/"):
        rel_path = f"/{rel_path}"

    metadata = {}
    if asset.metadata_json:
        try:
            metadata = json.loads(asset.metadata_json)
        except Exception:
            metadata = {}
    metadata.update(
        {
            "uploaded_by": user_email,
            "uploaded_at": datetime.utcnow().isoformat(),
            "original_filename": storage.filename,
        }
    )

    asset.display_name = model_name or asset.display_name or model_key.upper()
    asset.image_url = rel_path
    asset.thumbnail_url = rel_path
    asset.local_path = rel_path.lstrip("/")
    asset.asset_source = "user-upload"
    asset.is_user_override = True
    asset.metadata_json = json.dumps(metadata)
    asset.updated_at = datetime.utcnow()

    db.session.commit()
    return asset.to_dict()


def list_cached_assets(limit: int = 300) -> List[Dict]:
    """
    Return cached equipment assets for building the local library.
    """
    query = EquipmentAsset.query.order_by(EquipmentAsset.display_name.asc())
    if limit:
        query = query.limit(limit)
    assets = query.all()
    return [asset.to_dict() for asset in assets]

import json
import os
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
from flask import current_app

from models import db, EquipmentAsset

DEFAULT_CACHE_TTL_DAYS = 45
LOCAL_STORAGE_SUBDIR = "static/equipment_assets"
USER_AGENT = "CullyFDSBot/1.0 (+https://cullyautomation.com)"


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


def _search_remote_image(query: str, description: Optional[str] = None) -> Optional[Dict]:
    """
    Search for an equipment image using configured provider.
    """
    if not query:
        return None

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
        # Fallback to Unsplash featured search style (no API key required)
        # Provide placeholder image
        placeholder_url = f"https://source.unsplash.com/featured/?{quote_plus(search_terms)}"
        return {
            "image_url": placeholder_url,
            "thumbnail_url": None,
            "source": "unsplash-featured",
            "confidence": 0.05,
            "metadata": {"provider": "unsplash_featured"},
        }

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("value") or []
        if not results:
            return None
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
        return None


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

    if asset and not _should_refresh(asset):
        return asset

    if not asset:
        asset = EquipmentAsset(model_key=model_key, display_name=model_name)
        db.session.add(asset)

    search_result = _search_remote_image(model_name, description)

    if search_result:
        asset.image_url = search_result.get("image_url")
        asset.thumbnail_url = search_result.get("thumbnail_url")
        asset.asset_source = search_result.get("source")
        asset.confidence = search_result.get("confidence")
        metadata = search_result.get("metadata")
        if metadata:
            asset.metadata_json = json.dumps(metadata)

        asset.display_name = asset.display_name or model_name
        asset.fetched_at = datetime.utcnow()

        local_path = _download_asset(model_key, asset.image_url)
        if local_path:
            asset.local_path = local_path

    else:
        asset.asset_source = "unavailable"
        asset.fetched_at = datetime.utcnow()

    asset.updated_at = datetime.utcnow()
    db.session.commit()
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

        nodes.append(
            {
                "id": f"node-{payload.get('model_key') or index}",
                "model": raw.get("Model"),
                "description": raw.get("Description"),
                "quantity": raw.get("Quantity"),
                "remarks": raw.get("Remarks"),
                "image_url": asset.get("local_path") or asset.get("image_url"),
                "thumbnail_url": asset.get("thumbnail_url"),
                "asset_source": asset.get("asset_source"),
                "position": {"x": x, "y": y},
            }
        )
    return nodes


def build_architecture_payload(equipment_rows: List[Dict], existing_layout: Optional[Dict] = None) -> Dict:
    """
    Build the architecture payload combining cached assets and existing layout overrides.
    """
    enriched_assets = bulk_ensure_assets(equipment_rows)
    default_nodes = prepare_layout_nodes(enriched_assets)

    layout = existing_layout or {}
    saved_nodes = {node.get("id"): node for node in (layout.get("nodes") or []) if node.get("id")}

    merged_nodes = []
    for node in default_nodes:
        if node["id"] in saved_nodes:
            saved = saved_nodes[node["id"]]
            merged_nodes.append({**node, **saved})
        else:
            merged_nodes.append(node)

    payload = {
        "nodes": merged_nodes,
        "connections": layout.get("connections") or [],
        "generated_at": datetime.utcnow().isoformat(),
    }
    return payload

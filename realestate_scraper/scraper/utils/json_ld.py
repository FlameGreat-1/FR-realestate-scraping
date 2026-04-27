"""Robust JSON-LD walker for real estate listing pages.

The schema.org ecosystem is wildly inconsistent across CMSes; this
module produces a small, normalized dict the resolvers can rely on.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator

from selectolax.parser import HTMLParser

_LISTING_TYPES = {
    "product", "realestatelisting", "singlefamilyresidence", "house",
    "apartment", "accommodation", "residence", "realestate",
}

_AGENT_TYPES = {
    "realestateagent", "person",
}

_PRICE_KEYS = ("price", "lowprice", "highprice", "pricevalue")
_REF_KEYS = ("sku", "productid", "identifier", "ref", "reference", "reference_id")
_PHONE_KEYS = ("telephone", "phone", "phonenumber")
_DPE_KEYS = (
    "energyefficiencycategory", "energyclass", "energyrating",
    "dperating", "epcrating", "epccategory",
)
_AGENT_PARENT_KEYS = ("author", "seller", "publisher", "provider", "agent")


def _iter_scripts(html: str) -> Iterator[str]:
    if not html:
        return
    try:
        parser = HTMLParser(html)
    except Exception:
        return
    for node in parser.css('script[type="application/ld+json"]'):
        text = node.text(deep=True, separator="", strip=False)
        if text:
            yield text


def _safe_load(raw: str) -> Any:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # Some sites wrap JSON-LD in HTML comments or trailing commas.
        cleaned = re.sub(r"^$", "", raw).strip()
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            return None


def _agent_name_from(value: Any) -> str:
    """Pull a person-like name from a schema.org agent/seller node.

    Accepts either a string (`"author": "Jean Dupont"`) or a dict with
    an explicit `@type` of RealEstateAgent / Person, or a dict that
    simply carries `name` (many CMSes omit @type for agents).
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        node_type = value.get("@type") or value.get("type") or ""
        node_type_l = (
            node_type if isinstance(node_type, str) else ""
        ).lower()
        if node_type_l and node_type_l not in _AGENT_TYPES:
            # Organisation/LocalBusiness names are agency-level, not agent-level.
            return ""
        name = value.get("name")
        if isinstance(name, str):
            return name.strip()
    if isinstance(value, list):
        for item in value:
            picked = _agent_name_from(item)
            if picked:
                return picked
    return ""


def _walk(node: Any, out: dict[str, Any]) -> None:
    if isinstance(node, dict):
        node_type = node.get("@type") or node.get("type") or ""
        node_type_l = (node_type if isinstance(node_type, str) else "").lower()

        if node_type_l in _LISTING_TYPES:
            _harvest_listing(node, out)

        for key, value in node.items():
            kl = str(key).lower()
            if kl == "address":
                _harvest_address(value, out)
            elif kl == "geo" and isinstance(value, dict):
                lat = value.get("latitude") or value.get("lat")
                lng = value.get("longitude") or value.get("lng")
                if lat and lng:
                    out.setdefault("coordinates", f"{lat}, {lng}")
            elif kl in _PHONE_KEYS and isinstance(value, str):
                out.setdefault("phone", value)
            elif kl in _DPE_KEYS and isinstance(value, str):
                out.setdefault("dpe", value)
            elif kl in _REF_KEYS and isinstance(value, str):
                out.setdefault("reference_id", value)
            elif kl in ("name",) and isinstance(value, str):
                out.setdefault("name", value)
            elif kl in ("description",) and isinstance(value, str):
                out.setdefault("description", value)
            elif kl in ("url", "@id") and isinstance(value, str):
                out.setdefault("url", value)
            elif kl in _AGENT_PARENT_KEYS:
                # `offers.seller`, `author`, etc. carry the agent.
                # We *also* still recurse so any nested fields surface.
                if "agent_name" not in out:
                    candidate = _agent_name_from(value)
                    if candidate:
                        out["agent_name"] = candidate
                if isinstance(value, (dict, list)):
                    _walk(value, out)
            elif isinstance(value, (dict, list)):
                _walk(value, out)

        # `RealEstateAgent` may sit at the top of its own JSON-LD block.
        if node_type_l in _AGENT_TYPES and "agent_name" not in out:
            name = node.get("name")
            if isinstance(name, str) and name.strip():
                out["agent_name"] = name.strip()
    elif isinstance(node, list):
        for item in node:
            _walk(item, out)


def _harvest_listing(node: dict[str, Any], out: dict[str, Any]) -> None:
    offers = node.get("offers")
    if isinstance(offers, dict):
        for key in _PRICE_KEYS:
            value = offers.get(key)
            if value not in (None, ""):
                out.setdefault("price", str(value))
                break
    elif isinstance(offers, list):
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            for key in _PRICE_KEYS:
                value = offer.get(key)
                if value not in (None, ""):
                    out.setdefault("price", str(value))
                    break
            if "price" in out:
                break
    if "price" not in out:
        for key in _PRICE_KEYS:
            value = node.get(key)
            if value not in (None, ""):
                out.setdefault("price", str(value))
                break


def _harvest_address(addr: Any, out: dict[str, Any]) -> None:
    if isinstance(addr, dict):
        locality = addr.get("addressLocality") or addr.get("addresslocality") or ""
        postal = addr.get("postalCode") or addr.get("postalcode") or ""
        joined = f"{locality} {postal}".strip()
        if joined:
            out.setdefault("location", joined)
    elif isinstance(addr, str) and addr.strip():
        out.setdefault("location", addr.strip())


def extract_json_ld(html: str) -> dict[str, Any]:
    """Parse all JSON-LD blocks and return a flat normalized dict."""
    out: dict[str, Any] = {}
    for raw in _iter_scripts(html):
        parsed = _safe_load(raw)
        if parsed is not None:
            _walk(parsed, out)
    return out

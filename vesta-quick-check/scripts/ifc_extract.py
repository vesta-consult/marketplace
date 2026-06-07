#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["ifcopenshell>=0.8"]
# ///
"""IFC → draft-Payload für den Vesta Quick-Check.

Zieht Bauteile (Wände, Decken, Dächer) mit Fläche und Materialschichten
(Material-Name, Schichtdicke, optional Rohdichte) aus einem IFC-Modell.

Nicht eindeutig extrahierbare Werte werden mit `null` markiert (statt geraten)
→ fließt ins Gap-Feedback des Claude-Code-Skills.

CLI:
  python ifc_extract.py modell.ifc            # gibt draft_akte.json auf stdout
  python ifc_extract.py modell.ifc -o akte.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Stück-Bauteile (Fenster, Türen): kein Schichtaufbau, Menge = Stückzahl.
PIECE_TYPES = ("IfcWindow", "IfcDoor")

# Bauteiltypen, die für die LCA relevant sind (Hüllfläche + tragend + Stück).
ELEMENT_TYPES = (
    "IfcWall",
    "IfcWallStandardCase",
    "IfcSlab",
    "IfcRoof",
    "IfcCovering",
    *PIECE_TYPES,
)


def _material_name(element: Any) -> str | None:
    """Liefert den Material-/Konstituenten-Namen eines Elements, sonst None."""
    try:
        import ifcopenshell.util.element as ue

        mat = ue.get_material(element, should_inherit=True)
    except Exception:  # noqa: BLE001
        return None
    if mat is None:
        return None
    name = getattr(mat, "Name", None)
    return str(name) if name else None


def _piece_component(element: Any, etype: str) -> dict[str, Any]:
    """Baut ein Stück-Bauteil (Fenster/Tür): 1 Layer, unit_basis=piece, Menge 1.

    Fenster-/Tür-EPDs der ÖkobauDat haben die Bezugseinheit „Stück". Ohne
    Material-Treffer fällt der Layer-Name auf den Bauteilnamen zurück, den der
    Agent dann via `match_material(..., unit_basis="piece")` auflöst.
    """
    name = element.Name or f"{etype} #{element.id()}"
    material = _material_name(element) or name
    return {
        "name": name,
        "area_m2": None,  # Stück, nicht Fläche
        "layers": [
            {
                "material": material,
                "quantity": 1,
                "unit_basis": "piece",
                "density": None,
            }
        ],
        "_ifc_type": etype,
    }


def _area_from_quantities(element: Any) -> float | None:
    """Liest eine Netto-/Bruttofläche aus IfcElementQuantity-Quantity-Sets."""
    try:
        import ifcopenshell.util.element as ue

        psets = ue.get_psets(element, qtos_only=True)
    except Exception:  # noqa: BLE001
        return None
    # Bevorzugte Quantity-Namen in absteigender Priorität.
    prefer = (
        "NetSideArea",
        "GrossSideArea",
        "NetArea",
        "GrossArea",
        "NetFootprintArea",
    )
    for qset in psets.values():
        for name in prefer:
            val = qset.get(name)
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
    return None


def _density_from_material(material: Any) -> float | None:
    """Versucht MassDensity aus den Material-Psets zu lesen."""
    try:
        import ifcopenshell.util.element as ue

        psets = ue.get_psets(material)
    except Exception:  # noqa: BLE001
        return None
    for pset in psets.values():
        val = pset.get("MassDensity")
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return None


def _layers_from_element(element: Any) -> list[dict[str, Any]]:
    """Extrahiert Materialschichten via ifcopenshell material-util."""
    import ifcopenshell.util.element as ue

    mat = ue.get_material(element, should_inherit=True)
    layers: list[dict[str, Any]] = []
    if mat is None:
        return layers
    # MaterialLayerSetUsage → ForLayerSet, oder direkt MaterialLayerSet.
    layer_set = None
    if mat.is_a("IfcMaterialLayerSetUsage"):
        layer_set = mat.ForLayerSet
    elif mat.is_a("IfcMaterialLayerSet"):
        layer_set = mat
    if layer_set is not None:
        for ml in layer_set.MaterialLayers or []:
            material_name = (
                ml.Material.Name if ml.Material and ml.Material.Name else None
            )
            thickness = float(ml.LayerThickness) if ml.LayerThickness else None
            layer: dict[str, Any] = {
                "material": material_name,
                "quantity": thickness,
            }
            if ml.Material is not None:
                dens = _density_from_material(ml.Material)
                if dens is not None:
                    layer["density"] = dens
            layers.append(layer)
    elif mat.is_a("IfcMaterial"):
        layers.append({"material": mat.Name or None, "quantity": None})
    return layers


def extract_components(ifc_path: str) -> list[dict[str, Any]]:
    """Öffnet das IFC und liefert eine Liste von draft-components."""
    import ifcopenshell

    model = ifcopenshell.open(ifc_path)
    components: list[dict[str, Any]] = []
    for etype in ELEMENT_TYPES:
        for element in model.by_type(etype):
            if etype in PIECE_TYPES:
                components.append(_piece_component(element, etype))
                continue
            layers = _layers_from_element(element)
            if not layers:
                continue  # ohne Materialschichten für LCA wertlos
            components.append(
                {
                    "name": element.Name or f"{etype} #{element.id()}",
                    "area_m2": _area_from_quantities(element),
                    "layers": layers,
                    "_ifc_type": etype,
                }
            )
    return components


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IFC → draft-Payload")
    parser.add_argument("ifc", help="Pfad zur .ifc-Datei")
    parser.add_argument("-o", "--out", help="Ausgabedatei (Default: stdout)")
    args = parser.parse_args(argv)

    components = extract_components(args.ifc)
    draft = {
        "name": None,
        "nfa_m2": None,
        "rsp_years": None,
        "components": components,
        "operational": [],
        "_hinweis": "Felder mit null muss der Agent aus Doc-Dateien füllen "
        "(nfa_m2, rsp_years, operational, fehlende area_m2/material).",
    }
    text = json.dumps(draft, ensure_ascii=False, indent=2)
    if args.out:
        from pathlib import Path

        Path(args.out).write_text(text, encoding="utf-8")
        print(
            f"draft geschrieben: {args.out} ({len(components)} Bauteile)",
            file=sys.stderr,
        )
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

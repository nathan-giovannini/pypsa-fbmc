"""Loading and validation of config.yaml (the single place for user input)."""

import re
from pathlib import Path

import yaml

MODES = ("relative", "absolute")
KINDS = ("static", "timeseries")
SELECTOR_KEYS = {"names", "carrier", "countries", "query"}
TARGET_KEYS = {"component", "attribute", "kind"}


def slugify(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    return validate_config(cfg)


def validate_config(cfg):
    for key in ("study", "network", "perturbations"):
        if key not in cfg:
            raise ValueError(f"config is missing required key '{key}'")
    cfg.setdefault("country_bus_prefix_length", 2)
    cfg.setdefault("voll", 3000)
    cfg.setdefault("baseline", {})
    cfg.setdefault("solver", {"name": "highs", "options": {}})
    cfg.setdefault("tornado_metrics", ["welfare_shift"])
    cfg.setdefault("welfare_plots", [])
    names = set()
    for p in cfg["perturbations"]:
        validate_perturbation(p)
        if p["name"] in names:
            raise ValueError(f"duplicate perturbation name '{p['name']}'")
        names.add(p["name"])
    return cfg


def validate_perturbation(p):
    for key in ("name", "target", "mode"):
        if key not in p:
            raise ValueError(f"perturbation {p.get('name', p)} is missing '{key}'")
    target = p["target"]
    missing = {"component", "attribute", "kind"} - set(target)
    if missing:
        raise ValueError(f"perturbation '{p['name']}': target is missing {sorted(missing)}")
    if set(target) - TARGET_KEYS:
        raise ValueError(f"perturbation '{p['name']}': unknown target keys {sorted(set(target) - TARGET_KEYS)}")
    if target["kind"] not in KINDS:
        raise ValueError(f"perturbation '{p['name']}': target.kind must be one of {KINDS}")
    if p["mode"] not in MODES:
        raise ValueError(f"perturbation '{p['name']}': mode must be one of {MODES}")
    if p.get("up") is None and p.get("down") is None:
        raise ValueError(f"perturbation '{p['name']}': specify at least one of 'up' or 'down'")
    for d in ("up", "down"):
        if p.get(d) is not None and p[d] < 0:
            raise ValueError(f"perturbation '{p['name']}': '{d}' must be >= 0 (the sign comes from the direction)")
    unknown = set(p.get("selector") or {}) - SELECTOR_KEYS
    if unknown:
        raise ValueError(f"perturbation '{p['name']}': unknown selector keys {sorted(unknown)}")
    if p.get("per_country") and not (p.get("selector") or {}).get("countries"):
        raise ValueError(f"perturbation '{p['name']}': per_country needs selector.countries")


def expand_cases(cfg):
    """
    Expand the configured perturbations into one case per
    (perturbation, [country], direction). Directions without a magnitude
    are not run. Returns {case_id: case_spec}; case ids are filesystem safe.
    """
    cases = {}
    for p in cfg["perturbations"]:
        selector = dict(p.get("selector") or {})
        if p.get("per_country"):
            variants = [(f"{p['name']} - {c}", {**selector, "countries": [c]}) for c in selector["countries"]]
        else:
            variants = [(p["name"], selector)]
        for label, sel in variants:
            for direction in ("down", "up"):
                magnitude = p.get(direction)
                if magnitude is None:
                    continue
                case_id = f"{slugify(label)}__{direction}"
                if case_id in cases:
                    raise ValueError(f"case id collision for '{label}' [{direction}]")
                cases[case_id] = {
                    "parameter": label,
                    "direction": direction,
                    "target": dict(p["target"]),
                    "selector": sel,
                    "mode": p["mode"],
                    "magnitude": magnitude,
                }
    return cases


def resolve_path(path, base):
    path = Path(path)
    return path if path.is_absolute() else Path(base) / path

"""Builds the Nav2 parameter file: installed nav2_bringup defaults + our overrides (applied in order).

Done at launch time so the file matches the installed Nav2 version (parameter names
change between releases). Keys that don't exist in that version are ignored by Nav2.
"""
import yaml


REPLACE = '__replace__'


def deep_merge(base, over):
    """Recursive merge. A mapping containing  __replace__: true  replaces the default subtree
    instead of being merged into it (e.g. switching a controller plugin drops the old plugin's keys)."""
    for key, val in over.items():
        if isinstance(val, dict) and val.get(REPLACE):
            base[key] = deep_merge({}, {k: v for k, v in val.items() if k != REPLACE})
        elif isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def build(default_path, overrides, output_path):
    """overrides: one YAML path or a list of paths, later files win."""
    with open(default_path) as f:
        params = yaml.safe_load(f)
    for path in [overrides] if isinstance(overrides, str) else overrides:
        with open(path) as f:
            deep_merge(params, yaml.safe_load(f) or {})
    with open(output_path, 'w') as f:
        yaml.safe_dump(params, f, sort_keys=False)
    return output_path

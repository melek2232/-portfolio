"""Builds the Nav2 parameter file: installed nav2_bringup defaults + our overrides.

Done at launch time so the file matches the installed Nav2 version (parameter names
change between releases). Keys that don't exist in that version are ignored by Nav2.
"""
import yaml


def deep_merge(base, over):
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def build(default_path, overrides_path, output_path):
    with open(default_path) as f:
        params = yaml.safe_load(f)
    with open(overrides_path) as f:
        overrides = yaml.safe_load(f) or {}
    deep_merge(params, overrides)
    with open(output_path, 'w') as f:
        yaml.safe_dump(params, f, sort_keys=False)
    return output_path

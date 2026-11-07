"""Pure inventory guard for the current two-part case-specific binding policy."""


def validate_parts(config, mesh_names):
    parts = config.get('parts', [])
    if not isinstance(parts, list) or any(not isinstance(p, str) for p in parts):
        raise ValueError('parts must be an ordered list of mesh names')
    if len(parts) != len(set(parts)):
        raise ValueError('Duplicate rig parts')
    missing = set(mesh_names) - set(parts)
    absent = set(parts) - set(mesh_names)
    if missing or absent:
        raise ValueError(f'Rig inventory mismatch: unlisted meshes={sorted(missing)}; '
                         f'absent meshes={sorted(absent)}. Never omit shoes or other parts.')
    if len(parts) != 2:
        raise ValueError('Current binding policy supports body + clothing only; '
                         'implement and review explicit shoe/extra-part binding before rigging this case.')
    return parts

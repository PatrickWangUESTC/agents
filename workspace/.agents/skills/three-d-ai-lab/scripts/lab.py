#!/usr/bin/env python3
"""Checkpointed Blender execution. Agent writes operations and reviews; no hidden LLM."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


@contextmanager
def lock(root):
    path = root / '.lock'
    path.mkdir()  # Single writer; fail rather than race.
    try:
        yield
    finally:
        path.rmdir()


def revision(root, name):
    if not re.fullmatch(r'r\d{4}', name):
        raise ValueError('Invalid revision ID')
    return root / 'revisions' / name


def intact(folder):
    record = read(folder / 'receipt.json')
    for name, expected in record['files'].items():
        path = folder / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'Stale revision evidence: {path}')
    return record


def session(root):
    state = read(root / 'session.json')
    if digest(root / 'case.json') != state['case_sha256']:
        raise ValueError('Case changed; create a new Lab branch')
    if state.get('views_sha256') and digest(root / 'views.json') != state['views_sha256']:
        raise ValueError('Fixed views changed; create a new Lab branch')
    return state, read(root / 'case.json')


def sources_unchanged(case):
    for asset in case['assets'] + case.get('references', []):
        if not Path(asset['path']).is_file() or digest(asset['path']) != asset['sha256']:
            raise ValueError('Input changed: ' + asset['path'])


def run_revision(root, state, case, script=None, diagnosis=None, parent=None, timeout=600):
    sources_unchanged(case)
    index = len(list((root / 'revisions').glob('r*')))
    name = f'r{index:04d}'
    out = revision(root, name)
    source = None
    if parent:
        base = revision(root, parent)
        receipt = intact(base)
        if receipt['status'] != 'produced':
            raise ValueError('Parent did not produce a valid checkpoint')
        source = str(base / 'scene.blend')
    out.mkdir()
    worker = Path(__file__).with_name('worker.py')
    shutil.copy2(worker, out / 'worker.py')
    shutil.copy2(Path(__file__).with_name('geometry_checks.py'), out / 'geometry_checks.py')
    shutil.copy2(Path(__file__), out / 'lab.py')
    if script:
        shutil.copy2(script, out / 'operation.py')
        shutil.copy2(diagnosis, out / 'diagnosis.md')
    request = {'case': case, 'parent': source, 'out': str(out),
               'views': read(root / 'views.json') if (root / 'views.json').exists() else None}
    write(out / 'request.json', request)
    record = {'revision': name, 'parent': parent, 'status': 'running',
              'started': time.time(), 'acceptance': 'not_run', 'files': {}}
    write(out / 'receipt.json', record)
    command = [state['blender'], '--background', '--factory-startup',
               '--python-exit-code', '1', '--python', str(out / 'worker.py'),
               '--', str(out / 'request.json')]
    try:
        with (out / 'execution.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                           timeout=timeout, check=True)
        # Native checkpoint must survive a separate Blender process.
        with (out / 'readback.log').open('w') as log:
            subprocess.run(command + ['--readback'], stdout=log,
                           stderr=subprocess.STDOUT, timeout=timeout, check=True)
        sources_unchanged(case)
        before = read(revision(root, 'r0000') / 'inventory.json')
        after = read(out / 'inventory.json')
        checks = {}
        for obj, fields in case.get('protected', {}).items():
            for field in fields:
                old = before['objects'].get(obj, {}).get(field)
                new = after['objects'].get(obj, {}).get(field)
                checks[obj + ':' + field] = 'pass' if old is not None and old == new else 'fail'
        checks['finite_geometry'] = 'pass' if after['finite'] else 'fail'
        checks['native_readback'] = 'pass' if after == read(out / 'readback.json') else 'fail'
        if case.get('geometry_checks'):
            checks['static_surface_crossings'] = read(out / 'geometry-checks.json')['status']
            checks['static_surface_readback'] = ('pass' if read(out / 'geometry-checks.json') == read(out / 'geometry-readback.json') else 'fail')
        write(out / 'checks.json', checks)
        record['status'] = 'produced'
        if not (root / 'views.json').exists():
            shutil.copy2(out / 'views.json', root / 'views.json')
        state['views_sha256'] = digest(root / 'views.json')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        record.update(status='failed', error=str(exc))
    record['finished'] = time.time()
    record['files'] = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*'))
                       if p.is_file() and p.name != 'receipt.json'}
    write(out / 'receipt.json', record)
    if state['selected'] is None and record['status'] == 'produced':
        state['selected'] = name  # Baseline checkpoint, NOT accepted asset.
    state['latest'] = name
    write(root / 'session.json', state)
    return record


def review(root, name, review_file):
    state, case = session(root)
    out = revision(root, name)
    receipt = intact(out)
    if (out / 'review.json').exists():
        raise ValueError('Review exists; keep history and make a new revision')
    report = read(review_file)
    if report.get('revision') != name or report.get('decision') not in ('accept', 'reject'):
        raise ValueError('Review must name this revision and accept/reject')
    if report.get('scene_sha256') != receipt['files'].get('scene.blend'):
        raise ValueError('Review targets a different scene')
    if not report.get('reviewer') or not report.get('findings'):
        raise ValueError('Record reviewer and findings')
    if report['decision'] == 'accept':
        if receipt['status'] != 'produced' or any(x != 'pass' for x in read(out / 'checks.json').values()):
            raise ValueError('Execution or protected-property checks failed')
        for key in case['required_checks']:
            check = report.get('checks', {}).get(key, {})
            if check.get('status') != 'pass' or not check.get('evidence'):
                raise ValueError('Missing passing evidence for ' + key)
            for evidence in check['evidence']:
                if evidence not in receipt['files']:
                    raise ValueError('Evidence must belong to this revision: ' + evidence)
        state['selected'] = name
    write(out / 'review.json', report)
    receipt['acceptance'] = 'accepted' if report['decision'] == 'accept' else 'rejected'
    receipt['files']['review.json'] = digest(out / 'review.json')
    write(out / 'receipt.json', receipt)
    write(root / 'session.json', state)
    return {'revision': name, 'acceptance': receipt['acceptance'], 'selected': state['selected']}


def observe(root, revision_id=None):
    """A file-bound observation packet; the calling agent must inspect its images."""
    state, case = session(root)
    sources_unchanged(case)
    chosen = revision_id or state['selected']
    folder = revision(root, chosen)
    record = intact(folder)
    if record['status'] != 'produced':
        raise ValueError('Observe a produced checkpoint; failure logs are in latest_feedback')
    selected = state['selected']
    latest = state['latest']
    latest_folder = revision(root, latest)
    latest_record = intact(latest_folder)
    return {'schema_version': 1, 'session': str(root.resolve()),
            'case_sha256': state['case_sha256'], 'observed_revision': chosen,
            'selected_at_observation': selected, 'scene_sha256': record['files']['scene.blend'],
            'receipt_sha256': digest(folder / 'receipt.json'),
            'inventory': read(folder / 'inventory.json'),
            'checks': read(folder / 'checks.json'),
            'geometry_checks': read(folder / 'geometry-checks.json') if (folder / 'geometry-checks.json').exists() else {'status': 'not_run'},
            'images': [{'path': str(folder / name), 'sha256': value}
                       for name,value in record['files'].items() if name.lower().endswith('.png')],
            'latest_feedback': {'revision': latest, 'status': latest_record['status'],
                                'acceptance': latest_record['acceptance'],
                                'error': latest_record.get('error'),
                                'log': str(latest_folder / 'execution.log'),
                                'review': read(latest_folder / 'review.json') if (latest_folder / 'review.json').exists() else None},
            'required_checks': case['required_checks'],
            'instruction': 'Inspect actual images and measurements; propose one bounded edit. A packet is not a visual review.'}


def act(root, decision_path, timeout=600):
    decision_path = Path(decision_path).resolve()
    decision = read(decision_path)
    packet_path = (decision_path.parent / decision['observation']).resolve()
    if digest(packet_path) != decision['observation_sha256']:
        raise ValueError('Observation packet changed')
    packet = read(packet_path)
    state, case = session(root)
    if packet['session'] != str(root.resolve()) or packet['case_sha256'] != state['case_sha256']:
        raise ValueError('Observation belongs to another session/case')
    if packet['selected_at_observation'] != state['selected']:
        raise ValueError('Selected checkpoint changed; observe again')
    base = revision(root, packet['observed_revision'])
    receipt = intact(base)
    if (receipt['files'].get('scene.blend') != packet['scene_sha256']
            or digest(base / 'receipt.json') != packet['receipt_sha256']):
        raise ValueError('Observed revision changed; observe again')
    for key in ('diagnosis', 'operation', 'edit_scope', 'expected_improvement', 'stop_condition'):
        if not isinstance(decision.get(key),str) or not decision[key].strip():
            raise ValueError('Decision requires ' + key)
    reviewed = decision.get('viewed_images', [])
    available = {r['path']: r['sha256'] for r in packet['images']}
    if not reviewed or any(name not in available or digest(name)!=available[name] for name in reviewed):
        raise ValueError('Decision must identify current observed images; viewing is agent responsibility')
    script = (decision_path.parent / decision['operation']).resolve()
    if digest(script) != decision.get('operation_sha256'):
        raise ValueError('Operation changed')
    # Immutable action input directory; acts retain their exact observation and diagnosis.
    action_dir = root / 'actions' / ('a' + str(time.time_ns()))
    action_dir.mkdir(parents=True)
    shutil.copy2(packet_path, action_dir / 'observation.json')
    shutil.copy2(decision_path, action_dir / 'decision.json')
    shutil.copy2(script, action_dir / 'operation.py')
    (action_dir / 'diagnosis.md').write_text(decision['diagnosis'] + '\nScope: ' + decision['edit_scope']
        + '\nExpected: ' + decision['expected_improvement'] + '\nStop: ' + decision['stop_condition'] + '\n')
    return run_revision(root, state, case, action_dir / 'operation.py', action_dir / 'diagnosis.md',
                        packet['observed_revision'], timeout)


def validate_geometry_spec(case):
    spec = case.get('geometry_checks')
    if spec is None:
        return
    if not isinstance(spec,dict) or set(spec) != {'surface_pairs'} or not isinstance(spec['surface_pairs'],list) or not spec['surface_pairs']:
        raise ValueError('geometry_checks requires nonempty surface_pairs')
    for pair in spec['surface_pairs']:
        names = pair.get('objects')
        if (not isinstance(names,list) or len(names)!=2 or not all(isinstance(n,str) and n for n in names)
                or names[0]==names[1] or type(pair.get('max_crossings',0)) is not int or pair.get('max_crossings',0)<0):
            raise ValueError('Each surface pair needs two distinct names and nonnegative integer max_crossings')
        if 'region' in pair:
            region=pair['region']
            if (not isinstance(region,dict) or set(region)!={'min','max'}
                    or any(not isinstance(region[k],list) or len(region[k])!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in region[k]) for k in ('min','max'))
                    or any(a>=b for a,b in zip(region['min'],region['max']))):
                raise ValueError('Region needs finite increasing min/max bounds')


def initialize(path, root, blender, timeout):
    case = read(path)
    validate_geometry_spec(case)
    for field in ('goal', 'workflow', 'required_checks'):
        if not case.get(field):
            raise ValueError('Case needs ' + field)
    if not isinstance(case['required_checks'], list) or not all(isinstance(x, str) and x for x in case['required_checks']):
        raise ValueError('required_checks must be a nonempty list of names')
    if not case.get('assets'):
        raise ValueError('Supply existing assets')
    for asset in case['assets'] + case.get('references', []):
        p = (Path(path).resolve().parent / asset['path']).resolve()
        asset.update(path=str(p), sha256=digest(p))
    for asset in case['assets']:
        if Path(asset['path']).suffix.lower() not in ('.blend', '.glb', '.gltf', '.obj'):
            raise ValueError('Unsupported asset format')
    if any(Path(a['path']).suffix.lower() == '.blend' for a in case['assets']) and len(case['assets']) != 1:
        raise ValueError('Use one .blend scene or multiple mesh exports')
    supported = {'geometry', 'uv', 'transform', 'weights', 'morphs', 'rig'}
    for fields in case.get('protected', {}).values():
        if not isinstance(fields, list) or not fields or set(fields) - supported:
            raise ValueError('Unknown or empty protected property list')
    executable = shutil.which(blender) if blender else None
    if not executable:
        raise ValueError('Supply an installed Blender executable')
    root.mkdir(parents=True, exist_ok=False)
    (root / 'revisions').mkdir()
    write(root / 'case.json', case)
    state = {'schema_version': 1, 'case_sha256': digest(root / 'case.json'),
             'blender': executable, 'selected': None, 'latest': None}
    write(root / 'session.json', state)
    with lock(root):
        return run_revision(root, state, case, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('case', type=Path)
    init.add_argument('--out', type=Path, required=True)
    init.add_argument('--blender', default=shutil.which('blender'))
    init.add_argument('--timeout', type=int, default=600)
    run = sub.add_parser('run')
    run.add_argument('session', type=Path)
    run.add_argument('--script', type=Path, required=True)
    run.add_argument('--diagnosis', type=Path, required=True)
    run.add_argument('--parent')
    run.add_argument('--timeout', type=int, default=600)
    rev = sub.add_parser('review')
    rev.add_argument('session', type=Path)
    rev.add_argument('revision')
    rev.add_argument('--file', type=Path, required=True)
    status = sub.add_parser('status')
    status.add_argument('session', type=Path)
    obs = sub.add_parser('observe')
    obs.add_argument('session', type=Path)
    obs.add_argument('--revision')
    obs.add_argument('--out', type=Path, required=True)
    action = sub.add_parser('act')
    action.add_argument('session', type=Path)
    action.add_argument('--decision', type=Path, required=True)
    action.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            result = initialize(args.case, args.out.resolve(), args.blender, args.timeout)
        else:
            root = args.session.resolve()
            with lock(root):
                state, case = session(root)
                if args.command == 'run':
                    if not args.script.read_text().strip() or not args.diagnosis.read_text().strip():
                        raise ValueError('Operation and diagnosis must be nonempty')
                    result = run_revision(root, state, case, args.script, args.diagnosis,
                                          args.parent or state['selected'], args.timeout)
                elif args.command == 'observe':
                    if args.out.exists():
                        raise ValueError('Observation output exists; keep history')
                    result = observe(root, args.revision)
                    write(args.out, result)
                elif args.command == 'act':
                    result = act(root, args.decision, args.timeout)
                elif args.command == 'review':
                    result = review(root, args.revision, args.file)
                else:
                    result = {**state, 'revisions': []}
                    for out in sorted((root / 'revisions').iterdir()):
                        try:
                            row = intact(out)
                            result['revisions'].append({k: row[k] for k in ('revision', 'status', 'acceptance')})
                        except (ValueError, OSError) as exc:
                            result['revisions'].append({'revision': out.name, 'status': 'stale', 'error': str(exc)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('status') == 'failed' else 0
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())

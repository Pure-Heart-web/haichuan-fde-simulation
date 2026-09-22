"""Portable, hash-bound evidence manifests and synthetic shadow metrics."""
import hashlib
import json
from pathlib import Path
from statistics import median


def shadow_metrics(observations):
    rows = observations['observations']
    actions = {name: sum(row['human_action'] == name for row in rows)
               for name in ('accept', 'edit', 'escalate', 'abstain')}
    return {'mode': 'synthetic_shadow_observation', 'case_count': len(rows),
            'user_count': len({row['user_id'] for row in rows}),
            'actions': actions,
            'median_human_minutes': median(row['human_minutes'] for row in rows),
            'evidence_disagreement_count': sum(row['evidence_disagreement'] for row in rows),
            'unsafe_suggestion_count': sum(row['unsafe_suggestion'] for row in rows),
            'external_customer_actions': 0, 'actual_customer_users': 0}


def evidence_manifest(root, paths, metadata):
    root = Path(root).resolve()
    artifacts = []
    for path in sorted(Path(item).resolve() for item in paths):
        relative = path.relative_to(root).as_posix()
        artifacts.append({'path': relative,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size})
    controlled = {'version': 'stage14-evidence-v1', 'metadata': metadata,
                  'artifacts': artifacts}
    controlled['bundle_sha256'] = hashlib.sha256(json.dumps(controlled,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return controlled


def verify_manifest(root, manifest):
    root = Path(root).resolve()
    controlled = {key: value for key, value in manifest.items() if key != 'bundle_sha256'}
    expected = hashlib.sha256(json.dumps(controlled, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    if expected != manifest.get('bundle_sha256'):
        return False
    return all((root / item['path']).is_file() and
        hashlib.sha256((root / item['path']).read_bytes()).hexdigest() == item['sha256']
        for item in manifest['artifacts'])

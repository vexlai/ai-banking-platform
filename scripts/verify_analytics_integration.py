"""Read-only integrity and offline parity checks; never reruns analytical notebooks."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'artifacts/integration/analytics_import_manifest.json').read_text())
    for item in manifest['files']:
        assert sha(ROOT / item['destination']) == item['sha256'], item['destination']
        if args.source:
            assert sha(args.source / item['source']) == item['sha256'], item['source']
    out = ROOT / 'artifacts/evaluation'
    lock = json.loads((out / 'baseline_lock.json').read_text())
    for path, expected in lock['code_sha256'].items():
        assert sha(ROOT / path) == expected, path
    assert sha(out / 'dispute_intake_eval.jsonl') == lock['dataset_sha256']
    assert sha(out / 'retrieval_fixtures.jsonl') == lock['retrieval_fixtures_sha256']
    from src.evaluation.baseline_intake_parser import extract
    from src.evaluation.metrics import extraction_metrics, retrieval_metrics
    cases = [json.loads(line) for line in (out / 'dispute_intake_eval.jsonl').read_text().splitlines()]
    saved_predictions = [json.loads(line) for line in (out / 'baseline_predictions.jsonl').read_text().splitlines()]
    predictions = [extract(c['user_utterance']) for c in cases]
    assert predictions == [p['prediction'] for p in saved_predictions]
    saved = json.loads((out / 'baseline_metrics.json').read_text())
    groups = {s: {c['group_id'] for c in cases if c['split'] == s} for s in ('development', 'test')}
    assert groups['development'].isdisjoint(groups['test'])
    for split in groups:
        for language in ('all', 'es', 'pt'):
            idx = [i for i, c in enumerate(cases) if c['split'] == split and
                   (language == 'all' or c['language'] == language)]
            actual = extraction_metrics([cases[i] for i in idx], [predictions[i] for i in idx])
            assert all(saved['extraction'][f'{split}/{language}'][k] == v for k, v in actual.items())
    fixtures = [json.loads(line) for line in (out / 'retrieval_fixtures.jsonl').read_text().splitlines()]
    for split in groups:
        _, metrics = retrieval_metrics([f for f in fixtures if f['split'] == split])
        assert metrics == saved['retrieval'][split]
    import nbformat
    for path in (ROOT / 'notebooks').glob('*.ipynb'):
        nbformat.validate(nbformat.read(path, as_version=4))
    raw_checked = 0
    if (ROOT / 'dataset').is_dir():
        raw = json.loads((ROOT / 'reports/profiling/source_manifest.json').read_text())
        for item in raw:
            assert (ROOT / item['path']).stat().st_size == item['bytes']
        raw_checked = len(raw)
    print(json.dumps({'status': 'PASS', 'imported_files_sha256_verified': len(manifest['files']),
                      'source_files_also_verified': args.source is not None,
                      'extraction_predictions_identical': len(cases),
                      'retrieval_fixtures_metrics_identical': len(fixtures),
                      'raw_files_size_checked': raw_checked,
                      'raw_content_rehashed': False, 'llm_calls': 0, 'analysis_rerun': False}, indent=2))


if __name__ == '__main__':
    main()

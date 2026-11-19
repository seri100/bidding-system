"""Reconstruct reviewed sources from private original files; never deploy or send."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    original = Path(args.original_dir).resolve()
    output = Path(args.output_dir).resolve()
    if output == original or output == Path('/home/pi/n_data') or output.exists():
        raise SystemExit('Use a new review directory; originals/production cannot be overwritten')
    edits = json.loads((source / 'patches/source_edits.json').read_text(encoding='utf-8'))
    prepared = {}
    for name, spec in edits.items():
        raw = (original / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec['original_sha256']:
            raise SystemExit('Original SHA256 mismatch: ' + name)
        lines = raw.decode('utf-8').splitlines(keepends=True)
        for start, end, replacement in reversed(spec['edits']):
            lines[start:end] = replacement
        result = ''.join(lines).encode('utf-8')
        if hashlib.sha256(result).hexdigest() != spec['new_sha256']:
            raise SystemExit('Reconstructed SHA256 mismatch: ' + name)
        prepared[name] = result
    output.mkdir(parents=True)
    for name, content in prepared.items():
        (output / name).write_bytes(content)
    for name in ('g2b_joint_region.py', 'joint_region_status.py', 'apply_update.py', 'manifest.json'):
        shutil.copyfile(source / name, output / name)
    print('Review sources prepared (no deployment/send): ' + str(output))


if __name__ == '__main__':
    main()

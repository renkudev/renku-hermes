#!/usr/bin/env python3
"""Prepare/publish a release; existing published assets are verified, never replaced."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from build import manifest

ROOT = Path(__file__).resolve().parents[1]
REPO = 'renkudev/renku-hermes'

def run(*args, capture=False):
    result = subprocess.run([str(a) for a in args], cwd=ROOT, check=True,
                            stdout=subprocess.PIPE if capture else None, text=True)
    return result.stdout.strip() if capture else None

def main():
    version = sys.argv[1]
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise RuntimeError('Expected canonical major.minor.patch version')
    head = run('git', 'rev-parse', 'HEAD', capture=True)
    releases = json.loads(run('gh', 'api', f'repos/{REPO}/releases', '--paginate', capture=True))
    existing = next((r for r in releases if r['tag_name'] == version), None)
    out = ROOT / 'dist'
    if existing:
        out.mkdir(exist_ok=True)
        run('gh', 'release', 'download', version, '--repo', REPO, '--dir', out)
    else:
        tags = run('git', 'ls-remote', '--tags', 'origin', f'refs/tags/{version}', capture=True)
        if tags:
            raise RuntimeError('Tag exists without release; inspect interrupted publication before resuming')
        run('python3', 'scripts/build.py', '--version', version)
    metadata = json.loads((out / 'release.json').read_text())
    if metadata['version'] != version:
        raise RuntimeError('Release identity mismatch')
    for name, expected in metadata['artifacts'].items():
        if name not in ('hermesvm.xcframework.zip', 'hermesc-macos-arm64.tar.gz'):
            raise RuntimeError('Unexpected release artifact')
        if hashlib.sha256((out / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Release artifact checksum mismatch: {name}')
    package = manifest(version, metadata['artifacts']['hermesvm.xcframework.zip'])
    if existing and not existing['draft']:
        run('git', 'fetch', 'origin', f'refs/tags/{version}:refs/tags/{version}')
        if run('git', 'show', f'{version}:Package.swift', capture=True) != package.strip():
            raise RuntimeError('Published package manifest mismatch')
        print('Published release verified; no mutation performed.')
        return
    # A retry may start from either build inputs or the already committed manifest.
    if metadata['sourceCommit'] != head:
        prior = ROOT / 'release.json'
        if not prior.exists() or json.loads(prior.read_text()) != metadata:
            raise RuntimeError('Draft came from different source; do not rebuild/replace its assets')
    if not existing:
        run('gh', 'release', 'create', version, '--repo', REPO, '--draft', '--target', head,
            '--title', f'renku-hermes {version}', '--notes',
            f'Pinned Hermes {metadata["revision"]}; HBC {metadata["hbcVersion"]}; macOS arm64 compiler and Apple arm64 runtime. See release.json for build provenance.',
            out / 'hermesvm.xcframework.zip', out / 'hermesc-macos-arm64.tar.gz', out / 'release.json')
    (ROOT / 'Package.swift').write_text(package)
    (ROOT / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    run('git', 'config', 'user.name', 'github-actions[bot]')
    run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    run('git', 'add', 'Package.swift', 'release.json')
    if run('git', 'diff', '--cached', '--name-only', capture=True):
        run('git', 'commit', '-m', f'Release {version}')
    release_commit = run('git', 'rev-parse', 'HEAD', capture=True)
    run('git', 'push', 'origin', 'HEAD:main')
    tag = run('git', 'ls-remote', '--tags', 'origin', f'refs/tags/{version}', capture=True)
    if tag and tag.split()[0] != release_commit:
        raise RuntimeError('Existing tag does not identify the release manifest commit')
    if not tag:
        run('git', 'tag', version, release_commit)
        run('git', 'push', 'origin', f'refs/tags/{version}')
    run('gh', 'release', 'edit', version, '--repo', REPO, '--draft=false', '--target', release_commit)
    print(f'Published {version} at {release_commit}; build source {metadata["sourceCommit"]}')

if __name__ == '__main__':
    main()

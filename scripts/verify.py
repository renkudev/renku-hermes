#!/usr/bin/env python3
"""Verify packaged public headers, linkage, bytecode, and unpatched async behavior."""
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    out = Path(sys.argv[1]).resolve()
    compiler = out / 'host/bin/hermesc'
    subprocess.run([compiler, '-version'], check=True)
    linked = subprocess.check_output(['otool', '-L', compiler], text=True)
    for line in linked.splitlines()[1:]:
        dependency = line.strip().split(' ')[0]
        if not dependency.startswith(('/usr/lib/', '/System/Library/')):
            raise RuntimeError(f'Compiler has non-system dependency: {dependency}')
    info = plistlib.loads((out / 'hermesvm.xcframework/Info.plist').read_bytes())
    assert {v['LibraryIdentifier'] for v in info['AvailableLibraries']} == {'ios-arm64', 'ios-arm64-simulator', 'macos-arm64'}
    framework = out / 'hermesvm.xcframework/macos-arm64'
    runner = out / 'hermes-run'
    subprocess.run(['xcrun', 'clang++', '-std=c++20', '-mmacosx-version-min=27.0',
                    '-F', framework, ROOT / 'tests/run.cpp', '-framework', 'hermesvm',
                    '-Wl,-rpath,' + str(framework), '-o', runner], check=True)
    hbc = out / 'async.hbc'
    subprocess.run([compiler, '-Xes6-block-scoping', '-O', '-emit-binary', '-out', hbc, ROOT / 'tests/async.js'], check=True)
    assert int.from_bytes(hbc.read_bytes()[8:12], 'little') == 99
    output = subprocess.check_output([runner, hbc], text=True)
    assert 'renku-hermes unpatched async and Intl passed' in output, output
    print(output)

if __name__ == '__main__':
    main()

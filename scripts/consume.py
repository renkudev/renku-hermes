#!/usr/bin/env python3
"""Anonymous release download and remote SwiftPM compile/run acceptance."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
version = sys.argv[1]
if not re.fullmatch(r'\d+\.\d+\.\d+', version):
    raise SystemExit('Expected major.minor.patch')
url = f'https://github.com/renkudev/renku-hermes/releases/download/{version}'
with tempfile.TemporaryDirectory(prefix='hermes-consumer-') as temp:
    folder = Path(temp)
    metadata = json.load(urllib.request.urlopen(url + '/release.json'))
    for name, expected in metadata['artifacts'].items():
        if name not in ('hermesvm.xcframework.zip', 'hermesc-macos-arm64.tar.gz'):
            raise RuntimeError('Unexpected artifact name')
        data = urllib.request.urlopen(url + '/' + name).read()
        assert hashlib.sha256(data).hexdigest() == expected
        (folder / name).write_bytes(data)
    (folder / 'Package.swift').write_text(f'''// swift-tools-version: 6.4
import PackageDescription
let package = Package(name: "Probe", platforms: [.macOS("27.0")],
    dependencies: [.package(url: "https://github.com/renkudev/renku-hermes.git", exact: "{version}")],
    targets: [.executableTarget(name: "Probe", dependencies: [.product(name: "hermesvm", package: "renku-hermes")], linkerSettings: [.unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path"])])],
    cxxLanguageStandard: .cxx20)
''')
    source = folder / 'Sources/Probe'
    source.mkdir(parents=True)
    (source / 'main.cpp').write_bytes((ROOT / 'tests/run.cpp').read_bytes())
    subprocess.run(['swift', 'build', '--package-path', folder], check=True)
    subprocess.run(['tar', '-xzf', folder / 'hermesc-macos-arm64.tar.gz', '-C', folder], check=True)
    hbc = folder / 'test.hbc'
    subprocess.run([folder / 'host/bin/hermesc', '-O', '-emit-binary', '-out', hbc, ROOT / 'tests/ownership.js'], check=True)
    bindir = subprocess.check_output(['swift', 'build', '--package-path', folder, '--show-bin-path'], text=True).strip()
    subprocess.run([Path(bindir) / 'Probe', hbc], check=True)
print('Anonymous release consumption passed')

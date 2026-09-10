#!/usr/bin/env python3
"""Build the pinned renku Hermes distribution on macOS arm64 with Xcode 27."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
ENV = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'DEVELOPER_DIR') if k in os.environ}

def run(*args, capture=False, cwd=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=ENV, check=True,
                            stdout=subprocess.PIPE if capture else None, text=True)
    return result.stdout.strip() if capture else None

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def manifest(version=None, checksum=None):
    target = (f'url: "https://github.com/renkudev/renku-hermes/releases/download/{version}/hermesvm.xcframework.zip", checksum: "{checksum}"'
              if version else 'path: "hermesvm.xcframework"')
    return f'''// swift-tools-version: 6.4
import PackageDescription
let package = Package(
    name: "renku-hermes",
    platforms: [.iOS("27.0"), .macOS("27.0")],
    products: [.library(name: "hermesvm", targets: ["hermesvm"])],
    targets: [.binaryTarget(name: "hermesvm", {target})]
)
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.0.0-local')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-local)?', args.version):
        parser.error('Expected a numeric major.minor.patch version')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.error('Builds require macOS arm64')
    recipe = json.loads((ROOT / 'recipe.json').read_text())
    xcode = run('xcodebuild', '-version', capture=True)
    if not xcode.startswith('Xcode 27.'):
        parser.error('Select Xcode 27 with DEVELOPER_DIR')
    build, out = ROOT / 'build', ROOT / 'dist'
    build.mkdir(exist_ok=True)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    source = build / 'source'
    if not source.exists():
        run('git', 'init', source)
        run('git', '-C', source, 'remote', 'add', 'origin', 'https://github.com/facebook/hermes.git')
        run('git', '-C', source, 'fetch', '--depth', '1', 'origin', recipe['revision'])
        run('git', '-C', source, 'checkout', '--detach', 'FETCH_HEAD')
    if run('git', '-C', source, 'rev-parse', 'HEAD', capture=True) != recipe['revision']:
        raise RuntimeError('Unexpected source revision; remove the owned build directory and retry')
    adaptation = recipe['adaptation']
    path = source / adaptation['path']
    original = run('git', '-C', source, 'show', f"HEAD:{adaptation['path']}", capture=True) + '\n'
    if hashlib.sha256(original.encode()).hexdigest() != adaptation['upstreamSha256']:
        raise RuntimeError('Pinned upstream Promise hash mismatch')
    anchor = '      this.promise = promise;'
    if original.count(anchor) != 1:
        raise RuntimeError('Promise adaptation anchor mismatch')
    adapted = original.replace(anchor, anchor + '''
      if (typeof globalThis.__renkuBindAsync === 'function') {
        this.onFulfilled = globalThis.__renkuBindAsync(this.onFulfilled);
        this.onRejected = globalThis.__renkuBindAsync(this.onRejected);
      }''')
    changed = run('git', '-C', source, 'diff', '--name-only', capture=True).splitlines()
    if changed not in ([], [adaptation['path']]) or run('git', '-C', source, 'ls-files', '--others', '--exclude-standard', capture=True):
        raise RuntimeError('Unexpected changes in owned upstream source')
    if path.read_text() not in (original, adapted):
        raise RuntimeError('Unexpected Promise source modifications')
    path.write_text(adapted)
    cc = run('xcrun', '--find', 'clang', capture=True)
    cxx = run('xcrun', '--find', 'clang++', capture=True)
    common = ['-G', 'Ninja', f'-DCMAKE_C_COMPILER={cc}', f'-DCMAKE_CXX_COMPILER={cxx}',
              '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=27.0',
              '-DHERMES_ENABLE_TEST_SUITE=OFF']
    host = build / 'host'
    run('cmake', '-S', source, '-B', host, *common, '-DCMAKE_BUILD_TYPE=Release')
    jobs = str(min(os.cpu_count() or 2, 6))
    run('cmake', '--build', host, '--target', 'hermesc', '-j', jobs)
    headers = build / 'headers'
    if headers.exists():
        shutil.rmtree(headers)
    (headers / 'hermes').mkdir(parents=True)
    shutil.copytree(source / 'public/hermes/Public', headers / 'hermes/Public')
    shutil.copytree(source / 'API/jsi/jsi', headers / 'jsi')
    shutil.copy2(source / 'API/hermes/hermes.h', headers / 'hermes/hermes.h')
    # Framework-qualified includes make public headers usable through SwiftPM's -F
    # search path without consumer-specific unsafe include flags.
    for p in headers.rglob('*'):
        if p.is_file():
            if p.suffix not in ('.h', '.inc'):
                p.unlink()
                continue
            p.write_text(re.sub(r'(#\s*include\s*)[<"]((?:hermes|jsi)/[^>"]+)[>"]',
                                r'\1<hermesvm/\2>', p.read_text()))
    frameworks = []
    options = ['-DCMAKE_BUILD_TYPE=MinSizeRel', '-DHERMES_ENABLE_DEBUGGER=OFF',
               '-DHERMES_ENABLE_INTL=ON', '-DHERMES_BUILD_APPLE_FRAMEWORK=ON',
               '-DHERMES_BUILD_SHARED_JSI=OFF', '-DHERMES_EXTRA_LINKER_FLAGS=']
    for target in ('iphoneos', 'iphonesimulator', 'macosx'):
        directory = build / target
        run('cmake', '-S', source, '-B', directory, *common, *options,
            f'-DHERMES_APPLE_TARGET_PLATFORM={target}',
            f'-DIMPORT_HOST_COMPILERS={host}/ImportHostCompilers.cmake')
        run('cmake', '--build', directory, '--target', 'hermesvm', '-j', jobs)
        framework = directory / 'lib/hermesvm.framework'
        contents = framework / 'Versions/1' if target == 'macosx' else framework
        for name in ('Headers', 'Modules'):
            if (contents / name).exists():
                shutil.rmtree(contents / name)
        shutil.copytree(headers, contents / 'Headers')
        (contents / 'Headers/hermesvm.h').write_text('#pragma once\n#include <hermesvm/hermes/hermes.h>\n')
        (contents / 'Modules').mkdir()
        (contents / 'Modules/module.modulemap').write_text('framework module hermesvm {\n  umbrella header "hermesvm.h"\n  requires cplusplus\n  export *\n}\n')
        resources = contents / 'Resources' if target == 'macosx' else contents
        shutil.copy2(ROOT / 'PrivacyInfo.xcprivacy', resources / 'PrivacyInfo.xcprivacy')
        shutil.copy2(source / 'LICENSE', resources / 'Hermes-LICENSE')
        if target == 'macosx':
            for name in ('Headers', 'Modules'):
                link = framework / name
                if not link.is_symlink():
                    link.symlink_to(f'Versions/Current/{name}')
        frameworks += ['-framework', str(framework)]
    run('xcodebuild', '-create-xcframework', *frameworks, '-output', out / 'hermesvm.xcframework')
    (out / 'host/bin').mkdir(parents=True)
    shutil.copy2(host / 'bin/hermesc', out / 'host/bin/hermesc')
    shutil.copy2(source / 'LICENSE', out / 'Hermes-LICENSE')
    (out / 'Package.swift').write_text(manifest())
    run('python3', ROOT / 'scripts/verify.py', out)
    run('ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', out / 'hermesvm.xcframework', out / 'hermesvm.xcframework.zip')
    with tarfile.open(out / 'hermesc-macos-arm64.tar.gz', 'w:gz') as archive:
        for name in ('host/bin/hermesc', 'Hermes-LICENSE'):
            archive.add(out / name, arcname=name)
    metadata = dict(recipe, version=args.version, sourceCommit=run('git', 'rev-parse', 'HEAD', capture=True, cwd=ROOT),
                    xcode=xcode, clang=run('xcrun', 'clang', '--version', capture=True),
                    sdks={sdk: run('xcrun', '--sdk', sdk, '--show-sdk-build-version', capture=True)
                          for sdk in ('iphoneos', 'iphonesimulator', 'macosx')},
                    runnerImage=os.environ.get('ImageVersion', 'local'),
                    artifacts={name: digest(out / name) for name in ('hermesvm.xcframework.zip', 'hermesc-macos-arm64.tar.gz')})
    (out / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # Inventory local output after verification; consumers recheck bytes before use.
    files = {}
    for base in ('host', 'hermesvm.xcframework'):
        for p in sorted((out / base).rglob('*')):
            if p.is_symlink():
                files[str(p.relative_to(out))] = {'link': os.readlink(p)}
            elif p.is_file():
                files[str(p.relative_to(out))] = {'sha256': digest(p)}
    (out / 'inventory.json').write_text(json.dumps(files, indent=2) + '\n')
    print(out)

if __name__ == '__main__':
    main()

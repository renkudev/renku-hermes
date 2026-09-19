#!/usr/bin/env python3
"""Build the pinned compiler and static Apple runtime. No publishing."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
SOURCE = BUILD / "hermes"
REVISION = (ROOT / "hermes-revision.txt").read_text().strip()


def run(*args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, cwd=ROOT)


def output(*args):
    return subprocess.check_output(list(map(str, args)), text=True, cwd=ROOT).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("Building requires an Apple Silicon Mac and Xcode 27.2.")
    if not output("xcrun", "xcodebuild", "-version").startswith("Xcode 27.2\n"):
        raise SystemExit("Select Xcode 27.2 with DEVELOPER_DIR before building.")
    for sdk in ("macosx", "iphoneos", "iphonesimulator"):
        if output("xcrun", "--sdk", sdk, "--show-sdk-version") != "27.2":
            raise SystemExit(f"Expected {sdk} SDK 27.2")
    if not SOURCE.exists():
        run("git", "init", SOURCE)
        run("git", "-C", SOURCE, "remote", "add", "origin", "https://github.com/facebook/hermes.git")
    if subprocess.run(["git", "-C", str(SOURCE), "cat-file", "-e", REVISION],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run("git", "-C", SOURCE, "fetch", "--depth", "1", "origin", REVISION)
    run("git", "-C", SOURCE, "checkout", "--detach", REVISION)
    if output("git", "-C", SOURCE, "status", "--porcelain"):
        raise SystemExit("Hermes source has local changes; refusing an unpinned build.")
    common = [
        "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OSX_ARCHITECTURES=arm64",
        "-DHERMES_ENABLE_TEST_SUITE=OFF", "-DHERMES_ENABLE_DEBUGGER=OFF",
        "-DHERMES_ENABLE_NAPI=OFF", "-DHERMES_ENABLE_CORE_EXTENSIONS=OFF",
        "-DHERMES_ENABLE_CONTRIB_EXTENSIONS=OFF", "-DHERMES_ENABLE_INTL=OFF",
        "-DHERMESVM_ALLOW_JIT=0", "-DHERMES_ALLOW_BOOST_CONTEXT=0",
        "-DHERMES_BUILD_SHARED_JSI=OFF", "-DHERMESVM_INTERNAL_JAVASCRIPT_NATIVE=OFF",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
    ]
    jobs = os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL", str(min(os.cpu_count() or 4, 8)))
    host = BUILD / "host"
    run("cmake", "-S", SOURCE, "-B", host, *common, "-DHERMES_APPLE_TARGET_PLATFORM=macosx")
    run("cmake", "--build", host, "--target", "hermesc", "-j", jobs)
    stage = Path(tempfile.mkdtemp(prefix="artifacts-", dir=BUILD))
    try:
        libraries = []
        for sdk in ("iphoneos", "iphonesimulator", "macosx"):
            target = BUILD / sdk
            run("cmake", "-S", ROOT, "-B", target, *common,
                f"-DCMAKE_OSX_SYSROOT={sdk}", f"-DHERMES_APPLE_TARGET_PLATFORM={sdk}",
                "-DCMAKE_OSX_DEPLOYMENT_TARGET=27.2",
                f"-DIMPORT_HOST_COMPILERS={host / 'ImportHostCompilers.cmake'}")
            run("cmake", "--build", target, "--target", "RenkuHermesAdapter", "-j", jobs)
            library = stage / sdk / "libRenkuHermesNative.a"
            library.parent.mkdir()
            run("xcrun", "libtool", "-static", "-o", library,
                target / "libRenkuHermesAdapter.a",
                target / "hermes/lib/libhermesvmlean_a.a", target / "hermes/jsi/libjsi.a")
            libraries.extend(["-library", library, "-headers", ROOT / "Native/include"])
        run("xcrun", "xcodebuild", "-create-xcframework", *libraries,
            "-output", stage / "RenkuHermesNative.xcframework")
        for sdk in ("iphoneos", "iphonesimulator", "macosx"):
            shutil.rmtree(stage / sdk)
        shutil.copy2(host / "bin/hermesc", stage / "hermesc")
        shutil.copy2(SOURCE / "LICENSE", stage / "HERMES-LICENSE")
        # Preserve all upstream third-party license notices alongside the binary.
        for path in (SOURCE / "external").rglob("*"):
            if path.is_file() and path.name.lower().startswith(("license", "copying", "notice")):
                destination = stage / "licenses" / path.relative_to(SOURCE)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
        compiler_info = output(stage / "hermesc", "-version")
        import re
        version = int(re.search(r"HBC bytecode version:\s*(\d+)", compiler_info).group(1))
        files = {str(p.relative_to(stage)): digest(p) for p in sorted(stage.rglob("*")) if p.is_file()}
        inputs = [ROOT / "hermes-revision.txt", ROOT / "CMakeLists.txt", ROOT / "ResolveSDK.cmake", Path(__file__)]
        inputs += sorted((ROOT / "Native").rglob("*"))
        metadata = {"schemaVersion": 1, "hermesRevision": REVISION, "bytecodeVersion": version,
                    "sdkVersion": "27.2", "architectures": ["arm64"], "files": files,
                    "inputs": {str(p.relative_to(ROOT)): digest(p) for p in inputs if p.is_file()}}
        (stage / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
        destination = ROOT / "Artifacts"
        previous = BUILD / "previous-artifacts"
        if previous.exists():
            shutil.rmtree(previous)
        if destination.exists():
            destination.rename(previous)
        try:
            stage.rename(destination)
        except BaseException:
            if previous.exists():
                previous.rename(destination)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        print(f"Built {destination} from Hermes {REVISION}")
    finally:
        if stage.exists():
            shutil.rmtree(stage)


if __name__ == "__main__":
    BUILD.mkdir(exist_ok=True)
    with (BUILD / "build.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        build()

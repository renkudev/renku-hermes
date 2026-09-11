# renku-hermes

The Hermes compiler and Apple runtime distribution maintained for renku. This is not an
upstream Hermes release. The engine source is unpatched. Application ownership and cancellation belong to consumers;
compiler/runtime packaging and bytecode verification remain matched.

## Consume a release

Use the exact tagged Swift package version and the `hermesvm` product. Download the matching
`hermesc-macos-arm64.tar.gz` release asset, verify its SHA-256 in the pinned release metadata,
and run `host/bin/hermesc -Xes6-block-scoping -O -emit-binary -out app.hbc app.js`. Do not mix release identities.
The compiler runs on macOS 27 arm64. Runtime slices support iOS 27 devices/simulators and macOS
27 arm64. Import C++ headers through `<hermesvm/hermes/hermes.h>` and `<hermesvm/jsi/jsi.h>`.

## Develop

Install Xcode 27, CMake, Ninja, Git and Python 3. Run `python3 scripts/build.py`. The ignored
`dist/` directory contains a complete local package, compiler, runtime, checksums, and inventory.
Changes to the source checkout alone do not change released consumers. Rebuild and explicitly
select this complete local output in renku. Build source is pinned by `recipe.json`.

This repository can be edited as a submodule inside the private renku workspace. Commit and push
here first, then commit the submodule pointer in the parent. Its build never reads parent files.

## Release

Run the Release workflow manually from main with a new major.minor.patch version, initially
`0.1.0`. It builds on hosted arm64 Xcode 27, verifies actual bytecode/async behavior and headers,
prepares draft assets, commits a manifest containing their checksums, tags, publishes, and
verifies anonymous SwiftPM consumption. Published tags and assets are never overwritten.
Interrupted drafts may resume only with matching source/artifact metadata. Inspect a partial
upload rather than replacing assets blindly. A published correction always receives a new version.
To recheck an existing release, run the read-only Verify published release workflow; it never
changes tags or assets. After publication, adopt the release explicitly in renku and run its
native acceptance.

Hermes source and packaged notices retain the upstream MIT license. The build downloads only
that pinned source; no upstream history is vendored into this repository.

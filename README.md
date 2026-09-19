# Renku Hermes

Local Swift package embedding a pinned Static Hermes runtime through Swift C++
interoperability. No Objective-C++ sources, remote binary dependencies, or publishing.

## Build and test

Requires Apple Silicon, Xcode 27.2, CMake, Ninja, and Python 3:

```sh
DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer python3 scripts/build.py
DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer swift test
```

The build fetches the exact commit in `hermes-revision.txt` into `.build/hermes`.
It produces `Artifacts/RenkuHermesNative.xcframework`, a matching host `hermesc`,
license notices, and a SHA-256 manifest covering native inputs and artifacts.
The framework contains static libraries for arm64 iOS, iOS Simulator, and macOS
27.2. JIT, native JS compilation, debugger, Node-API, and optional extensions are
disabled. The runtime uses Hermes's lean bytecode-only library. Builds are
incremental and serialized; artifact publication uses a staged directory replacement.

Add this directory as a local Swift package and link the `RenkuHermes` product.
Enable C++ interoperability on the consuming target and use arm64 architecture.
Build the artifacts before resolving the package. Git intentionally excludes
`.build/`, `Artifacts/`, and SwiftPM user state.

## Interface

```swift
import RenkuHermes

let session = try HermesSession(bytecodeAt: url) // MainActor
let snapshot = try session.call("renkuMount")
let updated = try session.call("renkuDispatch", argument: eventID)
```

`HermesSession` loads bytecode once and keeps JavaScript state across calls. Calls
accept a string argument and must return a string. The Swift class is confined to
the main actor and releases the runtime when destroyed. Independent sessions do
not share state. `HermesRuntime.evaluate` remains available for one-shot execution.
Bytecode is copied into owned storage and validated before execution.

JavaScript and recoverable C++ errors become `HermesError`. C++ exceptions are
caught before reaching Swift, and the runtime outlives any exception retaining JS
values. Fatal engine errors and allocation failures are not generally recoverable.
The public C++ header contains no JSI types. This is a synchronous bytecode host;
networking, timers, downloaded module loading, and an asynchronous event loop are
future additions. Downloadable application assets must target the installed
runtime contract; this lean runtime does not evaluate browser ESM source.

Set `RENKU_TEST_HBC` to the generated docs app's `app.hbc` when running Swift tests
to also verify compiled Renku components, signals, events, and structural updates.

## Local repository workflow

Develop in `shokunin/native/renku-hermes`. The local origin is
`/Users/bndkt/Developer/renku-hermes`, and no GitHub remote is configured.
Commit changes here, then update the submodule gitlink in the parent repository.
Keep the local origin synchronized before expecting a fresh submodule clone to
contain the new commit. Publishing and replacing the local URL are manual future
steps, outside this integration.

Upstream Hermes and third-party license notices are copied into `Artifacts/`
alongside the binary. The upstream source retains its original license files.

// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "RenkuHermes",
    platforms: [.iOS("27.2"), .macOS("27.2")],
    products: [.library(name: "RenkuHermes", targets: ["RenkuHermes"])],
    targets: [
        .binaryTarget(name: "RenkuHermesNative", path: "Artifacts/RenkuHermesNative.xcframework"),
        .target(
            name: "RenkuHermes",
            dependencies: ["RenkuHermesNative"],
            swiftSettings: [.interoperabilityMode(.Cxx)],
            linkerSettings: [.linkedLibrary("c++"), .linkedFramework("CoreFoundation")]
        ),
        .testTarget(
            name: "RenkuHermesTests",
            dependencies: ["RenkuHermes"],
            swiftSettings: [.interoperabilityMode(.Cxx)]
        ),
    ],
    cxxLanguageStandard: .cxx17
)

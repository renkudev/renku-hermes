// swift-tools-version: 6.4
import PackageDescription
// Development checkout: run python3 scripts/build.py first. Releases replace this
// local artifact reference with the immutable download URL and checksum.
let package = Package(
    name: "renku-hermes",
    platforms: [.iOS("27.0"), .macOS("27.0")],
    products: [.library(name: "hermesvm", targets: ["hermesvm"])],
    targets: [.binaryTarget(name: "hermesvm", path: "dist/hermesvm.xcframework")]
)

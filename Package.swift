// swift-tools-version: 6.4
import PackageDescription
let package = Package(
    name: "renku-hermes",
    platforms: [.iOS("27.0"), .macOS("27.0")],
    products: [.library(name: "hermesvm", targets: ["hermesvm"])],
    targets: [.binaryTarget(name: "hermesvm", url: "https://github.com/renkudev/renku-hermes/releases/download/0.1.0/hermesvm.xcframework.zip", checksum: "61ab82314a0a23e4db5831fe833563388406604dcc421d2ea2fb014d1000f4d8")]
)

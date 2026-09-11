// swift-tools-version: 6.4
import PackageDescription
let package = Package(
    name: "renku-hermes",
    platforms: [.iOS("27.0"), .macOS("27.0")],
    products: [.library(name: "hermesvm", targets: ["hermesvm"])],
    targets: [.binaryTarget(name: "hermesvm", url: "https://github.com/renkudev/renku-hermes/releases/download/0.2.0/hermesvm.xcframework.zip", checksum: "3610b2d2ed02640bfa84d2d6a7c9d68a296a0548738b06b9b9c894e85371b975")]
)

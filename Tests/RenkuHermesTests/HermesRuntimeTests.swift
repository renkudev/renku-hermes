import Foundation
import XCTest
@testable import RenkuHermes

final class HermesRuntimeTests: XCTestCase {
    private func compile(_ source: String) throws -> Data {
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let script = directory.appendingPathComponent("test.js")
        let bytecode = directory.appendingPathComponent("test.hbc")
        try source.write(to: script, atomically: true, encoding: .utf8)
        let process = Process()
        process.executableURL = root.appendingPathComponent("Artifacts/hermesc")
        process.arguments = ["-O", "-emit-binary", "-out", bytecode.path, script.path]
        try process.run()
        process.waitUntilExit()
        XCTAssertEqual(process.terminationStatus, 0)
        return try Data(contentsOf: bytecode)
    }

    func testGreetingAndChangedJavaScript() throws {
        for text in ["Hello, world!", "Changed in JavaScript 日本語 🌍", ""] {
            let encoded = String(data: try JSONEncoder().encode(text), encoding: .utf8)!
            let hbc = try compile("globalThis.greeting = function () { return \(encoded); };")
            XCTAssertEqual(try HermesRuntime.evaluate(bytecode: hbc, function: "greeting"), text)
        }
    }

    func testOneShotPreservesZeroArgumentCall() throws {
        let hbc = try compile("globalThis.countArgs = function () { return String(arguments.length); };")
        XCTAssertEqual(try HermesRuntime.evaluate(bytecode: hbc, function: "countArgs"), "0")
    }

    func testJavaScriptErrorsStayRecoverable() throws {
        for source in [
            "throw new Error('startup failure');",
            "globalThis.greeting = function () { throw new Error('call failure'); };",
            "globalThis.greeting = function () { return 42; };",
            "globalThis.unrelated = 1;",
        ] {
            let hbc = try compile(source)
            XCTAssertThrowsError(try HermesRuntime.evaluate(bytecode: hbc, function: "greeting"))
        }
    }

    @MainActor
    func testPersistentSessionsAndRecoverableErrors() throws {
        let hbc = try compile("var n = 0; globalThis.next = function (amount) { n += Number(amount); return String(n); }; globalThis.fail = function () { throw new Error('failure'); };")
        let first = try HermesSession(bytecode: hbc)
        let second = try HermesSession(bytecode: hbc)
        XCTAssertEqual(try first.call("next", argument: "2"), "2")
        XCTAssertThrowsError(try first.call("fail"))
        XCTAssertEqual(try first.call("next", argument: "3"), "5")
        XCTAssertEqual(try second.call("next", argument: "1"), "1")
        XCTAssertThrowsError(try first.call("missing"))
    }

    @MainActor
    func testCompiledRenkuApp() throws {
        guard let path = ProcessInfo.processInfo.environment["RENKU_TEST_HBC"] else {
            throw XCTSkip("Set RENKU_TEST_HBC to a generated docs app bundle")
        }
        let session = try HermesSession(bytecodeAt: URL(fileURLWithPath: path))
        let initial = try session.call("renkuMount")
        func allNodes(_ text: String) throws -> [[String: Any]] {
            let value = try JSONSerialization.jsonObject(with: Data(text.utf8)) as! [String: Any]
            func flatten(_ nodes: [[String: Any]]) -> [[String: Any]] {
                nodes.flatMap { [$0] + flatten($0["children"] as? [[String: Any]] ?? []) }
            }
            return flatten(value["nodes"] as! [[String: Any]])
        }
        let nodes = try allNodes(initial)
        let button = nodes.first { ($0["props"] as? [String: Any])?["testID"] as? String == "increment" }!
        let changed = try session.call("renkuDispatch", argument: button["event"] as! String)
        XCTAssertTrue(try allNodes(changed).contains { $0["text"] as? String == "Count: 1" })
        XCTAssertTrue(try allNodes(changed).contains { ($0["props"] as? [String: Any])?["testID"] as? String == "detail" })
        XCTAssertEqual(try session.call("renkuDispatch", argument: button["event"] as! String), changed)
    }

    func testInvalidBytecodeAndMissingFile() throws {
        XCTAssertThrowsError(try HermesRuntime.evaluate(bytecodeAt: URL(fileURLWithPath: "/missing/renku.hbc"), function: "greeting"))
        for invalid in [Data(), Data("not bytecode at all".utf8)] {
            XCTAssertThrowsError(try HermesRuntime.evaluate(bytecode: invalid, function: "greeting"))
        }
        var hbc = try compile("globalThis.greeting = function () { return 'ok'; };")
        XCTAssertThrowsError(try HermesRuntime.evaluate(bytecode: hbc.prefix(16), function: "greeting"))
        hbc[8] ^= 0xff
        XCTAssertThrowsError(try HermesRuntime.evaluate(bytecode: hbc, function: "greeting"))
    }
}

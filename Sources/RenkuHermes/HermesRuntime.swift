import Foundation
import RenkuHermesNative

public enum HermesError: Error, LocalizedError {
    case execution(String)

    public var errorDescription: String? {
        switch self {
        case .execution(let message): message
        }
    }
}

/// One-shot, synchronous execution. Each call owns an independent Hermes runtime.
public enum HermesRuntime {
    public static var bytecodeVersion: UInt32 { renku.bytecodeVersion() }

    public static func evaluate(bytecodeAt url: URL, function: String) throws -> String {
        try evaluate(bytecode: Data(contentsOf: url), function: function)
    }

    public static func evaluate(bytecode: Data, function: String) throws -> String {
        let result = bytecode.withUnsafeBytes { bytes in
            renku.evaluateBytecode(
                bytes.bindMemory(to: UInt8.self).baseAddress,
                bytes.count,
                std.string(function)
            )
        }
        guard result.success else { throw HermesError.execution(String(result.error)) }
        return String(result.value)
    }
}

/// A main-actor-confined runtime. All calls share the loaded application's state.
@MainActor
public final class HermesSession {
    private var session = renku.RuntimeSession()

    public convenience init(bytecodeAt url: URL) throws {
        try self.init(bytecode: Data(contentsOf: url))
    }

    public init(bytecode: Data) throws {
        let result = bytecode.withUnsafeBytes { bytes in
            session.load(bytes.bindMemory(to: UInt8.self).baseAddress, bytes.count)
        }
        guard result.success else { throw HermesError.execution(String(result.error)) }
    }

    public func call(_ function: String, argument: String = "") throws -> String {
        let result = session.call(std.string(function), std.string(argument))
        guard result.success else { throw HermesError.execution(String(result.error)) }
        return String(result.value)
    }
}

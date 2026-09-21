#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <memory>

namespace renku {
struct EvaluationResult {
  bool success;
  std::string value;
  std::string error;
};

struct RuntimeState;
// Copies share ownership; Swift owns one session for the lifetime of its app model.
class RuntimeSession {
  std::shared_ptr<RuntimeState> state_;
  EvaluationResult invoke(const std::string &functionName, const std::string *argument) noexcept;
 public:
  RuntimeSession();
  EvaluationResult drainMicrotasks() noexcept;
  EvaluationResult load(const uint8_t *bytes, size_t size) noexcept;
  EvaluationResult callWithoutArguments(const std::string &functionName) noexcept;
  EvaluationResult call(const std::string &functionName, const std::string &argument) noexcept;
};

// Copies the bytecode before execution. No JS values or exceptions escape.
EvaluationResult evaluateBytecode(const uint8_t *bytes, size_t size,
                                  const std::string &functionName) noexcept;
uint32_t bytecodeVersion() noexcept;
}

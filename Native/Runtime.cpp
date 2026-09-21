#include "RenkuHermesNative.h"
#include <hermes/hermes.h>
#include <cstring>
#include <vector>

namespace renku {
namespace {
// Hermes retains shared ownership of this buffer for the runtime's lifetime.
class BytecodeBuffer final : public facebook::jsi::Buffer {
  std::vector<uint8_t> bytes_;
 public:
  BytecodeBuffer(const uint8_t *bytes, size_t size) : bytes_(bytes, bytes + size) {}
  size_t size() const override { return bytes_.size(); }
  const uint8_t *data() const override { return bytes_.data(); }
};

facebook::hermes::IHermesRootAPI *rootAPI() {
  return facebook::jsi::castInterface<facebook::hermes::IHermesRootAPI>(
      facebook::hermes::makeHermesRootAPI());
}
}

uint32_t bytecodeVersion() noexcept { return rootAPI()->getBytecodeVersion(); }

struct RuntimeState {
  std::unique_ptr<facebook::hermes::HermesRuntime> runtime;
};
RuntimeSession::RuntimeSession() : state_(std::make_shared<RuntimeState>()) {}

EvaluationResult RuntimeSession::load(const uint8_t *bytes, size_t size) noexcept {
  // Keep the candidate runtime alive until any JSError has been destroyed.
  std::unique_ptr<facebook::hermes::HermesRuntime> runtime;
  try {
    if (!bytes || size < 12) return {false, {}, "Missing or truncated Hermes bytecode"};
    auto buffer = std::make_shared<BytecodeBuffer>(bytes, size);
    auto *api = rootAPI();
    if (!api->isHermesBytecode(buffer->data(), buffer->size()))
      return {false, {}, "Expected Hermes bytecode"};
    uint32_t version;
    std::memcpy(&version, buffer->data() + 8, sizeof(version));
    if (version != api->getBytecodeVersion())
      return {false, {}, "Incompatible Hermes bytecode version"};
    std::string validationError;
    if (!api->hermesBytecodeSanityCheck(buffer->data(), buffer->size(), &validationError))
      return {false, {}, "Invalid Hermes bytecode: " + validationError};
    runtime = facebook::hermes::makeHermesRuntime();
    runtime->evaluateJavaScript(buffer, "renku.hbc");
    state_->runtime = std::move(runtime);
    return {true, {}, {}};
  } catch (const facebook::jsi::JSError &error) {
    return {false, {}, error.what()};
  } catch (const std::exception &error) {
    return {false, {}, error.what()};
  } catch (...) {
    return {false, {}, "Unknown Hermes runtime error"};
  }
}
EvaluationResult RuntimeSession::drainMicrotasks() noexcept {
  try {
    if (!state_->runtime) return {false, {}, "Hermes session is not loaded"};
    state_->runtime->drainMicrotasks();
    return {true, {}, {}};
  } catch (const facebook::jsi::JSError &error) {
    return {false, {}, error.what()};
  } catch (const std::exception &error) {
    return {false, {}, error.what()};
  } catch (...) {
    return {false, {}, "Unknown Hermes microtask error"};
  }
}
EvaluationResult RuntimeSession::call(const std::string &functionName,
                                     const std::string &argument) noexcept {
  return invoke(functionName, &argument);
}
EvaluationResult RuntimeSession::callWithoutArguments(const std::string &functionName) noexcept {
  return invoke(functionName, nullptr);
}
EvaluationResult RuntimeSession::invoke(const std::string &functionName,
                                       const std::string *argument) noexcept {
  try {
    if (!state_->runtime) return {false, {}, "Hermes session is not loaded"};
    auto &runtime = *state_->runtime;
    auto entry = runtime.global().getProperty(runtime, functionName.c_str());
    if (!entry.isObject() || !entry.getObject(runtime).isFunction(runtime))
      return {false, {}, "Missing JavaScript function: " + functionName};
    auto function = entry.getObject(runtime).getFunction(runtime);
    auto result = argument
        ? function.call(runtime, facebook::jsi::String::createFromUtf8(runtime, *argument))
        : function.call(runtime);
    if (!result.isString()) return {false, {}, "JavaScript function must return a string"};
    return {true, result.getString(runtime).utf8(runtime), {}};
  } catch (const facebook::jsi::JSError &error) {
    return {false, {}, error.what()};
  } catch (const std::exception &error) {
    return {false, {}, error.what()};
  } catch (...) {
    return {false, {}, "Unknown Hermes runtime error"};
  }
}
EvaluationResult evaluateBytecode(const uint8_t *bytes, size_t size,
                                  const std::string &functionName) noexcept {
  RuntimeSession session;
  auto loaded = session.load(bytes, size);
  if (!loaded.success) return loaded;
  return session.callWithoutArguments(functionName);
}
}

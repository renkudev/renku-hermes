#include <hermesvm/hermes/hermes.h>
#include <hermesvm/jsi/jsi.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <chrono>
#include <thread>
int main(int argc, char **argv) {
  try {
    if (argc < 2) return 2;
    auto vm = facebook::hermes::makeHermesRuntime();
    auto &rt = *vm;
    // Test-only host turns for the consumer's RPC shell tests, never app runtime APIs.
    using Clock = std::chrono::steady_clock;
    struct Timer { Clock::time_point due; facebook::jsi::Function callback; };
    std::map<int, Timer> timers;
    int nextTimer = 0;
    rt.global().setProperty(rt, "setTimeout", facebook::jsi::Function::createFromHostFunction(rt,
      facebook::jsi::PropNameID::forAscii(rt, "setTimeout"), 2,
      [&](facebook::jsi::Runtime &rt, const facebook::jsi::Value &, const facebook::jsi::Value *args, size_t count) {
        if (!count) throw facebook::jsi::JSError(rt, "Expected timer callback");
        auto callback = args[0].asObject(rt).asFunction(rt);
        auto delay = count > 1 && args[1].isNumber() ? args[1].getNumber() : 0;
        const auto id = ++nextTimer;
        timers.emplace(id, Timer{Clock::now() + std::chrono::milliseconds(static_cast<int>(delay)), std::move(callback)});
        return facebook::jsi::Value(id);
      }));
    rt.global().setProperty(rt, "clearTimeout", facebook::jsi::Function::createFromHostFunction(rt,
      facebook::jsi::PropNameID::forAscii(rt, "clearTimeout"), 1,
      [&](facebook::jsi::Runtime &, const facebook::jsi::Value &, const facebook::jsi::Value *args, size_t count) {
        if (count && args[0].isNumber()) timers.erase(static_cast<int>(args[0].getNumber()));
        return facebook::jsi::Value::undefined();
      }));
    rt.global().setProperty(rt, "print", facebook::jsi::Function::createFromHostFunction(rt,
      facebook::jsi::PropNameID::forAscii(rt, "print"), 1,
      [](facebook::jsi::Runtime &rt, const facebook::jsi::Value &, const facebook::jsi::Value *args, size_t count) {
        if (count) std::cout << args[0].toString(rt).utf8(rt) << std::endl;
        return facebook::jsi::Value::undefined();
      }));
    std::ifstream input(argv[argc - 1], std::ios::binary);
    if (!input) return 2;
    std::string bytes((std::istreambuf_iterator<char>(input)), {});
    rt.evaluateJavaScript(std::make_shared<facebook::jsi::StringBuffer>(bytes), "test.hbc");
    rt.drainMicrotasks();
    while (!timers.empty()) {
      auto next = timers.begin();
      for (auto it = timers.begin(); it != timers.end(); ++it)
        if (it->second.due < next->second.due) next = it;
      std::this_thread::sleep_until(next->second.due);
      auto callback = std::move(next->second.callback);
      timers.erase(next);
      callback.call(rt);
      rt.drainMicrotasks();
    }
    return 0;
  } catch (const std::exception &e) { std::cerr << e.what() << std::endl; return 1; }
}

#include <hermesvm/hermes/hermes.h>
#include <hermesvm/jsi/jsi.h>
#include <fstream>
#include <iostream>
#include <iterator>
int main(int argc, char **argv) {
  try {
    if (argc < 2) return 2;
    auto vm = facebook::hermes::makeHermesRuntime();
    auto &rt = *vm;
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
    return 0;
  } catch (const std::exception &e) { std::cerr << e.what() << std::endl; return 1; }
}

cmake_minimum_required(VERSION 3.21)
project(RenkuHermesNative LANGUAGES C CXX)
# Hermes sets CMAKE_OSX_SYSROOT again inside its subdirectory. Resolve the SDK
# name there after project() as well, since our parent already enabled C++.
set(CMAKE_PROJECT_Hermes_INCLUDE "${CMAKE_CURRENT_SOURCE_DIR}/ResolveSDK.cmake")
add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/.build/hermes" hermes)
add_library(RenkuHermesAdapter STATIC Native/Runtime.cpp)
target_include_directories(RenkuHermesAdapter PRIVATE Native/include)
target_compile_features(RenkuHermesAdapter PRIVATE cxx_std_17)
target_link_libraries(RenkuHermesAdapter PRIVATE hermesvmlean_a jsi)

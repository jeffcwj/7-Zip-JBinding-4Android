#!/usr/bin/env bash
set -euo pipefail

work=$1
serial=$2
[[ ${GITHUB_ACTIONS:-} == true && $serial == emulator-5554 ]]
mkdir -p "$work"

# 仅核验用仓库生成的样本，x86_64 原生库不进入发行 AAR。
aar=sevenzipjbinding/build/outputs/aar/sevenzipjbinding-release.aar
platform="$ANDROID_HOME/platforms/android-36/android.jar"
cmake_bin="$ANDROID_HOME/cmake/3.22.1/bin"
ndk="$ANDROID_HOME/ndk/28.2.13676358"
unzip -p "$aar" classes.jar > "$work/classes.jar"
python3 scripts/make_zip64_fixture.py "$work/fixture.zip"
javac -encoding UTF-8 --release 8 -cp "$work/classes.jar" -d "$work" scripts/VerifyZip64.java
"$ANDROID_HOME/build-tools/35.0.0/d8" --release --min-api 24 --lib "$platform" \
  --output "$work/proof.zip" "$work/classes.jar" "$work/VerifyZip64.class"
"$cmake_bin/cmake" -S sevenzipjbinding -B "$work/native" -G Ninja \
  "-DCMAKE_MAKE_PROGRAM=$cmake_bin/ninja" "-DCMAKE_TOOLCHAIN_FILE=$ndk/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=x86_64 -DANDROID_PLATFORM=android-24 -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release
"$cmake_bin/cmake" --build "$work/native" --target 7-Zip-JBinding --parallel 2

remote=/data/local/tmp/sevenzip-zip64
adb -s "$serial" shell "mkdir -p $remote"
adb -s "$serial" push "$work/fixture.zip" "$work/fixture-large-prefix.bin" "$work/fixture-large-tail.bin" \
  "$work/proof.zip" "$work/native/lib7-Zip-JBinding.so" "$remote/"
adb -s "$serial" shell "chmod 444 $remote/proof.zip && CLASSPATH=$remote/proof.zip app_process /system/bin VerifyZip64 $remote/fixture.zip $remote/lib7-Zip-JBinding.so $remote/fixture-large-prefix.bin $remote/fixture-large-tail.bin"

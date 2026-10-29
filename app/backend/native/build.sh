#!/bin/sh
# E3DP — 编译原生 STL 解析器（C99，无第三方依赖）
#
# 用法：
#   ./build.sh            # 编译到 ./libstl_fast.<ext>
#   ./build.sh clean      # 清理产物
#
# 产物命名：macOS → libstl_fast.dylib，Linux → libstl_fast.so
# Python 侧（app/services/native_stl.py）会自动查找该文件；缺失时自动回退 numpy 实现，
# 因此**不编译也能跑**，只是慢一些。

set -e
cd "$(dirname "$0")"

SRC=stl_fast.c
case "$(uname -s)" in
  Darwin)
    EXT=dylib
    # 同时产出 x86_64 与 arm64（universal2）：本机 Python 可能是 Intel/Rosetta，
    # 而 clang 默认按当前机器出 arm64 —— 不这样做会 dlopen 失败
    SHARED="-dynamiclib -arch x86_64 -arch arm64"
    ;;
  Linux)  EXT=so;    SHARED="-shared" ;;
  *) echo "不支持的系统：$(uname -s)（本机用 numpy 回退路径）"; exit 1 ;;
esac
OUT="libstl_fast.$EXT"

if [ "$1" = "clean" ]; then
  rm -f "$OUT" ./*.o
  echo "已清理 $OUT"
  exit 0
fi

CC=${CC:-cc}
# -O3 + 浮点优化：解析器是纯数值循环；-fno-math-errno 让 sqrt 内联
CFLAGS="-O3 -std=c99 -fPIC -fno-math-errno -Wall -Wextra -Wno-unused-parameter"

echo "==> $CC $SHARED $CFLAGS -o $OUT $SRC"
$CC $SHARED $CFLAGS -o "$OUT" "$SRC"

echo "==> 产物：$(pwd)/$OUT"
ls -lh "$OUT"

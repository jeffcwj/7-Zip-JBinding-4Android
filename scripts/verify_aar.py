import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile


ABIS = {"arm64-v8a": "AArch64", "armeabi-v7a": "ARM"}
PAGE_SIZE = 16384


def require(condition, detail):
    if not condition:
        raise SystemExit(detail)


def verify(aar_path, readelf):
    # 兼容 JitPack 镜像的旧版 Python，检查条件和输出证据不变。
    expected = {"jni/{}/lib7-Zip-JBinding.so".format(abi) for abi in ABIS}
    with ZipFile(str(aar_path)) as aar, tempfile.TemporaryDirectory(dir=str(aar_path.parent)) as tmp:
        libs = [name for name in aar.namelist() if name.endswith(".so")]
        require(len(libs) == len(expected) and set(libs) == expected, "原生库清单不符：{}".format(libs))
        require(b"-keep class net.sf.sevenzipjbinding.**" in aar.read("proguard.txt"), "缺少 JNI 保留规则")
        with ZipFile(io.BytesIO(aar.read("classes.jar"))) as classes:
            require("net/sf/sevenzipjbinding/SevenZip.class" in classes.namelist(), "缺少 Java 桥入口")
            for name in ("LGPL-2.1.txt", "7-Zip-License.txt", "unRarLicense.txt"):
                entry = "META-INF/sevenzipjbinding/{}".format(name)
                require(entry in classes.namelist() and bool(classes.read(entry).strip()), "缺少随库许可：{}".format(name))

        for abi, machine in ABIS.items():
            library = Path(tmp) / "{}.so".format(abi)
            library.write_bytes(aar.read("jni/{}/lib7-Zip-JBinding.so".format(abi)))
            headers = subprocess.check_output([readelf, "-h", "-lW", "-dW", str(library)], universal_newlines=True)
            actual_machine = next((line.partition(":")[2].strip() for line in headers.splitlines()
                                   if line.strip().startswith("Machine:")), "")
            require(actual_machine == machine, "{} 的机器类型不符：{}".format(abi, actual_machine))
            loads = [line.split() for line in headers.splitlines() if line.strip().startswith("LOAD ")]
            require(bool(loads), "{} 缺少 PT_LOAD".format(abi))
            for segment in loads:
                offset, address, alignment = int(segment[1], 16), int(segment[2], 16), int(segment[-1], 16)
                require(alignment >= PAGE_SIZE and (offset - address) % PAGE_SIZE == 0,
                        "{} 的 PT_LOAD 未达到 16 KB 对齐：{}".format(abi, " ".join(segment)))
            require(not any("libc++_shared.so" in line for line in headers.splitlines() if "(NEEDED)" in line),
                    "{} 意外依赖共享 C++ 运行库".format(abi))
            print("{}: {} 个 PT_LOAD 通过 16 KB 对齐检查".format(abi, len(loads)))
    print("AAR SHA-256: {}".format(hashlib.sha256(aar_path.read_bytes()).hexdigest()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("aar", type=Path)
    parser.add_argument("readelf")
    args = parser.parse_args()
    verify(args.aar, args.readelf)

from io import BytesIO, SEEK_SET
from pathlib import Path
import sys
import zipfile
from zlib import crc32


def write_entries(archive):
    archive.writestr("assetpacks/store.bin", bytes(range(256)) * 4, zipfile.ZIP_STORED)
    archive.writestr("assetpacks/deflate.bin", b"native-decode\n" * 8192, zipfile.ZIP_DEFLATED)


def write_fixture(target):
    # 用小文件生成真实的 ZIP64 目录及尾部记录，不需要游戏数据或多 GB 临时空间。
    original_limit = zipfile.ZIP64_LIMIT
    zipfile.ZIP64_LIMIT = 255
    try:
        with zipfile.ZipFile(target, "w", allowZip64=True) as archive:
            write_entries(archive)
    finally:
        zipfile.ZIP64_LIMIT = original_limit
    raw = target.read_bytes()
    if b"PK\x06\x06" not in raw or b"PK\x06\x07" not in raw:
        raise RuntimeError("样本没有生成 ZIP64 尾部记录")
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or archive.infolist()[1].header_offset <= 255:
            raise RuntimeError("ZIP64 样本目录或正文错误")


def write_large_offset_parts(target):
    # 只传输头尾，Android 侧用稀疏零区组装；两个被提取成员的实际偏移都超过 4 GiB。
    padding = zipfile.ZipInfo("assetpacks/padding.bin")
    padding.header_offset = 0
    padding.file_size = padding.compress_size = 1 << 32
    zeros = bytes(8 << 20)
    padding.CRC = 0
    for _ in range(padding.file_size // len(zeros)):
        padding.CRC = crc32(zeros, padding.CRC)
    prefix = padding.FileHeader(zip64=True)
    start = len(prefix) + padding.file_size

    class ArchiveTail(BytesIO):
        def tell(self):
            return super().tell() + start

        def seek(self, offset, whence=SEEK_SET):
            return super().seek(offset - start if whence == SEEK_SET else offset, whence) + start

    tail = ArchiveTail()
    with zipfile.ZipFile(tail, "w", allowZip64=True) as archive:
        archive.filelist.append(padding)
        write_entries(archive)
    target.with_name(f"{target.stem}-large-prefix.bin").write_bytes(prefix)
    target.with_name(f"{target.stem}-large-tail.bin").write_bytes(tail.getvalue())


if __name__ == "__main__":
    fixture = Path(sys.argv[1])
    write_fixture(fixture)
    write_large_offset_parts(fixture)

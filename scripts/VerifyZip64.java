import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.zip.CRC32;
import net.sf.sevenzipjbinding.ArchiveFormat;
import net.sf.sevenzipjbinding.ExtractOperationResult;
import net.sf.sevenzipjbinding.IInArchive;
import net.sf.sevenzipjbinding.PropID;
import net.sf.sevenzipjbinding.SevenZip;
import net.sf.sevenzipjbinding.impl.RandomAccessFileInStream;

public final class VerifyZip64 {
    private static void require(boolean condition, String detail) {
        if (!condition) {
            throw new AssertionError(detail);
        }
    }

    private static void verify(IInArchive zip, int index, String path, byte[] expected) throws Exception {
        require(path.equals(zip.getProperty(index, PropID.PATH)), "成员路径不符：" + path);
        require(((Number) zip.getProperty(index, PropID.SIZE)).longValue() == expected.length, "成员长度不符：" + path);
        CRC32 crc = new CRC32();
        crc.update(expected);
        require((((Number) zip.getProperty(index, PropID.CRC)).longValue() & 0xffffffffL) == crc.getValue(), "成员 CRC 不符：" + path);
        ByteArrayOutputStream output = new ByteArrayOutputStream(expected.length);
        ExtractOperationResult result = zip.extractSlow(index, bytes -> {
            require(bytes.length <= expected.length - output.size(), "成员展开超过预期：" + path);
            output.write(bytes, 0, bytes.length);
            return bytes.length;
        });
        require(result == ExtractOperationResult.OK, "成员解包失败：" + path + " / " + result);
        require(Arrays.equals(expected, output.toByteArray()), "成员正文不符：" + path);
    }

    private static void verifyArchive(File file, int first, byte[] stored, byte[] deflated) throws Exception {
        try (RandomAccessFile input = new RandomAccessFile(file, "r");
             IInArchive zip = SevenZip.openInArchive(ArchiveFormat.ZIP, new RandomAccessFileInStream(input))) {
            require(zip.getNumberOfItems() == first + 2, "ZIP64 目录条数不符");
            if (first == 1) {
                require(((Number) zip.getProperty(0, PropID.SIZE)).longValue() == (1L << 32), "ZIP64 稀疏成员长度不符");
            }
            verify(zip, first, "assetpacks/store.bin", stored);
            verify(zip, first + 1, "assetpacks/deflate.bin", deflated);
        }
    }

    public static void main(String[] args) throws Exception {
        require(args.length == 1 || args.length == 2 || args.length == 4, "需要 ZIP64 样本、可选原生库和稀疏样本的头尾");
        if (args.length >= 2) {
            // 独立 Android 核验不依赖宿主 APK 的库搜索路径，明确加载本轮构建的制品。
            System.load(args[1]);
            SevenZip.initLoadedLibraries();
        }
        byte[] stored = new byte[1024];
        for (int i = 0; i < stored.length; i++) {
            stored[i] = (byte) i;
        }
        byte[] line = "native-decode\n".getBytes(StandardCharsets.US_ASCII);
        byte[] deflated = new byte[line.length * 8192];
        for (int i = 0; i < deflated.length; i += line.length) {
            System.arraycopy(line, 0, deflated, i, line.length);
        }
        verifyArchive(new File(args[0]), 0, stored, deflated);
        if (args.length == 4) {
            File prefix = new File(args[2]);
            File sparse = File.createTempFile("zip64-offset-", ".zip", prefix.getParentFile());
            try {
                try (RandomAccessFile output = new RandomAccessFile(sparse, "rw")) {
                    output.write(Files.readAllBytes(prefix.toPath()));
                    output.seek(output.getFilePointer() + (1L << 32));
                    output.write(Files.readAllBytes(new File(args[3]).toPath()));
                }
                verifyArchive(sparse, 1, stored, deflated);
                System.out.println("超过 4 GiB 的成员偏移验证通过");
            } finally {
                Files.deleteIfExists(sparse.toPath());
            }
        }
        System.out.println("ZIP64 原生解包通过：STORE 和 DEFLATE 的路径、长度、CRC 和正文一致");
    }
}

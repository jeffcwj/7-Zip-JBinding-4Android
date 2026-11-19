# Android 双架构构建与分发

本分支基于上游 `Release-16.02-2.02`（`389e5cfb0cb3dd2f7c96105f598d1577c614d61d`）。保留上游归档格式支持，使用 C++14 编译旧版代码，仅为 Android 更新构建和发布配置。发行 AAR 包含 `arm64-v8a` 与 `armeabi-v7a`，两者的 ELF 加载段均要求 16 KB 对齐；Android 最低版本为 API 24。

## 从源码构建

使用 JDK 17、Android SDK 36、Build Tools 35.0.0、NDK 28.2.13676358 和 CMake 3.22.1。设置 `ANDROID_HOME` 指向 SDK，再使用仓库内的 Gradle Wrapper：

```bash
bash ./gradlew :sevenzipjbinding:assembleRelease :sevenzipjbinding:publishReleasePublicationToMavenLocal --no-daemon
```

本地 Maven 制品为 `net.sf.sevenzipjbinding:sevenzipjbinding:16.02-2.02-16kb.1`。`scripts/verify_aar.py` 检查 AAR 中的 ABI、ELF 对齐、JNI 保留规则与随包许可。GitHub Actions 另在临时 Android 模拟器中执行原生 ZIP64 核验：只使用脚本生成的样本，覆盖直接存储、Deflate 以及超过 4 GiB 的成员偏移。模拟器专用 x86_64 库不会进入发行 AAR。

## 定版与许可证

先验证 `android-16kb` 分支的自动构建，再对同一提交打固定版本标签；JitPack 构建并核验同一版源码，不依赖本机预编译文件。发行核验应分别记录 GitHub Actions 结果和 JitPack 的 POM、AAR 获取结果。

原始 LGPL 2.1 文本、7-Zip 许可和 unRAR 限制随 AAR 的 `classes.jar` 保留在 `META-INF/sevenzipjbinding/`。再分发时保留原许可及对应版本的完整源码来源。unRAR 源码不可用于重建专有的 RAR 压缩算法或开发与 RAR 兼容的压缩器。

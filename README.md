# vibe-rsa-ffmpeg.d —— 口播音频 + 15 张插图 → 重剪成片

甲方 2026-10-12 交代的活儿：把**已导出的视频**拆出音频，用**阿里云语音识别**标定每句的时间戳，
再按**15 张插图**（顺序与文稿 15 段一致）做背景图，用 **ffmpeg** 按时间戳重新合成一条视频。

## 成片

`杂物新陈代谢-重剪-260412.mp4` —— 886x1920@30fps，H.264(high, yuv420p) + AAC 192k，163.83s，4915 帧，9.3 MB。

## 关键事实（踩过的坑）

| 项 | 结论 |
|---|---|
| 阿里云 ASR | `paraformer-v2` + `timestamp_alignment_enabled=true`，异步「提交→轮询→取结果」，端点是**业务空间专属域名** `https://ws-ip710u7i2cpsugfs.cn-beijing.maas.aliyuncs.com`（key 文件里的 `http api host`）。 |
| 音频没法直接喂 | RESTful 接口**只收公网 URL**，不收本地文件/base64。本机公网端口**云侧拉不到**（`FILE_DOWNLOAD_FAILED`）⇒ 走官方**临时存储**：`GET /api/v1/uploads?action=getPolicy&model=paraformer-v2` → multipart 上传到 `upload_host` → 得到 `oss://...`，提交任务时**必须**带 `X-DashScope-OssResourceResolve: enable`。 |
| 原片没有硬切 | 15 张图是**渐变转场**，相邻帧差恒定（0.33），scene 检测在 0.02 阈值都测不到切点 ⇒ 切换时刻**无法从画面还原**，只能由音频/文稿推。 |
| 识别质量 | 17 句、580 字；同音误识 10 处（边际→编辑、清出事务→清楚事物、心理→心里 等），与文稿字符级对齐**相似度 0.9811**，不影响定位。 |

## 目录

```
bin/asr_cn.py        音频 → 临时 OSS → paraformer-v2（带时间戳）→ work/asr/transcription.json
bin/align_text.py    文稿 ⟷ 识别结果 字符级对齐 → work/align.char2time.tsv（每个字的时间）
bin/build_plan.py    15 段切点（图 ↔ 文稿片段 ↔ 时间）→ work/segments.json
bin/prep_frames.py   1535x2732 图 cover-crop 成 886x1920 偶数尺寸 → work/segfr/
bin/render_video.sh  分段编码 → concat → 配音频 → 成片
bin/verify_video.py  机械验收（流参数/帧数/PTS 单调/逐段图片命中/音频一致性）→ __SELFTEST__ 9 0
work/doc.txt         甲方给的文稿（切分基准）
work/分镜对账图.jpg   成片里 15 段的代表帧，一眼核对图文是否对应
```

## 复现

```bash
cd /home/longxia/vibe-rsa-ffmpeg.d
python3 bin/asr_cn.py work/audio16k.wav work/asr paraformer-v2
python3 bin/align_text.py work/doc.txt work/asr/transcription.json work/align
python3 bin/build_plan.py work/align.char2time.tsv work/doc.txt work/segments.json 163840
python3 bin/prep_frames.py work/segments.json work/images work/segfr 886 1920
bash bin/render_video.sh work/segments.json work/segfr <原视频> 杂物新陈代谢-重剪-260412.mp4
python3 bin/verify_video.py 杂物新陈代谢-重剪-260412.mp4 work/segments.json work/segfr <原视频>
```

## 15 段时间轴（成片实际值）

| # | 图（标签） | 覆盖文稿 | 起止(s) |
|---|---|---|---|
| 1 | 杂物多 | 开篇提问 | 0.00–5.92 |
| 2 | 物品进入 | 生活用品新陈代谢…大家都熟练 | 5.92–20.01 |
| 3 | 有进难出 | 但怎么把东西清出去… | 20.01–26.30 |
| 4 | 长期维护 | 不靠一次性大扫除…长期维护的小事 | 26.30–37.69 |
| 5 | 顺手顺路/成本/收益 | 核心就三个词… | 37.69–46.86 |
| 6 | 成本 | 是否顺手顺路…边际成本…心理带宽 | 46.86–61.50 |
| 7 | 收益 | 边际收益…找到西更省事…清爽舒服 | 61.50–81.83 |
| 8 | 顺手顺路 | 顺手顺路就是心理带宽富余…垃圾袋去扔掉 | 81.83–104.07 |
| 9 | 别装太满 | 垃圾袋很便宜…免得撑破撒出来 | 104.07–114.54 |
| 10 | 成本+收益→是否处理 | 这类小事做不做…成本就很低 | 114.54–128.62 |
| 11 | 成本收益 | 如果成本比收益低… | 128.62–133.95 |
| 12 | 出口 | 断舍离不是乱扔…建立一条出口 | 133.95–142.13 |
| 13 | 有进有出 | 只控制买东西进来不够…有进就得有出 | 142.13–149.20 |
| 14 | 进/出 | 进出的频率和数量…动态平衡 | 149.20–158.75 |
| 15 | 有序自洽 | 这样才能长期保持有序自洽 | 158.75–163.84 |

> 切点规则：取该段文本首字的时间，并落在识别结果的自然停顿上（段内不留空档、无重叠、总帧数严格等于音频长度）。
> 15 张图在成片里严格按甲方给的顺序 1→15 出现。

## 口径锁定（甲方 2026-10-12 定，勿改）

- 这 15 张图是**照着文稿内容专门做的一一匹配**。因此 `bin/build_plan.py` 里的 `image ↔ text`
  对照表**不许按"语义更贴切"去调整**，时间戳只从该对照表**推导**，不得反向改动。
- 具体后果（明确接受，不必修）：
  - 第 2 段「物品进入」覆盖 5.92–20.01s（14.1s，全片最长）；
  - 第 9 段「别装太满」从 104.07s（"垃圾袋很便宜"）起，而不是等 115.9s 的"建议不要把垃圾装得满满当当"。
- 再改口径 = 打乱甲方的图，属于词不达意；要调只能由甲方明确指示。

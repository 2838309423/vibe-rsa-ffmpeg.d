# vibe-rsa-ffmpeg.d —— 口播音频 + 插图 → 成片（可复用流水线）

**干什么**：拿一条已导出的口播视频（或其音频）+ N 张插图 + 文稿，自动标定每句话的时间戳，
把插图按文稿段落切成 N 段时间轴，用 ffmpeg 合成为一条竖屏成片，并做机械验收。

**从哪来**：甲方 2026-10-12 交代的活儿（豆包朗读音频 + 15 张豆包插图 → 重剪）。
2026-10-13 改造成配置驱动，目的是**能反复用于新片子**，不再只服务这一条。

## 30 秒上手（新片子）

```bash
cd /home/longxia/vibe-rsa-ffmpeg.d

# ① 建项目（源音频/视频一并拷进去）
bash bin/new_project.sh 260420-厨房收纳 --source /path/to/doubao.mp4

# ② 填两样东西
#    projects/260420-厨房收纳/doc.txt        ← 粘文稿（切分基准，逐字）
#    projects/260420-厨房收纳/project.json   ← segments[]：每段 {image,label,text}
#    images/ 里放插图，image 顺序 = 成片顺序

# ③ 一键跑完（识别→对齐→切点→帧图→合成→验收）
bash bin/run_all.sh --project projects/260420-厨房收纳

# 已有识别结果时省一次付费调用：
bash bin/run_all.sh --project projects/260420-厨房收纳 --skip-asr
```

产物都在 `projects/<名>/out/`：`final.mp4`（成片）、`plan.json`（时间轴）、`分镜对账图.jpg`（15 段代表帧拼图）。

## 目录

```
bin/
  config.py         项目配置读取（所有脚本共用；project.json 相对路径按项目目录解析）
  asr_cn.py         抽音频 → 阿里云临时 OSS → paraformer-v2（带时间戳）→ out/asr/
  align_text.py     文稿 ⟷ 识别结果 字符级对齐 → out/align.char2time.tsv
  build_plan.py     按 segments[] 推导时间轴 → out/plan.json
  prep_frames.py    插图 cover-crop 成偶数尺寸画幅 → out/segfr/
  render_video.sh   分段编码 → concat → 配音频 → out/final.mp4
  verify_video.py   机械验收（10 项）→ __SELFTEST__ 10 0
  run_all.sh        一键跑完 6 步
  new_project.sh    从模板新建项目
projects/
  260412-杂物新陈代谢/          本次实例（留档当样例）
    project.json  doc.txt  images/（15 张）  source.mp4  out/
docs/
  方案-可复用化与gitee建仓-261013.md
```

`project.json` 关键字段：

```json
{
  "source": "source.mp4",                       // 相对项目目录；音频/视频都行
  "video": {"width": 886, "height": 1920, "fps": 30, "crf": 20, "preset": "medium"},
  "asr": {"model": "paraformer-v2", "language_hints": ["zh"], "timestamp_alignment_enabled": true},
  "segments": [ {"image": "01-杂物多.jpg", "label": "杂物多", "text": "我既不傻又不懒，……"} ]
}
```

- `segments` 的**数组顺序 = 成片里图的顺序**；`text` 必须**逐字**取自 `doc.txt`（切点 = 该段首字的时间）。
- 切点会落在识别出的自然停顿上，段内不留空档、无重叠，总帧数严格等于音频长度（末段吸收取整误差）。
- 环境变量：`FFMPEG` / `FFPROBE`（缺省用 `PATH` 里的）、`BAILIAN_KEY_FILE`（缺省 `~/.config/aliyun-bailian/api-key.txt`）。

## 验收

`bin/verify_video.py` 10 项断言，全绿才算出片（末行 `__SELFTEST__ <断言数> <失败数>`）：
流参数/画幅/帧率、总帧数=计划、PTS 严格单调、末帧+1 帧≈时长、**逐段中点帧与源图比对**（MAE 判对图、判顺序）、
音频采样数一致、100ms 包络相关系数 > 0.99。

## 关键事实（踩过的坑，别再踩）

| 项 | 结论 |
|---|---|
| 阿里云 ASR | `paraformer-v2` + `timestamp_alignment_enabled=true`，异步「提交→轮询→取结果」；端点用 key 文件里的 `http api host` 推出的**业务空间专属域名** `https://<wsp>.cn-beijing.maas.aliyuncs.com`。 |
| 音频没法直接喂 | RESTful 接口**只收公网 URL**，不收本地文件/base64。本机公网端口**云侧拉不到**（`FILE_DOWNLOAD_FAILED`）⇒ 走官方**临时存储**：`GET /api/v1/uploads?action=getPolicy&model=paraformer-v2` → multipart 上传 → 得 `oss://...`；提交任务**必须**带 `X-DashScope-OssResourceResolve: enable`。 |
| 原片没有硬切 | 本例 15 张图是**渐变转场**，相邻帧差恒定（0.33），scene 检测阈值降到 0.02 都测不到切点 ⇒ 切换时刻**无法从画面还原**，只能由音频/文稿推。 |
| 奇数尺寸喂不了 libx264 | 插图 1535x2732 是奇数 ⇒ 先 `prep_frames.py` cover-crop 成偶数画幅，否则 `width not divisible by 2`。 |
| concat 的路径 | `-f concat` 列表里的 `file` 是**相对 concat.txt 所在目录**解析的 ⇒ 必须写绝对路径，否则出现 `work/render/work/render/...`。 |
| 识别质量 | 本例 17 句/580 字，同音误识 10 处（边际→编辑、清出事务→清楚事物、心理→心里 等），与文稿字符级对齐**相似度 0.9811**，不影响定位。 |
| 改造成本 | 16 vCPU 全 CPU 编码：163s 成片约 54s（先 `-preset ultrafast` 迭代时间轴，定稿再 medium）。 |

## 口径锁定（甲方 2026-10-12 定，勿改）

- 图与文稿段是**一一匹配**的（图照着文稿内容定制）。`segments` 里的 image ↔ text 对照
  **不许按"语义更贴切"去调整**；时间戳只从该表**推导**，不得反向改动。
- 已知且接受的不均衡：第 2 段「物品进入」14.1s（全片最长）；第 9 段「别装太满」从 104.07s
  （"垃圾袋很便宜"）起，而非等 115.9s 的"建议不要把垃圾装得满满当当"。
- 要调口径只能由甲方明确指示。

## 本例（projects/260412-杂物新陈代谢）读数

成片 `out/final.mp4`：886x1920@30fps，H.264(high,yuv420p)+AAC 192k，163.833s，4915 帧，9.3 MB，
md5 `46019d44f386caa2237cc9dfe7628bf3`（改造前后逐字节一致）。15 段逐段读数与文案见
`projects/260412-杂物新陈代谢/out/分镜对账图.jpg` 与 `out/plan.json`。

#!/usr/bin/env bash
# 一键跑完整条流水线：音频 → 识别 → 对齐 → 切点 → 帧图 → 合成 → 验收。
#
# 用法: bash bin/run_all.sh --project projects/<名> [--skip-asr] [--out 成片.mp4]
#   --skip-asr   已有 <out>/asr/transcription.json 时跳过识别（省钱、省时间）
#
# 依赖: ffmpeg/ffprobe（FFMPEG / FFPROBE 可指定绝对路径）、阿里云百炼 key
#       （缺省读 ~/.config/aliyun-bailian/api-key.txt，可用 BAILIAN_KEY_FILE 改）
set -euo pipefail

PROJECT="."; SKIP_ASR=0; OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --skip-asr) SKIP_ASR=1; shift ;;
    --out) OUT="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
[ -d "$PROJECT" ] || PROJECT="$ROOT/$PROJECT"
PY=python3
OUTDIR=$("$PY" -c "import sys;sys.path.insert(0,'bin');import config;print(config.read_project('$PROJECT')[0]['_out'])")
mkdir -p "$OUTDIR"

echo "########## 0/6 识别（阿里云 Paraformer，带时间戳） ##########"
if [ "$SKIP_ASR" = "1" ] && [ -f "$OUTDIR/asr/transcription.json" ]; then
  echo "已有 $OUTDIR/asr/transcription.json，跳过（--skip-asr）"
else
  "$PY" bin/asr_cn.py --project "$PROJECT"
fi

echo "########## 1/6 文稿 ⟷ 识别结果 字符级对齐 ##########"
"$PY" bin/align_text.py --project "$PROJECT"

echo "########## 2/6 切点 → plan.json ##########"
AUDIO_MS=$("$PY" -c "
import json,sys
j=json.load(open('$OUTDIR/asr/transcription.json',encoding='utf-8'))
print(j['properties']['original_duration_in_milliseconds'])")
"$PY" bin/build_plan.py --project "$PROJECT" --audio-ms "$AUDIO_MS"

echo "########## 3/6 插图 cover-crop → segfr ##########"
"$PY" bin/prep_frames.py --project "$PROJECT"

echo "########## 4/6 合成成片 ##########"
if [ -n "$OUT" ]; then bash bin/render_video.sh --project "$PROJECT" --out "$OUT";
else bash bin/render_video.sh --project "$PROJECT"; fi

echo "########## 5/6 机械验收 ##########"
if [ -n "$OUT" ]; then "$PY" bin/verify_video.py --project "$PROJECT" --out "$OUT";
else "$PY" bin/verify_video.py --project "$PROJECT"; fi

echo "########## 6/6 完成 ##########"
ls -la "$OUTDIR"/*.mp4 "$OUTDIR"/*.json 2>/dev/null || true

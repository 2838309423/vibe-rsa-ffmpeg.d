#!/usr/bin/env bash
# 按项目配置把插图 + 源音频合成成片（H.264 + AAC）。
#
# 用法: bash bin/render_video.sh --project projects/<名> [--out <成片.mp4>]
# 依赖: ffmpeg/ffprobe（可用 FFMPEG / FFPROBE 指定绝对路径）
#
# 流程: ① 从 source 抽音频 → ② 每段按 plan 的帧数生成无声片段 → ③ concat 拼接 → ④ 配音频出成片
set -euo pipefail

PROJECT="."
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --out)     OUT="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

FF="${FFMPEG:-ffmpeg}"
FP="${FFPROBE:-ffprobe}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
[ -d "$PROJECT" ] || PROJECT="$(pwd)/$PROJECT"

# 从 project.json 取运行参数（一次读全，避免多次起 python）
CFG_JSON=$(cd "$HERE/.." && python3 - "$PROJECT" <<'PY'
import json, os, sys
sys.path.insert(0, "bin")
import config
cfg, _ = config.read_project(sys.argv[1])
print(json.dumps({
    "out": cfg["_out"], "images": cfg["_images"], "source": cfg["_source"] or "",
    "w": cfg["video"]["width"], "h": cfg["video"]["height"], "fps": cfg["video"]["fps"],
    "crf": cfg["video"]["crf"], "preset": cfg["video"]["preset"],
    "abr": cfg["video"].get("audio_bitrate", "192k"),
}))
PY
)
get() { python3 -c "import json,sys;print(json.loads(sys.argv[1])['$1'])" "$CFG_JSON"; }

OUTDIR=$(get out); IMAGES=$(get images); SRC=$(get source)
W=$(get w); H=$(get h); FPS=$(get fps); CRF=$(get crf); PRESET=$(get preset); ABR=$(get abr)
PLAN="$OUTDIR/plan.json"
SEGFR="$OUTDIR/segfr"
WORK="$OUTDIR/render"                 # 必须绝对路径：concat 里的 file 相对 concat.txt 解析
[ -n "$OUT" ] || OUT="$OUTDIR/final.mp4"
case "$OUT" in /*) ;; *) OUT="$(pwd)/$OUT" ;; esac
[ -f "$PLAN" ] || { echo "缺 $PLAN（先跑 bin/build_plan.py）" >&2; exit 1; }
[ -d "$SEGFR" ] || { echo "缺 $SEGFR（先跑 bin/prep_frames.py）" >&2; exit 1; }
[ -n "$SRC" ] && [ -f "$SRC" ] || { echo "源文件不存在: $SRC" >&2; exit 1; }
mkdir -p "$WORK/parts"

echo "== ① 抽音频（$SRC）=="
"$FF" -hide_banner -loglevel error -y -i "$SRC" -vn -c:a aac -b:a "$ABR" -ar 44100 -ac 2 "$WORK/audio.m4a"
"$FP" -v error -show_entries format=duration -of csv=p=0 "$WORK/audio.m4a" | sed 's/^/音频时长: /'

echo "== ② 分段编码（${W}x${H}@${FPS} crf=${CRF} preset=${PRESET}）=="
: > "$WORK/concat.txt"
n=$(python3 -c "import json;print(len(json.load(open('$PLAN'))))")
for i in $(seq 1 "$n"); do
  FRAMES_N=$(python3 -c "import json;print(json.load(open('$PLAN'))[$i-1]['frames'])")
  SEG=$(printf "%s/seg%02d.png" "$SEGFR" "$i")
  [ -f "$SEG" ] || { echo "缺段图 $SEG（先跑 bin/prep_frames.py）" >&2; exit 1; }
  PART=$(printf "%s/parts/part%02d.mp4" "$WORK" "$i")
  "$FF" -hide_banner -loglevel error -y -loop 1 -i "$SEG" \
        -frames:v "$FRAMES_N" -r "$FPS" -c:v libx264 -preset "$PRESET" -crf "$CRF" \
        -pix_fmt yuv420p -profile:v high -level 4.1 -an "$PART"
  printf "  part%02d  %s 帧\n" "$i" "$FRAMES_N"
  echo "file '$PART'" >> "$WORK/concat.txt"
done

echo "== ③ 拼接视频轨 =="
"$FF" -hide_banner -loglevel error -y -f concat -safe 0 -i "$WORK/concat.txt" -c copy "$WORK/video.mp4"

echo "== ④ 配音频出成片 =="
"$FF" -hide_banner -loglevel error -y -i "$WORK/video.mp4" -i "$WORK/audio.m4a" \
      -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a "$ABR" -shortest \
      -movflags +faststart "$OUT"

echo "== 成片 =="
"$FP" -v error -show_entries format=duration,size,bit_rate \
      -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames \
      -of default=noprint_wrappers=1 "$OUT"
echo "-> $OUT"

#!/usr/bin/env bash
# 用 15 张图 + 原视频音频，按 segments.json 的时间轴合成新视频（H.264 + AAC，竖屏 886x1920@30）。
#
# 用法: bash bin/render_video.sh <segments.json> <frames_dir> <src_video> <out.mp4>
# 依赖: FFMPEG / FFPROBE 环境变量（缺省用 ~/toolchain 的静态版）
#
# 流程: ① 抽音频 → ② 每段按帧数生成无声片段 → ③ concat 拼接 → ④ 配音频出成片
set -euo pipefail

FF="${FFMPEG:-/home/longxia/toolchain/ffmpeg/ffmpeg-7.0.2-amd64-static/ffmpeg}"
FP="${FFPROBE:-/home/longxia/toolchain/ffmpeg/ffmpeg-7.0.2-amd64-static/ffprobe}"
PLAN="$1"; FRAMES="$2"; SRC="$3"; OUT="$4"
WORK="$(cd "$(dirname "$PLAN")" && pwd)/render"   # 必须绝对路径：concat 里的 file 相对 concat.txt 解析
FRAMES="$(cd "$FRAMES" && pwd)"
OUT="$([ "${OUT#/}" = "$OUT" ] && echo "$(pwd)/$OUT" || echo "$OUT")"
FPS=30
mkdir -p "$WORK/parts"

echo "== ① 抽音频 =="
"$FF" -hide_banner -loglevel error -y -i "$SRC" -vn -c:a aac -b:a 192k -ar 44100 -ac 2 "$WORK/audio.m4a"
"$FP" -v error -show_entries format=duration -of csv=p=0 "$WORK/audio.m4a" | sed 's/^/音频时长: /'

echo "== ② 分段编码 =="
: > "$WORK/concat.txt"
n=$(python3 -c "import json;print(len(json.load(open('$PLAN'))))")
for i in $(seq 1 "$n"); do
  read -r FRAMES_N <<<"$(python3 -c "
import json;p=json.load(open('$PLAN'))[$i-1];print(p['frames'])")"
  SEG=$(printf "%s/seg%02d.png" "$FRAMES" "$i")
  PART=$(printf "%s/parts/part%02d.mp4" "$WORK" "$i")
  "$FF" -hide_banner -loglevel error -y -loop 1 -i "$SEG" \
        -frames:v "$FRAMES_N" -r $FPS -c:v libx264 -preset medium -crf 20 \
        -pix_fmt yuv420p -profile:v high -level 4.1 -an "$PART"
  printf "  part%02d  %s 帧\n" "$i" "$FRAMES_N"
  echo "file '$PART'" >> "$WORK/concat.txt"
done

echo "== ③ 拼接视频轨 =="
"$FF" -hide_banner -loglevel error -y -f concat -safe 0 -i "$WORK/concat.txt" \
      -c copy "$WORK/video.mp4"

echo "== ④ 配音频出成片 =="
"$FF" -hide_banner -loglevel error -y -i "$WORK/video.mp4" -i "$WORK/audio.m4a" \
      -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest \
      -movflags +faststart "$OUT"

echo "== 成片 =="
"$FP" -v error -show_entries format=duration,size,bit_rate -show_entries stream=codec_name,width,height,r_frame_rate,nb_frames -of default=noprint_wrappers=1 "$OUT"

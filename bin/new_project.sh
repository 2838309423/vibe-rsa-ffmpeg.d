#!/usr/bin/env bash
# 从模板新建一个视频项目目录（新片子的起点）。
#
# 用法: bash bin/new_project.sh <项目名> [--source <音频/视频路径>]
#   例: bash bin/new_project.sh 260420-厨房收纳 --source /path/to/doubao.mp4
#
# 生成 projects/<项目名>/{project.json,doc.txt,images/}，随后：
#   1) 把文稿填进 doc.txt（切分基准）
#   2) 把插图按顺序放进 images/（文件名随意，顺序由 project.json 的 segments 决定）
#   3) 填 project.json 的 segments[]：每段 = {image, label, text}，text 是该段对应的文稿片段
#   4) bash bin/run_all.sh --project projects/<项目名>
set -euo pipefail

NAME="${1:-}"; shift || true
SRC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --source) SRC="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done
[ -n "$NAME" ] || { echo "用法: bash bin/new_project.sh <项目名> [--source <路径>]" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIR="$ROOT/projects/$NAME"
[ -e "$DIR" ] && { echo "已存在: $DIR" >&2; exit 1; }
mkdir -p "$DIR/images"

# 源文件：给了就拷进项目（相对路径、可复现），没给留占位
if [ -n "$SRC" ]; then
  [ -f "$SRC" ] || { echo "源文件不存在: $SRC" >&2; exit 1; }
  ext="${SRC##*.}"
  cp "$SRC" "$DIR/source.$ext"
  SRC_JSON="source.$ext"
else
  SRC_JSON="source.mp4"
fi

cat > "$DIR/project.json" <<JSON
{
  "name": "$NAME",
  "source": "$SRC_JSON",
  "doc": "doc.txt",
  "images_dir": "images",
  "out_dir": "out",
  "video": { "width": 886, "height": 1920, "fps": 30, "crf": 20, "preset": "medium" },
  "asr": { "model": "paraformer-v2", "language_hints": ["zh"], "timestamp_alignment_enabled": true },
  "segments": [
    { "image": "01.jpg", "label": "第一段标签", "text": "文稿里这一段逐字照抄（切点=这段首字的时间）" },
    { "image": "02.jpg", "label": "第二段标签", "text": "第二段文稿……" }
  ]
}
JSON
: > "$DIR/doc.txt"
: > "$DIR/images/.gitkeep"

cat <<EOF
已建: $DIR
  project.json   ← 填 segments[]（image 顺序 = 成片顺序；text 必须逐字来自 doc.txt）
  doc.txt        ← 粘文稿（切分基准）
  images/        ← 放插图（$([ -n "$SRC" ] && echo "源已拷为 $SRC_JSON" || echo "源未拷：把音频/视频放成 $SRC_JSON")）
然后: bash bin/run_all.sh --project projects/$NAME
EOF

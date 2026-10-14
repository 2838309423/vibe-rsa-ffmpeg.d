# 方案：BlenderKit（改名 Blendkit）× 房间整理 / 断舍离视频创作

> 2026-10-14 ｜ 状态：调研 + 实测完成，等你圈选开工
> 结论先行：**知道，而且已经打通**——家居整理类素材够多（免费档就有 2.3 万模型），
> "怎么呈现给你 + 怎么用"我做成**四件套机制 + 8 步 SOP**，并顺手抓了 **29 件精选样例**生成画册。

---

## 1. 关键事实速览（全部实测核实）

| 项 | 事实 |
|---|---|
| 品牌 | BlenderKit 正改名 **Blendkit**（blendkit.com），Blender 里的插件名仍叫 BlenderKit，两者混用都认 |
| 定位 | Blender 最大的内置资产库（模型/材质/HDRI/整屋场景/笔刷），**搜索→下载→拖放全在 Blender 内完成** |
| 套餐 | **Free $0**：23,688 模型 / 42,135 材质 / 1,067 场景；**Full $8.90/月**：82,589 模型全解锁（70% 分给创作者） |
| 许可 | 官方 FAQ 明确**商用与非商用都可用**，唯一限制是不能转卖资产本身 ⇒ 视频创作无障碍 |
| 安装 | Blender 4.5 → 偏好设置 → **获取扩展** → 搜 "BlenderKit" → 安装（extensions.blender.org 官方源） |
| 登录 | blendkit.com 注册账号；插件内 OAuth 登录。⚠ **VNC 桌面实测没有浏览器** ⇒ 对策见 §6.1 |
| 本地库 | 下载的资产进全局资产目录（默认用户目录下，可在偏好设置改），**跨场景复用、不重复下载** |
| 与 blender-mcp | 两个插件独立共存不冲突；Blender 重启后记得 N 面板重连 MCP（老规矩） |

来源：[套餐页](https://www.blendkit.com/plans/pricing/) ｜ [许可 FAQ](https://www.blendkit.com/faq-frequently-asked-questions/) ｜ [官方插件文档](https://github.com/BlenderKit/blenderkit/wiki/BlenderKit-add-on-documentation)

---

## 2. 我怎么向你呈现（四件套机制）

| 件 | 是什么 | 什么时候用 |
|---|---|---|
| **A 画册式** | 我按主题跑公开接口 → 生成缩略图画册（md）→ 文件卡发你 → **你报编号圈选** | 选型、找灵感（本次已交付 demo） |
| **B 购物清单式** | 你给分镜（"镜头1：塞满的衣柜→清空"）→ 我出 分镜×素材 清单 → 圈选定稿 | 单条片开工时 |
| **C 关键词速查卡** | 中文意图 → 英文搜索词对照表（§5） | 你自己在 Blender 里随手搜 |
| **D Blender 内逛** | Asset Browser 里搜索-预览-拖放是体验最好的，我供关键词+清单，你只管挑和摆 | 摆放阶段 |

**交互约定**：画册报编号 → 我落购物清单 → 你在 Blender 下载+拖放摆放（**审美归你，我不碰**）；
要我代摆 ⇒ 我出 bpy 脚本 + 预览报告 ⚠️ 等你批准。

---

## 3. 工作流 SOP（一条断舍离片，8 步）

| 步 | 内容 | 谁做 | 权限级 |
|---|---|---|---|
| 1 | 选题+分镜：要哪些"乱→整"画面 | 你 | — |
| 2 | 跑检索 → 出画册 / 购物清单 | 我 | ✅ 只读直做 |
| 3 | 圈选定稿（报编号） | 你 | — |
| 4 | 装 BlenderKit 扩展 + 登录（VNC 里操作） | 你（我出操作卡） | 一次性 |
| 5 | 按清单搜索 → 拖入摆放（自动吸附地面） | 你 | 审美你定 ❌我不碰 |
| 6 | 场景统计 / 穿模预检 / 视口截图给你核对 / GLB 备份 | 我 | ✅ 只读直做 |
| 7 | 整理动画（位移/开合关键帧） | 我出脚本+预览报告 | ⚠️ 待你批准 |
| 8 | 抽样低清测试渲染 → 正式渲染方案另批 | 我 | ✅ / ⚠️ |

---

## 4. 精选画册（29 件，已生成）

- 画册：`/home/longxia/vibe-rsa-ffmpeg.d/blenderkit/画册-精选素材-261014.md`
- 10 个主题：打包纸箱 / 收纳盒 / 收纳筐·置物架 / 衣物整理 / 衣柜 / 书架 / 厨房罐 / 鞋架 / "乱"素材 / 整屋场景
- 每件带：缩略图、**免费/Full 徽标**、质量分、**文件体积**（>100MB 标 ⚠）、详情页链接、Blender 内搜索词
- 圈选方式：直接回复编号（如"要 1、5、9"）

---

## 5. 关键词速查表（中文意图 → 英文搜索词）

| 你想要 | BlenderKit 里搜 | 备注 |
|---|---|---|
| 整理前的"乱" | `messy room` / `clothes pile` / `laundry basket` | 断舍离前状态 |
| 打包纸箱 | `cardboard box` / `moving box` | 免费质量很高（Poly Haven） |
| 收纳盒 | `storage box` / `storage bin` / `organizer box` | |
| 收纳筐 | `basket` / `wicker basket` / `laundry basket` | |
| 抽屉分格 | `drawer organizer` / `drawer dividers` | 数量少，多用收纳盒替代 |
| 衣柜 / 挂衣 | `wardrobe` / `closet` / `clothes rack` / `hanger` | |
| 叠好的衣服 | `folded clothes` / `folded towels` / `clothes stack` | 扫描级质量，文件偏大 |
| 书与书架 | `bookshelf` / `book stack` / `magazine holder` | |
| 鞋 | `shoe rack` / `shoe box` / `sneakers` | |
| 厨房收纳 | `glass jar` / `spice rack` / `food container` / `pantry` | |
| 桌面整理 | `desk organizer` / `pen holder` / `tray` | |
| 洞洞板 | `pegboard` | |
| 清洁工具 | `broom` / `vacuum cleaner` / `cleaning supplies` | |
| 玩具收纳 | `toy box` / `toy storage` | |
| 整屋舞台 | `bedroom interior` / `living room`（类型选 **Scene**） | 打包下载整间房 |
| 灯光 | HDRI 类目 → `Indoor` | 免费档充足 |

> 搜索是英文；认准结果里的 **Free/Full** 徽标。搜不到时换同义词（收纳 = storage / organizer / bin / basket 四个词轮着试）。

---

## 6. 坑与对策

**6.1 登录（唯一未实测环节，需要你的账号到场）** —— VNC 桌面实测无浏览器，三条路：
- a) 先在 Windows 浏览器注册 blendkit.com；VNC 里点 Login 后从 Blender 控制台复制授权 URL 到 Windows 浏览器完成登录；
- b) 装好后我看一眼扩展偏好里有没有可直接粘贴的 API Key 字段（源码里有该属性），有就最省事；
- c) 兜底：我下载 Chromium AppImage 落 `~/apps/`（纯用户态不动系统），VNC 里登录一次即可。

**6.2 文件体积**：选型看画册里的 MB 列，>100MB 慎选（本次抓到 508MB 的筐组合，直接跳），本机 16GB RAM。

**6.3 磁盘**：下载缓存默认在用户目录、可在偏好设置改；/home 余 146GB，充足。

**6.4 免费档够起步**：家居整理类免费模型很多；不够再上 Full（$8.9/月）。

**6.5 blender-mcp 共存**：互不干扰；Blender 重启后两件事——N 面板重连 MCP + BlenderKit 会自动恢复登录态。

---

## 7. 产物清单（已入正本仓，2026-10-14 甲方定）

- **归仓结论**：素材线 = 视频创作资产 ⇒ 入 **`gitee:gushiteng/vibe-rsa-ffmpeg.d.git`** 顶层 `blenderkit/`；
  **不进** `usavps-xfce-blender-turbovnc.d`（那是主机配置正本仓）——真把 BlenderKit 扩展装进 Blender 时，
  那边只补一行装机落地单，与素材/工具互不混放。
- 若素材库将来独立做大（几十主题 / 几百 MB / 跨机复用），再 subtree 拆独立仓；眼下不拆。

| 文件（仓内） | 说明 |
|---|---|
| `/home/longxia/vibe-rsa-ffmpeg.d/blenderkit/方案-blenderkit家居整理工作流-261014.md` | 本方案 |
| `/home/longxia/vibe-rsa-ffmpeg.d/blenderkit/画册-精选素材-261014.md` | 29 件画册 |
| `/home/longxia/vibe-rsa-ffmpeg.d/blenderkit/bk_search.py` | 检索工具：`python3 bk_search.py "关键词" --type model --max 5 --thumbs thumbs` |
| `/home/longxia/vibe-rsa-ffmpeg.d/blenderkit/build_gallery.py` | 画册生成器（改主题表即可复刻） |
| `…/thumbs/`（48 张）· `…/raw/`（10 份原始 JSON） | 缩略图与原始数据，可复跑可追溯 |

---

## 8. 下一步（回一个词即可）

1. **「圈选」** —— 报画册编号，我出购物清单
2. **「开工」** —— 我出 BlenderKit 安装+登录操作卡（VNC 里你点）
3. **「先不动」** —— 材料齐了，随时开

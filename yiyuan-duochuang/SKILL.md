---
name: yiyuan-duochuang
display_name: 一源多创 · 多平台图文
display_name_en: One Source, Multi-Platform Posts
description: >
  把一份素材（卖点、硬信息、实拍原图）改写成抖音图文、视频号图文、公众号、小红书、携程五个平台各自适配的图文稿和配图。按各平台官方规则出稿，文案去 AI 味，配图用 image2.6 以原图为参考生成，支持仿对标图版式，用 socai 汇总平台数据做选题和学习账号调性。AI 出稿，人工发布。
  当用户要一稿多发、分平台改写、多平台图文、给小红书或抖音或公众号或视频号或携程出稿、仿某张图的版式时使用。
  触发词：一源多创、多平台图文、分平台出稿、小红书笔记、抖音图文、视频号图文、公众号文章、携程笔记、对标图、仿版式、去AI味。
description_zh: 一份素材生成五个平台的差异化图文稿和配图：按官方规则出稿、去 AI 味、参考原图出最高清的图，AI 出稿，人工发布。
description_en: Turns one source brief into platform-specific image-and-text posts for Douyin, WeChat Channels, WeChat Official Accounts, Xiaohongshu and Ctrip, following each platform's rules and generating images from reference photos. AI drafts, humans publish.
category: writing
version: 0.1.0
author: pengdi190721-dot
allowed-tools: Bash,Read,Write,Glob,Grep
---

# 一源多创 · 多平台图文

## 这个技能做什么

把用户给的一份源素材包，改写成五个平台各自的图文稿和配图，打包成一个文件夹交给用户手动发布。

- 平台：抖音图文、视频号图文、公众号、小红书、携程。
- 只做图文，不做短视频。
- 只出稿，不发布。禁止调用任何平台的发布、评论、点赞、私信接口。
- 不编造。素材里没有的价格、日期、设施、数字、经历一律不写，缺什么就写"【待补：xx】"。

## 目录约定

- **技能目录**：本 SKILL.md 所在的目录。下文的 `scripts/`、`references/`、`templates/` 都指技能目录里的路径，运行脚本时用绝对路径，例如 `python3 <技能目录>/scripts/lint.py`。
- **用户数据目录**：用户工作目录下的 `yiyuan-data/`，存品牌信息、接口配置、字体、最新规则补充。技能更新时不会被覆盖。
- **工作台**：用户工作目录下的 `workbench/`，存 socai 采集的数据和账号调性档案。
- **输出目录**：用户工作目录下的 `输出/<日期>_<主题>/`，每次出稿一个文件夹。

## 每次开始前先检查

```bash
python3 <技能目录>/scripts/setup_check.py --status
```

- 返回 `initialized: false`：先做"首次运行"，做完再出稿。
- 返回 `rules_refresh_due: true`（距上次刷新超过 30 天）：提醒用户刷新规则，用户同意就做"首次运行"第 5 步。
- 其余缺项（例如没有字体、没配图片接口）：只补对应的那一步。

## 首次运行（7 步）

1. **建数据目录、检查环境。** 运行 `python3 <技能目录>/scripts/setup_check.py --init-data`。它会建好 `yiyuan-data/`，并检查 Python、Pillow、socai。没有 Pillow 就让用户运行 `python3 -m pip install pillow`。没有 socai 就提示用户在 WorkBuddy 技能市场添加"多平台社媒调研-Socai"，或按 https://socai.io/docs/installation/ 安装，装好后在 Chrome 里登录小红书和抖音。谁用这个技能，谁在自己电脑上装。
2. **接入 image2.6。** 问用户要接口地址和模型名，写进 `yiyuan-data/config/image.json`（字段见 `templates/image_config.example.json`）。API Key 由用户自己设置成环境变量 `IMAGE_API_KEY`，禁止让用户把 Key 发在对话里，禁止把 Key 写进任何文件。然后运行 `python3 <技能目录>/scripts/setup_check.py --test-image` 测一次。
3. **引导填品牌信息。** 按 @templates/brand_onboarding.md 一题一题问，每题给选项和示例，问完生成 `yiyuan-data/brand.md`，给用户看一遍再确认。
4. **学习账号调性。** 用户在问卷第 10 题给了自家账号，就按 @references/socai-workbench.md 的"账号调性档案"拉取近期作品，每个平台生成一份 `workbench/账号调性/<平台>.md`（模板 @templates/voice_profile.md）。没给账号或某平台样本少于 5 篇就跳过该平台。
5. **搜索最新规则。** 按 @references/rules_refresh.md 的检索清单搜索，把结果写进 `yiyuan-data/rules-latest/<平台>.md`，然后运行 `python3 <技能目录>/scripts/setup_check.py --mark rules_refreshed`。
6. **下载字体。** 运行 `python3 <技能目录>/scripts/fetch_fonts.py --data-dir yiyuan-data`，只下载 @references/fonts.md 白名单里的开源字体。
7. **初始化报告。** 再跑一次 `setup_check.py --status`，把结果用一句话一项讲给用户，问"确认"还是"某一步重来"。确认后运行 `setup_check.py --mark initialized`。

## 出稿流程（9 步 + 2 个交互点）

每一步只产出一个文件，写完再进下一步。所有文件写进同一个输出目录。

### 第 ① 步：素材拆解

- 输入：用户给的源素材包（文字、原图，可能还有对标图）。
- 动作：按 @templates/content_card.json 填内容卡。先数原图：每个卖点对应哪几张原图写进 `photos`；没有原图的卖点写进 `missing_photos`。
- 输出：`输出/<日期>_<主题>/00_内容卡.json`。
- 禁止：往内容卡里写素材里没有的事实；硬信息缺失时自己补。

### 第 ② 步：拆解对标图（用户给了对标图才做）

- 动作：按 @references/benchmark.md 看图拆解，每张对标图一份。
- 输出：`00_对标拆解_<序号>.json`。
- 禁止：猜看不清的内容，看不清就写 unknown。

### 第 ③ 步：对齐选题（workbench 里有近两周的选题机会表才做）

- 动作：读 `workbench/选题机会表.csv` 和 `workbench/排期表.csv`，找出和本次素材相关的选题、高频评论问题、搜索词，写进内容卡的 `topic_insights` 字段。
- 没有工作台数据就跳过，不要临时去大量采集。

### 第 ④ 步：逐平台写文案

一次只写一个平台，顺序：小红书 → 抖音图文 → 视频号图文 → 公众号 → 携程。只写用户在品牌信息里勾选过的平台。

每个平台按这个顺序做：

1. 读该平台规则 `references/platform-<平台>.md`，以及 `yiyuan-data/rules-latest/<平台>.md`（如果有）。
2. 读该平台账号调性档案 `workbench/账号调性/<平台>.md`（如果有），只学说话方式，不搬里面的事实。
3. 读 `yiyuan-data/brand.md`。
4. 从内容卡重新写，按 `templates/<平台>_post.json` 的字段填。禁止在上一个平台的稿子上改写。
5. 按 @references/humanizer-zh.md 开头的"改写清单"逐条改一遍。
6. 写进 `<平台目录>/post.json`。平台目录名见下表。

| 平台 | 平台代号 | 平台目录 |
| --- | --- | --- |
| 抖音图文 | douyin | 01_抖音图文 |
| 视频号图文 | shipinhao | 02_视频号图文 |
| 公众号 | gongzhonghao | 03_公众号 |
| 小红书 | xiaohongshu | 04_小红书 |
| 携程 | ctrip | 05_携程 |

### 第 ⑤ 步：写出图指令

- 动作：给 post.json 里 `images` 的每一项填完出图字段（模板 @templates/image_brief.json，规则 @references/image-generation.md）。张数按"有原图支撑的卖点数 + 首图 + 实用信息图"算，并落在平台区间内。
- 有对标图时：`text_mode` 填"底图叠字"，按对标拆解填 `text_layers`。
- 禁止：引用不存在的原图；让一张图承载两个卖点。

### 第 ⑥ 步：检查文案

```bash
python3 <技能目录>/scripts/lint.py --run "输出/<日期>_<主题>" --platform <平台代号>
```

- 有 FAIL：按报错逐条改 post.json，再跑一次。同一平台最多改 2 轮，仍有 FAIL 就把问题写进该平台 post.json 的 `needs_human`，继续下一个平台。
- 只有 WARN：逐条判断，确实有问题才改。

### 交互点 A：用户确认文案（在生图之前）

按 @templates/interaction_a.md 逐个平台问用户：选标题、改正文、勾选要出的图、原图不够时补不补。用户的选择写回 post.json（`chosen_title` 等字段），并追加到 `交互记录.md`。全部平台确认后才进入第 ⑦ 步。

### 第 ⑦ 步：生成图片

```bash
python3 <技能目录>/scripts/gen_image.py --run "输出/<日期>_<主题>" --platform <平台代号>
```

- 脚本按固定模板拼提示词，以原图为参考调用 image2.6，按最高分辨率存母版图，再导出平台尺寸并加"AI 生成"标识。
- `text_mode` 为"底图叠字"时，脚本先生成无字底图，再自动调用 overlay_text.py 叠字。
- 只重做某一张：加 `--slot <slot 名>`。先看提示词不调接口：加 `--dry-run`。

### 第 ⑧ 步：看图自查

逐张打开导出的图片，按 @templates/self_check.md 的"看图"部分逐条回答是或否：

- 图上文字和 `on_image_text` 是否一字不差；
- 有没有参考图里没有的设施、景观、菜品、人物；
- 有对标图时，文字层级和位置是否和对标拆解一致，文字有没有压住主体。

任一项为"否"：用 `--slot` 重新生成这一张，最多 3 次。直接画字 3 次都有错字，就把这张改成"底图叠字"再生成。仍不合格就写进 `needs_human`。

### 第 ⑨ 步：打包交付

```bash
python3 <技能目录>/scripts/lint.py --run "输出/<日期>_<主题>"
python3 <技能目录>/scripts/pack.py --run "输出/<日期>_<主题>"
```

lint 不带 `--platform` 会检查全部平台和平台间重复度；pack 生成各平台的发布文案、`07_交付清单.md`。

### 交互点 B：用户确认成品

按 @templates/interaction_b.md 展示每张图、文案终稿和审核报告摘要，逐张问"通过 / 重新生成 / 改为叠字 / 删掉"，确认发布声明。用户的选择追加到 `交互记录.md`。全部处理完再跑一次第 ⑨ 步，告诉用户输出目录在哪、发布时要勾选哪些声明。

## 执行规范

1. 一步只产出一个文件，写完再进下一步。
2. 输出一律按 templates 里的字段填写，不增删字段，字数不超上限。
3. 规则里写"必须"的必须做，写"禁止"的一律不做。
4. 每次只读当前平台的 references 文件，不同时加载五个平台。
5. 每篇文案先过去 AI 味清单，再交给 lint.py。
6. 看图任务用固定提问，按字段回答，看不清写 unknown。
7. 字数、禁用词、尺寸、重复度、照抄由 lint.py 判定，不靠自己判断。
8. 失败处理按上面写死的次数，达到上限就写进 `needs_human`，继续下一个平台。
9. 缺信息写"【待补：xx】"，禁止猜。
10. 和用户交互时，能给选项就给选项（WorkBuddy 支持选项卡片就用卡片，不支持就用编号让用户回复数字）。

## 文件索引

- 平台规则：`references/platform-douyin.md`、`platform-shipinhao.md`、`platform-gongzhonghao.md`、`platform-xiaohongshu.md`、`platform-ctrip.md`
- 合规：@references/compliance.md；禁用词：`references/banned_words.txt`
- 去 AI 味：@references/humanizer-zh.md
- 图片：@references/image-generation.md；对标：@references/benchmark.md；字体：@references/fonts.md
- 数据工作台：@references/socai-workbench.md；规则刷新：@references/rules_refresh.md
- 模板：`templates/` 下的全部文件
- 脚本：`setup_check.py`、`fetch_fonts.py`、`gen_image.py`、`overlay_text.py`、`lint.py`、`pack.py`

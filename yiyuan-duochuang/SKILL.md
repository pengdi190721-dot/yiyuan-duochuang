---
name: yiyuan-duochuang
display_name: 一源多创 · 多平台图文
display_name_en: One Source, Multi-Platform Posts
description: >
  把一份素材（卖点、硬信息、实拍原图）改写成抖音图文、视频号图文、公众号、小红书、携程五个平台各自适配的图文稿和配图，交付一个带一键复制按钮的"发布总览"网页。按各平台官方规则出稿，文案去 AI 味，配图用 image2.6 以原图为参考生成，支持仿对标图版式；用 socai 采集数据生成"内容数据中台"网页，每次出稿前给出发布建议和拍摄清单；可联网检索优秀案例；记住用户喜欢的对标图和文案。AI 出稿，人工发布。
  当用户发公司简介、要一稿多发、分平台改写、多平台图文、给小红书或抖音或公众号或视频号或携程出稿、看数据复盘、要拍摄建议、查优秀案例、上传喜欢的对标图或文案时使用。
  触发词：一源多创、多平台图文、分平台出稿、发布总览、数据中台、复盘、拍摄建议、优秀案例、对标图、仿版式、喜欢的文案、去AI味。
description_zh: 一份素材生成五个平台的差异化图文稿和配图，交付带一键复制的发布总览网页；采集数据生成数据中台，给出发布建议和拍摄清单；可查优秀案例、记住用户喜欢的风格。AI 出稿，人工发布。
description_en: Turns one source brief into platform-specific image-and-text posts for Douyin, WeChat Channels, WeChat Official Accounts, Xiaohongshu and Ctrip, delivered as an HTML page with copy buttons. Builds a data dashboard with publishing and shot-list advice, researches good cases online, and learns the user's preferred styles. AI drafts, humans publish.
category: writing
version: 0.2.0
author: pengdi190721-dot
allowed-tools: Bash,Read,Write,Glob,Grep
---

# 一源多创 · 多平台图文

## 这个技能做什么

把用户给的一份源素材，改写成五个平台各自的图文稿和配图，交付一个"发布总览"网页，用户点按钮复制、手动发布。用户再次来用时，先用上一次的数据复盘，给出这次的发布建议和拍摄清单。

- 平台：抖音图文、视频号图文、公众号、小红书、携程。
- 只做图文，不做短视频。
- 只出稿，不发布。禁止调用任何平台的发布、评论、点赞、私信接口。
- 不编造。素材和公司资料里没有的价格、日期、设施、数字、经历一律不写，缺什么就写"【待补：xx】"。

## 两个交付网页

| 网页 | 位置 | 由谁生成 | 内容 |
| --- | --- | --- | --- |
| 发布总览.html | `输出/<日期>_<主题>/发布总览.html` | `pack.py`（第 ⑨ 步） | 每个平台一张卡片：标题、正文、话题、配图、"复制全文 / 只复制标题 / 只复制正文"按钮、发布提醒 |
| 内容数据中台.html | `workbench/内容数据中台.html` | `dashboard.py`（第 0 步） | 总览、账号矩阵、平台表现、作品明细、经营基本面、诊断结论、本次发布建议和拍摄清单 |

两个网页都由脚本生成，模型不手写 HTML，也不手写页面上的统计数字。

## 目录约定

- **技能目录**：本 SKILL.md 所在的目录。下文的 `scripts/`、`references/`、`templates/` 都指技能目录里的路径，运行脚本时用绝对路径，例如 `python3 <技能目录>/scripts/lint.py`。
- **用户数据目录**：用户工作目录下的 `yiyuan-data/`，存品牌信息、公司资料、接口配置、字体、最新规则补充。
- **工作台**：用户工作目录下的 `workbench/`，存 socai 数据、数据中台、优秀案例、风格库、账号调性。
- **输出目录**：用户工作目录下的 `输出/<日期>_<主题>/`，每次出稿一个文件夹。

## 每次开始前先检查

```bash
python3 <技能目录>/scripts/setup_check.py --status
```

- `session_type` 为"首次使用"：做"首次运行"。
- `session_type` 为"再次使用"：先做"第 0 步"，再出稿。
- `rules_refresh_due` 为 true（距上次刷新超过 30 天）：提醒用户刷新规则，用户同意就做"首次运行"第 5 步。
- 其余缺项（例如没有字体、没配图片接口）：只补对应的那一步。

## 首次运行（7 步）

1. **建数据目录、检查环境。** 运行 `python3 <技能目录>/scripts/setup_check.py --init-data`。没有 Pillow 就让用户运行 `python3 -m pip install pillow`。没有 socai 就提示用户在 WorkBuddy 技能市场添加"多平台社媒调研-Socai"，或按 https://socai.io/docs/installation/ 安装，装好后在 Chrome 里登录小红书和抖音。谁用这个技能，谁在自己电脑上装。
2. **接入 image2.6。** 问用户要接口地址和模型名，写进 `yiyuan-data/config/image.json`（字段见 `templates/image_config.example.json`）。API Key 由用户自己设置成环境变量 `IMAGE_API_KEY`，禁止让用户把 Key 发在对话里，禁止把 Key 写进任何文件。然后运行 `setup_check.py --test-image` 测一次。
3. **从公司简介建品牌信息。** 按 @templates/brand_onboarding.md：请用户发公司简介，整理出 `yiyuan-data/公司资料.md` 和 `yiyuan-data/brand.md`，只问简介里没有的题，最后请用户确认。
4. **学习账号调性。** 用户给了自家账号，就按 @references/socai-workbench.md 的"账号调性档案"拉取近期作品，生成 `workbench/账号调性/<平台代号>.md`。同时把这批数据按"结果怎么存"的规则存进 `workbench/raw/`，运行 collect_data.py 和 dashboard.py，生成第一版内容数据中台。
5. **搜索最新规则。** 按 @references/rules_refresh.md 搜索，结果写进 `yiyuan-data/rules-latest/<平台代号>.md`，然后运行 `setup_check.py --mark rules_refreshed`。
6. **下载字体。** 运行 `python3 <技能目录>/scripts/fetch_fonts.py --data-dir yiyuan-data`。
7. **初始化报告。** 再跑一次 `setup_check.py --status`，一句话一项讲给用户，问"确认"还是"某一步重来"。确认后运行 `setup_check.py --mark initialized`，并按 brand_onboarding.md 第四步提醒用户可以上传喜欢的对标图和文案。

## 第 0 步：数据复盘与本次发布建议（再次使用时）

按 @references/publish-advice.md 做：

1. 数据不是今天的，先问用户要不要更新；更新就用 socai 采集、存进 `workbench/raw/`，运行 `collect_data.py`。
2. 对比上一次的快照，写 `workbench/数据/诊断结论.json` 和 `workbench/数据/发布建议.json`（含拍摄清单：拍什么、怎么拍、用在哪、预期效果、依据）。
3. 运行 `dashboard.py` 生成内容数据中台。
4. 用 3–5 句话讲结论和建议，告诉用户可以打开 `workbench/内容数据中台.html` 看完整版，再问：按建议出稿 / 用我自己的素材出稿 / 只看数据。

用户还没拍新素材时，把拍摄清单交给用户转给摄影师，这次到此为止；拍好后再来出稿。

## 出稿流程（9 步 + 2 个交互点）

每一步只产出一个文件，写完再进下一步。所有文件写进同一个输出目录。

### 第 ① 步：素材拆解

- 输入：用户给的源素材包（文字、原图，可能还有对标图）、`yiyuan-data/公司资料.md`。
- 动作：按 @templates/content_card.json 填内容卡。事实只能来自本次素材或公司资料，来源写进 `fact_sources`。先数原图：每个卖点对应哪几张原图写进 `photos`，没有原图的卖点写进 `missing_photos`。采用了第 0 步的建议，就在 `advice_ref` 里写上选题。
- 输出：`输出/<日期>_<主题>/00_内容卡.json`。
- 禁止：往内容卡里写素材和公司资料里都没有的事实。

### 第 ② 步：拆解对标图

- 本次用户给了对标图：按 @references/benchmark.md 看图拆解，每张一份 `00_对标拆解_<序号>.json`。
- 本次没给、但风格库里有本平台的对标图：直接用风格库里已有的拆解，不用重拆。
- 都没有就跳过。看不清的写 unknown，不猜。

### 第 ③ 步：对齐选题与优秀案例

- 读 `workbench/数据/发布建议.json`、`workbench/数据/选题样本.csv`（有才读），把相关的选题、评论高频问题、搜索词写进内容卡的 `topic_insights`。
- 这个选题 7 天内没检索过优秀案例，就按 @references/case-research.md 检索一次，记进 `workbench/优秀案例.md`，用到的案例写进内容卡的 `case_refs`。

### 第 ④ 步：逐平台写文案

一次只写一个平台，顺序：小红书 → 抖音图文 → 视频号图文 → 公众号 → 携程。只写品牌信息里勾选过的平台。

每个平台按这个顺序做：

1. 读该平台规则 `references/platform-<平台代号>.md`，以及 `yiyuan-data/rules-latest/<平台代号>.md`（如果有）。
2. 读风格库里本平台和"通用"的文案样本、本平台的账号调性档案，按 @references/style-library.md 的优先级借鉴，只学写法，不搬事实。
3. 读 `yiyuan-data/brand.md`。
4. 从内容卡重新写，按 `templates/<平台代号>_post.json` 的字段填。禁止在上一个平台的稿子上改写。
5. 按 @references/humanizer-zh.md 开头的"改写清单"逐条改一遍。
6. 写进 `<平台目录>/post.json`。

| 平台 | 平台代号 | 平台目录 |
| --- | --- | --- |
| 抖音图文 | douyin | 01_抖音图文 |
| 视频号图文 | shipinhao | 02_视频号图文 |
| 公众号 | gongzhonghao | 03_公众号 |
| 小红书 | xiaohongshu | 04_小红书 |
| 携程 | ctrip | 05_携程 |

### 第 ⑤ 步：写出图指令

- 动作：给 post.json 里 `images` 的每一项填完出图字段（模板 @templates/image_brief.json，规则 @references/image-generation.md）。张数按"有原图支撑的卖点数 + 首图 + 实用信息图"算，并落在平台区间内。
- 有对标拆解（本次的，或风格库里本平台的）：`text_mode` 填"底图叠字"，按拆解填 `text_layers`。
- 禁止：引用不存在的原图；让一张图承载两个卖点。

### 第 ⑥ 步：检查文案

```bash
python3 <技能目录>/scripts/lint.py --run "输出/<日期>_<主题>" --platform <平台代号>
```

- 有 FAIL：按报错逐条改 post.json，再跑一次。同一平台最多改 2 轮，仍有 FAIL 就把问题写进 `needs_human`，继续下一个平台。
- 只有 WARN：逐条判断，确实有问题才改。

### 交互点 A：用户确认文案（在生图之前）

按 @templates/interaction_a.md 逐个平台问用户：选标题、改正文、勾选要出的图、原图不够时补不补。用户的选择写回 post.json，并追加到 `交互记录.md`。全部平台确认后才进入第 ⑦ 步。

### 第 ⑦ 步：生成图片

```bash
python3 <技能目录>/scripts/gen_image.py --run "输出/<日期>_<主题>" --platform <平台代号>
```

- 脚本按固定模板拼提示词，以原图为参考调用 image2.6，按最高分辨率存母版图，再导出平台尺寸并加"AI 生成"标识。
- `text_mode` 为"底图叠字"时，脚本先生成无字底图，再自动叠字。
- 只重做某一张：加 `--slot <slot 名>`。先看提示词不调接口：加 `--dry-run`。

### 第 ⑧ 步：看图自查

逐张打开导出的图片，按 @templates/self_check.md 的"看图"部分逐条回答是或否。任一项为"否"：用 `--slot` 重新生成这一张，最多 3 次；直接画字 3 次都有错字，就改成"底图叠字"再生成；仍不合格就写进 `needs_human`。

### 第 ⑨ 步：打包交付

```bash
python3 <技能目录>/scripts/lint.py --run "输出/<日期>_<主题>"
python3 <技能目录>/scripts/pack.py --run "输出/<日期>_<主题>"
```

lint 不带 `--platform` 会检查全部平台和平台间重复度。pack 生成主交付物 `发布总览.html`，以及各平台的纯文本发布文案和 `07_交付清单.md`。

### 交互点 B：用户确认成品

按 @templates/interaction_b.md 展示每张图、文案终稿和审核报告摘要，逐张确认，确认发布声明。用户的选择追加到 `交互记录.md`。全部处理完再跑一次第 ⑨ 步，最后按 interaction_b.md 的"结束语"告诉用户：打开发布总览.html 复制发布；可以随时上传喜欢的对标图和文案；明天回来看数据复盘。

## 随时可以做的事

用户在任何时候提出下面的要求，直接按对应规则做，不必走完整流程：

| 用户说 | 怎么做 |
| --- | --- |
| "去网上查一查优秀案例" | 按 @references/case-research.md 检索并总结 |
| 发来喜欢的对标图或文案 | 按 @references/style-library.md 先问用在哪个平台，再存进风格库 |
| "看看数据""复盘一下" | 做第 0 步 |
| "该拍什么""给摄影师的建议" | 做第 0 步，重点讲拍摄清单 |
| "刷新一下平台规则" | 做首次运行第 5 步 |

## 执行规范

1. 一步只产出一个文件，写完再进下一步。
2. 输出一律按 templates 里的字段填写，不增删字段，字数不超上限。
3. 规则里写"必须"的必须做，写"禁止"的一律不做。
4. 每次只读当前平台的 references 文件，不同时加载五个平台。
5. 每篇文案先过去 AI 味清单，再交给 lint.py。
6. 看图任务用固定提问，按字段回答，看不清写 unknown。
7. 字数、禁用词、尺寸、重复度、照抄由 lint.py 判定；统计数字由 collect_data.py 和 dashboard.py 计算，不靠自己判断或手写。
8. 失败处理按上面写死的次数，达到上限就写进 `needs_human`，继续下一个平台。
9. 缺信息写"【待补：xx】"，禁止猜；建议和结论必须写依据。
10. 和用户交互时，能给选项就给选项（WorkBuddy 支持选项卡片就用卡片，不支持就用编号让用户回复数字）。

## 文件索引

- 平台规则：`references/platform-douyin.md`、`platform-shipinhao.md`、`platform-gongzhonghao.md`、`platform-xiaohongshu.md`、`platform-ctrip.md`
- 合规：@references/compliance.md；禁用词：`references/banned_words.txt`
- 去 AI 味：@references/humanizer-zh.md
- 图片：@references/image-generation.md；对标：@references/benchmark.md；字体：@references/fonts.md
- 数据：@references/socai-workbench.md；复盘与发布建议：@references/publish-advice.md
- 优秀案例：@references/case-research.md；风格库：@references/style-library.md
- 规则刷新：@references/rules_refresh.md
- 模板：`templates/` 下的全部文件
- 脚本：`setup_check.py`、`fetch_fonts.py`、`collect_data.py`、`dashboard.py`、`gen_image.py`、`overlay_text.py`、`lint.py`、`pack.py`、`render_publish.py`

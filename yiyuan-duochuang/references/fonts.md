# 字体白名单

下面 8 款字体都是 SIL Open Font License 1.1 开源协议，可以免费商用。`scripts/fetch_fonts.py` 只下载这 8 款，存到 `yiyuan-data/fonts/`。

| 字体 | 文件名 | 风格类别 | 适合 | 下载来源 |
| --- | --- | --- | --- | --- |
| 思源黑体（Noto Sans SC） | NotoSansSC.ttf | 无衬线 | 通用正文、信息图、"AI 生成"标识 | Google Fonts（GitHub google/fonts） |
| 思源宋体（Noto Serif SC） | NotoSerifSC.ttf | 宋体 | 杂志感标题、公众号封面 | Google Fonts |
| 得意黑 | SmileySans-Oblique.ttf | 斜体粗标题 | 醒目的封面大字 | GitHub atelier-anchor/smiley-sans |
| 霞鹜文楷 | LXGWWenKai-Regular.ttf | 手写楷书 | 文艺、温柔的说明文字 | GitHub lxgw/LxgwWenKai |
| 站酷快乐体 | ZCOOLKuaiLe-Regular.ttf | 圆润可爱 | 亲子、轻松的标签 | Google Fonts |
| 站酷庆科黄油体 | ZCOOLQingKeHuangYou-Regular.ttf | 粗壮醒目 | 价格、促销信息 | Google Fonts |
| 站酷小薇 | ZCOOLXiaoWei-Regular.ttf | 文艺宋体 | 文艺风标题 | Google Fonts |
| 马善政毛笔 | MaShanZheng-Regular.ttf | 毛笔书法 | 国风、景区 | Google Fonts |

## 选字体的规则

1. 对标拆解里的 `font_style` 只能填上表"风格类别"一列中的一项；看不出来填"无衬线"。
2. 叠字时按 `font_style` 选上表对应的字体。
3. 对标图用的若是方正、汉仪、造字工房等商用字体，禁止下载、禁止仿冒，选上表风格最接近的一款。
4. 用户自己有授权的字体可以放进 `yiyuan-data/fonts/`，并在 `yiyuan-data/brand.md` 的"## 授权字体"一节登记字体名、文件名和授权说明，之后可在 `text_layers` 里直接写文件名。

## 授权

SIL Open Font License 1.1 允许免费使用、嵌入、再分发，不允许单独售卖字体文件本身。详见 https://openfontlicense.org 。

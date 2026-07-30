# translate-academic-paper-zh

面向 Codex 的英文学术论文中文翻译 Skill。它将论文来源识别、结构化提取、术语管理、全文翻译、学术排版、PDF 检查和可编辑源文件打包串成一条可复用工作流。

目标不是逐句直译，而是在合理范围内完整保留论文的：

- 标题、作者、单位、摘要和关键词；
- 章节层级、编号、脚注、附录和补充材料；
- LaTeX/MathML 公式、变量、运算符和公式编号；
- 表格结构、数值、模型名、数据集名和指标；
- 图片、图注、表注和交叉引用；
- 引文顺序、参考文献、URL 和 DOI；
- 正式、自然、术语一致的中文学术表达。

默认交付中文 PDF、可编辑 HTML ZIP 和来源/已知限制说明；复杂公式或超宽表格不适合 Word 时，不会为了生成 DOCX 而牺牲内容保真度。

## 与 Paper-Translator 的关系

本项目沿用了 [Prozacc/Paper-Translator](https://github.com/Prozacc/Paper-Translator) 的核心思想：

- 阅读并翻译整篇论文，不省略附录、脚注或补充材料；
- 建立术语表并保持全文一致；
- 保留公式、表格、图片和参考文献；
- 以语义化 HTML 作为排版基础；
- 输出适合阅读和打印的中文 PDF。

在此基础上，本项目针对实际论文翻译增加了：

- 输入论文的标题、作者、版本、页数和来源核对；
- LaTeX、结构化 HTML、数字 PDF 和 OCR 的来源优先级；
- 公式、引用、单位、模型名和数据集名的占位保护；
- 文本去重、批量翻译和本地缓存指导；
- 私密论文与公共翻译服务之间的授权边界；
- 大型本地翻译模型和依赖下载限制；
- Paged.js 截断长表格时的浏览器原生 A4 打印回退；
- HTML/PDF 结构统计、缺失资源和乱码检查；
- PDF 全页视觉检查和交付限制披露；
- 可编辑 HTML 资源包的确定性打包脚本。

它是一个 Codex 工作流 Skill，不是翻译模型，也不是常驻 MCP 服务。

## 快速安装

仓库根目录本身就是 Skill 目录。将仓库克隆到 Codex 的个人 Skills 目录：

### Windows PowerShell

```powershell
git clone https://github.com/Prozacc/translate-academic-paper-zh.git `
  "$env:USERPROFILE\.codex\skills\translate-academic-paper-zh"
```

### macOS / Linux

```bash
git clone https://github.com/Prozacc/translate-academic-paper-zh.git \
  ~/.codex/skills/translate-academic-paper-zh
```

如果已经安装，可在 Skill 目录中更新：

```bash
git pull --ff-only
```

重新打开一个 Codex 任务后，Skill 会以 `translate-academic-paper-zh` 出现在可用 Skills 中。

## 使用方式

显式调用：

```text
使用 $translate-academic-paper-zh 把这个英文论文 PDF 翻译成中文，
保留公式、表格、图片、参考文献和附录，输出 PDF 和可编辑 HTML。
```

也可以使用自然语言：

```text
用论文翻译 Skill 翻译这个 PDF。
```

```text
把这篇 arXiv 论文完整翻译成中文，术语保持一致，
图注和表头需要翻译，参考文献保留原文。
```

```text
离线翻译这篇未发表论文，不允许发送到公共翻译服务。
如需下载本地模型，先告诉我大小并征得同意。
```

## 工作流程

```text
确认论文来源与版本
  → 选择 LaTeX / 结构化 HTML / 数字 PDF / OCR
  → 统计章节、图片、表格、公式、参考文献和附录
  → 建立论文专属术语表并保护不可翻译内容
  → 对文本节点去重、分批翻译并缓存
  → 生成语义化中文 HTML
  → 渲染 A4 PDF
  → 自动验证结构和资源
  → 渲染全部 PDF 页面并进行视觉检查
  → 打包 PDF、可编辑 HTML ZIP 和限制说明
```

来源优先级：

1. 原始 LaTeX 或官方源代码包；
2. 带 MathML 的结构化 HTML；
3. 文本层可靠的数字 PDF；
4. 扫描 PDF 的 OCR 结果。

当上传附件不可访问时，Skill 不会静默替换文件。只有在标题和作者能够核对一致时，才会使用官方版本继续处理，并在最终交付中明确说明替代来源。

## 默认翻译策略

- 标题、摘要、正文、标题层级、图注、表头、表注和附录正文翻译为中文。
- 公式、变量、数字、单位、代码、Citation Key、URL 和 DOI 保持不变。
- 模型名、数据集名、库名、会议名和公认缩写保留其规范写法。
- 参考文献默认保留原始书目信息，便于检索；只有用户明确要求时才翻译文献标题。
- 首次出现的专业术语可使用“中文（英文或缩写）”，后续使用统一中文术语或标准缩写。
- 图片内部嵌入的英文默认不重绘；翻译图注并在交付说明中标记图内英文。

基础术语映射见 [`references/terminology.md`](references/terminology.md)。每篇论文仍需根据研究方向补充专属术语。

## 安全与性能约束

- 未经用户明确同意，不下载本地翻译模型、模型权重或超过 100 MB 的依赖包。
- 未经用户明确同意，不把私密、未发表或内部论文发送到公共翻译服务。
- 优先复用当前工作区已经具备的 PDF、浏览器和文档能力。
- 对重复文本去重并批量翻译，避免逐句网络调用。
- 缓存已完成的翻译，失败重试时不从头处理整篇论文。
- 中间文件与最终交付文件分开保存，避免把缓存或原论文误当成发布文件。

## 输出内容

标准交付包括：

1. 中文翻译 PDF；
2. 可编辑 HTML 及其图片、样式资源 ZIP；
3. 来源、版本和已知限制说明；
4. DOCX（仅在用户要求且公式、表格能够可靠转换时提供）。

翻译后页数可能与原文不同。Skill 保留阅读顺序、章节层级、编号和内容组织，但不会为了逐页一一对应而压缩或删除内容。

## 辅助脚本

### 验证 HTML 和 PDF

```bash
python scripts/validate_delivery.py \
  --html path/to/translated.html \
  --pdf path/to/translated.pdf
```

检查内容包括：

- 标题、图片、表格、MathML 和参考文献数量；
- 中文字符和残余英文概况；
- 本地图片、样式等资源是否缺失；
- Unicode 替换字符或潜在乱码；
- PDF 是否存在、页数和加密状态。

`pypdf` 可用时会检查 PDF 页数和加密状态；没有安装时，其余 HTML 检查仍然可以运行。

### 打包可编辑 HTML

```bash
python scripts/package_html.py \
  --html path/to/translated.html \
  --output path/to/editable-html.zip
```

脚本会：

- 收集 HTML 引用的本地图片、脚本和样式；
- 保持相对目录结构；
- 拒绝不安全的绝对路径或上级目录引用；
- 在资源缺失时终止，而不是生成不完整的 ZIP。

## 质量检查

自动验证不能替代视觉检查。发布 PDF 前应将全部页面渲染成图片或联系表，并检查：

- 是否有空白页、裁切、文字重叠或缺字；
- 每个图、表和公式是否存在且编号正确；
- 超宽表格是否仍然可读；
- 标题是否悬空在页面底部；
- 摘要、章节首段、图注、表头、附录和最后一条参考文献是否完整；
- 关键术语、否定关系、比较结论、百分比和单位是否与原文一致。

完整发布检查清单见 [`references/quality-checklist.md`](references/quality-checklist.md)。

## 目录结构

```text
translate-academic-paper-zh/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ assets/
│  └─ paper-zh.css
├─ references/
│  ├─ workflow.md
│  ├─ terminology.md
│  └─ quality-checklist.md
└─ scripts/
   ├─ validate_delivery.py
   └─ package_html.py
```

## 当前边界

- 本项目不内置翻译模型，也不提供固定的第三方翻译 API。
- 翻译质量仍取决于当前 Codex 模型、论文领域、术语表和人工复核。
- PDF 生成依赖运行环境提供的浏览器或 PDF 工具。
- 扫描论文、复杂多栏版式、跨页超宽表格和图片内文字可能需要额外人工处理。
- 自动检查能够发现缺失资源和部分结构问题，但不能证明所有学术含义都翻译正确。

详细执行规则见 [`SKILL.md`](SKILL.md) 和 [`references/workflow.md`](references/workflow.md)。

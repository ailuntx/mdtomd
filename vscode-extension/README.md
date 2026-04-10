# mdtomd

在 VS Code 里直接翻译 Markdown。

安装后，你可以右键 `.md`、`.markdown`、`.mdx` 文件或文件夹，先看待翻译文件数量、token 和价格估算，再选择模型开始翻译。

## 适合什么场景

- 想在 VS Code 里直接翻译单个 Markdown 文件
- 想批量翻译一个文档目录
- 想先比较不同模型价格，再决定用哪一个
- 已经在项目里用 `config.yaml`，希望在编辑器里直接调用

## 第一次使用

1. 安装扩展
2. 打开 VS Code 设置，搜索 `mdtomd`
3. 在你要使用的厂商分组里填写 `model` 和 `apiKey`

也可以不直接填写 `apiKey`，改为填写 `apiKeyEnv`，然后在系统环境变量里准备好对应的 key。

如果当前项目里已经有 `config.yaml`，扩展也会读取里面的 `providers` 配置。

## 使用方式

1. 在资源管理器里右键 Markdown 文件或文件夹
2. 选择 `mdtomd: 翻译 Markdown`
3. 先查看本次翻译的文件数、token 和价格参考
4. 点“继续”后，从已配置可用 key 的模型里选择一个
5. 点“开始翻译”

## 你会看到什么

- 翻译前估算：文件数、分块数、token、推荐模型价格参考
- 模型选择：只显示已经配置好可用 key 的模型
- 翻译结果：状态栏显示完成情况，失败时可在输出面板查看详情

## 配置说明

扩展设置页已经按厂商分组，普通使用只需要关心这些字段：

- `model`
- `apiKey` 或 `apiKeyEnv`
- `baseUrl`
- `maxTokens`

如果没有单独设置 `chunk_size`，CLI 会默认使用当前模型的 `max_tokens` 作为分块大小。

当前支持这些厂商分组：

- DeepSeek
- MiniMax
- OpenAI
- OpenAI Codex
- OpenRouter
- Anthropic
- Gemini
- Z.ai
- Kimi
- Alibaba
- OpenAI Compatible

## 自动安装 CLI

扩展会自动检查本机是否已安装 `mdtomd` CLI。

如果没有安装，会自动执行：

```bash
python -m pip install --user -U mdtomd
```

安装完成后会继续执行翻译。

## 常见问题

### 为什么“继续”后看不到模型列表？

因为还没有配置可用模型。请先在 VS Code 设置里填写：

- `model`
- `apiKey`

或者填写：

- `model`
- `apiKeyEnv`

并确保对应环境变量真实存在。

### 没有 `config.yaml` 也能用吗？

可以。没有项目配置时，扩展会直接使用 VS Code 设置里的模型参数和目标语言。

### 默认目标语言是什么？

默认是 `Chinese`，可以在设置里的 `mdtomd.targetLanguage` 下拉框里修改。

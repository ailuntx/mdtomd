# mdtomd

在 VS Code 里直接翻译 Markdown。

右键 `.md`、`.markdown`、`.mdx` 文件或文件夹，先看估算，再选模型，再开始翻译。

![操作演示](https://raw.githubusercontent.com/ailuntx/mdtomd/main/vscode-extension/media/readme-demo.gif)

## 适合什么场景

- 在编辑器里直接翻译单个 Markdown
- 批量翻译文档目录
- 先比较不同模型价格，再决定用哪一个
- 复用项目里的 `config.yaml`

## 第一次使用

1. 安装扩展
2. 打开 VS Code 设置，搜索 `mdtomd`
3. 在目标厂商分组里填写 `model`
4. 再填写 `apiKey` 或 `apiKeyEnv`

如果项目里已经有 `config.yaml`，扩展也会读取里面的 `providers`。
目标语言和输出后缀以 VS Code 设置为准，会覆盖 `config.yaml` 里的默认值。

## 使用方式

1. 右键 Markdown 文件或文件夹
2. 选择 `mdtomd: 翻译 Markdown`
3. 查看文件数、token 和价格参考
4. 点“继续”后选择模型
5. 点“开始翻译”

## 你会看到什么

- 估算信息：文件数、分块数、token、价格参考
- 模型列表：只显示已经配置好可用 key 的模型
- 实时进度：provider / model、总 chunk、当前文件、当前分块
- 取消按钮：中途可直接终止当前翻译

## CLI 自动安装 / 同步

扩展不会在 VS Code 启动时自动打扰你。

真正执行翻译命令时才会检查 CLI：

- 没安装就自动安装
- 版本不匹配就自动同步到兼容版本
- 如果你固定了 `mdtomd.cliPath`，扩展不会擅自改动那个 CLI

自动安装 / 同步本质上执行的是：

```bash
python -m pip install --user -U mdtomd
```

## 常用设置

普通使用主要关心这些项：

- `targetLanguage`
- `languageSuffixes`
- `translatedSuffixAliases`
- 各厂商分组里的 `model`
- 各厂商分组里的 `apiKey` 或 `apiKeyEnv`
- `baseUrl`
- `maxTokens`

如果没有单独设置 `chunk_size`，CLI 会默认使用当前模型的 `max_tokens` 作为分块大小。

## 常见问题

### 为什么“继续”后看不到模型列表？

因为还没有配置可用模型。先在设置里填写：

- `model`
- `apiKey`

或者：

- `model`
- `apiKeyEnv`

并确保对应环境变量真实存在。

### 没有 `config.yaml` 也能用吗？

可以。没有项目配置时，扩展会直接使用 VS Code 设置里的模型参数和目标语言。

### 默认目标语言是什么？

默认是 `Chinese`，可以在 `mdtomd.targetLanguage` 下拉框里修改。

### 为什么有些已经翻译过的文件还是被算进去了？

可以在 `mdtomd.translatedSuffixAliases` 里补充已翻译后缀别名。

例如：

```json
{
  "Chinese": "cn, chinese"
}
```

这样 `_cn`、`_CN`、`_chinese` 这类文件会被当成已翻译结果跳过。

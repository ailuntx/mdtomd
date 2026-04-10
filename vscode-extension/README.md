# mdtomd VS Code Extension

一个很薄的 VS Code 壳，所有翻译逻辑都继续走 `mdtomd` CLI。

插件首次安装后会检查 `mdtomd` CLI；如果本机还没有，会先尝试自动安装，再继续执行翻译。

## 调试

直接用 VS Code 打开当前目录，按 `F5` 即可。

如果当前目录没有 `config.yaml`，插件会使用 VS Code 设置里的 `mdtomd.targetLanguage`，这是一个下拉项，默认是 `Chinese`。

插件流程：

1. 先调用 `estimate --json`
2. 弹出待翻译文件信息和 10 个推荐模型价格参考
3. 点“继续”后选择实际用于翻译的模型配置
4. 再点“开始翻译”

## 厂商配置

直接在 VS Code 设置面板里搜 `mdtomd` 即可，设置页现在会按“通用 + 各厂商”分组显示，不需要手改 `settings.json`。

当前已内置这些厂商分组：

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

普通厂商都可以直接填写：

- `model`
- `baseUrl`
- `apiKey`
- `apiKeyEnv`
- `apiMode`
- `maxTokens`

如果没有单独指定 `chunk_size`，CLI 会默认用当前模型的 `max_tokens` 作为分块大小。

其中 OpenAI Codex 额外支持：

- `codexHome`
- `authFile`

如果当前目录已有 `config.yaml`，插件也会继续读取其中的 `providers` 配置。

## 打包

```bash
cd /Volumes/usb_main/home/template_paper/mdtomd/vscode-extension
npm run package
```

会在当前目录生成 `mdtomd-vscode.vsix`。

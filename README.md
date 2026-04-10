# mdtomd

一个给自己用的 Markdown/MDX 翻译工具。

默认会读取当前目录的 `config.yaml`，支持：

- 单文件翻译
- 目录批量翻译
- `.md` / `.markdown` / `.mdx`
- 翻译前 token 估算
- 翻译后显示输入 / 输出 token

**安装**

发布版安装：

```bash
python3 -m pip install mdtomd
```

本地开发安装：

```bash
python3 -m pip install -e .
```

如果想尽量自动把 `mdtomd` 放进当前机器的可执行路径：

```bash
./scripts/install_cli.sh
```

**配置**

直接改 `config.yaml` 即可。

常见方式：

1. 在 `providers.<provider>` 里写 `model/base_url/api_key/max_tokens`
2. 在 `llm.provider` 里选默认 provider
3. `translator.chunk_size` 留空时，会默认跟当前模型的 `max_tokens` 一致
4. 临时覆盖时再用命令行参数或环境变量

如果不想把 key 写进配置，可以用环境变量，例如：

```bash
export DEEPSEEK_API_KEY="your-key"
```

**用法**

快捷命令，先 estimate 再 translate：

```bash
mdtomd examples/doc1.md
mdtomd examples
```

单文件翻译：

```bash
mdtomd translate -i examples/doc1.md
```

目录翻译：

```bash
mdtomd translate -i examples
```

目录输入会自动递归处理，并默认把结果写回原目录，生成 `*_zh.md` / `*_zh.mdx`。

如果想输出到别的目录：

```bash
mdtomd translate -i examples --output-dir out
```

先看 token：

```bash
mdtomd estimate -i examples/doc1.md
mdtomd estimate -i examples
```

给插件或脚本用结构化输出：

```bash
mdtomd estimate -i examples/doc1.md --json
mdtomd translate -i examples/doc1.md --json
```

查看 provider 和模型：

```bash
mdtomd providers
mdtomd models
```

**输出说明**

单文件翻译完成后会额外打印：

- `原文 tokens`
- `请求输入 tokens`
- `回复输出 tokens`

其中：

- `请求输入 tokens` 是按当前 prompt 和分块策略统计的输入 token
- `回复输出 tokens` 是模型接口实际返回的 completion token

**测试**

```bash
python3 -m unittest discover -s tests -v
```

**CLI 发布**

构建并检查产物：

```bash
./scripts/build_cli.sh
```

上传到 PyPI：

```bash
export TWINE_PASSWORD="pypi-***"
./scripts/publish_cli.sh
```

**VS Code 插件**

插件目录在 `vscode-extension/`。

本地调试：
直接用 VS Code 打开 `vscode-extension` 目录，按 `F5` 启动 Extension Development Host。

打包：

```bash
cd vscode-extension
npm run package
```

当前插件已支持：

- 文件树右键翻译 Markdown 文件
- 文件树右键翻译文件夹
- 首次安装后自动检测 CLI，缺失时会优先尝试自动安装
- 先调用 `estimate --json` 弹确认框
- 从 `config.yaml` 已配模型里选择
- 直接在 VS Code 设置面板里按“通用 + 厂商分组”填写模型参数，不需要手改 `settings.json`
- 支持 DeepSeek、MiniMax、OpenAI、OpenAI Codex、OpenRouter、Anthropic、Gemini、Z.ai、Kimi、Alibaba、OpenAI Compatible
- 调用 `translate --json`
- 状态栏显示完成结果

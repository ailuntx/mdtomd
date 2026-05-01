# mdtomd

Markdown / MDX 翻译工具，提供 CLI 和 VS Code 插件两种用法。

支持：

- 单文件、目录、glob 批量翻译
- `estimate` 先看 token 和价格
- `translate` 正式翻译
- `--json` 结构化输出
- 多厂商 LLM

**安装**

```bash
python3 -m pip install mdtomd
```

如果想尽量把 `mdtomd` 放进当前机器的可执行路径：

```bash
./scripts/install_cli.sh
```

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_cli.ps1
```

**配置**

默认读取当前目录的 `config.yaml`。

常见配置点：

- `llm.provider` 选择默认 provider
- `providers.<provider>` 配 `model/base_url/api_key/max_tokens`
- `translator.chunk_size` 留空时，默认跟当前模型的 `max_tokens` 一致

如果不想把 key 写进配置，可以用环境变量：

```bash
export DEEPSEEK_API_KEY="your-key"
```

**常用命令**

先估算再翻译：

```bash
mdtomd examples/doc1.md
mdtomd examples
```

只看估算：

```bash
mdtomd estimate -i examples/doc1.md
mdtomd estimate -i examples
```

正式翻译：

```bash
mdtomd translate -i examples/doc1.md
mdtomd translate -i examples
```

输出到别的目录：

```bash
mdtomd translate -i examples --output-dir out
```

结构化输出：

```bash
mdtomd estimate -i examples/doc1.md --json
mdtomd translate -i examples/doc1.md --json
```

查看能力：

```bash
mdtomd providers
mdtomd models
mdtomd --version
```

**行为说明**

- 目录输入会递归处理 `.md` / `.markdown` / `.mdx`
- 默认回写源目录，生成 `*_zh.md` 这类文件
- 会自动跳过 `node_modules`
- 会跳过空 Markdown
- 单文件输出里会显示 `原文 tokens`、`请求输入 tokens`、`回复输出 tokens`

**VS Code 插件**

插件目录在 `vscode-extension/`。

![VS Code 插件演示](https://raw.githubusercontent.com/ailuntx/mdtomd/main/vscode-extension/media/readme-demo.gif)

当前插件支持：

- 右键翻译 Markdown 文件或文件夹
- 先估算，再选模型
- 实际使用时按需安装 / 同步 CLI
- 只显示已配置可用 key 的模型
- 实时进度和取消
- 语言后缀与已翻译别名设置

**开发**

测试：

```bash
python3 -m unittest discover -s tests -v
```

构建 CLI：

```bash
./scripts/build_cli.sh
```

发布 CLI：

```bash
export TWINE_PASSWORD="pypi-***"
./scripts/publish_cli.sh
```

# mdtomd

一个给自己用的 Markdown/MDX 翻译工具。

默认会读取当前目录的 [config.yaml](/Volumes/usb_main/home/template_paper/mdtomd/config.yaml)，支持：

- 单文件翻译
- 目录批量翻译
- `.md` / `.markdown` / `.mdx`
- 翻译前 token 估算
- 翻译后显示输入 / 输出 token

**安装**

```bash
cd /Volumes/usb_main/home/template_paper/mdtomd
python3 -m pip install -r requirements.txt
```

**配置**

直接改 [config.yaml](/Volumes/usb_main/home/template_paper/mdtomd/config.yaml) 即可。

常见方式：

1. 在 `providers.<provider>` 里写 `model/base_url/api_key/max_tokens`
2. 在 `llm.provider` 里选默认 provider
3. 临时覆盖时再用命令行参数或环境变量

如果不想把 key 写进配置，可以用环境变量，例如：

```bash
export DEEPSEEK_API_KEY="your-key"
```

**用法**

单文件翻译：

```bash
python3 -m mdtomd translate -i examples/doc1.md
```

目录翻译：

```bash
python3 -m mdtomd translate -i examples
```

目录输入会自动递归处理，并默认把结果写回原目录，生成 `*_zh.md` / `*_zh.mdx`。

如果想输出到别的目录：

```bash
python3 -m mdtomd translate -i examples --output-dir out
```

先看 token：

```bash
python3 -m mdtomd estimate -i examples/doc1.md
python3 -m mdtomd estimate -i examples
```

查看 provider 和模型：

```bash
python3 -m mdtomd providers
python3 -m mdtomd models
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

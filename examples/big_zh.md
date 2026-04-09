---
name: 实现-llms-litgpt
description: 使用 Lightning AI 的 LitGPT 实现和训练 LLM，支持 20+ 预训练架构（Llama、Gemma、Phi、Qwen、Mistral）。适用于需要简洁模型实现、架构教学理解或使用 LoRA/QLoRA 进行生产级微调的场景。单文件实现，无抽象层。
version: 1.0.0
author: Orchestra Research
license: MIT
tags: [模型架构, LitGPT, Lightning AI, LLM 实现, LoRA, QLoRA, 微调, Llama, Gemma, Phi, Mistral, 教学]
dependencies: [litgpt, torch, transformers]
---

# LitGPT - 简洁的 LLM 实现

## 快速开始

LitGPT 提供 20+ 预训练 LLM 实现，代码清晰易读，并包含生产就绪的训练工作流。

**安装**：
```bash
pip install 'litgpt[extra]'
```

**加载并使用任意模型**：
```python
from litgpt import LLM

# 加载预训练模型
llm = LLM.load("microsoft/phi-2")

# 生成文本
result = llm.generate(
    "法国的首都是哪里？",
    max_new_tokens=50,
    temperature=0.7
)
print(result)
```

**列出可用模型**：
```bash
litgpt download list
```

## 常用工作流

### 工作流 1：在自定义数据集上微调

复制此清单：

```
微调设置：
- [ ] 步骤 1：下载预训练模型
- [ ] 步骤 2：准备数据集
- [ ] 步骤 3：配置训练
- [ ] 步骤 4：运行微调
```

**步骤 1：下载预训练模型**

```bash
# 下载 Llama 3 8B
litgpt download meta-llama/Meta-Llama-3-8B

# 下载 Phi-2（更小、更快）
litgpt download microsoft/phi-2

# 下载 Gemma 2B
litgpt download google/gemma-2b
```

模型将保存到 `checkpoints/` 目录。

**步骤 2：准备数据集**

LitGPT 支持多种格式：

**Alpaca 格式**（指令-回复）：
```json
[
  {
    "instruction": "法国的首都是哪里？",
    "input": "",
    "output": "法国的首都是巴黎。"
  },
  {
    "instruction": "翻译成西班牙语：你好，最近怎么样？",
    "input": "",
    "output": "Hola, ¿cómo estás?"
  }
]
```

保存为 `data/my_dataset.json`。

**步骤 3：配置训练**

```bash
# 全参数微调（7B 模型需要 40GB+ GPU）
litgpt finetune \
  meta-llama/Meta-Llama-3-8B \
  --data JSON \
  --data.json_path data/my_dataset.json \
  --train.max_steps 1000 \
  --train.learning_rate 2e-5 \
  --train.micro_batch_size 1 \
  --train.global_batch_size 16

# LoRA 微调（高效，16GB GPU）
litgpt finetune_lora \
  microsoft/phi-2 \
  --data JSON \
  --data.json_path data/my_dataset.json \
  --lora_r 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --train.max_steps 1000 \
  --train.learning_rate 1e-4
```

**步骤 4：运行微调**

训练自动将检查点保存到 `out/finetune/`。

监控训练：
```bash
# 查看日志
tail -f out/finetune/logs.txt

# TensorBoard（如果使用 --train.logger_name tensorboard）
tensorboard --logdir out/finetune/lightning_logs
```

### 工作流 2：单 GPU 上的 LoRA 微调

最节省内存的选项。

```
LoRA 训练：
- [ ] 步骤 1：选择基础模型
- [ ] 步骤 2：配置 LoRA 参数
- [ ] 步骤 3：使用 LoRA 训练
- [ ] 步骤 4：合并 LoRA 权重（可选）
```

**步骤 1：选择基础模型**

对于有限 GPU 内存（12-16GB）：
- **Phi-2** (2.7B) - 最佳质量/大小权衡
- **Llama 3 1B** - 最小、最快
- **Gemma 2B** - 推理能力良好

**步骤 2：配置 LoRA 参数**

```bash
litgpt finetune_lora \
  microsoft/phi-2 \
  --data JSON \
  --data.json_path data/my_dataset.json \
  --lora_r 16 \          # LoRA 秩（8-64，越高容量越大）
  --lora_alpha 32 \      # LoRA 缩放（通常为 2×r）
  --lora_dropout 0.05 \  # 防止过拟合
  --lora_query true \    # 对查询投影应用 LoRA
  --lora_key false \     # 通常不需要
  --lora_value true \    # 对值投影应用 LoRA
  --lora_projection true \  # 对输出投影应用 LoRA
  --lora_mlp false \     # 通常不需要
  --lora_head false      # 通常不需要
```

LoRA 秩指南：
- `r=8`：轻量级，2-4MB 适配器
- `r=16`：标准，质量良好
- `r=32`：高容量，用于复杂任务
- `r=64`：最高质量，适配器大 4 倍

**步骤 3：使用 LoRA 训练**

```bash
litgpt finetune_lora \
  microsoft/phi-2 \
  --data JSON \
  --data.json_path data/my_dataset.json \
  --lora_r 16 \
  --train.epochs 3 \
  --train.learning_rate 1e-4 \
  --train.micro_batch_size 4 \
  --train.global_batch_size 32 \
  --out_dir out/phi2-lora

# 内存使用：Phi-2 带 LoRA 约 8-12GB
```

**步骤 4：合并 LoRA 权重**（可选）

将 LoRA 适配器合并到基础模型以进行部署：

```bash
litgpt merge_lora \
  out/phi2-lora/final \
  --out_dir out/phi2-merged
```

现在使用合并后的模型：
```python
from litgpt import LLM
llm = LLM.load("out/phi2-merged")
```

### 工作流 3：从零开始预训练

在您的领域数据上训练新模型。

```
预训练：
- [ ] 步骤 1：准备预训练数据集
- [ ] 步骤 2：配置模型架构
- [ ] 步骤 3：设置多 GPU 训练
- [ ] 步骤 4：启动预训练
```

**步骤 1：准备预训练数据集**

LitGPT 期望分词后的数据。使用 `prepare_dataset.py`：

```bash
python scripts/prepare_dataset.py \
  --source_path data/my_corpus.txt \
  --checkpoint_dir checkpoints/tokenizer \
  --destination_path data/pretrain \
  --split train,val
```

**步骤 2：配置模型架构**

编辑配置文件或使用现有配置：

```python
# config/pythia-160m.yaml
model_name: pythia-160m
block_size: 2048
vocab_size: 50304
n_layer: 12
n_head: 12
n_embd: 768
rotary_percentage: 0.25
parallel_residual: true
bias: true
```

**步骤 3：设置多 GPU 训练**

```bash
# 单 GPU
litgpt pretrain \
  --config config/pythia-160m.yaml \
  --data.data_dir data/pretrain \
  --train.max_tokens 10_000_000_000

# 使用 FSDP 的多 GPU
litgpt pretrain \
  --config config/pythia-1b.yaml \
  --data.data_dir data/pretrain \
  --devices 8 \
  --train.max_tokens 100_000_000_000
```

**步骤 4：启动预训练**

对于集群上的大规模预训练：

```bash
# 使用 SLURM
sbatch --nodes=8 --gpus-per-node=8 \
  pretrain_script.sh

# pretrain_script.sh 内容：
litgpt pretrain \
  --config config/pythia-1b.yaml \
  --data.data_dir /shared/data/pretrain \
  --devices 8 \
  --num_nodes 8 \
  --train.global_batch_size 512 \
  --train.max_tokens 300_000_000_000
```

### 工作流 4：转换和部署模型

导出 LitGPT 模型用于生产。

```
模型部署：
- [ ] 步骤 1：本地测试推理
- [ ] 步骤 2：量化模型（可选）
- [ ] 步骤 3：转换为 GGUF（用于 llama.cpp）
- [ ] 步骤 4：通过 API 部署
```

**步骤 1：本地测试推理**

```python
from litgpt import LLM

llm = LLM.load("out/phi2-lora/final")

# 单次生成
print(llm.generate("什么是机器学习？"))

# 流式生成
for token in llm.generate("解释量子计算", stream=True):
    print(token, end="", flush=True)

# 批量推理
prompts = ["你好", "再见", "谢谢"]
results = [llm.generate(p) for p in prompts]
```

**步骤 2：量化模型**（可选）

以最小质量损失减少模型大小：

```bash
# 8 位量化（大小减少 50%）
litgpt convert_lit_checkpoint \
  out/phi2-lora/final \
  --dtype bfloat16 \
  --quantize bnb.nf4

# 4 位量化（大小减少 75%）
litgpt convert_lit_checkpoint \
  out/phi2-lora/final \
  --quantize bnb.nf4-dq  # 双重量化
```

**步骤 3：转换为 GGUF**（用于 llama.cpp）

```bash
python scripts/convert_lit_checkpoint.py \
  --checkpoint_path out/phi2-lora/final \
  --output_path models/phi2.gguf \
  --model_name microsoft/phi-2
```

**步骤 4：通过 API 部署**

```python
from fastapi import FastAPI
from litgpt import LLM

app = FastAPI()
llm = LLM.load("out/phi2-lora/final")

@app.post("/generate")
def generate(prompt: str, max_tokens: int = 100):
    result = llm.generate(
        prompt,
        max_new_tokens=max_tokens,
        temperature=0.7
    )
    return {"response": result}

# 运行：uvicorn api:app --host 0.0.0.0 --port 8000
```

## 何时使用 vs 替代方案

**使用 LitGPT 当：**
- 希望理解 LLM 架构（代码清晰易读）
- 需要生产就绪的训练方案
- 用于教学目的或研究
- 原型化新模型想法
- Lightning 生态系统用户

**使用替代方案当：**
- **Axolotl/TRL**：更多微调功能，YAML 配置
- **Megatron-Core**：>70B 模型的最高性能
- **HuggingFace Transformers**：最广泛的模型支持
- **vLLM**：仅推理（无训练）

## 常见问题

**问题：微调时内存不足**

使用 LoRA 替代全参数微调：
```bash
# 替代 litgpt finetune（需要 40GB+）
litgpt finetune_lora  # 仅需 12-16GB
```

或启用梯度检查点：
```bash
litgpt finetune_lora \
  ... \
  --train.gradient_accumulation_iters 4  # 累积梯度
```

**问题：训练太慢**

启用 Flash Attention（内置，在兼容硬件上自动启用）：
```python
# 在 Ampere+ GPU（A100、RTX 30/40 系列）上默认已启用
# 无需配置
```

使用较小的微批次并累积：
```bash
--train.micro_batch_size 1 \
--train.global_batch_size 32 \
--train.gradient_accumulation_iters 32  # 有效批次=32
```

**问题：模型无法加载**

检查模型名称：
```bash
# 列出所有可用模型
litgpt download list

# 如果不存在则下载
litgpt download meta-llama/Meta-Llama-3-8B
```

验证检查点目录：
```bash
ls checkpoints/
# 应看到：meta-llama/Meta-Llama-3-8B/
```

**问题：LoRA 适配器太大**

降低 LoRA 秩：
```bash
--lora_r 8  # 替代 16 或 32
```

对更少的层应用 LoRA：
```bash
--lora_query true \
--lora_value true \
--lora_projection false \  # 禁用此项
--lora_mlp false  # 以及此项
```

## 高级主题

**支持的架构**：参见 [references/supported-models.md](references/supported-models.md) 获取 20+ 模型系列的完整列表，包括大小和能力。

**训练方案**：参见 [references/training-recipes.md](references/training-recipes.md) 获取预训练和微调的已验证超参数配置。

**FSDP 配置**：参见 [references/distributed-training.md](references/distributed-training.md) 获取使用完全分片数据并行的多 GPU 训练。

**自定义架构**：参见 [references/custom-models.md](references/custom-models.md) 获取以 LitGPT 风格实现新模型架构的指南。

## 硬件要求

- **GPU**：NVIDIA（CUDA 11.8+）、AMD（ROCm）、Apple Silicon（MPS）
- **内存**：
  - 推理（Phi-2）：6GB
  - LoRA 微调（7B）：16GB
  - 全参数微调（7B）：40GB+
  - 预训练（1B）：24GB
- **存储**：每个模型 5-50GB（取决于大小）

## 资源

- GitHub：https://github.com/Lightning-AI/litgpt
- 文档：https://lightning.ai/docs/litgpt
- 教程：https://lightning.ai/docs/litgpt/tutorials
- 模型库：20+ 预训练架构（Llama、Gemma、Phi、Qwen、Mistral、Mixtral、Falcon 等）

# Claude 科学技能

> **新功能：[K-Dense BYOK](https://github.com/K-Dense-AI/k-dense-byok)** — 一款免费、开源的 AI 协科学家，可在您的桌面上运行，由 Claude 科学技能提供支持。自带 API 密钥，从 40+ 模型中选择，获得完整的研究工作空间，包括网络搜索、文件处理、100+ 科学数据库，以及访问此仓库中的所有 134 项技能。您的数据保留在您的计算机上，并且您可以选择通过 [Modal](https://modal.com/) 扩展到云端计算以处理繁重工作负载。[在此开始使用。](https://github.com/K-Dense-AI/k-dense-byok)

[![许可证: MIT](https://img.shields.io/badge/许可证-MIT-yellow.svg)](LICENSE.md)
[![技能](https://img.shields.io/badge/技能-134-brightgreen.svg)](#whats-included)
[![数据库](https://img.shields.io/badge/数据库-100%2B-orange.svg)](#whats-included)
[![智能体技能](https://img.shields.io/badge/标准-智能体_技能-blueviolet.svg)](https://agentskills.io/)
[![兼容](https://img.shields.io/badge/兼容-Cursor_|_Claude_Code_|_Codex-blue.svg)](#getting-started)
[![X](https://img.shields.io/badge/在_X_上关注-%40k__dense__ai-000000?logo=x)](https://x.com/k_dense_ai)
[![领英](https://img.shields.io/badge/领英-K--Dense_Inc.-0A66C2?logo=linkedin)](https://www.linkedin.com/company/k-dense-inc)
[![YouTube](https://img.shields.io/badge/YouTube-K--Dense_Inc.-FF0000?logo=youtube)](https://www.youtube.com/@K-Dense-Inc)

一个全面的 **134 项即用型科学和研究技能** 集合（涵盖癌症基因组学、药物-靶点结合、分子动力学、RNA 速率、地理空间科学、时间序列预测、78+ 科学数据库等），适用于任何支持开放 [智能体技能](https://agentskills.io/) 标准的 AI 智能体，由 [K-Dense](https://k-dense.ai) 创建。兼容 **Cursor、Claude Code、Codex 等**。将您的 AI 智能体转变为能够跨生物学、化学、医学等领域执行复杂多步骤科学工作流的研究助手。

<p align="center">
  <a href="https://k-dense.ai">
    <img src="docs/k-dense-web.gif" alt="K-Dense 网页演示" width="800"/>
  </a>
  <br/>
  <em>上方演示展示了 <a href="https://k-dense.ai">K-Dense Web</a> — 基于这些技能构建的托管平台。Claude 科学技能是开源技能集合；K-Dense Web 是功能更强大且无需设置的全功能 AI 协科学家平台。</em>
</p>

---

这些技能使您的 AI 智能体能够跨多个科学领域无缝使用专业科学库、数据库和工具。虽然智能体可以自行使用任何 Python 包或 API，但这些明确定义的技能提供了精选的文档和示例，使其在以下工作流中显著更强大、更可靠：
- 🧬 生物信息学与基因组学 - 序列分析、单细胞 RNA-seq、基因调控网络、变异注释、系统发育分析
- 🧪 化学信息学与药物发现 - 分子性质预测、虚拟筛选、ADMET 分析、分子对接、先导化合物优化
- 🔬 蛋白质组学与质谱分析 - LC-MS/MS 处理、肽段鉴定、谱图匹配、蛋白质定量
- 🏥 临床研究与精准医学 - 临床试验、药物基因组学、变异解释、药物安全性、临床决策支持、治疗计划
- 🧠 医疗 AI 与临床机器学习 - EHR 分析、生理信号处理、医学影像、临床预测模型
- 🖼️ 医学影像与数字病理学 - DICOM 处理、全切片图像分析、计算病理学、放射学工作流
- 🤖 机器学习与 AI - 深度学习、强化学习、时间序列分析、模型可解释性、贝叶斯方法
- 🔮 材料科学与化学 - 晶体结构分析、相图、代谢建模、计算化学
- 🌌 物理学与天文学 - 天文数据分析、坐标变换、宇宙学计算、符号数学、物理计算
- ⚙️ 工程与模拟 - 离散事件模拟、多目标优化、代谢工程、系统建模、过程优化
- 📊 数据分析与可视化 - 统计分析、网络分析、时间序列、出版质量图表、大规模数据处理、EDA
- 🌍 地理空间科学与遥感 - 卫星图像处理、GIS 分析、空间统计、地形分析、地球观测机器学习
- 🧪 实验室自动化 - 液体处理协议、实验室设备控制、工作流自动化、LIMS 集成
- 📚 科学交流 - 文献综述、同行评审、科学写作、文档处理、海报、幻灯片、示意图、引文管理
- 🔬 多组学与系统生物学 - 多模态数据整合、通路分析、网络生物学、系统级洞察
- 🧬 蛋白质工程与设计 - 蛋白质语言模型、结构预测、序列设计、功能注释
- 🎓 研究方法论 - 假设生成、科学头脑风暴、批判性思维、基金撰写、学者评估

**将您的 AI 编码智能体转变为桌面上的“AI 科学家”！**

> ⭐ **如果您觉得此仓库有用**，请考虑给它一个星标！这有助于其他人发现这些工具，并鼓励我们继续维护和扩展此集合。

> 🎬 **初次接触 Claude 科学技能？** 观看我们的 [Claude 科学技能入门](https://youtu.be/ZxbnDaD_FVg) 视频以快速了解。

---

## 📦 包含内容

此仓库提供 **134 项科学和研究技能**，按以下类别组织：

- **100+ 科学与金融数据库** - 统一的数据库查询技能提供对 78 个公共数据库的直接访问（PubChem、ChEMBL、UniProt、COSMIC、ClinicalTrials.gov、FRED、USPTO 等），外加针对 DepMap、Imaging Data Commons、PrimeKG 和美国财政部财政数据的专用技能。多数据库包如 BioServices（约 40 项生物信息服务）、BioPython（通过 Entrez 访问 38 个 NCBI 子数据库）和 gget（20+ 基因组学数据库）进一步扩展了覆盖范围
- **70+ 优化的 Python 包技能** - 针对 RDKit、Scanpy、PyTorch Lightning、scikit-learn、BioPython、pyzotero、BioServices、PennyLane、Qiskit、OpenMM、MDAnalysis、scVelo、TimesFM 等的明确定义技能 — 包含精选文档、示例和最佳实践。注意：智能体可以使用*任何* Python 包编写代码，不仅仅是这些；这些技能仅为所列包提供更强、更可靠的性能
- **9 项科学集成技能** - 针对 Benchling、DNAnexus、LatchBio、OMERO、Protocols.io、Open Notebook 等的明确定义技能。再次强调，智能体不受限于这些 — 任何可从 Python 访问的 API 或平台都是可行的；这些技能是经过优化、预先文档化的路径
- **30+ 分析与交流工具** - 文献综述、科学写作、同行评审、文档处理、海报、幻灯片、示意图、信息图、Mermaid 图表等
- **10+ 研究与临床工具** - 假设生成、基金撰写、临床决策支持、治疗计划、法规遵从、情景分析

每项技能包括：
- ✅ 全面文档（`SKILL.md`）
- ✅ 实用代码示例
- ✅ 用例和最佳实践
- ✅ 集成指南
- ✅ 参考资料

---

## 📋 目录

- [包含内容](#whats-included)
- [为何使用此项目？](#why-use-this)
- [快速开始](#getting-started)
- [安全免责声明](#-security-disclaimer)
- [支持开源](#-support-the-open-source-community)
- [先决条件](#prerequisites)
- [快速示例](#quick-examples)
- [用例](#use-cases)
- [可用技能](#available-skills)
- [贡献指南](#contributing)
- [故障排除](#troubleshooting)
- [常见问题](#faq)
- [支持](#support)
- [加入我们的社区](#join-our-community)
- [引用](#citation)
- [许可证](#license)

---

## 🚀 为何使用此项目？

### ⚡ **加速您的研究**
- **节省数天工作量** - 跳过 API 文档研究和集成设置
- **生产就绪代码** - 经过测试、验证的示例，遵循科学最佳实践
- **多步骤工作流** - 通过单个提示执行复杂流程

### 🎯 **全面覆盖**
- **134 项技能** - 覆盖所有主要科学领域的广泛覆盖
- **100+ 数据库** - 通过数据库查询技能统一访问 78+ 数据库，外加专用数据访问技能以及 BioServices、BioPython 和 gget 等多数据库包
- **70+ 优化的 Python 包技能** - RDKit、Scanpy、PyTorch Lightning、scikit-learn、BioServices、PennyLane、Qiskit、OpenMM、scVelo、TimesFM 等（智能体可以使用任何 Python 包；这些是预先文档化、性能更高的路径）

### 🔧 **易于集成**
- **简单设置** - 将技能复制到您的技能目录并开始工作
- **自动发现** - 您的智能体自动查找并使用相关技能
- **文档完善** - 每项技能包含示例、用例和最佳实践

### 🌟 **维护与支持**
- **定期更新** - 由 K-Dense 团队持续维护和扩展
- **社区驱动** - 开源，有活跃的社区贡献
- **企业就绪** - 提供商业支持以满足高级需求

---

## 🎯 快速开始

通过单个命令安装 Claude 科学技能：

```bash
npx skills add K-Dense-AI/claude-scientific-skills
```

这是跨**所有平台**安装智能体技能的官方标准方法，包括 **Claude Code**、**Claude Cowork**、**Codex**、**Gemini CLI**、**Cursor** 以及任何其他支持开放 [智能体技能](https://agentskills.io/) 标准的智能体。

**就这样！** 您的 AI 智能体将自动发现这些技能，并在与您的科学任务相关时使用它们。您也可以通过提示中提及技能名称手动调用任何技能。

---

## ⚠️ 安全免责声明

> **技能可以执行代码并影响您的编码智能体行为。请审查您安装的内容。**

智能体技能非常强大 — 它们可以指示您的 AI 智能体运行任意代码、安装包、发起网络请求以及修改您系统上的文件。恶意或编写不当的技能有可能引导您的编码智能体产生有害行为。

我们高度重视安全。所有贡献都经过审查流程，并且我们对仓库中的每项技能运行基于 LLM 的安全扫描（通过 [Cisco AI Defense Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner)）。然而，作为一个团队规模较小且社区贡献不断增长的团队，我们无法保证每项技能都经过详尽审查以应对所有可能的风险。

**最终，审查您安装的技能并决定信任哪些是您的责任。**

我们建议以下事项：

- **不要一次性安装所有内容。** 仅安装您实际工作所需的技能。虽然当 K-Dense 创建和维护每项技能时，安装完整集合是合理的，但该仓库现在包含许多我们可能未彻底审查的社区贡献。
- **安装前阅读 `SKILL.md`。** 每项技能的文档描述了它的功能、使用的包以及连接的外部服务。如果某些内容看起来可疑，请不要安装它。
- **检查贡献历史。** 由 K-Dense（`K-Dense-AI`）创作的技能已经过我们的内部审查流程。社区贡献的技能已尽我们所能进行审查，但资源有限。
- **自行运行安全扫描器。** 在安装第三方技能之前，请本地扫描它们：
  ```bash
  uv pip install cisco-ai-skill-scanner
  skill-scanner scan /path/to/skill --use-behavioral
  ```
- **报告任何可疑内容。** 如果您发现某项技能看起来恶意或行为异常，请立即[提交问题](https://github.com/K-Dense-AI/claude-scientific-skills/issues)以便我们调查。

---

## ❤️ 支持开源社区

Claude 科学技能由 **50+ 令人惊叹的开源项目** 提供支持，这些项目由全球专注的开发者和研究社区维护。像 Biopython、Scanpy、RDKit、scikit-learn、PyTorch Lightning 等许多项目构成了这些技能的基础。

**如果您从此仓库中获得价值，请考虑支持使其成为可能的项目：**

- ⭐ **在 GitHub 上给他们的仓库加星标**
- 💰 **通过 GitHub Sponsors 或 NumFOCUS 赞助维护者**
- 📝 **在您的出版物中引用项目**
- 💻 **贡献**代码、文档或错误报告

👉 **[查看要支持的完整项目列表](docs/open-source-sponsors.md)**

---

## ⚙️ 先决条件

- **Python**：3.11+（推荐 3.12+ 以获得最佳兼容性）
- **uv**：Python 包管理器（安装技能依赖项所必需）
- **客户端**：任何支持 [智能体技能](https://agentskills.io/) 标准的智能体（Cursor、Claude Code、Gemini CLI、Codex 等）
- **系统**：macOS、Linux 或带 WSL2 的 Windows
- **依赖项**：由各个技能自动处理（查看 `SKILL.md` 文件了解具体要求）

### 安装 uv

技能使用 `uv` 作为包管理器来安装 Python 依赖项。根据您的操作系统使用以下说明安装：

**macOS 和 Linux：**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows：**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**替代方法（通过 pip）：**
```bash
pip install uv
```

安装后，通过运行以下命令验证其是否正常工作：
```bash
uv --version
```

有关更多安装选项和详细信息，请访问 [官方 uv 文档](https://docs.astral.sh/uv/)。

---

## 💡 快速示例

安装技能后，您可以要求您的 AI 智能体执行复杂的多步骤科学工作流。以下是一些示例提示：

### 🧪 药物发现流程
**目标**：寻找用于肺癌治疗的新型 EGFR 抑制剂

**提示**：
```
尽可能使用您有权访问的可用技能。查询 ChEMBL 获取 EGFR 抑制剂（IC50 < 50nM），使用 RDKit 分析构效关系，
使用 datamol 生成改进的类似物，使用 DiffDock 针对 AlphaFold EGFR 结构进行虚拟筛选，
搜索 PubMed 获取耐药机制，检查 COSMIC 获取突变，并创建可视化和综合报告。
```

**使用的技能**：ChEMBL、RDKit、datamol、DiffDock、AlphaFold DB、PubMed、COSMIC、科学可视化

*需要云端 GPU 和最终可发表的报告吗？[在 K-Dense Web 上免费运行此流程。](https://k-dense.ai)*

---

### 🔬 单细胞 RNA-seq 分析
**目标**：结合公共数据对 10X Genomics 数据进行全面分析

**提示**：
```
尽可能使用您有权访问的可用技能。使用 Scanpy 加载 10X 数据集，执行 QC 和双联体去除，与 Cellxgene Census 数据整合，
使用 NCBI Gene 标记物识别细胞类型，使用 PyDESeq2 运行差异表达，使用 Arboreto 推断基因调控网络，
通过 Reactome/KEGG 富集通路，并使用 Open Targets 识别治疗靶点。
```

**使用的技能**：Scanpy、Cellxgene Census、NCBI Gene、PyDESeq2、Arboreto、Reactome、KEGG、Open Targets

*想要零设置云端执行和可共享的输出吗？[免费试用 K-Dense Web。](https://k-dense.ai)*

---

### 🧬 多组学生物标志物发现
**目标**：整合 RNA-seq、蛋白质组学和代谢组学以预测患者结果

**提示**：
```
尽可能使用您有权访问的可用技能。使用 PyDESeq2 分析 RNA-seq，使用 pyOpenMS 处理质谱数据，从 HMDB/Metabolomics Workbench 整合代谢物，
将蛋白质映射到通路（UniProt/KEGG），通过 STRING 查找相互作用，使用 statsmodels 关联组学层，
使用 scikit-learn 构建预测模型，并搜索 ClinicalTrials.gov 获取相关试验。
```

**使用的技能**：PyDESeq2、pyOpenMS、HMDB、Metabolomics Workbench、UniProt、KEGG、STRING、statsmodels、scikit-learn、ClinicalTrials.gov

*此流程计算量较大。[在 K-Dense Web 上使用云端 GPU 运行，免费开始。](https://k-dense.ai)*

---

### 🎯 虚拟筛选活动
**目标**：发现蛋白质-蛋白质相互作用的变构调节剂

**提示**：
```
尽可能使用您有权访问的可用技能。检索 AlphaFold 结构，使用 BioPython 识别相互作用界面，搜索 ZINC 获取变构候选物（MW 300-500，logP 2-4），
使用 RDKit 过滤，使用 DiffDock 对接，使用 DeepChem 排名，检查 PubChem 供应商，搜索 USPTO 专利，
并使用 MedChem/molfeat 优化先导化合物。
```

**使用的技能**：AlphaFold DB、BioPython、ZINC、RDKit、DiffDock、DeepChem、PubChem、USPTO、MedChem、molfeat

*跳过本地 GPU 瓶颈。[在 K-Dense Web 上免费运行虚拟筛选。](https://k-dense.ai)*

---

### 🏥 临床变异解释
**目标**：分析 VCF 文件以评估遗传性癌症风险

**提示**：
```
尽可能使用您有权访问的可用技能。使用 pysam 解析 VCF，使用 Ensembl VEP 注释变异，查询 ClinVar 获取致病性，
检查 COSMIC 获取癌症突变，从 NCBI Gene 检索基因信息，使用 UniProt 分析蛋白质影响，
搜索 PubMed 获取病例报告，检查 ClinPGx 获取药物基因组学信息，使用文档处理工具生成临床报告，
并在 ClinicalTrials.gov 上查找匹配的试验。
```

**使用的技能**：pysam、Ensembl、ClinVar、COSMIC、NCBI Gene、UniProt、PubMed、ClinPGx、文档技能、ClinicalTrials.gov

*需要最终得到精美的临床报告，而不仅仅是代码吗？[K-Dense Web 提供可发表的输出。免费试用。](https://k-dense.ai)*

---

### 🌐 系统生物学网络分析
**目标**：从 RNA-seq 数据中分析基因调控网络

**提示**：
```
尽可能使用您有权访问的可用技能。查询 NCBI Gene 获取注释，从 UniProt 检索序列，通过 STRING 识别相互作用，
映射到 Reactome/KEGG 通路，使用 Torch Geometric 分析拓扑结构，使用 Arboreto 重建 GRN，
使用 Open Targets 评估成药性，使用 PyMC 建模，可视化网络，并搜索 GEO 获取相似模式。
```

**使用的技能**：NCBI Gene、UniProt、STRING、Reactome、KEGG、Torch Geometric、Arboreto、Open Targets、PyMC、GEO

*想要端到端流程、可共享的输出且无需设置吗？[免费试用 K-Dense Web。](https://k-dense.ai)*

> 📖 **想要更多示例？** 查看 [docs/examples.md](docs/examples.md) 获取全面的工作流示例和跨所有科学领域的详细用例。

---

## 🚀 想跳过设置直接开始科研？

**是否遇到过以下情况？**

- 配置环境的时间比运行分析的时间还长
- 你的工作流需要本地机器没有的 GPU
- 你需要可共享、可直接发表的图表或报告，而不仅仅是脚本
- 你想立即运行复杂的多步骤流程，而无需先阅读软件包文档

如果是这样，**[K-Dense Web](https://k-dense.ai)** 就是为你打造的。它是完整的 AI 科研协作平台：包含本仓库的所有功能，外加云端 GPU、200+ 技能，以及可直接放入论文或演示文稿的输出结果。零设置要求。

| 功能 | 本仓库 | K-Dense Web |
|---------|-----------|-------------|
| 科学技能 | 134 项技能 | **200+ 项技能**（独家访问） |
| 设置 | 手动安装 | **零设置，即时可用** |
| 计算资源 | 你的机器 | **包含云端 GPU 和 HPC** |
| 工作流 | 提示词和代码 | **端到端研究流程** |
| 输出 | 代码和分析 | **可直接发表的图表、报告和论文** |
| 集成 | 本地工具 | **实验室系统、电子实验记录本和云存储** |

> *"K-Dense Web 让我在一个下午内从原始测序数据到完成图表初稿。过去需要三天环境设置和脚本编写的工作，现在直接就能完成。"*
> **计算生物学家，药物发现领域**

> ### 💰 50 美元免费额度，无需信用卡
> 几分钟内即可开始运行真实的科学工作流。
>
> **[免费试用 K-Dense Web](https://k-dense.ai)**

*[k-dense.ai](https://k-dense.ai) | [阅读完整对比](https://k-dense.ai/blog/k-dense-web-vs-claude-scientific-skills)*

---

## 🔬 用例

### 🧪 药物发现与药物化学
- **虚拟筛选**：从 PubChem/ZINC 中筛选数百万化合物针对蛋白质靶点
- **先导化合物优化**：使用 RDKit 分析构效关系，使用 datamol 生成类似物
- **ADMET 预测**：使用 DeepChem 预测吸收、分布、代谢、排泄和毒性
- **分子对接**：使用 DiffDock 预测结合构象和亲和力
- **生物活性挖掘**：查询 ChEMBL 获取已知抑制剂并分析 SAR 模式

### 🧬 生物信息学与基因组学
- **序列分析**：使用 BioPython 和 pysam 处理 DNA/RNA/蛋白质序列
- **单细胞分析**：使用 Scanpy 分析 10X Genomics 数据，识别细胞类型，使用 Arboreto 推断基因调控网络
- **变异注释**：使用 Ensembl VEP 注释 VCF 文件，查询 ClinVar 获取致病性信息
- **变异数据库管理**：使用 TileDB-VCF 构建可扩展的 VCF 数据库，支持增量样本添加、高效群体规模查询和基因组变异数据的压缩存储
- **基因发现**：查询 NCBI Gene、UniProt 和 Ensembl 获取全面的基因信息
- **网络分析**：通过 STRING 识别蛋白质-蛋白质相互作用，映射到通路（KEGG、Reactome）

### 🏥 临床研究与精准医疗
- **临床试验**：搜索 ClinicalTrials.gov 获取相关研究，分析入组标准
- **变异解读**：使用 ClinVar、COSMIC 和 ClinPGx 注释变异以进行药物基因组学研究
- **药物安全性**：查询 FDA 数据库获取不良事件、药物相互作用和召回信息
- **精准治疗**：将患者变异与靶向疗法和临床试验相匹配

### 🔬 多组学与系统生物学
- **多组学整合**：整合 RNA-seq、蛋白质组学和代谢组学数据
- **通路分析**：在 KEGG/Reactome 通路中富集差异表达基因
- **网络生物学**：重建基因调控网络，识别枢纽基因
- **生物标志物发现**：整合多组学层以预测患者结局

### 📊 数据分析与可视化
- **统计分析**：进行假设检验、功效分析和实验设计
- **发表级图表**：使用 matplotlib 和 seaborn 创建发表级质量的可视化图表
- **网络可视化**：使用 NetworkX 可视化生物网络
- **报告生成**：使用文档技能生成全面的 PDF 报告

### 🧪 实验室自动化
- **实验方案设计**：为自动化液体处理创建 Opentrons 协议
- **LIMS 集成**：与 Benchling 和 LabArchives 集成进行数据管理
- **工作流自动化**：自动化多步骤实验室工作流

---

## 📚 可用技能

本仓库包含 **134 项科学和研究技能**，涵盖多个领域。每项技能都提供全面的文档、代码示例和最佳实践，用于处理科学库、数据库和工具。

### 技能类别

> **注意：** 下面列出的 Python 包和集成技能是*明确定义*的技能——经过精心策划，包含文档、示例和最佳实践，以实现更强、更可靠的性能。它们不是上限：智能体可以安装和使用*任何* Python 包或调用*任何* API，即使没有专门的技能。列出的技能只是让常见工作流更快、更可靠。

#### 🧬 **生物信息学与基因组学** (21+ 项技能)
- 序列分析：BioPython、pysam、scikit-bio、BioServices
- 单细胞分析：Scanpy、AnnData、scvi-tools、scVelo（RNA 速率）、Arboreto、Cellxgene Census
- 基因组学工具：gget、geniml、gtars、deepTools、FlowIO、Polars-Bio、Zarr、TileDB-VCF
- 差异表达：PyDESeq2
- 系统发育学：ETE Toolkit、Phylogenetics（MAFFT、IQ-TREE 2、FastTree）

#### 🧪 **化学信息学与药物发现** (10+ 项技能)
- 分子操作：RDKit、Datamol、Molfeat
- 深度学习：DeepChem、TorchDrug
- 对接与筛选：DiffDock
- 分子动力学：OpenMM + MDAnalysis（MD 模拟与轨迹分析）
- 云端量子化学：Rowan（pKa、对接、共折叠）
- 类药性：MedChem
- 基准测试：PyTDC

#### 🔬 **蛋白质组学与质谱分析** (2 项技能)
- 谱图处理：matchms、pyOpenMS

#### 🏥 **临床研究与精准医疗** (8+ 项技能)
- 临床数据库：通过数据库查询（ClinicalTrials.gov、ClinVar、ClinPGx、COSMIC、FDA、cBioPortal、Monarch 等）
- 癌症基因组学：DepMap（癌症依赖性评分、药物敏感性）
- 癌症影像学：Imaging Data Commons（通过 idc-index 访问 NCI 放射学和病理学数据集）
- 医疗 AI：PyHealth、NeuroKit2、临床决策支持
- 临床文档：临床报告、治疗计划

#### 🖼️ **医学影像与数字病理学** (3 项技能)
- DICOM 处理：pydicom
- 全切片成像：histolab、PathML

#### 🧠 **神经科学与电生理学** (1 项技能)
- 神经记录：Neuropixels-Analysis（细胞外尖峰、硅探针、尖峰排序）

#### 🤖 **机器学习与人工智能** (16+ 项技能)
- 深度学习：PyTorch Lightning、Transformers、Stable Baselines3、PufferLib
- 经典机器学习：scikit-learn、scikit-survival、SHAP
- 时间序列：aeon、TimesFM（谷歌用于单变量预测的零样本基础模型）
- 贝叶斯方法：PyMC
- 优化：PyMOO
- 图机器学习：Torch Geometric
- 降维：UMAP-learn
- 统计建模：statsmodels

#### 🔮 **材料科学、化学与物理学** (7 项技能)
- 材料学：Pymatgen
- 代谢建模：COBRApy
- 天文学：Astropy
- 量子计算：Cirq、PennyLane、Qiskit、QuTiP

#### ⚙️ **工程与模拟** (4 项技能)
- 数值计算：MATLAB/Octave
- 计算流体动力学：FluidSim
- 离散事件模拟：SimPy
- 符号数学：SymPy

#### 📊 **数据分析与可视化** (16+ 项技能)
- 可视化：Matplotlib、Seaborn、科学可视化
- 地理空间分析：GeoPandas、GeoMaster（遥感、GIS、卫星影像、空间机器学习、500+ 示例）
- 数据处理：Dask、Polars、Vaex
- 网络分析：NetworkX
- 文档处理：文档技能（PDF、DOCX、PPTX、XLSX）
- 信息图表：信息图表（AI 驱动的专业信息图表创建）
- 图表：Markdown 与 Mermaid 写作（基于文本的图表作为默认文档标准）
- 探索性数据分析：EDA 工作流
- 统计分析：统计分析工作流

#### 🧪 **实验室自动化** (4 项技能)
- 液体处理：PyLabRobot
- 云端实验室：Ginkgo Cloud Lab（无细胞蛋白质表达、通过自主 RAC 基础设施实现的荧光像素艺术）
- 协议管理：Protocols.io
- LIMS 集成：Benchling、LabArchives

#### 🔬 **多组学与系统生物学** (4+ 项技能)
- 通路分析：通过数据库查询（KEGG、Reactome、STRING）和 PrimeKG
- 多组学：HypoGeniC
- 数据管理：LaminDB

#### 🧬 **蛋白质工程与设计** (3 项技能)
- 蛋白质语言模型：ESM
- 糖基化工程：糖基化工程（N/O-糖基化预测、治疗性抗体优化）
- 云端实验室平台：Adaptyv（自动化蛋白质测试与验证）

#### 📚 **科学交流** (20+ 项技能)
- 文献：论文查找（PubMed、PMC、bioRxiv、medRxiv、arXiv、OpenAlex、Crossref、Semantic Scholar、CORE、Unpaywall）、文献综述
- 高级论文搜索：BGPT 论文搜索（每篇论文 25+ 个结构化字段——方法、结果、样本量、质量评分——来自全文，不仅仅是摘要）
- 网络搜索：Perplexity 搜索（AI 驱动的实时信息搜索）、Parallel Web（带引用的综合摘要）
- 研究笔记：开放笔记本（自托管的 NotebookLM 替代品——PDF、视频、音频、网页；16+ AI 提供商；多说话人播客生成）
- 写作：科学写作、同行评审
- 文档处理：XLSX、MarkItDown、文档技能
- 出版：期刊模板
- 演示文稿：科学幻灯片、LaTeX 海报、PPTX 海报
- 图表：科学示意图、Markdown 与 Mermaid 写作
- 信息图表：信息图表（10 种类型，8 种风格，色盲安全调色板）
- 引用：引用管理
- 插图：生成图像（使用 FLUX.2 Pro 和 Gemini 3 Pro（Nano Banana Pro）进行 AI 图像生成）

#### 🔬 **科学数据库与数据访问** (5 项技能 → 总计 100+ 个数据库)
> 一个统一的数据库查询技能提供对 78 个跨领域公共数据库的直接 REST API 访问。专用技能涵盖专业数据平台。多数据库包如 BioServices（约 40 个生物信息服务）、BioPython（通过 Entrez 访问 38 个 NCBI 子数据库）和 gget（20+ 个基因组学数据库）进一步扩展了覆盖范围。
- 统一访问：数据库查询（78 个数据库，涵盖化学、基因组学、临床、通路、专利、经济学等领域——PubChem、ChEMBL、UniProt、PDB、AlphaFold、KEGG、Reactome、STRING、ClinVar、COSMIC、ClinicalTrials.gov、FDA、FRED、USPTO、SEC EDGAR 等数十个）
- 癌症基因组学：DepMap（癌细胞系依赖性、药物敏感性、基因效应谱）
- 癌症影像学：Imaging Data Commons（通过 idc-index 访问 NCI 放射学和病理学数据集）
- 知识图谱：PrimeKG（精准医疗知识图谱——基因、药物、疾病、表型）
- 财政数据：美国财政部财政数据（国债、财政部报表、拍卖、汇率）

#### 🔧 **基础设施与平台** (7+ 项技能)
- 云端计算：Modal
- GPU 加速：GPU 优化（CuPy、Numba CUDA、Warp、cuDF、cuML、cuGraph、KvikIO、cuCIM、cuxfilter、cuVS、cuSpatial、RAFT）
- 基因组学平台：DNAnexus、LatchBio
- 显微镜：OMERO
- 自动化：Opentrons
- 资源检测：获取可用资源

#### 🎓 **研究方法论与规划** (12+ 项技能)
- 构思：科学头脑风暴、假设生成
- 批判性分析：科学批判性思维、学者评估
- 情景分析：假设分析预言家（多分支可能性探索、风险分析、战略选项）
- 多视角审议：意识理事会（多样化专家观点、魔鬼代言人分析）
- 认知分析：DHDNA 分析器（从任何文本中提取思维模式和认知特征）
- 资金：研究基金
- 发现：研究查找、论文查找（10 个学术数据库）
- 市场分析：市场研究报告

#### ⚖️ **法规与标准** (1 项技能)
- 医疗器械标准：ISO 13485 认证

> 📖 **有关所有技能的完整详情**，请参阅 [docs/scientific-skills.md](docs/scientific-skills.md)

> 💡 **寻找实用示例？** 查看 [docs/examples.md](docs/examples.md) 获取跨所有科学领域的全面工作流示例。

---

## 🤝 贡献

我们欢迎贡献来扩展和改进这个科学技能仓库！

### 贡献方式

✨ **添加新技能**
- 为额外的科学包或数据库创建技能
- 添加科学平台和工具的集成

📚 **改进现有技能**
- 通过更多示例和用例增强文档
- 添加新的工作流和参考资料
- 改进代码示例和脚本
- 修复错误或更新过时信息

🐛 **报告问题**
- 提交包含详细重现步骤的错误报告
- 提出改进建议或新功能

### 如何贡献

1. **Fork** 本仓库
2. **创建** 功能分支 (`git checkout -b feature/amazing-skill`)
3. **遵循** 现有的目录结构和文档模式
4. **确保** 所有新技能都包含全面的 `SKILL.md` 文件
5. **测试** 你的示例和工作流
6. **提交** 更改 (`git commit -m 'Add amazing skill'`)
7. **推送** 到你的分支 (`git push origin feature/amazing-skill`)
8. **提交** 拉取请求，并清晰描述你的更改

### 贡献指南

✅ **遵守 [Agent Skills 规范](https://agentskills.io/specification)** — 每项技能必须遵循官方规范（有效的 `SKILL.md` 元数据、命名约定、目录结构）  
✅ 保持与现有技能文档格式的一致性  
✅ 确保所有代码示例经过测试且功能正常  
✅ 在示例和工作流中遵循科学最佳实践  
✅ 添加新功能时更新相关文档  
✅ 在代码中提供清晰的注释和文档字符串  
✅ 包含官方文档的引用

### 安全扫描

本仓库中的所有技能都使用 [Cisco AI Defense Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner) 进行安全扫描，这是一个开源工具，用于检测 Agent Skills 中的提示注入、数据泄露和恶意代码模式。

如果你要贡献新技能，我们建议在提交拉取请求前本地运行扫描器：

```bash
uv pip install cisco-ai-skill-scanner
skill-scanner scan /path/to/your/skill --use-behavioral
```

> **注意：** 干净的扫描结果可以减少审查中的干扰，但不能保证技能完全没有风险。贡献的技能在合并前也会经过人工审查。

### 认可

贡献者将在我们的社区中得到认可，并可能出现在：
- 仓库贡献者列表
- 发布说明中的特别提及
- K-Dense 社区亮点

你的贡献有助于使科学计算更易用，并让研究人员能更有效地利用 AI 工具！

### 支持开源

本项目建立在 50+ 个优秀的开源项目之上。如果你在这些技能中发现了价值，请考虑[支持我们依赖的项目](docs/open-source-sponsors.md)。

---

## 🔧 故障排除

### 常见问题

**问题：技能未加载**
- 确认技能文件夹在正确的目录中（参见[入门指南](#getting-started)）
- 每个技能文件夹必须包含 `SKILL.md` 文件
- 复制技能后重启你的智能体/IDE
- 在 Cursor 中，检查 Settings → Rules 以确认技能已被发现

**问题：缺少 Python 依赖**
- 解决方案：检查具体的 `SKILL.md` 文件获取所需包
- 安装依赖：`uv pip install package-name`

**问题：API 速率限制**
- 解决方案：许多数据库都有速率限制。查看具体数据库文档
- 考虑实现缓存或批量请求

**问题：认证错误**
- 解决方案：某些服务需要 API 密钥。检查 `SKILL.md` 获取认证设置
- 验证你的凭据和权限

**问题：示例过时**
- 解决方案：通过 GitHub Issues 报告问题
- 查看官方包文档获取更新的语法

---

## ❓ 常见问题解答

### 一般问题

**问：这是免费使用的吗？**  
答：是的！本仓库采用 MIT 许可证。但是，每项技能在其 `SKILL.md` 文件的 `license` 元数据字段中都有自己指定的许可证——请务必查看并遵守这些条款。

**问：为什么所有技能都放在一起，而不是单独的包？**  
答：我们相信，在 AI 时代，好的科学本质上是跨学科的。将所有技能捆绑在一起，让你（和你的智能体）可以轻松跨越领域——例如，在一个工作流中结合基因组学、化学信息学、临床数据和机器学习——而无需担心要安装或连接哪些单独的技能。

**问：我可以将此用于商业项目吗？**  
答：仓库本身是 MIT 许可证，允许商业使用。但是，个别技能可能有不同的许可证——检查每项技能 `SKILL.md` 文件中的 `license` 字段，以确保符合你的预期用途。

**问：所有技能都有相同的许可证吗？**  
答：不是。每项技能在其 `SKILL.md` 文件的 `license` 元数据字段中都有自己指定的许可证。这些许可证可能与仓库的 MIT 许可证不同。用户有责任查看并遵守他们使用的每项技能的许可证条款。

**问：多久更新一次？**  
答：我们会定期更新技能以反映包和 API 的最新版本。主要更新会在发布说明中宣布。

**问：我可以将此与其他 AI 模型一起使用吗？**  
答：这些技能遵循开放的 [Agent Skills](https://agentskills.io/) 标准，可与任何兼容的智能体一起使用，包括 Cursor、Claude Code 和 Codex。

### 安装与设置

**问：我需要安装所有的 Python 包吗？**  
答：不需要！只安装你需要的包。每项技能在其 `SKILL.md` 文件中指定了其要求。

**问：如果一项技能不工作怎么办？**  
答：首先检查[故障排除](#troubleshooting)部分。如果问题仍然存在，请在 GitHub 上提交问题，并提供详细的重现步骤。

**问：这些技能可以离线工作吗？**  
答：数据库技能需要互联网访问来查询 API。包技能在安装 Python 依赖后可以离线工作。

### 贡献

**问：我可以贡献自己的技能吗？**  
答：当然可以！我们欢迎贡献。请参阅[贡献](#contributing)部分了解指南和最佳实践。

**问：如何报告错误或提出功能建议？**  
答：在 GitHub 上提交问题，并提供清晰的描述。对于错误，请包含重现步骤以及预期与实际行为。

---

## 💬 支持

需要帮助？以下是如何获取支持：

- 📖 **文档**：查看相关的 `SKILL.md` 和 `references/` 文件夹
- 🐛 **错误报告**：[提交问题](https://github.com/K-Dense-AI/claude-scientific-skills/issues)
- 💡 **功能请求**：[提交功能请求](https://github.com/K-Dense-AI/claude-scientific-skills/issues/new)
- 💼 **企业支持**：联系 [K-Dense](https://k-dense.ai/) 获取商业支持
- 🌐 **社区**：[加入我们的 Slack](https://join.slack.com/t/k-densecommunity/shared_invite/zt-3iajtyls1-EwmkwIZk0g_o74311Tkf5g)

---

## 🎉 加入我们的社区！

**我们非常欢迎你的加入！** 🚀

与使用 AI 智能体进行科学计算的其他科学家、研究人员和 AI 爱好者联系。分享你的发现、提问、获取项目帮助，并与社区合作！

🌟 **[加入我们的 Slack 社区](https://join.slack.com/t/k-densecommunity/shared_invite/zt-3iajtyls1-EwmkwIZk0g_o74311Tkf5g)** 🌟

无论你是刚刚入门还是高级用户，我们的社区都会为你提供支持。我们分享技巧、共同解决问题、展示酷炫项目，并讨论 AI 驱动科学研究的最新发展。

**期待在那里见到你！** 💬

---

## 📖 引用

如果你在研究或项目中使用 Claude Scientific Skills，请引用为：

### BibTeX
```bibtex
@software{claude_scientific_skills_2026,
  author = {{K-Dense Inc.}},
  title = {Claude Scientific Skills: A Comprehensive Collection of Scientific Tools for Claude AI},
  year = {2026},
  url = {https://github.com/K-Dense-AI/claude-scientific-skills},
  note = {134 skills covering databases, packages, integrations, and analysis tools}
}
```

### APA
```
K-Dense Inc. (2026). Claude Scientific Skills: A comprehensive collection of scientific tools for Claude AI [Computer software]. https://github.com/K-Dense-AI/claude-scientific-skills
```

### MLA
```
K-Dense Inc. Claude Scientific Skills: A Comprehensive Collection of Scientific Tools for Claude AI. 2026, github.com/K-Dense-AI/claude-scientific-skills.
```

### 纯文本
```
Claude Scientific Skills by K-Dense Inc. (2026)
Available at: https://github.com/K-Dense-AI/claude-scientific-skills
```

我们感谢在受益于这些技能的出版物、演示文稿或项目中的致谢！

---

## 📄 许可证

本项目采用 **MIT 许可证**。

**版权所有 © 2026 K-Dense Inc.** ([k-dense.ai](https://k-dense.ai/))

### 要点：
- ✅ **免费用于任何用途**（商业和非商业）
- ✅ **开源** - 可自由修改、分发和使用
- ✅ **宽松** - 对重用限制极少
- ⚠️ **无担保** - 按"原样"提供，无任何形式的担保

完整条款请参阅 [LICENSE.md](LICENSE.md)。

### 个别技能许可证

> ⚠️ **重要提示**：每项技能在其 `SKILL.md` 文件的 `license` 元数据字段中都有自己指定的许可证。这些许可证可能与仓库的 MIT 许可证不同，并且可能包含额外的条款或限制。**用户有责任查看并遵守他们使用的每项技能的许可证条款。**

## Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=K-Dense-AI/claude-scientific-skills&type=date&legend=top-left)](https://www.star-history.com/#K-Dense-AI/claude-scientific-skills&type=date&legend=top-left)

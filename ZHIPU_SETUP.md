# 智谱 AI (Zhipu AI) 配置指南

## 1. 获取 API Key

访问智谱 AI 开放平台注册并获取 API Key：
👉 https://open.bigmodel.cn/

## 2. 设置环境变量

### macOS / Linux (终端)
```bash
export ZHIPUAI_API_KEY='your-api-key-here'
```

### Windows (PowerShell)
```powershell
$env:ZHIPUAI_API_KEY='your-api-key-here'
```

### Windows (CMD)
```cmd
set ZHIPUAI_API_KEY=your-api-key-here
```

## 3. 永久设置（推荐）

### macOS / Linux
将以下内容添加到 `~/.zshrc` 或 `~/.bashrc`：
```bash
export ZHIPUAI_API_KEY='your-api-key-here'
```

然后执行：
```bash
source ~/.zshrc  # 或 source ~/.bashrc
```

### Windows
在系统环境变量中添加 `ZHIPUAI_API_KEY`

## 4. 可用的 GLM 模型

- `glm-4-flash` - 快速响应，适合日常对话（推荐）
- `glm-4` - 标准版，平衡性能和成本
- `glm-4-plus` - 增强版，更强的推理能力
- `glm-4v` - 视觉模型，支持图片理解

## 5. 运行应用

### Web UI 界面
```bash
python agno_agent.py
```
然后访问：http://localhost:7777

### 命令行交互
```bash
python chat_cli.py
```

## 6. 注意事项

⚠️ **重要提示：**
- API Key 格式通常是：`{key_id}.{key_secret}`
- 请妥善保管你的 API Key，不要提交到版本控制系统
- 如果遇到问题，检查 API Key 是否正确设置
- 确保账户有足够的余额或免费额度

## 7. 测试连接

运行以下命令测试连接：
```bash
python chat_cli.py
```

输入一个简单的问候语，如 "你好"，如果能收到回复说明配置成功！

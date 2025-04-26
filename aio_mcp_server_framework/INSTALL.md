# 安装说明

## 从PyPI安装

最简单的安装方式是通过pip：

```bash
pip install aio-mcp-server-framework
```

## 从源代码安装

### 前提条件

- Python 3.8+
- pip
- setuptools
- wheel

### 安装步骤

1. 克隆仓库或下载源代码：

```bash
git clone https://github.com/yourusername/aio-mcp-server-framework.git
cd aio-mcp-server-framework
```

2. 使用提供的构建脚本安装：

```bash
# 在Windows上
python build.py install

# 在Linux/macOS上
chmod +x build.py
./build.py install
```

或者手动安装：

```bash
pip install -e .
```

## 验证安装

安装完成后，运行以下命令确认安装成功：

```bash
aio-mcp --version
```

## 创建新项目

使用以下命令创建新的MCP服务器项目：

```bash
aio-mcp --create-project my-project --author "您的名字" --github "https://github.com/yourusername/your-repo"
```

## 依赖关系

- mcp >= 0.5.0
- uvicorn >= 0.17.6
- starlette >= 0.20.4

## 开发设置

如果您想为此项目做贡献，可以按照以下方式设置开发环境：

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python -m unittest discover -s aio_mcp_server_framework/tests
``` 
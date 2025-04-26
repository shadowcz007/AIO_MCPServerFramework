# AIO MCP服务器框架

这是一个用于快速开发MCP（Model Control Protocol）服务器的综合框架。MCP协议是一种用于与大型语言模型（LLM）进行通信的标准，AIO MCP服务器框架简化了MCP服务器的开发和部署流程。

## 特性

- 🚀 快速启动MCP服务器
- 🧩 模块化设计，方便扩展
- 📝 内置日志和通知系统
- 🔧 完整的命令行工具支持
- 🌐 同时支持stdio和SSE通信模式
- 💾 自动配置保存和加载

## 安装

```bash
pip install aio-mcp-server-framework
```

详细的安装说明请参阅 [INSTALL.md](INSTALL.md)。

## 快速开始

使用命令行工具创建新项目：

```bash
aio-mcp --create-project my-mcp-server
cd my-mcp-server
pip install -r requirements.txt
python main.py
```

## 项目结构

```
aio_mcp_server_framework/
├── aio_mcp_server_framework/    # 包主目录
│   ├── __init__.py             # 包初始化文件
│   ├── core.py                 # 核心功能模块
│   ├── cli.py                  # 命令行接口
│   ├── templates/              # 项目模板
│   │   └── main.py.template    # 主程序模板
│   └── tests/                  # 测试目录
│       ├── __init__.py         # 测试包初始化
│       └── test_core.py        # 核心功能测试
├── pyproject.toml              # 项目构建配置
├── setup.py                    # 安装脚本
├── setup.cfg                   # 安装配置
├── MANIFEST.in                 # 包含清单
├── LICENSE                     # 许可证
├── README.md                   # 项目说明
├── INSTALL.md                  # 安装说明
└── build.py                    # 构建脚本
```

## 示例代码

```python
from aio_mcp_server_framework import MCPServerFramework, BaseModuleManager, SERVICE_VERSION
from typing import Dict, List
import mcp.types as types

# 创建自定义模块管理器
class MyModuleManager(BaseModuleManager):
    async def initialize(self, **kwargs) -> None:
        # 初始化模块
        print("模块初始化成功")
    
    def get_tools(self) -> List[types.Tool]:
        # 返回工具列表
        return [
            types.Tool(
                name="my_tool",
                description="这是一个示例工具",
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "消息内容"
                        }
                    },
                    "required": ["message"]
                }
            )
        ]
    
    async def call_tool(self, name: str, arguments: Dict, ctx=None) -> Dict:
        # 处理工具调用
        if name == "my_tool":
            message = arguments.get("message", "")
            if ctx:
                await ctx.info(f"接收到消息: {message}")
            return {"result": f"处理结果: {message}"}
        raise ValueError(f"未知工具: {name}")

def main():
    # 创建框架实例
    framework = MCPServerFramework(
        name="我的MCP服务器",
        version="1.0.0",
        description="这是我的第一个MCP服务器",
        author="您的名字",
        github="https://github.com/yourusername/your-repo",
        module_parameters={
            "api_key": {
                "type": "str",
                "help": "API密钥",
                "default": ""
            }
        }
    )
    
    # 运行服务器
    framework.run(
        create_module_manager_func=lambda **kwargs: MyModuleManager()
    )

if __name__ == "__main__":
    main()
```

## 环境变量支持

您可以使用环境变量设置以下配置：

- `AIO_MCP_PORT`: 服务器端口号
- `AIO_MCP_TRANSPORT`: 传输类型 (stdio 或 sse)

## 开发自定义模块

要开发自定义模块，需要继承`BaseModuleManager`类并实现以下方法：

1. `initialize(**kwargs)` - 初始化模块
2. `get_tools()` - 返回工具列表
3. `call_tool(name, arguments, ctx)` - 处理工具调用

## 构建与发布

构建包:

```bash
python build.py build
```

安装到本地:

```bash
python build.py install
```

详细信息请参考 [build.py](build.py) 脚本。

## 许可证

MIT 
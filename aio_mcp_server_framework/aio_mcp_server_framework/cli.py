import sys
import argparse
from importlib.metadata import version
from pathlib import Path
import shutil
import os
from .core import SERVICE_VERSION, MCPServerFramework

def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(description="AIO MCP服务器框架")
    parser.add_argument('--version', action='store_true', help='显示版本信息')
    parser.add_argument('--create-project', type=str, help='创建新的MCP服务器项目')
    parser.add_argument('--author', type=str, help='项目作者名称 (用于 --create-project)')
    parser.add_argument('--github', type=str, help='GitHub仓库地址 (用于 --create-project)')
    parser.add_argument('--description', type=str, help='项目描述 (用于 --create-project)')
    
    args = parser.parse_args()
    
    if args.version:
        try:
            pkg_version = version("aio-mcp-server-framework")
        except:
            pkg_version = SERVICE_VERSION
        print(f"AIO MCP服务器框架 v{pkg_version}")
        return 0
    
    if args.create_project:
        project_name = args.create_project
        project_dir = Path(project_name)
        
        if project_dir.exists():
            print(f"错误: 目录 '{project_name}' 已存在")
            return 1
            
        # 获取参数或使用默认值
        author = args.author or "AIO MCP用户"
        github = args.github or "https://github.com/yourusername/your-repo"
        description = args.description or f"{project_name} - 基于AIO MCP服务器框架创建的项目"
        
        # 创建项目目录
        project_dir.mkdir(parents=True)
        
        # 获取模板目录
        template_dir = Path(__file__).parent / "templates"
        
        # 检查是否存在模板文件
        main_template_path = template_dir / "main.py.template"
        if main_template_path.exists():
            # 使用模板创建main.py
            with open(main_template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            
            # 替换模板变量
            template_content = template_content.replace("{{PROJECT_NAME}}", project_name)
            template_content = template_content.replace("{{PROJECT_DESCRIPTION}}", description)
            template_content = template_content.replace("{{AUTHOR}}", author)
            template_content = template_content.replace("{{GITHUB_URL}}", github)
            
            # 写入main.py
            main_file = project_dir / "main.py"
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(template_content)
        else:
            # 如果没有模板，创建基本main.py
            main_file = project_dir / "main.py"
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(f"""#!/usr/bin/env python3
import sys
from aio_mcp_server_framework import MCPServerFramework, BaseModuleManager, SERVICE_VERSION
from typing import Dict, List
import mcp.types as types

# 示例模块管理器
class ExampleModuleManager(BaseModuleManager):
    async def initialize(self, **kwargs) -> None:
        # 在这里初始化您的模块
        print("模块初始化成功")
    
    def get_tools(self) -> List[types.Tool]:
        # 返回您的工具列表
        return [
            types.Tool(
                name="example_tool",
                description="这是一个示例工具",
                parameters={{
                    "type": "object",
                    "properties": {{
                        "message": {{
                            "type": "string",
                            "description": "消息内容"
                        }}
                    }},
                    "required": ["message"]
                }}
            )
        ]
    
    async def call_tool(self, name: str, arguments: Dict, ctx=None) -> Dict:
        # 处理工具调用
        if name == "example_tool":
            message = arguments.get("message", "")
            if ctx:
                await ctx.info(f"接收到消息: {{message}}")
            return {{"result": f"您发送的消息是: {{message}}"}}
        raise ValueError(f"未知工具: {{name}}")

def main():
    # 创建框架实例
    framework = MCPServerFramework(
        name="{project_name}",
        version=SERVICE_VERSION,
        description="{description}",
        author="{author}",
        github="{github}",
        module_parameters={{
            "example_param": {{
                "type": "str",
                "help": "示例参数",
                "default": "默认值"
            }}
        }}
    )
    
    # 运行服务器
    framework.run(
        create_module_manager_func=lambda **kwargs: ExampleModuleManager()
    )

if __name__ == "__main__":
    main()
""")
        
        # 创建requirements.txt
        req_file = project_dir / "requirements.txt"
        with open(req_file, "w", encoding="utf-8") as f:
            f.write("""aio-mcp-server-framework
mcp>=0.5.0
uvicorn>=0.17.6
starlette>=0.20.4
""")
        
        # 创建README.md
        readme_file = project_dir / "README.md"
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(f"""# {project_name}

{description}

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 作者

{author}

## 仓库

{github}
""")
        
        print(f"✅ 项目 '{project_name}' 创建成功!")
        print(f"  📁 项目目录: {project_dir.absolute()}")
        print(f"  📝 请修改 main.py 文件以实现您的自定义功能")
        print(f"  🚀 使用以下命令启动服务器:")
        print(f"    cd {project_name}")
        print(f"    pip install -r requirements.txt")
        print(f"    python main.py")
        
        return 0
    
    # 如果没有参数，显示帮助信息
    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
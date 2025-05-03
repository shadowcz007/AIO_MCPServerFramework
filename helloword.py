import logging
from MCPServerFramework import BaseModuleManager, MCPServerFramework
import mcp.types as types

# 1. logging 配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HelloWorld")

# 2. 最简单的模块管理器
class HelloWorldModuleManager(BaseModuleManager):
    async def initialize(self, **kwargs):
        logger.info("HelloWorldModuleManager 初始化完成")

    def get_tools(self):
        return [
            types.Tool(
                name="hello",
                description="返回Hello World",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "你的名字"}
                    },
                    "required": ["name"]
                }
            )
        ]

    async def call_tool(self, name, arguments, ctx=None):
        if name == "hello":
            user = arguments.get("name", "World")
            logger.info(f"收到 hello 工具调用，参数 name={user}")
            return {"message": f"Hello, {user}!"}
        return {"error": "未知工具"}

    def get_prompt_templates(self):
        return [
            types.Prompt(
                name="hello_prompt",
                description="打招呼的提示词",
                arguments=[
                    types.PromptArgument(
                        name="name",
                        description="你的名字",
                        required=False,
                        default="World"
                    )
                ]
            )
        ]

    def get_prompt_content(self, name, arguments):
        if name == "hello_prompt":
            user = arguments.get("name", "World") if arguments else "World"
            logger.info(f"生成 hello_prompt，name={user}")
            return types.GetPromptResult(
                description="打招呼的提示词",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"你好，{user}！"
                        )
                    )
                ]
            )
        raise ValueError(f"未知提示模板: {name}")

# 3. module_parameters 示例
module_parameters = {
    "greeting": {
        "type": "str",
        "help": "自定义问候语",
        "default": "Hello"
    }
}

# 4. create_module_manager 示例
def create_module_manager(**kwargs):
    logger.info("create_module_manager 被调用")
    return HelloWorldModuleManager()

# 5. 启动服务
if __name__ == "__main__":
    server = MCPServerFramework(
        name="HelloWorldAPI",
        version="0.1",
        description="最简单的Hello World API服务示例",
        author="你的名字",
        github="https://github.com/your/repo",
        module_parameters=module_parameters
    )
    server.run(
        create_module_manager_func=create_module_manager,
        get_prompt_templates_func=lambda: HelloWorldModuleManager().get_prompt_templates(),
        get_prompt_content_func=lambda name, args: HelloWorldModuleManager().get_prompt_content(name, args)
    )
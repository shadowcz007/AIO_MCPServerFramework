import sys, os
import json
from pathlib import Path
from datetime import datetime
import logging
from typing import Any, List, Dict, Callable, Optional, Union
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.types as types
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import asyncio
from mcp.shared.context import RequestContext
import logging


# 服务版本号
SERVICE_VERSION = "1.2.2"

class ExtendedRequestContext:
    """扩展的请求上下文，增加了日志功能和客户端通知机制"""
    
    def __init__(self, original_ctx):
        """初始化扩展上下文
        
        Args:
            original_ctx: 原始的RequestContext对象
        """
        self._original_ctx = original_ctx
        
    def __getattr__(self, name):
        """获取原始上下文的属性"""
        return getattr(self._original_ctx, name)
        
    async def info(self, message, logger_name="default"):
        """发送信息日志
        
        Args:
            message: 日志消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        logging.getLogger(logger_name).info(message)
        
        # 发送到客户端
        if self._original_ctx and hasattr(self._original_ctx, "session"):
            if hasattr(self._original_ctx.session, "send_log_message"):
                try:
                    await self._original_ctx.session.send_log_message(
                        level="info", 
                        data=message, 
                        logger=logger_name
                    )
                except Exception as e:
                    logging.error(f"向客户端发送日志消息失败: {e}")
        
    async def error(self, message, logger_name="default"):
        """发送错误日志
        
        Args:
            message: 错误消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        logging.getLogger(logger_name).error(message)
        
        # 发送到客户端
        if self._original_ctx and hasattr(self._original_ctx, "session"):
            if hasattr(self._original_ctx.session, "send_log_message"):
                try:
                    await self._original_ctx.session.send_log_message(
                        level="error", 
                        data=message, 
                        logger=logger_name
                    )
                except Exception as e:
                    logging.error(f"向客户端发送日志消息失败: {e}")
        
    async def warning(self, message, logger_name="default"):
        """发送警告日志
        
        Args:
            message: 警告消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        logging.getLogger(logger_name).warning(message)
        
        # 发送到客户端
        if self._original_ctx and hasattr(self._original_ctx, "session"):
            if hasattr(self._original_ctx.session, "send_log_message"):
                try:
                    await self._original_ctx.session.send_log_message(
                        level="warning", 
                        data=message, 
                        logger=logger_name
                    )
                except Exception as e:
                    logging.error(f"向客户端发送日志消息失败: {e}")
        
    async def debug(self, message, logger_name="default"):
        """发送调试日志
        
        Args:
            message: 调试消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        logging.getLogger(logger_name).debug(message)
        
        # 发送到客户端
        if self._original_ctx and hasattr(self._original_ctx, "session"):
            if hasattr(self._original_ctx.session, "send_log_message"):
                try:
                    await self._original_ctx.session.send_log_message(
                        level="debug", 
                        data=message, 
                        logger=logger_name
                    )
                except Exception as e:
                    logging.error(f"向客户端发送日志消息失败: {e}")
    
    async def report_progress(self, progress: float, total: float = None):
        """报告进度
        
        Args:
            progress: 当前进度
            total: 总进度
        """
        if self._original_ctx and hasattr(self._original_ctx, "session"):
            # 获取进度令牌
            progress_token = None
            if hasattr(self._original_ctx, "meta") and self._original_ctx.meta:
                progress_token = getattr(self._original_ctx.meta, "progressToken", None)
            
            # 如果没有进度令牌，可以使用请求ID作为标识
            if progress_token is None:
                progress_token = str(self._original_ctx.request_id)
                
            # 发送进度通知
            if hasattr(self._original_ctx.session, "send_progress_notification"):
                try:
                    await self._original_ctx.session.send_progress_notification(
                        progress_token=progress_token,
                        progress=progress,
                        total=total
                    )
                except Exception as e:
                    logging.error(f"向客户端发送进度通知失败: {e}")

# 抽象基础模块管理器接口
class BaseModuleManager:
    """模块管理器的抽象基类，所有功能模块管理器需继承此类"""
    
    def __init__(self):
        self.change_listeners = []
        
    def add_change_listener(self, listener: Callable) -> None:
        """添加变更监听器"""
        self.change_listeners.append(listener)
        
    def notify_changes(self) -> None:
        """通知所有监听器数据已变更"""
        for listener in self.change_listeners:
            listener()
    
    async def initialize(self, **kwargs) -> None:
        """初始化模块，子类必须实现"""
        raise NotImplementedError("子类必须实现initialize方法")
    
    def get_tools(self) -> List[types.Tool]:
        """返回此模块提供的工具列表，子类必须实现"""
        raise NotImplementedError("子类必须实现get_tools方法")
    
    async def call_tool(self, name: str, arguments: Dict, ctx=None) -> Dict:
        """调用工具，子类必须实现"""
        raise NotImplementedError("子类必须实现call_tool方法")
    
    def get_prompt_templates(self) -> List[types.Prompt]:
        """获取提示模板列表，子类可以覆盖此方法提供提示模板"""
        return []
    
    def get_prompt_content(self, name: str, arguments: Dict[str, str] | None) -> types.GetPromptResult:
        """获取提示模板内容，子类可以覆盖此方法提供提示模板内容"""
        raise ValueError(f"未找到提示模板: {name}")


class MCPServerCore:
    """MCP服务器核心类，负责管理模块和提供服务框架"""
    
    def __init__(self, name: str, version: str, module_manager: BaseModuleManager, instructions: str = "", 
                 get_prompt_templates_func=None, get_prompt_content_func=None):
        self.name = name
        self.version = version
        self.instructions = instructions
        self.module_manager = module_manager
        self.get_prompt_templates_func = get_prompt_templates_func
        self.get_prompt_content_func = get_prompt_content_func
        self.app = self._create_server()
        
    def _create_server(self) -> Server:
        """创建MCP服务器实例"""
        app = Server(
            self.name,
            version=self.version,
            instructions=self.instructions
        )
        
        # 自定义初始化选项
        def custom_initialization_options(
            server,
            notification_options: NotificationOptions | None = None,
            experimental_capabilities: Dict[str, Dict[str, Any]] | None = None,
        ) -> InitializationOptions:
            def pkg_version(package: str) -> str:
                try:
                    from importlib.metadata import version
                    v = version(package)
                    if v is not None:
                        return v
                except Exception:
                    pass
                return "unknown"
                
            return InitializationOptions(
                server_name=server.name,
                server_version=server.version if server.version else pkg_version("mcp"),
                capabilities=server.get_capabilities(
                    notification_options or NotificationOptions(
                        resources_changed=True,
                        tools_changed=True
                    ),
                    experimental_capabilities or {},
                ),
                instructions=server.instructions,
            )
        
        app.create_initialization_options = lambda self=app: custom_initialization_options(
            self,
            notification_options=NotificationOptions(
                resources_changed=True,
                tools_changed=True,
                prompts_changed=True
            ),
            experimental_capabilities={"mix": {}}
        )
        
        # 添加资源变更通知
        async def notify_resources_changed():
            """通知客户端资源列表已变更"""
            logger = logging.getLogger(__name__)
            logger.debug("发送资源变更通知")
            try:
                await app.request_context.session.send_resource_list_changed()
            except Exception as e:
                logger.error(f"发送资源变更通知失败: {e}")
        
        def on_data_changed():
            """当数据变更时触发异步通知"""
            asyncio.create_task(notify_resources_changed())
        
        self.module_manager.add_change_listener(on_data_changed)
        
        # 注册工具列表处理函数
        @app.list_tools()
        async def handle_list_tools():
            return self.module_manager.get_tools()
        
        # 注册工具调用处理函数
        @app.call_tool()
        async def handle_call_tool(name: str, arguments: Dict | None) -> List:
            try:
                if not arguments:
                    raise ValueError("Missing arguments")
                
                # 获取当前请求上下文
                current_ctx = app.request_context
                extended_ctx = ExtendedRequestContext(current_ctx)

                # 将请求上下文传递给模块的call_tool方法
                result = await self.module_manager.call_tool(name, arguments, ctx=extended_ctx)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False)
                )]
                
            except Exception as e:
                print(f"Error in tool {name}: {str(e)}")
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]
        
        # 注册提示模板列表处理函数
        @app.list_prompts()
        async def handle_list_prompts() -> List[types.Prompt]:
            try:
                # 优先使用外部提供的函数，如果没有则使用模块管理器的方法
                if self.get_prompt_templates_func is not None:
                    return self.get_prompt_templates_func()
                else:
                    return self.module_manager.get_prompt_templates()
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"获取提示模板列表出错: {e}")
                return []
        
        # 注册获取提示模板处理函数
        @app.get_prompt()
        async def handle_get_prompt(name: str, arguments: Dict[str, str] | None) -> types.GetPromptResult:
            try:
                logger = logging.getLogger(__name__)
                logger.debug(f"获取提示模板: {name} 参数: {arguments}")
                
                # 优先使用外部提供的函数，如果没有则使用模块管理器的方法
                if self.get_prompt_content_func is not None:
                    return self.get_prompt_content_func(name, arguments)
                else:
                    return self.module_manager.get_prompt_content(name, arguments)
            except Exception as e:
                logger.error(f"获取提示模板内容出错: {e}")
                raise
        
        return app


# 通用服务器启动与配置框架
class MCPServerFramework:
    """MCP服务器框架，处理配置、命令行参数、启动服务等通用功能"""
    
    def __init__(self, 
                 name: str, 
                 version: str, 
                 description: str, 
                 author: str, 
                 github: str,
                 module_parameters: Dict[str, Dict] = None):
        """
        初始化服务器框架
        
        Args:
            name: 服务名称
            version: 服务版本
            description: 服务描述
            author: 作者信息
            github: GitHub仓库地址
            module_parameters: 模块特定参数的配置，格式为 {参数名: {type: 类型, help: 帮助信息, default: 默认值}}
        """
        self.name = name
        self.version = version  
        self.description = description
        self.author = author
        self.github = github
        self.module_parameters = module_parameters or {}
        self.config = self._load_config()
        
    def _setup_logging(self, log_level=logging.INFO) -> logging.Logger:
        """设置日志系统"""
        if getattr(sys, 'frozen', False):
            log_path = Path(sys.executable).parent / "logs"
        else:
            log_path = Path(__file__).parent / "logs"
        
        # 创建日志目录
        log_path.mkdir(exist_ok=True)
        
        # 设置日志文件名（使用当前日期）
        log_file = log_path / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 配置日志
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        return logger
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        config_path = self._get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_config(self, config: Dict) -> None:
        """保存配置到文件"""
        config_path = self._get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / "config.json"
        else:
            return Path(__file__).parent / "config.json"
    
    def _get_user_input(self, prompt: str, default: str) -> str:
        """获取用户输入，如果用户直接回车则使用默认值"""
        try:
            user_input = input(f"{prompt} (默认: {default}): ").strip()
            if user_input.startswith('\ufeff'):
                user_input = user_input[1:]
            return user_input if user_input else default
        except Exception as e:
            print(f"输入处理错误: {e}")
            return default
    
    def _handle_help_request(self, request_id: str) -> None:
        """处理帮助请求，返回标准JSON-RPC格式的帮助信息"""
        # 构建模块参数Schema
        module_params_schema = {}
        for param_name, param_config in self.module_parameters.items():
            module_params_schema[param_name] = {
                "type": param_config["type"],
                "description": param_config["help"],
                "default": param_config.get("default", "")
            }
        
        help_response = {
            "jsonrpc": "2.0",
            "result": {
                "type": "mcp",
                "description": self.description,
                "author": self.author,
                "version": self.version,
                "github": self.github,
                "transport": ["stdio", "sse"],
                "methods": [
                    {
                        "name": "help",
                        "description": "显示此帮助信息。"
                    },
                    {
                        "name": "start",
                        "description": "启动服务器",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "transport": {
                                    "type": "string",
                                    "enum": ["stdio", "sse"],
                                    "description": "传输类型",
                                    "default": "sse"
                                },
                                "port": {
                                    "type": "integer",
                                    "description": "服务器端口号 (仅在 transport=sse 时需要设置)",
                                    "default": 8080
                                },
                                **module_params_schema
                            }
                        }
                    }
                ]
            },
            "id": request_id
        }
        print(json.dumps(help_response, ensure_ascii=False, indent=2))
    
    async def _run_stdio_server(self, create_module_manager_func, params, 
                            get_prompt_templates_func=None, get_prompt_content_func=None):
        """运行stdio模式服务器"""
        from mcp.server.stdio import stdio_server
        
        # 创建模块管理器
        module_manager = create_module_manager_func(**params)
        await module_manager.initialize(**params)
        
        # 创建服务器核心
        server_core = MCPServerCore(
            self.name,
            self.version,
            module_manager,
            instructions=self.description,
            get_prompt_templates_func=get_prompt_templates_func,
            get_prompt_content_func=get_prompt_content_func
        )
        
        # 运行stdio服务器
        async with stdio_server() as (read_stream, write_stream):
            await server_core.app.run(
                read_stream,
                write_stream,
                server_core.app.create_initialization_options()
            )
    
    async def _run_sse_server(self, port: int, create_module_manager_func, params,
                             get_prompt_templates_func=None, get_prompt_content_func=None):
        """运行SSE模式服务器"""
        from mcp.server.sse import SseServerTransport
        
        # 创建模块管理器
        module_manager = create_module_manager_func(**params)
        await module_manager.initialize(**params)
        
        # 创建服务器核心
        server_core = MCPServerCore(
            self.name,
            self.version,
            module_manager,
            instructions=self.description,
            get_prompt_templates_func=get_prompt_templates_func,
            get_prompt_content_func=get_prompt_content_func
        )
        
        # 设置 SSE 服务器
        sse = SseServerTransport("/messages/")
        
        # 定义SSE处理函数
        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server_core.app.run(
                    streams[0], streams[1], server_core.app.create_initialization_options()
                )
                
        # 添加 CORS 中间件配置        
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
                
        # 创建Starlette应用
        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
            middleware=middleware
        )

        # 启动服务器
        import uvicorn
        import socket

        def get_local_ip():
            try:
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                return ip
            except:
                return "127.0.0.1"

        local_ip = get_local_ip()
        print(f"\n🚀 服务器启动成功!")
        print(f"📡 本地访问地址: http://127.0.0.1:{port}")
        print(f"📡 局域网访问地址: http://{local_ip}:{port}")
        print("\n按 CTRL+C 停止服务器\n")

        config = uvicorn.Config(
            starlette_app, 
            host="0.0.0.0", 
            port=port,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self, create_module_manager_func: Callable, 
            get_prompt_templates_func=None, get_prompt_content_func=None):
        """
        运行服务器框架，处理命令行参数、配置加载和服务启动
        
        Args:
            create_module_manager_func: 创建模块管理器实例的函数
            get_prompt_templates_func: 获取提示模板列表的函数
            get_prompt_content_func: 获取提示模板内容的函数
        """
        import argparse
        
        # 创建命令行参数解析器
        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument('--port', type=int, help='服务器端口号 (仅在 transport=sse 时需要)')
        parser.add_argument('--transport', type=str, choices=['stdio', 'sse'], default='sse', help='传输类型 (stdio 或 sse)')
        
        # 添加模块特定的参数
        for param_name, param_config in self.module_parameters.items():
            parser.add_argument(
                f'--{param_name}', 
                type=eval(param_config["type"]) if param_config["type"] in ["int", "str", "float", "bool"] else str,
                help=param_config["help"]
            )
        
        args = parser.parse_args()
        
        # 处理stdio模式
        if args.transport == 'stdio':
            # 提取模块参数
            params = {}
            for param_name in self.module_parameters:
                param_value = getattr(args, param_name.replace('-', '_'), None)
                if param_value is not None:
                    params[param_name] = param_value
            
            # 运行stdio服务器
            asyncio.run(self._run_stdio_server(
                create_module_manager_func, 
                params,
                get_prompt_templates_func, 
                get_prompt_content_func
            ))
            sys.exit(0)
        
        # 加载上次的配置
        last_config = self.config
        port = None
        params = {}
        
        # 检查是否有 stdin 输入
        try:
            if not sys.stdin.isatty():
                json_str = sys.stdin.read().strip()
                if json_str:
                    if json_str.startswith('\ufeff'):
                        json_str = json_str[1:]
                    stdin_config = json.loads(json_str)
                    
                    # 检查是否是帮助请求
                    if (stdin_config.get("jsonrpc") == "2.0" and 
                        stdin_config.get("method") == "help" and 
                        "id" in stdin_config):
                        
                        self._handle_help_request(stdin_config["id"])
                        sys.exit(0)

                    if (stdin_config.get("jsonrpc") == "2.0" and 
                        stdin_config.get("method") == "start" and 
                        "params" in stdin_config):
                        
                        cmd_params = stdin_config["params"]
                        transport = cmd_params.get("transport", "sse")
                        
                        # 提取模块参数
                        for param_name in self.module_parameters:
                            if param_name in cmd_params:
                                params[param_name] = cmd_params[param_name]
                        
                        if transport == "sse":
                            port = cmd_params.get("port")
                            if port is None:
                                port = 8080
                        else:
                            port = None

        except Exception as e:
            print(f"处理 stdin 输入时出错: {e}")
        
        # 获取 transport 参数
        transport = args.transport

        if transport != "stdio":
            if port is None:
                port = args.port

            if port is None:
                default_port = str(last_config.get('port', 8080))
                if default_port == "None":
                    default_port = 8080
                    
                port = int(self._get_user_input("请输入服务器端口号", str(default_port)))

        # 获取模块参数
        for param_name, param_config in self.module_parameters.items():
            if param_name not in params:
                arg_value = getattr(args, param_name.replace('-', '_'), None)
                if arg_value is not None:
                    params[param_name] = arg_value
                else:
                    # 从配置文件获取默认值
                    saved_value = last_config.get(param_name)
                    default_value = param_config.get("default", "")
                    
                    if transport == "sse" and param_config.get("interactive", True):
                        # 交互式输入
                        value = self._get_user_input(
                            f"请输入{param_config['help']}", 
                            str(saved_value if saved_value is not None else default_value)
                        )
                        # 转换类型
                        if param_config["type"] == "int":
                            params[param_name] = int(value)
                        elif param_config["type"] == "float":
                            params[param_name] = float(value)
                        elif param_config["type"] == "bool":
                            params[param_name] = value.lower() in ("yes", "true", "t", "1")
                        else:
                            params[param_name] = value
                    else:
                        # 非交互式使用默认值
                        params[param_name] = saved_value if saved_value is not None else default_value
        
        # 处理Windows事件循环策略
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # 保存配置
        save_config = {
            'port': port,
            **params
        }
        self._save_config(save_config)

        # 打印启动信息
        if sys.platform == "darwin":
            print(f"\033[1;32mStarting {self.name}\033[0m")
            print(f"\033[1;34mby {self.author} - GitHub: {self.github}\033[0m")
        else:
            print(f"\033[1;32mStarting {self.name}\033[0m")
            print(f"\033[1;34mby {self.author} \033]8;;{self.github}\033\\GitHub\033]8;;\033\\\033[0m")
        print()
        print()

        # 启动服务器
        if transport == "sse":
            asyncio.run(self._run_sse_server(
                port, 
                create_module_manager_func, 
                params,
                get_prompt_templates_func, 
                get_prompt_content_func
            ))
        else:
            asyncio.run(self._run_stdio_server(
                create_module_manager_func, 
                params,
                get_prompt_templates_func, 
                get_prompt_content_func
            )) 
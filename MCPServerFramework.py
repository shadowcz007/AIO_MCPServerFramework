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
from anyio import Event
import signal
import psutil
import uvicorn

# 服务版本号
SERVICE_VERSION = "1.3.0"

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
        # logging.getLogger(logger_name).info(message)
        self.logger.info(message)
        
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
                    self.logger.error(f"向客户端发送日志消息失败: {e}")
        
    async def error(self, message, logger_name="default"):
        """发送错误日志
        
        Args:
            message: 错误消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        # logging.getLogger(logger_name).error(message)
        self.logger.error(message)
        
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
                    self.logger.error(f"向客户端发送日志消息失败: {e}")
        
    async def warning(self, message, logger_name="default"):
        """发送警告日志
        
        Args:
            message: 警告消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        # logging.getLogger(logger_name).warning(message)
        self.logger.warning(message)

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
                    self.logger.error(f"向客户端发送日志消息失败: {e}")
        
    async def debug(self, message, logger_name="default"):
        """发送调试日志
        
        Args:
            message: 调试消息
            logger_name: 日志记录器名称
        """
        # 记录到本地日志
        # logging.getLogger(logger_name).debug(message)
        self.logger.debug(message)
        
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
                print("#DEBUG# progress_token", self._original_ctx.meta)
                progress_token = getattr(self._original_ctx.meta, "progressToken", None)
            
            # 如果没有进度令牌，可以使用请求ID作为标识
            if progress_token is None:
                return
                
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
            logger = self.logger
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
                extended_ctx.logger = self.logger
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
                logger = self.logger
                logger.error(f"获取提示模板列表出错: {e}")
                return []
        
        # 注册获取提示模板处理函数
        @app.get_prompt()
        async def handle_get_prompt(name: str, arguments: Dict[str, str] | None) -> types.GetPromptResult:
            try:
                logger = self.logger
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
        """
        self.name = name
        self.version = version  
        self.description = description
        self.author = author
        self.github = github
        self.module_parameters = module_parameters or {}
        
        # 创建 anyio Event 用于内部事件同步
        self._shutdown_event = Event()
        
        # 首先设置日志系统并保存logger实例
        self.logger = self._setup_logging()
        
        self.config = self._load_config()
        
        # 获取父进程ID
        self.parent_pid = os.getppid()
        self.logger.info(f"父进程ID: {self.parent_pid}")
        
        # 设置信号处理器
        def handle_shutdown(signum, frame):
            signal_names = {
                signal.SIGTERM: "SIGTERM",
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGBREAK: "SIGBREAK" if hasattr(signal, 'SIGBREAK') else None
            }
            signal_name = signal_names.get(signum, str(signum))
            self.logger.warning(f"收到系统终止信号: {signal_name}")
            self.logger.info("开始执行优雅退出流程...")
            # 使用 anyio 的方式设置事件
            asyncio.create_task(self._trigger_shutdown())

        # 注册所有可能的终止信号
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        if hasattr(signal, 'SIGBREAK'):  # Windows specific
            signal.signal(signal.SIGBREAK, handle_shutdown)
            
        # 启动父进程监控任务
        # asyncio.create_task(self._monitor_parent_process())
        
    async def _monitor_parent_process(self):
        """监控父进程状态"""
        while True:
            try:
                # 检查父进程是否存在
                if not psutil.pid_exists(self.parent_pid):
                    self.logger.warning("父进程已终止，开始执行优雅退出...")
                    await self._trigger_shutdown()
                    break
                
                # 检查父进程状态
                parent = psutil.Process(self.parent_pid)
                if parent.status() == psutil.STATUS_ZOMBIE:
                    self.logger.warning("父进程处于僵尸状态，开始执行优雅退出...")
                    await self._trigger_shutdown()
                    break
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.logger.warning("无法访问父进程，开始执行优雅退出...")
                await self._trigger_shutdown()
                break
                
            except Exception as e:
                self.logger.error(f"监控父进程时发生错误: {e}")
                
            # 每秒检查一次
            await asyncio.sleep(1)

    async def _trigger_shutdown(self):
        """触发关闭事件的异步方法"""
        self._shutdown_event.set()
        
        # 获取当前进程ID
        current_pid = os.getpid()
        
        # 在Windows环境下，使用CTRL_BREAK_EVENT
        if sys.platform == "win32":
            try:
                # 发送CTRL_BREAK_EVENT信号
                os.kill(current_pid, signal.CTRL_BREAK_EVENT)
            except Exception as e:
                self.logger.error(f"发送CTRL_BREAK_EVENT失败: {e}")
                # 如果发送信号失败，直接调用sys.exit
                sys.exit(1)
        else:
            # 在非Windows环境下，使用SIGTERM
            try:
                os.kill(current_pid, signal.SIGTERM)
            except Exception as e:
                self.logger.error(f"发送SIGTERM失败: {e}")
                # 如果发送信号失败，直接调用sys.exit
                sys.exit(1)
    
    def _setup_logging(self, log_level=logging.DEBUG) -> logging.Logger:
        """设置日志系统"""
        if getattr(sys, 'frozen', False):
            log_path = Path(sys.executable).parent / "logs"
        else:
            log_path = Path(__file__).parent / "logs"
        
        # 创建日志目录
        log_path.mkdir(exist_ok=True)
        
        # 设置日志文件名（使用当前日期）
        log_file = log_path / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 创建logger实例
        logger = logging.getLogger(self.name)
        logger.setLevel(log_level)  # 设置日志级别
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # 创建控制台处理器
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # 清除可能存在的旧处理器
        logger.handlers.clear()
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
        # 防止日志向上传播
        logger.propagate = False
        
        logger.info(f"日志路径: {log_file}")
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
        
        logger = self.logger
        logger.info("准备启动 stdio 模式服务器...")
        
        try:
            # 创建模块管理器
            logger.info("正在初始化模块管理器...")
            module_manager = create_module_manager_func(**params)
            await module_manager.initialize(**params)
            logger.info("模块管理器初始化完成")
            
            # 创建服务器核心
            logger.info("正在创建服务器核心...")
            server_core = MCPServerCore(
                self.name,
                self.version,
                module_manager,
                instructions=self.description,
                get_prompt_templates_func=get_prompt_templates_func,
                get_prompt_content_func=get_prompt_content_func
            )
            server_core.logger = self.logger
            logger.info("服务器核心创建完成")
 

            async with stdio_server() as (read_stream, write_stream):
                logger.info("stdio 服务器启动成功")
                # 启动父进程监控
                asyncio.create_task(self._monitor_parent_process())
                await server_core.app.run(
                    read_stream,
                    write_stream,
                    server_core.app.create_initialization_options()
                )
                
        except Exception as e:
            logger.error(f"服务器启动失败: {e}")
            raise
        finally:
            try:
                logger.info("服务器正在关闭...")
                # 确保日志被写入
                for handler in logger.handlers:
                    handler.flush()
                logger.info("服务器已完全关闭")
                # 再次确保最后的日志被写入
                for handler in logger.handlers:
                    handler.flush()
            except Exception as e:
                print(f"关闭时发生错误: {e}")
    
    async def _run_sse_server(self, port: int, create_module_manager_func, params,
                             get_prompt_templates_func=None, get_prompt_content_func=None):
        """运行SSE模式服务器"""
        from mcp.server.sse import SseServerTransport
        
        logger = self.logger
        logger.info(f"准备启动 SSE 模式服务器，端口: {port}")
        
        try:
            # 创建模块管理器
            logger.info("正在初始化模块管理器...")
            module_manager = create_module_manager_func(**params)
            await module_manager.initialize(**params)
            logger.info("模块管理器初始化完成")
            
            # 创建服务器核心
            logger.info("正在创建服务器核心...")
            server_core = MCPServerCore(
                self.name,
                self.version,
                module_manager,
                instructions=self.description,
                get_prompt_templates_func=get_prompt_templates_func,
                get_prompt_content_func=get_prompt_content_func
            )
            server_core.logger = self.logger
            logger.info("服务器核心创建完成")
            
            # 设置 SSE 服务器
            sse = SseServerTransport("/messages/")
            
            # 定义SSE处理函数
            async def handle_sse(request):
                logger.debug(f"新的 SSE 连接: {request.client}")
                try:
                    async with sse.connect_sse(
                        request.scope, request.receive, request._send
                    ) as streams:
                        await server_core.app.run(
                            streams[0], streams[1], server_core.app.create_initialization_options()
                        )
                except Exception as e:
                    logger.error(f"SSE 连接处理错误: {e}")
                    raise
                finally:
                    logger.debug(f"SSE 连接关闭: {request.client}")
                
            # 创建Starlette应用
            starlette_app = Starlette(
                debug=True,
                routes=[
                    Route("/", endpoint=handle_sse),
                    Mount("/messages/", app=sse.handle_post_message),
                ],
                middleware=[
                    Middleware(
                        CORSMiddleware,
                        allow_origins=["*"],
                        allow_credentials=True,
                        allow_methods=["*"],
                        allow_headers=["*"],
                    )
                ]
            )

            @starlette_app.on_event("startup")
            async def startup_event():
                logger.info("Web 服务器启动完成")

            @starlette_app.on_event("shutdown")
            async def shutdown_event():
                logger.info("Web 服务器开始关闭")
                # 这里可以添加额外的清理代码
                logger.info("Web 服务器清理完成")

            # 启动服务器
            config = uvicorn.Config(
                starlette_app, 
                host="0.0.0.0", 
                port=port,
                log_level="warning"
            )
            server = uvicorn.Server(config)
            
            try:
                logger.info("开始运行 Web 服务器...")
                await server.serve()
            except Exception as e:
                logger.error(f"Web 服务器运行错误: {e}")
                raise
            finally:
                logger.info("Web 服务器已关闭")
                
        except Exception as e:
            logger.error(f"SSE 服务器启动失败: {e}")
            raise
        finally:
            logger.info("SSE 服务器完全关闭")
    
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
        # 添加日志级别参数
        parser.add_argument('--log-level', 
                           type=str, 
                           choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                           default='INFO',
                           help='日志级别')
        
        # 添加模块特定的参数
        for param_name, param_config in self.module_parameters.items():
            parser.add_argument(
                f'--{param_name}', 
                type=eval(param_config["type"]) if param_config["type"] in ["int", "str", "float", "bool"] else str,
                help=param_config["help"]
            )
        
        args = parser.parse_args()
        
        # 设置日志级别
        log_level = getattr(logging, args.log_level)
        self.logger.setLevel(log_level)
        
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

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
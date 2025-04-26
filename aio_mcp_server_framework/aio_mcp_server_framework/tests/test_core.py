import unittest
from aio_mcp_server_framework import SERVICE_VERSION, ExtendedRequestContext, BaseModuleManager

class TestCore(unittest.TestCase):
    def test_version(self):
        """测试版本号格式是否正确"""
        # 检查版本号格式
        version_parts = SERVICE_VERSION.split('.')
        self.assertEqual(len(version_parts), 3)
        for part in version_parts:
            self.assertTrue(part.isdigit())
    
    def test_base_module_manager(self):
        """测试基础模块管理器"""
        manager = BaseModuleManager()
        # 检查初始状态
        self.assertEqual(len(manager.change_listeners), 0)
        
        # 添加监听器
        def test_listener():
            pass
        
        manager.add_change_listener(test_listener)
        self.assertEqual(len(manager.change_listeners), 1)
        
        # 检查抽象方法是否按预期工作
        with self.assertRaises(NotImplementedError):
            import asyncio
            asyncio.run(manager.initialize())
        
        with self.assertRaises(NotImplementedError):
            manager.get_tools()
        
        with self.assertRaises(NotImplementedError):
            import asyncio
            asyncio.run(manager.call_tool("test", {}))
        
        # 检查默认方法
        self.assertEqual(manager.get_prompt_templates(), [])
        
        with self.assertRaises(ValueError):
            manager.get_prompt_content("test", {})

if __name__ == '__main__':
    unittest.main() 
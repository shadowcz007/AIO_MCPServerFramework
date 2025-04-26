#!/usr/bin/env python3
"""
构建脚本 - 用于构建和安装 AIO MCP Server Framework 包
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, cwd=None):
    """运行命令并输出结果"""
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

def clean():
    """清理构建文件"""
    print("正在清理构建文件...")
    dirs_to_remove = [
        "build",
        "dist",
        "aio_mcp_server_framework.egg-info"
    ]
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            if sys.platform == "win32":
                run_command(["rmdir", "/s", "/q", dir_name])
            else:
                run_command(["rm", "-rf", dir_name])
    print("清理完成!")

def build():
    """构建包"""
    print("正在构建包...")
    ret = run_command([sys.executable, "-m", "pip", "install", "--upgrade", "build", "wheel", "setuptools"])
    if ret != 0:
        print("依赖安装失败")
        return False
    
    ret = run_command([sys.executable, "-m", "build"])
    if ret != 0:
        print("构建失败")
        return False
    
    print("构建成功!")
    return True

def install():
    """安装包到本地环境"""
    print("正在安装包到本地环境...")
    ret = run_command([sys.executable, "-m", "pip", "install", "--force-reinstall", "."])
    if ret != 0:
        print("安装失败")
        return False
    
    print("安装成功!")
    return True

def upload_to_pypi():
    """上传包到PyPI"""
    print("正在上传包到PyPI...")
    ret = run_command([sys.executable, "-m", "pip", "install", "--upgrade", "twine"])
    if ret != 0:
        print("安装twine失败")
        return False
    
    ret = run_command([sys.executable, "-m", "twine", "upload", "dist/*"])
    if ret != 0:
        print("上传失败")
        return False
    
    print("上传成功!")
    return True

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python build.py [clean|build|install|upload|all]")
        return 1
    
    command = sys.argv[1]
    
    if command == "clean":
        clean()
    elif command == "build":
        clean()
        build()
    elif command == "install":
        clean()
        if build():
            install()
    elif command == "upload":
        clean()
        if build():
            upload_to_pypi()
    elif command == "all":
        clean()
        if build():
            install()
            upload_to_pypi()
    else:
        print(f"未知命令: {command}")
        print("用法: python build.py [clean|build|install|upload|all]")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
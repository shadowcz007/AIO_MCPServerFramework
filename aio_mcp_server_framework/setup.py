from setuptools import setup, find_packages
import os
import sys

# 读取版本信息
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'aio_mcp_server_framework'))
from aio_mcp_server_framework import __version__

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="aio-mcp-server-framework",
    version=__version__,
    author="AIO MCP Server Framework Team",
    author_email="your-email@example.com",
    description="一个用于构建MCP服务器的综合框架",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/aio-mcp-server-framework",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "mcp>=0.5.0",
        "uvicorn>=0.17.6",
        "starlette>=0.20.4",
    ],
    entry_points={
        "console_scripts": [
            "aio-mcp=aio_mcp_server_framework.cli:main",
        ],
    },
) 
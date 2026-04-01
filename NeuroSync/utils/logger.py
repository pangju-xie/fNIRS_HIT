# utils/logger.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from utils.paths import LOG_DIR

def setup_logger(level=logging.INFO):
    """
    配置全局日志系统
    
    :param log_dir: 日志文件夹路径
    :param log_filename: 日志文件名
    :param level: 全局拦截的日志级别
    """
    # 1. 确保日志存储目录存在
    
    log_dir = str(LOG_DIR) # 兼容 pathlib.Path 转为普通字符串
        
    current_date = datetime.now().strftime('%Y%m%d')
    log_filename = f"neurosync_{current_date}.log"
        
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_path = os.path.join(log_dir, log_filename)

    # 2. 获取根 Logger 并设置全局级别
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清空之前可能存在的 handlers，防止在调试时重复打印
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 3. 定义高规格的日志格式
    # 格式示例: 2023-10-25 10:30:15 - [MainThread] - core.controller - INFO - 设备已连接
    # 注意：%(threadName)s 在多线程开发中极其重要！
    formatter = logging.Formatter(
        fmt='%(asctime)s - [%(threadName)s] - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 4. 文件 Handler (RotatingFileHandler)
    # 单个日志文件最大 10MB，最多保留 5 个历史备份 (超过 50MB 自动覆盖最老的)
    file_handler = RotatingFileHandler(
        filename=log_path, 
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5, 
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # 5. 控制台 Handler (输出到终端屏幕)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # 6. 将 Handlers 挂载到全局 Logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("==================================================")
    logging.info(f"全局日志系统初始化完成，日志将保存在: {log_path}")
    logging.info("==================================================")

    return root_logger

def get_logger(name):
    """
    提供给各个模块获取专属 logger 的辅助函数。
    其实这等价于标准的 logging.getLogger(name)，写在这里是为了封装统一性。
    """
    return logging.getLogger(name)
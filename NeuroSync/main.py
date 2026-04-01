# main.py
import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from ui.mainWindow import MainWindow        # View 视图层
from core.controller import AppController    # Controller 控制层
from utils.logger import setup_logger        # 你的全局日志配置工具

def main():
    # 1. 启动全局日志系统
    setup_logger()
    logging.info("="*50)
    logging.info("启动 NeuroSync fNIRS 多模态数据采集系统...")

    # 2. 配置 PyQt 应用程序环境 (开启高分屏支持)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    
    # 获取当前 main.py 所在的绝对路径，并拼接出 style.qss 的路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(base_dir, "assets", "styles.qss")
    
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        logging.info(f"成功加载全局样式表: {qss_path}")
    else:
        logging.warning(f"未找到样式表文件: {qss_path}，将使用默认系统 UI。")

    # 3. 实例化 MVC 架构
    # 创建纯净的主视图 (View)
    main_window = MainWindow()
    
    # 创建统筹全局的控制器 (Controller)，并将视图注入
    app_controller = AppController(ui=main_window)

    # 4. 显示界面并进入主事件循环
    main_window.show()
    logging.info("主界面加载完毕，系统就绪。")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"系统发生未捕获的致命错误: {str(e)}", exc_info=True)
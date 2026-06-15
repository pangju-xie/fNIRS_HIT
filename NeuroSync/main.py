import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from ui.mainWindow import MainWindow
from core.controller import AppController
from utils.logger import setup_logger
from utils.paths import get_resource_path


def main():
    setup_logger()
    logging.info("=" * 50)
    logging.info("正在启动 NeuroSync 多模态数据采集系统...")

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)

    qss_path = get_resource_path(os.path.join("assets", "styles.qss"))

    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        logging.info("已成功加载全局样式表：%s", qss_path)
    else:
        logging.warning("未找到样式表文件：%s，将使用默认系统 UI。", qss_path)

    main_window = MainWindow()
    app_controller = AppController(ui=main_window)
    main_window._app_controller = app_controller

    main_window.show()
    logging.info("主界面加载完成，系统已就绪。")

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical("系统发生未捕获的致命错误：%s", str(e), exc_info=True)

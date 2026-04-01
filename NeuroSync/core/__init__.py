"""
核心业务逻辑层 (Core Logic)

本包负责整个上位机的后台运行，严禁包含任何 UI 界面的绘制逻辑。
- controller.py: 核心调度器，统筹整个生命周期。
- thread_wifi.py: 负责 UDP 底层高速通信的子线程。
- process.py: 负责数据解包与分流的子线程。
- buffer.py: 维护多线程安全的环形缓冲区。
"""

# 显式导入该包向外暴露的核心类
# from .controller import AppController
# from .thread_wifi import UdpAcquisitionThread # 假设类名叫这个，可以按你实际的改
# from .process import DataProcessingThread
# from .buffer import DataBufferManager

# __all__ 规定了如果有人使用 `from core import *`，只会导入以下四个类
# 这不仅规范了代码，还能让现代 IDE (如 VSCode/PyCharm) 提供更精准的智能提示
__all__ = [
    'AppController',
    'UdpAcquisitionThread',
    'DataProcessingThread',
    'DataBufferManager'
]
NeuroSync 多模态脑机接口上位机架构文档
1. 系统概述
    NeuroSync 是一款专为多模态生理信号（fNIRS / EEG / sEMG）设计的实时数据采集与分析上位机系统。

2. 系统宏观架构解析
    系统在逻辑上被划分为三个核心层级：基础设施与数据层、业务逻辑与控制层、以及UI层。

    2.1 基础设施与数据层
        负责底层网络I/O、二进制协议解析以及数据持久化，直接与下位机硬件进行交互。

        ~异步网络通信 (UdpThread)：工作在独立子线程中，负责非阻塞式监听 UDP 端口，实现底层字节流的高频并发接收与分发。
        ~通信协议处理 (DeviceProcessManager)：实现硬件协议层解析。负责封装下行控制指令包，并解析上行状态包（如设备连接、电量查询、ACK 回调）。
        ~数据缓冲与调度 (DataBufferManager)：系统的核心数据路由层。负责多模态数据缓存、按系统状态分流，并实现了基于序列号的丢包检测与补包调度算法。
        ~生理信号算法库 (physioSignal/)：包含独立的模态解算器。负责执行 24-bit ADC 二进制解码，以及物理量纲转换（例如 fNIRS 的 MBLL 修正比尔-朗伯定律计算）。

    2.2 业务逻辑与控制层
        负责处理全局调度、状态流转以及特定业务模块的逻辑实现。

        核心控制器 (AppController)：全局事件总线与调度中心。实现视图层事件与底层异步事件的解耦，负责动态管理各业务组件的生命周期。
        状态机管理 ( SystemState & WorkflowStates)：维护系统的单一真值。通过有限状态机控制应用的运行阶段（DISCONNECTED -> CONNECTED -> CONFIGURED -> QUALIFIED -> ACQUIRED），并据此严格限制 UI 的交互权限与底层数据的写入权限。
        视图控制器 (core/widget_manager/)：作为 Controller 与 View 之间的中间件，负责具体业务逻辑的绑定：

    2.3 UI层
        负责纯 UI 组件的实例化与空间布局，完全剥离业务逻辑。
        静态布局容器 (ui/views/)：包含 display_view.py, quality_view.py 等模块。通过 Qt 布局管理器实现控件树的构建。


3. 目录结构与模块说明
NeuroSync/
├── assets/                     # 静态资源目录
│   ├── icons/                  # 界面图标
│   ├── extinction_coefficients.csv # fNIRS 消光系数矩阵
│   └── styles.qss              # 全局 Qt 样式表
├── core/                       # 核心控制与调度层
│   ├── widget_manager/         # 视图控制器 (业务逻辑与 UI 绑定)
│   │   ├── bmap_manager.py     # 脑图与空间拓扑节点管理
│   │   ├── channel.py          # 通道配置与采样率参数下发
│   │   ├── display.py          # 实时波形渲染与记录控制
│   │   ├── quality.py          # 信号质量与阻抗动态评估
│   │   └── user.py             # 受试者信息录入与管理
│   ├── buffer.py               # 数据缓冲管理器 (数据分流、丢包检测与补全)
│   ├── controller.py           # 主控制器 (生命周期管理、状态机流转、信号路由)
│   ├── process.py              # 设备通信管理器 (硬件指令解析与封装)
│   └── thread_udp.py           # 底层 UDP 异步网络收发线程
├── physioSignal/               # 底层算法与协议解析层
│   ├── eeg.py                  # EEG 信号处理器
│   ├── emg.py                  # sEMG 信号处理器
│   └── fnirs.py                # fNIRS 处理器 (24位解码, MBLL定律, SNIRF文件生成)
├── ui/                         # 纯静态视图层 (由 UI 设计器生成及自定义组件)
│   ├── views/                  # 各个子模块的纯布局定义
│   │   ├── analysis_view.py    # 离线数据分析布局
│   │   ├── channel_view.py     # 通道参数配置布局
│   │   ├── display_view.py     # 实时波形展示布局
│   │   ├── locate_widget.py    # 2D 脑图拓扑绘制组件
│   │   ├── quality_view.py     # 阻抗与信号质量评估布局
│   │   └── user_view.py        # 受试者信息管理布局
│   └── mainWindow.py           # 主窗口容器壳
├── utils/                      # 通用工具与数据结构
│   ├── crc.py                  # 校验和算法
│   ├── filter.py               # 数字信号处理引擎 (IIR, Butterworth, S-G 滤波等)
│   ├── logger.py               # 全局日志记录器配置
│   ├── paths.py                # 路径管理与寻址工具
│   ├── stats.py                # 全局状态机 (SystemState) 与系统枚举 (SensorTypes)
│   └── subjects.py             # 受试者本地数据库/文件管理
├── main.py                     # 应用程序入口点
├── readme.md                   # 先看看我
└── requirements.txt            # 依赖包列表
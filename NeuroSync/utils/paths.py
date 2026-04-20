import os, sys
import logging

logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """
    智能寻址函数：兼容代码开发环境与 PyInstaller 打包后的 exe 环境
    """
    if hasattr(sys, '_MEIPASS'):
        # 如果是 exe 运行，它会去系统的临时解压目录找
        return os.path.join(sys._MEIPASS, relative_path) # type: ignore
    else:
        # 如果是纯代码运行，就在项目根目录下找
        return os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), relative_path)
    
# ==========================================
# 1. 智能决策工作区根目录
# ==========================================
# 优先尝试使用 D 盘，如果 D 盘不存在（如部分笔记本只有C盘），则放在用户的“我的文档”中
if os.path.exists("D:\\"):
    WORKSPACE_BASE = r"D:/NeuroSync_Workspace"
else:
    WORKSPACE_BASE = os.path.join(os.path.expanduser("~"), "Documents", "NeuroSync_Workspace")

# ==========================================
# 2. 定义各大业务模块的具体子目录
# ==========================================
# 采集记录存储区 (.snirf, .csv 等波形数据)
DATA_DIR = os.path.join(WORKSPACE_BASE, "Data")

# 用户数据库存储区 (患者登记信息 JSON/DB)
DB_DIR = os.path.join(WORKSPACE_BASE, "Database")

# 模板与配置存储区 (你提到的模板信息、自定义脑图排布等)
TEMPLATE_DIR = os.path.join(WORKSPACE_BASE, "Montages")

LOG_DIR = os.path.join(WORKSPACE_BASE, "Logs")

# ==========================================
# 3. 初始化时自动创建这些目录
# ==========================================
for d in [DATA_DIR, DB_DIR, TEMPLATE_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

logger.info(f"系统工作区已挂载至: {WORKSPACE_BASE}")
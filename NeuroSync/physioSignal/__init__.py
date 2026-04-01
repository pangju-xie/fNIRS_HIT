"""
多模态生理信号算法库 (Physiological Signal Processing Library)

本包包含纯粹的数学和信号处理算法，与系统的业务状态完全解耦。
所有函数或类应尽量设计为无状态（Stateless），严格遵循“输入矩阵 -> 输出处理后矩阵/特征”的原则。

- eeg.py: 脑电信号处理 (滤波、去基线、空间滤波等)
- fnirs.py: 近红外信号解算 (MBLL定律、光强转OD、OD转血氧浓度等)
- emg.py: 表面肌电处理 (整流、平滑包络提取、激活期检测等)
"""

# 在这里可以暴露出最常用的处理流水线函数
# from .eeg import eeg_pipeline_basic
# from .fnirs import calc_hbo_hbr
# from .emg import get_emg_envelope

__all__ = [
    'eeg_pipeline_basic',
    'calc_hbo_hbr',
    'get_emg_envelope'
]
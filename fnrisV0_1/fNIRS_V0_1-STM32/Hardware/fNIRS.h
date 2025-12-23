#ifndef __FNIRS_H
#define __FNIRS_H

/******************************************************************************
 * fNIRS 近红外光谱脑成像系统
 * 功能：采集近红外光谱数据用于脑功能成像
 ******************************************************************************/

#include "main.h"
#include <stdio.h>
#include <stdint.h>
#include "CSNP32.h"

/******************************************************************************
 * 常量定义
 ******************************************************************************/

#define LEN_ONE_DOT         3      /**< 每个光电极点数据长度（字节）*/
#define LEN_ONE_SOURCE      (LEN_ONE_DOT * 2)  /**< 每个光源数据长度（包含红/红外两个波长）*/

#define FNIRS_PERIOD        1      /**< 数据发送周期（单位：批次）*/

/******************************************************************************
 * fNIRS系统状态枚举
 ******************************************************************************/
typedef enum {
    FNIRS_STATE_INIT  = 0,    /**< 初始化状态 */
    FNIRS_STATE_READY = 1,    /**< 初始化完成，准备就绪 */
    FNIRS_STATE_START = 2,    /**< 数据采集开始 */
    FNIRS_STATE_STOP  = 3,    /**< 数据采集停止 */
} FNIRS_STATE;

/******************************************************************************
 * fNIRS配置结构体
 * 描述：光源-探测器网络配置信息
 ******************************************************************************/
typedef struct {
    uint8_t  source_count;          /**< 光源数量 */
    uint8_t  detector_count;        /**< 探测器数量 */
    uint16_t config[20];            /**< 光源-探测器配置数组，每个元素表示一个光源的探测器配置 */
    uint8_t  detector_open[20];     /**< 每个光源激活的探测器数量 */
    uint8_t  detector_cumulative[20];  /**< 累积激活的探测器数量，用于快速索引 */
} FNIRS_CONFIG;

/******************************************************************************
 * fNIRS读取缓冲区结构体
 * 描述：临时存储单次读取的光电数据
 ******************************************************************************/
typedef struct {
    uint8_t data_buffer[50];        /**< 光电数据暂存数组 */
} FNIRS_READ_BUF;

/******************************************************************************
 * fNIRS ADS缓冲区结构体
 * 描述：双缓冲区用于红/红外双波长数据
 ******************************************************************************/
typedef struct {
    uint8_t active_idx;             /**< 当前激活的缓冲区索引（0或1） */
    FNIRS_READ_BUF wavelength_buf[2];  /**< 红/红外双波长数据缓冲区 */
} FNIRS_ADS_BUF;

/******************************************************************************
 * fNIRS数据存储结构体
 * 描述：存储完整的一帧fNIRS数据
 ******************************************************************************/
typedef struct {
    uint8_t channel_data[1800];     /**< fNIRS通道数据存储数组，最大1800字节 */
} FNIRS_DATA_STRUCT;

/******************************************************************************
 * fNIRS数据缓冲区管理结构体
 * 描述：管理双缓冲区和SD卡存储
 ******************************************************************************/
typedef struct {
    uint8_t  buffer_idx;            /**< 当前发送缓冲区索引（0或1） */
    uint32_t period_counter;        /**< 发送周期计数器 */
    int      data_frame_len;        /**< 数据帧长度（字节） */
    int      send_buffer_len;       /**< 发送缓冲区长度（字节） */
    uint8_t* data_save_addr;        /**< 数据保存地址指针 */
    
    FNIRS_DATA_STRUCT send_buffer[2];   /**< 双缓冲发送数组，用于乒乓操作 */
    FNIRS_ADS_BUF     adc_buffer;       /**< ADC数据双缓冲结构 */
    SD_CARD_STRUCT    sd_buffer;        /**< SD卡缓冲区 */
} FNIRS_DATA_BUF;

/******************************************************************************
 * fNIRS主结构体
 * 描述：fNIRS系统的完整状态和控制信息
 ******************************************************************************/
typedef struct {
    FNIRS_STATE    state;           /**< 系统当前状态 */
    uint8_t        sample_rate;     /**< 采样率（Hz） */
    FNIRS_CONFIG   config;          /**< 光源-探测器网络配置 */
    FNIRS_DATA_BUF data_buffer;     /**< 数据缓冲区管理 */
    uint32_t       timer_count;     /**< 定时器计数器，用于时序控制 */
} FNIRS_STRUCT;

/******************************************************************************
 * 全局变量声明
 ******************************************************************************/
extern FNIRS_STRUCT fnirs_system;   /**< 全局fNIRS系统实例 */
extern uint8_t g_fnirs_ready_flag;  /*  fnirs单周期采样完成*/
/******************************************************************************
 * 函数声明
 ******************************************************************************/
void ads1258(void);
/**
 * @brief 初始化fNIRS系统结构体
 * @note  清零所有结构体成员，设置初始状态
 */
void fnirs_struct_init(void);

/**
 * @brief 脑氧采集功能初始化
 * @note  初始化硬件接口、ADC、定时器等，准备采集系统
 */
void nirs_init(void);

/**
 * @brief 设置fNIRS采样率
 * @param sample_rate_hz 采样率值（Hz）
 * @return 操作状态：0=成功，1=失败（参数无效）
 * @note  配置ADC采样率和系统定时器
 */
uint8_t nirs_set_sample_rate(uint8_t sample_rate_hz);

/**
 * @brief 配置fNIRS光源-探测器网络
 * @param config_data 配置数据数组指针
 * @param data_len    配置数据长度
 * @return 操作状态：0=成功，1=失败（参数无效）
 * @note  根据配置数据设置光源和探测器的连接关系
 */
uint8_t nirs_config(uint8_t* config_data, uint8_t data_len);

/**
 * @brief 启动fNIRS数据采集
 * @return 操作状态：0=成功，1=失败（系统未就绪）
 * @note  启动ADC转换、开启定时器，开始连续数据采集
 */
uint8_t nirs_start(void);

/**
 * @brief 停止fNIRS数据采集
 * @return 操作状态：0=成功，1=失败（系统未运行）
 * @note  停止ADC转换、关闭定时器，保存已采集数据
 */
uint8_t nirs_stop(void);

/**
 * @brief 获取fNIRS系统当前状态
 * @return 当前系统状态（FNIRS_STATE枚举值）
 */
uint8_t nirs_get_state(void);

/**
 * @brief 获取当前数据帧长度
 * @return 数据帧长度（字节）
 * @note  根据配置的通道数计算数据长度
 */
uint16_t nirs_get_len(void);

/**
 * @brief 发送fNIRS数据
 * @note 处理数据包并发送到SPI和SD卡
 */
void nirs_data_send(void);
  
/**
 * @brief 定时器中断处理函数
 * @param flag 光源开关控制
 * @note  在定时器中断中调用，处理数据采集时序
 */
void nirs_timer_handle(uint8_t flag);

/**
 * @brief 脑氧数据采集函数
 * @param gpio_pin 触发采集的GPIO引脚号
 * @note  由GPIO中断触发，采集单次光电极点数据
 */
void nirs_data_collect(uint16_t gpio_pin);

/**
 * @brief 从SD卡读取fNIRS数据
 * @param package_number 数据包编号
 * @note  读取指定编号的数据包用于回放或分析
 */
void sd_read_nirs(uint32_t package_number);

/******************************************************************************
 * 宏定义 - 状态检查
 ******************************************************************************/

/**
 * @brief 检查fNIRS系统是否已初始化
 */
#define IS_FNIRS_INITIALIZED()      (fnirs_system.state >= FNIRS_STATE_READY)

/**
 * @brief 检查fNIRS系统是否正在采集
 */
#define IS_FNIRS_COLLECTING()       (fnirs_system.state == FNIRS_STATE_START)

/**
 * @brief 检查fNIRS系统是否就绪
 */
#define IS_FNIRS_READY()            (fnirs_system.state == FNIRS_STATE_READY)

/******************************************************************************
 * 宏定义 - 缓冲区操作
 ******************************************************************************/

/**
 * @brief 切换发送缓冲区索引
 */
#define FNIRS_TOGGLE_SEND_BUFFER() \
    do { \
        fnirs_system.data_buffer.buffer_idx ^= 1; \
    } while(0)

/**
 * @brief 切换ADC缓冲区索引
 */
#define FNIRS_TOGGLE_ADC_BUFFER() \
    do { \
        fnirs_system.data_buffer.adc_buffer.active_idx ^= 1; \
    } while(0)

/**
 * @brief 获取当前发送缓冲区指针
 */
#define FNIRS_GET_CURRENT_SEND_BUFFER() \
    (&fnirs_system.data_buffer.send_buffer[fnirs_system.data_buffer.buffer_idx])

/**
 * @brief 获取当前ADC缓冲区指针
 */
#define FNIRS_GET_CURRENT_ADC_BUFFER() \
    (&fnirs_system.data_buffer.adc_buffer.wavelength_buf[fnirs_system.data_buffer.adc_buffer.active_idx])

#endif /* __FNIRS_H */
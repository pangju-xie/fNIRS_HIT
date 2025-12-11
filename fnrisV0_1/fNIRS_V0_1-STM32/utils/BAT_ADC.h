#ifndef __BAT_ADC_H
#define __BAT_ADC_H

/******************************************************************************
 * @file     bat_adc.h
 * @brief    电池电量检测模块头文件
 * @version  V1.0
 * @date     2024/8/10
 * @author   谢发文 <823767544@qq.com>
 * @note     负责电池电压的ADC采集、电量百分比计算和低电量告警功能
 ******************************************************************************/

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include <stdio.h>
#include "adc.h"

/******************************************************************************
 * 电池电压参数定义
 ******************************************************************************/

#define BATTERY_REFERENCE_VOLTAGE_MV    6600    /**< ADC参考电压 (mV)，用于电压计算 */
#define ADC_RESOLUTION_BITS             4096    /**< ADC分辨率 (12位: 2^12 = 4096) */

/******************************************************************************
 * 电池电压-电量百分比对应表 (单位: mV)
 * @note 根据电池放电曲线定义，需要根据实际电池特性调整
 ******************************************************************************/

#define BATTERY_VOLTAGE_100_PERCENT     4200    /**< 100% 电量对应的电压值 */
#define BATTERY_VOLTAGE_90_PERCENT      4080    /**< 90% 电量对应的电压值 */
#define BATTERY_VOLTAGE_80_PERCENT      4000    /**< 80% 电量对应的电压值 */
#define BATTERY_VOLTAGE_70_PERCENT      3930    /**< 70% 电量对应的电压值 */
#define BATTERY_VOLTAGE_60_PERCENT      3870    /**< 60% 电量对应的电压值 */
#define BATTERY_VOLTAGE_50_PERCENT      3820    /**< 50% 电量对应的电压值 */
#define BATTERY_VOLTAGE_40_PERCENT      3790    /**< 40% 电量对应的电压值 */
#define BATTERY_VOLTAGE_30_PERCENT      3770    /**< 30% 电量对应的电压值 */
#define BATTERY_VOLTAGE_20_PERCENT      3730    /**< 20% 电量对应的电压值 */
#define BATTERY_VOLTAGE_10_PERCENT      3680    /**< 10% 电量对应的电压值 */
#define BATTERY_VOLTAGE_0_PERCENT       2500    /**< 0% 电量对应的电压值 (放电截止电压) */

/******************************************************************************
 * 低电量告警阈值定义
 ******************************************************************************/

#define BATTERY_WARNING_THRESHOLD       20      /**< 低电量告警阈值 (%)，低于此值需要告警 */
#define BATTERY_CRITICAL_THRESHOLD      10      /**< 严重低电量阈值 (%)，低于此值应立即处理 */

/******************************************************************************
 * ADC采样参数定义
 ******************************************************************************/

#define BATTERY_ADC_CHANNEL             ADC_CHANNEL_0  /**< 电池电压检测使用的ADC通道 */
#define ADC_SAMPLES_COUNT               32             /**< ADC采样次数，用于平均值滤波 */
#define ADC_SAMPLE_DELAY_MS             10             /**< ADC采样间隔延时 (ms) */

/******************************************************************************
 * 电压计算相关宏定义
 ******************************************************************************/

/** @brief 将ADC原始值转换为实际电压值 (mV) */
#define ADC_TO_VOLTAGE_MV(adc_value)    ((adc_value) * BATTERY_REFERENCE_VOLTAGE_MV / ADC_RESOLUTION_BITS)

/** @brief 将实际电压值转换为ADC原始值 */
#define VOLTAGE_TO_ADC(voltage_mv)      ((voltage_mv) * ADC_RESOLUTION_BITS / BATTERY_REFERENCE_VOLTAGE_MV)

/******************************************************************************
 * 外部变量声明
 ******************************************************************************/

extern volatile uint8_t g_battery_data_ready;  /**< 电池数据就绪标志: 0=未就绪, 1=就绪 */

/******************************************************************************
 * 电池状态枚举定义
 ******************************************************************************/

/** @brief 电池状态枚举，用于表示电池的当前状态 */
typedef enum {
    BATTERY_STATUS_NORMAL = 0,       /**< 电池状态正常 (电量 > 20%) */
    BATTERY_STATUS_WARNING = 1,      /**< 电池低电量警告 (电量 10%-20%) */
    BATTERY_STATUS_CRITICAL = 2,     /**< 电池电量严重不足 (电量 < 10%) */
    BATTERY_STATUS_CHARGING = 3,     /**< 电池正在充电 */
    BATTERY_STATUS_ERROR = 4,        /**< 电池检测错误 */
} BATTERY_STATUS;

/******************************************************************************
 * 电池信息结构体定义
 ******************************************************************************/

/** @brief 电池信息结构体，包含电池的完整状态信息 */
typedef struct {
    uint16_t raw_adc_value;          /**< ADC原始采样值 */
    uint16_t voltage_mv;             /**< 电池电压值 (mV) */
    uint8_t  percentage;             /**< 电池电量百分比 (0-100%) */
    BATTERY_STATUS status;           /**< 电池当前状态 */
    uint32_t last_update_time;       /**< 最后更新时间戳 (ms) */
    uint8_t  sample_count;           /**< 当前采样次数，用于平均值计算 */
} BATTERY_INFO;

/******************************************************************************
 * 函数声明 - 电池检测初始化
 ******************************************************************************/

/**
 * @brief 初始化电池检测模块
 * @note 配置ADC通道、初始化相关变量和启动检测
 */
void battery_detection_init(void);

/**
 * @brief 获取电池ADC原始采样值
 * @return ADC原始采样值 (0-4095)
 * @note 执行单次ADC采样，返回原始12位数据
 */
uint16_t get_battery_adc_raw_value(void);

/******************************************************************************
 * 函数声明 - 电池检测核心功能
 ******************************************************************************/

/**
 * @brief 执行电池电量检测
 * @note 采集ADC值、计算电压和电量百分比、更新电池状态
 *       此函数应在主循环或定时器中定期调用
 */
void detect_battery_status(void);

/**
 * @brief 获取电池电量百分比
 * @return 电池电量百分比 (0-100%)
 * @note 如果电量数据未就绪，返回最近一次的有效值
 */
uint8_t get_battery_percentage(void);

/**
 * @brief 获取电池电压值
 * @return 电池电压值 (mV)
 */
uint16_t get_battery_voltage(void);

/**
 * @brief 获取电池状态信息
 * @return 电池当前状态 (BATTERY_STATUS枚举值)
 */
BATTERY_STATUS get_battery_status(void);

/******************************************************************************
 * 函数声明 - 电池数据处理
 ******************************************************************************/

/**
 * @brief 将电池电压值转换为电量百分比
 * @param voltage_mv 电池电压值 (mV)
 * @return 电池电量百分比 (0-100%)
 * @note 使用预定义的电压-电量对应表进行线性插值计算
 */
uint8_t convert_voltage_to_percentage(uint16_t voltage_mv);

/**
 * @brief 根据电量百分比判断电池状态
 * @param percentage 电池电量百分比
 * @return 电池状态 (BATTERY_STATUS枚举值)
 */
BATTERY_STATUS determine_battery_status(uint8_t percentage);

/**
 * @brief 电池电压滤波处理
 * @param adc_value ADC原始采样值
 * @return 滤波后的ADC值
 * @note 使用移动平均滤波器减少噪声影响
 */
uint16_t filter_battery_adc_value(uint16_t adc_value);

/******************************************************************************
 * 函数声明 - 低电量处理
 ******************************************************************************/

/**
 * @brief 低电量警告处理
 * @param percentage 当前电量百分比
 * @note 当电量低于阈值时触发警告（如LED闪烁、蜂鸣器等）
 */
void handle_low_battery_warning(uint8_t percentage);

/**
 * @brief 严重低电量处理
 * @note 当电量严重不足时执行紧急处理（如保存数据、进入休眠等）
 */
void handle_critical_battery_level(void);

#ifdef __cplusplus
}
#endif

#endif /* __BAT_ADC_H */
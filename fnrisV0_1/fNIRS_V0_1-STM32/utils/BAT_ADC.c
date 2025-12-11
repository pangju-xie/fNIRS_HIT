#include "BAT_ADC.h"
#include <stdio.h>
#include "usart.h"
#include "utils.h"
#include "main.h"
#include "led.h"

/******************************************************************************
 * 全局变量定义
 ******************************************************************************/

/** @brief 电池电压-电量百分比对应阈值表 (单位: mV) */
static const uint16_t g_battery_voltage_thresholds[11] = {
    BATTERY_VOLTAGE_0_PERCENT,   /**< 0% 电量阈值 */
    BATTERY_VOLTAGE_10_PERCENT,  /**< 10% 电量阈值 */
    BATTERY_VOLTAGE_20_PERCENT,  /**< 20% 电量阈值 */
    BATTERY_VOLTAGE_30_PERCENT,  /**< 30% 电量阈值 */
    BATTERY_VOLTAGE_40_PERCENT,  /**< 40% 电量阈值 */
    BATTERY_VOLTAGE_50_PERCENT,  /**< 50% 电量阈值 */
    BATTERY_VOLTAGE_60_PERCENT,  /**< 60% 电量阈值 */
    BATTERY_VOLTAGE_70_PERCENT,  /**< 70% 电量阈值 */
    BATTERY_VOLTAGE_80_PERCENT,  /**< 80% 电量阈值 */
    BATTERY_VOLTAGE_90_PERCENT,  /**< 90% 电量阈值 */
    BATTERY_VOLTAGE_100_PERCENT  /**< 100% 电量阈值 */
};

static uint16_t g_adc_raw_value = 0;       /**< ADC原始采样值 */
static uint16_t g_battery_voltage_mv = 0;  /**< 电池电压值 (mV) */
static uint8_t  g_battery_percentage = 0;  /**< 电池电量百分比 (0-100%) */

/******************************************************************************
 * 辅助函数声明
 ******************************************************************************/

static uint8_t _calculate_checksum(uint8_t *buffer, uint8_t length);
static void    _update_battery_indicator(uint16_t voltage_mv);

/******************************************************************************
 * 电池检测核心函数
 ******************************************************************************/

/**
 * @brief 检测电池电量状态
 * @note 执行ADC采样、电压计算、电量百分比转换和状态指示更新
 *       此函数应在系统空闲或定时调用，避免在关键时序中调用
 */
void detect_battery_status(void)
{
    HAL_StatusTypeDef adc_status;
    
    /* 启动ADC转换 */
    HAL_ADC_Start(&hadc1);
    
    /* 等待ADC转换完成，超时时间100ms */
    adc_status = HAL_ADC_PollForConversion(&hadc1, 100);
    
    if (adc_status == HAL_OK) {
        /* 检查ADC转换完成标志 */
        if (HAL_IS_BIT_SET(HAL_ADC_GetState(&hadc1), HAL_ADC_STATE_REG_EOC)) {
            /* 获取ADC原始值 */
            g_adc_raw_value = HAL_ADC_GetValue(&hadc1);
            
            /* 转换为实际电压值 (mV) */
            g_battery_voltage_mv = ADC_TO_VOLTAGE_MV(g_adc_raw_value);
            
            /* 转换为电量百分比 */
            g_battery_percentage = convert_voltage_to_percentage(g_battery_voltage_mv);
            
            /* 更新LED指示灯状态 */
            _update_battery_indicator(g_battery_voltage_mv);
            
            DebugPrintf("Battery status: ADC=%d, Voltage=%dmV, Percentage=%d%%\r\n",
                       g_adc_raw_value, g_battery_voltage_mv, g_battery_percentage);
        } else {
            DebugPrintf("ADC conversion not ready\r\n");
        }
    } else {
        DebugPrintf("ADC conversion timeout or error\r\n");
    }
    
    /* 停止ADC转换以节省功耗 */
    HAL_ADC_Stop(&hadc1);
}

/**
 * @brief 获取电池ADC原始采样值
 * @return ADC原始采样值 (0-4095)
 */
uint16_t get_battery_adc_raw_value(void)
{
    return g_adc_raw_value;
}

/**
 * @brief 获取电池电压值
 * @return 电池电压值 (mV)
 */
uint16_t get_battery_voltage(void)
{
    return g_battery_voltage_mv;
}

/**
 * @brief 获取电池电量百分比
 * @return 电池电量百分比 (0-100%)
 */
uint8_t get_battery_percentage(void)
{
    return g_battery_percentage;
}

/**
 * @brief 获取电池状态信息
 * @return 电池当前状态 (BATTERY_STATUS枚举值)
 */
BATTERY_STATUS get_battery_status(void)
{
    return determine_battery_status(g_battery_percentage);
}

/******************************************************************************
 * 电池数据处理函数
 ******************************************************************************/

/**
 * @brief 将电池电压值转换为电量百分比
 * @param voltage_mv 电池电压值 (mV)
 * @return 电池电量百分比 (0-100%)
 * @note 使用查表法进行线性插值计算
 */
uint8_t convert_voltage_to_percentage(uint16_t voltage_mv)
{
    int i;
    
    /* 检查电压是否低于最低阈值 */
    if (voltage_mv < g_battery_voltage_thresholds[0]) {
        return 0;  /* 电压异常低，返回0% */
    }
    
    /* 检查电压是否高于最高阈值 */
    if (voltage_mv >= g_battery_voltage_thresholds[10]) {
        return 100;  /* 电压充足，返回100% */
    }
    
    /* 查表法确定电量百分比 */
    for (i = 10; i >= 0; i--) {
        if (voltage_mv >= g_battery_voltage_thresholds[i]) {
            return i * 10;  /* 返回对应的电量百分比 */
        }
    }
    
    /* 理论上不会执行到这里 */
    return 0;
}

/**
 * @brief 根据电量百分比判断电池状态
 * @param percentage 电池电量百分比
 * @return 电池状态 (BATTERY_STATUS枚举值)
 */
BATTERY_STATUS determine_battery_status(uint8_t percentage)
{
    if (percentage >= BATTERY_WARNING_THRESHOLD) {
        return BATTERY_STATUS_NORMAL;      /* 电量充足，状态正常 */
    } else if (percentage >= BATTERY_CRITICAL_THRESHOLD) {
        return BATTERY_STATUS_WARNING;     /* 低电量警告 */
    } else {
        return BATTERY_STATUS_CRITICAL;    /* 电量严重不足 */
    }
}

/**
 * @brief 电池电压滤波处理
 * @param adc_value ADC原始采样值
 * @return 滤波后的ADC值
 * @note 使用简单的移动平均滤波器
 */
uint16_t filter_battery_adc_value(uint16_t adc_value)
{
    static uint16_t adc_history[ADC_SAMPLES_COUNT] = {0};
    static uint8_t  history_index = 0;
    static uint8_t  sample_count = 0;
    uint32_t sum = 0;
    uint8_t i;
    
    /* 更新历史数据 */
    adc_history[history_index] = adc_value;
    history_index = (history_index + 1) % ADC_SAMPLES_COUNT;
    
    /* 更新采样计数 */
    if (sample_count < ADC_SAMPLES_COUNT) {
        sample_count++;
    }
    
    /* 计算移动平均值 */
    for (i = 0; i < sample_count; i++) {
        sum += adc_history[i];
    }
    
    return (uint16_t)(sum / sample_count);
}

/******************************************************************************
 * 低电量处理函数
 ******************************************************************************/

/**
 * @brief 低电量警告处理
 * @param percentage 当前电量百分比
 * @note 当电量低于阈值时触发警告
 */
void handle_low_battery_warning(uint8_t percentage)
{
    static uint8_t warning_count = 0;
    const uint8_t MAX_WARNING_COUNT = 3;
    
    if (percentage < BATTERY_WARNING_THRESHOLD) {
        if (warning_count < MAX_WARNING_COUNT) {
            DebugPrintf("Low battery warning: %d%% remaining\r\n", percentage);
            
            /* 可以通过LED闪烁、蜂鸣器等方式进行警告 */
            set_led_color('r');  /* 设置为红色警告 */
            warning_count++;
        }
    } else {
        warning_count = 0;  /* 重置警告计数 */
    }
}

/**
 * @brief 严重低电量处理
 * @note 当电量严重不足时执行紧急处理
 */
void handle_critical_battery_level(void)
{
    static uint8_t critical_handled = 0;
    
    if (g_battery_percentage < BATTERY_CRITICAL_THRESHOLD && !critical_handled) {
        DebugPrintf("CRITICAL: Battery level %d%%, taking emergency actions\r\n",
                   g_battery_percentage);
        
        /* 执行紧急处理操作 */
        set_led_color('r');  /* 设置为红色紧急状态 */
        
        /* 可以添加以下操作：
           1. 保存关键数据到非易失存储器
           2. 停止所有非必要的功耗操作
           3. 进入低功耗休眠模式
           4. 发送紧急通知到上位机
        */
        
        critical_handled = 1;  /* 标记已处理，避免重复操作 */
    } else if (g_battery_percentage >= BATTERY_CRITICAL_THRESHOLD) {
        critical_handled = 0;  /* 电量恢复，重置处理标志 */
    }
}

/******************************************************************************
 * 内部辅助函数
 ******************************************************************************/

/**
 * @brief 更新电池状态指示灯
 * @param voltage_mv 电池电压值 (mV)
 * @note 根据电池电压设置不同颜色的LED指示
 */
static void _update_battery_indicator(uint16_t voltage_mv)
{
    if (voltage_mv >= BATTERY_VOLTAGE_80_PERCENT) {
        /* 电量充足 (≥80%)：绿色指示灯 */
        set_led_color('g');
    } else if (voltage_mv >= BATTERY_VOLTAGE_50_PERCENT) {
        /* 电量中等 (50%-80%)：黄色指示灯 */
        set_led_color('y');
    } else if (voltage_mv >= BATTERY_VOLTAGE_20_PERCENT){
        /* 电量不够 (20%-50%)：红色指示灯 */
        set_led_color('r');
    } else{
        /* 电量不足 (<20%)，触发低电量警告 */
        handle_low_battery_warning(g_battery_percentage);
    }
    
    /* 检查是否达到严重低电量状态 */
    handle_critical_battery_level();
}

/**
 * @brief 计算校验和（累加法）
 * @param buffer 待校验数据缓冲区
 * @param length 数据长度 (字节)
 * @return 8位校验和
 * @note 简单的累加校验，适用于要求不高的场景
 */
static uint8_t _calculate_checksum(uint8_t *buffer, uint8_t length)
{
    uint8_t checksum = 0;
    uint8_t i;
    
    for (i = 0; i < length; i++) {
        checksum += buffer[i];
    }
    
    return checksum;
}

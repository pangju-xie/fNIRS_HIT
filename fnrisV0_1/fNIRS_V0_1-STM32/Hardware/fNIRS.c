#include "fnirs.h"
#include "main.h"
#include "tim.h"
#include "sdio.h"
#include "ads1258.h"
#include "is31fl.h"
#include "utils.h"
#include <string.h>
#include <stdlib.h>
#include "transmit.h"
#include "led.h"
#include <math.h>
#include "tlc5940.h"

/******************************************************************************
 * 宏定义
 ******************************************************************************/

#define LED_RED_WAVELENGTH      0      /**< 红光LED标识 */
#define LED_IR_WAVELENGTH       1      /**< 红外光LED标识 */

#define ADS_SAMPLES_PER_LED     16     /**< 每个LED的平均采样次数 */

/******************************************************************************
 * 数据结构定义
 ******************************************************************************/

/**
 * @brief ADC采样数据结构
 * @note 用于统计多次采样的平均值
 */
typedef struct {
    int      sample_count;           /**< 采样次数计数器 */
    uint32_t sample_buffer[ADS_SAMPLES_PER_LED];  /**< 原始采样值缓冲区 */
    uint32_t sample_sum;             /**< 采样值累加和 */
    uint32_t average_value;          /**< 平均采样值 */
} ADC_SAMPLE_DATA;

/******************************************************************************
 * 全局变量定义
 ******************************************************************************/

FNIRS_STRUCT g_fnirs_ctx = {0};      /**< fNIRS全局上下文 */
ADC_SAMPLE_DATA g_adc_sample = {0};  /**< ADC采样数据 */

/******************************************************************************
 * 静态函数声明
 ******************************************************************************/

static void _fnirs_init_default_config(void);
static void _fnirs_update_buffer_length(void);
static void _fnirs_handle_red_wavelength(uint8_t led_index, uint16_t detector_config);
static void _fnirs_handle_ir_wavelength(uint8_t led_index, uint16_t detector_config);
static void _fnirs_process_adc_samples(uint8_t* save_addr);
static void _fnirs_write_sd_card(uint8_t* data_buffer, uint32_t period_number);

/******************************************************************************
 * 中断回调函数
 ******************************************************************************/

/**
 * @brief GPIO外部中断回调函数
 * @param GPIO_Pin 触发中断的GPIO引脚号
 * @note 处理NIRS_DRDY_Pin的数据就绪中断
 */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == NIRS_DRDY_Pin) {
        nirs_data_collect(GPIO_Pin);
    }
}

/**
 * @brief fNIRS数据采集函数
 * @param GPIO_Pin 触发采集的GPIO引脚号
 * @note 在DRDY引脚中断中调用，采集ADC数据
 */
void nirs_data_collect(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == NIRS_DRDY_Pin) {
        if (!ReadNIRS()) {  /* 检查DRDY引脚是否为低电平（数据就绪） */
            /* 读取ADC数据并累加 */
            uint8_t temp_buffer[3] = {0};
            ReadDataDirect(temp_buffer);
            
            /* 将3字节数据转换为24位整数 */
            uint32_t adc_value = ((uint32_t)temp_buffer[0] << 16) |
                                 ((uint32_t)temp_buffer[1] << 8)  |
                                 (uint32_t)temp_buffer[2];
            
            g_adc_sample.sample_sum += adc_value;
            g_adc_sample.sample_count++;
        }
        __HAL_GPIO_EXTI_CLEAR_IT(NIRS_DRDY_Pin);
    }
}

/******************************************************************************
 * 初始化函数
 ******************************************************************************/

/**
 * @brief 初始化fNIRS数据结构
 * @note 设置默认配置和初始化缓冲区
 */
void fnirs_struct_init(void)
{
    /* 清零全局上下文 */
    memset(&g_fnirs_ctx, 0, sizeof(g_fnirs_ctx));
    
    /* 设置默认状态和采样率 */
    g_fnirs_ctx.state = FNIRS_STATE_INIT;
    g_fnirs_ctx.sample_rate = 10;  /* 默认采样率10Hz */
    
    /* 初始化默认配置 */
    _fnirs_init_default_config();
    
    /* 初始化数据缓冲区 */
    _fnirs_update_buffer_length();
    init_data_frame(g_fnirs_ctx.data_buffer.send_buffer[0].channel_data, SENSOR_FNIRS, CMD_DATA_TRANSMISSION, 
                g_fnirs_ctx.data_buffer.data_frame_len);
    init_data_frame(g_fnirs_ctx.data_buffer.send_buffer[1].channel_data, SENSOR_FNIRS, CMD_DATA_TRANSMISSION, 
                g_fnirs_ctx.data_buffer.data_frame_len);
}

/**
 * @brief 初始化默认fNIRS配置
 * @note 设置16个光源和16个探测器，全部开启
 */
static void _fnirs_init_default_config(void)
{
    /* 设置光源和探测器数量 */
    g_fnirs_ctx.config.source_count = 16;
    g_fnirs_ctx.config.detector_count = 16;
    
    /* 设置默认配置：所有探测器全部开启 */
    for (uint8_t i = 0; i < g_fnirs_ctx.config.source_count; i++) {
        g_fnirs_ctx.config.config[i] = 0xFFFF;  /* 所有16位都置1 */
        g_fnirs_ctx.config.detector_open[i] = 16;  /* 每个光源开启16个探测器 */
        g_fnirs_ctx.config.detector_cumulative[i+1] = 
            g_fnirs_ctx.config.detector_open[i] + g_fnirs_ctx.config.detector_cumulative[i];
    }
}

/**
 * @brief 更新缓冲区长度计算
 * @note 根据当前配置重新计算数据帧长度
 */
static void _fnirs_update_buffer_length(void)
{
    /* 计算数据帧长度 = 有效数据 + 4字节包头 */
    int valid_channels = g_fnirs_ctx.config.detector_cumulative[g_fnirs_ctx.config.source_count];
    g_fnirs_ctx.data_buffer.data_frame_len = valid_channels * LEN_ONE_SOURCE + 4;
    
    /* 计算总发送长度 = 数据帧长度 + 帧头长度 */
    g_fnirs_ctx.data_buffer.send_buffer_len = g_fnirs_ctx.data_buffer.data_frame_len + FRAME_FIXED_HEADER_LENGTH;
}

/**
 * @brief fNIRS系统初始化
 * @note 初始化所有硬件组件和数据结构
 */
void nirs_init(void)
{
    /* 初始化硬件组件 */
    tlc5940_init();          /* 初始化LED驱动器 */
    ads1258init();           /* 初始化ADC */
    init_data_frame_module();         /* 初始化数据帧结构 */
    fnirs_struct_init();     /* 初始化fNIRS数据结构 */
    
    DebugPrintf("fNIRS  init done\r\n");
}

/******************************************************************************
 * 配置函数
 ******************************************************************************/

/**
 * @brief 设置fNIRS采样率
 * @param sample_rate_hz 采样率值（Hz）
 * @return 操作状态：0=失败，1=成功
 */
uint8_t nirs_set_sample_rate(uint8_t sample_rate_hz)
{
    uint8_t ret = 0;
    
    switch (sample_rate_hz) {
        case 1:
            g_fnirs_ctx.sample_rate = 10;
            ret = 1;
            break;
        case 2:
            g_fnirs_ctx.sample_rate = 20;
            ret = 1;
            break;
        default:
            DebugPrintf("sample rate error: %d Hz\r\n", sample_rate_hz);
            break;
    }
    
    if (ret) {
        /* 计算并设置定时器重载值 */
        uint16_t period_value = (1000 * 32) / g_fnirs_ctx.config.source_count / g_fnirs_ctx.sample_rate;
        __HAL_TIM_SET_AUTORELOAD(g_tlc.tlctim, period_value - 1);
        //DebugPrintf("采样率设置为: %d Hz, 定时器周期: %d\r\n", g_fnirs_ctx.sample_rate, period_value);
    }
    
    return ret;
}

/**
 * @brief 配置fNIRS光源-探测器网络
 * @param config_data 配置数据数组指针
 * @param data_len 配置数据长度
 * @return 操作状态：0=失败，1=成功
 */
uint8_t nirs_config(uint8_t* config_data, uint8_t data_len)
{
    /* 清零配置结构体 */
    memset(&g_fnirs_ctx.config, 0, sizeof(g_fnirs_ctx.config));
    
    /* 读取光源和探测器数量 */
    g_fnirs_ctx.config.source_count = config_data[0];
    g_fnirs_ctx.config.detector_count = config_data[1];
    
    if (g_fnirs_ctx.config.source_count > 20 || g_fnirs_ctx.config.detector_count > 16) {
//        DebugPrintf("配置参数错误: 光源数=%d, 探测器数=%d\r\n", 
//                   g_fnirs_ctx.config.source_count, g_fnirs_ctx.config.detector_count);
        return 0;
    }
    
    /* 解析每个光源的配置 */
    for (uint8_t source_idx = 0; source_idx < g_fnirs_ctx.config.source_count; source_idx++) {
        uint16_t detector_config = 0;
        
        /* 构建探测器配置字 */
        for (uint8_t byte_idx = 0; byte_idx < data_len; byte_idx++) {
            uint8_t data_index = source_idx * data_len + 2 + byte_idx;
            detector_config = (detector_config << 8) | config_data[data_index];
        }
        g_fnirs_ctx.config.config[source_idx] = detector_config;
        
        /* 统计该光源开启的探测器数量 */
        uint8_t open_count = 0;
        for (uint8_t detector_idx = 0; detector_idx < g_fnirs_ctx.config.detector_count; detector_idx++) {
            if (GET_BIT(detector_config, detector_idx)) {
                open_count++;
            }
        }
        g_fnirs_ctx.config.detector_open[source_idx] = open_count;
        
        /* 计算累积开启的探测器数量 */
        g_fnirs_ctx.config.detector_cumulative[source_idx + 1] = 
            open_count + g_fnirs_ctx.config.detector_cumulative[source_idx];
    }
    
    /* 更新缓冲区长度 */
    _fnirs_update_buffer_length();
    
    /* 重新初始化数据缓冲区 */
    init_data_frame(g_fnirs_ctx.data_buffer.send_buffer[0].channel_data, SENSOR_FNIRS, CMD_DATA_TRANSMISSION, 
                g_fnirs_ctx.data_buffer.data_frame_len);
    init_data_frame(g_fnirs_ctx.data_buffer.send_buffer[1].channel_data, SENSOR_FNIRS, CMD_DATA_TRANSMISSION, 
                g_fnirs_ctx.data_buffer.data_frame_len);
    
    /* 初始化SD卡缓冲区 */
    g_fnirs_ctx.data_buffer.sd_buffer.sd_base_address = 0;
    g_fnirs_ctx.data_buffer.sd_buffer.buffer_idx = 0;
    g_fnirs_ctx.data_buffer.sd_buffer.batches_per_block = BLOCKSIZE / g_fnirs_ctx.data_buffer.send_buffer_len;
    g_fnirs_ctx.data_buffer.sd_buffer.blocks_to_write = 1;
    g_fnirs_ctx.data_buffer.sd_buffer.buffer_size = g_fnirs_ctx.data_buffer.sd_buffer.blocks_to_write * BLOCKSIZE;
    
    /* 更新系统状态 */
    g_fnirs_ctx.state = FNIRS_STATE_READY;
    
//    DebugPrintf("fNIRS配置完成: 光源=%d, 探测器=%d, 数据长度=%d\r\n", 
//               g_fnirs_ctx.config.source_count, g_fnirs_ctx.config.detector_count, 
//               g_fnirs_ctx.data_buffer.send_buffer_len);
    
    return 1;
}

/******************************************************************************
 * 控制函数
 ******************************************************************************/

/**
 * @brief 启动fNIRS数据采集
 * @return 操作状态：1=成功
 */
uint8_t nirs_start(void)
{
    DebugPrintf("===== start fnirs =====\r\n");
    
    /* 更新系统状态 */
    g_fnirs_ctx.state = FNIRS_STATE_START;
    g_fnirs_ctx.timer_count = 0;
    
    /* 重置定时器 */
    __HAL_TIM_SetCounter(g_tlc.tlctim, 0);
    HAL_TIM_Base_Start_IT(g_tlc.tlctim);
    
    /* 初始化数据缓冲区 */
    g_fnirs_ctx.data_buffer.buffer_idx = 0;
    g_fnirs_ctx.data_buffer.data_save_addr = 
        g_fnirs_ctx.data_buffer.send_buffer[g_fnirs_ctx.data_buffer.buffer_idx].channel_data + FRAME_DATA_POSITION;
    
    /* 清零ADC采样数据 */
    memset(&g_adc_sample, 0, sizeof(g_adc_sample));
    
    return 1;
}

/**
 * @brief 停止fNIRS数据采集
 * @return 操作状态：1=成功
 */
uint8_t nirs_stop(void)
{
    DebugPrintf("===== stop fNIRS=====\r\n");
    
    /* 关闭所有LED */
    tlcSetGS(0, g_tlc.red_led, 0, 0);
    
    /* 停止ADC转换和定时器 */
    stopConversions();
    HAL_TIM_Base_Stop_IT(g_tlc.tlctim);
    
    /* 更新系统状态 */
    g_fnirs_ctx.state = FNIRS_STATE_STOP;
    
    return 1;
}

/**
 * @brief 获取fNIRS系统当前状态
 * @return 当前系统状态
 */
uint8_t nirs_get_state(void)
{
    return g_fnirs_ctx.state;
}

/**
 * @brief 获取当前数据帧长度
 * @return 数据帧长度（字节）
 */
uint16_t nirs_get_len(void)
{
    return g_fnirs_ctx.data_buffer.send_buffer_len;
}

/******************************************************************************
 * 数据处理函数
 ******************************************************************************/

/**
 * @brief 处理ADC采样数据并计算平均值
 * @param save_addr 数据保存地址
 */
static void _fnirs_process_adc_samples(uint8_t* save_addr)
{
    if (g_adc_sample.sample_count > 0) {
        /* 计算平均值 */
        g_adc_sample.average_value = g_adc_sample.sample_sum / g_adc_sample.sample_count;
        
        /* 保存3字节数据 */
        save_addr[0] = (g_adc_sample.average_value >> 16) & 0xFF;
        save_addr[1] = (g_adc_sample.average_value >> 8) & 0xFF;
        save_addr[2] = g_adc_sample.average_value & 0xFF;
        
        /* 重置采样数据 */
        g_adc_sample.sample_sum = 0;
        g_adc_sample.sample_count = 0;
    }
}

/**
 * @brief 处理红光波长采集
 * @param led_index LED索引
 * @param detector_config 探测器配置字
 */
static void _fnirs_handle_red_wavelength(uint8_t led_index, uint16_t detector_config)
{
    Delay_us(1);
    ADS1258_START(LOW);  /* 停止ADC转换 */
    
    /* 开启红光LED */
    tlcSetGS(led_index, g_tlc.red_led, 1, 1);
    
    /* 设置ADC通道 */
    set_ads_channel(&detector_config);
    
    HAL_Delay(1);  /* 等待稳定 */
    
    /* 根据开启的探测器数量控制ADC转换 */
    uint8_t open_detectors = g_fnirs_ctx.config.detector_open[led_index];
    if (open_detectors >= 1) {
        ADS1258_START(HIGH);  /* 开始ADC转换 */
    }
}

/**
 * @brief 处理红外光波长采集
 * @param led_index LED索引
 * @param detector_config 探测器配置字
 */
static void _fnirs_handle_ir_wavelength(uint8_t led_index, uint16_t detector_config)
{
    Delay_us(1);
    ADS1258_START(LOW);  /* 停止ADC转换 */
    
    /* 关闭红光LED，准备红外光采集 */
    tlcSetGS(led_index, g_tlc.red_led, 0, 1);
    Delay_us(1);
    
    /* 根据开启的探测器数量控制ADC转换 */
    uint8_t open_detectors = g_fnirs_ctx.config.detector_open[led_index];
    if (open_detectors >= 1) {
        ADS1258_START(HIGH);  /* 开始ADC转换 */
    }
}


/**
 * @brief 发送fNIRS数据
 * @param srcbuf 源数据缓冲区指针
 * @note 处理数据包并发送到SPI和SD卡
 */
void nirs_data_send(uint8_t* srcbuf)
{
    /* 指示灯闪烁 */
    SwitchLED();
    
    /* 填充数据包编号（大端格式） */
    uint32_t packet_number_be = ENDIAN_SWAP_32B(g_fnirs_ctx.data_buffer.period_counter);
    memcpy(srcbuf + g_fnirs_ctx.data_buffer.send_buffer_len - 6, 
           &packet_number_be, sizeof(packet_number_be));
    
    /* 计算CRC校验码 */
    uint16_t crc_value = calculate_crc16(srcbuf, g_fnirs_ctx.data_buffer.send_buffer_len - 2);
    uint16_t crc_value_be = ENDIAN_SWAP_16B(crc_value);
    memcpy(srcbuf + g_fnirs_ctx.data_buffer.send_buffer_len - 2, 
           &crc_value_be, sizeof(crc_value_be));
    
    /* 通过SPI DMA发送数据 */
    spi_transmit_dma(srcbuf, g_fnirs_ctx.data_buffer.send_buffer_len, 1000);
    
    /* 写入SD卡 */
    _fnirs_write_sd_card(srcbuf, g_fnirs_ctx.data_buffer.period_counter);
    
    /* 切换缓冲区索引 */
    g_fnirs_ctx.data_buffer.buffer_idx = (g_fnirs_ctx.data_buffer.buffer_idx == 1) ? 0 : 1;
    g_fnirs_ctx.data_buffer.period_counter++;
    
    /* 更新数据保存地址 */
    g_fnirs_ctx.data_buffer.data_save_addr = 
        g_fnirs_ctx.data_buffer.send_buffer[g_fnirs_ctx.data_buffer.buffer_idx].channel_data + FRAME_DATA_POSITION;
}

/**
 * @brief 定时器中断处理函数
 * @note 在定时器中断中调用，控制采集时序
 */
void nirs_timer_handle(void)
{
    /* 检查系统状态 */
    if (g_fnirs_ctx.state != FNIRS_STATE_START) {
        return;
    }
    
    /* 计算当前处理的LED和波长类型 */
    uint8_t half_cycle = g_fnirs_ctx.timer_count / 2;  /* 每个LED有两个波长周期 */
    uint8_t wavelength_type = g_fnirs_ctx.timer_count % 2;  /* 0=红光, 1=红外光 */
    uint8_t led_index = half_cycle % g_fnirs_ctx.config.source_count;
    
    /* 获取当前缓冲区和探测器配置 */
    uint8_t* current_buffer = g_fnirs_ctx.data_buffer.send_buffer[g_fnirs_ctx.data_buffer.buffer_idx].channel_data;
    uint16_t detector_config = g_fnirs_ctx.config.config[led_index];
    
    /* 根据波长类型处理 */
    if (wavelength_type == LED_RED_WAVELENGTH) {
        _fnirs_handle_red_wavelength(led_index, detector_config);
    } else {
        _fnirs_handle_ir_wavelength(led_index, detector_config);
    }
    
    /* 处理之前采集的数据（除了第一个周期） */
    if (g_fnirs_ctx.timer_count != 0) {
        _fnirs_process_adc_samples(g_fnirs_ctx.data_buffer.data_save_addr);
        g_fnirs_ctx.data_buffer.data_save_addr += 3;  /* 移动到下一个数据位置 */
        
        /* 检查是否完成一轮完整的采集 */
        uint8_t total_cycles = g_fnirs_ctx.config.source_count * 2;
        if (g_fnirs_ctx.timer_count % total_cycles == 0) {
            nirs_data_send(current_buffer);
        }
    }
    
    g_fnirs_ctx.timer_count++;
}

/**
 * @brief 写入SD卡数据
 * @param data_buffer 数据缓冲区指针
 * @param period_number 数据包编号
 */
static void _fnirs_write_sd_card(uint8_t* data_buffer, uint32_t period_number)
{
    SD_CARD_STRUCT* sd_card = &g_fnirs_ctx.data_buffer.sd_buffer;
    
    /* 计算在缓冲区中的位置 */
    uint8_t batch_offset = period_number % sd_card->batches_per_block;
    uint32_t block_offset = period_number / sd_card->batches_per_block;
    
    /* 复制数据到SD卡缓冲区 */
    uint8_t* dest_addr = sd_card->tx_buffer[sd_card->buffer_idx].buffer + 
                         batch_offset * g_fnirs_ctx.data_buffer.send_buffer_len;
    memcpy(dest_addr, data_buffer, g_fnirs_ctx.data_buffer.send_buffer_len);
    
    /* 检查是否写满一个块 */
    if (batch_offset == sd_card->batches_per_block - 1) {
        uint32_t block_address = sd_card->sd_base_address + block_offset * sd_card->blocks_to_write;
        
        if (!sdio_write(sd_card->tx_buffer[sd_card->buffer_idx].buffer, 
                       block_address, sd_card->blocks_to_write)) {
            DebugPrintf("SD card write error\r\n");
        }
        
        /* 切换缓冲区索引 */
        sd_card->buffer_idx = (sd_card->buffer_idx == 1) ? 0 : 1;
    }
}


/**
 * @brief 从SD卡读取fNIRS数据
 * @param package_number 数据包编号
 */
void sd_read_nirs(uint32_t package_number)
{
    SD_CARD_STRUCT* sd_card = &g_fnirs_ctx.data_buffer.sd_buffer;
    
    /* 计算数据包位置 */
    uint8_t batch_offset = package_number % sd_card->batches_per_block;
    uint32_t block_offset = package_number / sd_card->batches_per_block;
    uint32_t block_address = sd_card->sd_base_address + block_offset * sd_card->blocks_to_write;
    
    /* 使用备用缓冲区（索引2）进行读取 */
    uint8_t* read_buffer = sd_card->tx_buffer[2].buffer;
    
    /* 从SD卡读取数据 */
    if (sdio_read(read_buffer, block_address, sd_card->blocks_to_write) != HAL_OK) {
        DebugPrintf("SD card read error\r\n");
        return;
    }
    
    /* 定位到具体的数据包位置 */
    uint8_t* data_packet = read_buffer + batch_offset * g_fnirs_ctx.data_buffer.send_buffer_len;
    
    /* 修改命令类型为应答 */
    data_packet[FRAME_CMD_POSITION] = CMD_SUPPLEMENTARY;
    
    /* 重新计算CRC校验码 */
    uint16_t crc_value = calculate_crc16(data_packet, g_fnirs_ctx.data_buffer.send_buffer_len - 2);
    uint16_t crc_value_be = ENDIAN_SWAP_16B(crc_value);
    memcpy(data_packet + g_fnirs_ctx.data_buffer.send_buffer_len - 2, 
           &crc_value_be, sizeof(crc_value_be));
    
    /* 通过SPI发送数据 */
    spi_transmit_dma(data_packet, g_fnirs_ctx.data_buffer.send_buffer_len, 100);
}


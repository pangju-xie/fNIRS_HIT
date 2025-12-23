#include "ads1258.h"
#include "spi.h"
#include "string.h"
#include "utils.h"
#include "main.h"
#include "gpio.h"
#include "usart.h"
/******************************************************************************
 * 全局变量定义
 ******************************************************************************/

uint8_t coutflag = 0;                      /**< 计数器标志，用于调试或状态指示 */
uint8_t registerMap[NUM_REGISTERS] = {0};  /**< 寄存器映射表，存储所有寄存器的当前值 */
uint8_t datadone = 0;                      /**< 数据完成标志，用于指示一轮扫描完成 */

/* 数据缓冲区 */
uint8_t DataTx[20] = {0};                  /**< SPI发送数据缓冲区 */
uint8_t DataRx[20] = {0};                  /**< SPI接收数据缓冲区 */
uint8_t RxBuf[90]  = {0};                  /**< 原始数据接收缓冲区 */
uint8_t StaBuf[30] = {0};                  /**< 状态数据缓冲区 */

channel_info channel = {0};                 /**< 通道信息结构体 */

/******************************************************************************
 * 内部函数声明
 ******************************************************************************/

static void _ads1258_spi_transfer(uint8_t *tx_data, uint8_t *rx_data, uint16_t size);
static uint8_t _ads1258_validate_address(uint8_t address);

/******************************************************************************
 * 函数实现
 ******************************************************************************/

/**
 * @brief SPI传输封装函数
 * @param tx_data 发送数据指针
 * @param rx_data 接收数据指针
 * @param size 传输数据大小
 * @note 封装SPI传输过程，简化代码重复
 */
static void _ads1258_spi_transfer(uint8_t *tx_data, uint8_t *rx_data, uint16_t size)
{
    ADS1258_CS(LOW);
    HAL_SPI_TransmitReceive(&ADS1258_SPI, tx_data, rx_data, size, 100);
    ADS1258_CS(HIGH);
}

/**
 * @brief 验证寄存器地址有效性
 * @param address 要验证的寄存器地址
 * @return 有效返回地址，无效返回0xFF
 */
static uint8_t _ads1258_validate_address(uint8_t address)
{
    if (address >= NUM_REGISTERS) {
        DebugPrintf("ADS1258 addr error: 0x%02X overflow (max: 0x%02X)\r\n", 
                   address, NUM_REGISTERS - 1);
        return 0xFF;
    }
    return address;
}

/**
 * @brief 获取配置寄存器值
 * @param address 寄存器地址
 * @return 寄存器值，如果地址无效返回0
 * @note 从寄存器映射表中获取值，不进行实际SPI读取
 */
uint8_t getRegisterValue(uint8_t address)
{
    address = _ads1258_validate_address(address);
    if (address == 0xFF) {
        return 0;
    }
    return registerMap[address];
}

/**
 * @brief 初始化ADS1258
 * @note 配置ADS1258的初始状态，包括复位、寄存器配置等
 *       执行以下步骤：
 *       1. 初始化硬件引脚
 *       2. 验证设备ID
 *       3. 配置初始寄存器设置
 *       4. 验证寄存器配置
 */
void ads1258init(void)
{
    /* 初始化硬件引脚 */
    ADS1258_START(LOW);     /* 停止转换 */
    ADS1258_CS(HIGH);       /* 取消片选 */
    Delay_us(25);           /* 等待稳定 */
    
    /* 验证设备ID */
    uint8_t device_id = readSingleRegister(REG_ADDR_ID);
    if (ADS1258_ID != device_id) {
        DebugPrintf("ADS1258 init error: read ID error (expect: 0x%02X, get: 0x%02X)\r\n", 
                   ADS1258_ID, device_id);
        Error_Handler();
        return;
    }
    
    /* 配置初始寄存器设置 */
    uint8_t initRegisterMap[NUM_REGISTERS] = {0};
    memset(initRegisterMap, 0, NUM_REGISTERS);
    initRegisterMap[REG_ADDR_CONFIG0] = CONFIG0_BYPAS_MASK |   /* 外部多路复用器 */
                                        CONFIG0_CHOP_MASK  |   /* 启用斩波功能 */
                                        CONFIG0_STAT_MASK;     /* 读取数据时包含状态字节 */
    
    initRegisterMap[REG_ADDR_CONFIG1] = CONFIG1_DLY_0us |      /* 无通道转换延迟 */
                                        CONFIG1_DRATE_23739SPS; /* 23739 SPS采样率 */
    
//    initRegisterMap[REG_ADDR_MUXSG0]  = MUXSG0_DEFAULT;        /* 单端通道0-7全开 */
//    initRegisterMap[REG_ADDR_MUXSG1]  = MUXSG1_DEFAULT;        /* 单端通道8-15全开 */
    
    /* 写入可写寄存器 (跳过只读的ID寄存器) */
    writeMultipleRegisters(REG_ADDR_CONFIG0, NUM_REGISTERS - 1, initRegisterMap);
    
    /* 读取回所有寄存器进行验证 */
    readMultipleRegisters(REG_ADDR_CONFIG0, NUM_REGISTERS - 1);
    
    /* 验证寄存器配置是否成功 */
    if (memcmp(initRegisterMap, registerMap, NUM_REGISTERS - 1) != 0) {
        DebugPrintf("ADS1258 register validate error\r\n");
        for (uint8_t i = 0; i < NUM_REGISTERS - 1; i++) {
            if (initRegisterMap[i] != registerMap[i]) {
                DebugPrintf("register 0x%02X: hope=0x%02X, get=0x%02X\r\n", 
                           i, initRegisterMap[i], registerMap[i]);
            }
        }
        Error_Handler();
        return;
    }
    
    DebugPrintf("ADS1258 Init Done\r\n");
}

/**
 * @brief 设置GPIO输出电平
 * @param bit 要设置的位 (0-7)
 * @param on 电平设置：1=高电平，0=低电平
 */
void ads1258_setgpio(uint8_t bit, uint8_t on)
{
    if (bit > 7) {
        DebugPrintf("ADS1258 GPIO bit error: %d (validate range: 0-7)\r\n", bit);
        return;
    }
    
    uint8_t mask = (1 << bit);
    
    if (on) {
        SET_BIT(registerMap[REG_ADDR_GPIOD], mask);
    } else {
        CLEAR_BIT(registerMap[REG_ADDR_GPIOD], mask);
    }
    
    writeSingleRegister(REG_ADDR_GPIOD, registerMap[REG_ADDR_GPIOD]);
    DebugPrintf("ADS1258 GPIO%d set to %s\r\n", bit, on ? "high" : "low");
}

/**
 * @brief 统计通道信息
 * @note 根据当前寄存器配置计算通道数量、映射关系等信息
 *       统计范围：MUXDIF, MUXSG0, MUXSG1, SYSRED寄存器
 */
void count_channel_info(void)
{
    /* 清零通道信息结构体 */
    memset(&channel, 0, sizeof(channel));
    
    /* 构建通道掩码 */
    channel.mask = 0;
    for (uint8_t i = REG_ADDR_SYSRED; i >= REG_ADDR_MUXDIF; i--) {
        channel.mask = (channel.mask << 8) | registerMap[i];
    }
    
    /* 统计通道数量和构建映射表 */
    for (uint8_t i = 0; i < 32; i++) {
        if (GET_BIT(channel.mask, i)) {
            channel.chn_map[channel.num] = i;
            channel.num++;
        }
    }
    
    /* 设置d2chn标志 */
    if (channel.num == 0) {
        channel.d2chn = 0xFF;      /* 无通道 */
    } else if (channel.num == 1) {
        channel.d2chn = 0xFE;      /* 单通道 */
    } else {
        channel.d2chn = channel.chn_map[channel.num - 2]; /* 倒数第二个通道 */
    }
    
//    DebugPrintf("channel count done: total num=%d, mask=0x%08lX, d2chn=0x%02X\r\n", 
//               channel.num, channel.mask, channel.d2chn);
}

/**
 * @brief 设置ADS1258通道
 * @param buf_cfg 通道配置数组指针
 * @note 配置ADS1258的输入通道，支持差分和单端模式
 */
void set_ads_channel(uint16_t *buf_cfg)
{
    /* 写入通道配置寄存器 */
    writeMultipleRegisters(REG_ADDR_MUXSG0, 2, (uint8_t *)buf_cfg);
    
    /* 读取回寄存器进行验证 */
    readMultipleRegisters(REG_ADDR_MUXSG0, 2);
    
    /* 重新统计通道信息 */
    count_channel_info();
    
//    DebugPrintf("channel set Done: MUXSG0=0x%02X, MUXSG1=0x%02X\r\n", 
//               registerMap[REG_ADDR_MUXSG0], registerMap[REG_ADDR_MUXSG1]);
}

/**
 * @brief 读取单个寄存器
 * @param address 寄存器地址
 * @return 寄存器值
 */
uint8_t readSingleRegister(uint8_t address)
{
    address = _ads1258_validate_address(address);
    if (address == 0xFF) {
        return 0;
    }
    
    uint8_t tx_data[2] = {0};
    uint8_t rx_data[2] = {0};
    
    /* 构建发送数据：读取寄存器命令 + 地址 */
    tx_data[0] = OPCODE_RREG | (address & OPCODE_A_MASK);
    
    /* 执行SPI传输 */
    _ads1258_spi_transfer(tx_data, rx_data, 2);
    
    /* 更新寄存器映射表并返回结果 */
    registerMap[address] = rx_data[1];
    return rx_data[1];
}

/**
 * @brief 读取多个寄存器
 * @param startAddress 起始地址
 * @param count 读取数量
 * @note 使用getRegisterValue()函数获取读取的值
 */
void readMultipleRegisters(uint8_t startAddress, uint8_t count)
{
    /* 参数检查 */
    if (startAddress + count > NUM_REGISTERS) {
        DebugPrintf("read address error: start=0x%02X, num =%d\r\n", startAddress, count);
        return;
    }
    
    uint8_t tx_data[20] = {0};
    uint8_t rx_data[20] = {0};
    
    /* 构建发送数据：读取多个寄存器命令 */
    tx_data[0] = OPCODE_RREG | OPCODE_MUL_MASK | (startAddress & OPCODE_A_MASK);
    
    /* 执行SPI传输 */
    _ads1258_spi_transfer(tx_data, rx_data, count + 1);
    
    /* 复制数据到寄存器映射表 */
    memcpy(registerMap + startAddress, rx_data + 1, count);
}

/**
 * @brief 写入单个寄存器
 * @param address 寄存器地址
 * @param data 要写入的数据
 */
void writeSingleRegister(uint8_t address, uint8_t data)
{
    address = _ads1258_validate_address(address);
    if (address == 0xFF) {
        return;
    }
    
    uint8_t tx_data[2] = {0};
    uint8_t rx_data[2] = {0};
    
    /* 构建发送数据：写入寄存器命令 + 数据 */
    tx_data[0] = OPCODE_WREG | (address & OPCODE_A_MASK);
    tx_data[1] = data;
    
    /* 执行SPI传输 */
    _ads1258_spi_transfer(tx_data, rx_data, 2);
    
//    /* 更新寄存器映射表 */
//    registerMap[address] = data;
}

/**
 * @brief 写入多个寄存器
 * @param startAddress 起始地址
 * @param count 写入数量
 * @param regData 要写入的数据数组
 * @note 写入后应重新读取寄存器以确保正确配置
 */
void writeMultipleRegisters(uint8_t startAddress, uint8_t count, uint8_t regData[])
{
    /* 参数检查 */
    if (startAddress + count > NUM_REGISTERS) {
        DebugPrintf("write addr error: start=0x%02X, num=%d\r\n", startAddress, count);
        return;
    }
    
    uint8_t tx_data[20] = {0};
    uint8_t rx_data[20] = {0};
    
    /* 构建发送数据：写入多个寄存器命令 + 数据 */
    tx_data[0] = OPCODE_WREG | OPCODE_MUL_MASK | (startAddress & OPCODE_A_MASK);
    memcpy(tx_data + 1, regData, count);
    
    /* 执行SPI传输 */
    _ads1258_spi_transfer(tx_data, rx_data, count + 1);
    
//    /* 更新寄存器映射表 */
//    memcpy(registerMap + startAddress, regData, count);
}

/**
 * @brief 发送SPI命令
 * @param op_code SPI命令字节
 */
void sendCommand(uint8_t op_code)
{
    /* 执行SPI传输 */
    ADS1258_CS(LOW);
    HAL_SPI_Transmit(&ADS1258_SPI, &op_code, 1, 100);
    ADS1258_CS(HIGH);
    
    /* 如果是复位命令，恢复寄存器默认值 */
    if (OPCODE_RESET == op_code) {
        restoreRegisterDefaults();
    }
}

/**
 * @brief 启动连续转换
 */
void startConversions(void)
{
    ADS1258_START(HIGH);
}

/**
 * @brief 停止连续转换
 */
void stopConversions(void)
{
    ADS1258_START(LOW);
}

/**
 * @brief 直接读取数据模式
 * @param data 数据存储数组
 * @return 转换后的电压值（单位：mV）
 * @note 使用直接读取模式获取转换数据
 */
uint8_t ReadDataDirect(uint8_t data[])
{
    uint8_t tx_data[4] = {0};
    uint8_t rx_data[4] = {0};
    uint8_t channel_id = 0;
    float voltage = 0.0f;
    
    /* 构建发送数据：直接读取命令 */
    tx_data[0] = OPCODE_READ_DIRECT;
    
    /* 短暂延迟确保数据稳定 */
    Delay_us(1);
    
    /* 执行SPI传输 */
    _ads1258_spi_transfer(tx_data, rx_data, 4);
    
    /* 提取通道ID */
    channel_id = rx_data[0] & STATUS_CHID_MASK;
    
    memcpy(data, rx_data + 1, 3);
    voltage = DataConvert(channel_id, data);
//    /* 查找通道在映射表中的位置并存储数据 */
//    for (uint8_t i = 0; i < channel.num; i++) {
//        if (channel_id == channel.chn_map[i]) {
//            uint8_t data_index = i * 3;  /* 每个通道3字节数据 */
//            memcpy(data + data_index, rx_data + 1, 3);
//            voltage = DataConvert(channel_id, data + data_index);
//            break;
//        }
//    }
//    /* 检查是否完成一轮扫描 */
//    if (channel.num > 1 && channel_id == channel.d2chn) {
//        ADS1258_START(LOW);  /* 停止转换 */
//        datadone = 1;        /* 设置完成标志 */
//    }
    
    return channel_id - STATUS_CHID_AIN0;
}

/**
 * @brief 命令模式读取数据
 * @param data 数据存储数组
 */
void ReadDataCommand(uint8_t data[])
{
    uint8_t tx_data[5] = {0};
    uint8_t rx_data[5] = {0};
    uint8_t channel_id = 0;
    
    /* 构建发送数据：命令读取模式（带MUL标志） */
    tx_data[0] = OPCODE_READ_COMMAND | OPCODE_MUL_MASK;
    
    /* 执行SPI传输 */
    _ads1258_spi_transfer(tx_data, rx_data, 5);
    
    /* 提取通道ID */
    channel_id = rx_data[1] & STATUS_CHID_MASK;
    
    /* 查找通道在映射表中的位置并存储数据 */
    for (uint8_t i = 0; i < channel.num; i++) {
        if (channel_id == channel.chn_map[i]) {
            uint8_t data_index = i * 3;  /* 每个通道3字节数据 */
            memcpy(data + data_index, rx_data + 2, 3);
            break;
        }
    }
}

/**
 * @brief 数据转换函数
 * @param chn 通道ID
 * @param data 原始数据数组（3字节）
 * @return 转换后的物理量值
 * @note 根据通道类型将原始24位数据转换为相应的物理量
 *       支持：电压、温度、参考电压、增益、偏移、电源电压
 */
float DataConvert(uint8_t chn, uint8_t data[])
{
    /* 校准参数（静态变量保持值） */
    static float offset = 0.0f;    /* 偏移校准值 */
    static float vcc    = 5.0f;    /* 电源电压值 */
    static float temp   = 0.0f;    /* 温度值 */
    static float gain   = 0.999f;  /* 增益校准值 */
    static float ref    = 5.0f;    /* 参考电压值 */
    
    float result = 0.0f;
    
    /* 参数检查 */
    if (chn > STATUS_CHID_FIXEDCHMODE) {
        return 0.0f;
    }
    
    /* 合并24位数据 */
    uint32_t raw_value = ((uint32_t)data[0] << 16) | 
                         ((uint32_t)data[1] << 8)  | 
                         (uint32_t)data[2];
    
    /* 根据通道类型进行转换 */
    switch (chn) {
        case STATUS_CHID_OFFSET:
            offset = raw_value / 1.0f;
            //DebugPrintf("偏移校准值: 0x%06lX = %.3f\r\n", raw_value, offset);
            result = offset;
            break;
            
        case STATUS_CHID_VCC:
            vcc = raw_value / 786432.0f;  /* 24位满量程对应VCC/4 */
            //DebugPrintf("电源电压: 0x%06lX = %.3fV\r\n", raw_value, vcc);
            result = vcc;
            break;
            
        case STATUS_CHID_TEMP:
            /* 温度传感器处理（处理负数） */
            if (raw_value & 0x800000) {
                raw_value = 0xFFFFFF - raw_value;  /* 补码转换 */
            }
            temp = (((float)(raw_value / 0x780000) * ref) * 1000000 - 168000) / 563 + 25;
            //DebugPrintf("温度: 0x%06lX = %.2f°C\r\n", raw_value, temp);
            result = temp;
            break;
            
        case STATUS_CHID_GAIN:
            gain = raw_value / 7864320.0f;  /* 24位满量程对应10倍增益 */
            //DebugPrintf("增益校准: 0x%06lX = %.3f\r\n", raw_value, gain);
            result = gain;
            break;
            
        case STATUS_CHID_REF:
            ref = raw_value / 786432.0f;  /* 24位满量程对应参考电压/4 */
            //DebugPrintf("参考电压: 0x%06lX = %.3fV\r\n", raw_value, ref);
            result = ref;
            break;
            
        default:
            /* 普通模拟输入通道（差分或单端） */
            if (chn < STATUS_CHID_AIN15) {
                if (raw_value & 0x800000) {
                    /* 负数处理 */
                    raw_value = 0xFFFFFF - raw_value;
                    result = -((float)raw_value / 0x780000) * ref / gain * 1000;  /* 转换为mV */
                } else {
                    /* 正数处理 */
                    result = ((float)raw_value / 0x780000) * ref / gain * 1000;  /* 转换为mV */
                }
                
                //HAL_UART_Transmit(&huart2, (uint8_t*)&result,4, 100);
                
                /* 输出调试信息 */
                if (chn < STATUS_CHID_DIFF7) {
                    DebugPrintf("diff channel %d: 0x%06lX = %.2fmV\r\n", chn, raw_value, result);
                } else {
                    uint8_t single_channel = chn - STATUS_CHID_DIFF7;
                    DebugPrintf("single channel %d: %.2fmV\r\n", single_channel, result);
                }
            }
            break;
    }
    
    return result;
}

/**
 * @brief 恢复寄存器默认值
 * @note 将寄存器映射表更新为默认值
 *       在设备复位后调用此函数以保持软件与硬件同步
 */
void restoreRegisterDefaults(void)
{
    registerMap[REG_ADDR_CONFIG0] = CONFIG0_DEFAULT;
    registerMap[REG_ADDR_CONFIG1] = CONFIG1_DEFAULT;
    registerMap[REG_ADDR_MUXSCH]  = MUXSCH_DEFAULT;
    registerMap[REG_ADDR_MUXDIF]  = MUXDIF_DEFAULT;
    registerMap[REG_ADDR_MUXSG0]  = MUXSG0_DEFAULT;
    registerMap[REG_ADDR_MUXSG1]  = MUXSG1_DEFAULT;
    registerMap[REG_ADDR_SYSRED]  = SYSRED_DEFAULT;
    registerMap[REG_ADDR_GPIOC]   = GPIOC_DEFAULT;
    registerMap[REG_ADDR_GPIOD]   = GPIOD_DEFAULT;
    registerMap[REG_ADDR_ID]      = 0x00;  /* 0x00表示尚未读取ID寄存器 */
    
    //DebugPrintf("寄存器映射表已恢复为默认值\r\n");
}


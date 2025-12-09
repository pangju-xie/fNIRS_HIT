/* --COPYRIGHT--,BSD
 * Copyright (c) 2018, Texas Instruments Incorporated
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 * --/COPYRIGHT--*/

#ifndef ADS1258_H_
#define ADS1258_H_

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include "main.h"
#include "spi.h"

/******************************************************************************
 * 硬件引脚定义和宏
 ******************************************************************************/

/* 使用SPI1接口与ADS1258通信 */
#define ADS1258_SPI              (hspi1)

/* 片选信号控制宏 */
#define ADS1258_CS(x)            (HAL_GPIO_WritePin(NIRS_CS_GPIO_Port, NIRS_CS_Pin, x))

/* 启动转换信号控制宏 */
#define ADS1258_START(x)         (HAL_GPIO_WritePin(NIRS_START_GPIO_Port, NIRS_START_Pin, x))

/* 读取数据就绪信号宏 */
#define ReadNIRS()               (HAL_GPIO_ReadPin(NIRS_DRDY_GPIO_Port, NIRS_DRDY_Pin))

/* 高低电平定义 */
#define HIGH                     (GPIO_PIN_SET)
#define LOW                      (GPIO_PIN_RESET)

/******************************************************************************
 * 常量定义
 ******************************************************************************/

/* ADS1258设备ID */
#define ADS1258_ID               0x8B

/* 寄存器数量 */
#define NUM_REGISTERS            10

/******************************************************************************
 * 数据结构定义
 ******************************************************************************/

/**
 * @brief 通道信息结构体
 * @param mask    通道掩码，用于快速计算通道数
 * @param num     通道总数
 * @param d2chn   差分通道数
 * @param chn_map 通道映射表，最大支持30个通道
 */
typedef struct {
    uint32_t mask;      /**< 通道掩码 */
    uint8_t  num;       /**< 通道总数 */
    uint8_t  d2chn;     /**< 差分通道数 */
    uint8_t  chn_map[30]; /**< 通道映射表 */
} channel_info;

/******************************************************************************
 * 命令字节定义
 * ---------------------------------------------------------------------------------
 * |  Bit 7  |  Bit 6  |  Bit 5  |  Bit 4  |  Bit 3  |  Bit 2  |  Bit 1  |  Bit 0  |
 * ---------------------------------------------------------------------------------
 * |            C[2:0]           |   MUL   |                A[3:0]                 |
 * ---------------------------------------------------------------------------------
 ******************************************************************************/

/* SPI操作码定义 */
#define OPCODE_READ_DIRECT       0x00  /**< 直接读取数据 */
#define OPCODE_READ_COMMAND      0x30  /**< 通过命令读取数据（包含MUL位） */
#define OPCODE_RREG              0x40  /**< 读取寄存器 */
#define OPCODE_WREG              0x60  /**< 写入寄存器 */
#define OPCODE_PULSE_CONVERT     0x80  /**< 脉冲转换命令 */
#define OPCODE_RESET             0xC0  /**< 复位命令 */

/* 命令字节掩码 */
#define OPCODE_C_MASK            0xE0  /**< 命令位掩码（高3位） */
#define OPCODE_MUL_MASK          0x10  /**< MUL位掩码 */
#define OPCODE_A_MASK            0x0F  /**< 地址位掩码（低4位） */

/**
 * @brief 读取模式枚举
 */
typedef enum {
    DIRECT,     /**< 直接读取模式 */
    COMMAND     /**< 命令读取模式 */
} readMode;

/******************************************************************************
 * 状态字节定义
 * ---------------------------------------------------------------------------------
 * |  Bit 7  |  Bit 6  |  Bit 5  |  Bit 4  |  Bit 3  |  Bit 2  |  Bit 1  |  Bit 0  |
 * ---------------------------------------------------------------------------------
 * |   NEW   |   OVF   |  SUPPLY |                    CHID[4:0]                    |
 * ---------------------------------------------------------------------------------
 ******************************************************************************/

/* 状态字节字段掩码 */
#define STATUS_NEW_MASK          0x80  /**< 新数据指示位 */
#define STATUS_OVF_MASK          0x40  /**< 差分超量程指示位 */
#define STATUS_SUPPLY_MASK       0x20  /**< 低模拟电源指示位 */
#define STATUS_CHID_MASK         0x1F  /**< 通道ID位掩码 */

/* 通道ID值定义 */
#define STATUS_CHID_DIFF0        0x00  /**< 差分通道0 */
#define STATUS_CHID_DIFF1        0x01  /**< 差分通道1 */
#define STATUS_CHID_DIFF2        0x02  /**< 差分通道2 */
#define STATUS_CHID_DIFF3        0x03  /**< 差分通道3 */
#define STATUS_CHID_DIFF4        0x04  /**< 差分通道4 */
#define STATUS_CHID_DIFF5        0x05  /**< 差分通道5 */
#define STATUS_CHID_DIFF6        0x06  /**< 差分通道6 */
#define STATUS_CHID_DIFF7        0x07  /**< 差分通道7 */

#define STATUS_CHID_AIN0         0x08  /**< 单端输入AIN0 */
#define STATUS_CHID_AIN1         0x09  /**< 单端输入AIN1 */
#define STATUS_CHID_AIN2         0x0A  /**< 单端输入AIN2 */
#define STATUS_CHID_AIN3         0x0B  /**< 单端输入AIN3 */
#define STATUS_CHID_AIN4         0x0C  /**< 单端输入AIN4 */
#define STATUS_CHID_AIN5         0x0D  /**< 单端输入AIN5 */
#define STATUS_CHID_AIN6         0x0E  /**< 单端输入AIN6 */
#define STATUS_CHID_AIN7         0x0F  /**< 单端输入AIN7 */
#define STATUS_CHID_AIN8         0x10  /**< 单端输入AIN8 */
#define STATUS_CHID_AIN9         0x11  /**< 单端输入AIN9 */
#define STATUS_CHID_AIN10        0x12  /**< 单端输入AIN10 */
#define STATUS_CHID_AIN11        0x13  /**< 单端输入AIN11 */
#define STATUS_CHID_AIN12        0x14  /**< 单端输入AIN12 */
#define STATUS_CHID_AIN13        0x15  /**< 单端输入AIN13 */
#define STATUS_CHID_AIN14        0x16  /**< 单端输入AIN14 */
#define STATUS_CHID_AIN15        0x17  /**< 单端输入AIN15 */

#define STATUS_CHID_OFFSET       0x18  /**< 偏移校准通道 */
#define STATUS_CHID_VCC          0x1A  /**< 电源电压通道 */
#define STATUS_CHID_TEMP         0x1B  /**< 温度传感器通道 */
#define STATUS_CHID_GAIN         0x1C  /**< 增益校准通道 */
#define STATUS_CHID_REF          0x1D  /**< 参考电压通道 */
#define STATUS_CHID_FIXEDCHMODE  0x1F  /**< 固定通道模式ID */

/******************************************************************************
 * 寄存器地址定义
 ******************************************************************************/

/* 寄存器地址定义 */
#define REG_ADDR_CONFIG0         0x00  /**< 配置寄存器0地址 */
#define REG_ADDR_CONFIG1         0x01  /**< 配置寄存器1地址 */
#define REG_ADDR_MUXSCH          0x02  /**< 多路选择通道寄存器地址（固定通道模式） */
#define REG_ADDR_MUXDIF          0x03  /**< 多路差分寄存器地址（自动模式） */
#define REG_ADDR_MUXSG0          0x04  /**< 多路单端0寄存器地址（自动模式） */
#define REG_ADDR_MUXSG1          0x05  /**< 多路单端1寄存器地址（自动模式） */
#define REG_ADDR_SYSRED          0x06  /**< 系统监控寄存器地址（自动模式） */
#define REG_ADDR_GPIOC           0x07  /**< GPIO配置寄存器地址 */
#define REG_ADDR_GPIOD           0x08  /**< GPIO数据寄存器地址 */
#define REG_ADDR_ID              0x09  /**< ID寄存器地址 */

/******************************************************************************
 * 寄存器配置定义（CONFIG0）
 * ---------------------------------------------------------------------------------
 * |  Bit 7  |  Bit 6  |  Bit 5  |  Bit 4  |  Bit 3  |  Bit 2  |  Bit 1  |  Bit 0  |
 * ---------------------------------------------------------------------------------
 * |    0    |  SPIRST |  MUXMOD |  BYPAS  |  CLKENB |   CHOP  |   STAT  |    0    |
 * ---------------------------------------------------------------------------------
 ******************************************************************************/

/* CONFIG0默认值（复位值） */
#define CONFIG0_DEFAULT          0x0A

/* CONFIG0寄存器字段掩码 */
#define CONFIG0_SPIRST_MASK      0x40  /**< SPI复位时间：0=256us，1=16us */
#define CONFIG0_MUXMOD_MASK      0x20  /**< 通道操作模式：0=自动扫描，1=固定通道 */
#define CONFIG0_BYPAS_MASK       0x10  /**< 多路复用器输出选择：0=内部，1=外部 */
#define CONFIG0_CLKENB_MASK      0x08  /**< CLKIO输出：0=不输出，1=输出 */
#define CONFIG0_CHOP_MASK        0x04  /**< 外部多路复用器斩波功能：0=不使能，1=使能 */
#define CONFIG0_STAT_MASK        0x02  /**< 数据读取时是否包含状态字节：0=不带，1=带 */

/******************************************************************************
 * 寄存器配置定义（CONFIG1）
 * ---------------------------------------------------------------------------------
 * |  Bit 7  |  Bit 6  |  Bit 5  |  Bit 4  |  Bit 3  |  Bit 2  |  Bit 1  |  Bit 0  |
 * ---------------------------------------------------------------------------------
 * |  IDLMOD |           DLY[2:0]          |     SCBCS[1:0]    |     DRATE[0:1]    |
 * ---------------------------------------------------------------------------------
 ******************************************************************************/

/* CONFIG1默认值（复位值） */
#define CONFIG1_DEFAULT          0x83

/* CONFIG1寄存器字段掩码 */
#define CONFIG1_IDLMOD_MASK      0x80  /**< 空闲模式：0=待机，1=睡眠 */
#define CONFIG1_DLY_MASK         0x70  /**< 通道转换延迟时间 */
#define CONFIG1_SCBCS_MASK       0x0C  /**< 传感器偏置电流源 */
#define CONFIG1_DRATE_MASK       0x03  /**< 数据转换速率 */

/* 延迟时间字段值 */
#define CONFIG1_DLY_0us          0x00
#define CONFIG1_DLY_8us          0x10
#define CONFIG1_DLY_16us         0x20
#define CONFIG1_DLY_32us         0x30
#define CONFIG1_DLY_64us         0x40
#define CONFIG1_DLY_128us        0x50
#define CONFIG1_DLY_256us        0x60
#define CONFIG1_DLY_384us        0x70

/* 传感器偏置电流源字段值 */
#define CONFIG1_SCBCS_OFF        0x00  /**< 关闭偏置电流 */
#define CONFIG1_SCBCS_1_5uA      0x40  /**< 1.5μA偏置电流 */
#define CONFIG1_SCBCS_24uA       0xC0  /**< 24μA偏置电流 */

/* 数据转换速率字段值（固定通道模式） */
#define CONFIG1_DRATE_1953SPS    0x00  /**< 1953 SPS */
#define CONFIG1_DRATE_7813SPS    0x01  /**< 7813 SPS */
#define CONFIG1_DRATE_31250SPS   0x02  /**< 31250 SPS */
#define CONFIG1_DRATE_125000SPS  0x03  /**< 125000 SPS */

/* 数据转换速率字段值（自动模式） */
#define CONFIG1_DRATE_1831SPS    0x00  /**< 1831 SPS */
#define CONFIG1_DRATE_6068SPS    0x01  /**< 6068 SPS */
#define CONFIG1_DRATE_15123SPS   0x02  /**< 15123 SPS */
#define CONFIG1_DRATE_23739SPS   0x03  /**< 23739 SPS */

/******************************************************************************
 * 多路选择通道寄存器（MUXSCH）定义
 * ---------------------------------------------------------------------------------
 * |  Bit 7  |  Bit 6  |  Bit 5  |  Bit 4  |  Bit 3  |  Bit 2  |  Bit 1  |  Bit 0  |
 * ---------------------------------------------------------------------------------
 * |               AINP[3:0]               |               AINN[3:0]               |
 * ---------------------------------------------------------------------------------
 ******************************************************************************/

/* MUXSCH默认值（复位值） */
#define MUXSCH_DEFAULT           0x00

/* MUXSCH寄存器字段掩码 */
#define MUXSCH_AINP_MASK         0xF0  /**< 正输入选择（固定通道模式专用） */
#define MUXSCH_AINN_MASK         0x0F  /**< 负输入选择 */

/* 正输入选择值 */
#define MUXSCH_AINP_AIN0         0x00
#define MUXSCH_AINP_AIN1         0x10
#define MUXSCH_AINP_AIN2         0x20
#define MUXSCH_AINP_AIN3         0x30
#define MUXSCH_AINP_AIN4         0x40
#define MUXSCH_AINP_AIN5         0x50
#define MUXSCH_AINP_AIN6         0x60
#define MUXSCH_AINP_AIN7         0x70
#define MUXSCH_AINP_AIN8         0x80
#define MUXSCH_AINP_AIN9         0x90
#define MUXSCH_AINP_AIN10        0xA0
#define MUXSCH_AINP_AIN11        0xB0
#define MUXSCH_AINP_AIN12        0xC0
#define MUXSCH_AINP_AIN13        0xD0
#define MUXSCH_AINP_AIN14        0xE0
#define MUXSCH_AINP_AIN15        0xF0

/* 负输入选择值 */
#define MUXSCH_AINN_AIN0         0x00
#define MUXSCH_AINN_AIN1         0x01
#define MUXSCH_AINN_AIN2         0x02
#define MUXSCH_AINN_AIN3         0x03
#define MUXSCH_AINN_AIN4         0x04
#define MUXSCH_AINN_AIN5         0x05
#define MUXSCH_AINN_AIN6         0x06
#define MUXSCH_AINN_AIN7         0x07
#define MUXSCH_AINN_AIN8         0x08
#define MUXSCH_AINN_AIN9         0x09
#define MUXSCH_AINN_AIN10        0x0A
#define MUXSCH_AINN_AIN11        0x0B
#define MUXSCH_AINN_AIN12        0x0C
#define MUXSCH_AINN_AIN13        0x0D
#define MUXSCH_AINN_AIN14        0x0E
#define MUXSCH_AINN_AIN15        0x0F

/******************************************************************************
 * 多路差分寄存器（MUXDIF）定义 - 自动模式专用
 ******************************************************************************/

/* MUXDIF默认值（复位值） */
#define MUXDIF_DEFAULT           0x00

/* MUXDIF寄存器字段掩码（差分输入使能） */
#define MUXDIF_DIFF7_ENABLE      0x80  /**< 差分通道7使能 */
#define MUXDIF_DIFF6_ENABLE      0x40  /**< 差分通道6使能 */
#define MUXDIF_DIFF5_ENABLE      0x20  /**< 差分通道5使能 */
#define MUXDIF_DIFF4_ENABLE      0x10  /**< 差分通道4使能 */
#define MUXDIF_DIFF3_ENABLE      0x08  /**< 差分通道3使能 */
#define MUXDIF_DIFF2_ENABLE      0x04  /**< 差分通道2使能 */
#define MUXDIF_DIFF1_ENABLE      0x02  /**< 差分通道1使能 */
#define MUXDIF_DIFF0_ENABLE      0x01  /**< 差分通道0使能 */

/******************************************************************************
 * 多路单端寄存器（MUXSG0/MUXSG1）定义 - 自动模式专用
 ******************************************************************************/

/* 默认值（复位值） */
#define MUXSG0_DEFAULT           0xFF
#define MUXSG1_DEFAULT           0xFF

/* 单端输入使能掩码（低位字节） */
#define MUXSG0_AIN7_ENABLE       0x80
#define MUXSG0_AIN6_ENABLE       0x40
#define MUXSG0_AIN5_ENABLE       0x20
#define MUXSG0_AIN4_ENABLE       0x10
#define MUXSG0_AIN3_ENABLE       0x08
#define MUXSG0_AIN2_ENABLE       0x04
#define MUXSG0_AIN1_ENABLE       0x02
#define MUXSG0_AIN0_ENABLE       0x01

/* 单端输入使能掩码（高位字节） */
#define MUXSG1_AIN15_ENABLE      0x80
#define MUXSG1_AIN14_ENABLE      0x40
#define MUXSG1_AIN13_ENABLE      0x20
#define MUXSG1_AIN12_ENABLE      0x10
#define MUXSG1_AIN11_ENABLE      0x08
#define MUXSG1_AIN10_ENABLE      0x04
#define MUXSG1_AIN9_ENABLE       0x02
#define MUXSG1_AIN8_ENABLE       0x01

/******************************************************************************
 * 系统监控寄存器（SYSRED）定义 - 自动模式专用
 ******************************************************************************/

/* SYSRED默认值（复位值） */
#define SYSRED_DEFAULT           0x00

/* SYSRED寄存器字段掩码 */
#define SYSRED_REF_ENABLE        0x20  /**< 参考电压监控使能 */
#define SYSRED_GAIN_ENABLE       0x10  /**< 增益校准监控使能 */
#define SYSRED_TEMP_ENABLE       0x08  /**< 温度监控使能 */
#define SYSRED_VCC_ENABLE        0x04  /**< 电源电压监控使能 */
#define SYSRED_OFFSET_ENABLE     0x01  /**< 偏移校准监控使能 */

/******************************************************************************
 * GPIO配置寄存器（GPIOC/GPIOD）定义
 ******************************************************************************/

/* 默认值（复位值） */
#define GPIOC_DEFAULT            0xFF  /**< 配置为输入模式 */
#define GPIOD_DEFAULT            0x00  /**< 输出低电平 */

/* GPIO配置寄存器字段掩码（GPIOC） */
#define GPIOC_GPIO7_INPUT        0x80  /**< GPIO7配置：0=输出，1=输入 */
#define GPIOC_GPIO6_INPUT        0x40  /**< GPIO6配置：0=输出，1=输入 */
#define GPIOC_GPIO5_INPUT        0x20  /**< GPIO5配置：0=输出，1=输入 */
#define GPIOC_GPIO4_INPUT        0x10  /**< GPIO4配置：0=输出，1=输入 */
#define GPIOC_GPIO3_INPUT        0x08  /**< GPIO3配置：0=输出，1=输入 */
#define GPIOC_GPIO2_INPUT        0x04  /**< GPIO2配置：0=输出，1=输入 */
#define GPIOC_GPIO1_INPUT        0x02  /**< GPIO1配置：0=输出，1=输入 */
#define GPIOC_GPIO0_INPUT        0x01  /**< GPIO0配置：0=输出，1=输入 */

/* GPIO数据寄存器字段掩码（GPIOD） */
#define GPIOD_GPIO7_HIGH         0x80  /**< GPIO7电平：0=低，1=高 */
#define GPIOD_GPIO6_HIGH         0x40  /**< GPIO6电平：0=低，1=高 */
#define GPIOD_GPIO5_HIGH         0x20  /**< GPIO5电平：0=低，1=高 */
#define GPIOD_GPIO4_HIGH         0x10  /**< GPIO4电平：0=低，1=高 */
#define GPIOD_GPIO3_HIGH         0x08  /**< GPIO3电平：0=低，1=高 */
#define GPIOD_GPIO2_HIGH         0x04  /**< GPIO2电平：0=低，1=高 */
#define GPIOD_GPIO1_HIGH         0x02  /**< GPIO1电平：0=低，1=高 */
#define GPIOD_GPIO0_HIGH         0x01  /**< GPIO0电平：0=低，1=高 */

/******************************************************************************
 * ID寄存器定义
 ******************************************************************************/

/* ID寄存器字段掩码 */
#define ID_ID4_MASK              0x10  /**< 设备类型标识位 */

/* ID4字段值 */
#define ID_ID4_ADS1258           0x00  /**< ADS1258设备 */
#define ID_ID4_ADS1158           0x10  /**< ADS1158设备 */

/******************************************************************************
 * 外部变量声明
 ******************************************************************************/

extern uint8_t coutflag;  /**< 计数器标志，用于调试或状态指示 */

/******************************************************************************
 * 函数原型声明
 ******************************************************************************/

/* 初始化与配置函数 */
/**
 * @brief 测试ADS1258功能
 * @note 用于测试ADS1258的基本功能是否正常
 */
void ads1258_test(void);

/**
 * @brief 初始化ADS1258
 * @note 配置ADS1258的初始状态，包括复位、寄存器配置等
 */
void ads1258init(void);

/**
 * @brief 计算通道信息
 * @note 根据当前配置计算通道数量、映射关系等信息
 */
void count_channel_info(void);

/**
 * @brief 设置ADS1258通道
 * @param buf_cfg 通道配置数组指针
 * @return 操作状态：0=成功，其他=失败
 * @note 配置ADS1258的输入通道，支持差分和单端模式
 */
void set_ads_channel(uint16_t* buf_cfg);

/* 数据读取函数 */
/**
 * @brief 读取转换数据
 * @param status 状态字节存储数组
 * @param data 数据存储数组（24位数据，3个字节）
 * @param mode 读取模式：DIRECT或COMMAND
 * @return 转换后的32位有符号数据
 * @note 根据指定的读取模式从ADS1258读取转换数据
 */
int32_t readData(uint8_t status[], uint8_t data[], readMode mode);

/**
 * @brief 直接读取数据
 * @param data 数据存储数组
 * @return 转换后的浮点电压值
 * @note 使用直接读取模式获取转换数据并转换为电压值
 */
float ReadDataDirect(uint8_t data[]);

/**
 * @brief 命令模式读取数据
 * @param data 数据存储数组
 * @note 使用命令读取模式获取转换数据
 */
void ReadDataCommand(uint8_t data[]);

/**
 * @brief 数据转换函数
 * @param chn 通道ID
 * @param data 原始数据数组
 * @return 转换后的物理量值
 * @note 根据通道类型（电压、温度等）将原始数据转换为物理量
 */
float DataConvert(uint8_t chn, uint8_t data[]);

/* 寄存器操作函数 */
/**
 * @brief 读取单个寄存器
 * @param address 寄存器地址
 * @return 寄存器值
 * @note 从指定地址读取单个寄存器的值
 */
uint8_t readSingleRegister(uint8_t address);

/**
 * @brief 读取多个寄存器
 * @param startAddress 起始地址
 * @param count 读取数量
 * @note 连续读取多个寄存器的值
 */
void readMultipleRegisters(uint8_t startAddress, uint8_t count);

/**
 * @brief 写入单个寄存器
 * @param address 寄存器地址
 * @param data 要写入的数据
 * @note 向指定地址写入单个寄存器的值
 */
void writeSingleRegister(uint8_t address, uint8_t data);

/**
 * @brief 写入多个寄存器
 * @param startAddress 起始地址
 * @param count 写入数量
 * @param regData 要写入的数据数组
 * @note 连续写入多个寄存器的值
 */
void writeMultipleRegisters(uint8_t startAddress, uint8_t count, uint8_t regData[]);

/**
 * @brief 恢复寄存器默认值
 * @note 将所有寄存器恢复为默认值
 */
void restoreRegisterDefaults(void);

/**
 * @brief 获取寄存器值
 * @param address 寄存器地址
 * @return 寄存器当前值
 * @note 获取缓存的寄存器值（不进行实际读取）
 */
uint8_t getRegisterValue(uint8_t address);

/* 转换控制函数 */
/**
 * @brief 发送命令
 * @param op_code 操作码
 * @note 向ADS1258发送指定的命令
 */
void sendCommand(uint8_t op_code);

/**
 * @brief 启动转换
 * @note 启动ADS1258的连续转换模式
 */
void startConversions(void);

/**
 * @brief 停止转换
 * @note 停止ADS1258的连续转换模式
 */
void stopConversions(void);

/******************************************************************************
 * 宏定义
 ******************************************************************************/

/**
 * @brief 检查MUXMOD位是否设置
 * @return true=已设置（固定通道模式），false=未设置（自动扫描模式）
 */
#define IS_MUXMOD_SET       ((bool)(getRegisterValue(REG_ADDR_CONFIG0) & CONFIG0_MUXMOD_MASK))

/**
 * @brief 检查STAT位是否设置
 * @return true=已设置（读取数据时包含状态字节），false=未设置
 */
#define IS_STAT_SET         ((bool)(getRegisterValue(REG_ADDR_CONFIG0) & CONFIG0_STAT_MASK))

#endif /* ADS1258_H_ */
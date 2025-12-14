#ifndef __TLC5940_H
#define __TLC5940_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"

/* TLC5940 配置参数 */
#define CHANNEL_NUM           16     // TLC5940 通道数量
#define GS_LEN                24     // 灰度控制数据长度 (16通道 * 12位 / 8 = 24字节)
#define DC_LEN                12     // 点校正数据长度 (16通道 * 6位 / 8 = 12字节)
#define MAX_TLC_LEN           72     // 最大数据传输长度 (GS_LEN * 2 + DC_LEN * 2)



#define GPIO_ON  			GPIO_PIN_SET
#define GPIO_OFF 			GPIO_PIN_RESET

/* GPIO 控制宏定义 */
#define SETBLANK(x)           HAL_GPIO_WritePin(BLANK_GPIO_Port, BLANK_Pin, x)
#define SETXLAT(x)            HAL_GPIO_WritePin(XLAT_GPIO_Port, XLAT_Pin, x)
#define SETVPRG(x)            HAL_GPIO_WritePin(VRPG_GPIO_Port, VRPG_Pin, x)

/* TLC5940 控制结构体 */
typedef struct {
  SPI_HandleTypeDef* tlcspi;          // SPI 句柄
  TIM_HandleTypeDef* gsclk;           // GSCLK 定时器句柄
  TIM_HandleTypeDef* tlctim;          // TLC 控制定时器句柄
  uint32_t tim_chn;                   // 定时器通道
  uint16_t red_led;                    // 红光LED电流设置
  uint8_t ir_led;                     // 红外LED电流设置
  uint8_t freq;                       // 刷新频率
  uint8_t write_data[MAX_TLC_LEN];    // 写入数据缓冲区
  uint16_t red_gs_ctrl[CHANNEL_NUM];  // 红光灰度控制值
  uint8_t red_dc_ctrl[CHANNEL_NUM];   // 红光电校正值
  uint16_t ir_gs_ctrl[CHANNEL_NUM];   // 红外灰度控制值
  uint8_t ir_dc_ctrl[CHANNEL_NUM];    // 红外点校正值
  uint32_t tlctim_polarity;           // 定时器输入捕获边沿
} TLC_TYPEDEF;

extern TLC_TYPEDEF g_tlc;

/* 函数声明 */
void tlc5940_init(void);
void writeTLC(uint8_t* data, uint8_t len);
void tlcSetDC(uint8_t red, uint8_t ir);
void tlcSetGS(uint8_t chn, uint16_t value, uint8_t red_ir, uint8_t on_off);
void closeLED(void);
void resetTLC(void);
void tlcSetChn(uint16_t *chn, uint8_t len);
void tlc_set_frequency(uint16_t frequency);

#ifdef __cplusplus
}
#endif

#endif


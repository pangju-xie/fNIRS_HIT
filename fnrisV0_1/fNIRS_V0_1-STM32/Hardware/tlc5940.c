#include "main.h"
#include "spi.h"
#include "tlc5940.h"
#include "tim.h"
#include <string.h>
#include "utils.h"

/* 全局 TLC5940 控制结构体 */
TLC_TYPEDEF g_tlc;

/**
  * @brief  初始化 TLC5940 结构体
  * @note   设置默认参数并清零所有缓冲区
  */
void init_tlc_struct(void) {
  g_tlc.tlcspi = &hspi1;
  g_tlc.gsclk = &htim1;
  g_tlc.tlctim = &htim4;
  g_tlc.tim_chn = TIM_CHANNEL_1;
  g_tlc.freq = 10;           // 默认频率 10Hz
  g_tlc.red_led = 0x0fff;       // 红光LED电流 120mA
  g_tlc.ir_led  = 0x3f;        // 红外LED电流 60mA
  g_tlc.tlctim_polarity = TIM_INPUTCHANNELPOLARITY_RISING;  //默认优先上升沿捕获
  
  
  // 清零所有数据缓冲区
  memset(g_tlc.write_data, 0, MAX_TLC_LEN);
  memset(g_tlc.red_gs_ctrl, 0, sizeof(g_tlc.red_gs_ctrl));
  memset(g_tlc.red_dc_ctrl, 0, sizeof(g_tlc.red_dc_ctrl));
  memset(g_tlc.ir_gs_ctrl, 0, sizeof(g_tlc.ir_gs_ctrl));
  memset(g_tlc.ir_dc_ctrl, 0, sizeof(g_tlc.ir_dc_ctrl));
}

/**
  * @brief  TLC5940 初始化函数
  * @note   初始化结构体并重置芯片
  */
void tlc5940_init(void) {
  init_tlc_struct();
  
   // 确保所有控制信号初始状态正确
  SETVPRG(GPIO_OFF);   // 灰度控制模式
  SETXLAT(GPIO_OFF);   // XLAT初始为低
  SETBLANK(GPIO_ON); // 初始关闭输出
  
  HAL_TIM_Base_Start_IT(&htim2);
  __HAL_TIM_SET_AUTORELOAD(g_tlc.gsclk,1000-1);
  __HAL_TIM_SET_PRESCALER(g_tlc.gsclk, 1250-1);
  HAL_TIM_PWM_Start(g_tlc.gsclk, g_tlc.tim_chn);
  // 短暂延时确保芯片稳定
  HAL_Delay(10);
  
  tlcSetGS(0, g_tlc.red_led, 0, 0);
  HAL_Delay(10);
  // 设置点校正（重要！）
  tlcSetDC(g_tlc.ir_led, g_tlc.ir_led);  // 设置适当的点校正值，不要用最大值63
  HAL_Delay(10);
  // 最后开启输出
  //SETBLANK(GPIO_OFF);
}

/**
  * @brief  设置 TLC5940 刷新频率
  * @param  frequency: 目标频率 (Hz)
  */
void tlc_set_frequency(uint16_t frequency) {
  if (frequency == 0) return; // 防止除零错误
  
  g_tlc.freq = frequency;
  uint16_t set_value = 40000 / frequency - 1;
  __HAL_TIM_SET_PRESCALER(g_tlc.tlctim, set_value);
}

/**
  * @brief  向 TLC5940 写入数据
  * @param  data: 要写入的数据指针
  * @param  len: 数据长度
  */
void writeTLC(uint8_t* data, uint8_t len) {
  uint8_t RxData[MAX_TLC_LEN] = {0};
  
  // 2. 确保BLANK为高（关闭输出）
  SETBLANK(GPIO_ON); 
  
  // SPI 传输数据
  HAL_SPI_TransmitReceive(g_tlc.tlcspi, data, RxData, len, 1000);
  
  // 4. 产生XLAT脉冲锁存数据
  SETXLAT(GPIO_OFF);
  Delay_us(2);  // 短暂延时
  SETXLAT(GPIO_ON);
  Delay_us(2);  // 短暂延时  
  SETXLAT(GPIO_OFF);
  Delay_us(2);  // 短暂延时  
  
  SETBLANK(GPIO_OFF);  // 恢复各通道控制
 
}

/**
  * @brief  设置所有通道的点校正值
  * @param  red: 红光点校正值 (0-63)
  * @param  ir: 红外点校正值 (0-63)
  */
void tlcSetDC(uint8_t red, uint8_t ir) {
  // 设置点校正模式
  SETVPRG(GPIO_ON);
  
  // 限制数值范围
  red = red & 0x3F;
  ir = ir & 0x3F;
  
  // 设置所有通道的点校正值
  memset(g_tlc.red_dc_ctrl, red, sizeof(g_tlc.red_dc_ctrl));
  memset(g_tlc.ir_dc_ctrl, ir, sizeof(g_tlc.ir_dc_ctrl));
  memset(g_tlc.write_data, 0, DC_LEN * 2);
  
  // 打包红光点校正数据 (6位/通道 -> 字节数组)
  for (int i = 0; i < 4; i++) {
    g_tlc.write_data[i * 3 + 0] = g_tlc.red_dc_ctrl[i * 4 + 0] << 2 | g_tlc.red_dc_ctrl[i * 4 + 1] >> 4;
    g_tlc.write_data[i * 3 + 1] = g_tlc.red_dc_ctrl[i * 4 + 1] << 4 | g_tlc.red_dc_ctrl[i * 4 + 2] >> 2;
    g_tlc.write_data[i * 3 + 2] = g_tlc.red_dc_ctrl[i * 4 + 2] << 6 | g_tlc.red_dc_ctrl[i * 4 + 3];
  }
  
  // 打包红外点校正数据
  for (int i = 0; i < 4; i++) {
    g_tlc.write_data[i * 3 + DC_LEN + 0] = g_tlc.ir_dc_ctrl[i * 4 + 0] << 2 | g_tlc.ir_dc_ctrl[i * 4 + 1] >> 4;
    g_tlc.write_data[i * 3 + DC_LEN + 1] = g_tlc.ir_dc_ctrl[i * 4 + 1] << 4 | g_tlc.ir_dc_ctrl[i * 4 + 2] >> 2;
    g_tlc.write_data[i * 3 + DC_LEN + 2] = g_tlc.ir_dc_ctrl[i * 4 + 2] << 6 | g_tlc.ir_dc_ctrl[i * 4 + 3];
  }
  
  // 写入点校正数据
  writeTLC(g_tlc.write_data, DC_LEN * 2);
  
  // 切换回灰度控制模式
  SETVPRG(GPIO_OFF);
}

/**
  * @brief  设置指定通道的灰度值
  * @param  chn: 通道号 (0-15)
  * @param  value: 灰度值 (0-4095)
  * @param  red_ir: 0-红外, 1-红光
  * @param  on_off: 0-关闭, 1-开启
  */
void tlcSetGS(uint8_t chn, uint16_t value, uint8_t red_ir, uint8_t on_off) {
  // 限制数值范围
  value = value & 0x0FFF;
  
  // 清零写入缓冲区
  memset(g_tlc.write_data, 0, GS_LEN * 2);
  
  // 通道号转换 (TLC5940 数据顺序为通道15到0)
  chn = 15 - chn;
  
  if (on_off == 1) {
    // 计算数据位置并设置灰度值
    if ((chn & 1) == 0) {
      // 偶数通道: 占用3字节中的前1.5字节
      g_tlc.write_data[(chn >> 1) * 3 + 0 + red_ir * GS_LEN] |= (uint8_t)((value >> 4) & 0xFF);
      g_tlc.write_data[(chn >> 1) * 3 + 1 + red_ir * GS_LEN] |= (uint8_t)((value & 0x000F) << 4);
    } else {
      // 奇数通道: 占用3字节中的后1.5字节
      g_tlc.write_data[(chn >> 1) * 3 + 1 + red_ir * GS_LEN] |= (uint8_t)((value >> 8) & 0x0F);
      g_tlc.write_data[(chn >> 1) * 3 + 2 + red_ir * GS_LEN] |= (uint8_t)(value & 0xFF);
    }
  }
  
  // 写入灰度数据
  writeTLC(g_tlc.write_data, GS_LEN * 2);
}

/**
  * @brief  设置多个通道的灰度值
  * @param  chn: 通道灰度值数组
  * @param  len: 数组长度
  * @note   此函数需要进一步测试和完善
  */
void tlcSetChn(uint16_t *chn, uint8_t len) {
  // 注意: 此函数逻辑需要验证，目前可能存在问题
  memset(g_tlc.write_data, 0, GS_LEN * 2);
  uint32_t data[16] = {0};
  
  // 数据重组逻辑
  for (int i = 15; i >= 0; i--) {
    data[15 - i] |= g_tlc.write_data[i * 2 + 1] << 12;
    data[15 - i] |= g_tlc.write_data[i * 2] & 0x0FFF;
  }
  
  // 打包为24字节数据
  for (uint8_t i = 0; i < 16; i++) {
    g_tlc.write_data[i * 3] = (uint8_t)(data[i] >> 16);
    g_tlc.write_data[i * 3 + 1] = (uint8_t)(data[i] >> 8);
    g_tlc.write_data[i * 3 + 2] = (uint8_t)(data[i]);
  }
  
  writeTLC(g_tlc.write_data, GS_LEN * 2);
}

/**
  * @brief  关闭所有LED
  */
void closeLED(void) {
  tlcSetGS(0, 0, 0, 0);
}

/**
  * @brief  重置 TLC5940
  * @note   关闭所有通道并设置默认点校正值
  */
void resetTLC(void) {
  tlcSetGS(0, 0, 0, 1);  // 关闭所有灰度输出
  tlcSetDC(31, 31);      // 设置最大点校正值
}


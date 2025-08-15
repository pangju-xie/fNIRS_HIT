/**********************************************************************
Copyright : Xie Fawen. 2025. All rights reserved.
文件名			: IS31FL.h
作者	  	: 谢发文<823767544@qq.com>
版本	   	: V1.0
描述	   	: IS31FL数码管驱动芯片头文件
其他	   	: 无
日志	   	: 初版V1.0 2025/2/27 谢发文创建
***********************************************************************/
#ifndef __IS31FL_H
#define __IS31FL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

#define IS31FL_I2C								(hi2c2)		

#define IS31FL_ADDR								(0x78)								//芯片从机地址，只支持写操作0x7A 0x7C 0X7E
#define LED_CHN_NUM								(36)									//共有36路寄存器

#define REGADDR_SHUTDOWN					(0x00)								//关机指令寄存器
#define REGADDR_PWN_START					(0x01)								//PWM调整指令寄存器
#define REGADDR_PWM_UPDATE				(0x25)								//更新PWM指令值和LED控制指令值的寄存器，需要通过向该寄存器写入地址进行更新
#define REGADDR_LED_CTRL					(0x26)								//LED控制指令寄存器
#define REGADDR_LED_G_CTRL				(0x4A)								//LED全局控制指令寄存器
#define REGADDR_FOUT_SET					(0x4B)								//调整输出频率寄存器
#define REGADDR_RESET							(0x4F)								//重启指令寄存器

//reg0：关机控制指令
#define SSD_SD										(0x00)								//软件层面芯片关机
#define SSD_NRM										(0x01)								//芯片正常工作模式

//reg1-reg36:PWM配置指令
/*指令值范围在0-255，用于调整LED光强，36通道LED单独控制*/

//reg37:PWM调整指令
/*PWM配置指令跟LED控制指令的值会存放在临时寄存器上，需要通过PWM更新指令进行更新
该指令范围就是1-36和38-37，即PWM调整指令和LED控制指令的寄存器地址*/

//reg38-73:LED控制指令
#define CUR_I_DIV_1								(0x00<<1)							//输出电流为最大电流/1
#define CUR_I_DIV_2								(0x01<<1)							//输出电流为最大电流/2
#define CUR_I_DIV_3								(0x02<<1)							//输出电流为最大电流/3
#define CUR_I_DIV_4								(0x033<<1)							//输出电流为最大电流/4

#define LED_STATE_OFF							(0x00)							//关闭通道LED
#define LED_STATE_ON							(0x01)							//开启通道LED

//reg74:LED全局控制
#define LEG_G_NRM									(0x00)								//所有通道正常配置
#define LEG_G_SD 									(0x01)								//所有通道全关闭

//reg75:LED输出频率控制
#define FOUT_3K										(0x00)								//LED输出频率为3kHz
#define FOUT_22K									(0x01)								//LED输出频率为22kHz


#define DISABLE_IS31FL()					HAL_GPIO_WritePin(SDB_GPIO_Port, SDB_Pin,GPIO_PIN_RESET)
#define ENABLE_IS31FL()						HAL_GPIO_WritePin(SDB_GPIO_Port, SDB_Pin,GPIO_PIN_SET)
/********************************************
	* @description		:IS31FL写入多字节
	* @param	 REGAddr:写入寄存器地址
	* @param	 Val    :写入寄存器数组
	* @param	 len    :写入寄存器数组长度
	* @return					:
********************************************/
void LEDWriteMultiData(uint8_t REGAddr, uint8_t* Val, uint8_t len);


void SetLED_ALL(uint8_t on);										//配置所有led开关
void SetPWM_ALL(uint8_t pwm);										//配置所有光强度，为0-255
void SetIR(uint8_t chn, uint8_t on);						//开关IR灯
void SetRED(uint8_t chn, uint8_t on);						//开关RED灯
void SwitchSameLED(uint8_t chn);								//切换RED/IR灯
void SwitchDiffLED(uint8_t chn1, uint8_t chn2);	//切换IR/RED灯
void SwitchLEDLight(void);


/********************************************
	* @description		:IS31FL初始化
	* @param					:
	* @return					:
********************************************/
void LED_Init(void);

/********************************************
	* @description		:IS31FL关机指令
	* @param			 val:关机->SSD_SD, 正常工作->SSD_NRM
	* @return					:
********************************************/
void LED_ShutDown(uint8_t val);

/********************************************
	* @description		:IS31FL复位指令
	* @param					:
	* @return					:
********************************************/
void LED_Reset(void);

/********************************************
	* @description		:IS31FL全局控制LED指令
	* @param			 val:全关->LEG_G_SD, 正常工作->LEG_G_NRM
	* @return					:
********************************************/
void LED_GControl(uint8_t val);

/********************************************
	* @description		:IS31FL寄存器更新指令
	* @param			 		:
	* @return					:
********************************************/
void LED_Update(void);

/********************************************
	* @description		:IS31FL配置PWM指令
	* @param			 chn:配置的通道数->0-35
	* @param			 val:配置PWM值->0-255
	* @return					:
********************************************/
void LED_PWM_Config(uint8_t chn, uint8_t val);

/********************************************
	* @description		:IS31FL配置LED指令
	* @param			 chn:配置的通道数->0-35
	* @param			 val:配置电流大小-> 0-3
	* @param		 state:配置的LED状态：关闭：LED_STATE_OFF，开启：LED_STATE_ON
	* @return					:
********************************************/
void LED_Control(uint8_t chn, uint8_t cur, uint8_t state);

/********************************************
	* @description		:IS31FL调整输出频率指令
	* @param			 val:FOUT_3K /  FOUT_22K
	* @return					:
********************************************/
void LED_OFS(uint8_t val);

/********************************************
	* @description		:IS31FL测试例程
	* @param					:
	* @return					:
********************************************/
void LED_Test(void);


#ifdef __cplusplus
}
#endif

#endif

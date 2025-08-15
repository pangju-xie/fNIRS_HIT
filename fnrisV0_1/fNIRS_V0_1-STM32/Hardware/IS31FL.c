/**********************************************************************
Copyright : Xie Fawen. 2025. All rights reserved.
文件名			: IS31FL.c
作者	  	: 谢发文<823767544@qq.com>
版本	   	: V1.0
描述	   	: IS31FL数码管驱动芯片库文件
其他	   	: 无
日志	   	: 初版V1.0 2025/2/27 谢发文创建
***********************************************************************/
#include "IS31FL.h"
#include "i2c.h"
#include "string.h"
#include "utils.h"
//#include "myiic.h"

HAL_StatusTypeDef s1 = HAL_OK;
const uint8_t gamma_pwm[32] = {0, 1, 2, 4, 6, 10, 13, 18,	
															 22, 28, 33, 39, 46, 53, 61, 69,
															 78, 86, 96, 106, 116, 126, 138, 149,
															 161, 173, 186, 199, 212, 226, 240, 255};
///********************************************
//	* @description		:IS31FL测试例程
//	* @param					:
//	* @return					:
//********************************************/
//void LED_Test(void){
//	uint8_t led_num2 = 35, led_num1 = 0;
//	uint8_t pwm_buf[36] = {0};
//	uint8_t led_buf[36] = {0};
////	IIC_Init();
//	HAL_Delay(10);
//	LED_Reset();
//	HAL_Delay(10);
//	HAL_GPIO_WritePin(SDB_GPIO_Port, SDB_Pin,GPIO_PIN_SET);
//	HAL_Delay(10);
//	LED_ShutDown(SSD_NRM);
//	LED_OFS(FOUT_22K);
//	LED_GControl(LEG_G_NRM);
//	LED_Update();
//	HAL_Delay(10);
////	uint8_t light = 0;
////	uint8_t flag = 255;
//	memset(pwm_buf, 10, sizeof(pwm_buf));
//	memset(led_buf, (CUR_I_DIV_1|LED_STATE_OFF), 36);
//	LEDWriteMultiData(REGADDR_PWN_START, pwm_buf, 36);
//	LEDWriteMultiData(REGADDR_LED_CTRL, led_buf, 36);
////	for(uint8_t i=0;i<LED_CHN_NUM;i++){
////		LED_PWM_Config(i, 255);
////		LED_Control(i, CUR_I_DIV_1, LED_STATE_OFF);
////	}
//	LED_Update();
//	HAL_Delay(100);
//	while(1){
//		for(uint8_t i = 0; i<32;i++){
//			memset(pwm_buf, gamma_pwm[i], sizeof(pwm_buf));
//			LEDWriteMultiData(REGADDR_PWN_START, pwm_buf, 36);
//			LED_Update();
//			for(uint8_t i = 0; i<36;i++){
////			memset(pwm_buf, gamma_pwm[i], sizeof(pwm_buf));
////			LEDWriteMultiData(REGADDR_PWN_START, pwm_buf, 36);
//				LED_Control(i, CUR_I_DIV_1, LED_STATE_ON);
//				LED_Update();
//				HAL_Delay(2);
//				LED_Control(i, CUR_I_DIV_1, LED_STATE_OFF);
//				LED_Update();
//				HAL_Delay(2);
//			}
//		}
//	}
//	
//}

void SetLED_ALL(uint8_t on){
	uint8_t buf[36] = {0};
	memset(buf, (CUR_I_DIV_1|on), 36);
	LEDWriteMultiData(REGADDR_LED_CTRL, buf, 36);
	LED_Update();
}
//配置所有光强度，为0-255
void SetPWM_ALL(uint8_t pwm){
	uint8_t buf[36] = {0};
	memset(buf, pwm, 36);
	LEDWriteMultiData(REGADDR_PWN_START, buf, 36);
	LED_Update();
}

//开关IR灯
void SetIR(uint8_t chn, uint8_t on){
	LED_Control(chn*2+1, CUR_I_DIV_1, on);
}

//开关LED灯
void SetRED(uint8_t chn, uint8_t on){
	LED_Control(chn*2, CUR_I_DIV_1, on);
}

void SwitchSameLED(uint8_t chn){
	SetRED(chn, LED_STATE_OFF);
	SetIR(chn, LED_STATE_ON);
	LED_Update();
}

void SwitchDiffLED(uint8_t chn1, uint8_t chn2){
	SetIR(chn1, LED_STATE_OFF);
	SetRED(chn2, LED_STATE_ON);
	LED_Update();
}
/********************************************
	* @description		:IS31FL初始化
	* @param					:
	* @return					:
********************************************/
void LED_Init(void){
	LED_Reset();
	HAL_Delay(10);
	ENABLE_IS31FL();
	HAL_Delay(10);
	LED_ShutDown(SSD_NRM);
	LED_OFS(FOUT_22K);
	LED_GControl(LEG_G_NRM);
	//LED_Update();
	HAL_Delay(10);
	
	SetPWM_ALL(255);
	SetLED_ALL(LED_STATE_OFF);
}

void SwitchLEDLight(void){
  for(uint8_t i = 0; i<32;i++){
    SetPWM_ALL(gamma_pwm[i]);
    HAL_Delay(500);
  }
}

/********************************************
	* @description		:IS31FL写入单字节
	* @param	 REGAddr:写入寄存器地址
	* @param	 Val    :写入寄存器值
	* @return					:
********************************************/
void LEDWriteOneData(uint8_t REGAddr, uint8_t Val){
//	IIC_Write_One_Byte(IS31FL_ADDR, REGAddr, Val);
	HAL_StatusTypeDef ret = HAL_OK;
	ret = HAL_I2C_Mem_Write(&IS31FL_I2C, IS31FL_ADDR, REGAddr, I2C_MEMADD_SIZE_8BIT, &Val, 1, 0xff);
	if(HAL_OK != ret){
		printf("Data Transmit error: %d\r\n;", ret);
		HAL_Delay(10);
		//Error_Handler();
	}
}

/********************************************
	* @description		:IS31FL写入多字节
	* @param	 REGAddr:写入寄存器地址
	* @param	 Val    :写入寄存器数组
	* @param	 len    :写入寄存器数组长度
	* @return					:
********************************************/
void LEDWriteMultiData(uint8_t REGAddr, uint8_t* Val, uint8_t len){
	HAL_StatusTypeDef ret = HAL_OK;
	ret = HAL_I2C_Mem_Write(&IS31FL_I2C, IS31FL_ADDR, REGAddr, I2C_MEMADD_SIZE_8BIT, Val, len, 0xff);
	if(HAL_OK != ret){
		printf("Data Multi Transmit error: %d\r\n;", ret);
		HAL_Delay(10);
		//Error_Handler();
	}

}

/********************************************
	* @description		:IS31FL关机指令
	* @param			 val:关机->SSD_SD, 正常工作->SSD_NRM
	* @return					:
********************************************/
void LED_ShutDown(uint8_t val){
	LEDWriteOneData(REGADDR_SHUTDOWN, val&0x01);
}

/********************************************
	* @description		:IS31FL复位指令
	* @param					:
	* @return					:
********************************************/
void LED_Reset(void){
	LEDWriteOneData(REGADDR_RESET, 0);
}

/********************************************
	* @description		:IS31FL全局控制LED指令
	* @param			 val:全关->LEG_G_SD, 正常工作->LEG_G_NRM
	* @return					:
********************************************/
void LED_GControl(uint8_t val){
	LEDWriteOneData(REGADDR_LED_G_CTRL, val&0x01);
}

/********************************************
	* @description		:IS31FL寄存器更新指令
	* @param			 		:
	* @return					:
********************************************/
void LED_Update(void){
	LEDWriteOneData(REGADDR_PWM_UPDATE, 0);
}

/********************************************
	* @description		:IS31FL配置PWM指令
	* @param			 chn:配置的通道数->0-35
	* @param			 val:配置PWM值->0-255
	* @return					:
********************************************/
void LED_PWM_Config(uint8_t chn, uint8_t val){
	LEDWriteOneData(REGADDR_PWN_START+chn, val);
	//LED_Update();
}

/********************************************
	* @description		:IS31FL配置LED指令
	* @param			 chn:配置的通道数->0-35
	* @param			 val:配置电流大小-> 0-3
	* @param		 state:配置的LED状态：关闭：LED_STATE_OFF，开启：LED_STATE_ON
	* @return					:
********************************************/
void LED_Control(uint8_t chn, uint8_t cur, uint8_t state){
	LEDWriteOneData(REGADDR_LED_CTRL+chn, (cur|state));
	//LED_Update();
}

/********************************************
	* @description		:IS31FL调整输出频率指令
	* @param			 val:FOUT_3K /  FOUT_22K
	* @return					:
********************************************/
void LED_OFS(uint8_t val){
	LEDWriteOneData(REGADDR_FOUT_SET, val&0x01);
}




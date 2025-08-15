/**********************************************************************
Copyright : Xie Fawen. 2025. All rights reserved.
�ļ���			: IS31FL.c
����	  	: л����<823767544@qq.com>
�汾	   	: V1.0
����	   	: IS31FL���������оƬ���ļ�
����	   	: ��
��־	   	: ����V1.0 2025/2/27 л���Ĵ���
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
//	* @description		:IS31FL��������
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
//�������й�ǿ�ȣ�Ϊ0-255
void SetPWM_ALL(uint8_t pwm){
	uint8_t buf[36] = {0};
	memset(buf, pwm, 36);
	LEDWriteMultiData(REGADDR_PWN_START, buf, 36);
	LED_Update();
}

//����IR��
void SetIR(uint8_t chn, uint8_t on){
	LED_Control(chn*2+1, CUR_I_DIV_1, on);
}

//����LED��
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
	* @description		:IS31FL��ʼ��
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
	* @description		:IS31FLд�뵥�ֽ�
	* @param	 REGAddr:д��Ĵ�����ַ
	* @param	 Val    :д��Ĵ���ֵ
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
	* @description		:IS31FLд����ֽ�
	* @param	 REGAddr:д��Ĵ�����ַ
	* @param	 Val    :д��Ĵ�������
	* @param	 len    :д��Ĵ������鳤��
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
	* @description		:IS31FL�ػ�ָ��
	* @param			 val:�ػ�->SSD_SD, ��������->SSD_NRM
	* @return					:
********************************************/
void LED_ShutDown(uint8_t val){
	LEDWriteOneData(REGADDR_SHUTDOWN, val&0x01);
}

/********************************************
	* @description		:IS31FL��λָ��
	* @param					:
	* @return					:
********************************************/
void LED_Reset(void){
	LEDWriteOneData(REGADDR_RESET, 0);
}

/********************************************
	* @description		:IS31FLȫ�ֿ���LEDָ��
	* @param			 val:ȫ��->LEG_G_SD, ��������->LEG_G_NRM
	* @return					:
********************************************/
void LED_GControl(uint8_t val){
	LEDWriteOneData(REGADDR_LED_G_CTRL, val&0x01);
}

/********************************************
	* @description		:IS31FL�Ĵ�������ָ��
	* @param			 		:
	* @return					:
********************************************/
void LED_Update(void){
	LEDWriteOneData(REGADDR_PWM_UPDATE, 0);
}

/********************************************
	* @description		:IS31FL����PWMָ��
	* @param			 chn:���õ�ͨ����->0-35
	* @param			 val:����PWMֵ->0-255
	* @return					:
********************************************/
void LED_PWM_Config(uint8_t chn, uint8_t val){
	LEDWriteOneData(REGADDR_PWN_START+chn, val);
	//LED_Update();
}

/********************************************
	* @description		:IS31FL����LEDָ��
	* @param			 chn:���õ�ͨ����->0-35
	* @param			 val:���õ�����С-> 0-3
	* @param		 state:���õ�LED״̬���رգ�LED_STATE_OFF��������LED_STATE_ON
	* @return					:
********************************************/
void LED_Control(uint8_t chn, uint8_t cur, uint8_t state){
	LEDWriteOneData(REGADDR_LED_CTRL+chn, (cur|state));
	//LED_Update();
}

/********************************************
	* @description		:IS31FL�������Ƶ��ָ��
	* @param			 val:FOUT_3K /  FOUT_22K
	* @return					:
********************************************/
void LED_OFS(uint8_t val){
	LEDWriteOneData(REGADDR_FOUT_SET, val&0x01);
}




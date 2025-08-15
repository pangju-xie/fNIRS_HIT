/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
文件名		: key.h
作者	  	: 谢发文<823767544@qq.com>
版本	   	: V1.0
描述	   	: 按键功能头文件
其他	   	: 无
日志	   	: 初版V1.0 2024/8/10 谢发文创建
***********************************************************************/
#include "Key.h"
#include "led.h"
#include "stdio.h"
#include "utils.h"

uint8_t key_return = NON_KEY;

#define LONG_PRESS_CNT 100
#define TWICE_PRESS_CNT 20

/**
  * @brief  KEY_Scan();// 按键检测
  * @note   按键检测，返回单击，双击，长按
  * @param  无
  * @retval 无
	PS:key_return属于外部全局变量，用于接受反馈信息
  */	
uint8_t KEY_Scan(void)
{
	//反馈系统
	static uint8_t  Click_Buf = FALSE;  	//第一次弹起标志，用与区分双击的第一次按下和第二次按下
	static uint8_t  KEY_flag= FALSE;		//标志触发判断标志位，用于在反馈结束后统一清零
	static uint8_t  Click   = FALSE;		//单击判断标志位
	static uint8_t  Long_Press = FALSE; 	//长按判断标志位
	static uint8_t  Double_Click  = FALSE;	//双击判断标志位
	 
	static uint8_t key_state = KEY_Up;
	
	//计时系统
	//定时器10ms进入一次函数
	static uint8_t  Long_Cnt = LONG_PRESS_CNT;//长按计时时长1s
	static uint8_t  Twice_Cnt = TWICE_PRESS_CNT;//双击间隔计时时长200ms
	Long_Cnt--;
	Twice_Cnt--;
	
	//状态系统
	switch(key_state)
	{
		/*状态1：空闲状态（单击）和按键弹起后（双击）*/
		case KEY_Up:
		{	
			if(ReadKey() == 0){
				key_state = KEY_Down;//切换到状态3
				Long_Cnt = LONG_PRESS_CNT;//长按计时开始
			}
			else{
				//判断是否为按键弹起状态
				if(Click_Buf == TRUE){
					//弹起时间超过200ms,双击判定时间失效，且一定不为长按，直接判断为单击
					if(Twice_Cnt<=0){
						KEY_flag = TRUE;
						Click = TRUE;
					}
				}
			}
			break;
		}
    /*状态3：按键按下到长按标志触发状态*/
		case KEY_Down:
    {
      if(ReadKey() == 1){
        key_state = KEY_Up;//切换到状态4
        //不是长按操作，则判断是不是双击操作
        if(Long_Press == FALSE){
          //双击检测
          //前面已经单击一次，这次就判断为双击操作
          if(Click_Buf == TRUE){
			KEY_flag = TRUE;
			Double_Click  = TRUE;
          }
          else{
            //这是单击或双击的第一次点击，标志位置1
            Click_Buf = TRUE;
            //双击计时器开始计时
			Twice_Cnt = TWICE_PRESS_CNT;
          } 
        }
      }
      else{
        //长按检测（一直在按下，第一次弹起不会触发）
        if(Long_Press == FALSE&&Click_Buf == FALSE){
			//1s时间到就判断为长按
			if(Long_Cnt<=0){
				key_state = KEY_wait;//切换到状态4
				KEY_flag = TRUE;
				Long_Press = TRUE;
			}
        }
      }  
      break;  
    }
    
    /*状态4：标志触发到等待按键弹起状态*/
    case KEY_wait:
    {
      if(ReadKey() == 1)
        key_state = KEY_Up;//完成一次按键动作,切换到状态1
      break;
    }
		
    default:
      key_state = KEY_Up;//默认情况都切换到状态1
      break;
  }
	
	//标志触发，反馈结果
	//PS:key_return属于外部全局变量，用于接受反馈信息
	if(KEY_flag == TRUE)
	{
	//	static uint16_t HZ = 1000;
		//单击动作，工作模式
		if(Click == TRUE){
			key_return = SHORT_KEY;
			/*single click function start*/
			DebugPrintf("single click.\r\n");
			/*single click function end*/
		}
		//长按动作，关机
		else if(Long_Press == TRUE){
			key_return = LONG_KEY;
			/*long time click function start*/
			DebugPrintf("long time click, switch off.\r\n");
			SetLED('o');
			SetKey(LEDOFF);
			/*long time click function end*/
			
		}
		//双击动作，配网模式
		else if(Double_Click == TRUE){
			key_return = DOUBLE_CLICK;
			/*double click function start*/
			DebugPrintf("double click.");
			/*double click function end*/
		}
		//按键状态位清零，为下一次按下准备
		KEY_flag= FALSE;
		Click_Buf = FALSE;
		Click = FALSE;
		Long_Press = FALSE;
		Double_Click  = FALSE;
	}
	return key_state==KEY_Up?0:1;
}


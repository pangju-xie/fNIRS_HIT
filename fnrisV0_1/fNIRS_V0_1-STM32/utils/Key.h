/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
文件名		: key.h
作者	  	: 谢发文<823767544@qq.com>
版本	   	: V1.1
描述	   	: 按键功能头文件
其他	   	: 无
日志	   	: 初版V1.0 2024/8/10 谢发文创建
***********************************************************************/
#ifndef __KEY__H
#define __KEY__H

#include "main.h"
#include "utils.h"
#include "stdio.h"

#define KEY_Up  1         //按键弹起
#define KEY_DownShake  2  //按下抖动
#define KEY_Down  3       //按键按下
#define KEY_wait  4       //等待状态

#define NON_KEY 0
#define SHORT_KEY 1       //短按反馈
#define LONG_KEY 2        //长按反馈
#define DOUBLE_CLICK 3    //双击反馈

#define FALSE 0
#define TRUE 1  


extern uint8_t key_return;

/**
  * @brief  KEY_Scan();// 按键检测
  * @note   按键检测，返回单击，双击，长按
  * @param  1按键按下，0按键松开
  * @retval 无
	PS:key_return属于外部全局变量，用于接受反馈信息
  */	
uint8_t KEY_Scan(void);
#endif

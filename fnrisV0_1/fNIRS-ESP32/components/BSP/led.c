#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"

#include <stdio.h>
#include "esp_log.h"
#include "esp_attr.h"  // 包含 IRAM_ATTR 宏
#include "nvs_flash.h"
#include "led.h"

static char* TAG = "LED";

static char cur_chr = 'o';
static char pre_chr = 'o';

static xQueueHandle gpio_evt_queue = NULL;					//按键中断序列

static void IRAM_ATTR key_handler(void* arg){
    uint32_t gpio_num = (uint32_t) arg;
    xQueueSendFromISR(gpio_evt_queue, &gpio_num, NULL);
}

static void key_task(void* arg){
	uint32_t io_num;
	bool ret = 0;
	int time_flag = 0;
	while(1){
		if(xQueueReceive(gpio_evt_queue, &io_num, portMAX_DELAY) == pdTRUE){
			if(gpio_get_level(io_num)==0){
				vTaskDelay(10/portTICK_PERIOD_MS);
				time_flag++;
				while(gpio_get_level(io_num)==0){
					vTaskDelay(10/portTICK_PERIOD_MS);
					time_flag++;
					if(time_flag>300){	//按键长按3s
						ret = 1;
						break;
					}
				}
				time_flag = 0;
				if(ret){
					ESP_LOGI(TAG, "按键长按3s。");
					ret = 0;
					led_set('w');	//LED白光
					//清除nvs并重启
					ESP_ERROR_CHECK(nvs_flash_erase());
					ESP_LOGE(TAG, "nvs_flash_erased!\n");
					vTaskDelay(1000 / portTICK_PERIOD_MS);
					esp_restart();
				}
				else{
					ESP_LOGI(TAG, "按键短按。");
				}
			}
			else{
				ESP_LOGI(TAG, "按键松开。");
			}
		}
		vTaskDelay(1/portTICK_PERIOD_MS);
	}
}

void Key_init(void){
	gpio_config_t power_key_conf = {0};

	power_key_conf.intr_type = GPIO_INTR_ANYEDGE;          	/* 失能引脚中断 */
    power_key_conf.mode = GPIO_MODE_INPUT;          		/* 输入输出模式 */
    power_key_conf.pull_up_en = GPIO_PULLUP_ENABLE;       	/* 失能上拉 */
    power_key_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;   	/* 失能下拉 */
    power_key_conf.pin_bit_mask = 1ull << KEY_PIN;       	/* 设置的引脚的位掩码 */
    gpio_config(&power_key_conf); 

	gpio_evt_queue = xQueueCreate(2, sizeof(uint32_t));
    gpio_install_isr_service(0);           							//注册中断函数
    gpio_isr_handler_add(KEY_PIN, key_handler, (void*) KEY_PIN);     //添加中断处理

	xTaskCreate(key_task, "key_task", 2048, NULL, 3, NULL);
}

void led_init(void){
    gpio_config_t gpio_led_conf = {0};

    gpio_led_conf.intr_type = GPIO_INTR_DISABLE;          /* 失能引脚中断 */
    gpio_led_conf.mode = GPIO_MODE_INPUT_OUTPUT;          /* 输入输出模式 */
    gpio_led_conf.pull_up_en = GPIO_PULLUP_DISABLE;       /* 失能上拉 */
    gpio_led_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;   /* 失能下拉 */
    gpio_led_conf.pin_bit_mask = (1ull << LED_R)|(1ull << LED_G)|(1ull << LED_B);       /* 设置的引脚的位掩码 */
    gpio_config(&gpio_led_conf);                          /* 配置GPIO */

	led_set('o');
}

void led_set(char chr){
    switch(chr){
		case 'r':
		case 'R':
			cur_chr = 'r';
			SETLEDR(1);
			SETLEDG(0);
			SETLEDB(0);
			break;
		case 'g':
		case 'G':
			cur_chr = 'g';
			SETLEDR(0);
			SETLEDG(1);
			SETLEDB(0);
			break;
		case 'b':
		case 'B':
			cur_chr = 'b';
			SETLEDR(0);
			SETLEDG(0);
			SETLEDB(1);
			break;
		case 'y':
		case 'Y':
			cur_chr = 'y';
			SETLEDR(1);
			SETLEDG(1);
			SETLEDB(0);
			break;
		case 'c':
		case 'C':
			cur_chr = 'c';
			SETLEDR(0);
			SETLEDG(1);
			SETLEDB(1);
			break;
		case 'p':
		case 'P':
			cur_chr = 'p';
			SETLEDR(1);
			SETLEDG(0);
			SETLEDB(1);
			break;
		case 'w':
		case 'W':
			cur_chr = 'w';
			SETLEDR(1);
			SETLEDG(1);
			SETLEDB(1);
			break;
		case 'o':
		case 'O':
			cur_chr = 'o';
			SETLEDR(0);
			SETLEDG(0);
			SETLEDB(0);
			break;
		default:
			cur_chr = 'o';
			SETLEDR(0);
			SETLEDG(0);
			SETLEDB(0);
			break;
	}
}

void led_toggle(void){
	if(cur_chr!= 'o'){
		pre_chr = cur_chr;
		led_set('o');
	}
	else{
		if(pre_chr=='o'){
			pre_chr = 'w';		//默认白光
		}
		led_set(pre_chr);
	}
}



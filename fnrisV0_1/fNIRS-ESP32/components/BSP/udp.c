#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "lwip/err.h"   
#include "lwip/sockets.h"
#include "lwip/sys.h"

#include <stdio.h>
#include "udp.h"
#include "wifi.h"
#include "led.h"
#include "uart.h"
#include "esp_netif.h"
#include "transmit.h"

static const char* TAG = "UDP_CLIENT";

struct sockaddr_in dest_addr;			//目的端，上位机
struct sockaddr_storage broad_adr;		//上位机广播地址
struct sockaddr_in src_addr;			//源端，从机

uint8_t isPCConnect = 0;
char addr_str[30];

#define UDP_RX_SIZE   1024

int sock=-1;

//安全发送udp数据
ssize_t udp_safe_send(uint8_t *buf, ssize_t len)
{
	ssize_t left = len;
	ssize_t nsend = 0;
	socklen_t destlen = sizeof(dest_addr);
	while (isPCConnect && (0 < left))
	{
		nsend = sendto(sock, buf, left, 0, (struct sockaddr*)&dest_addr, destlen);
		if (0 == nsend)
		{
			/* server调用close()关闭 */
			ESP_LOGE("UDP_CLIENT", "server closed: %s", strerror(errno));
			return -1;
		}
		else if (0 > nsend)
		{
			if (EINTR  == errno || EAGAIN == errno || EWOULDBLOCK == errno)
			{
				/* 
				 * 参考链接：https://blog.csdn.net/modi000/article/details/106783572
				 */
				continue;
			}
			ESP_LOGE("UDP_CLIENT", "send failed errno: %d info: %s", errno, strerror(errno));
			return -1;
		}
		else{
			
			inet_ntoa_r(((struct sockaddr_in *)&dest_addr)->sin_addr, addr_str, sizeof(addr_str) - 1);
			ESP_LOGI("UDP_CLIENT", "send %d bytes data to ip addr: %s, port: %d", nsend, addr_str, PORT1 );
		}
		left -= nsend;
		buf += nsend;
	}

	return (len - left);
}

static void udp_receice_task(void *arg){

    uint8_t data[128];
	uint8_t txbuf[20];
	int txlen = 0;
    int len = 0;



    dest_addr.sin_family = AF_INET;
    // dest_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    dest_addr.sin_port = htons(PORT1);
	socklen_t broadlen = sizeof(broad_adr);

	src_addr.sin_family = AF_INET;
	src_addr.sin_addr.s_addr = local_ip_info.ip.addr;
	src_addr.sin_port = htons(PORT0);

    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if(sock < 0){
        ESP_LOGE(TAG,  "Unable to create socket: errno %d", errno);
		goto exit;
    }
	ESP_LOGI(TAG, "SOCKET CREATED, sock id: %d", sock);
    // 设置套接字为非阻塞模式
    int opt = 1;
    if (ioctl(sock, FIONBIO, &opt) < 0) {
        // Error handling
        ESP_LOGE(TAG, "Unable to set socket FIONBIO: errno %d", errno);
        goto exit;
    }					
	if (bind(sock,(struct sockaddr *)&src_addr,sizeof(src_addr)) != 0 ){        //绑定从机的端口号
		ESP_LOGE(TAG, "Socket unable to bind: errno %d", errno);
		goto exit;
	}
	inet_ntop(AF_INET, &src_addr.sin_addr, addr_str, sizeof(addr_str));
	ESP_LOGI(TAG, "Socket bound, ip: %s, port %d", addr_str, PORT0);

    while(1){
		vTaskDelay(10/portTICK_PERIOD_MS);
        len = recvfrom(sock, data, sizeof(data)-1, 0, (struct sockaddr*)&broad_adr, &broadlen);
        // Error occurred during receiving
		if (len < 0) {
			if (errno == EINPROGRESS || errno == EAGAIN || errno == EWOULDBLOCK) {
				//ESP_LOGE(TAG, "recvfrom negnected: errno %d", errno);
				//errno为该几个并非通讯错误，可忽略
            	continue;   // Not an error
        	}
			else{
				ESP_LOGE(TAG, "recvfrom failed: errno %d", errno);
				break;
			}
		}
        else{
			if(broad_adr.ss_family == PF_INET){	
			 	inet_ntoa_r(((struct sockaddr_in *)&broad_adr)->sin_addr, addr_str, sizeof(addr_str) - 1);
				ESP_LOGI(TAG, "Received %d bytes data from ip:%s", len, addr_str);
			}
			printf("read data:");
			for(int i = 0;i<len && i<15 ;i++){
				printf("%2x ", data[i]);
			}
			printf(".\r\n");
            data[len] = 0;
			int ret = DecodeCommand(data, len);
			if(ret<0){
				ESP_LOGE(TAG, "Received data error happened.");
			}
			else if(ret == 0 && isPCConnect){
				uart_tx_task(data, len);
				led_toggle();
			}
			else{
				if(CMD_CONN == (T_COMMAND) ret){
					memcpy(&dest_addr.sin_addr.s_addr, data+DATA_PLACE, 4);
			 		inet_ntoa_r(((struct sockaddr_in *)&dest_addr)->sin_addr, addr_str, sizeof(addr_str) - 1);
					
					ESP_LOGI(TAG, "dest address: %s, dest connected", addr_str);
					isPCConnect = 1;
					txlen = EncodeCommand(txbuf, CMD_CONN, (uint8_t*)&local_ip_info.ip);
					udp_safe_send(txbuf, txlen);

					led_set('G');
				}
				else if(CMD_DISC == (T_COMMAND) ret){
					uint8_t ddd = 1;
					txlen = EncodeCommand(txbuf, CMD_DISC, &ddd);
					ESP_LOGI(TAG, "dest disconnected.");
					udp_safe_send(txbuf, txlen);
					isPCConnect = 0;
					led_set('y');
				}
			}
        }
    }
exit:
	if (sock != -1) {
		ESP_LOGE(TAG, "Shutting down socket and restarting...");
		lwip_shutdown(sock, 0);
		close(sock);
	}
	vTaskDelete(NULL);
}

void udp_task(void){
	ESP_LOGE(TAG, "CREATE UDP RX TASK. ");
	xTaskCreate(udp_receice_task, "udp_receice_task", 4096, NULL, 6, NULL);
}


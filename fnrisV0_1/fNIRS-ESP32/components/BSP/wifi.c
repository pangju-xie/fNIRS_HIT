#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_mac.h"
#include "esp_log.h"
#include <netdb.h>
#include "nvs_flash.h"

#include "lwip/ip4_addr.h"
#include "lwip/ip_addr.h"

#include <stdio.h>
#include <string.h>
#include "wifi.h"
#include "dns_server.h"
#include "web_server_post.h"
#include "led.h"

#define WIFI_AP_SSID                "ESP_AP"                //热点名
#define WIFI_AP_PASSWORD            "12345678"              //热点密码
#define WIFI_AP_LEN                 0                       //
#define WIFI_AP_MAX_CON             4                       //STA模式最大连接数
#define WIFI_AP_AUTOMODE            WIFI_AUTH_WPA2_PSK      //AP连接方式

#define WIFI_MAXIMUM_RETRY          5                       //最大重连次数

#define WIFI_CONNECT_BIT            BIT0
#define WIFI_DISCONNECT_BIT         BIT1

static const char* TAG = "WIFI";

static EventGroupHandle_t s_wifi_event_group;

char wifi_ssid_from_nvs[50] = {0};
char wifi_password_from_nvs[50] = {0};
int s_retry_num = 0;

static wifi_config_t wifi_sta_config = {
    .sta = {
        .threshold.authmode = WIFI_AUTH_WPA_WPA2_PSK,
        .sae_pwe_h2e = WIFI_AUTH_WPA_WPA2_PSK,
    }
};

static wifi_config_t wifi_ap_config = {
    .ap = {
        .ssid = WIFI_AP_SSID,
        .ssid_len = WIFI_AP_LEN,
        .password = WIFI_AP_PASSWORD,
        .authmode = WIFI_AP_AUTOMODE,
        .max_connection = WIFI_AP_MAX_CON,
    }
};

esp_netif_ip_info_t local_ip_info;

static void event_handler(void* arg, esp_event_base_t event_base,
                                int32_t event_id, void* event_data)
{
    //sta mode event
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "START CONNECTINTG WIFI.");
        esp_wifi_connect();
    }
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < WIFI_MAXIMUM_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGE(TAG, "retry to connect to the AP");
        } else {
            ESP_LOGE(TAG, "FAIL TO CONNECT TO THE AP");
            xEventGroupSetBits(s_wifi_event_group, WIFI_DISCONNECT_BIT);
        }
        led_set('r');
        ESP_LOGE(TAG,"connect to the AP fail");
    } 
    else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        local_ip_info = event->ip_info;
        ESP_LOGI(TAG, "GER ip:" IPSTR, IP2STR(&local_ip_info.ip));
        ESP_LOGI(TAG, "GER mask:" IPSTR, IP2STR(&local_ip_info.netmask));
        ESP_LOGI(TAG, "GER gateway:" IPSTR, IP2STR(&event->ip_info.gw));
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECT_BIT);
    }

    //ap mode event
    if (event_id == WIFI_EVENT_AP_STACONNECTED) {
        wifi_event_ap_staconnected_t* event = (wifi_event_ap_staconnected_t*) event_data;
        ESP_LOGI(TAG, "station "MACSTR" join, AID=%d", MAC2STR(event->mac), event->aid);
    } else if (event_id == WIFI_EVENT_AP_STADISCONNECTED) {
        wifi_event_ap_stadisconnected_t* event = (wifi_event_ap_stadisconnected_t*) event_data;
        ESP_LOGI(TAG, "station "MACSTR" leave, AID=%d", MAC2STR(event->mac), event->aid);
    }
}

void set_wifi_mode(uint8_t mode){
    //mode:0->ap; 1->sta
    esp_netif_t *sta_netif;
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    
    if(mode){
        sta_netif = esp_netif_create_default_wifi_sta();
    }
    else{
        sta_netif = esp_netif_create_default_wifi_ap();
    }
    assert(sta_netif);

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,&event_handler, sta_netif,&instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, sta_netif, &instance_got_ip));
    if(mode){
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_sta_config));
    }
    else{
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));                           //设置ap模式
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_ap_config) );            //配置ap模式的参数
    }

    ESP_ERROR_CHECK(esp_wifi_start());

    if(mode){
        /* Waiting until either the connection is established (WIFI_CONNECTED_BIT) or connection failed for the maximum
        * number of re-tries (WIFI_FAIL_BIT). The bits are set by event_handler() (see above) */
        EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECT_BIT | WIFI_DISCONNECT_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
        /* xEventGroupWaitBits() returns the bits before the call returned, hence we can test which event actually happened. */
        if (bits & WIFI_CONNECT_BIT) {
            ESP_LOGI(TAG, "connected to ap SSID:%s password:%s",
                    (char *)&wifi_sta_config.sta.ssid, (char *)&wifi_sta_config.sta.password);
            led_set('y');
        } else if (bits & WIFI_DISCONNECT_BIT) {
            ESP_LOGI(TAG, "Failed to connect to SSID:%s, password:%s",
                    (char *)&wifi_sta_config.sta.ssid, (char *)&wifi_sta_config.sta.password);
            led_set('r');
            //当前根据串口打印出来的信息，会自动重连5次。（还不清楚这五次是从哪里来的,如果可以的话可以增加到10-15次，测试过程中重新上电时会有几次重连失败的情况，5次不太保险）
            //找到了，这个retry是在event_handler函数中，当前已经将最大重试次数改为15次了
            //在当前的基础上，这里加上功能：连接failed之后，就直接清除nvs消息并重启就可以了
            //还需要加上一个延时以及LOG
            ESP_ERROR_CHECK(nvs_flash_erase());
            ESP_LOGE(TAG, "nvs_flash_erased!\n");
            vTaskDelay(2000 / portTICK_PERIOD_MS);
            esp_restart();
        } else {
            ESP_LOGE(TAG, "UNEXPECTED EVENT");
        }
        /* The event will not be processed after unregister */
        ESP_ERROR_CHECK(esp_event_handler_instance_unregister(WIFI_EVENT, ESP_EVENT_ANY_ID, instance_any_id));
        vEventGroupDelete(s_wifi_event_group);
    }
}

int wifi_init(void){
    int err_nvs;
    err_nvs = NVS_read_data_from_flash(wifi_ssid_from_nvs, wifi_password_from_nvs, "OK");
    // ESP_LOGI(TAG, "err_nvs = %d." (int)err_nvs);
    if(err_nvs){
        led_set('w');
        set_wifi_mode(0);   //ap mode
        dns_server_start();
        web_server_start();
        return 0;
    }
    else{
        led_set('o');
        ESP_LOGI(TAG, "WIFI_SSID = %s", wifi_ssid_from_nvs);
        ESP_LOGI(TAG, "WIFI_PASSWORD = %s", wifi_password_from_nvs);
        strcpy((char*)&wifi_sta_config.sta.ssid, wifi_ssid_from_nvs);
        strcpy((char*)&wifi_sta_config.sta.password,wifi_password_from_nvs);
        set_wifi_mode(1);        //sta mode
        return 1;
    }
}


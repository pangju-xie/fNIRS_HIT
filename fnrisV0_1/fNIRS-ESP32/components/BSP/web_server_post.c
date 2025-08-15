//readme
//用于处理从html中得到的post事件（及得到数据的那个信号）
//参考网站：https://blog.csdn.net/q_fy_p/article/details/127175477
//handler的编写参考网站：https://blog.csdn.net/sinat_36568888/article/details/118355836


#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "nvs_flash.h"

#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"

#include "nvs_flash.h"
#include "nvs.h"

#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/sys.h"
#include "lwip/netdb.h"
#include "lwip/dns.h"

#include "esp_http_server.h"



#define MIN( x, y ) ( ( x ) < ( y ) ? ( x ) : ( y ) )

//这里的代码引用html文件，在CMakeLists.list已经嵌入了index.html文件
extern const uint8_t index_html_start[] asm("_binary_index_html_start");
extern const uint8_t index_html_end[]   asm("_binary_index_html_end");

static const char *TAG = "WEB_SERVER_POST";

/*-----------------这里是my_nvs的程序_start------------------*/
//这部分代码为新的nvs程序，参考来源：https://blog.csdn.net/weixin_59288228/article/details/129493804

void NVS_write_data_to_flash(char *WIFI_Name_write_in, char *WIFI_Password_write_in, char *ConfirmString)
{
    //本函数用于保存收集到的wifi信息进flash中
    //输入参数ConfirmString没啥作用，但是去掉的话会报错：NVS_write_data_to_flash定义的参数太多
    //输入参数confirmstring的作用为设置校检字符串
    nvs_handle my_nvs_handle;
    wifi_config_t nvs_wifi_store;       //定义一个wifi_config_t的变量用于储存wifi信息
    
	// 要写入的WIFI信息，这部分对应将函数中的name password分别写入到wifi_config_to_store中
    strcpy((char *)&nvs_wifi_store.sta.ssid,WIFI_Name_write_in);            //将ssid_write_in参数写入到需要保存的变量中
    strcpy((char *)&nvs_wifi_store.sta.password,WIFI_Password_write_in);    //将password_write_in参数写入需要保存的变量中
    ESP_ERROR_CHECK( nvs_open("wifi", NVS_READWRITE, &my_nvs_handle) );     //打开nvs，以可读可写的方式
    ESP_ERROR_CHECK( nvs_set_str( my_nvs_handle, "check", ConfirmString) ); //储存校检符号
    ESP_ERROR_CHECK( nvs_set_blob( my_nvs_handle, "wifi_config", &nvs_wifi_store, sizeof(nvs_wifi_store)));     //将类型为wifi_config_t的变量nvs_wifi_store储存于flash中 
    if(ESP_OK != nvs_commit(my_nvs_handle)){                              //commit数据
        ESP_LOGE(TAG, "nvs_commit error!");
    }
    nvs_close(my_nvs_handle);                                             //关闭nvs
}

unsigned char NVS_read_data_from_flash(char *WIFI_Name,char *WIFI_Password, char *ConfirmString)
{   
    //该函数的功能用于读取nvs中的wifi信息
    //输入参数ConfirmString没啥作用，但是去掉的话会报错：NVS_write_data_to_flash定义的参数太多
    //输入参数confirmstring的作用为设置校检字符串
    nvs_handle my_nvs_handle;
    size_t str_length = 50;
    char str_data[50] = {0};
    wifi_config_t nvs_wifi_stored;       //定义一个用于保存wifi信息的wifi_config_t类型的变量
    memset(&nvs_wifi_stored, 0x0, sizeof(nvs_wifi_stored));       //为已经保持的用户信息
    size_t wifi_len = sizeof(nvs_wifi_stored);
    ESP_ERROR_CHECK( nvs_open("wifi", NVS_READWRITE, &my_nvs_handle) );
    //ESP_ERROR_CHECK( nvs_get_str(my_nvs_handle, "check", str_data, &str_length) );       //校验字符串，用于与read中的confirmstring相对应的
    //ESP_ERROR_CHECK( nvs_get_blob(my_nvs_handle, "wifi_config", &nvs_wifi_stored, &wifi_len));       //用于保存读取到的wifi信息，key为wifi_config
    nvs_get_str(my_nvs_handle, "check", str_data, &str_length);
    nvs_get_blob(my_nvs_handle, "wifi_config", &nvs_wifi_stored, &wifi_len);
    //上面两条读取nvs内容的代码不能使用ESP_ERROR_CHECK来检测错误，不然若NVS为空的时候，会一直报错并且一直重启
    //以下打印信息为字节长度及已保持的wifi信息
    //printf("[data1]: %s len:%u\r\n", str_data, str_length);
    //printf("[data3]: ssid:%s passwd:%s\r\n", wifi_config_stored.sta.ssid, wifi_config_stored.sta.password);
    //
    strcpy(WIFI_Name,(char *)&nvs_wifi_stored.sta.ssid);
    strcpy(WIFI_Password,(char *)&nvs_wifi_stored.sta.password);
    nvs_close(my_nvs_handle);
    //下面这部分代码是判断是否正确读写flash中的数据
    if(strcmp(ConfirmString,str_data) == 0)
    {
        return 0x00;
    }
    else
    {
        return 0xFF;
    }
}



/*-----------------这里是my_nvs的程序_end----------------------*/

//20230519的demo中的nvs部分
//下面这部分的nvs程序测试结果来说使用不了
//实际上打开write函数不知道有没有效果
//在main函数中打开read函数，esp32会不断重启
//因此还需要另外的代码来实现nvs储存功能
/* void NVS_write_data_to_flash(char *WIFI_Name, char *WIFI_Password, char *ConfirmString)
{
    //本函数用于保存收集到的wifi信息进flash中
    nvs_handle my_nvs_handle;

    // 写入一个整形数据，一个字符串，WIFI信息以及版本信息
    static const char *NVS_CUSTOMER = "customer data";
    static const char *DATA2 = "String";
    static const char *DATA3 = "blob_wifi";
    
	// 要写入的WIFI信息，这部分对应将函数中的name password分别写入到wifi_config_to_store中
    wifi_config_t wifi_config_to_store;
    strcpy((char *)&wifi_config_to_store.sta.ssid,WIFI_Name);
    strcpy((char *)&wifi_config_to_store.sta.password,WIFI_Password);
    ESP_LOGE(TAG,"set size : %u!/r/n",sizeof(wifi_config_to_store));    //打印出保持的字节数
    ESP_ERROR_CHECK( nvs_open( NVS_CUSTOMER, NVS_READWRITE, &my_nvs_handle) );
    ESP_ERROR_CHECK( nvs_set_str( my_nvs_handle, DATA2, ConfirmString) );       //暂不清楚这部分的作用
    ESP_ERROR_CHECK( nvs_set_blob( my_nvs_handle, DATA3, &wifi_config_to_store, sizeof(wifi_config_to_store)));     //暂不清楚这部分的作用
    ESP_ERROR_CHECK( nvs_commit(my_nvs_handle) );
    nvs_close(my_nvs_handle);
}
 */
/* unsigned char NVS_read_data_from_flash(char *ConfirmString,char *WIFI_Name,char *WIFI_Password)
{
    nvs_handle my_nvs_handle;
    // 写入一个整形数据，一个字符串，WIFI信息以及版本信息
    static const char *NVS_CUSTOMER = "customer data";
    static const char *DATA2 = "String";
    static const char *DATA3 = "blob_wifi";
    uint32_t str_length = 50;
    char str_data[50] = {0};
    wifi_config_t wifi_config_stored;
    memset(&wifi_config_stored, 0x0, sizeof(wifi_config_stored));       //为已经保持的用户信息
    uint32_t wifi_len = sizeof(wifi_config_stored);
    ESP_ERROR_CHECK( nvs_open(NVS_CUSTOMER, NVS_READWRITE, &my_nvs_handle) );

    ESP_ERROR_CHECK ( nvs_get_str(my_nvs_handle, DATA2, str_data, &str_length) );
    ESP_ERROR_CHECK ( nvs_get_blob(my_nvs_handle, DATA3, &wifi_config_stored, &wifi_len) );
    //以下打印信息为字节长度及已保持的wifi信息
    //printf("[data1]: %s len:%u\r\n", str_data, str_length);
    //printf("[data3]: ssid:%s passwd:%s\r\n", wifi_config_stored.sta.ssid, wifi_config_stored.sta.password);
    //
    strcpy(WIFI_Name,(char *)&wifi_config_stored.sta.ssid);
    strcpy(WIFI_Password,(char *)&wifi_config_stored.sta.password);
    nvs_close(my_nvs_handle);
    //下面这部分代码是判断是否正确读写flash中的数据
    if(strcmp(ConfirmString,str_data) == 0)
    {
        return 0x00;
    }
    else
    {
        return 0xFF;
    }
}
 */

//http_SendText_html函数是https://blog.csdn.net/q_fy_p/article/details/127175477中编写的
//代码功能应该是用于发送html至sta设备
static esp_err_t http_SendText_html(httpd_req_t *req)
{
    /* Get handle to embedded file upload script */
 
    const size_t upload_script_size = (index_html_end - index_html_start);
    
    /* Add file upload form and script which on execution sends a POST request to /upload */
    //这部分代码参考来源：https://blog.csdn.net/q_fy_p/article/details/127175477
    //这部分是demo的源代码部分，但是跑不通，弹不出网页来，估计是httpd_resp_send_chunk函数的问题
    // const char TxBuffer[] = "<h1> SSID1 other WIFI</h1>";
    // httpd_resp_send_chunk(req, (const char *)index_html_start, upload_script_size);
    // httpd_resp_send_chunk(req,(const char *)TxBuffer,sizeof(TxBuffer));
    
    //下面这部分代码参考来源：https://blog.csdn.net/qq_27114397/article/details/89643232
    //httpd_resp_set_type和httpd_resp_set_hdr这俩函数不是很清楚它们的功能，只保留httpd_reso_send函数就能自动弹出页面
    //httpd_resp_set_type(req, "text/html");
    //httpd_resp_set_hdr(req, "Content-Encoding", "gzip");
    return httpd_resp_send(req, (const char *)index_html_start, upload_script_size);
    //return ESP_OK;
}

//HTTP_FirstGet_handler函数是https://blog.csdn.net/q_fy_p/article/details/127175477中编写的
//代码功能:强制门户访问时连接wifi后的第一次任意GET请求
static esp_err_t HTTP_FirstGet_handler(httpd_req_t *req)
{
    http_SendText_html(req);
    return ESP_OK;
}

unsigned char CharToNum(unsigned char Data)
{
    if(Data >= '0' && Data <= '9')
    {
        return Data - '0';
    }
    else if(Data >= 'a' && Data <= 'f')
    {
        switch (Data)
        {
            case 'a':return 10;
            case 'b':return 11;
            case 'c':return 12;
            case 'd':return 13;
            case 'e':return 14;
            case 'f':return 15;
        default:
            break;
        }
    }
    else if(Data >= 'A' && Data <= 'F')
    {
        switch (Data)
        {
            case 'A':return 10;
            case 'B':return 11;
            case 'C':return 12;
            case 'D':return 13;
            case 'E':return 14;
            case 'F':return 15;
        default:
            break;
        }
    }
    return 0;
}


//当前主要工作就是对这部分代码进行解析并处理，这里需要完成的内容：
//1、需要将ssid和password保存至nvs flash中
//2、然后需要在main中进行sta和ap之间的切换
//3、测试一下nvs flash保存的内容
/* 门户页面发回的，带有要连接的WIFI的名字和密码 */
static esp_err_t WIFI_Config_POST_handler(httpd_req_t *req)
{
    char buf[100];
    int ret, remaining = req->content_len;
 
    while (remaining > 0) {
        /* Read the data for the request */
        //这部分代码用于读取到来自ipad端的post请求
        if ((ret = httpd_req_recv(req, buf,
                        MIN(remaining, sizeof(buf)))) <= 0) {
            if (ret == HTTPD_SOCK_ERR_TIMEOUT) {
                /* Retry receiving if timeout occurred */
                continue;
            }
            return ESP_FAIL;
        }
        /* Send back the same data */
        //将接收到的数据发送回浏览器端（回环），注释掉这部分的代码
        // char WIFI_ConfigBackInformation[100] = "The WIFI To Connect :";
        // strcat(WIFI_ConfigBackInformation,buf);
        // httpd_resp_send_chunk(req, WIFI_ConfigBackInformation, sizeof(WIFI_ConfigBackInformation));
        
        remaining -= ret;
 
        char wifi_name[50];                             //用于储存wifi ssid
        char wifi_password[50];                         //用于储存password
        char wifi_passwordTransformation[50] = {0};     //这个数组用于储存转化后的password,暂时不知道为什么需要转化
        //重要代码，用于接收ssid，注意“ssid”要与index.html中的名称匹配
        esp_err_t e = httpd_query_key_value(buf,"ssid",wifi_name,sizeof(wifi_name));
        if(e == ESP_OK) {
            printf("SSID = %s\r\n",wifi_name);
        }
        else {
            printf("error = %d\r\n",e);
        }
        //重要代码，用于接收password，注意“password”要与index.html中的名称匹配
        e = httpd_query_key_value(buf,"password",wifi_password,sizeof(wifi_password));
        if(e == ESP_OK) {
            /*对传回来的数据进行处理*/ //源自源代码作者的备注
            //但是这部分感觉处理和不处理没啥大关系？算了，两个都试一下吧
            unsigned char Len = strlen(wifi_password);
            char tempBuffer[2];
            char *temp;
            unsigned char Cnt = 0;
            temp = wifi_password;
            for(int i=0;i<Len;){
                if(*temp == '%'){
                    tempBuffer[0] = CharToNum(temp[1]);
                    tempBuffer[1] = CharToNum(temp[2]);
                    *temp = tempBuffer[0] * 16 + tempBuffer[1];
                    wifi_passwordTransformation[Cnt] = *temp;
                    temp+=3;
                    i+=3;
                    Cnt++;
                }
                else{
                    wifi_passwordTransformation[Cnt] = *temp;
                    temp++;
                    i++;
                    Cnt++;
                }
            }
            temp -= Len;
            printf("Len = %d\r\n",Len);
            printf("wifi_password = %s\r\n",wifi_password);
            printf("pswd = %s\r\n",wifi_passwordTransformation);
        }
        else {
            printf("error = %d\r\n",e);
        }
        /* Log data received */
        //这部分是打印出post method的内容
         ESP_LOGI(TAG, "=========== RECEIVED DATA ==========");
         ESP_LOGI(TAG, "%.*s", ret, buf);
         ESP_LOGI(TAG, "====================================");

        //这句代码用于将得到的数据保存至nvs中
        //这里用到的password是上面转化前的password
        NVS_write_data_to_flash(wifi_name,wifi_password,"OK");
        printf("nvs ssid is %s, nvs password is %s !\n",wifi_name,wifi_password);
        //读取到数据后就重新启动esp32并切换成sta模式重新连接
        esp_restart();

        //下面这部分代码则是重启后先stop ap模式，随后进行sta模式的初始化即连接，来源：原demo
        //原demo中的wifi sta模式初始化部分的内容已删除
    }
 
    return ESP_OK;
}


void web_server_start(void)
{
    // xTaskCreate(&webserver, "webserver_task", 2048, NULL, 5, NULL);
    httpd_handle_t server = NULL;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    /* Use the URI wildcard matching function in order to
     * allow the same handler to respond to multiple different
     * target URIs which match the wildcard scheme */
    config.uri_match_fn = httpd_uri_match_wildcard;
    
    //启动web服务器
    ESP_LOGI(TAG, "Starting HTTP Server on port: '%d'", config.server_port); 
    if (httpd_start(&server, &config) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start file server!");
        return ;
    }
 
    /* URI handler for getting uploaded files */
    //这部分代码的功能讲解：
    //当ipad端打开192.168.4.1时会向esp32(即server端)发送一个HTTP_GET method的一个请求
    //此时就会触发HTTP_FistGet_handler这个事件，事件的功能为跳转至配网页面
    httpd_uri_t file_download = {
        .uri       = "/*",  // Match all URIs of type /path/to/file
        .method    = HTTP_GET,
        .handler   = HTTP_FirstGet_handler,
        .user_ctx  = NULL,
    };
    httpd_register_uri_handler(server, &file_download);
 
    /* URI handler for uploading files to server */
    //这部分代码的功能讲解：
    //这部分则是与html中定义的configwifi语句相关，当在ipad端点击submit时触发该语句并向esp32端发送一个HTTP_POST method类型的请求
    //此时就会触发WIFI_Config_POST_handler函数，这个函数的功能还需要再确定修改一下，因为现在还不知道POST发送过来的数据是咋样的
    //当前部分的功能已经能够正常接收到POST的数据了
    httpd_uri_t file_upload = {
        .uri       = "/configwifi",   // Match all URIs of type /upload/path/to/file
        .method    = HTTP_POST,
        .handler   = WIFI_Config_POST_handler,
        .user_ctx  = NULL,
    };
    httpd_register_uri_handler(server, &file_upload);
 

}

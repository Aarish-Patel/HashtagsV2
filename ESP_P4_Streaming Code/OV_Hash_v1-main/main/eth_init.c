/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "eth_init.h"
#include "sdkconfig.h"
#include "esp_log.h"
#include "esp_check.h"
#include "esp_eth.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "driver/gpio.h"

static const char *TAG = "eth_init";

#define ETH_MDC_GPIO       31
#define ETH_MDIO_GPIO      52
#define ETH_PHY_RST_GPIO   51
#define ETH_PHY_ADDR        1

// Store handles statically for deinit
static esp_eth_handle_t      s_eth_handle  = NULL;
static esp_netif_t           *s_eth_netif  = NULL;
static esp_eth_netif_glue_handle_t s_glue  = NULL;

static void eth_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    switch (event_id) {
    case ETHERNET_EVENT_CONNECTED:
        ESP_LOGI(TAG, "Ethernet link up");
        break;
    case ETHERNET_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "Ethernet link down");
        break;
    case ETHERNET_EVENT_START:
        ESP_LOGI(TAG, "Ethernet started");
        break;
    case ETHERNET_EVENT_STOP:
        ESP_LOGI(TAG, "Ethernet stopped");
        break;
    default:
        break;
    }
}

static void got_ip_event_handler(void *arg, esp_event_base_t event_base,
                                  int32_t event_id, void *event_data)
{
    ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
    ESP_LOGI(TAG, "Ethernet got IP: " IPSTR, IP2STR(&event->ip_info.ip));
    ESP_LOGI(TAG, "  Netmask: " IPSTR, IP2STR(&event->ip_info.netmask));
    ESP_LOGI(TAG, "  Gateway: " IPSTR, IP2STR(&event->ip_info.gw));
}

static bool parse_ip4(const char *str, esp_ip4_addr_t *addr)
{
    unsigned int a, b, c, d;
    if (sscanf(str, "%u.%u.%u.%u", &a, &b, &c, &d) != 4) return false;
    if (a > 255 || b > 255 || c > 255 || d > 255) return false;
    addr->addr = (d << 24) | (c << 16) | (b << 8) | a;
    return true;
}

esp_err_t eth_init(void)
{
    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "TCP/IP init failed");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "Event loop create failed");

    esp_netif_config_t netif_cfg = ESP_NETIF_DEFAULT_ETH();
    s_eth_netif = esp_netif_new(&netif_cfg);

#ifdef CONFIG_ETH_IP_STATIC
    ESP_RETURN_ON_ERROR(esp_netif_dhcpc_stop(s_eth_netif), TAG, "DHCP client stop failed");

    esp_netif_ip_info_t ip_info = { 0 };
    if (!parse_ip4(CONFIG_ETH_STATIC_IP, &ip_info.ip) ||
        !parse_ip4(CONFIG_ETH_STATIC_NETMASK, &ip_info.netmask) ||
        !parse_ip4(CONFIG_ETH_STATIC_GATEWAY, &ip_info.gw)) {
        ESP_LOGE(TAG, "Invalid static IP config");
        return ESP_ERR_INVALID_ARG;
    }
    ESP_RETURN_ON_ERROR(esp_netif_set_ip_info(s_eth_netif, &ip_info),
                        TAG, "Set static IP failed");
    ESP_LOGI(TAG, "Static IP: " IPSTR, IP2STR(&ip_info.ip));
#else
    ESP_LOGI(TAG, "DHCP mode");
#endif

    eth_mac_config_t mac_config = ETH_MAC_DEFAULT_CONFIG();
    eth_esp32_emac_config_t esp32_emac_config = ETH_ESP32_EMAC_DEFAULT_CONFIG();
    esp32_emac_config.smi_gpio.mdc_num  = ETH_MDC_GPIO;
    esp32_emac_config.smi_gpio.mdio_num = ETH_MDIO_GPIO;

    esp_eth_mac_t *mac = esp_eth_mac_new_esp32(&esp32_emac_config, &mac_config);
    ESP_RETURN_ON_FALSE(mac, ESP_FAIL, TAG, "MAC create failed");

    eth_phy_config_t phy_config = ETH_PHY_DEFAULT_CONFIG();
    phy_config.phy_addr       = ETH_PHY_ADDR;
    phy_config.reset_gpio_num = ETH_PHY_RST_GPIO;

    esp_eth_phy_t *phy = esp_eth_phy_new_ip101(&phy_config);
    ESP_RETURN_ON_FALSE(phy, ESP_FAIL, TAG, "PHY create failed");

    esp_eth_config_t config = ETH_DEFAULT_CONFIG(mac, phy);
    ESP_RETURN_ON_ERROR(esp_eth_driver_install(&config, &s_eth_handle),
                        TAG, "Driver install failed");

    s_glue = esp_eth_new_netif_glue(s_eth_handle);
    ESP_RETURN_ON_ERROR(esp_netif_attach(s_eth_netif, s_glue),
                        TAG, "Netif attach failed");

    ESP_RETURN_ON_ERROR(
        esp_event_handler_register(ETH_EVENT, ESP_EVENT_ANY_ID,
                                   &eth_event_handler, NULL),
        TAG, "ETH event handler register failed");
    ESP_RETURN_ON_ERROR(
        esp_event_handler_register(IP_EVENT, IP_EVENT_ETH_GOT_IP,
                                   &got_ip_event_handler, NULL),
        TAG, "IP event handler register failed");

    ESP_RETURN_ON_ERROR(esp_eth_start(s_eth_handle), TAG, "Ethernet start failed");

    ESP_LOGI(TAG, "Ethernet initialized (IP101GR PHY)");
    return ESP_OK;
}

esp_err_t eth_deinit(void)
{
    ESP_LOGI(TAG, "Shutting down Ethernet...");

    if (s_eth_handle) {
        esp_eth_stop(s_eth_handle);
        vTaskDelay(pdMS_TO_TICKS(200)); // let PHY power down
        esp_eth_driver_uninstall(s_eth_handle);
        s_eth_handle = NULL;
    }

    if (s_glue) {
        esp_eth_del_netif_glue(s_glue);
        s_glue = NULL;
    }

    if (s_eth_netif) {
        esp_netif_destroy(s_eth_netif);
        s_eth_netif = NULL;
    }

    esp_event_handler_unregister(ETH_EVENT, ESP_EVENT_ANY_ID, &eth_event_handler);
    esp_event_handler_unregister(IP_EVENT, IP_EVENT_ETH_GOT_IP, &got_ip_event_handler);

    ESP_LOGI(TAG, "Ethernet shut down");
    return ESP_OK;
}
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_log.h"
#include "hgic_raw.h"
#include "lwip/opt.h"
#include "lwip/def.h"
#include "lwip/mem.h"
#include "lwip/pbuf.h"
#include "lwip/sys.h"
#include "lwip/stats.h"
#include "lwip/snmp.h"
#include "lwip/ethip6.h"
#include "lwip/tcpip.h"
#include "netif/etharp.h"

static const char *TAG = "HGIC_LWIP";

struct ethernetif {
    unsigned char tx_buff[2048];
    unsigned char *rx_buff;
    unsigned int  rx_data_len;
};

static struct netif hgic_wifi;
extern struct hgic_raw hgic;

static err_t low_level_output(struct netif *netif, struct pbuf *p)
{
    struct ethernetif *ethernetif = netif->state;
    int ret = 0;

#if ETH_PAD_SIZE
    pbuf_header(p, -ETH_PAD_SIZE); /* drop the padding word */
#endif

    pbuf_copy_partial(p, ethernetif->tx_buff, p->tot_len, 0);

    ret = hgic_raw_send_ether(ethernetif->tx_buff, p->tot_len);
    if (ret) {
        ESP_LOGE(TAG, "Send ethernet frame error, ret:%d", ret);
        return ERR_IF;
    }

#if ETH_PAD_SIZE
    pbuf_header(p, ETH_PAD_SIZE); /* reclaim the padding word */
#endif
    return ERR_OK;
}

static struct pbuf *low_level_input(struct netif *netif)
{
    struct ethernetif *ethernetif = netif->state;
    struct pbuf *p = NULL;
    u16_t len = ethernetif->rx_data_len;

#if ETH_PAD_SIZE
    len += ETH_PAD_SIZE;
#endif

    p = pbuf_alloc(PBUF_RAW, len, PBUF_POOL);
    if (p != NULL) {
#if ETH_PAD_SIZE
        pbuf_header(p, -ETH_PAD_SIZE);
#endif
        pbuf_take(p, ethernetif->rx_buff, ethernetif->rx_data_len);
#if ETH_PAD_SIZE
        pbuf_header(p, ETH_PAD_SIZE);
#endif
    } else {
        ESP_LOGE(TAG, "No memory, drop packet!");
    }
    return p;
}

static void ethernetif_input(struct netif *netif)
{
    struct pbuf *p;
    p = low_level_input(netif);
    if (p != NULL) {
        if (netif->input(p, netif) != ERR_OK) {
            pbuf_free(p);
        }
    }
}

void hgic_netif_rx(unsigned char *data, unsigned int len)
{
    struct netif *wifi = &hgic_wifi;
    struct ethernetif *eth_if = (struct ethernetif *)wifi->state;

    eth_if->rx_buff     = data;
    eth_if->rx_data_len = len;
    ethernetif_input(wifi);
}

static err_t ethernetif_init(struct netif *netif)
{
    LWIP_ASSERT("netif != NULL", (netif != NULL));
    
#if LWIP_NETIF_HOSTNAME
    netif->hostname = "esp-halow";
#endif

    netif->name[0] = 'w';
    netif->name[1] = '0';
    netif->output = etharp_output;
#if LWIP_IPV6
    netif->output_ip6 = ethip6_output;
#endif
    netif->linkoutput = low_level_output;
    netif->hwaddr_len = ETHARP_HWADDR_LEN;
    netif->mtu = 1500;
    netif->flags = NETIF_FLAG_BROADCAST | NETIF_FLAG_ETHARP | NETIF_FLAG_LINK_UP;

    return ERR_OK;
}

int hgic_lwip_netif_add(void)
{
    struct ethernetif *ethif = NULL;

    memset(&hgic_wifi, 0, sizeof(struct netif));
    memcpy(hgic_wifi.hwaddr, hgic.fwinfo.mac, 6);

    ethif = malloc(sizeof(struct ethernetif));
    if (!ethif) {
        return -1;
    }
    memset(ethif, 0, sizeof(struct ethernetif));

    ip4_addr_t ipaddr, netmask, gw;
    IP4_ADDR(&ipaddr, 192, 168, 0, 198);
    IP4_ADDR(&netmask, 255, 255, 255, 0);
    IP4_ADDR(&gw, 192, 168, 0, 1);

    if (NULL == netif_add(&hgic_wifi, &ipaddr, &netmask, &gw,
                          (void *)ethif, ethernetif_init, tcpip_input)) {
        ESP_LOGE(TAG, "Add to netif failed!");
        return -1;
    }

    netif_set_default(&hgic_wifi);
    netif_set_up(&hgic_wifi);
    netif_set_link_up(&hgic_wifi);
    ESP_LOGI(TAG, "HaLow netif added successfully. IP: 192.168.0.198");
    return 0;
}

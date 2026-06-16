#pragma once

#ifdef __cplusplus
extern "C" {
#endif

int hgic_lwip_netif_add(void);
void hgic_netif_rx(unsigned char *data, unsigned int len);

#ifdef __cplusplus
}
#endif

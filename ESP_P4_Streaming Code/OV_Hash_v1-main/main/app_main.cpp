#include "camera_pipeline.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "http_server.h"
#include "perf_monitor.h"
#include "sdkconfig.h"
#include "uvc_controls.h"
#include "uvc_streaming.h"

// HaLow Includes
#include "t_halow_p4_config.h"
#include "cpp_bus_driver_library.h"
#include "esp_netif.h"
#include "esp_event.h"
#include <memory>
#include <algorithm>

extern "C" {
#include "hgic_sdspi.h"
#include "hgic_raw.h"
#include "hgic_lwip.h"
}

static const char *TAG = "hashtag_node";

#define WAKEUP_GPIO GPIO_NUM_20
#define WAKEUP_GPIO_MASK (1ULL << WAKEUP_GPIO)
#define IR_LED_PIN GPIO_NUM_22
#define STREAM_DURATION_MS 30000 // 30 seconds, adjust as needed

// ---------------------------------------------------------
// HaLow SPI Driver Wrappers
// ---------------------------------------------------------
#define MAX_SPI_RECEIVE_SIZE std::min(HGIC_RAW_DATA_ROOM, HGIC_RAW_MAX_PAYLOAD)

static auto spidrv_read_buffer = std::make_unique<uint8_t[]>(MAX_SPI_RECEIVE_SIZE);
static volatile bool Interrupt_Flag = false;

static auto Tx_Ah_R900pnr_Spi_Bus = std::make_shared<Cpp_Bus_Driver::Hardware_Spi>(
    TX_AH_R900PNR_MOSI, TX_AH_R900PNR_SCLK, TX_AH_R900PNR_MISO,
    SPI2_HOST, 0, spi_clock_source_t::SPI_CLK_SRC_SPLL);

extern "C" void spidrv_write_read(void *priv, unsigned char *wdata, unsigned char *rdata, unsigned int len) {
    Tx_Ah_R900pnr_Spi_Bus->write_read(wdata, rdata, len);
}

extern "C" void spidrv_write(void *priv, unsigned char *data, unsigned int len, char dma_flag) {
    Tx_Ah_R900pnr_Spi_Bus->write(data, len);
}

extern "C" void spidrv_read(void *priv, unsigned char *data, unsigned int len, char dma_flag) {
    Tx_Ah_R900pnr_Spi_Bus->write_read(spidrv_read_buffer.get(), data, len);
}

extern "C" void spidrv_cs(void *priv, char enable) { }

extern "C" int spidrv_hw_crc(void *priv, unsigned char *data, unsigned int len, char flag) { return 0; }

extern "C" int hgic_raw_send_data(unsigned char *data, unsigned int len) {
    return hgic_sdspi_write(0, data, len);
}

static void hgic_rx_task(void *arg) {
    while (1) {
        if (hgic_sdspi_detect_alive(0) == -1) {
            ESP_LOGW(TAG, "hgic_sdspi_detect_alive fail, restarting hgic_sdspi");
            hgic_sdspi_init(0);
        }

        if (Interrupt_Flag == true) {
            auto buffer = std::make_unique<unsigned char[]>(2048);
            size_t length = hgic_sdspi_read(0, buffer.get(), 2048, 0);

            if (length != static_cast<size_t>(-1) && length > 0) {
                unsigned char *buf_p = buffer.get();
                unsigned int length_2 = static_cast<unsigned int>(length);
                
                int type = hgic_raw_rx(&buf_p, &length_2);
                if (type == HGIC_RAW_RX_TYPE_DATA) {
                    hgic_netif_rx(buf_p, length_2);
                }
            }
            Interrupt_Flag = false;
        }

        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
// ---------------------------------------------------------

static void go_to_sleep(void) {
  // IR LEDs off
  gpio_set_level(IR_LED_PIN, 0);

  gpio_config_t io_conf = {
      .pin_bit_mask = WAKEUP_GPIO_MASK,
      .mode = GPIO_MODE_INPUT,
      .pull_up_en = GPIO_PULLUP_DISABLE,
      .pull_down_en = GPIO_PULLDOWN_ENABLE,
      .intr_type = GPIO_INTR_DISABLE,
  };
  gpio_config(&io_conf);

  esp_sleep_enable_ext1_wakeup(WAKEUP_GPIO_MASK, ESP_EXT1_WAKEUP_ANY_HIGH);

  ESP_LOGI(TAG, "Entering deep sleep");
  fflush(stdout);
  esp_deep_sleep_start();
}

extern "C" void app_main(void) {
  // IR LED pin setup - off by default
  gpio_config_t led_conf = {
      .pin_bit_mask = (1ULL << IR_LED_PIN),
      .mode = GPIO_MODE_OUTPUT,
      .pull_up_en = GPIO_PULLUP_DISABLE,
      .pull_down_en = GPIO_PULLDOWN_DISABLE,
      .intr_type = GPIO_INTR_DISABLE,
  };
  gpio_config(&led_conf);
  gpio_set_level(IR_LED_PIN, 0); // off until we need it

  // --- HA-LOW INITIALIZATION ---
  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());

  ESP_LOGI(TAG, "Initializing HaLow SPI Bus...");
  Tx_Ah_R900pnr_Spi_Bus->create_gpio_interrupt(TX_AH_R900PNR_INT, Cpp_Bus_Driver::Tool::Interrupt_Mode::FALLING,
                                               [](void *arg) -> IRAM_ATTR void {
                                                   Interrupt_Flag = true;
                                               });

  memset(spidrv_read_buffer.get(), 0xFF, MAX_SPI_RECEIVE_SIZE);
  Tx_Ah_R900pnr_Spi_Bus->begin(40000000, TX_AH_R900PNR_CS);

  vTaskDelay(pdMS_TO_TICKS(1000));

  int32_t assert_sdspi = hgic_sdspi_init(0);
  while (assert_sdspi == -1) {
      ESP_LOGE(TAG, "hgic_sdspi_init fail (error code: %ld)", assert_sdspi);
      assert_sdspi = hgic_sdspi_init(0);
      vTaskDelay(pdMS_TO_TICKS(1000));
  }
  ESP_LOGI(TAG, "hgic_sdspi_init success");

  if (hgic_raw_get_fwinfo() == -1) {
      ESP_LOGE(TAG, "hgic_raw_get_fwinfo fail");
  }

  hgic_raw_set_mode((char *)"sta");

  // Add LWIP netif for HaLow
  if(hgic_lwip_netif_add() != 0) {
      ESP_LOGE(TAG, "Failed to add lwip netif for HaLow");
  }

  xTaskCreate(hgic_rx_task, "hgic_rx_task", 4096, NULL, 10, NULL);
  // -----------------------------

  // Check wakeup reason
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  if (cause != ESP_SLEEP_WAKEUP_EXT1) {
    ESP_LOGI(TAG, "Cold boot or non-motion wakeup - going to sleep");
    // NOTE: For testing HaLow, you may want to comment out the next two lines
    // so it doesn't go to sleep if you just power it on.
    // go_to_sleep();
    // return;
  }

  // Motion triggered wakeup - start streaming
  ESP_LOGI(TAG, "=== Motion Detected - Hashtag Node Active ===");

  // Turn IR LEDs on
  gpio_set_level(IR_LED_PIN, 1);
  ESP_LOGI(TAG, "IR LEDs on");

  // Phase 1: Camera init
  esp_err_t ret = camera_init();
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Camera init failed: %s", esp_err_to_name(ret));
    go_to_sleep();
    return;
  }

  // Phase 2: UVC streaming pipeline
  static uvc_stream_ctx_t stream_ctx;
  ret = uvc_stream_init(&stream_ctx);
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "UVC stream init failed: %s", esp_err_to_name(ret));
    go_to_sleep();
    return;
  }

  perf_monitor_start(&stream_ctx);

  // Phase 3: UVC controls
  uvc_ctrl_init();
  uvc_ctrl_set_jpeg_quality(stream_ctx.jpeg_enc.m2m_fd,
                            30);                               // Quality 30
  uvc_ctrl_set_h264_params(stream_ctx.h264_enc.m2m_fd, 500000, /* 500 kbps */
                           CONFIG_UVC_H264_I_PERIOD, CONFIG_UVC_H264_MIN_QP,
                           CONFIG_UVC_H264_MAX_QP);

  // Phase 5: HTTP server (Phase 4 Ethernet was removed)
  ret = http_server_start(&stream_ctx);
  if (ret != ESP_OK) {
    ESP_LOGW(TAG, "HTTP server failed: %s", esp_err_to_name(ret));
    go_to_sleep();
    return;
  }

  ESP_LOGI(TAG, "Streaming for %d seconds...", STREAM_DURATION_MS / 1000);
  ESP_LOGI(TAG, "HTTP: http://<device-ip>/stream");

  // Wait for the duration of the clip
  vTaskDelay(pdMS_TO_TICKS(STREAM_DURATION_MS));

  ESP_LOGI(TAG, "Stream duration reached, returning to sleep");
  go_to_sleep();
}
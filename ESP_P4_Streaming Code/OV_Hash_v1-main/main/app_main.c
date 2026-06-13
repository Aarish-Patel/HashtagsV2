#include "camera_pipeline.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "eth_init.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "http_server.h"
#include "perf_monitor.h"
#include "sdkconfig.h"
#include "uvc_controls.h"
#include "uvc_streaming.h"

static const char *TAG = "hashtag_node";

#define WAKEUP_GPIO GPIO_NUM_4
#define WAKEUP_GPIO_MASK (1ULL << WAKEUP_GPIO)
#define IR_LED_PIN GPIO_NUM_22
#define STREAM_DURATION_MS 30000 // 30 seconds, adjust as needed

static void go_to_sleep(void) {
  // Teardown ethernet cleanly
  eth_deinit();

  // IR LEDs off
  gpio_set_level(IR_LED_PIN, 0);

  gpio_config_t io_conf = {
      .pin_bit_mask = WAKEUP_GPIO_MASK,
      .mode = GPIO_MODE_INPUT,
      .pull_down_en = GPIO_PULLDOWN_ENABLE,
      .pull_up_en = GPIO_PULLUP_DISABLE,
      .intr_type = GPIO_INTR_DISABLE,
  };
  gpio_config(&io_conf);

  esp_sleep_enable_ext1_wakeup(WAKEUP_GPIO_MASK, ESP_EXT1_WAKEUP_ANY_HIGH);

  ESP_LOGI(TAG, "Entering deep sleep");
  fflush(stdout);
  esp_deep_sleep_start();
}

void app_main(void) {
  // IR LED pin setup - off by default
  gpio_config_t led_conf = {
      .pin_bit_mask = (1ULL << IR_LED_PIN),
      .mode = GPIO_MODE_OUTPUT,
      .pull_down_en = GPIO_PULLDOWN_DISABLE,
      .pull_up_en = GPIO_PULLUP_DISABLE,
      .intr_type = GPIO_INTR_DISABLE,
  };
  gpio_config(&led_conf);
  gpio_set_level(IR_LED_PIN, 0); // off until we need it

  // Check wakeup reason
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  if (cause != ESP_SLEEP_WAKEUP_EXT1) {
    ESP_LOGI(TAG, "Cold boot or non-motion wakeup - going to sleep");
    go_to_sleep();
    return;
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

  // Phase 4: Ethernet
  ret = eth_init();
  if (ret != ESP_OK) {
    ESP_LOGW(TAG, "Ethernet init failed: %s", esp_err_to_name(ret));
    go_to_sleep();
    return;
  }

  // Phase 5: HTTP server
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
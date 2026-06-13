/*
 * SPDX-FileCopyrightText: 2025
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "http_server.h"
#include "esp_check.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "linux/videodev2.h"
#include "sys/param.h"
#include "uvc_frame_config.h"
#include "uvc_streaming.h"
#include "uvc_controls.h"
#include <sys/ioctl.h>

static const char *TAG = "http_server";

#define PART_BOUNDARY "123456789000000000000987654321"
static const char *_STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char *_STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char *_STREAM_PART =
    "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static uvc_stream_ctx_t *s_uvc_ctx = NULL;
static volatile bool s_uvc_streaming = false;
static httpd_handle_t s_httpd = NULL;

void http_server_notify_uvc_start(void) { s_uvc_streaming = true; }

void http_server_notify_uvc_stop(void) { s_uvc_streaming = false; }

static esp_err_t stream_handler(httpd_req_t *req) {
  esp_err_t res = ESP_OK;
  char part_buf[128];

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) {
    return res;
  }

  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  if (!s_uvc_ctx) {
    ESP_LOGE(TAG, "UVC Context not set");
    return ESP_FAIL;
  }

  camera_ctx_t *cam = &s_uvc_ctx->camera;
  encoder_ctx_t *enc = &s_uvc_ctx->jpeg_enc;

  // We can't stream if UVC is using the camera
  if (s_uvc_streaming) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  // Start camera (UYVY for JPEG encoder)
  if (camera_start(cam, CAMERA_CAPTURE_WIDTH, CAMERA_CAPTURE_HEIGHT,
                   V4L2_PIX_FMT_UYVY) != ESP_OK) {
    ESP_LOGE(TAG, "Camera start failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  if (encoder_start(enc, CAMERA_CAPTURE_WIDTH, CAMERA_CAPTURE_HEIGHT,
                    V4L2_PIX_FMT_UYVY) != ESP_OK) {
    ESP_LOGE(TAG, "JPEG encoder start failed");
    camera_stop(cam);
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  ESP_LOGI(TAG, "MJPEG stream started (5 FPS Optimized Latency)");

  s_uvc_ctx->active_format = STREAM_FORMAT_MJPEG;
  s_uvc_ctx->negotiated_width = CAMERA_CAPTURE_WIDTH;
  s_uvc_ctx->negotiated_height = CAMERA_CAPTURE_HEIGHT;
  s_uvc_ctx->streaming = true;

  int64_t last_send_time = 0;

  while (true) {
    if (s_uvc_streaming) {
      ESP_LOGI(TAG, "UVC stream started, stopping HTTP stream");
      break;
    }

    uint32_t buf_idx, bytesused;
    if (camera_dequeue(cam, &buf_idx, &bytesused) != ESP_OK) {
      vTaskDelay(pdMS_TO_TICKS(5));
      continue;
    }

    int64_t now = esp_timer_get_time();
    // 5 FPS = 200,000 microseconds (200ms)
    if (now - last_send_time >= 200000) {
      // Apply heavy JPEG compression quality (15) to minimize bitrate
      uvc_ctrl_set_jpeg_quality(enc->m2m_fd, 15);

      uint8_t *enc_buf;
      uint32_t enc_len;
      esp_err_t enc_res = encoder_encode(enc, cam->cap_buffer[buf_idx], bytesused,
                                         &enc_buf, &enc_len);

      camera_enqueue(cam, buf_idx); // return buffer to camera immediately

      if (enc_res == ESP_OK && enc_len > 0) {
        res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY,
                                    strlen(_STREAM_BOUNDARY));
        if (res == ESP_OK) {
          size_t hlen =
              snprintf((char *)part_buf, sizeof(part_buf), _STREAM_PART, enc_len);
          res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
        }
        if (res == ESP_OK) {
          res = httpd_resp_send_chunk(req, (const char *)enc_buf, enc_len);
        }

        // Re-queue encoder capture buffer for next encode
        struct v4l2_buffer qbuf = {
            .index = 0,
            .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
            .memory = V4L2_MEMORY_MMAP,
        };
        ioctl(enc->m2m_fd, VIDIOC_QBUF, &qbuf);

        s_uvc_ctx->perf_frame_count++;
        s_uvc_ctx->perf_byte_count += enc_len;
        last_send_time = now;
      }
    } else {
      // Drop early frame to keep camera queue fresh (latency <20ms)
      camera_enqueue(cam, buf_idx);
    }

    if (res != ESP_OK) {
      ESP_LOGI(TAG, "Send chunk failed, client likely disconnected");
      break;
    }
  }

  encoder_stop(enc);
  camera_stop(cam);
  s_uvc_ctx->streaming = false;

  return res;
}

static const httpd_uri_t stream_uri = {.uri = "/stream",
                                       .method = HTTP_GET,
                                       .handler = stream_handler,
                                       .user_ctx = NULL};

esp_err_t http_server_start(void *uvc_ctx) {
  s_uvc_ctx = (uvc_stream_ctx_t *)uvc_ctx;
  s_uvc_streaming = false;

  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.max_uri_handlers = 8;
  config.server_port = 80;

  ESP_LOGI(TAG, "Starting web server on port: '%d'", config.server_port);
  if (httpd_start(&s_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(s_httpd, &stream_uri);
    return ESP_OK;
  }

  ESP_LOGE(TAG, "Error starting server!");
  return ESP_FAIL;
}

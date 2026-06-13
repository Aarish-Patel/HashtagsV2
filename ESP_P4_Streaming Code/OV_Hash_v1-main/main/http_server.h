/*
 * SPDX-FileCopyrightText: 2025
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Start the HTTP web server for MJPEG streaming
 *
 * @param uvc_ctx Pointer to the shared UVC context (used for camera access)
 * @return esp_err_t ESP_OK on success
 */
esp_err_t http_server_start(void *uvc_ctx);

/**
 * @brief Notify HTTP server that UVC streaming has started
 * 
 * If self-capture is active, this will stop it and yield the camera.
 */
void http_server_notify_uvc_start(void);

/**
 * @brief Notify HTTP server that UVC streaming has stopped
 * 
 * Allows HTTP server to resume self-capture if needed.
 */
void http_server_notify_uvc_stop(void);

#ifdef __cplusplus
}
#endif

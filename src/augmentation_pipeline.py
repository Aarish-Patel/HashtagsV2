"""
augmentation_pipeline.py — OV5647 Image Degradation & Augmentation Engine

Simulates the exact image quality produced by the OV5647 camera sensor
connected to the ESP32-P4 field node. Applied both at inference time
(webcam simulation) and at training time (dataset preparation).

Key characteristics replicated:
- 800x640 resolution
- JPEG quality 15 compression artifacts
- Magenta/pink color cast from ISP CCM overshoot
- Barrel lens distortion
- Sensor noise (day/night modes)
- IR LED illumination falloff pattern
- Motion blur from 2-5fps capture

Author: HashtagV2 System
"""

import cv2
import numpy as np
from typing import Tuple, Optional


class OV5647Degrader:
    """
    Applies the full chain of image degradations that the OV5647 camera
    produces in the field. This bridges the domain gap between clean
    training images and real deployment imagery.
    """

    def __init__(
        self,
        target_width: int = 800,
        target_height: int = 640,
        jpeg_quality: int = 15,
        r_gain: float = 1.25,
        g_gain: float = 0.82,
        b_gain: float = 0.93,
        saturation_scale: float = 0.85,
        noise_sigma_day: float = 5.0,
        noise_sigma_night: float = 18.0,
        distortion_k1: float = -0.04,
        distortion_k2: float = 0.02,
    ):
        self.target_w = target_width
        self.target_h = target_height
        self.jpeg_quality = jpeg_quality
        self.r_gain = r_gain
        self.g_gain = g_gain
        self.b_gain = b_gain
        self.saturation_scale = saturation_scale
        self.noise_sigma_day = noise_sigma_day
        self.noise_sigma_night = noise_sigma_night

        # Build camera matrix and distortion coefficients
        fx = fy = 500.0
        cx, cy = target_width / 2.0, target_height / 2.0
        self.K = np.array([
            [fx,  0.0, cx],
            [0.0, fy,  cy],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)
        self.D = np.array([distortion_k1, distortion_k2, 0.0, 0.0, 0.0], dtype=np.float64)

        # Pre-compute undistortion maps for the target resolution
        self._dist_map1, self._dist_map2 = cv2.initUndistortRectifyMap(
            self.K, self.D, None, self.K,
            (self.target_w, self.target_h), cv2.CV_16SC2
        )

    def apply_color_cast(self, frame: np.ndarray) -> np.ndarray:
        """
        Applies the magenta/pink color cast produced by the OV5647's ISP
        Daylight CCM profile. The CCM overshoots red and undershoots green,
        producing the characteristic pink tint visible in personOV.jpeg.
        """
        # Split channels (BGR)
        b, g, r = cv2.split(frame.astype(np.float32))

        # Apply per-channel gains matching the ISP CCM effect
        r = np.clip(r * self.r_gain, 0, 255)
        g = np.clip(g * self.g_gain, 0, 255)
        b = np.clip(b * self.b_gain, 0, 255)

        result = cv2.merge([b, g, r]).astype(np.uint8)

        # Apply overall desaturation (ISP processing loss)
        if self.saturation_scale < 1.0:
            hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] *= self.saturation_scale
            hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
            result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        return result

    def apply_jpeg_compression(self, frame: np.ndarray, quality: Optional[int] = None) -> np.ndarray:
        """
        Simulates the heavy JPEG compression (Q15) used on the ESP32-P4
        HTTP stream to minimize bandwidth over the low-rate link.
        """
        q = quality if quality is not None else self.jpeg_quality
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), q]
        _, encoded = cv2.imencode('.jpg', frame, encode_param)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    def apply_lens_distortion(self, frame: np.ndarray) -> np.ndarray:
        """
        Applies mild barrel distortion matching the OV5647 lens module.
        Uses the calibration from the V1 K_MATRIX and D_COEFFS.
        """
        if frame.shape[1] == self.target_w and frame.shape[0] == self.target_h:
            return cv2.remap(frame, self._dist_map1, self._dist_map2, cv2.INTER_LINEAR)
        else:
            # Recompute maps for this resolution
            h, w = frame.shape[:2]
            K = self.K.copy()
            K[0, 2] = w / 2.0
            K[1, 2] = h / 2.0
            m1, m2 = cv2.initUndistortRectifyMap(K, self.D, None, K, (w, h), cv2.CV_16SC2)
            return cv2.remap(frame, m1, m2, cv2.INTER_LINEAR)

    def apply_sensor_noise(self, frame: np.ndarray, night_mode: bool = False) -> np.ndarray:
        """
        Adds Gaussian sensor noise matching OV5647 characteristics.
        Night mode uses higher sigma simulating ISO gain amplification.
        """
        sigma = self.noise_sigma_night if night_mode else self.noise_sigma_day
        noise = np.random.normal(0, sigma, frame.shape).astype(np.float32)
        noisy = np.clip(frame.astype(np.float32) + noise, 0, 255)
        return noisy.astype(np.uint8)

    def apply_ir_illumination(self, frame: np.ndarray) -> np.ndarray:
        """
        Simulates the IR LED illumination falloff pattern at night.
        The IR LEDs (GPIO22 on ESP32-P4) produce a circular hotspot
        centered on the frame with brightness falling off at edges.
        """
        h, w = frame.shape[:2]
        cx, cy = w / 2.0, h / 2.0
        max_r = np.sqrt(cx ** 2 + cy ** 2)

        # Create radial falloff mask
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / max_r
        # Falloff: 100% at center, ~40% at edges
        falloff = np.clip(1.0 - 0.6 * (dist / 0.7) ** 2, 0.4, 1.0)

        frame_f = frame.astype(np.float32)
        for c in range(3):
            frame_f[:, :, c] *= falloff
        return np.clip(frame_f, 0, 255).astype(np.uint8)

    def apply_night_mode(self, frame: np.ndarray) -> np.ndarray:
        """
        Simulates the OV5647 in near-IR mode (IR-cut filter removed).
        Converts to grayscale with IR-like tonal response and applies
        IR LED illumination pattern.
        """
        # Convert to grayscale (IR sensors see all channels similarly)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Near-IR has higher sensitivity to red/NIR — weight channels
        b, g, r = cv2.split(frame.astype(np.float32))
        ir_response = np.clip(r * 0.5 + g * 0.3 + b * 0.2, 0, 255).astype(np.uint8)

        # Convert back to 3-channel grayscale for pipeline compatibility
        ir_frame = cv2.merge([ir_response, ir_response, ir_response])

        # Apply IR LED illumination falloff
        ir_frame = self.apply_ir_illumination(ir_frame)

        # Higher noise in IR mode
        ir_frame = self.apply_sensor_noise(ir_frame, night_mode=True)

        return ir_frame

    def apply_motion_blur(self, frame: np.ndarray, angle: float = 0.0, length: int = 5) -> np.ndarray:
        """
        Simulates motion blur from moving subjects captured at 2-5fps.
        """
        if length < 2:
            return frame

        # Create motion blur kernel
        kernel = np.zeros((length, length), dtype=np.float32)
        rad = np.deg2rad(angle)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        center = length // 2

        for i in range(length):
            offset = i - center
            x = int(center + offset * cos_a)
            y = int(center + offset * sin_a)
            if 0 <= x < length and 0 <= y < length:
                kernel[y, x] = 1.0

        kernel /= max(kernel.sum(), 1.0)
        return cv2.filter2D(frame, -1, kernel)

    def degrade_full(
        self,
        frame: np.ndarray,
        night_mode: bool = False,
        motion_blur_angle: float = 0.0,
        motion_blur_length: int = 0,
    ) -> np.ndarray:
        """
        Applies the FULL OV5647 degradation chain to produce imagery
        matching what the real field node transmits.

        Pipeline order matters — matches the real camera's processing:
        1. Resize to sensor resolution
        2. Apply lens distortion
        3. Apply color cast (ISP CCM) OR night mode
        4. Add sensor noise
        5. Apply motion blur (if any)
        6. JPEG compress at Q15 (the bandwidth bottleneck)
        """
        # Step 1: Resize to OV5647 native output
        frame = cv2.resize(frame, (self.target_w, self.target_h), interpolation=cv2.INTER_AREA)

        # Step 2: Lens distortion
        frame = self.apply_lens_distortion(frame)

        # Step 3: Color processing
        if night_mode:
            frame = self.apply_night_mode(frame)
        else:
            frame = self.apply_color_cast(frame)
            frame = self.apply_sensor_noise(frame, night_mode=False)

        # Step 4: Motion blur (if subject is moving)
        if motion_blur_length > 1:
            frame = self.apply_motion_blur(frame, motion_blur_angle, motion_blur_length)

        # Step 5: JPEG compression (the biggest quality killer)
        frame = self.apply_jpeg_compression(frame)

        return frame


class TrainingAugmentor:
    """
    Extended augmentation for training data preparation.
    Applies randomized degradations to make models robust to OV5647 output.
    """

    def __init__(self, degrader: Optional[OV5647Degrader] = None):
        self.degrader = degrader or OV5647Degrader()

    def random_ov5647_degrade(self, frame: np.ndarray) -> np.ndarray:
        """
        Randomly varies the OV5647 degradation parameters to create
        diverse training samples covering the full range of field conditions.
        """
        # Random JPEG quality (Q10-Q25 range)
        q = np.random.randint(10, 26)

        # Random color cast intensity (0.7-1.0 of full cast)
        cast_strength = np.random.uniform(0.7, 1.0)
        r_g = 1.0 + (self.degrader.r_gain - 1.0) * cast_strength
        g_g = 1.0 + (self.degrader.g_gain - 1.0) * cast_strength
        b_g = 1.0 + (self.degrader.b_gain - 1.0) * cast_strength

        # Random noise
        sigma = np.random.uniform(3, 20)

        # Random motion blur
        blur_len = np.random.choice([0, 0, 0, 3, 5, 7])  # 50% chance no blur
        blur_angle = np.random.uniform(0, 360)

        # Random night mode (20% chance)
        night = np.random.random() < 0.2

        # Resize
        frame = cv2.resize(frame, (self.degrader.target_w, self.degrader.target_h),
                           interpolation=cv2.INTER_AREA)

        if night:
            frame = self.degrader.apply_night_mode(frame)
        else:
            # Apply varied color cast
            bf, gf, rf = cv2.split(frame.astype(np.float32))
            rf = np.clip(rf * r_g, 0, 255)
            gf = np.clip(gf * g_g, 0, 255)
            bf = np.clip(bf * b_g, 0, 255)
            frame = cv2.merge([bf, gf, rf]).astype(np.uint8)

            # Noise
            noise = np.random.normal(0, sigma, frame.shape).astype(np.float32)
            frame = np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # Motion blur
        if blur_len > 1:
            frame = self.degrader.apply_motion_blur(frame, blur_angle, blur_len)

        # JPEG compression
        frame = self.degrader.apply_jpeg_compression(frame, quality=q)

        # Random brightness/contrast shift (simulating time-of-day)
        alpha = np.random.uniform(0.7, 1.3)   # contrast
        beta = np.random.randint(-30, 31)      # brightness
        frame = np.clip(frame.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

        return frame

    def simulate_partial_occlusion(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Randomly occludes part of a person bounding box to simulate
        vegetation, terrain features, or concealment.
        """
        x, y, w, h = bbox
        frame_copy = frame.copy()

        # Random occlusion: cover 20-60% of the bounding box
        occ_frac = np.random.uniform(0.2, 0.6)
        occ_h = int(h * occ_frac)

        # Decide occlusion position (bottom = behind bush, top = behind wall)
        if np.random.random() < 0.6:
            # Bottom occlusion (most common in outdoor — behind terrain)
            oy = y + h - occ_h
        else:
            # Side/top occlusion
            oy = y

        # Fill with nearby background color (not just black)
        bg_region = frame[max(0, oy - 5):min(frame.shape[0], oy + 5),
                          max(0, x - 5):min(frame.shape[1], x + 5)]
        if bg_region.size > 0:
            fill_color = bg_region.mean(axis=(0, 1)).astype(np.uint8)
        else:
            fill_color = np.array([80, 100, 60], dtype=np.uint8)  # earthy green

        frame_copy[oy:oy + occ_h, x:x + w] = fill_color

        return frame_copy

    def simulate_ghillie_texture(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Overlays a procedural foliage-like texture onto a person bounding
        box to simulate ghillie suit appearance. Since no ghillie suit
        dataset exists, this synthetic augmentation is critical.
        """
        x, y, w, h = bbox
        if w < 5 or h < 5:
            return frame

        frame_copy = frame.copy()

        # Extract the person region
        roi = frame_copy[y:y + h, x:x + w].copy()

        # Generate procedural foliage texture
        # Use fractal-like noise to create bush/grass patterns
        noise_scale = np.random.uniform(0.02, 0.06)
        texture = np.zeros((h, w, 3), dtype=np.float32)

        # Base foliage colors (earth tones: browns, greens, tans)
        base_colors = [
            (40, 80, 30),    # dark green
            (50, 100, 50),   # medium green
            (60, 90, 70),    # olive
            (80, 110, 90),   # light olive
            (70, 80, 60),    # brown-green
        ]

        # Create random patches of foliage color
        for _ in range(int(w * h * 0.01)):
            px = np.random.randint(0, max(1, w))
            py = np.random.randint(0, max(1, h))
            color = base_colors[np.random.randint(0, len(base_colors))]
            radius = np.random.randint(2, max(3, min(w, h) // 6))
            cv2.circle(texture, (px, py), radius, color, -1)

        # Blur the texture to look natural
        texture = cv2.GaussianBlur(texture, (7, 7), 3.0)

        # Blend with the person region (30-70% opacity)
        opacity = np.random.uniform(0.3, 0.7)
        blended = cv2.addWeighted(roi.astype(np.float32), 1.0 - opacity,
                                   texture, opacity, 0)

        frame_copy[y:y + h, x:x + w] = np.clip(blended, 0, 255).astype(np.uint8)

        return frame_copy

    def simulate_distance_scaling(self, frame: np.ndarray, scale_factor: float = 0.3) -> np.ndarray:
        """
        Simulates a person at long range by downscaling and then upscaling,
        producing the aliasing and loss of detail seen at 50-100m distances.
        """
        h, w = frame.shape[:2]

        # Downscale
        small_w = max(8, int(w * scale_factor))
        small_h = max(8, int(h * scale_factor))
        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)

        # Upscale back (introduces blocky artifacts)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

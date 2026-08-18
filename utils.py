# utils.py
# 通用工具：屏幕截图、图像处理、鼠标轨迹、按键解析等

import ctypes
import math
import os
import random
import time

import cv2
import numpy as np
import pyautogui
import platform

from definitions import KEY_NAME_ALIAS, SHIFT_CHAR_MAP


# ── Windows 光标坐标结构体 ──
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


# Windows 下设置 DPI 感知，避免高分屏缩放导致坐标不准
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"

_user32 = ctypes.windll.user32


# ── 尝试加载 dxcam（高性能 DXGI 截图库） ──
try:
    import dxcam

    HAS_DXCAM = True
except ImportError:
    HAS_DXCAM = False

_DXCAM_INSTANCE = None


class Utils:
    # ================================================================
    #  屏幕 / 截图相关
    # ================================================================

    @staticmethod
    def get_screen_size():
        """获取主显示器分辨率 (宽, 高)"""
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        return w, h

    @staticmethod
    def init_dxcam():
        """初始化 DXGI 截图引擎（仅首次调用生效）"""
        global _DXCAM_INSTANCE
        if HAS_DXCAM and _DXCAM_INSTANCE is None:
            try:
                _DXCAM_INSTANCE = dxcam.create(output_color="BGR")
                print("DXGI 截图引擎初始化成功")
            except Exception as e:
                print(f"DXGI 初始化失败: {e}")
                _DXCAM_INSTANCE = None

    @staticmethod
    def grab_screen(region=None):
        """截取屏幕，优先使用 dxcam，失败则回退到 pyautogui
        region: (x, y, w, h) 或 None（全屏）
        """
        global _DXCAM_INSTANCE
        if _DXCAM_INSTANCE:
            try:
                if region:
                    x, y, w, h = region
                    return _DXCAM_INSTANCE.grab(region=(x, y, x + w, y + h))
                else:
                    return _DXCAM_INSTANCE.grab()
            except Exception:
                pass
        # 回退方案：pyautogui 截图
        try:
            pil_img = pyautogui.screenshot(region=region)
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"截图失败: {e}")
            return None

    # ================================================================
    #  图像读取 / 处理
    # ================================================================

    @staticmethod
    def read_image_safe(path):
        """安全读取图片文件，支持中文路径"""
        if not os.path.exists(path):
            return None
        try:
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            return img
        except Exception as e:
            print(f"读取图片失败: {e}")
            return None

    @staticmethod
    def resize_image(img, ratio):
        """按比例缩放图片，缩小用 INTER_AREA，放大用 INTER_LINEAR"""
        if img is None or ratio == 1.0:
            return img
        h, w = img.shape[:2]
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        if new_w <= 0 or new_h <= 0:
            return img
        interpolation = cv2.INTER_AREA if ratio < 1.0 else cv2.INTER_LINEAR
        return cv2.resize(img, (new_w, new_h), interpolation=interpolation)

    @staticmethod
    def get_canny_edge(img):
        """提取图片的 Canny 边缘（灰度→高斯模糊→Canny→膨胀）"""
        if img is None:
            return None
        if len(img.shape) == 3 and img.shape[2] == 4:
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((3, 3), np.uint8)
        dilated_edges = cv2.dilate(edges, kernel, iterations=1)
        return dilated_edges

    @staticmethod
    def match_template(screen_img, template_img, confidence=0.7, return_max_val=False):
        """模板匹配，支持带 Alpha 通道的模板（自动生成 mask）
        返回匹配中心坐标；return_max_val=True 时额外返回匹配度
        """
        if screen_img is None or template_img is None:
            return (None, None, 0.0) if return_max_val else None
        try:
            h_img, w_img = screen_img.shape[:2]
            h_tpl, w_tpl = template_img.shape[:2]
            # 模板比截图大则直接返回
            if h_img < h_tpl or w_img < w_tpl:
                return (None, None, 0.0) if return_max_val else None

            # 统一截图为 BGR
            if len(screen_img.shape) == 3 and screen_img.shape[2] == 4:
                screen_img = cv2.cvtColor(screen_img, cv2.COLOR_BGRA2BGR)

            # 若模板含 Alpha 通道，拆出 mask
            mask = None
            template_bgr = template_img
            if len(template_img.shape) == 3 and template_img.shape[2] == 4:
                b, g, r, a = cv2.split(template_img)
                template_bgr = cv2.merge((b, g, r))
                mask = a

            # 有 mask 时用 CCORR_NORMED，否则用 CCOEFF_NORMED
            if mask is not None:
                res = cv2.matchTemplate(screen_img, template_bgr, cv2.TM_CCORR_NORMED, mask=mask)
            else:
                res = cv2.matchTemplate(screen_img, template_bgr, cv2.TM_CCOEFF_NORMED)

            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val < confidence:
                return (None, None, max_val) if return_max_val else None

            # 计算匹配区域中心点
            h, w = template_bgr.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val) if return_max_val else (center_x, center_y)
        except Exception as e:
            print(f"匹配异常: {e}")
            return (None, None, 0.0) if return_max_val else None

    # ================================================================
    #  鼠标 / 坐标相关
    # ================================================================

    @staticmethod
    def get_cursor_pos():
        """获取当前鼠标光标的屏幕坐标"""
        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    @staticmethod
    def get_distance(x1, y1, x2, y2):
        """计算两点之间的欧氏距离"""
        return math.hypot(x2 - x1, y2 - y1)

    @staticmethod
    def get_bezier_curve(start_pos, end_pos, control_points, steps):
        """生成三阶贝塞尔曲线路径点列表，用于模拟鼠标平滑移动"""
        t = np.linspace(0, 1, steps)
        path_x = (
            (1 - t) ** 3 * start_pos[0]
            + 3 * (1 - t) ** 2 * t * control_points[0][0]
            + 3 * (1 - t) * t**2 * control_points[1][0]
            + t**3 * end_pos[0]
        )
        path_y = (
            (1 - t) ** 3 * start_pos[1]
            + 3 * (1 - t) ** 2 * t * control_points[0][1]
            + 3 * (1 - t) * t**2 * control_points[1][1]
            + t**3 * end_pos[1]
        )
        return list(zip(path_x, path_y))

    @staticmethod
    def stochastic_round(val):
        """依小数位作为概率对小数进行取整"""
        int_part = int(val)
        frac_part = abs(val - int_part)
        if random.random() < frac_part:
            return int_part + (1 if val > 0 else -1)
        return int_part

    # ================================================================
    #  随机化 / 时间控制
    # ================================================================

    @staticmethod
    def get_gaussian_offset(x, y, range_val):
        """在 (x, y) 附近按高斯分布生成随机偏移坐标，range_val 为最大偏移量"""
        if range_val <= 0:
            return int(x), int(y)
        sigma = range_val / 3
        offset_x = random.gauss(0, sigma)
        offset_y = random.gauss(0, sigma)
        final_x = int(x + max(-range_val, min(range_val, offset_x)))
        final_y = int(y + max(-range_val, min(range_val, offset_y)))
        return final_x, final_y

    @staticmethod
    def get_random_time(min_ms, max_ms):
        """在 [min_ms, max_ms] 毫秒范围内生成高斯随机延时，返回秒"""
        if min_ms >= max_ms:
            return min_ms / 1000.0
        mu = (min_ms + max_ms) / 2
        sigma = (max_ms - min_ms) / 6
        val = random.gauss(mu, sigma)
        val = max(min_ms, min(max_ms, val))
        return val / 1000.0

    @staticmethod
    def precise_wait(target_time):
        """高精度等待"""
        while True:
            rem = target_time - time.perf_counter()
            if rem <= 0:
                break
            if rem > 0.002:
                time.sleep(0.001)
            else:
                pass

    # ================================================================
    #  按键名称解析 / 映射
    # ================================================================

    @staticmethod
    def tokenize_key_code(key_code):
        """将按键字符串按 '+' 拆分为 token 列表，支持字符串、列表、元组输入"""
        if isinstance(key_code, str):
            raw = key_code.strip()
            if not raw:
                return []
            tokens = []
            buf = ""
            for ch in raw:
                if ch == "+":
                    if buf.strip():
                        tokens.append(buf.strip())
                        buf = ""
                    else:
                        # 单独的 '+' 字符本身作为按键
                        tokens.append("+")
                else:
                    buf += ch
            if buf.strip():
                tokens.append(buf.strip())
            return tokens
        elif isinstance(key_code, (list, tuple)):
            return [str(k).strip() for k in key_code if str(k).strip()]
        else:
            text = str(key_code).strip()
            return [text] if text else []

    @staticmethod
    def normalize_key_code(key_code):
        """将按键 token 规范化：别名替换、大写字母拆为 shift+小写、去重"""
        raw_tokens = Utils.tokenize_key_code(key_code)
        if not raw_tokens:
            return []
        result = []
        for token in raw_tokens:
            token = token.strip()
            if not token:
                continue
            # 查找别名映射
            alias = KEY_NAME_ALIAS.get(token.lower(), token)
            # 单个大写字母 → shift + 小写
            if len(alias) == 1 and alias.isalpha() and alias.isupper():
                result.extend(["shift", alias.lower()])
                continue
            # 需要 shift 的特殊字符（如 ! → shift+1）
            if alias in SHIFT_CHAR_MAP:
                result.extend(SHIFT_CHAR_MAP[alias])
                continue
            # 多字符键名或字母统一小写
            if len(alias) > 1 or alias.isalpha():
                result.append(alias.lower())
            else:
                result.append(alias)
        # 去重并保持顺序
        final_keys = []
        seen = set()
        for k in result:
            if k not in seen:
                final_keys.append(k)
                seen.add(k)
        return final_keys

    @staticmethod
    def map_key_names(keys, key_map):
        """将规范化后的按键名称映射为底层扫描码/虚拟键码"""
        mapped_codes = []
        unsupported_keys = []
        for k in keys:
            if k in key_map:
                mapped_codes.append(key_map[k])
            else:
                unsupported_keys.append(k)
        return mapped_codes, unsupported_keys


# ================================================================
#  色彩处理
# ================================================================
from dataclasses import dataclass
from typing import Tuple, List


@dataclass
class ColorStats:
    rgb_min: Tuple[int, int, int]
    rgb_max: Tuple[int, int, int]
    hsv_min: Tuple[float, float, float]
    hsv_max: Tuple[float, float, float]


class ColorUtils:
    @staticmethod
    def hsv_circular_min_interval(hues: np.ndarray) -> Tuple[float, float]:
        """计算色相范围的最短距离区间"""
        if len(hues) == 0:
            return (0.0, 0.0)
        hs = np.sort(hues % 360.0)
        if np.all(np.abs(hs - hs[0]) < 1e-6):
            return (float(hs[0]), float(hs[0]))
        gaps = [(hs[i + 1] - hs[i], i, i + 1) for i in range(len(hs) - 1)]
        gaps.append(((hs[0] + 360.0) - hs[-1], len(hs) - 1, 0))
        max_gap, i, j = max(gaps, key=lambda x: x[0])
        return (float(hs[j]), float(hs[i]))

    @staticmethod
    def rgb_to_hsv_cv2(rgb_arr: np.ndarray) -> np.ndarray:
        """RGB 转 HSV"""
        rgb_normalized = (rgb_arr / 255.0).astype(np.float32)
        rgb_reshaped = rgb_normalized.reshape(1, -1, 3)
        hsv_reshaped = cv2.cvtColor(rgb_reshaped, cv2.COLOR_RGB2HSV)
        return hsv_reshaped.reshape(-1, 3)

    @staticmethod
    def analyze_samples(samples: List[Tuple[int, int, int]]) -> dict:
        """计算取色采样 RGB/HSV 的极值和中心色值"""
        arr_rgb = np.array(samples)
        r_min, g_min, b_min = arr_rgb.min(axis=0)
        r_max, g_max, b_max = arr_rgb.max(axis=0)
        r_mean, g_mean, b_mean = arr_rgb.mean(axis=0)
        hex_code = f"#{int(r_mean):02X}{int(g_mean):02X}{int(b_mean):02X}"

        arr_hsv = ColorUtils.rgb_to_hsv_cv2(arr_rgb)
        hues = arr_hsv[:, 0]
        svals = arr_hsv[:, 1] * 255.0
        vvals = arr_hsv[:, 2] * 255.0

        h_start, h_end = ColorUtils.hsv_circular_min_interval(hues)
        s_min, s_max = svals.min(), svals.max()
        v_min, v_max = vvals.min(), vvals.max()

        return {
            "rgb_min": (r_min, g_min, b_min),
            "rgb_max": (r_max, g_max, b_max),
            "hsv_min": (h_start, s_min, v_min),
            "hsv_max": (h_end, s_max, v_max),
            "hex_code": hex_code,
        }

    @staticmethod
    def generate_hsv_gradient_matrix(
        h_start: float, h_end: float, s_min: float, s_max: float, v_val: float, width=200, height=100
    ) -> np.ndarray:
        """生成 HSV 范围渐变矩阵"""
        if h_end < h_start:
            h_end += 360.0
        h_arr = (np.linspace(h_start, h_end, width) % 360.0) / 360.0
        s_arr = np.linspace(s_max, s_min, height) / 255.0
        H, S = np.meshgrid(h_arr, s_arr)
        V = np.full_like(H, v_val / 255.0)
        hsv_image = np.dstack((H * 360.0, S, V)).astype(np.float32)
        rgb_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2RGB)
        return (rgb_image * 255).astype(np.uint8)

    @staticmethod
    def hex_to_hsv(hex_str: str) -> Tuple[float, float, float]:
        """Hex 转标准 HSV"""
        hex_str = hex_str.lstrip("#")
        if len(hex_str) != 6:
            return 0.0, 0.0, 0.0
        try:
            r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
        except ValueError:
            return 0.0, 0.0, 0.0
        arr = np.array([[r, g, b]])
        hsv = ColorUtils.rgb_to_hsv_cv2(arr)[0]
        return float(hsv[0]), float(hsv[1] * 255.0), float(hsv[2] * 255.0)

    @staticmethod
    def get_basic_hsv_ranges(hex_str: str, tolerance: int) -> dict:
        """基础模式：根据中心色和容差，计算出 UI 显示的范围和 OpenCV 使用的范围"""
        hc, sc, vc = ColorUtils.hex_to_hsv(hex_str)
        t = max(0, min(100, tolerance))

        # 实际偏移量
        delta_h = (t / 100.0) * 20.0
        delta_s = (t / 100.0) * 255 * 0.6
        delta_v = (t / 100.0) * 255 * 0.75

        # 限制极值范围
        s_min, s_max = max(0, sc - delta_s), min(255, sc + delta_s)
        v_min, v_max = max(0, vc - delta_v), min(255, vc + delta_v)

        h_start = (hc - delta_h) % 360.0
        h_end = (hc + delta_h) % 360.0

        # OpenCV 底层所需数据
        cv_s_min, cv_s_max = int(s_min), int(s_max)
        cv_v_min, cv_v_max = int(v_min), int(v_max)
        hsv_ranges = []

        if hc - delta_h < 0:
            hsv_ranges.append(((0, cv_s_min, cv_v_min), (int(h_end / 2), cv_s_max, cv_v_max)))
            hsv_ranges.append(((int((360 + hc - delta_h) / 2), cv_s_min, cv_v_min), (180, cv_s_max, cv_v_max)))
        elif hc + delta_h >= 360:
            hsv_ranges.append(((int(h_start / 2), cv_s_min, cv_v_min), (180, cv_s_max, cv_v_max)))
            hsv_ranges.append(((0, cv_s_min, cv_v_min), (int((hc + delta_h - 360) / 2), cv_s_max, cv_v_max)))
        else:
            hsv_ranges.append(((int(h_start / 2), cv_s_min, cv_v_min), (int(h_end / 2), cv_s_max, cv_v_max)))

        raw_values = {
            "h_start": float(h_start),
            "h_end": float(h_end),
            "s_min": int(s_min),
            "s_max": int(s_max),
            "v_min": int(v_min),
            "v_max": int(v_max),
        }

        return {"hsv_ranges": hsv_ranges, "raw_values": raw_values}

    @staticmethod
    def get_advanced_hsv_ranges(h_start: float, h_end: float, s_min: int, s_max: int, v_min: int, v_max: int) -> list:
        """高级模式：将 HSV 极值转换为 OpenCV 使用的范围"""
        h_s, h_e = int(h_start / 2), int(h_end / 2)
        s_s, s_e = int(s_min), int(s_max)
        v_s, v_e = int(v_min), int(v_max)

        if h_s <= h_e:
            return [((h_s, s_s, v_s), (h_e, s_e, v_e))]
        else:
            return [((h_s, s_s, v_s), (180, s_e, v_e)), ((0, s_s, v_s), (h_e, s_e, v_e))]

    @staticmethod
    def calc_tolerance_from_ranges(
        hex_str: str, h_start: float, h_end: float, s_min: float, s_max: float, v_min: float, v_max: float
    ) -> int:
        """反向推导：计算 HSV 的包围容差"""
        import math

        hc, sc, vc = ColorUtils.hex_to_hsv(hex_str)

        # 计算各个维度与中心色的最大偏差
        dist_h_start = min(abs(h_start - hc), 360.0 - abs(h_start - hc))
        dist_h_end = min(abs(h_end - hc), 360.0 - abs(h_end - hc))
        max_h_dist = max(dist_h_start, dist_h_end)

        max_s_dist = max(abs(s_min - sc), abs(s_max - sc))
        max_v_dist = max(abs(v_min - vc), abs(v_max - vc))

        # 反推容差
        t_h = (max_h_dist / 20.0) * 100.0
        t_s = (max_s_dist / (255 * 0.6)) * 100.0
        t_v = (max_v_dist / (255 * 0.75)) * 100.0

        if t_h < 0.1:
            t_h = 0.0
        if t_s < 0.1:
            t_s = 0.0
        if t_v < 0.1:
            t_v = 0.0

        tolerance = int(math.ceil(max(t_h, t_s, t_v)))
        return max(0, min(100, tolerance))

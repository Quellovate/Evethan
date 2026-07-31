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

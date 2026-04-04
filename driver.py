# driver.py
# 底层硬件/软件键鼠操作驱动，以及 OpenCV 图像识别
import os
import random
import time
from typing import Tuple

import pyautogui

from collections import OrderedDict

from utils import Utils

try:
    import lgdriver

    HAS_LG_DRIVER_FILE = True
except ImportError:
    HAS_LG_DRIVER_FILE = False
    print("未找到 lgdriver，将仅支持软件模拟")

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01


class TargetDriver:
    """负责通过固定坐标、相对坐标或图像匹配获取屏幕坐标"""

    def __init__(self, max_cache_size=100):
        self._image_cache = OrderedDict()  # LRU 图片模板缓存
        self.max_cache_size = max_cache_size
        Utils.init_dxcam()

    def clear_cache(self):
        """清空图片模板缓存"""
        self._image_cache.clear()
        print("图片缓存已清理")

    def get_fixed_coordinate(self, x, y, random_range=0):
        """获取固定坐标（带高斯随机偏移）"""
        return Utils.get_gaussian_offset(x, y, random_range)

    def get_relative_coordinate(self, dx, dy, random_range=0):
        """获取相对于当前鼠标位置的坐标（带高斯随机偏移）"""
        current_x, current_y = Utils.get_cursor_pos()
        return Utils.get_gaussian_offset(current_x + dx, current_y + dy, random_range)

    def get_image_coordinate(
        self, image_path, confidence=0.7, offset_x=0, offset_y=0, random_range=0, region=None, env_w=0, env_h=0
    ):
        """通过图像模板匹配获取目标在屏幕上的坐标，支持多尺度和边缘检测匹配"""
        if not os.path.exists(image_path):
            return None

        # 根据当前屏幕分辨率与环境分辨率计算缩放比例
        _, current_h = Utils.get_screen_size()
        base_ratio = (current_h / env_h) if env_h > 0 else 1.0

        scaled_offset_x = int(offset_x * base_ratio)
        scaled_offset_y = int(offset_y * base_ratio)

        # 计算搜索区域（如指定 region）
        search_region = None
        region_offset_x, region_offset_y = 0, 0
        if region and len(region) == 4 and (region[2] > 0 or region[3] > 0):
            rx = int(region[0] * base_ratio)
            ry = int(region[1] * base_ratio)
            rw = int(region[2] * base_ratio)
            rh = int(region[3] * base_ratio)
            search_region = (rx, ry, rw, rh)
            region_offset_x = rx
            region_offset_y = ry

        # 构建缓存 key，命中则复用，否则生成多尺度模板并缓存
        cache_key = f"{image_path}_{base_ratio:.3f}"
        if cache_key in self._image_cache:
            self._image_cache.move_to_end(cache_key)  # 刷新 LRU 顺序
        else:
            raw_img = Utils.read_image_safe(image_path)
            if raw_img is None:
                return None

            # 生成多个缩放比例的彩色模板
            scales = [1.0, 0.98, 1.02, 0.96, 1.04]
            color_templates = {}
            for s in scales:
                actual_ratio = base_ratio * s
                color_templates[s] = Utils.resize_image(raw_img, actual_ratio)

            # 生成 Canny 边缘模板（用于兜底匹配）
            base_template = color_templates[1.0]
            canny_template = Utils.get_canny_edge(base_template)

            # 生成缩小版模板（用于快速预筛选）
            color_small = {s: Utils.resize_image(img, 0.5) for s, img in color_templates.items()}
            canny_small = Utils.resize_image(canny_template, 0.5) if canny_template is not None else None

            # 淘汰最旧的缓存项
            if len(self._image_cache) >= self.max_cache_size:
                self._image_cache.popitem(last=False)

            self._image_cache[cache_key] = {
                "color": color_templates,
                "canny": canny_template,
                "scales": scales,
                "color_small": color_small,
                "canny_small": canny_small,
                "base_shape": (base_template.shape[1], base_template.shape[0]),
            }

        cache_data = self._image_cache[cache_key]

        # 截取屏幕图像
        screen_img = Utils.grab_screen(region=search_region)
        if screen_img is None:
            return None

        match_result = None

        # === 第一层：用原始尺度彩色模板直接匹配 ===
        tier1_res = Utils.match_template(screen_img, cache_data["color"][1.0], confidence, return_max_val=True)
        tier1_x, tier1_y, base_max_val = tier1_res

        if tier1_x is not None:
            match_result = (tier1_x, tier1_y)
        else:
            # 最大匹配值低于阈值则跳过后续尝试
            cutoff_threshold = confidence * 0.80

            if base_max_val >= cutoff_threshold:
                screen_h, screen_w = screen_img.shape[:2]
                target_w, target_h = cache_data["base_shape"]
                can_downscale = screen_h >= 200 and screen_w >= 200 and target_w >= 32 and target_h >= 32

                if can_downscale:
                    # === 第二层：缩小图上用其他尺度快速预筛 ===
                    screen_small = Utils.resize_image(screen_img, 0.5)
                    best_candidate = None

                    tier2_conf = confidence * 0.85
                    for s in cache_data["scales"][1:]:
                        res_s = Utils.match_template(screen_small, cache_data["color_small"][s], tier2_conf)
                        if res_s:
                            best_candidate = ("color", s, res_s)
                            break

                    # === 第三层：缩小图上用 Canny 边缘匹配 ===
                    if not best_candidate and cache_data["canny_small"] is not None:
                        tier3_conf = confidence * 0.80
                        screen_canny_small = Utils.get_canny_edge(screen_small)
                        res_s = Utils.match_template(screen_canny_small, cache_data["canny_small"], tier3_conf)
                        if res_s:
                            best_candidate = ("canny", 1.0, res_s)

                    # 对预筛结果在原图 ROI 区域进行精确验证
                    if best_candidate:
                        ttype, tscale, res_s = best_candidate
                        cx_r, cy_r = int(res_s[0] * 2), int(res_s[1] * 2)  # 还原到原始分辨率坐标

                        target_tpl = cache_data["color"][tscale] if ttype == "color" else cache_data["canny"]
                        th, tw = target_tpl.shape[:2]

                        # 裁剪 ROI 区域
                        roi_x1 = max(0, cx_r - tw)
                        roi_y1 = max(0, cy_r - th)
                        roi_x2 = min(screen_w, cx_r + tw)
                        roi_y2 = min(screen_h, cy_r + th)

                        roi_img = screen_img[roi_y1:roi_y2, roi_x1:roi_x2]

                        if ttype == "canny":
                            roi_eval = Utils.get_canny_edge(roi_img)
                            verify_conf = confidence * 0.85
                        else:
                            roi_eval = roi_img
                            verify_conf = confidence * 0.9

                        res_v = Utils.match_template(roi_eval, target_tpl, verify_conf)
                        if res_v:
                            match_result = (roi_x1 + res_v[0], roi_y1 + res_v[1])
                else:
                    # 图像太小无法缩放，直接在原图上尝试其他尺度
                    tier2_conf = confidence * 0.9
                    for s in cache_data["scales"][1:]:
                        res = Utils.match_template(screen_img, cache_data["color"][s], tier2_conf)
                        if res:
                            match_result = res
                            break

                    # Canny 边缘匹配
                    if not match_result and cache_data["canny"] is not None:
                        tier3_conf = confidence * 0.85
                        screen_canny = Utils.get_canny_edge(screen_img)
                        res = Utils.match_template(screen_canny, cache_data["canny"], tier3_conf)
                        if res:
                            match_result = res

        # 将局部坐标转换为屏幕绝对坐标并加上偏移
        if match_result:
            local_x, local_y = match_result
            final_x = region_offset_x + local_x + scaled_offset_x
            final_y = region_offset_y + local_y + scaled_offset_y
            return Utils.get_gaussian_offset(final_x, final_y, random_range)

        return None


class ActionDriver:
    """封装鼠标移动/点击/拖拽/滚轮和键盘操作，支持硬件模拟与软件模拟两种模式"""

    DRIVER_DETECTED = False  # 类级别标志：硬件驱动是否可用

    def __init__(self, use_hardware=True):
        self.use_driver = False
        self.lg_device = None
        self.lg_mouse = None
        self.lg_keyboard = None

        driver_files_exist = HAS_LG_DRIVER_FILE

        # 检测硬件驱动设备是否可用
        if driver_files_exist:
            try:
                temp_device = lgdriver.Device()
                temp_device.close()
                ActionDriver.DRIVER_DETECTED = True
            except:
                ActionDriver.DRIVER_DETECTED = False

        user_wants_hardware = use_hardware

        # 根据检测结果和用户选择决定使用哪种模式
        if ActionDriver.DRIVER_DETECTED and user_wants_hardware:
            try:
                self.lg_device = lgdriver.Device()
                self.lg_mouse = lgdriver.Mouse(self.lg_device)
                self.lg_keyboard = lgdriver.Keyboard(self.lg_device)
                self.use_driver = True
                print("硬件模拟已启用")
            except Exception as e:
                print(f"硬件模拟启用失败: {e} -> 将使用软件模拟")
                self.use_driver = False
        else:
            if ActionDriver.DRIVER_DETECTED and not user_wants_hardware:
                print("硬件驱动就绪，但用户选择使用软件模拟")
            else:
                print("软件模拟已启用")
            self.use_driver = False

    @staticmethod
    def is_driver_available():
        """返回硬件驱动是否可用"""
        return ActionDriver.DRIVER_DETECTED

    def mouse_move(self, x, y, duration=0.5):
        """鼠标移动到目标坐标，使用贝塞尔曲线模拟自然轨迹，支持偏移重路由和末端精确校正"""
        target_x, target_y = int(x), int(y)

        original_duration = duration
        original_start_x, original_start_y = Utils.get_cursor_pos()
        original_dist = Utils.get_distance(original_start_x, original_start_y, target_x, target_y)

        if original_dist == 0:
            original_dist = 1

        start_time_global = time.perf_counter()
        deadline = start_time_global + duration
        original_pause = pyautogui.PAUSE
        pyautogui.PAUSE = 0

        REROUTE_THRESHOLD = 50  # 实际位置偏离路径超过此值时重新规划

        while True:
            curr_x, curr_y = Utils.get_cursor_pos()
            dist_to_target = Utils.get_distance(curr_x, curr_y, target_x, target_y)

            # 已足够接近目标，退出
            if dist_to_target < 10:
                break

            # 动态计算剩余移动时间
            now = time.perf_counter()
            remaining_time = deadline - now
            adjusted_duration = max(remaining_time, original_duration * (dist_to_target / original_dist))
            if adjusted_duration < 0.05:
                adjusted_duration = 0.05

            steps = int(max(20, adjusted_duration * 120))

            # 生成带随机扰动的贝塞尔控制点
            ctrl_1_x = curr_x + (target_x - curr_x) * random.uniform(0.2, 0.4) + random.randint(-10, 10)
            ctrl_1_y = curr_y + (target_y - curr_y) * random.uniform(0.1, 0.3) + random.randint(-10, 10)
            ctrl_2_x = curr_x + (target_x - curr_x) * random.uniform(0.6, 0.8) + random.randint(-10, 10)
            ctrl_2_y = curr_y + (target_y - curr_y) * random.uniform(0.7, 0.9) + random.randint(-10, 10)

            path_points = Utils.get_bezier_curve(
                (curr_x, curr_y), (target_x, target_y), ((ctrl_1_x, ctrl_1_y), (ctrl_2_x, ctrl_2_y)), steps
            )

            path_start_time = time.perf_counter()
            reroute_triggered = False

            # 沿路径逐步移动
            for i, (next_ideal_x, next_ideal_y) in enumerate(path_points):
                real_x, real_y = Utils.get_cursor_pos()
                deviation = Utils.get_distance(real_x, real_y, next_ideal_x, next_ideal_y)

                # 偏离过大，触发重路由
                if deviation > REROUTE_THRESHOLD:
                    reroute_triggered = True
                    break

                dx = int(next_ideal_x - real_x)
                dy = int(next_ideal_y - real_y)

                # 限制单步最大位移
                limit = 50
                dx = max(-limit, min(limit, dx))
                dy = max(-limit, min(limit, dy))

                if self.use_driver:
                    if dx != 0 or dy != 0:
                        self.lg_mouse.move_relative(dx, dy)
                else:
                    pyautogui.platformModule._moveTo(int(next_ideal_x), int(next_ideal_y))

                # 按时间片精确等待，保持移动速度一致
                time_slice = (i + 1) / steps * adjusted_duration
                target_timestamp = path_start_time + time_slice
                Utils.precise_wait(target_timestamp)

            if not reroute_triggered:
                break

        if self.use_driver:
            self._hw_correction(target_x, target_y, timeout=1.0, step_div=3, limit=20, sleep_s=0.012)
        else:
            curr_x, curr_y = Utils.get_cursor_pos()
            if curr_x != target_x or curr_y != target_y:
                pyautogui.moveTo(target_x, target_y)

        pyautogui.PAUSE = original_pause

    def mouse_move_linear(self, x, y, duration=0.0):
        """鼠标直线匀速移动到目标坐标"""
        target_x, target_y = int(x), int(y)
        # ── 瞬移：耗时为 0 ──
        if duration < 0.001:
            if self.use_driver:
                self._hw_correction(target_x, target_y, timeout=2.0, step_div=1, limit=127, sleep_s=0.005)
            else:
                original_pause = pyautogui.PAUSE
                pyautogui.PAUSE = 0
                pyautogui.moveTo(target_x, target_y)
                pyautogui.PAUSE = original_pause
            return

        # ── 有耗时的直线移动 ──
        start_x, start_y = Utils.get_cursor_pos()
        steps = int(max(20, duration * 120))

        original_pause = pyautogui.PAUSE
        pyautogui.PAUSE = 0
        start_time = time.perf_counter()

        for i in range(1, steps + 1):
            progress = i / steps
            next_x = start_x + (target_x - start_x) * progress
            next_y = start_y + (target_y - start_y) * progress

            if self.use_driver:
                real_x, real_y = Utils.get_cursor_pos()
                dx = int(next_x - real_x)
                dy = int(next_y - real_y)
                limit = 50
                dx = max(-limit, min(limit, dx))
                dy = max(-limit, min(limit, dy))
                if dx != 0 or dy != 0:
                    self.lg_mouse.move_relative(dx, dy)
            else:
                pyautogui.platformModule._moveTo(int(next_x), int(next_y))
            target_timestamp = start_time + (i / steps) * duration
            Utils.precise_wait(target_timestamp)
        if self.use_driver:
            self._hw_correction(target_x, target_y, timeout=1.0, step_div=3, limit=20, sleep_s=0.012)

        pyautogui.PAUSE = original_pause

    def _hw_correction(self, target_x, target_y, timeout=1.0, step_div=3, limit=127, sleep_s=0.005):
        """硬件模式末端校正：逐步微调直到鼠标到达目标位置"""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            curr_x, curr_y = Utils.get_cursor_pos()
            diff_x = target_x - curr_x
            diff_y = target_y - curr_y

            if diff_x == 0 and diff_y == 0:
                break

            if step_div > 1:
                sx = int(diff_x / step_div)
                sy = int(diff_y / step_div)
                if sx == 0 and diff_x != 0:
                    sx = 1 if diff_x > 0 else -1
                if sy == 0 and diff_y != 0:
                    sy = 1 if diff_y > 0 else -1
            else:
                sx, sy = diff_x, diff_y

            sx = max(-limit, min(limit, sx))
            sy = max(-limit, min(limit, sy))

            self.lg_mouse.move_relative(sx, sy)
            time.sleep(sleep_s)

    def _hardware_move_to_instant(self, tx, ty):
        """硬件模式：尽快移动到目标位置"""
        timeout = time.perf_counter() + 2.0
        while time.perf_counter() < timeout:
            cx, cy = Utils.get_cursor_pos()
            dx = tx - cx
            dy = ty - cy

            if dx == 0 and dy == 0:
                break

            # 单次相对移动限幅 ±127
            mx = max(-127, min(127, dx))
            my = max(-127, min(127, dy))
            self.lg_mouse.move_relative(mx, my)
            time.sleep(0.005)

    def _hardware_move_linear_over_time(self, tx, ty, duration):
        """硬件模式：在指定时间内匀速线性移动到目标"""
        sx, sy = Utils.get_cursor_pos()
        start_time = time.perf_counter()

        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed >= duration:
                break

            progress = elapsed / duration

            # 根据进度计算理想位置
            ideal_x = sx + (tx - sx) * progress
            ideal_y = sy + (ty - sy) * progress

            curr_x, curr_y = Utils.get_cursor_pos()
            dx = int(ideal_x - curr_x)
            dy = int(ideal_y - curr_y)

            if dx != 0 or dy != 0:
                mx = max(-127, min(127, dx))
                my = max(-127, min(127, dy))
                self.lg_mouse.move_relative(mx, my)

            time.sleep(0.01)

        # 最后确保精确到达目标
        self._hardware_move_to_instant(tx, ty)

    def mouse_move_relative(self, dx, dy, duration=0.5):
        """发送用于 3D 游戏视角控制的相对鼠标位移"""
        import ctypes

        MOUSEEVENTF_MOVE = 0x0001

        if duration <= 0.001:
            if self.use_driver:
                mx = max(-127, min(127, int(dx)))
                my = max(-127, min(127, int(dy)))
                self.lg_mouse.move_relative(mx, my)
            else:
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
            return

        steps = int(max(20, duration * 120))
        step_dx = dx / steps
        step_dy = dy / steps

        start_time = time.perf_counter()
        for i in range(1, steps + 1):
            # 计算每步应移动的真实增量，避免浮点数截断导致的误差累积
            move_x = int(step_dx * i) - int(step_dx * (i - 1))
            move_y = int(step_dy * i) - int(step_dy * (i - 1))

            if self.use_driver:
                mx = max(-127, min(127, move_x))
                my = max(-127, min(127, move_y))
                if mx != 0 or my != 0:
                    self.lg_mouse.move_relative(mx, my)
            else:
                if move_x != 0 or move_y != 0:
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)

            target_timestamp = start_time + (i / steps) * duration
            Utils.precise_wait(target_timestamp)

    def mouse_click(self, x=None, y=None, button="left", repeat=1, duration=0.05, interval=0.1):
        """鼠标点击，可指定坐标、按钮、重复次数和按下时长"""
        if x is not None and y is not None:
            self.mouse_move(x, y, 0.5)

        for i in range(repeat):
            if self.use_driver:
                btn_code = lgdriver.MouseButton.LEFT
                if button == "right":
                    btn_code = lgdriver.MouseButton.RIGHT
                elif button == "middle":
                    btn_code = lgdriver.MouseButton.MIDDLE

                self.lg_mouse.down(btn_code)
                time.sleep(duration)
                self.lg_mouse.up()
            else:
                pyautogui.mouseDown(button=button)
                time.sleep(duration)
                pyautogui.mouseUp(button=button)

            # 多次点击之间的间隔
            if repeat > 1 and i < repeat - 1:
                time.sleep(interval)

    def mouse_drag(self, start_x, start_y, end_x, end_y, duration=0.8, button="left"):
        """鼠标拖拽"""
        self.mouse_move(start_x, start_y, duration=0.3)
        time.sleep(0.1)

        if self.use_driver:
            btn_code = lgdriver.MouseButton.LEFT
            if button == "right":
                btn_code = lgdriver.MouseButton.RIGHT
            self.lg_mouse.down(btn_code)
        else:
            pyautogui.mouseDown(button=button)

        time.sleep(0.05)
        self.mouse_move(end_x, end_y, duration=duration)
        time.sleep(0.05)

        if self.use_driver:
            self.lg_mouse.up()
        else:
            pyautogui.mouseUp(button=button)

    def mouse_scroll(self, clicks):
        """鼠标滚轮滚动"""
        if self.use_driver:
            val = int(clicks / 100) if abs(clicks) >= 100 else (1 if clicks > 0 else -1)
            self.lg_mouse.scroll(val)
        else:
            pyautogui.scroll(clicks)

    def key_press(self, key_code, repeat=1, duration=0.05, interval=0.1):
        """键盘按键，支持组合键、重复按下"""
        keys_to_press = Utils.normalize_key_code(key_code)

        if not keys_to_press:
            return

        for i in range(repeat):
            if self.use_driver:
                # 硬件模式：将按键名映射为 HID 码后发送
                hid_codes, unsupported_keys = Utils.map_key_names(keys_to_press, lgdriver.KEY_MAP)

                if unsupported_keys:
                    print(f"硬件模式不支持这些按键: {unsupported_keys}")

                if hid_codes:
                    try:
                        self.lg_keyboard.press_keys(hid_codes)
                        time.sleep(duration)
                    finally:
                        self.lg_keyboard.release()
            else:
                # 软件模式：逐个按下再逆序释放
                for k in keys_to_press:
                    try:
                        pyautogui.keyDown(k)
                    except:
                        pass

                time.sleep(duration)

                for k in reversed(keys_to_press):
                    try:
                        pyautogui.keyUp(k)
                    except:
                        pass

            if repeat > 1 and i < repeat - 1:
                time.sleep(interval)

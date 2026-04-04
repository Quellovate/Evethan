# executor.py:
# 脚本执行器：封装各类鼠标、键盘、找图等自动化操作

import random
import time
import os
from driver import TargetDriver, ActionDriver
from utils import Utils
from config import global_config


class ExecutionEvent:
    """执行事件类型常量，用于日志和事件通知"""
    STEP_START = "STEP_START"
    DEBUG = "DEBUG"
    INFO = "INFO"
    RESULT = "RESULT"
    WARNING = "WARNING"
    ERROR = "ERROR"
    STATUS = "STATUS"


class ScriptExecutor:
    """脚本执行器，封装了所有自动化操作的执行逻辑"""

    def __init__(self):
        # 初始化目标定位驱动（找图、坐标计算等）
        self.target = TargetDriver()
        # 根据配置决定是否使用硬件模拟输入
        use_hw_setting = global_config.get_app_setting("use_hardware", True)
        self.action = ActionDriver(use_hardware=use_hw_setting)
        self._hold_links = {} # 跟踪 start 和 end 节点的配对状态
        self.check_stop_func = None       # 外部停止检查回调
        self.context_provider = None       # 上下文信息提供回调（如循环信息）
        self.current_step_desc = "初始化..."
        self.event_listener = None         # 事件监听回调

    def set_stop_check(self, func):
        """设置停止检查函数"""
        self.check_stop_func = func

    def set_event_listener(self, callback):
        """设置事件监听器"""
        self.event_listener = callback

    def set_context_provider(self, func):
        """设置上下文提供函数"""
        self.context_provider = func

    def set_current_step_desc(self, desc):
        """更新当前步骤描述"""
        self.current_step_desc = desc

    def _is_stopped(self):
        """检查任务是否已被外部请求停止"""
        if self.check_stop_func:
            return not self.check_stop_func()
        return False

    def _emit(self, event_type, message, data=None):
        """发送事件通知，附带当前步骤和上下文信息"""
        if self._is_stopped():
            return
        if data is None:
            data = {}
        data["step_desc"] = self.current_step_desc
        if self.context_provider:
            data["loop_context"] = self.context_provider()
        if self.event_listener:
            self.event_listener(event_type, message, data)
        else:
            print(f"[{event_type}] {message} | {data}")

    def _wait_after(self, min_ms, max_ms):
        """操作后随机等待一段时间，模拟人类操作间隔"""
        wait_time = Utils.get_random_time(min_ms, max_ms)
        if wait_time > 0.5:
            self._emit(ExecutionEvent.DEBUG, f"操作后随机等待: {wait_time:.3f}s")
        if wait_time > 0:
            time.sleep(wait_time)

    def _smart_move(self, tx, ty, enable_move=True, min_ms=200, max_ms=800):
        """智能移动鼠标：启用拟人移动时走贝塞尔曲线，关闭时走直线，耗时由参数控制"""
        move_duration = Utils.get_random_time(min_ms, max_ms)

        if move_duration < 0.001:
            # 耗时为 0 就瞬移
            self._emit(ExecutionEvent.DEBUG, f"瞬间移动 -> ({tx}, {ty})", {"x": tx, "y": ty})
            self.action.mouse_move_linear(tx, ty, duration=0)
        elif enable_move:
            self._emit(ExecutionEvent.DEBUG, f"拟人移动 -> ({tx}, {ty}), 耗时 {move_duration:.2f}s", {"x": tx, "y": ty})
            self.action.mouse_move(tx, ty, move_duration)
        else:
            self._emit(ExecutionEvent.DEBUG, f"直线移动 -> ({tx}, {ty}), 耗时 {move_duration:.2f}s", {"x": tx, "y": ty})
            self.action.mouse_move_linear(tx, ty, duration=move_duration)

        self._emit(ExecutionEvent.RESULT, "移动完成", {"target": (tx, ty)})

    def _loop_until_found(self, image_path, confidence, off_x, off_y, random_range, region=None, env_w=0, env_h=0):
        """循环查找图片直到找到或任务被停止，返回坐标或None"""
        img_name = os.path.basename(image_path)
        region_str = (
            f"区域:{region}"
            if (region and isinstance(region, list) and len(region) == 4 and (region[2] > 0 or region[3] > 0))
            else "全屏"
        )
        start_time = time.time()
        last_log_time = 0
        self._emit(ExecutionEvent.DEBUG, f"开始找图: {img_name} ({region_str})", {"image": img_name})
        while True:
            if self._is_stopped():
                self._emit(ExecutionEvent.WARNING, "任务中止，退出找图", {"reason": "stopped"})
                return None
            # 尝试匹配图片并获取坐标
            res = self.target.get_image_coordinate(
                image_path, confidence, off_x, off_y, random_range, region=region, env_w=env_w, env_h=env_h
            )
            if res:
                elapsed = time.time() - start_time
                self._emit(
                    ExecutionEvent.DEBUG, f"找到图片: {res}, 耗时: {elapsed:.2f}s", {"coord": res, "elapsed": elapsed}
                )
                return res
            # 每秒输出一次未找到的日志
            current_time = time.time()
            if current_time - last_log_time >= 1.0:
                print(f"[{time.strftime('%H:%M:%S')}] 找图异常: 未找到 {img_name}")
                last_log_time = current_time
            # 前5秒高频重试，之后降低频率
            elapsed = time.time() - start_time
            if elapsed < 5.0:
                sleep_time = random.uniform(0.02, 0.05)
            else:
                sleep_time = random.uniform(0.05, 0.15)
            time.sleep(sleep_time)

    # ==================== 鼠标移动 ====================


    def exec_mouse_move(self, x, y, random_range=0, move_enable=True, move_time_min=200, move_time_max=800, wait_min=50, wait_max=200):
        """执行鼠标移动，到指定坐标"""
        self._emit(ExecutionEvent.STEP_START, f"移动鼠标 ({x},{y})")
        tx, ty = self.target.get_fixed_coordinate(x, y, random_range)
        self._emit(ExecutionEvent.DEBUG, f"坐标计算: 原始({x},{y}) -> 随机化({tx},{ty})")
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        self._emit(ExecutionEvent.RESULT, "移动完成", {"target": (tx, ty)})
        self._wait_after(wait_min, wait_max)

    def exec_camera_turn(self, drag_dx, drag_dy, random_range=10, move_time_min=200, move_time_max=800, wait_min=50, wait_max=200):
        """执行 3D 视角转动"""
        final_dx, final_dy = Utils.get_gaussian_offset(drag_dx, drag_dy, random_range)
        duration = Utils.get_random_time(move_time_min, move_time_max)
        self._emit(ExecutionEvent.STEP_START, f"转动视角 (dx={final_dx}, dy={final_dy})")
        self._emit(ExecutionEvent.DEBUG, f"相对移动，耗时 {duration:.2f}s")
        self.action.mouse_move_relative(final_dx, final_dy, duration)
        self._emit(ExecutionEvent.RESULT, "视角转动完成")
        self._wait_after(wait_min, wait_max)

        # 旋转完视角，立刻把 Windows 隐藏的虚拟光标拉回屏幕中心
        w, h = Utils.get_screen_size()
        import ctypes
        ctypes.windll.user32.SetCursorPos(w // 2, h // 2)


    # ==================== 点击操作 ====================

    def exec_fixed_click(
        self,
        x,
        y,
        button="left",
        random_range=0,
        repeat=1,
        move_enable=True,
        move_time_min=200,
        move_time_max=800,
        interval_min=80,
        interval_max=160,
        wait_min=50,
        wait_max=200,
    ):
        """在固定坐标处点击"""
        self._emit(ExecutionEvent.STEP_START, f"点击 ({x},{y})")
        tx, ty = self.target.get_fixed_coordinate(x, y, random_range)
        self._emit(ExecutionEvent.DEBUG, f"坐标计算: 目标({x},{y}) -> 实际({tx},{ty})")
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        interval = Utils.get_random_time(interval_min, interval_max)
        click_duration = Utils.get_random_time(50, 120)
        self.action.mouse_click(
            x=None, y=None, button=button, repeat=repeat, duration=click_duration, interval=interval
        )
        self._emit(ExecutionEvent.RESULT, "点击完成", {"coord": (x, y)})
        self._wait_after(wait_min, wait_max)

    def exec_offset_click(
        self,
        off_x,
        off_y,
        button="left",
        random_range=0,
        repeat=1,
        move_enable=True,
        move_time_min=200,
        move_time_max=800,
        interval_min=80,
        interval_max=160,
        wait_min=50,
        wait_max=200,
    ):
        """在当前鼠标位置的偏移处点击"""
        self._emit(ExecutionEvent.STEP_START, f"偏移点击 ({off_x},{off_y})")
        tx, ty = self.target.get_relative_coordinate(off_x, off_y, random_range)
        self._emit(ExecutionEvent.DEBUG, f"坐标计算: 当前位置+偏移 -> 目标({tx},{ty})")
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        interval = Utils.get_random_time(interval_min, interval_max)
        click_duration = Utils.get_random_time(50, 120)
        self.action.mouse_click(
            x=None, y=None, button=button, repeat=repeat, duration=click_duration, interval=interval
        )
        self._emit(ExecutionEvent.RESULT, f"点击完成 (dx={off_x}, dy={off_y})")
        self._wait_after(wait_min, wait_max)

    def exec_image_click(
        self,
        image_path,
        confidence=0.7,
        off_x=0,
        off_y=0,
        button="left",
        random_range=0,
        repeat=1,
        move_enable=True,
        move_time_min=200,
        move_time_max=800,
        interval_min=80,
        interval_max=160,
        wait_min=50,
        wait_max=200,
        region=None,
        env_w=0,
        env_h=0,
    ):
        """通过图片识别定位目标并点击"""
        img_name = os.path.basename(image_path)
        self._emit(ExecutionEvent.STEP_START, f"查找并点击 {img_name}", {"image": img_name})
        res = self._loop_until_found(image_path, confidence, off_x, off_y, random_range, region, env_w, env_h)
        if res is None:
            self._emit(ExecutionEvent.WARNING, "未找到图片，跳过", {"image": img_name})
            return False
        tx, ty = res
        self._emit(ExecutionEvent.RESULT, "找到目标", {"coord": res})
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        interval = Utils.get_random_time(interval_min, interval_max)
        click_duration = Utils.get_random_time(50, 120)
        self.action.mouse_click(
            x=None, y=None, button=button, repeat=repeat, duration=click_duration, interval=interval
        )
        self._wait_after(wait_min, wait_max)
        return True

    # ==================== 长按操作 ====================

    def exec_fixed_long_press(
        self,
        x,
        y,
        button="left",
        random_range=0,
        duration_s=3.0,
        repeat=1,
        move_enable=True,
        move_time_min=200,
        move_time_max=800,
        interval_min=80,
        interval_max=160,
        wait_min=50,
        wait_max=200,
    ):
        """在固定坐标处长按"""
        self._emit(ExecutionEvent.STEP_START, f"长按 ({x},{y}) {duration_s}s")
        tx, ty = self.target.get_fixed_coordinate(x, y, random_range)
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        interval = Utils.get_random_time(interval_min, interval_max)
        self.action.mouse_click(x=None, y=None, button=button, repeat=repeat, duration=duration_s, interval=interval)
        self._emit(ExecutionEvent.RESULT, "长按完成")
        self._wait_after(wait_min, wait_max)

    def exec_offset_long_press(
        self,
        off_x,
        off_y,
        button="left",
        random_range=0,
        duration_s=3.0,
        repeat=1,
        move_enable=True,
        move_time_min=200,
        move_time_max=800,
        interval_min=80,
        interval_max=160,
        wait_min=50,
        wait_max=200,
    ):
        """在偏移坐标处长按"""
        self._emit(ExecutionEvent.STEP_START, f"偏移长按 ({off_x},{off_y}) {duration_s}s")
        tx, ty = self.target.get_relative_coordinate(off_x, off_y, random_range)
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        interval = Utils.get_random_time(interval_min, interval_max)
        self.action.mouse_click(x=None, y=None, button=button, repeat=repeat, duration=duration_s, interval=interval)
        self._emit(ExecutionEvent.RESULT, "长按完成")
        self._wait_after(wait_min, wait_max)

    def exec_image_long_press(
        self,
        image_path,
        confidence=0.7,
        off_x=0,
        off_y=0,
        button="left",
        random_range=0,
        duration_s=3.0,
        repeat=1,
        move_enable=True,
        move_time_min=200,
        move_time_max=800,
        interval_min=80,
        interval_max=160,
        wait_min=50,
        wait_max=200,
        region=None,
        env_w=0,
        env_h=0,
    ):
        """通过图片识别定位目标并长按"""
        img_name = os.path.basename(image_path)
        self._emit(ExecutionEvent.STEP_START, f"查找并长按 {img_name}", {"image": img_name})
        res = self._loop_until_found(image_path, confidence, off_x, off_y, random_range, region, env_w, env_h)
        if res is None:
            return False
        tx, ty = res
        self._emit(ExecutionEvent.RESULT, "找到目标", {"coord": res})
        self._smart_move(tx, ty, move_enable, move_time_min, move_time_max)
        interval = Utils.get_random_time(interval_min, interval_max)
        self.action.mouse_click(x=None, y=None, button=button, repeat=repeat, duration=duration_s, interval=interval)
        self._wait_after(wait_min, wait_max)
        return True

    # ==================== 拖拽操作 ====================

    def exec_mouse_drag(
        self,
        x1,
        y1,
        x2,
        y2,
        random_range=5,
        move_time_min=500,
        move_time_max=1500,
        button="left",
        wait_min=50,
        wait_max=200,
    ):
        """从坐标(x1,y1)拖拽到(x2,y2)"""
        self._emit(ExecutionEvent.STEP_START, f"拖拽 ({x1},{y1}) -> ({x2},{y2})")
        sx, sy = self.target.get_fixed_coordinate(x1, y1, random_range)
        ex, ey = self.target.get_fixed_coordinate(x2, y2, random_range)
        duration = Utils.get_random_time(move_time_min, move_time_max)
        self._emit(ExecutionEvent.DEBUG, f"拖拽轨迹: 起点({sx},{sy}) -> 终点({ex},{ey}), 耗时{duration:.2f}s")
        self.action.mouse_drag(sx, sy, ex, ey, duration, button)
        self._emit(ExecutionEvent.RESULT, "拖拽完成")
        self._wait_after(wait_min, wait_max)

    def exec_image_drag(
        self,
        image_path,
        drag_dx,
        drag_dy,
        confidence=0.7,
        off_x=0,
        off_y=0,
        random_range=5,
        move_time_min=500,
        move_time_max=1500,
        button="left",
        wait_min=50,
        wait_max=200,
        region=None,
        env_w=0,
        env_h=0,
    ):
        """找到图片后，从图片位置拖拽指定偏移量"""
        img_name = os.path.basename(image_path)
        self._emit(ExecutionEvent.STEP_START, f"拖拽图片 {img_name}", {"image": img_name})
        res = self._loop_until_found(image_path, confidence, off_x, off_y, random_range, region, env_w, env_h)
        if res is None:
            return False
        start_x, start_y = res
        self._emit(ExecutionEvent.DEBUG, f"找到拖拽起点: ({start_x}, {start_y})")
        # 根据拖拽偏移量计算终点，并加入高斯随机扰动
        end_x, end_y = Utils.get_gaussian_offset(start_x + drag_dx, start_y + drag_dy, random_range)
        duration = Utils.get_random_time(move_time_min, move_time_max)
        self._emit(ExecutionEvent.DEBUG, f"计算终点: ({end_x}, {end_y})")
        self.action.mouse_drag(start_x, start_y, end_x, end_y, duration, button)
        self._emit(ExecutionEvent.RESULT, "拖拽完成")
        self._wait_after(wait_min, wait_max)
        return True

    # ==================== 滚轮操作 ====================

    def exec_scroll(self, scroll_amount=100, random_range=0, wait_min=50, wait_max=200):
        """执行鼠标滚轮滚动"""
        final_amount = int(Utils.get_gaussian_offset(scroll_amount, 0, random_range)[0])
        direction = "上" if final_amount > 0 else "下"
        self._emit(ExecutionEvent.STEP_START, f"滚轮滚动 {final_amount}")
        self.action.mouse_scroll(final_amount)
        self._emit(ExecutionEvent.RESULT, f"向{direction}滚动 {abs(final_amount)}")
        self._wait_after(wait_min, wait_max)

    # ==================== 键盘操作 ====================

    def exec_key_press(self, key_code, repeat=1, interval_min=80, interval_max=160, wait_min=50, wait_max=200):
        """执行键盘按键"""
        self._emit(ExecutionEvent.STEP_START, f"按键 {key_code} ({repeat}次)")
        interval = Utils.get_random_time(interval_min, interval_max)
        self.action.key_press(key_code, repeat=repeat, duration=0.08, interval=interval)
        self._emit(ExecutionEvent.RESULT, "按键完成")
        self._wait_after(wait_min, wait_max)

    def exec_key_long_press(
        self, key_code, duration_s=1.5, repeat=1, interval_min=80, interval_max=160, wait_min=50, wait_max=200
    ):
        """执行键盘长按"""
        self._emit(ExecutionEvent.STEP_START, f"长按键 {key_code} {duration_s}s")
        interval = Utils.get_random_time(interval_min, interval_max)
        self.action.key_press(key_code, repeat=repeat, duration=duration_s, interval=interval)
        self._emit(ExecutionEvent.RESULT, "长按完成")
        self._wait_after(wait_min, wait_max)

    # ==================== 找图等待 ====================

    def exec_find_image(self, image_path, confidence=0.7, wait_min=50, wait_max=200, region=None, env_w=0, env_h=0):
        """等待指定图片出现在屏幕上"""
        img_name = os.path.basename(image_path)
        self._emit(ExecutionEvent.STEP_START, f"等待图片 {img_name}", {"image": img_name})
        res = self._loop_until_found(image_path, confidence, 0, 0, 0, region, env_w, env_h)
        if res:
            self._emit(ExecutionEvent.RESULT, "图片已出现")
            self._wait_after(wait_min, wait_max)
            return True
        else:
            return False

    # ==================== 延时等待 ====================

    def exec_wait(self, time_s=2.0, random_add_s=0.5):
        """等待指定时间，附加随机额外时长"""
        extra = random.uniform(0, random_add_s)
        final_time = time_s + extra

        if final_time > 1.0:
            # 较长等待：分段sleep并定期汇报剩余时间
            self._emit(ExecutionEvent.STEP_START, f"等待 {final_time:.1f}s")
            start_time = time.time()
            last_reported_sec = -1
            while True:
                if self._is_stopped():
                    self._emit(ExecutionEvent.WARNING, "等待被中止")
                    return
                elapsed = time.time() - start_time
                remaining = final_time - elapsed
                if remaining <= 0:
                    self._emit(ExecutionEvent.RESULT, "等待结束")
                    break
                current_rem_sec = int(remaining)
                if current_rem_sec != last_reported_sec and current_rem_sec > 0:
                    self._emit(ExecutionEvent.RESULT, f"还需等待 {current_rem_sec} 秒")
                    last_reported_sec = current_rem_sec
                time.sleep(0.1)
        else:
            # 较短等待：直接sleep
            self._emit(ExecutionEvent.DEBUG, f"执行等待: {final_time:.2f}s")
            if final_time > 0:
                time.sleep(final_time)

    # ==================== 条件判断（If/Else/End） ====================

    def exec_if_start(self, image_path, confidence=0.7, timeout=5.0, link_id=None, region=None, env_w=0, env_h=0):
        """条件判断：在超时时间内查找图片，找到返回True，否则False"""
        img_name = os.path.basename(image_path)
        region_str = (
            f"区域:{region}" if (region and isinstance(region, list) and (region[2] > 0 or region[3] > 0)) else "全屏"
        )
        self._emit(ExecutionEvent.STEP_START, f"判断: {img_name}", {"image": img_name, "timeout": timeout})
        start_time = time.time()
        while True:
            if self._is_stopped():
                return False
            found_coord = self.target.get_image_coordinate(
                image_path, confidence, 0, 0, 0, region=region, env_w=env_w, env_h=env_h
            )
            if found_coord:
                self._emit(ExecutionEvent.RESULT, "条件成立")
                return True
            if time.time() - start_time > timeout:
                self._emit(ExecutionEvent.RESULT, "条件不成立")
                return False
            time.sleep(0.05)

    def exec_else_branch(self, link_id=None):
        """进入Else分支"""
        self._emit(ExecutionEvent.DEBUG, "进入 Else 分支")

    def exec_if_end(self, link_id=None):
        """If结构结束标记"""
        pass

    # ==================== 流程控制 ====================

    def exec_break(self):
        """跳出当前循环"""
        self._emit(ExecutionEvent.RESULT, "跳出循环")

    def exec_stop_task(self):
        """终止整个任务"""
        self._emit(ExecutionEvent.RESULT, "任务停止")

    def exec_loop_start(self, count=1, link_id=None, current_loop_index=0):
        """循环开始标记"""
        self._emit(ExecutionEvent.DEBUG, f"循环开始: 第 {current_loop_index + 1}/{count} 次")

    def exec_loop_end(self, link_id=None):
        """循环结束标记"""
        pass

    # ==================== 分组与分割线 ====================

    def exec_group_start(self, label="分组", link_id=None, collapsed=False):
        """进入步骤分组"""
        self._emit(ExecutionEvent.DEBUG, f"进入分组: {label}")

    def exec_group_end(self, link_id=None):
        """离开步骤分组"""
        self._emit(ExecutionEvent.DEBUG, "离开分组")

    def exec_separator(self, label="—— 分割线 ——"):
        """分割线标记，仅用于视觉分隔"""
        self._emit(ExecutionEvent.DEBUG, f"分割线: {label}")



    # ==================== 状态保持与清理机制 ====================

    def cleanup_all_holds(self):
        """清理由于异常中断导致的按键残留"""
        if self._hold_links or (hasattr(self.action, '_held_keys') and self.action._held_keys):
            self._emit(ExecutionEvent.WARNING, "正在强制清理并复位残留的鼠标与键盘按下状态...")
            self.action.release_all_hardware_and_software_holds()
            self._hold_links.clear()

    def exec_stop_task(self):
        """覆盖原有的停止方法，注入清理逻辑"""
        self.cleanup_all_holds()
        self._emit(ExecutionEvent.RESULT, "任务停止")

    # ==================== 同步执行 (按下/抬起) ====================

    def exec_mouse_hold_start(self, button="left", link_id=None, wait_min=50, wait_max=200):
        """开始按下鼠标"""
        self._emit(ExecutionEvent.STEP_START, f"按下并保持鼠标 [{button}] 键")
        self.action.mouse_down(button)
        if link_id:
            # 记录此时实际按下的按键
            self._hold_links[link_id] = {"type": "mouse", "val": button}
        self._wait_after(wait_min, wait_max)

    def exec_mouse_hold_end(self, link_id=None, **kwargs):
        """抬起鼠标"""
        target_btn = "left"
        if link_id and link_id in self._hold_links:
            target_btn = self._hold_links[link_id].get("val", "left")
            del self._hold_links[link_id] 
            
        self._emit(ExecutionEvent.RESULT, f"抬起鼠标 [{target_btn}] 键")
        self.action.mouse_up(target_btn)

    def exec_key_hold_start(self, key_code, link_id=None, wait_min=50, wait_max=200):
        """开始按下键盘按键"""
        self._emit(ExecutionEvent.STEP_START, f"按下并保持按键 [{key_code}]")
        self.action.key_down(key_code)
        if link_id:
            self._hold_links[link_id] = {"type": "key", "val": key_code}
        self._wait_after(wait_min, wait_max)

    def exec_key_hold_end(self, link_id=None, **kwargs): 
        """抬起键盘按键"""
        target_key = "" 
        if link_id and link_id in self._hold_links:
            target_key = self._hold_links[link_id].get("val", "")
            del self._hold_links[link_id]

        if target_key:
            self._emit(ExecutionEvent.RESULT, f"抬起按键 [{target_key}]")
            self.action.key_up(target_key)
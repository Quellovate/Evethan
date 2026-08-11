# tools.py
# 屏幕工具：包含屏幕定位、测距、截图、区域选择、按键录制等功能

import sys
import os
import ctypes
import platform
import numpy as np
import cv2

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

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QKeySequence, QPainter, QPen, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QSizePolicy, QSlider, QVBoxLayout, QWidget


from ui_styles import UIColors, UIFonts, UIStyles, UIDims
from utils import ColorUtils, ColorStats


class ScreenTool(QWidget):
    """
    屏幕工具：全屏覆盖式交互组件
    支持四种模式：picker(取点)、ruler(测距)、screenshot(截图)、rect_select(区域选择)
    """

    finished = Signal(int, int, int, int)  # 取点/测距完成信号 (x, y, dx, dy)
    screenshot_created = Signal(object)  # 截图完成信号，携带 QPixmap
    rect_selected = Signal(list)  # 区域选择完成信号，携带 [x, y, w, h]

    def __init__(self, mode="picker"):
        super().__init__()
        self.mode = mode
        # 无边框、置顶、透明背景、十字光标
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        # 铺满主屏幕
        screen_geo = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geo)
        self.start_pos = None  # 框选/测距的起点
        self.current_pos = QCursor.pos()  # 当前光标位置
        self.is_processing = False  # 防止重复处理
        self._bg_pixmap = None

    def showEvent(self, event):
        screen = QApplication.primaryScreen()
        self._bg_pixmap = screen.grabWindow(0)
        super().showEvent(event)

    # 绘制
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        screen_w = self.width()
        screen_h = self.height()
        cx, cy = self.current_pos.x(), self.current_pos.y()
        if self._bg_pixmap:
            painter.drawPixmap(0, 0, self._bg_pixmap)

        is_selecting = (self.mode in ("screenshot", "rect_select")) and self.start_pos

        if is_selecting:
            # 绘制选区：选区外半透明遮罩，选区内透明 + 边框
            self._draw_selection(painter, cx, cy)
        else:
            # 全屏半透明遮罩
            painter.fillRect(self.rect(), UIColors.TOOL_OVERLAY)

        # 非框选状态下绘制十字准线
        if not is_selecting:
            self._draw_crosshair(painter, cx, cy)

        # 绘制信息文本（坐标、提示等）
        self._draw_info_text(painter, cx, cy, screen_w, screen_h)

    def _draw_selection(self, painter, cx, cy):
        """绘制框选区域：遮罩挖空 + 选区边框 + 尺寸标注"""
        painter.setBrush(UIColors.TOOL_OVERLAY)
        painter.setPen(Qt.NoPen)
        selection = QRect(self.start_pos, self.current_pos).normalized()

        # 用区域减法实现"选区透明、其余遮罩"
        rgn = QRegion(self.rect())
        rgn -= QRegion(selection)
        for rect in rgn:
            painter.drawRect(rect)

        # 选区边框颜色取决于模式
        painter.setBrush(Qt.NoBrush)
        color = UIColors.TOOL_RECT_SCREENSHOT if self.mode == "screenshot" else UIColors.TOOL_RECT_SELECT
        painter.setPen(QPen(color, 2))
        painter.drawRect(selection)

        # 选区尺寸标注
        txt = f"[{selection.x()},{selection.y()}]  {selection.width()} x {selection.height()}"
        painter.setPen(UIColors.TOOL_COORD_TEXT)
        if selection.y() < 20:
            painter.drawText(selection.topLeft() + QPoint(UIDims.TOOL_TEXT_OFFSET_X, UIDims.TOOL_TEXT_OFFSET_Y), txt)
        else:
            painter.drawText(selection.topLeft() + QPoint(UIDims.TOOL_TEXT_OFFSET_X, -UIDims.TOOL_TEXT_OFFSET_X), txt)

    def _draw_crosshair(self, painter, cx, cy):
        """绘制全屏十字准线"""
        pen = QPen(UIColors.TOOL_CROSSHAIR, 1)
        painter.setPen(pen)
        painter.drawLine(0, cy, self.width(), cy)
        painter.drawLine(cx, 0, cx, self.height())

    def _draw_info_text(self, painter, cx, cy, screen_w, screen_h):
        """绘制提示文字和光标旁的坐标/偏移信息"""
        painter.setPen(UIColors.TOOL_COORD_TEXT)
        painter.setFont(UIFonts.tool_overlay())

        hint_text = ""
        info_text_lines = []
        coord_text = f"X: {cx}, Y: {cy}"

        # 根据模式生成提示和信息行
        if self.mode == "picker":
            hint_text = "【定位模式】 单击左键确定位置 （右键退出）"
            info_text_lines.append(coord_text)
        elif self.mode == "ruler":
            if not self.start_pos:
                hint_text = "【测距模式】 单击左键确定起点 （右键退出）"
                info_text_lines.append(coord_text)
            else:
                hint_text = "【测距模式】 单击左键确定终点 （右键退出）"
                # 画起点到当前的连线
                painter.setPen(QPen(UIColors.TOOL_RULER_LINE, 2))
                painter.drawLine(self.start_pos, self.current_pos)
                dx = cx - self.start_pos.x()
                dy = cy - self.start_pos.y()
                info_text_lines.append(f"起点: ({self.start_pos.x()},{self.start_pos.y()})")
                info_text_lines.append(f"当前: ({cx},{cy})")
                info_text_lines.append(f"偏移: dx={dx}, dy={dy}")
        elif self.mode == "screenshot":
            hint_text = "【截图模式】 拖拽框选 -> 松开完成"
            if not self.start_pos:
                info_text_lines.append(coord_text)
        elif self.mode == "rect_select":
            hint_text = "【范围选择】 拖拽框选识别区域 -> 松开完成"
            if not self.start_pos:
                info_text_lines.append(coord_text)

        # 在光标旁绘制信息文本（自动判断方向避免超出屏幕）
        if info_text_lines:
            fm = painter.fontMetrics()
            line_height = fm.height() + 5
            max_width = max(fm.horizontalAdvance(line) for line in info_text_lines)
            total_h = len(info_text_lines) * line_height
            offset_dist = UIDims.TOOL_CURSOR_OFFSET

            draw_x = cx + offset_dist
            draw_y = cy + offset_dist + fm.ascent()
            if cx > screen_w / 2:
                draw_x = cx - offset_dist - max_width
            if cy > screen_h / 2:
                draw_y = cy - offset_dist - total_h + fm.ascent()

            painter.setPen(UIColors.TOOL_COORD_TEXT)
            for i, line in enumerate(info_text_lines):
                painter.drawText(draw_x, draw_y + (i * line_height), line)

        # 屏幕顶部居中绘制模式提示
        painter.setPen(UIColors.TOOL_HINT_TEXT)
        painter.drawText(QRect(0, 50, self.width(), 50), Qt.AlignCenter, hint_text)

    # 鼠标事件

    def mouseMoveEvent(self, event):
        """跟踪光标位置并刷新画面"""
        self.current_pos = event.globalPos()
        self.update()

    def mousePressEvent(self, event):
        """处理鼠标按下：右键退出，左键根据模式执行不同逻辑"""
        if self.is_processing:
            return
        if event.button() == Qt.RightButton:
            self.close()
            return

        if event.button() == Qt.LeftButton:
            if self.mode == "picker":
                # 取点模式：直接发射坐标
                self.is_processing = True
                pos = event.globalPos()
                self.close()
                QApplication.processEvents()
                self.finished.emit(pos.x(), pos.y(), 0, 0)

            elif self.mode in ("screenshot", "rect_select"):
                # 截图/区域选择：记录起点，等待拖拽释放
                self.start_pos = event.globalPos()

            elif self.mode == "ruler":
                if not self.start_pos:
                    # 测距第一次点击：记录起点
                    self.start_pos = event.globalPos()
                    self.update()
                else:
                    # 测距第二次点击：计算偏移并发射
                    self.is_processing = True
                    end_pos = event.globalPos()
                    dx = end_pos.x() - self.start_pos.x()
                    dy = end_pos.y() - self.start_pos.y()
                    self.close()
                    QApplication.processEvents()
                    self.finished.emit(end_pos.x(), end_pos.y(), dx, dy)

    def mouseReleaseEvent(self, event):
        """处理鼠标释放：截图/区域选择模式下完成框选"""
        if self.is_processing:
            return
        if event.button() == Qt.LeftButton:
            if self.mode in ("screenshot", "rect_select") and self.start_pos:
                end_pos = event.globalPos()
                rect = QRect(self.start_pos, end_pos).normalized()
                # 忽略过小的选区
                if rect.width() < 5 or rect.height() < 5:
                    self.start_pos = None
                    self.update()
                    return

                self.is_processing = True
                self.hide()
                QApplication.processEvents()

                if self.mode == "screenshot":
                    # 截取选区图像
                    if self._bg_pixmap:
                        pixmap = self._bg_pixmap.copy(rect)
                    else:
                        screen = QApplication.primaryScreen()
                        pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
                    self.screenshot_created.emit(pixmap)

                elif self.mode == "rect_select":
                    self.rect_selected.emit([rect.x(), rect.y(), rect.width(), rect.height()])

                self.close()


class KeyRecorder(QWidget):
    """
    按键录制器：弹出小窗口捕获用户按键（支持组合键）
    松开所有按键后自动发射录制结果，按 Esc 取消
    """

    key_recorded = Signal(str)  # 录制完成信号，携带按键字符串如 "ctrl+c"

    # 修饰键排序优先级（保证组合键字符串顺序一致）
    SORT_PRIORITY = {"win": 0, "ctrl": 1, "alt": 2, "shift": 3}

    # Qt 按键到字符串的映射表
    KEY_MAP = {
        Qt.Key_Escape: "esc",
        Qt.Key_Return: "enter",
        Qt.Key_Enter: "enter",
        Qt.Key_Tab: "tab",
        Qt.Key_Backspace: "backspace",
        Qt.Key_Delete: "delete",
        Qt.Key_Insert: "insert",
        Qt.Key_Home: "home",
        Qt.Key_End: "end",
        Qt.Key_PageUp: "pageup",
        Qt.Key_PageDown: "pagedown",
        Qt.Key_Up: "up",
        Qt.Key_Down: "down",
        Qt.Key_Left: "left",
        Qt.Key_Right: "right",
        Qt.Key_Space: "space",
        Qt.Key_F1: "f1",
        Qt.Key_F2: "f2",
        Qt.Key_F3: "f3",
        Qt.Key_F4: "f4",
        Qt.Key_F5: "f5",
        Qt.Key_F6: "f6",
        Qt.Key_F7: "f7",
        Qt.Key_F8: "f8",
        Qt.Key_F9: "f9",
        Qt.Key_F10: "f10",
        Qt.Key_F11: "f11",
        Qt.Key_F12: "f12",
        Qt.Key_Control: "ctrl",
        Qt.Key_Shift: "shift",
        Qt.Key_Alt: "alt",
        Qt.Key_Meta: "win",
        Qt.Key_CapsLock: "capslock",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("按键录制")
        self.resize(UIDims.WINDOW_RECORDER_W, UIDims.WINDOW_RECORDER_H)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)

        self.lbl_title = QLabel("正在录制...")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet(UIStyles.RECORDER_TITLE)
        layout.addWidget(self.lbl_title)

        self.lbl_current = QLabel("请按下按键 (支持组合键，如ctrl+c)")
        self.lbl_current.setAlignment(Qt.AlignCenter)
        self.lbl_current.setStyleSheet(UIStyles.RECORDER_DISPLAY)
        layout.addWidget(self.lbl_current)

        self.lbl_hint = QLabel("松开所有按键后自动完成\n(按下 Esc 键取消)")
        self.lbl_hint.setAlignment(Qt.AlignCenter)
        self.lbl_hint.setStyleSheet(UIStyles.RECORDER_HINT)
        layout.addWidget(self.lbl_hint)

        self.pressed_keys = set()  # 当前被按住的键集合
        self.last_valid_combo = ""  # 最后一次有效的组合键字符串

    # 按键名称转换

    def _get_key_str(self, qt_key):
        """将 Qt 键码转为可读字符串"""
        if qt_key in self.KEY_MAP:
            return self.KEY_MAP[qt_key]
        try:
            text = QKeySequence(qt_key).toString().lower()
            if text and text.strip():
                return text
        except:
            pass
        return None

    # 显示更新

    def _update_display(self):
        """根据当前按住的键更新界面显示"""
        if not self.pressed_keys:
            self.lbl_current.setText("等待按键...")
            return
        key_strs = []
        for k in self.pressed_keys:
            s = self._get_key_str(k)
            if s:
                key_strs.append(s)
        # 按修饰键优先级排序
        key_strs.sort(key=lambda x: self.SORT_PRIORITY.get(x, 100))
        combo_str = "+".join(key_strs)
        self.lbl_current.setText(f"{combo_str}")
        self.lbl_current.setStyleSheet(UIStyles.RECORDER_DISPLAY_ACTIVE)
        if combo_str:
            self.last_valid_combo = combo_str

    # 键盘事件

    def keyPressEvent(self, event):
        """按键按下：记录到集合并更新显示"""
        key = event.key()
        # 空闲状态下按 Esc 直接取消
        if key == Qt.Key_Escape and not self.pressed_keys:
            self.close()
            return
        if event.isAutoRepeat():
            return
        if key == 0 or key == Qt.Key_unknown:
            return
        self.pressed_keys.add(key)
        self._update_display()

    def keyReleaseEvent(self, event):
        """按键释放：全部松开后发射录制结果"""
        key = event.key()
        if event.isAutoRepeat():
            return
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
        # 所有键都松开 → 完成录制
        if not self.pressed_keys:
            if self.last_valid_combo:
                self.key_recorded.emit(self.last_valid_combo)
                self.close()
            else:
                self._update_display()


class ColorPickerTool(QWidget):
    """
    取色器：全屏取色遮罩层
    通过点击或拖拽进行取色
    """

    picked = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.target_screen = QApplication.primaryScreen()
        self.setGeometry(self.target_screen.geometry())

        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        self._pix = None
        self._img = None
        self._collecting = False
        self._samples = []
        self._last_pos = None
        self._device_ratio = self.target_screen.devicePixelRatio()

    def showEvent(self, e):
        """截取整个屏幕画面"""
        self._pix = self.target_screen.grabWindow(0)
        self._img = self._pix.toImage()
        self._last_pos = self.mapFromGlobal(QCursor.pos())
        super().showEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        screen_w, screen_h = self.width(), self.height()

        if self._pix:
            p.drawPixmap(0, 0, self._pix)

        # 绘制遮罩
        p.fillRect(self.rect(), UIColors.TOOL_OVERLAY)

        # 绘制提示文字
        p.setFont(UIFonts.tool_overlay())
        p.setPen(UIColors.TOOL_HINT_TEXT)
        p.drawText(
            QRect(0, 50, screen_w, 50), Qt.AlignCenter, "【取色模式】 点击或拖拽进行采样 -> 松开完成 （右键退出）"
        )

        # 绘制预览与取色信息
        if self._last_pos:
            x, y = self._last_pos.x(), self._last_pos.y()
            p.setPen(QPen(UIColors.TOOL_CROSSHAIR, 1))
            p.drawLine(x - 10, y, x + 10, y)
            p.drawLine(x, y - 10, x, y + 10)

            color = self.sample_at(self._last_pos)
            if color and self._img:
                r, g, b = color
                info_text_lines = [f"X: {x}, Y: {y}", f"RGB: ({r}, {g}, {b})"]
                fm = p.fontMetrics()
                line_height = fm.height() + 5
                max_width = max(fm.horizontalAdvance(line) for line in info_text_lines)
                total_h = len(info_text_lines) * line_height

                zoom_pixels, zoom_scale = 11, 8
                mag_size = zoom_pixels * zoom_scale
                offset_dist = UIDims.TOOL_CURSOR_OFFSET
                draw_x, draw_y = x + offset_dist, y + offset_dist

                if x > screen_w / 2:
                    draw_x = x - offset_dist - max(max_width, mag_size)
                if y > screen_h / 2:
                    draw_y = y - offset_dist - total_h - mag_size - 10

                p.setPen(UIColors.TOOL_COORD_TEXT)
                text_start_y = draw_y + fm.ascent()
                for i, line in enumerate(info_text_lines):
                    p.drawText(draw_x, text_start_y + (i * line_height), line)

                # 绘制放大镜
                mag_rect = QRect(draw_x, draw_y + total_h + 5, mag_size, mag_size)
                px_x, px_y = int(x * self._device_ratio), int(y * self._device_ratio)
                half_z = zoom_pixels // 2
                src_rect = QRect(px_x - half_z, px_y - half_z, zoom_pixels, zoom_pixels)
                p.drawImage(mag_rect, self._img.copy(src_rect))

                p.setPen(QPen(QColor(255, 255, 255, 80), 1))
                for i in range(zoom_pixels + 1):
                    line_x = mag_rect.x() + i * zoom_scale
                    p.drawLine(line_x, mag_rect.y(), line_x, mag_rect.bottom())
                    line_y = mag_rect.y() + i * zoom_scale
                    p.drawLine(mag_rect.x(), line_y, mag_rect.right(), line_y)

                center_rect = QRect(
                    mag_rect.x() + half_z * zoom_scale, mag_rect.y() + half_z * zoom_scale, zoom_scale, zoom_scale
                )
                p.setPen(QPen(Qt.red, 2))
                p.drawRect(center_rect)

                info_rect = QRect(mag_rect.x(), mag_rect.bottom(), mag_size, 20)
                p.fillRect(info_rect, QColor(r, g, b))
                p.setPen(QPen(UIColors.TOOL_CROSSHAIR, 1))
                p.drawRect(mag_rect)
                p.drawRect(info_rect)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.close()
        elif e.button() == Qt.LeftButton:
            self._collecting = True
            self._samples.clear()
            self._last_pos = e.position().toPoint()
            self.add_sample(self._last_pos)
            self.update()

    def mouseMoveEvent(self, e):
        self._last_pos = e.position().toPoint()
        if self._collecting:
            self.add_sample(self._last_pos)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._collecting:
            self._collecting = False
            self.picked.emit(self._samples[:])
            self.close()

    def add_sample(self, pos):
        """提取颜色并加入样本库"""
        c = self.sample_at(pos)
        if c:
            self._samples.append(c)

    def sample_at(self, pos):
        """获取指定坐标的 RGB 值"""
        if not self._img:
            return None
        px_x = max(0, min(int(pos.x() * self._device_ratio), self._img.width() - 1))
        px_y = max(0, min(int(pos.y() * self._device_ratio), self._img.height() - 1))
        qc = QColor(self._img.pixel(px_x, px_y))
        return (qc.red(), qc.green(), qc.blue())


class ColorResultDialog(QDialog):
    """
    计算 RGB 和 HSV 的范围并展示
    提供一个滑动条，动态生成并预览所选颜色范围
    """

    def __init__(self, samples, parent=None):
        super().__init__(parent)
        self.setWindowTitle("取色结果")
        self.resize(600, 450)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)

        self.info_label = QLabel()
        self.info_label.setFont(UIFonts.app_default())
        self.info_label.setTextFormat(Qt.RichText)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(100)

        self.val_label = QLabel("V: 0")
        self.val_label.setFont(UIFonts.app_default())
        self.val_label.setStyleSheet(f"color: {UIColors.Semantic.TEXT_PRIMARY};")

        lbl_slider = QLabel("调节亮度(V):")
        lbl_slider.setFont(UIFonts.app_default())
        lbl_slider.setStyleSheet(f"color: {UIColors.Semantic.TEXT_PRIMARY};")

        slider_layout = QHBoxLayout()
        slider_layout.addWidget(lbl_slider)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.val_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self.info_label)
        layout.addWidget(self.img_label, 1)
        layout.addLayout(slider_layout)

        self.slider.valueChanged.connect(self._generate_base_image)
        self._H = None
        self._S = None

        self.process_samples(samples)

    def process_samples(self, samples):
        """计算极值，转换色彩空间，生成预览图"""
        arr_rgb = np.array(samples)
        rmin, gmin, bmin = arr_rgb.min(axis=0)
        rmax, gmax, bmax = arr_rgb.max(axis=0)
        r_mean, g_mean, b_mean = arr_rgb.mean(axis=0)
        hex_code = f"#{int(r_mean):02X}{int(g_mean):02X}{int(b_mean):02X}"

        arr_hsv = ColorUtils.rgb_to_hsv_cv2(arr_rgb)
        hues = arr_hsv[:, 0]
        svals = arr_hsv[:, 1] * 255.0
        vvals = arr_hsv[:, 2] * 255.0

        h_lo, h_hi = ColorUtils.hsv_circular_min_interval(hues)
        smin, smax = svals.min(), svals.max()
        vmin, vmax = vvals.min(), vvals.max()

        txt = (
            f"<table width='100%' style='color: {UIColors.Semantic.TEXT_PRIMARY};'>"
            f"  <tr>"
            f"    <td width='50%' valign='top'>"
            f"      <b>RGB 范围</b><br><br>"
            f"      R: [{rmin}, {rmax}]<br>"
            f"      G: [{gmin}, {gmax}]<br>"
            f"      B: [{bmin}, {bmax}]<br><br>"
            f"      <b>中心色值:</b> {hex_code} "
            f"      <span style='background-color: {hex_code}; border: 1px solid {UIColors.Semantic.BORDER_DEFAULT};'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>"
            f"    </td>"
            f"    <td width='50%' valign='top'>"
            f"      <b>HSV 范围</b><br><br>"
            f"      H: [{h_lo:.1f}°, {h_hi:.1f}°]<br>"
            f"      S: [{int(smin)}, {int(smax)}]<br>"
            f"      V: [{int(vmin)}, {int(vmax)}]"
            f"    </td>"
            f"  </tr>"
            f"</table>"
        )
        self.info_label.setText(txt)

        if h_hi < h_lo:
            h_hi += 360.0
        h_arr = (np.linspace(h_lo, h_hi, 200) % 360.0) / 360.0
        s_arr = np.linspace(smax, smin, 100) / 255.0
        self._H, self._S = np.meshgrid(h_arr, s_arr)

        self.slider.blockSignals(True)
        self.slider.setRange(int(vmin), int(vmax))
        self.slider.setValue(int(vmax))
        self.slider.blockSignals(False)
        self._generate_base_image(int(vmax))

    def _generate_base_image(self, v_val):
        """根据 V 值动态生成预览图"""
        if self._H is None:
            return
        self.val_label.setText(f"V: {v_val}")

        V = np.full_like(self._H, v_val / 255.0)
        hsv_image = np.dstack((self._H * 360.0, self._S, V)).astype(np.float32)
        rgb_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2RGB)

        img_data = (rgb_image * 255).astype(np.uint8)
        h, w, ch = img_data.shape
        qimg = QImage(img_data.data, w, h, ch * w, QImage.Format_RGB888).copy()

        self.img_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(self.img_label.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        )

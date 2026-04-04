# tools.py
# 屏幕工具：包含屏幕定位、测距、截图、区域选择、按键录制等功能

import sys
import os
import ctypes
import platform

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

from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPixmap, QCursor, QRegion, QKeySequence

from ui_styles import UIColors, UIFonts, UIStyles, UIDims


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

    # 绘制

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        screen_w = self.width()
        screen_h = self.height()
        cx, cy = self.current_pos.x(), self.current_pos.y()

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

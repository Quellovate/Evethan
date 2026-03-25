# ui_system.py
# 系统设置页面：包含 OSD 悬浮日志、OSD 配置工具、系统设置、默认参数设置

import sys
import os
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QScrollArea,
    QFrame,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen, QColor, QCursor, QPixmap

import driver
from config import global_config
from definitions import PARAM_TRANSLATIONS
from tools import KeyRecorder

from ui_styles import UIColors, UIDims, UIFonts, UIStyles
from ui_components import WidgetFactory, ToolboxList


# ============================================================
#  FloatingOSD —— 屏幕悬浮信息提示（OSD）
# ============================================================
class FloatingOSD(QWidget):
    """始终置顶、透明背景、不接收输入的 OSD 悬浮窗，用于显示任务执行状态"""

    def __init__(self):
        super().__init__()
        # 置顶 + 无边框 + 工具窗口 + 鼠标穿透
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.is_visible_by_hotkey = False  # 是否被快捷键切换为可见
        self.line1 = "等待任务启动..."
        self.line2 = ""
        self.reload_config()

    def reload_config(self):
        """从全局配置重新读取字号和中心坐标，并刷新显示"""
        self.font_size = global_config.get_app_setting("osd_font_size", 24)
        self.cx = global_config.get_app_setting("osd_center_x", 960)
        self.cy = global_config.get_app_setting("osd_center_y", 100)
        # OSD 铺满整个主屏幕（仅在中心坐标附近绘制文字）
        screen_geo = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geo)
        self.update()

    def toggle_visibility(self):
        """快捷键切换 OSD 显示/隐藏"""
        self.is_visible_by_hotkey = not self.is_visible_by_hotkey
        if self.is_visible_by_hotkey:
            self.show()
        else:
            self.hide()

    def update_text(self, title, detail, brief_line2, is_detail_only):
        """外部更新显示文本；若 is_detail_only 则忽略（OSD 只显示简要信息）"""
        if is_detail_only:
            return
        self.line1 = title
        self.line2 = brief_line2
        if self.is_visible_by_hotkey:
            self.update()

    # ---- 绘制 ----

    def paintEvent(self, event):
        """在中心坐标处绘制两行带描边的文字"""
        if not self.line1 and not self.line2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        font = UIFonts.osd(self.font_size)
        painter.setFont(font)
        fm = painter.fontMetrics()

        spacing = max(10, self.font_size // 3)
        h1 = fm.height()
        h2 = fm.height() if self.line2 else 0
        total_h = h1 + h2 + 10
        start_y = self.cy - (total_h // 2)

        if self.line1:
            self._draw_text_with_outline(painter, self.line1, self.cx, start_y + fm.ascent())
        if self.line2:
            self._draw_text_with_outline(painter, self.line2, self.cx, start_y + h1 + spacing + fm.ascent())

    def _draw_text_with_outline(self, painter, text, cx, base_y):
        """以 (cx, base_y) 为基准，先画描边再填充，实现带轮廓的文字效果"""
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        draw_x = cx - (text_w // 2)

        path = QPainterPath()
        path.addText(draw_x, base_y, painter.font(), text)

        outline_width = max(2, self.font_size // 8)
        # 描边
        painter.setPen(QPen(UIColors.OSD_TEXT_OUTLINE, outline_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        # 填充
        painter.setPen(Qt.NoPen)
        painter.setBrush(UIColors.OSD_TEXT_FILL)
        painter.drawPath(path)


# ============================================================
#  OSDConfigTool —— OSD 位置与字号的可视化配置工具
# ============================================================
class OSDConfigTool(QWidget):
    """全屏半透明覆盖层，拖拽移动 OSD 中心点，+/- 调节字号，右键保存退出"""

    config_saved = Signal()  # 保存后通知外部刷新

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        screen_geo = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geo)

        # 从配置读取当前值
        self.font_size = global_config.get_app_setting("osd_font_size", 24)
        self.cx = global_config.get_app_setting("osd_center_x", screen_geo.width() // 2)
        self.cy = global_config.get_app_setting("osd_center_y", 100)

        self.is_dragging = False
        self.drag_offset = QPoint()
        self.btn_plus_rect = QRect()
        self.btn_minus_rect = QRect()

    # ---- 绘制 ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 半透明遮罩
        painter.fillRect(self.rect(), UIColors.OSD_OVERLAY)

        # 顶部操作提示
        painter.setFont(UIFonts.osd_config_hint())
        painter.setPen(UIColors.TEXT_INVERSE)
        painter.drawText(
            self.rect().adjusted(0, 50, 0, 0),
            Qt.AlignTop | Qt.AlignHCenter,
            "拖动绿色文字移动位置 | 点击 +/- 调整大小\n（鼠标右键点击任意位置保存并退出）",
        )

        # 预览文字
        font = UIFonts.osd(self.font_size)
        painter.setFont(font)
        fm = painter.fontMetrics()

        line1 = "正在执行：1. 示例动作名称"
        line2 = "✅ 示例动作结果"
        spacing = max(10, self.font_size // 3)
        h1 = fm.height()
        h2 = fm.height()
        total_h = h1 + h2 + 10
        start_y = self.cy - (total_h // 2)

        self._draw_text_with_outline(painter, line1, self.cx, start_y + fm.ascent())
        self._draw_text_with_outline(painter, line2, self.cx, start_y + h1 + spacing + fm.ascent())

        # 十字准心
        painter.setPen(QPen(UIColors.OSD_CROSSHAIR, 1, Qt.DashLine))
        painter.drawLine(self.cx - 50, self.cy, self.cx + 50, self.cy)
        painter.drawLine(self.cx, self.cy - 50, self.cx, self.cy + 50)

        # +/- 按钮
        btn_y = start_y + total_h + 20
        btn_w, btn_h = 50, 40
        self.btn_minus_rect = QRect(self.cx - btn_w - 10, btn_y, btn_w, btn_h)
        self.btn_plus_rect = QRect(self.cx + 10, btn_y, btn_w, btn_h)

        painter.setPen(Qt.NoPen)
        painter.setBrush(UIColors.OSD_BTN_BG)
        painter.drawRoundedRect(self.btn_minus_rect, 5, 5)
        painter.drawRoundedRect(self.btn_plus_rect, 5, 5)

        painter.setPen(UIColors.TEXT_NORMAL)
        painter.setFont(UIFonts.osd_config_btn())
        painter.drawText(self.btn_minus_rect, Qt.AlignCenter, "-")
        painter.drawText(self.btn_plus_rect, Qt.AlignCenter, "+")

    def _draw_text_with_outline(self, painter, text, cx, base_y):
        """带描边的文字绘制（与 FloatingOSD 相同逻辑）"""
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        draw_x = cx - (text_w // 2)

        path = QPainterPath()
        path.addText(draw_x, base_y, painter.font(), text)

        outline_width = max(2, self.font_size // 8)
        painter.setPen(QPen(UIColors.OSD_TEXT_OUTLINE, outline_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        painter.setPen(Qt.NoPen)
        painter.setBrush(UIColors.OSD_TEXT_FILL)
        painter.drawPath(path)

    # ---- 鼠标交互 ----

    def mousePressEvent(self, event):
        # 右键：保存配置并关闭
        if event.button() == Qt.RightButton:
            global_config.set_app_setting("osd_font_size", self.font_size)
            global_config.set_app_setting("osd_center_x", self.cx)
            global_config.set_app_setting("osd_center_y", self.cy)
            self.config_saved.emit()
            self.close()
            return

        # 左键：点击按钮调节字号，或开始拖拽
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            if self.btn_minus_rect.contains(pos):
                self.font_size = max(12, self.font_size - 2)
                self.update()
            elif self.btn_plus_rect.contains(pos):
                self.font_size = min(96, self.font_size + 2)
                self.update()
            else:
                self.is_dragging = True
                self.drag_offset = QPoint(self.cx - pos.x(), self.cy - pos.y())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            # 拖拽更新中心点
            pos = event.pos()
            self.cx = pos.x() + self.drag_offset.x()
            self.cy = pos.y() + self.drag_offset.y()
            self.update()
        else:
            # 按钮区域显示手型光标，其余显示移动光标
            if self.btn_minus_rect.contains(event.pos()) or self.btn_plus_rect.contains(event.pos()):
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False


# ============================================================
#  SettingsWidget —— 系统设置页（驱动/日志/快捷键）
# ============================================================
class SettingsWidget(QWidget):
    settings_changed = Signal()  # 设置变更信号（通知主窗口重新注册快捷键等）

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        UIDims.apply_page_layout(layout)

        # ---------- 驱动设置区 ----------
        hw_box = QGroupBox("驱动设置")
        hw_box.setStyleSheet(UIStyles.PANEL_SETTINGS_HW)
        hw_layout = QVBoxLayout()

        self.chk_hardware = QCheckBox("启用硬件模拟")
        self.chk_hardware.setStyleSheet(UIStyles.LBL_SETTINGS_CHECKBOX)
        self.lbl_hw_hint = QLabel("勾选后将使用罗技驱动执行键鼠操作。\n未勾选时将使用 Windows API 软件模拟。")
        self.lbl_hw_hint.setStyleSheet(UIStyles.LBL_SETTINGS_HINT)

        hw_layout.addWidget(self.chk_hardware)
        hw_layout.addWidget(self.lbl_hw_hint)
        hw_box.setLayout(hw_layout)

        # 仅在驱动可用时显示该区域
        if driver.ActionDriver.is_driver_available():
            layout.addWidget(hw_box)
            is_hw_enabled = global_config.get_app_setting("use_hardware", True)
            self.chk_hardware.setChecked(is_hw_enabled)
            self.chk_hardware.clicked.connect(self.save_hardware_setting)
        else:
            hw_box.hide()

        # ---------- 日志与 OSD 设置区 ----------
        log_box = QGroupBox("日志与悬浮日志设置")
        log_box.setStyleSheet(UIStyles.PANEL_SETTINGS_LOG)

        log_main_layout = QHBoxLayout(log_box)
        log_main_layout.setContentsMargins(10, 10, 10, 10)

        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)
        log_main_layout.addLayout(log_layout, 1)

        # 右侧装饰图片
        lbl_img = QLabel()
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        img_path = os.path.join(base_dir, "assets", "jio.jpg")

        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            lbl_img.setPixmap(pixmap.scaledToHeight(120, Qt.SmoothTransformation))
        else:
            lbl_img.setText(" [找不到jio.jpg] ")
            lbl_img.setStyleSheet("color: #666666; font-style: italic;")

        lbl_img.setAlignment(Qt.AlignCenter)
        log_main_layout.addWidget(lbl_img, 0, Qt.AlignVCenter)
        log_main_layout.addSpacing(200)

        log_layout.addStretch()

        # 详细日志开关
        self.chk_detail_log = QCheckBox("启用详细日志模式")
        self.chk_detail_log.setStyleSheet(UIStyles.LBL_SETTINGS_CHECKBOX)

        lbl_log_hint = QLabel(
            "勾选后为【详细模式】：显示坐标计算、找图耗时、偏移过程等细节。\n"
            "未勾选时为【简要模式】：仅显示任务状态、当前步骤和关键结果。"
        )
        lbl_log_hint.setStyleSheet(UIStyles.LBL_SETTINGS_HINT)

        # OSD 位置调整按钮
        self.btn_adjust_osd = QPushButton("调整悬浮日志位置与大小")
        self.btn_adjust_osd.setCursor(Qt.PointingHandCursor)
        self.btn_adjust_osd.setStyleSheet(UIStyles.BTN_OSD_ADJUST)
        self.btn_adjust_osd.clicked.connect(self.open_osd_config)

        log_layout.addWidget(self.chk_detail_log)
        log_layout.addWidget(lbl_log_hint)
        log_layout.addWidget(self.btn_adjust_osd)
        log_box.setLayout(log_layout)
        layout.addWidget(log_box)

        is_detail_enabled = global_config.get_app_setting("detailed_log", False)
        self.chk_detail_log.setChecked(is_detail_enabled)
        self.chk_detail_log.clicked.connect(self.save_log_setting)
        log_layout.addStretch()

        # ---------- 快捷键配置区 ----------
        key_box = QGroupBox("快捷键配置")
        key_box.setStyleSheet(UIStyles.PANEL_SETTINGS_KEY)

        key_box_layout = QVBoxLayout(key_box)
        key_box_layout.setContentsMargins(0, 0, 0, 0)

        key_scroll = QScrollArea()
        key_scroll.setWidgetResizable(True)
        key_scroll.setFrameShape(QFrame.NoFrame)
        key_scroll.setStyleSheet("background-color: transparent;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        main_key_layout = QHBoxLayout(scroll_content)

        # 左列：可自定义快捷键
        left_container = QWidget()
        self.custom_key_layout = QFormLayout(left_container)
        self.custom_key_layout.setVerticalSpacing(6)
        self.custom_key_layout.setContentsMargins(0, 0, 10, 0)

        # 分隔线
        v_line = QFrame()
        v_line.setFrameShape(QFrame.VLine)
        v_line.setFrameShadow(QFrame.Sunken)
        v_line.setStyleSheet(UIStyles.SEPARATOR_VLINE)

        # 右列：固定快捷键（只读）
        right_container = QWidget()
        self.fixed_key_layout = QFormLayout(right_container)
        self.fixed_key_layout.setVerticalSpacing(6)
        self.fixed_key_layout.setContentsMargins(10, 0, 0, 0)

        main_key_layout.addWidget(left_container, 1)
        main_key_layout.addWidget(v_line)
        main_key_layout.addWidget(right_container, 1)

        key_scroll.setWidget(scroll_content)
        key_box_layout.addWidget(key_scroll)

        layout.addWidget(key_box, 1)

        # 可自定义快捷键的 action_key → 显示名称
        self.shortcut_map = {
            "run_task": "运行任务 (全局)",
            "stop_task": "停止任务 (全局)",
            "toggle_osd": "显示/隐藏悬浮日志 (全局)",
            "move_up": "指令上移 (编辑器)",
            "move_down": "指令下移 (编辑器)",
        }

        # 固定快捷键列表
        self.fixed_shortcuts = [
            ("Ctrl + S", "保存任务 (编辑器)"),
            ("Ctrl + A", "全选所有指令"),
            ("Ctrl + X", "剪切选中指令"),
            ("Ctrl + C", "复制选中指令"),
            ("Ctrl + V", "粘贴指令"),
            ("Ctrl + Z", "撤销操作 (Undo)"),
            ("Ctrl + Y", "重做操作 (Redo)"),
            ("Del / Backspace", "删除选中指令"),
        ]

        self.refresh_shortcut_ui()

    # ---- 快捷键 UI 构建 ----

    def refresh_shortcut_ui(self):
        """清空并重新构建左右两列快捷键表单"""
        # 清空左列
        while self.custom_key_layout.count():
            child = self.custom_key_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        # 清空右列
        while self.fixed_key_layout.count():
            child = self.fixed_key_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        current_shortcuts = global_config.get_shortcuts()

        # —— 左列：可自定义 ——
        lbl_left_title = QLabel("【可自定义快捷键】")
        lbl_left_title.setStyleSheet(UIStyles.LBL_SETTINGS_SECTION_TITLE)
        self.custom_key_layout.addRow(lbl_left_title)

        for action_key, desc in self.shortcut_map.items():
            val = current_shortcuts.get(action_key, "")

            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(40, 0, 0, 0)
            h.setSpacing(10)

            line = QLineEdit(val)
            line.setReadOnly(True)
            line.setMaximumWidth(UIDims.SETTINGS_KEY_INPUT_MAX_W)
            line.setFixedHeight(38)
            line.setStyleSheet(UIStyles.SETTINGS_KEY_INPUT_EDITABLE)

            btn_rec = QPushButton("录制")
            btn_rec.setCursor(Qt.PointingHandCursor)
            btn_rec.setFixedWidth(UIDims.SETTINGS_KEY_REC_BTN_W)
            btn_rec.setFixedHeight(38)
            btn_rec.setStyleSheet(UIStyles.BTN_SETTINGS_RECORD)
            btn_rec.clicked.connect(lambda _, k=action_key, l=line: self.record_key(k, l))

            h.addWidget(line)
            h.addWidget(btn_rec)
            h.addStretch()

            self.custom_key_layout.addRow(desc, container)

        # —— 右列：固定 ——
        lbl_right_title = QLabel("【固定快捷键】（不可修改）")
        lbl_right_title.setStyleSheet(UIStyles.LBL_SETTINGS_FIXED_TITLE)
        self.fixed_key_layout.addRow(lbl_right_title)

        for key_str, desc in self.fixed_shortcuts:
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(40, 0, 0, 0)

            line = QLineEdit(key_str)
            line.setReadOnly(True)
            line.setMaximumWidth(UIDims.SETTINGS_FIXED_KEY_INPUT_MAX_W)
            line.setFixedHeight(38)
            line.setStyleSheet(UIStyles.SETTINGS_KEY_INPUT_READONLY)

            h.addWidget(line)
            h.addStretch()

            self.fixed_key_layout.addRow(desc, container)

    # ---- 录制与保存 ----

    def record_key(self, action_key, line_edit):
        """打开按键录制器，录制完成后写入配置"""
        self.recorder = KeyRecorder()
        self.recorder.key_recorded.connect(lambda k: self.save_shortcut(action_key, k, line_edit))
        self.recorder.show()

    def save_shortcut(self, action_key, key_str, line_edit):
        """将录制到的快捷键保存到配置并更新 UI"""
        line_edit.setText(key_str)
        global_config.set_shortcut(action_key, key_str)
        self.settings_changed.emit()

    def save_hardware_setting(self):
        """保存硬件模拟开关（需重启生效）"""
        val = self.chk_hardware.isChecked()
        global_config.set_app_setting("use_hardware", val)
        QMessageBox.information(self, "设置已更改", "硬件模拟设置将在重启程序后生效")

    def save_log_setting(self):
        """保存详细日志开关。"""
        val = self.chk_detail_log.isChecked()
        global_config.set_app_setting("detailed_log", val)

    def open_osd_config(self):
        """打开 OSD 可视化配置工具"""
        self.osd_tool = OSDConfigTool()
        self.osd_tool.config_saved.connect(self.settings_changed.emit)
        self.osd_tool.show()


# ============================================================
#  DefaultSettingsWidget —— 指令默认参数编辑页
# ============================================================
class DefaultSettingsWidget(QWidget):
    """左侧选择指令类型，右侧编辑该指令的默认参数值"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        UIDims.apply_page_layout(layout)

        splitter = QSplitter(Qt.Horizontal)

        # ---------- 左侧：指令列表 ----------
        left_box = QGroupBox("选择指令")
        left_box.setStyleSheet(UIStyles.PANEL_CONFIG)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(5, 15, 5, 5)

        self.toolbox = ToolboxList(enable_drag=False)
        self.toolbox.itemClicked.connect(self.on_toolbox_clicked)
        left_layout.addWidget(self.toolbox)
        left_box.setLayout(left_layout)

        # ---------- 右侧：参数编辑表单 ----------
        right_box = QGroupBox("修改默认参数")
        right_box.setStyleSheet(UIStyles.PANEL_CONFIG)

        # 顶部提示
        lbl_hint = QLabel("在此处修改后的数值将作为新的【默认参数】 (即刻生效)", right_box)
        custom_hint_style = (
            UIStyles.LBL_HINT_ITALIC.replace("font-style: italic;", "") + " background-color: transparent;"
        )
        lbl_hint.setStyleSheet(custom_hint_style)
        lbl_hint.setFixedWidth(450)
        lbl_hint.move(180, 18)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(5, 15, 5, 5)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        self.form_layout.setVerticalSpacing(8)
        self.scroll.setWidget(self.form_widget)
        right_layout.addWidget(self.scroll)

        # 重置按钮
        btn_reset = QPushButton("重置该指令为原始设置")
        btn_reset.setStyleSheet(UIStyles.BTN_RESET_DANGER)
        btn_reset.clicked.connect(self.reset_current_cmd)
        right_layout.addWidget(btn_reset)
        right_box.setLayout(right_layout)

        splitter.addWidget(left_box)
        splitter.addWidget(right_box)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

        self.current_cmd_type = None   # 当前选中的指令类型
        self.active_widgets = {}       # key → 对应的输入控件

    # ---- 指令选择 ----

    def on_toolbox_clicked(self, item):
        """点击左侧列表项时加载对应指令的默认参数"""
        if item.data(Qt.UserRole):
            self.load_settings_for_cmd(item.data(Qt.UserRole))

    # ---- 加载参数表单 ----

    def load_settings_for_cmd(self, cmd_type):
        """根据指令类型，动态生成右侧参数编辑表单"""
        self.current_cmd_type = cmd_type
        self.active_widgets = {}

        # 清空旧表单
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        config = global_config.get_config().get(cmd_type)
        if not config:
            return

        for key, (data_type, current_default_val) in config["params"].items():
            # 跳过内部使用的参数
            if key in ["link_id", "collapsed", "region", "env_w", "env_h"]:
                continue

            label_text = PARAM_TRANSLATIONS.get(key, f"{key}:")

            # 鼠标按钮 —— 下拉框
            if key == "button":
                widget = QComboBox()
                widget.addItems(["left", "right", "middle"])
                current_val = str(current_default_val).lower()
                if current_val not in ["left", "right", "middle"]:
                    current_val = "left"
                widget.setCurrentText(current_val)
                widget.currentTextChanged.connect(lambda v, c=cmd_type, k=key: self._save_setting(c, k))
                self.active_widgets[key] = widget
                self.form_layout.addRow(label_text, widget)
                continue

            # 按键码 —— 文本框 + 录制按钮
            if key == "key_code":
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(5)

                widget = QLineEdit(str(current_default_val))
                widget.setPlaceholderText("例如: ctrl+c")
                widget.editingFinished.connect(lambda *args, c=cmd_type, k=key: self._save_setting(c, k))

                btn_record = QPushButton("录制")
                btn_record.setCursor(Qt.PointingHandCursor)
                btn_record.setStyleSheet(UIStyles.BTN_ACTION_GREEN)
                btn_record.clicked.connect(
                    lambda _, w=widget, c=cmd_type, k=key: self.open_key_recorder(w, c, k)
                )

                h_layout.addWidget(widget)
                h_layout.addWidget(btn_record)
                self.active_widgets[key] = widget
                self.form_layout.addRow(label_text, container)
                continue

            # 通用参数 —— 由工厂方法生成控件
            widget = WidgetFactory.create_input_widget(
                data_type,
                current_default_val,
                finish_callback=lambda *args, c=cmd_type, k=key: self._save_setting(c, k),
            )

            if widget:
                self.active_widgets[key] = widget
                if isinstance(widget, QLineEdit) and "image" in key:
                    widget.setPlaceholderText("默认图片文件名")
                if isinstance(widget, QCheckBox):
                    widget.setText("默认启用")
                self.form_layout.addRow(label_text, widget)

    # ---- 按键录制 ----

    def open_key_recorder(self, line_edit, cmd_type, key):
        """打开按键录制器，录制结果写回控件并保存"""
        self.recorder = KeyRecorder()
        self.recorder.key_recorded.connect(lambda k_str: self._on_key_recorded(line_edit, cmd_type, key, k_str))
        self.recorder.show()

    def _on_key_recorded(self, line_edit, cmd_type, key, key_str):
        """按键录制完成回调"""
        line_edit.setText(key_str)
        global_config.save_user_setting(cmd_type, key, key_str)

    # ---- 保存与重置 ----

    def _save_setting(self, cmd_type, key):
        """从对应控件读取值并写入全局配置"""
        if key not in self.active_widgets:
            return

        widget = self.active_widgets[key]
        val = None
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            val = widget.value()
        elif isinstance(widget, QLineEdit):
            val = widget.text()
        elif isinstance(widget, QCheckBox):
            val = widget.isChecked()
        elif isinstance(widget, QComboBox):
            val = widget.currentText()

        if val is not None:
            global_config.save_user_setting(cmd_type, key, val)

    def reset_current_cmd(self):
        """将当前指令的默认参数恢复为出厂值"""
        if not self.current_cmd_type:
            return
        reply = QMessageBox.question(
            self, "确认重置", f"确定要恢复 [{self.current_cmd_type}] 的出厂设置吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            global_config.reset_to_factory(self.current_cmd_type)
            self.load_settings_for_cmd(self.current_cmd_type)
            QMessageBox.information(self, "提示", "已恢复出厂设置。")

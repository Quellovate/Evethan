# ui_widgets.py
# 自定义属性控件库：包含各类单体控件，复合控件和控件装配工厂

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QLinearGradient, QColor, QPen, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QSizePolicy,
)

from definitions import PARAM_TRANSLATIONS
from ui_styles import UIColors, UIStyles, UIFonts, UIDims


# ============================================================
#  基类与接口定义
# ============================================================
class BaseParamWidget(QWidget):
    """参数控件基类，定义统一的数据交互接口"""

    valueChanged = Signal(object)  # 统一的数据变更信号，传递最新值

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_updating_ui = False  # UI 更新锁，防止代码修改 UI 时触发信号死循环

    def set_value(self, val):
        """接收外部数据并更新 UI"""
        raise NotImplementedError

    def get_value(self):
        """获取当前 UI 的最新数据"""
        raise NotImplementedError

    def _notify_value_changed(self, *args, **kwargs):
        """内部控件值改变时，触发数据变更信号"""
        if not self._is_updating_ui:
            self.valueChanged.emit(self.get_value())

    def clearFocus(self):
        """清除内部所有控件的焦点"""
        if hasattr(self, "inner_widget") and self.inner_widget:
            self.inner_widget.clearFocus()
        if hasattr(self, "btn") and self.btn:
            self.btn.clearFocus()
        super().clearFocus()


# ============================================================
#  复合 UI 控件
# ============================================================
class GenericParamWidget(BaseParamWidget):
    """标准 Qt 控件通用包装器"""

    def __init__(self, inner_widget, parent=None):
        super().__init__(parent)
        self.inner_widget = inner_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.inner_widget)

        if isinstance(self.inner_widget, (QSpinBox, QDoubleSpinBox)):
            self.inner_widget.editingFinished.connect(self._notify_value_changed)
        elif isinstance(self.inner_widget, QLineEdit):
            self.inner_widget.editingFinished.connect(self._notify_value_changed)
        elif isinstance(self.inner_widget, QCheckBox):
            self.inner_widget.clicked.connect(self._notify_value_changed)
        elif isinstance(self.inner_widget, QComboBox):
            self.inner_widget.currentTextChanged.connect(self._notify_value_changed)

    def set_value(self, val):
        self._is_updating_ui = True
        if isinstance(self.inner_widget, (QSpinBox, QDoubleSpinBox)):
            self.inner_widget.setValue(float(val) if isinstance(self.inner_widget, QDoubleSpinBox) else int(val))
        elif isinstance(self.inner_widget, QLineEdit):
            self.inner_widget.setText(str(val))
        elif isinstance(self.inner_widget, QCheckBox):
            self.inner_widget.setChecked(bool(val))
        elif isinstance(self.inner_widget, QComboBox):
            self.inner_widget.setCurrentText(str(val))
        self._is_updating_ui = False

    def get_value(self):
        if isinstance(self.inner_widget, (QSpinBox, QDoubleSpinBox)):
            return self.inner_widget.value()
        elif isinstance(self.inner_widget, QLineEdit):
            return self.inner_widget.text()
        elif isinstance(self.inner_widget, QCheckBox):
            return self.inner_widget.isChecked()
        elif isinstance(self.inner_widget, QComboBox):
            return self.inner_widget.currentText()


class ButtonParamWidget(BaseParamWidget):
    """为特定参数增加快捷按钮"""

    sig_action_clicked = Signal()

    def __init__(self, inner_widget: BaseParamWidget, btn_text, btn_style, parent=None):
        super().__init__(parent)
        self.inner_widget = inner_widget
        self.inner_widget.valueChanged.connect(self.valueChanged.emit)

        self.btn = QPushButton(btn_text)
        self.btn.setStyleSheet(btn_style)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.sig_action_clicked.emit)

        self.hide()

    def set_value(self, val):
        self.inner_widget.set_value(val)

    def get_value(self):
        return self.inner_widget.get_value()


# ============================================================
#  特定参数控件
# ============================================================


class ModeToggleWidget(BaseParamWidget):
    """找色模式切换按钮控件（基础/高级）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "basic"

        self.btn_toggle = QPushButton()
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_toggle.clicked.connect(self._on_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.btn_toggle)

    def set_value(self, val):
        self._is_updating_ui = True
        self._mode = str(val).lower()
        if self._mode not in ["basic", "advanced"]:
            self._mode = "basic"

        if self._mode == "basic":
            self.btn_toggle.setText("当前模式：【基础】")
            self.btn_toggle.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
        else:
            self.btn_toggle.setText("当前模式：【高级】")
            self.btn_toggle.setStyleSheet(UIStyles.BTN_ACTION_PURPLE)

        self._is_updating_ui = False

    def get_value(self):
        return self._mode

    def _on_clicked(self):
        new_mode = "advanced" if self._mode == "basic" else "basic"
        self.set_value(new_mode)
        self._notify_value_changed()


class HueRangeSlider(BaseParamWidget):
    """色相范围预览滑块"""

    def __init__(self, mode="basic", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

        self._h_start, self._h_end = 0.0, 360.0
        self._margin, self._bar_h, self._hit_r = 15, 12, 12
        self._dragging = None

        self.color_border = UIColors.GRAY_BORDER
        self.color_start_active = QColor(UIColors.Semantic.DANGER_BG)
        self.color_end_active = QColor(UIColors.Semantic.SUCCESS_BG)
        self.color_disabled = UIColors.GRAY_TEXT_SEC

    def set_value(self, val):
        if not isinstance(val, (list, tuple)) or len(val) != 2:
            return
        self._is_updating_ui = True
        self._h_start = max(0.0, min(360.0, val[0]))
        self._h_end = max(0.0, min(360.0, val[1]))
        self.update()
        self._is_updating_ui = False

    def get_value(self):
        return (self._h_start, self._h_end)

    @property
    def _track_w(self):
        return max(1, self.width() - 2 * self._margin)

    def _get_target(self, pos: QPointF):
        x, y = pos.x(), pos.y()
        x_s = self._margin + (self._h_start / 360.0) * self._track_w
        x_e = self._margin + (self._h_end / 360.0) * self._track_w

        dist_s = abs(x - x_s)
        dist_e = abs(x - x_e)

        if dist_s <= self._hit_r and dist_e <= self._hit_r:
            return "start" if y < self.height() / 2 else "end"
        if dist_s <= self._hit_r:
            return "start"
        if dist_e <= self._hit_r:
            return "end"
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bar_y = (self.height() - self._bar_h) / 2
        bar_rect = QRectF(self._margin, bar_y, self._track_w, self._bar_h)

        gradient = QLinearGradient(bar_rect.topLeft(), bar_rect.topRight())
        for i in range(7):
            gradient.setColorAt(i / 6, QColor.fromHsvF(i / 6, 1.0, 1.0))

        bar_path = QPainterPath()
        bar_path.addRoundedRect(bar_rect, self._bar_h / 2, self._bar_h / 2)

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(bar_path)

        x_s = self._margin + (self._h_start / 360.0) * self._track_w
        x_e = self._margin + (self._h_end / 360.0) * self._track_w

        painter.setClipPath(bar_path)
        painter.setBrush(QColor(0, 0, 0, 120))

        if self._h_start <= self._h_end:
            painter.drawRects(
                [
                    QRectF(self._margin, bar_y, x_s - self._margin, self._bar_h),
                    QRectF(x_e, bar_y, self.width() - self._margin - x_e, self._bar_h),
                ]
            )
        else:
            painter.drawRect(QRectF(x_e, bar_y, x_s - x_e, self._bar_h))

        painter.setClipping(False)
        painter.setPen(QPen(self.color_border, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(bar_path)

        c_start = self.color_disabled if self.mode == "basic" else self.color_start_active
        c_end = self.color_disabled if self.mode == "basic" else self.color_end_active

        self._draw_arrow(painter, x_s, bar_y - 2, True, c_start)
        self._draw_arrow(painter, x_e, bar_y + self._bar_h + 2, False, c_end)

    def _draw_arrow(self, painter, x, y, is_top, color):
        dy = -8 if is_top else 8
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon([QPointF(x, y), QPointF(x - 6, y + dy), QPointF(x + 6, y + dy)])

    def mousePressEvent(self, e: QMouseEvent):
        if self.mode == "basic":
            return
        if e.button() == Qt.LeftButton:
            self._dragging = self._get_target(e.position())

    def mouseMoveEvent(self, e: QMouseEvent):
        if self.mode == "basic":
            return

        if not self._dragging:
            self.setCursor(Qt.PointingHandCursor if self._get_target(e.position()) else Qt.ArrowCursor)
            return

        x = e.position().x()
        hue = max(0.0, min(360.0, (x - self._margin) / self._track_w * 360.0))

        if self._dragging == "start":
            self._h_start = hue
        else:
            self._h_end = hue

        self.update()
        if hasattr(self, "_w_start") and hasattr(self, "_w_end"):
            self._w_start.set_value(self._h_start)
            self._w_end.set_value(self._h_end)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self.mode == "basic":
            return
        self._dragging = None
        self._notify_value_changed()

    def bind_inputs(self, w_start, w_end):
        """修改参数框，同步移动滑块"""
        self._w_start = w_start
        self._w_end = w_end

        def on_input_changed(*args):
            try:
                h_s = float(self._w_start.get_value())
                h_e = float(self._w_end.get_value())
                self.set_value((h_s, h_e))
            except (ValueError, TypeError):
                pass

        self._w_start.valueChanged.connect(on_input_changed)
        self._w_end.valueChanged.connect(on_input_changed)


class KeyInputWidget(BaseParamWidget):
    """按键录制控件"""

    sig_request_record = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("例如: ctrl+c")
        self.line_edit.editingFinished.connect(self._notify_value_changed)

        self.btn_record = QPushButton("录制")
        self.btn_record.setCursor(Qt.PointingHandCursor)
        self.btn_record.setStyleSheet(UIStyles.BTN_ACTION_GREEN)
        self.btn_record.clicked.connect(lambda: self.sig_request_record.emit(self.line_edit))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.btn_record)

    def set_value(self, val):
        self._is_updating_ui = True
        self.line_edit.setText(str(val))
        self._is_updating_ui = False

    def get_value(self):
        return self.line_edit.text().strip()


class RegionSelector(BaseParamWidget):
    """区域框选控件"""

    sig_request_select = Signal()
    sig_request_reset = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_val = [0, 0, 0, 0]

        self.line_display = QLineEdit()
        self.line_display.setReadOnly(True)
        self.line_display.setStyleSheet(UIStyles.READONLY_INPUT)

        self.btn_select = QPushButton("框选")
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
        self.btn_select.clicked.connect(self.sig_request_select.emit)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(UIStyles.BTN_ACTION_RED)
        self.btn_reset.clicked.connect(self.sig_request_reset.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.line_display)
        layout.addWidget(self.btn_select)
        layout.addWidget(self.btn_reset)

    def set_value(self, val):
        self._is_updating_ui = True
        self._current_val = val
        if isinstance(val, list) and len(val) == 4 and (val[2] > 0 or val[3] > 0):
            self.line_display.setText(f"X:{val[0]} Y:{val[1]} {val[2]}x{val[3]}")
        else:
            self.line_display.setText("全屏 (自动)")
        self._is_updating_ui = False

    def get_value(self):
        return self._current_val


class ColorInputWidget(BaseParamWidget):
    """中心色值输入与预览控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_edit = QLineEdit()
        self.line_edit.editingFinished.connect(self._notify_value_changed)
        self.line_edit.textChanged.connect(self._update_preview)

        self.color_preview = QLabel()
        self.color_preview.setFixedWidth(60)
        self.color_preview.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Ignored)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.color_preview)

    def _update_preview(self, hex_str):
        hex_str = hex_str.strip()
        if len(hex_str) == 7 and hex_str.startswith("#"):
            self.color_preview.setStyleSheet(
                f"background-color: {hex_str}; border: 1px solid {UIColors.Semantic.BORDER_DEFAULT}; border-radius: 4px;"
            )

    def set_value(self, val):
        self._is_updating_ui = True
        self.line_edit.setText(str(val))
        self._update_preview(str(val))
        self._is_updating_ui = False

    def get_value(self):
        return self.line_edit.text().strip()


class AnchorComboBox(BaseParamWidget):
    """目标锚点下拉选择控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setStyleSheet(UIStyles.COMBOBOX_EDITABLE)

        self._options_list = []

        self.combo.lineEdit().editingFinished.connect(self._handle_editing_finished)
        self.combo.activated.connect(self._notify_value_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo)

    def set_anchor_options(self, options_list):
        """注入当前已有的锚点列表"""
        self._is_updating_ui = True
        self._options_list = options_list
        current = self.combo.currentText().strip()

        self.combo.clear()
        self.combo.addItems(options_list)

        matched = current
        if current:
            input_id = current.split()[0]
            for option in options_list:
                if option.startswith(input_id + " "):
                    matched = option
                    break

        self.combo.setCurrentText(matched)
        self._is_updating_ui = False

        if matched != current:
            self._notify_value_changed()

    def _handle_editing_finished(self):
        """自动补全锚点 ID"""
        text = self.combo.currentText().strip()
        if text:
            input_id = text.split()[0]
            for option in self._options_list:
                if option.startswith(input_id + " "):
                    self._is_updating_ui = True
                    self.combo.setCurrentText(option)
                    self._is_updating_ui = False
                    break
        self._notify_value_changed()

    def set_value(self, val):
        self._is_updating_ui = True
        self.combo.setCurrentText(str(val))
        self._is_updating_ui = False

    def get_value(self):
        return self.combo.currentText().strip()


# ============================================================
#  通用工厂
# ============================================================
class WidgetFactory:
    """根据参数创建对应的输入控件"""

    @staticmethod
    def create_widget(key, data_type, current_val, all_keys, preview_mode=False, batch_edit_mode=False):
        widget = None

        if key == "button":
            cb = QComboBox()
            cb.setStyleSheet("QComboBox { padding-left: 4px; }")
            cb.addItems(["left", "right", "middle"])
            safe_val = str(current_val).lower()
            if safe_val not in ["left", "right", "middle"]:
                safe_val = "left"
            current_val = safe_val
            widget = GenericParamWidget(cb)

        elif key == "mode":
            widget = ModeToggleWidget()
        # 在批量编辑模式下将跳过
        elif not batch_edit_mode:
            if key == "region":
                widget = RegionSelector()
            elif key == "center_hex":
                widget = ColorInputWidget()
            elif key == "target_id":
                widget = AnchorComboBox()
            elif key == "key_code":
                widget = KeyInputWidget()
            elif key == "mode":
                widget = ModeToggleWidget()

        if not widget:
            if data_type == int:
                sp = QSpinBox()
                sp.setRange(-9999, 9999)
                min_w = sp.sizeHint().width()
                sp.setRange(-9999999, 9999999)
                sp.setMinimumWidth(min_w)
                sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                widget = GenericParamWidget(sp)
            elif data_type == float:
                sp = QDoubleSpinBox()
                sp.setRange(-9999.0, 9999.0)
                if key == "confidence":
                    sp.setDecimals(2)
                    sp.setSingleStep(0.01)
                else:
                    sp.setDecimals(1)
                    sp.setSingleStep(0.1)
                min_w = sp.sizeHint().width()
                sp.setRange(-9999999.0, 9999999.0)
                sp.setMinimumWidth(min_w)
                sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                widget = GenericParamWidget(sp)
            elif data_type == str:
                le = QLineEdit()
                if "image" in key:
                    le.setPlaceholderText("请输入文件名")
                widget = GenericParamWidget(le)
            elif data_type == bool:
                cb = QCheckBox("启用")
                widget = GenericParamWidget(cb)
            else:
                return None

        if not widget:
            return None

        if key == "anchor_id":
            actual_widget = widget.inner_widget if hasattr(widget, "inner_widget") else widget
            if isinstance(actual_widget, QLineEdit):
                actual_widget.setReadOnly(True)

        widget.set_value(current_val)

        if preview_mode:
            widget.setEnabled(False)
            return widget

        # 特定参数挂载辅助快捷按钮
        if not batch_edit_mode:
            if key == "image_path":
                widget = ButtonParamWidget(widget, "快捷截图", UIStyles.BTN_ACTION_ORANGE)
            elif key == "center_hex":
                widget = ButtonParamWidget(widget, "快捷取色", UIStyles.BTN_ACTION_ORANGE)
            elif key == "y" and "x" in all_keys:
                widget = ButtonParamWidget(widget, "快捷填入坐标", UIStyles.BTN_ACTION_BLUE)
            elif key == "y1" and "x1" in all_keys:
                widget = ButtonParamWidget(widget, "快捷填入起点", UIStyles.BTN_ACTION_BLUE)
            elif key == "y2" and "x2" in all_keys:
                widget = ButtonParamWidget(widget, "快捷填入终点", UIStyles.BTN_ACTION_BLUE)
            elif key == "off_y" and "off_x" in all_keys:
                btn_text = "快捷填入偏移 (修正起点)" if "drag_dx" in all_keys else "快捷填入偏移"
                widget = ButtonParamWidget(widget, btn_text, UIStyles.BTN_ACTION_PURPLE)
            elif key == "drag_dy" and "drag_dx" in all_keys:
                widget = ButtonParamWidget(widget, "快捷填入拖动距离 (动作路径)", UIStyles.BTN_ACTION_DEEP_PURPLE)

        return widget

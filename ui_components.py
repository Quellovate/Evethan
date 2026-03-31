# ui_components.py
# 本模块包含脚本编辑器的所有核心UI组件：
# 工具箱列表、任务编辑器、属性编辑器、批量编辑器、任务说明编辑器等

import copy
import json
import os
import time
import uuid
from collections import deque

from PySide6.QtCore import QKeyCombination, QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDrag, QFont, QIcon, QKeySequence, QPen, QShortcut, QPixmap, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from config import global_config
from definitions import PARAM_TRANSLATIONS, DISPLAY_NAME_OVERRIDE
from tools import KeyRecorder, ScreenTool
from ui_styles import UIColors, UIDims, UIStyles, UIFonts


# ============================================================
#  通用工厂：根据数据类型创建对应的输入控件
# ============================================================
class WidgetFactory:
    """根据参数的数据类型，自动创建 QSpinBox / QLineEdit / QCheckBox 等控件"""

    @staticmethod
    def create_input_widget(data_type, value, finish_callback=None):
        widget = None
        if data_type == int:
            widget = QSpinBox()
            widget.setRange(-9999, 9999)
            widget.setValue(int(value))
            if finish_callback:
                widget.editingFinished.connect(finish_callback)
        elif data_type == float:
            widget = QDoubleSpinBox()
            widget.setRange(0.0, 9999.0)
            widget.setSingleStep(0.1)
            widget.setValue(float(value))
            if finish_callback:
                widget.editingFinished.connect(finish_callback)
        elif data_type == str:
            widget = QLineEdit(str(value))
            if finish_callback:
                widget.editingFinished.connect(finish_callback)
        elif data_type == bool:
            widget = QCheckBox("启用")
            widget.setChecked(bool(value))
            if finish_callback:
                widget.clicked.connect(finish_callback)
        return widget


# ============================================================
#  撤销/重做 历史管理器
# ============================================================
class HistoryManager:
    """管理撤销(Undo)和重做(Redo)操作，基于快照机制"""

    def __init__(self, timeline, max_history=30):
        self.timeline = timeline
        self.undo_stack = deque(maxlen=max_history)  # 撤销栈
        self.redo_stack = deque(maxlen=max_history)  # 重做栈
        self.is_performing_undo_redo = False          # 防止在撤销/重做时再次记录快照

    def create_snapshot(self, action_name="未知操作"):
        """在执行操作前创建一份当前状态的深拷贝快照"""
        if self.is_performing_undo_redo:
            return
        current_state = self.timeline.get_all_data_deep_copy()
        self.undo_stack.append((current_state, action_name))
        self.redo_stack.clear()  # 新操作后清空重做栈
        self.timeline.history_changed.emit()

    def undo(self):
        """撤销：弹出上一个快照并恢复，同时把当前状态压入重做栈"""
        if not self.undo_stack:
            return
        self.is_performing_undo_redo = True
        try:
            current_row = self.timeline.currentRow()
            current_state = self.timeline.get_all_data_deep_copy()
            prev_state_data, action_name = self.undo_stack.pop()
            self.redo_stack.append((current_state, action_name))
            self.timeline.load_from_data(prev_state_data)
            # 尝试保持选中行不变
            if current_row != -1 and current_row < self.timeline.count():
                self.timeline.setCurrentRow(current_row)
                item = self.timeline.item(current_row)
                self.timeline.on_item_clicked(item)
            self.timeline.history_changed.emit()
        finally:
            self.is_performing_undo_redo = False

    def redo(self):
        """重做：弹出重做栈顶快照并恢复"""
        if not self.redo_stack:
            return
        self.is_performing_undo_redo = True
        try:
            current_row = self.timeline.currentRow()
            current_state = self.timeline.get_all_data_deep_copy()
            next_state_data, action_name = self.redo_stack.pop()
            self.undo_stack.append((current_state, action_name))
            self.timeline.load_from_data(next_state_data)
            if current_row != -1 and current_row < self.timeline.count():
                self.timeline.setCurrentRow(current_row)
                item = self.timeline.item(current_row)
                self.timeline.on_item_clicked(item)
            self.timeline.history_changed.emit()
        finally:
            self.is_performing_undo_redo = False

    def get_status_text(self):
        """返回撤销/重做栈顶的操作名称，供状态栏显示"""
        undo_text = self.undo_stack[-1][1] if self.undo_stack else "无"
        redo_text = self.redo_stack[-1][1] if self.redo_stack else "无"
        return undo_text, redo_text


# ============================================================
#  自定义绘制委托：控制任务编排列表中每一行的绘制方式
# ============================================================
class TaskDelegate(QStyledItemDelegate):
    """自定义列表项绘制：含勾选框、缩进引导线、折叠按钮、按键录制按钮等"""

    def paint(self, painter, option, index):
        painter.save()
        item_data = index.data(Qt.UserRole)
        is_checked = item_data.get("checked", False)
        cmd_type = item_data.get("type", "")
        params = item_data.get("params", {})
        rect = option.rect

        # ---------- 分割线类型：特殊绘制后直接返回 ----------
        if cmd_type == "separator":
            painter.fillRect(rect, UIColors.SEPARATOR_BG)
            painter.setPen(UIColors.SEPARATOR_TEXT)
            painter.setFont(UIFonts.delegate_separator(option.font))
            painter.drawText(rect, Qt.AlignCenter, params.get("label", "—— 分割线 ——"))
            painter.setPen(UIColors.SEPARATOR_LINE)
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            painter.restore()
            return

        # ---------- 计算缩进与区域 ----------
        indent_level = item_data.get("_cache_indent", 0)
        strip_w = UIDims.DELEGATE_STRIP_WIDTH
        # 左侧色条区域（放置勾选框）
        left_strip_rect = QRect(rect.left(), rect.top(), strip_w, rect.height())
        content_offset = indent_level * UIDims.DELEGATE_INDENT_STEP
        # 主内容区域（去掉色条和缩进）
        main_body_rect = QRect(
            rect.left() + strip_w + content_offset, rect.top(), rect.width() - strip_w - content_offset, rect.height()
        )

        # ---------- 绘制左侧色条与勾选框 ----------
        painter.fillRect(left_strip_rect, UIColors.STRIP_BG)
        painter.setPen(UIColors.STRIP_LINE)
        painter.drawLine(left_strip_rect.topRight(), left_strip_rect.bottomRight())

        list_widget = option.widget
        style = list_widget.style()
        opt = QStyleOptionButton()
        chk_size = UIDims.DELEGATE_CHECKBOX_SIZE
        chk_x = left_strip_rect.x() + UIDims.DELEGATE_CHECKBOX_MARGIN_LEFT
        chk_y = left_strip_rect.y() + (left_strip_rect.height() - chk_size) // 2
        opt.rect = QRect(chk_x, chk_y, chk_size, chk_size)
        opt.state = QStyle.State_Enabled | QStyle.State_Active
        opt.state |= QStyle.State_On if is_checked else QStyle.State_Off
        style.drawPrimitive(QStyle.PE_IndicatorCheckBox, opt, painter, list_widget)

        # ---------- 根据指令类型和选中状态决定背景色 ----------
        is_selected = option.state & QStyle.State_Selected
        if "loop_" in cmd_type:
            bg_color = UIColors.BG_LOOP_SEL if is_selected else UIColors.BG_LOOP
        elif "group_" in cmd_type:
            bg_color = UIColors.BG_GROUP_SEL if is_selected else UIColors.BG_GROUP
        elif "if_" in cmd_type or cmd_type == "else_branch":
            bg_color = UIColors.BG_IF_SEL if is_selected else UIColors.BG_IF
        else:
            bg_color = UIColors.BG_NORMAL_SEL if is_selected else UIColors.BG_NORMAL

        painter.fillRect(main_body_rect, bg_color)

        # ---------- 绘制缩进引导线（虚线） ----------
        if indent_level > 0:
            painter.setPen(QPen(UIColors.GUIDE_LINE, 1, Qt.DashLine))
            step = UIDims.DELEGATE_INDENT_STEP
            for lvl in range(1, indent_level + 1):
                line_x = rect.left() + strip_w + (lvl * step)
                painter.drawLine(line_x, rect.top(), line_x, rect.bottom())

        content_start_x = rect.left() + strip_w + (indent_level * UIDims.DELEGATE_INDENT_STEP) + 5

        # ---------- 分组起始行：绘制折叠按钮 + 标签 ----------
        if cmd_type == "group_start":
            is_collapsed = params.get("collapsed", False)
            btn_size = UIDims.DELEGATE_FOLD_BTN_SIZE
            btn_rect = QRect(content_start_x, rect.top() + (rect.height() - btn_size) // 2, btn_size, btn_size)
            painter.setPen(UIColors.FOLD_BTN_BORDER)
            painter.setBrush(UIColors.FOLD_BTN_BG)
            painter.drawRect(btn_rect)
            # 绘制 +/- 号
            painter.setPen(UIColors.FOLD_BTN_SYMBOL)
            center = btn_rect.center()
            painter.drawLine(center.x() - 3, center.y(), center.x() + 3, center.y())
            if is_collapsed:
                painter.drawLine(center.x(), center.y() - 3, center.x(), center.y() + 3)
            text_x = content_start_x + btn_size + 8
            group_label = params.get("label", "分组")
            painter.setFont(UIFonts.delegate_bold(option.font))
            text_rect = QRect(text_x, rect.top(), rect.right() - text_x, rect.height())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, f"{group_label}")

        # ---------- 按键类指令：绘制录制按钮和按键显示框 ----------
        elif cmd_type in ["key_press", "key_long_press"]:
            text = index.data(Qt.DisplayRole)
            painter.setPen(UIColors.TEXT_NORMAL)
            title_rect = QRect(content_start_x, rect.top() + 4, rect.right() - content_start_x, 20)
            painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop, text)
            btn_y = rect.top() + UIDims.DELEGATE_INNER_MARGIN_TOP
            btn_rec_w = UIDims.BTN_REC_WIDTH
            btn_rec_h = UIDims.BTN_REC_HEIGHT
            # 录制按钮
            btn_rect = QRect(content_start_x, btn_y, btn_rec_w, btn_rec_h)
            painter.setBrush(UIColors.BTN_RECORD_BG)
            painter.setPen(UIColors.BTN_RECORD_BORDER)
            painter.drawRoundedRect(btn_rect, 3, 3)
            painter.setFont(UIFonts.delegate_rec_btn(option.font))
            painter.setPen(UIColors.BTN_RECORD_TEXT)
            painter.drawText(btn_rect, Qt.AlignCenter, "录制")
            # 按键值显示框
            display_x = content_start_x + btn_rec_w + 8
            display_rect = QRect(display_x, btn_y, 120, btn_rec_h)
            painter.setBrush(UIColors.BG_INNER_BOX)
            painter.setPen(UIColors.REC_DISPLAY_BORDER)
            painter.drawRoundedRect(display_rect, 2, 2)
            painter.setPen(UIColors.TEXT_NORMAL)
            painter.drawText(
                display_rect.adjusted(5, 0, -5, 0), Qt.AlignVCenter | Qt.AlignLeft, str(params.get("key_code", ""))
            )

        # ---------- 其他指令：普通文本绘制 ----------
        else:
            text_x = content_start_x
            text = index.data(Qt.DisplayRole)
            if any(x in cmd_type for x in ["loop_start", "if_start"]):
                painter.setFont(UIFonts.delegate_bold(option.font))
            if cmd_type in ["break_loop", "stop_task"]:
                painter.setPen(UIColors.TEXT_KEYWORD)
                painter.setFont(UIFonts.delegate_bold(option.font))
            else:
                painter.setPen(UIColors.TEXT_NORMAL)
            text_rect = QRect(text_x, rect.top(), rect.right() - text_x, rect.height())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

        # ---------- 底部分隔线 ----------
        painter.setPen(UIColors.ITEM_BOTTOM_BORDER)
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        # ---------- 拖拽放置指示线 ----------
        drop_row = getattr(option.widget, "drop_indicator_row", -1)
        if drop_row != -1:
            pen = QPen(UIColors.DROP_LINE, 3)
            painter.setPen(pen)
            current_row = index.row()
            if drop_row == current_row:
                painter.drawLine(rect.topLeft(), rect.topRight())
            elif drop_row == option.widget.count() and current_row == option.widget.count() - 1:
                painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        painter.restore()


# ============================================================
#  工具箱列表：左侧可拖拽的指令面板
# ============================================================
class ToolboxList(QListWidget):
    """左侧工具箱：按分类展示所有可用指令，支持拖拽"""

    def __init__(self, enable_drag=True):
        super().__init__()
        self.enable_drag = enable_drag
        self.setDragEnabled(enable_drag)
        self.setStyleSheet(UIStyles.LIST_WIDGET_BASE)
        # 指令分类定义
        self.categories = [
            (
                "鼠标操作",
                [
                    "mouse_move", "scroll", "camera_turn",
                    "fixed_click", "offset_click", "image_click",
                    "fixed_long_press", "offset_long_press", "image_long_press",
                    "mouse_drag", "image_drag",
                ],
            ),
            ("键盘操作", ["key_press", "key_long_press"]),
            ("流程控制", ["wait", "find_image", "break_loop", "stop_task"]),
            ("结构模块", ["loop_start", "if_start", "else_branch", "group_start", "separator"]),
        ]
        self.populate_tools()

    def populate_tools(self):
        """根据分类和全局配置，填充工具箱列表项"""
        full_config = global_config.get_config()
        # 各分类对应的项目背景色
        bg_color_map = {
            "鼠标操作": UIColors.TOOLBOX_ITEM_MOUSE,
            "键盘操作": UIColors.TOOLBOX_ITEM_KEYBOARD,
            "流程控制": UIColors.TOOLBOX_ITEM_CONTROL,
        }
        # 分类标题的背景色和文字色
        header_style_map = {
            "鼠标操作": (UIColors.TOOLBOX_HEADER_MOUSE_BG, UIColors.TOOLBOX_HEADER_MOUSE_TEXT),
            "键盘操作": (UIColors.TOOLBOX_HEADER_KEYBOARD_BG, UIColors.TOOLBOX_HEADER_KEYBOARD_TEXT),
            "流程控制": (UIColors.TOOLBOX_HEADER_CONTROL_BG, UIColors.TOOLBOX_HEADER_CONTROL_TEXT),
        }
        for category_name, cmd_list in self.categories:
            # 添加分类标题（不可点击/拖拽）
            header_item = QListWidgetItem(category_name)
            if category_name in header_style_map:
                bg_color, text_color = header_style_map[category_name]
                header_item.setBackground(QBrush(bg_color))
                header_item.setForeground(QBrush(text_color))
            else:
                header_item.setBackground(UIColors.TOOLBOX_HEADER_BG)
                header_item.setForeground(UIColors.TOOLBOX_HEADER_TEXT)
            header_item.setFont(UIFonts.toolbox_header(header_item.font()))
            header_item.setFlags(Qt.NoItemFlags)
            header_item.setSizeHint(QSize(0, UIDims.TOOLBOX_HEADER_H))
            self.addItem(header_item)
            # 添加该分类下的各条指令
            for cmd_type in cmd_list:
                if cmd_type not in full_config:
                    continue
                config = full_config[cmd_type]
                label = DISPLAY_NAME_OVERRIDE.get(cmd_type, config["label"])
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, cmd_type)
                item.setToolTip(config["desc"])
                item.setSizeHint(QSize(0, UIDims.TOOLBOX_ITEM_H))
                if category_name in bg_color_map:
                    item.setBackground(QBrush(bg_color_map[category_name]))
                self.addItem(item)

    def startDrag(self, supportedActions):
        """开始拖拽：将指令类型作为 MIME 文本传递"""
        if not self.enable_drag:
            return
        item = self.currentItem()
        if not item:
            return
        cmd_type = item.data(Qt.UserRole)
        if not cmd_type:
            return
        mime_data = QMimeData()
        mime_data.setText(cmd_type)
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction)


# ============================================================
#  任务编排列表：管理所有指令的排列与交互
# ============================================================
class ScriptTimeline(QListWidget):
    """任务编排列表：支持拖拽排序、勾选批量操作、折叠分组、撤销重做等"""

    structure_changed = Signal()  # 结构变化信号（缩进/行号等需要刷新时）
    history_changed = Signal()   # 撤销/重做栈变化信号

    def __init__(self, property_panel):
        super().__init__()
        self.property_panel = property_panel
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setItemDelegate(TaskDelegate())
        self.setFocusPolicy(Qt.ClickFocus)
        self.setStyleSheet(UIStyles.TIMELINE_BASE)
        self.itemClicked.connect(self.on_item_clicked)

        # 初始化历史管理器，并将回调传递给属性面板
        self.history_mgr = HistoryManager(self, max_history=30)
        self.property_panel.set_history_callback(self.history_mgr.create_snapshot)
        self.property_panel.set_undo_redo_callbacks(self.history_mgr.undo, self.history_mgr.redo)

        # 拖拽指示器行号（-1 表示不显示）
        self.drop_indicator_row = -1

        # 鼠标交互状态机相关变量
        self._interaction_mode = "none"        # 当前交互模式
        self._drag_start_pos = None            # 拖拽起始位置
        self._swipe_anchor_row = -1            # 滑动勾选的锚定行
        self._initial_check_states = {}        # 滑动勾选开始前各行的勾选状态
        self._swipe_target_value = None        # 滑动勾选的目标值
        self._dragged_items = []               # 当前正在拖拽的项目列表

    # -------------------- 数据获取/辅助 --------------------

    def get_all_data_deep_copy(self):
        """获取所有项目数据的深拷贝（用于撤销/重做快照）"""
        return copy.deepcopy([self.item(i).data(Qt.UserRole) for i in range(self.count())])

    def get_all_data(self):
        """获取所有项目数据的引用列表"""
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]

    def _get_item_desc(self, item):
        """获取项目的描述文本（用于日志/提示）"""
        if not item:
            return "未知指令"
        data = item.data(Qt.UserRole)
        return data.get("desc", data.get("type", "指令"))

    def _get_indent_level(self, row):
        """获取指定行的缩进层级"""
        item = self.item(row)
        if not item:
            return 0
        return item.data(Qt.UserRole).get("_cache_indent", 0)

    def _has_checked_items(self):
        """检查是否有任何项目被勾选"""
        return any(self.item(i).data(Qt.UserRole).get("checked", False) for i in range(self.count()))

    # -------------------- UI刷新 --------------------

    def refresh_ui(self):
        """统一刷新：更新缩进缓存 → 刷新行号 → 发出结构变化信号"""
        self.update_indentation_cache()
        self.refresh_line_numbers()
        self.structure_changed.emit()
        self.viewport().update()

    def update_indentation_cache(self):
        """遍历所有项，根据结构层级计算并缓存每项的缩进深度"""
        depth = 0
        for i in range(self.count()):
            item = self.item(i)
            data = item.data(Qt.UserRole)
            t = data.get("type", "")
            current_indent = depth
            # 结束标记：先减深度
            if t in ["loop_end", "group_end", "if_end"]:
                depth = max(0, depth - 1)
                current_indent = depth
            elif t == "else_branch":
                current_indent = max(0, depth - 1)
            # 仅在值变化时写入，减少不必要的 setData 调用
            if data.get("_cache_indent") != current_indent:
                data["_cache_indent"] = current_indent
                item.setData(Qt.UserRole, data)
            # 开始标记：后增深度
            if t in ["loop_start", "group_start", "if_start"]:
                depth += 1

    def refresh_line_numbers(self):
        """更新每个项的显示文本（行号 + 描述）"""
        for i in range(self.count()):
            item = self.item(i)
            data = item.data(Qt.UserRole)
            prefix = f"{i + 1}. "
            label = data.get("desc", "未命名")
            if data["type"] == "group_start":
                label = f"📂 {data['params'].get('label', '分组')}"
            item.setText(f"{prefix}{label}")

    def _apply_fold_states(self):
        """根据分组的折叠状态，隐藏/显示组内子项"""
        current_collapsed_id = None
        for i in range(self.count()):
            item = self.item(i)
            data = item.data(Qt.UserRole)
            t = data.get("type", "")
            params = data.get("params", {})
            link_id = params.get("link_id")
            if current_collapsed_id:
                # 遇到对应的 group_end 时结束折叠
                if t == "group_end" and link_id == current_collapsed_id:
                    item.setHidden(False)
                    current_collapsed_id = None
                else:
                    item.setHidden(True)
            elif t == "group_start" and params.get("collapsed", False):
                current_collapsed_id = link_id
                item.setHidden(False)
            else:
                item.setHidden(False)

    # -------------------- 数据加载/重建 --------------------

    def refresh_with_data(self, new_data_list):
        """用新的数据列表完整重建编排状态（保持滚动位置）"""
        self.setUpdatesEnabled(False)
        scroll_val = self.verticalScrollBar().value()
        self.clear()
        for data in new_data_list:
            data["checked"] = False
            item = self._create_item_from_data(data)
            self.addItem(item)
        self._apply_fold_states()
        self.refresh_ui()
        QApplication.processEvents()
        self.verticalScrollBar().setValue(scroll_val)
        self.setUpdatesEnabled(True)

    def load_from_data(self, script_data):
        """从数据列表加载（撤销/重做/文件加载时使用）"""
        self.property_panel.clear_panel()
        self.refresh_with_data(script_data)

    def _create_item_from_data(self, data):
        """根据数据字典创建一个 QListWidgetItem，并设置合适的行高"""
        item = QListWidgetItem()
        t = data.get("type", "")
        height = UIDims.ITEM_H_NORMAL
        if t in ["key_press", "key_long_press"]:
            height = UIDims.ITEM_H_KEY
        elif any(x in t for x in ["loop_", "group_", "if_"]):
            height = UIDims.ITEM_H_STRUCTURE
        elif t == "separator":
            height = UIDims.ITEM_H_SEPARATOR
        item.setSizeHint(QSize(0, height))
        item.setData(Qt.UserRole, data)
        return item

    # -------------------- 添加指令 --------------------

    def add_new_cmd(self, cmd_type, data=None):
        """在当前行之后添加新指令（自动处理成对结构）"""
        current_row = self.currentRow()
        insert_row_idx = (current_row + 1) if current_row != -1 else (self.count() + 1)
        full_config = global_config.get_config()
        label = DISPLAY_NAME_OVERRIDE.get(cmd_type, full_config.get(cmd_type, {}).get("label", cmd_type))
        self.history_mgr.create_snapshot(f"在第 {insert_row_idx} 行添加 [{label}]")
        # 成对结构（循环/分组/判断）的特殊处理
        if cmd_type == "loop_start" and data is None:
            self.add_paired_module(insert_row_idx - 1, "loop")
        elif cmd_type == "group_start" and data is None:
            self.add_paired_module(insert_row_idx - 1, "group")
        elif cmd_type == "if_start" and data is None:
            self.add_paired_module(insert_row_idx - 1, "if")
        else:
            self._insert_cmd_at(insert_row_idx - 1, cmd_type, data)

    def add_paired_module(self, row, mode="loop"):
        """插入成对的开始/结束标记（循环、分组、条件判断），共享 link_id"""
        full_config = global_config.get_config()
        link_id = str(uuid.uuid4())[:8]
        start_type = f"{mode}_start"
        end_type = f"{mode}_end"
        start_data = {
            "type": start_type,
            "desc": full_config[start_type]["label"],
            "params": {k: v[1] for k, v in full_config[start_type]["params"].items()},
            "checked": False,
        }
        start_data["params"]["link_id"] = link_id
        end_data = {
            "type": end_type,
            "desc": full_config[end_type]["label"],
            "params": {k: v[1] for k, v in full_config[end_type]["params"].items()},
            "checked": False,
        }
        end_data["params"]["link_id"] = link_id
        self._insert_cmd_at(row, start_data)
        self._insert_cmd_at(row + 1, end_data)
        self.setCurrentRow(row)
        self.on_item_clicked(self.item(row))

    def _insert_cmd_at(self, row, cmd_type_or_data, data=None):
        """在指定行插入一条指令（支持传入 cmd_type 字符串或完整 data 字典）"""
        current_scroll = self.verticalScrollBar().value()
        self.setUpdatesEnabled(False)
        full_config = global_config.get_config()
        if isinstance(cmd_type_or_data, dict):
            final_data = cmd_type_or_data
        else:
            cmd_type = cmd_type_or_data
            if cmd_type not in full_config:
                self.setUpdatesEnabled(True)
                return
            config = full_config[cmd_type]
            if data is None:
                final_data = {
                    "type": cmd_type,
                    "desc": config["label"],
                    "params": {k: v[1] for k, v in config["params"].items()},
                    "checked": False,
                }
            else:
                final_data = data
        item = self._create_item_from_data(final_data)
        self.insertItem(row, item)
        self.refresh_ui()
        self.setCurrentItem(item)
        self.verticalScrollBar().setValue(current_scroll)
        self.setUpdatesEnabled(True)

    # -------------------- 按键录制（内联） --------------------

    def open_inline_key_recorder(self, item):
        """打开按键录制器（在列表项内的录制按钮触发）"""
        self.key_recorder = KeyRecorder()
        self.key_recorder.key_recorded.connect(lambda k: self.update_key_code(item, k))
        self.key_recorder.show()

    def update_key_code(self, item, code_str):
        """录制完成后更新按键值"""
        row = self.row(item) + 1
        name = self._get_item_desc(item)
        self.history_mgr.create_snapshot(f"修改第 {row} 行 [{name}] 的按键为 '{code_str}'")
        data = item.data(Qt.UserRole)
        data["params"]["key_code"] = code_str
        item.setData(Qt.UserRole, data)
        self.refresh_ui()
        if self.currentItem() == item:
            self.property_panel.load_properties(item, data)

    # -------------------- 鼠标事件处理 --------------------

    def mousePressEvent(self, event):
        """鼠标按下：区分点击区域，进入不同交互模式"""
        pos_int = event.position().toPoint()
        x, y = pos_int.x(), pos_int.y()
        item = self.itemAt(pos_int)
        if not item:
            super().mousePressEvent(event)
            return
        data = item.data(Qt.UserRole)
        rect = self.visualItemRect(item)
        indent = self._get_indent_level(self.row(item))
        strip_w = UIDims.DELEGATE_STRIP_WIDTH
        indent_step = UIDims.DELEGATE_INDENT_STEP
        content_start_x = rect.left() + strip_w + (indent * indent_step) + 5

        # 点击分组折叠按钮
        if data.get("type") == "group_start":
            fold_btn_size = UIDims.DELEGATE_FOLD_BTN_SIZE
            if content_start_x <= x <= content_start_x + fold_btn_size:
                self.toggle_group_fold(item)
                return

        # 点击按键录制按钮
        if data.get("type") in ["key_press", "key_long_press"]:
            btn_y_start = rect.top() + UIDims.DELEGATE_INNER_MARGIN_TOP
            btn_x_start = content_start_x
            btn_w = UIDims.BTN_REC_WIDTH
            btn_h = UIDims.BTN_REC_HEIGHT
            if btn_x_start <= x <= btn_x_start + btn_w and btn_y_start <= y <= btn_y_start + btn_h:
                self.open_inline_key_recorder(item)
                return

        # 点击左侧色条区域：进入勾选或滑动选择模式
        if data.get("type") != "separator":
            chk_size = UIDims.DELEGATE_CHECKBOX_SIZE
            chk_start = UIDims.DELEGATE_CHECKBOX_MARGIN_LEFT
            if x < strip_w:
                self._drag_start_pos = pos_int
                if chk_start <= x <= chk_start + chk_size:
                    # 点在勾选框上：等待判断是勾选还是拖拽
                    self._interaction_mode = "checkbox_wait"
                else:
                    # 点在色条空白处：进入滑动勾选模式
                    self._interaction_mode = "swipe_select"
                    self._swipe_anchor_row = self.row(item)
                    self._initial_check_states = {
                        i: self.item(i).data(Qt.UserRole).get("checked", False) for i in range(self.count())
                    }
                    self._swipe_target_value = None
            else:
                # 点在内容区域：标准列表行为
                self._interaction_mode = "standard"
                super().mousePressEvent(event)
        else:
            self._interaction_mode = "standard"
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动：根据交互模式执行拖拽或滑动勾选"""
        if not self._drag_start_pos and self._interaction_mode != "standard":
            return
        pos_int = event.position().toPoint()
        dist = (pos_int - self._drag_start_pos).manhattanLength() if self._drag_start_pos else 0
        if self._interaction_mode == "checkbox_wait":
            # 超过阈值且有勾选项时，启动拖拽
            if dist > 10 and self._has_checked_items():
                self.startDrag(Qt.MoveAction)
                self._interaction_mode = "none"
        elif self._interaction_mode == "swipe_select":
            if dist > 10:
                if self._swipe_target_value is None:
                    anchor_state = self._initial_check_states.get(self._swipe_anchor_row, False)
                    self._swipe_target_value = not anchor_state
                item = self.itemAt(pos_int)
                if item:
                    self._update_swipe_range(self.row(item))
        elif self._interaction_mode == "standard":
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放：完成勾选切换或结束滑动选择"""
        pos_int = event.position().toPoint()
        item = self.itemAt(pos_int)
        if self._interaction_mode == "checkbox_wait" and item:
            chk_size = UIDims.DELEGATE_CHECKBOX_SIZE
            chk_start = UIDims.DELEGATE_CHECKBOX_MARGIN_LEFT
            if chk_start <= pos_int.x() <= chk_start + chk_size:
                self._toggle_check_state(item)
        elif self._interaction_mode == "swipe_select":
            # 没有实际滑动时，单击切换勾选
            if self._swipe_target_value is None and item:
                self._toggle_check_state(item)
        # 重置交互状态
        self._interaction_mode = "none"
        self._drag_start_pos = None
        self._initial_check_states = {}
        self._swipe_target_value = None
        super().mouseReleaseEvent(event)

    # -------------------- 勾选相关 --------------------

    def _toggle_check_state(self, item):
        """切换单个项目的勾选状态"""
        data = item.data(Qt.UserRole)
        data["checked"] = not data.get("checked", False)
        item.setData(Qt.UserRole, data)
        self.viewport().update()

    def _update_swipe_range(self, current_row):
        """滑动勾选：将锚定行到当前行之间的项目设为目标勾选值"""
        if self._swipe_anchor_row == -1 or self._swipe_target_value is None:
            return
        start = min(self._swipe_anchor_row, current_row)
        end = max(self._swipe_anchor_row, current_row)
        for i in range(self.count()):
            item = self.item(i)
            should_be_checked = (
                self._swipe_target_value if start <= i <= end else self._initial_check_states.get(i, False)
            )
            data = item.data(Qt.UserRole)
            if data.get("checked") != should_be_checked:
                data["checked"] = should_be_checked
                item.setData(Qt.UserRole, data)
        self.viewport().update()

    def set_all_items_checked(self, checked: bool):
        """全选/全不选"""
        self.setUpdatesEnabled(False)
        has_changed = False
        for i in range(self.count()):
            item = self.item(i)
            data = item.data(Qt.UserRole)
            if data.get("checked", False) != checked:
                data["checked"] = checked
                item.setData(Qt.UserRole, data)
                has_changed = True
        self.setUpdatesEnabled(True)
        if has_changed:
            self.viewport().update()

    # -------------------- 分组折叠 --------------------

    def toggle_group_fold(self, item):
        """切换分组的折叠/展开状态"""
        data = item.data(Qt.UserRole)
        if data.get("type") != "group_start":
            return
        is_collapsed = not data["params"].get("collapsed", False)
        data["params"]["collapsed"] = is_collapsed
        item.setData(Qt.UserRole, data)
        link_id = data["params"]["link_id"]
        start_row = self.row(item)
        # 找到对应的 group_end
        end_row = -1
        for i in range(start_row + 1, self.count()):
            d = self.item(i).data(Qt.UserRole)
            if d.get("params", {}).get("link_id") == link_id and d.get("type") == "group_end":
                end_row = i
                break
        if end_row != -1:
            for i in range(start_row + 1, end_row):
                self.item(i).setHidden(is_collapsed)
        self.viewport().update()

    # -------------------- 拖拽（内部排序 & 外部添加） --------------------

    def startDrag(self, supportedActions):
        """发起拖拽：收集勾选项或当前选中项，创建半透明拖拽预览"""
        drag = QDrag(self)
        mime = QMimeData()
        items_to_drag = []
        if self._interaction_mode == "checkbox_wait":
            items_to_drag = [
                self.item(i) for i in range(self.count()) if self.item(i).data(Qt.UserRole).get("checked", False)
            ]
        else:
            if self.currentItem():
                items_to_drag.append(self.currentItem())
        if not items_to_drag:
            return
        self._dragged_items = items_to_drag
        mime.setText(json.dumps([it.data(Qt.UserRole) for it in items_to_drag]))
        drag.setMimeData(mime)
        # 生成半透明拖拽预览图
        if items_to_drag:
            rect = self.visualItemRect(items_to_drag[0])
            original_pixmap = self.viewport().grab(rect)
            transparent_pixmap = QPixmap(original_pixmap.size())
            transparent_pixmap.fill(Qt.transparent)
            painter = QPainter(transparent_pixmap)
            painter.setOpacity(0.65)
            painter.drawPixmap(0, 0, original_pixmap)
            painter.end()
            drag.setPixmap(transparent_pixmap)
            drag.setHotSpot(QPoint(20, transparent_pixmap.height() // 2))
        drag.exec(Qt.MoveAction)
        self.drop_indicator_row = -1
        self.viewport().update()

    def dragEnterEvent(self, event):
        """拖拽进入：接受包含文本数据的拖拽"""
        if event.mimeData().hasText():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """拖拽移动：计算并更新放置指示线位置"""
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        if item:
            rect = self.visualItemRect(item)
            self.drop_indicator_row = self.row(item) if pos.y() < rect.center().y() else self.row(item) + 1
        else:
            self.drop_indicator_row = self.count() if self.count() > 0 else 0
        self.viewport().update()
        if event.mimeData().hasText():
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        """拖拽离开：清除放置指示线"""
        self.drop_indicator_row = -1
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """拖拽放下：执行移动/添加操作，并验证结构合法性"""
        # 记录来源行号（用于历史记录描述）
        source_rows = []
        if event.source() == self and self._dragged_items:
            source_rows = sorted([self.row(it) + 1 for it in self._dragged_items])

        # 计算目标插入位置
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        insert_idx_0based = self.count()
        if item:
            rect = self.visualItemRect(item)
            insert_idx_0based = self.row(item) if pos.y() < rect.center().y() else self.row(item) + 1

        # 生成历史记录描述
        if not source_rows:
            msg = "拖拽添加新指令"
        elif len(source_rows) > 1:
            row_str = ",".join(map(str, source_rows[:4])) + ("..." if len(source_rows) > 4 else "")
            msg = f"批量移动了第 {row_str} 行的指令"
        else:
            src_row = source_rows[0]
            final_display_row = insert_idx_0based if src_row <= insert_idx_0based else insert_idx_0based + 1
            name = self._get_item_desc(self._dragged_items[0])
            msg = f"移动第 {src_row} 行的 [{name}] 到第 {final_display_row} 行"
        self.history_mgr.create_snapshot(msg)

        mime_text = event.mimeData().text()
        self.drop_indicator_row = -1
        try:
            data_list = json.loads(mime_text)
            is_valid_list = isinstance(data_list, list)
        except Exception:
            is_valid_list = False
            cmd_type = mime_text

        # 在模拟列表上执行移动操作
        target_row = insert_idx_0based
        simulated_list = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        indices_to_remove = []
        if event.source() == self and self._dragged_items:
            indices_to_remove = sorted([self.row(it) for it in self._dragged_items if self.row(it) != -1], reverse=True)
            for idx in indices_to_remove:
                if idx < len(simulated_list):
                    simulated_list.pop(idx)
            target_row = max(0, target_row - sum(1 for x in indices_to_remove if x < target_row))

        # 构建待插入的数据
        if not is_valid_list:
            cmd_type = mime_text
            if cmd_type == "loop_start":
                items_to_insert = self._create_paired_data("loop")
            elif cmd_type == "group_start":
                items_to_insert = self._create_paired_data("group")
            elif cmd_type == "if_start":
                items_to_insert = self._create_paired_data("if")
            else:
                items_to_insert = [self._create_single_data(cmd_type)]
        else:
            items_to_insert = data_list

        for i, new_data in enumerate(items_to_insert):
            simulated_list.insert(target_row + i, new_data)

        # 验证结构合法性
        valid, msg_err = self._validate_and_fix_structure(simulated_list)
        if not valid:
            QMessageBox.warning(self, "非法操作", msg_err)
            event.ignore()
            self.viewport().update()
            return

        event.accept()
        self.refresh_with_data(simulated_list)
        self._dragged_items = []

    # -------------------- 数据创建辅助 --------------------

    def _create_single_data(self, cmd_type):
        """根据指令类型创建单条数据字典"""
        config = global_config.get_config().get(cmd_type)
        if not config:
            return {}
        data = {"type": cmd_type, "desc": config["label"], "params": {}, "checked": False}
        for k, v in config["params"].items():
            data["params"][k] = v[1]
        return data

    def _create_paired_data(self, mode):
        """创建成对的 start/end 数据字典列表"""
        link_id = str(uuid.uuid4())[:8]
        start = self._create_single_data(f"{mode}_start")
        start["params"]["link_id"] = link_id
        end = self._create_single_data(f"{mode}_end")
        end["params"]["link_id"] = link_id
        return [start, end]

    # -------------------- 结构验证 --------------------

    def _validate_and_fix_structure(self, data_list):
        """验证指令列表的结构合法性（嵌套是否正确、分组是否闭合等）"""
        stack = []
        in_group = False
        for item in data_list:
            t = item.get("type", "")
            params = item.get("params", {})
            link_id = params.get("link_id", "")
            if t == "group_start":
                if in_group:
                    return False, "分组模块不可嵌套！"
                if stack:
                    return False, "分组模块只能放在最外层！"
                in_group = True
            elif t == "group_end":
                if not in_group:
                    return False, "存在孤立的分组结束标记！"
                if stack:
                    return False, "分组内的模块未闭合 (存在交叉嵌套)！"
                in_group = False
            elif "start" in t and link_id:
                stack.append((t, link_id))
            elif "end" in t and link_id:
                if not stack:
                    return False, f"存在孤立的结束标记 ({t})！"
                parent_type, parent_id = stack[-1]
                if parent_id != link_id:
                    return False, "结构错误：存在交叉嵌套！"
                if parent_type != t.replace("_end", "_start"):
                    return False, f"结构错误：{t} 试图闭合 {parent_type}！"
                stack.pop()
            elif t == "else_branch":
                if not stack:
                    return False, "孤立的【否则(Else)】：必须放在【判断(If)】内部！"
                parent_type, parent_id = stack[-1]
                if parent_type != "if_start":
                    return False, "位置错误：【否则(Else)】只能直接位于【判断(If)】层级下！"
                if link_id != parent_id:
                    params["link_id"] = parent_id  # 自动修正 link_id
        if stack:
            return False, "结构不完整：存在未闭合的开始标记！"
        if in_group:
            return False, "结构不完整：分组未闭合！"
        return True, "OK"

    # -------------------- 移动指令 --------------------

    def move_current_item(self, direction):
        """上移(-1)或下移(+1)当前选中的指令"""
        current_row = self.currentRow()
        if (
            current_row == -1
            or (direction == -1 and current_row == 0)
            or (direction == 1 and current_row == self.count() - 1)
        ):
            return
        target_row = current_row + direction
        name = self._get_item_desc(self.item(current_row))
        self.history_mgr.create_snapshot(f"{'上移' if direction == -1 else '下移'}了第 {current_row + 1} 行的 [{name}]")
        self.insertItem(target_row, self.takeItem(current_row))
        self.setCurrentRow(target_row)
        self.refresh_ui()
        self._validate_and_fix_structure(self.get_all_data())

    # -------------------- 键盘快捷键 --------------------

    def keyPressEvent(self, event):
        """处理键盘事件：全选、剪切、复制、粘贴、撤销、重做、删除、上下移动等"""
        mods = event.modifiers()
        key = event.key()

        if event.matches(QKeySequence.SelectAll):
            self.set_all_items_checked(True)
            event.accept()
            return
        elif event.matches(QKeySequence.Cut):
            has_checked = any(self.item(i).data(Qt.UserRole).get("checked", False) for i in range(self.count()))
            has_selected = bool(self.selectedItems())
            if has_checked or has_selected:
                self.copy_selection()
                self.delete_selection()
            event.accept()
            return
        elif event.matches(QKeySequence.Undo):
            self.history_mgr.undo()
            return
        elif (
            event.matches(QKeySequence.Redo)
            or (mods == (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_Z)
            or (mods == Qt.ControlModifier and key == Qt.Key_Y)
        ):
            self.history_mgr.redo()
            return
        elif event.matches(QKeySequence.Copy):
            self.copy_selection()
            return
        elif event.matches(QKeySequence.Paste):
            self.paste_selection()
            return
        elif key in [Qt.Key_Delete, Qt.Key_Backspace]:
            self.delete_selection()
            return

        # 自定义快捷键（上移/下移）
        try:
            key_str = QKeySequence(QKeyCombination(mods, Qt.Key(key))).toString().lower()
        except:
            key_str = QKeySequence(key | int(mods)).toString().lower()
        shortcuts = global_config.get_shortcuts()
        if key_str == shortcuts.get("move_up", "w").lower():
            self.move_current_item(-1)
            event.accept()
        elif key_str == shortcuts.get("move_down", "s").lower():
            self.move_current_item(1)
            event.accept()
        else:
            super().keyPressEvent(event)

    # -------------------- 删除/复制/粘贴 --------------------

    def delete_selection(self):
        """删除勾选项或当前选中项"""
        current_scroll = self.verticalScrollBar().value()
        self.setUpdatesEnabled(False)
        # 优先删除勾选项，否则删除列表选中项
        items_to_delete = [self.item(i) for i in range(self.count()) if self.item(i).data(Qt.UserRole).get("checked")]
        if not items_to_delete:
            items_to_delete = self.selectedItems()
        if not items_to_delete:
            self.setUpdatesEnabled(True)
            return
        rows = sorted([self.row(it) + 1 for it in items_to_delete])
        if len(rows) == 1:
            self.history_mgr.create_snapshot(f"删除第 {rows[0]} 行的 [{self._get_item_desc(items_to_delete[0])}]")
        else:
            row_str = ",".join(map(str, rows[:4])) + ("..." if len(rows) > 4 else "")
            self.history_mgr.create_snapshot(f"批量删除 {len(rows)} 个指令 (行: {row_str})")
        for row in sorted([self.row(it) for it in items_to_delete], reverse=True):
            self.takeItem(row)
        self.refresh_ui()
        self.property_panel.clear_panel()
        self.verticalScrollBar().setValue(current_scroll)
        self.setUpdatesEnabled(True)

    def copy_selection(self):
        """将勾选项或选中项的数据复制到剪贴板（JSON格式）"""
        items = [self.item(i) for i in range(self.count()) if self.item(i).data(Qt.UserRole).get("checked")]
        if not items:
            items = self.selectedItems()
        if items:
            QApplication.clipboard().setText(json.dumps([it.data(Qt.UserRole) for it in items]))

    def paste_selection(self):
        """从剪贴板粘贴指令数据，并验证结构合法性"""
        curr_idx = self.currentRow() if self.currentRow() != -1 else self.count()
        target_row = curr_idx + 1
        try:
            data_list = json.loads(QApplication.clipboard().text())
            if not isinstance(data_list, list):
                return
            self.history_mgr.create_snapshot(f"在第 {target_row} 行粘贴 {len(data_list)} 个指令")
        except:
            return
        # 为粘贴的成对结构生成新的 link_id，避免与已有项冲突
        id_map = {}
        for data in data_list:
            if "link_id" in data.get("params", {}):
                old = data["params"]["link_id"]
                if old not in id_map:
                    id_map[old] = str(uuid.uuid4())[:8]
                data["params"]["link_id"] = id_map[old]
            data["checked"] = False
        simulated_list = [self.item(i).data(Qt.UserRole) for i in range(self.count())]
        for i, new_data in enumerate(data_list):
            simulated_list.insert(target_row + i if self.currentRow() != -1 else self.count() + i, new_data)
        valid, msg = self._validate_and_fix_structure(simulated_list)
        if not valid:
            QMessageBox.warning(self, "无法粘贴", f"粘贴后会导致结构错误：\n{msg}")
            return
        self.refresh_with_data(simulated_list)

    # -------------------- 点击事件 --------------------

    def on_item_clicked(self, item):
        """点击列表项时，将其数据加载到右侧属性面板"""
        if item:
            self.property_panel.load_properties(item, item.data(Qt.UserRole))


# ============================================================
#  属性编辑器：右侧面板，编辑选中指令的参数
# ============================================================
class PropertyEditor(QWidget):
    """属性编辑面板：显示并编辑当前选中指令的所有参数"""

    data_changed = Signal()  # 参数修改后发出的信号

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.ClickFocus)
        self.current_item = None       # 当前正在编辑的列表项
        self.current_data = None       # 当前项的数据字典
        self.task_root_path = None     # 任务根目录（截图保存用）

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.form_widget = QWidget()
        self.layout = QFormLayout(self.form_widget)
        self.layout.setVerticalSpacing(5)
        self.scroll_area.setWidget(self.form_widget)
        main_layout.addWidget(self.scroll_area)

        self.active_widgets = {}       # 参数名 → 控件 的映射
        self.history_callback = None   # 历史记录创建回调
        self.undo_callback = None
        self.redo_callback = None

        # 在属性面板内也支持撤销/重做快捷键
        self.shortcut_undo = QShortcut(QKeySequence.Undo, self, context=Qt.WidgetWithChildrenShortcut)
        self.shortcut_undo.activated.connect(self._trigger_undo)
        self.shortcut_redo = QShortcut(QKeySequence.Redo, self, context=Qt.WidgetWithChildrenShortcut)
        self.shortcut_redo.activated.connect(self._trigger_redo)
        self.shortcut_redo_y = QShortcut(QKeySequence("Ctrl+Y"), self, context=Qt.WidgetWithChildrenShortcut)
        self.shortcut_redo_y.activated.connect(self._trigger_redo)

    # -------------------- 回调设置 --------------------

    def set_history_callback(self, callback):
        self.history_callback = callback

    def set_undo_redo_callbacks(self, undo_cb, redo_cb):
        self.undo_callback = undo_cb
        self.redo_callback = redo_cb

    def _trigger_undo(self):
        if self.undo_callback:
            self.undo_callback()

    def _trigger_redo(self):
        if self.redo_callback:
            self.redo_callback()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    # -------------------- 面板内容管理 --------------------

    def clear_panel(self):
        """清空面板中所有控件"""
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.active_widgets = {}

    def load_preview(self, cmd_type):
        """预览模式：展示指令的默认参数（只读，不关联具体项）"""
        self.clear_panel()
        self.current_item = None
        self.current_data = None
        self.task_root_path = None
        full_config = global_config.get_config()
        config = full_config.get(cmd_type)
        if config:
            self._render_widgets(
                {"type": cmd_type, "desc": config["label"], "params": {k: v[1] for k, v in config["params"].items()}},
                preview_mode=True,
            )

    def load_properties(self, item, task_data, task_root_path=None):
        """加载指定项的属性到面板（可编辑）"""
        self.clear_panel()
        self.current_item = item
        self.current_data = task_data
        self.task_root_path = task_root_path
        self._render_widgets(task_data, preview_mode=False)

    # -------------------- 控件渲染 --------------------

    def _render_widgets(self, data_dict, preview_mode=False):
        """根据指令数据和配置，动态生成所有参数编辑控件"""
        config = global_config.get_config().get(data_dict["type"])
        if not config:
            return
        cmd_type = data_dict.get("type", "")
        original_name = DISPLAY_NAME_OVERRIDE.get(cmd_type, config["label"])

        # 指令类型（只读）
        type_display = QLabel(original_name)
        self.layout.addRow("指令类型:", type_display)

        # 备注说明
        desc_edit = QLineEdit(data_dict.get("desc", ""))
        if not preview_mode:
            desc_edit.editingFinished.connect(lambda: self.update_desc(desc_edit.text()))
        else:
            desc_edit.setEnabled(False)
        self.layout.addRow("备注说明:", desc_edit)
        self.active_widgets["_desc_input"] = desc_edit

        keys = config["params"].keys()

        # 遍历每个参数，生成对应控件
        for key, (data_type, default_val) in config["params"].items():
            # 跳过内部参数
            if key in ["link_id", "collapsed", "env_w", "env_h"]:
                continue
            val = data_dict["params"].get(key, default_val)
            label_text = PARAM_TRANSLATIONS.get(key, f"{key}:")

            # --- 鼠标按键下拉框 ---
            if key == "button":
                widget = QComboBox()
                widget.addItems(["left", "right", "middle"])
                current_btn = str(val).lower()
                if current_btn not in ["left", "right", "middle"]:
                    current_btn = "left"
                widget.setCurrentText(current_btn)
                if not preview_mode:
                    widget.currentTextChanged.connect(lambda v, k=key: self.update_param_from_widget(k))
                else:
                    widget.setEnabled(False)
                self.active_widgets[key] = widget
                self.layout.addRow(label_text, widget)
                continue

            # --- 区域选择控件 ---
            if key == "region":
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(5)
                display_str = (
                    f"X:{val[0]} Y:{val[1]} {val[2]}x{val[3]}"
                    if isinstance(val, list) and len(val) == 4 and (val[2] > 0 or val[3] > 0)
                    else "全屏 (自动)"
                )
                line_display = QLineEdit(display_str)
                line_display.setReadOnly(True)
                line_display.setStyleSheet(UIStyles.READONLY_INPUT)
                btn_select = QPushButton("框选")
                btn_select.setCursor(Qt.PointingHandCursor)
                btn_select.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
                btn_reset = QPushButton("重置")
                btn_reset.setCursor(Qt.PointingHandCursor)
                btn_reset.setStyleSheet(UIStyles.BTN_ACTION_RED)
                if not preview_mode:
                    btn_select.clicked.connect(self.open_region_selector)
                    btn_reset.clicked.connect(self.reset_region_to_fullscreen)
                else:
                    btn_select.setEnabled(False)
                    btn_reset.setEnabled(False)
                h_layout.addWidget(line_display)
                h_layout.addWidget(btn_select)
                h_layout.addWidget(btn_reset)
                self.layout.addRow(label_text, container)
                continue

            # --- 通用控件（由工厂创建） ---
            finish_cb = None if preview_mode else lambda v=None, k=key: self.update_param_from_widget(k)
            widget = WidgetFactory.create_input_widget(data_type, val, finish_callback=finish_cb)
            if widget:
                self.active_widgets[key] = widget

                # 按键录制控件：附带录制按钮
                if key == "key_code":
                    container = QWidget()
                    h_layout = QHBoxLayout(container)
                    h_layout.setContentsMargins(0, 0, 0, 0)
                    h_layout.setSpacing(5)
                    if isinstance(widget, QLineEdit):
                        widget.setPlaceholderText("例如: ctrl+c")
                    btn_record = QPushButton("录制")
                    btn_record.setCursor(Qt.PointingHandCursor)
                    btn_record.setStyleSheet(UIStyles.BTN_ACTION_GREEN)
                    btn_record.clicked.connect(lambda _, w=widget: self.open_key_recorder(w))
                    if preview_mode:
                        btn_record.setEnabled(False)
                    h_layout.addWidget(widget)
                    h_layout.addWidget(btn_record)
                    self.layout.addRow(label_text, container)
                else:
                    if isinstance(widget, QLineEdit) and "image" in key:
                        widget.setPlaceholderText("请输入文件名")
                    if preview_mode:
                        widget.setEnabled(False)
                    self.layout.addRow(label_text, widget)

            # --- 辅助按钮（仅编辑模式） ---
            if not preview_mode:
                if key == "image_path" and self.task_root_path:
                    btn_shot = QPushButton("快捷截图")
                    btn_shot.setStyleSheet(UIStyles.BTN_ACTION_ORANGE)
                    btn_shot.clicked.connect(self.open_screenshot_tool)
                    self.layout.addRow(btn_shot)
                elif key == "y" and "x" in keys:
                    btn_pick = QPushButton("快捷填入坐标")
                    btn_pick.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
                    btn_pick.clicked.connect(lambda: self.open_locator("x", "y"))
                    self.layout.addRow(btn_pick)
                elif key == "y1" and "x1" in keys:
                    btn_pick_start = QPushButton("快捷填入起点")
                    btn_pick_start.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
                    btn_pick_start.clicked.connect(lambda: self.open_locator("x1", "y1"))
                    self.layout.addRow(btn_pick_start)
                elif key == "y2" and "x2" in keys:
                    btn_pick_end = QPushButton("快捷填入终点")
                    btn_pick_end.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
                    btn_pick_end.clicked.connect(lambda: self.open_locator("x2", "y2"))
                    self.layout.addRow(btn_pick_end)
                elif key == "off_y" and "off_x" in keys:
                    has_drag = "drag_dx" in keys and "drag_dy" in keys
                    btn_offset = QPushButton("快捷填入偏移 (修正起点)" if has_drag else "快捷填入偏移")
                    btn_offset.setStyleSheet(UIStyles.BTN_ACTION_PURPLE)
                    btn_offset.clicked.connect(lambda: self.open_ruler("off_x", "off_y"))
                    self.layout.addRow(btn_offset)
                elif key == "drag_dy" and "drag_dx" in keys:
                    btn_drag = QPushButton("快捷填入拖动距离 (动作路径)")
                    btn_drag.setStyleSheet(UIStyles.BTN_ACTION_DEEP_PURPLE)
                    btn_drag.clicked.connect(lambda: self.open_ruler("drag_dx", "drag_dy"))
                    self.layout.addRow(btn_drag)

    # -------------------- 按键录制 --------------------

    def open_key_recorder(self, target_line_edit):
        """打开按键录制窗口"""
        self.recorder = KeyRecorder()
        self.recorder.key_recorded.connect(lambda k: self._on_key_recorded(target_line_edit, k))
        self.recorder.show()

    def _on_key_recorded(self, line_edit, key_str):
        """按键录制完成回调"""
        line_edit.setText(key_str)
        self.update_param_from_widget("key_code")

    # -------------------- 区域选择 --------------------

    def open_region_selector(self):
        """打开屏幕区域框选工具"""
        self.tool_window = ScreenTool(mode="rect_select")
        self.tool_window.rect_selected.connect(self.on_region_selected)
        self.tool_window.show()

    def on_region_selected(self, rect_list):
        """区域框选完成回调"""
        if self.history_callback:
            self.history_callback(f"修改第 {self._get_current_row_idx()} 行: 设置识别区域 {rect_list}")
        self.current_data["params"]["region"] = rect_list
        self.current_item.setData(Qt.UserRole, self.current_data)
        self.data_changed.emit()
        self.load_properties(self.current_item, self.current_data, self.task_root_path)

    def reset_region_to_fullscreen(self):
        """重置识别区域为全屏"""
        if self.history_callback:
            self.history_callback(f"修改第 {self._get_current_row_idx()} 行: 重置识别区域为全屏")
        self.current_data["params"]["region"] = [0, 0, 0, 0]
        self.current_item.setData(Qt.UserRole, self.current_data)
        self.data_changed.emit()
        self.load_properties(self.current_item, self.current_data, self.task_root_path)

    # -------------------- 截图工具 --------------------

    def open_screenshot_tool(self):
        """打开屏幕截图工具"""
        self.tool_window = ScreenTool(mode="screenshot")
        self.tool_window.screenshot_created.connect(self.on_screenshot_captured)
        self.tool_window.show()

    def on_screenshot_captured(self, pixmap):
        """截图完成回调：保存图片并更新参数"""
        if not self.task_root_path:
            QMessageBox.warning(self, "错误", "无法确定任务路径，请先保存任务")
            return
        filename = f"target_{int(time.time())}.png"
        full_path = os.path.join(self.task_root_path, filename)
        try:
            pixmap.save(full_path, "PNG")
            # 记录截图时的屏幕分辨率
            screen_geo = QApplication.primaryScreen().geometry()
            env_w = screen_geo.width()
            env_h = screen_geo.height()
            self.current_data["params"]["env_w"] = env_w
            self.current_data["params"]["env_h"] = env_h
            if self.current_item:
                self.current_item.setData(Qt.UserRole, self.current_data)
            if "image_path" in self.active_widgets:
                self.active_widgets["image_path"].setText(filename)
                self.update_param_from_widget("image_path")
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    # -------------------- 定位/测距工具 --------------------

    def open_locator(self, key_x="x", key_y="y"):
        """打开定位工具"""
        self.tool_window = ScreenTool(mode="picker")
        self.tool_window.finished.connect(lambda x, y, dx, dy: self.on_picked(x, y, dx, dy, key_x, key_y))
        self.tool_window.show()

    def open_ruler(self, key_x="off_x", key_y="off_y"):
        """打开测距工具（测量偏移/拖动距离）"""
        self.tool_window = ScreenTool(mode="ruler")
        self.tool_window.finished.connect(lambda x, y, dx, dy: self.on_measured(x, y, dx, dy, key_x, key_y))
        self.tool_window.show()

    def on_picked(self, x, y, dx, dy, key_x="x", key_y="y"):
        """定位完成回调"""
        if key_x in self.active_widgets:
            self.active_widgets[key_x].setValue(x)
            self.update_param_from_widget(key_x)
        if key_y in self.active_widgets:
            self.active_widgets[key_y].setValue(y)
            self.update_param_from_widget(key_y)

    def on_measured(self, x, y, dx, dy, key_x="off_x", key_y="off_y"):
        """测距完成回调"""
        if key_x in self.active_widgets:
            self.active_widgets[key_x].setValue(dx)
            self.update_param_from_widget(key_x)
        if key_y in self.active_widgets:
            self.active_widgets[key_y].setValue(dy)
            self.update_param_from_widget(key_y)

    # -------------------- 参数更新 --------------------

    def _get_current_row_idx(self):
        """获取当前编辑项的行号（1-based），用于历史记录描述"""
        return (
            self.current_item.listWidget().row(self.current_item) + 1
            if self.current_item and self.current_item.listWidget()
            else "未知"
        )

    def update_desc(self, text):
        """更新指令的备注说明"""
        if self.current_data:
            if self.current_data.get("desc", "") == text:
                if "_desc_input" in self.active_widgets:
                    self.active_widgets["_desc_input"].clearFocus()
                return
            if self.history_callback:
                self.history_callback(f"修改第 {self._get_current_row_idx()} 行指令的备注")
            self.current_data["desc"] = text
            # 分组/分割线备注同步更新 label
            if self.current_data["type"] in ["group_start", "separator"]:
                self.current_data["params"]["label"] = text
            self.current_item.setData(Qt.UserRole, self.current_data)
            if self.current_item.listWidget():
                self.current_item.listWidget().refresh_line_numbers()
            self.data_changed.emit()
            if "_desc_input" in self.active_widgets:
                self.active_widgets["_desc_input"].clearFocus()

    def update_param_from_widget(self, key):
        """从控件中读取新值并更新到数据字典"""
        if not self.current_data or key not in self.active_widgets:
            return
        widget = self.active_widgets[key]
        new_val = None
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            new_val = widget.value()
        elif isinstance(widget, QLineEdit):
            new_val = widget.text()
        elif isinstance(widget, QCheckBox):
            new_val = widget.isChecked()
        elif isinstance(widget, QComboBox):
            new_val = widget.currentText()
        if new_val is not None and self.current_data["params"].get(key) != new_val:
            if self.history_callback:
                self.history_callback(
                    f"修改第 {self._get_current_row_idx()} 行: {PARAM_TRANSLATIONS.get(key, key)} -> {new_val}"
                )
            self.current_data["params"][key] = new_val
            self.current_item.setData(Qt.UserRole, self.current_data)
            if self.current_item.listWidget():
                self.current_item.listWidget().viewport().update()
            self.data_changed.emit()
            widget.clearFocus()

    # -------------------- 辅助按钮生成 --------------------

    def add_helper_buttons(self, params_config):
        """根据参数配置添加辅助操作按钮"""
        keys = params_config.keys()
        if "image_path" in keys and self.task_root_path:
            btn_shot = QPushButton("快捷截图")
            btn_shot.setStyleSheet(UIStyles.BTN_ACTION_ORANGE)
            btn_shot.clicked.connect(self.open_screenshot_tool)
            self.layout.addRow(btn_shot)
        has_xy, has_start, has_end = (
            ("x" in keys and "y" in keys),
            ("x1" in keys and "y1" in keys),
            ("x2" in keys and "y2" in keys),
        )
        if has_xy or has_start or has_end:
            btn_pick = QPushButton("快捷填入坐标")
            btn_pick.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
            if has_xy:
                btn_pick.clicked.connect(lambda: self.open_locator("x", "y"))
            elif has_start:
                btn_pick.clicked.connect(lambda: self.open_locator("x1", "y1"))
            if has_start and has_end:
                btn_pick_start = QPushButton("快捷填入起点")
                btn_pick_start.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
                btn_pick_start.clicked.connect(lambda: self.open_locator("x1", "y1"))
                self.layout.addRow(btn_pick_start)
                btn_pick_end = QPushButton("快捷填入终点")
                btn_pick_end.setStyleSheet(UIStyles.BTN_ACTION_BLUE)
                btn_pick_end.clicked.connect(lambda: self.open_locator("x2", "y2"))
                self.layout.addRow(btn_pick_end)
            elif not (has_start and has_end):
                self.layout.addRow(btn_pick)
        has_offset = "off_x" in keys and "off_y" in keys
        has_drag = "drag_dx" in keys and "drag_dy" in keys
        if has_offset:
            btn_offset = QPushButton("快捷填入偏移 (修正起点)" if has_drag else "快捷填入偏移")
            btn_offset.setStyleSheet(UIStyles.BTN_ACTION_PURPLE)
            btn_offset.clicked.connect(lambda: self.open_ruler("off_x", "off_y"))
            self.layout.addRow(btn_offset)
        if has_drag:
            btn_drag = QPushButton("快捷填入拖动距离 (动作路径)")
            btn_drag.setStyleSheet(UIStyles.BTN_ACTION_DEEP_PURPLE)
            btn_drag.clicked.connect(lambda: self.open_ruler("drag_dx", "drag_dy"))
            self.layout.addRow(btn_drag)


# ============================================================
#  任务说明/备注 编辑器
# ============================================================
class TaskReadmeWidget(QWidget):
    """任务详情/使用说明/备注 的纯文本编辑区"""

    text_changed = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(QLabel("任务详情/使用说明/备注"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setStyleSheet(UIStyles.README_EDITOR)
        self.text_edit.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self.text_edit)

    def set_content(self, text):
        """设置内容（不触发 textChanged 信号）"""
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.text_edit.blockSignals(False)

    def get_content(self):
        return self.text_edit.toPlainText()


# ============================================================
#  批量编辑器：同时修改多个同类指令的参数
# ============================================================
class BatchEditWidget(QWidget):
    """批量编辑面板：勾选多个同类指令后，统一修改它们的参数"""

    data_changed = Signal()

    def __init__(self, timeline):
        super().__init__()
        self.timeline = timeline
        self.current_cmd_type = None
        self.target_items = []

        self.layout = QVBoxLayout(self)

        # 提示信息标签
        self.lbl_info = QLabel("请在左侧勾选多个同类指令")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setAlignment(Qt.AlignCenter)
        self.lbl_info.setStyleSheet(UIStyles.LBL_INFO_GRAY)
        self.layout.addWidget(self.lbl_info)

        # 参数表单区域（可滚动）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        self.scroll.setWidget(self.form_widget)
        self.layout.addWidget(self.scroll)

        # 确认按钮
        self.btn_apply = QPushButton("确认同步修改选中的指令")
        self.btn_apply.clicked.connect(self.apply_changes)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet(UIStyles.BTN_PRIMARY)
        self.layout.addWidget(self.btn_apply)

        self.active_widgets = {}      # 参数名 → 输入控件
        self.active_checkboxes = {}   # 参数名 → 是否启用勾选框

    def refresh_selection(self):
        """根据勾选的项目刷新批量编辑面板"""
        self.target_items = [
            self.timeline.item(i)
            for i in range(self.timeline.count())
            if self.timeline.item(i).data(Qt.UserRole).get("checked", False)
        ]
        # 无勾选项
        if not self.target_items:
            self.lbl_info.setText("当前未勾选任何指令。\n\n请在左侧点击【复选框】选择多个同类指令。")
            self.lbl_info.setStyleSheet(UIStyles.LBL_INFO_GRAY)
            self.clear_form()
            return
        # 检查是否全部为同一类型
        first_type = self.target_items[0].data(Qt.UserRole).get("type")
        if any(item.data(Qt.UserRole).get("type") != first_type for item in self.target_items):
            self.lbl_info.setText("选中了不同类型的指令，无法批量编辑。\n\n请只勾选同一种类型的指令。")
            self.lbl_info.setStyleSheet(UIStyles.LBL_INFO_ERROR)
            self.clear_form()
            return
        config = global_config.get_config().get(first_type)
        if not config:
            self.lbl_info.setText(f"未知指令类型: {first_type}")
            self.clear_form()
            return
        self.lbl_info.setText(
            f"已选中 {len(self.target_items)} 个【{config['label']}】\n修改下方参数后点击确认，将覆盖所有选中项。"
        )
        self.lbl_info.setStyleSheet(UIStyles.LBL_INFO_SUCCESS)
        self.current_cmd_type = first_type
        self.load_form(first_type)
        self.btn_apply.setEnabled(True)

    def clear_form(self):
        """清空批量编辑表单"""
        self.current_cmd_type = None
        self.btn_apply.setEnabled(False)
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.active_widgets = {}
        self.active_checkboxes = {}

    def load_form(self, cmd_type):
        """根据指令类型生成批量编辑表单（每个参数前有勾选框控制是否修改）"""
        self.clear_form()
        self.btn_apply.setEnabled(True)
        self.current_cmd_type = cmd_type
        config = global_config.get_config().get(cmd_type)

        # 备注说明
        chk_desc = QCheckBox("备注说明")
        chk_desc.setChecked(True)
        desc_widget = QLineEdit(config["label"])
        self.form_layout.addRow(chk_desc, desc_widget)
        self.active_checkboxes["desc"] = chk_desc
        self.active_widgets["desc"] = desc_widget

        # 各参数
        for key, (data_type, default_val) in config["params"].items():
            if key in ["link_id", "collapsed", "env_w", "env_h"]:
                continue
            chk_param = QCheckBox(PARAM_TRANSLATIONS.get(key, f"{key}:"))
            chk_param.setChecked(True)
            widget = WidgetFactory.create_input_widget(data_type, default_val)
            if widget:
                self.form_layout.addRow(chk_param, widget)
                self.active_widgets[key] = widget
                self.active_checkboxes[key] = chk_param

    def apply_changes(self):
        """将表单中启用的参数值批量写入所有目标项"""
        if not self.target_items:
            return
        # 记录历史
        rows = sorted([self.timeline.row(it) + 1 for it in self.target_items])
        row_str = ",".join(map(str, rows[:4])) + ("..." if len(rows) > 4 else "")
        self.timeline.history_mgr.create_snapshot(f"批量修改了第 {row_str} 行的指令")

        # 收集启用的新值
        new_params = {}
        new_desc = self.active_widgets["desc"].text() if self.active_checkboxes["desc"].isChecked() else None
        for key, widget in self.active_widgets.items():
            if key == "desc" or not self.active_checkboxes[key].isChecked():
                continue
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                new_params[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                new_params[key] = widget.text()
            elif isinstance(widget, QCheckBox):
                new_params[key] = widget.isChecked()

        # 写入每个目标项
        for item in self.target_items:
            data = item.data(Qt.UserRole)
            if new_desc is not None:
                data["desc"] = new_desc
            for k, v in new_params.items():
                if k in data["params"]:
                    data["params"][k] = v
            item.setData(Qt.UserRole, data)

        self.timeline.refresh_line_numbers()
        self.data_changed.emit()
        QMessageBox.information(self, "完成", f"已成功更新 {len(self.target_items)} 个指令的属性。")

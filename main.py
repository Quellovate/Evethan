# main.py
# 主程序入口：包含全局快捷键、任务编辑器、任务执行器、任务管理器及主窗口

import sys
import os
import json
import time
import uuid
import threading
import ctypes
import platform

try:
    import keyboard
except ImportError:
    print("未安装 keyboard 库，全局快捷键功能不可用，请运行: pip install keyboard")

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

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QGroupBox,
    QPushButton,
    QMessageBox,
    QSplitter,
    QSpinBox,
    QScrollArea,
    QTabWidget,
    QInputDialog,
    QTextEdit,
    QFrame,
    QLineEdit,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QObject, QEvent, QRect, QPoint, QUrl
from PySide6.QtGui import QCloseEvent, QFont, QKeySequence, QShortcut, QDesktopServices, QIcon, QPixmap

# ---------- 导入项目内部模块 ----------

try:
    from config import global_config, TaskManager
except ImportError:
    print("错误: 找不到 config.py")
    sys.exit(1)

try:
    from scheduler import TaskScheduler
except ImportError:
    print("错误: 找不到 scheduler.py")
    sys.exit(1)

try:
    from tools import ScreenTool
except ImportError:
    print("错误: 找不到 tools.py")
    sys.exit(1)

try:
    from ui_components import (
        TaskDelegate,
        ToolboxList,
        ScriptTimeline,
        PropertyEditor,
        TaskReadmeWidget,
        BatchEditWidget,
    )
except ImportError as e:
    print(f"错误: 无法导入 ui_components.py。\n详细错误: {e}")
    sys.exit(1)

try:
    from ui_system import FloatingOSD, DefaultSettingsWidget, SettingsWidget
except ImportError as e:
    print(f"错误: 无法导入 ui_system.py。\n详细错误: {e}")
    sys.exit(1)

from ui_styles import UIStyles, UIColors, UIDims, UIFonts


# ========================================================================
#  全局快捷键处理器：监听键盘快捷键并发射对应信号
# ========================================================================


class GlobalHotkeyHandler(QObject):
    sig_run = Signal()  # 运行任务信号
    sig_stop = Signal()  # 停止任务信号
    sig_toggle_osd = Signal()  # 切换悬浮日志显示信号

    def __init__(self):
        super().__init__()

    def start(self):
        """首次启动时加载快捷键"""
        self.reload()

    def reload(self):
        """重新加载全局快捷键配置（先清除旧绑定再重新注册）"""
        if "keyboard" not in sys.modules:
            return
        try:
            keyboard.unhook_all()
        except:
            pass

        shortcuts = global_config.get_shortcuts()
        run_key = shortcuts.get("run_task", "f8")
        stop_key = shortcuts.get("stop_task", "f9")
        osd_key = shortcuts.get("toggle_osd", "f10")

        try:
            if run_key:
                keyboard.add_hotkey(run_key, self.sig_run.emit)
            if stop_key:
                keyboard.add_hotkey(stop_key, self.sig_stop.emit)
            if osd_key:
                keyboard.add_hotkey(osd_key, self.sig_toggle_osd.emit)
            print(f"全局快捷键已加载: 运行[{run_key}], 停止[{stop_key}], 悬浮日志[{osd_key}]")
        except Exception as e:
            print(f"全局快捷键注册失败: {e}")


# ========================================================================
#  自定义事件 & 信号桥（用于线程到主线程的安全通信）
# ========================================================================


class MyFinishEvent(QEvent):
    """任务执行完成后发送给 ExecuteWidget 的自定义事件"""

    def __init__(self):
        super().__init__(QEvent.Type(QEvent.User + 1))


class SignalBridge(QObject):
    """线程安全的日志信号桥"""

    log_signal = Signal(str, str, str, bool)
    # 用于界面状态和 OSD 更新
    status_signal = Signal(str, str)


# ========================================================================
#  快捷替换图片页面：显示待替换图片及其相关信息
# ========================================================================
class QuickReplaceWindow(QDialog):
    def __init__(self, task_name, image_data_map, task_manager, parent_editor):
        super().__init__(parent_editor)
        self.task_name = task_name
        self.image_data_map = image_data_map
        self.task_manager = task_manager
        self.parent_editor = parent_editor
        self.task_path = self.task_manager.get_task_path(self.task_name)

        # 获取当前系统真实分辨率
        screen_geo = QApplication.primaryScreen().geometry()
        self.current_screen_w = screen_geo.width()
        self.current_screen_h = screen_geo.height()

        self.setWindowTitle(f"快捷替换图片 - {self.task_name}")
        self.resize(UIDims.WINDOW_REPLACE_W, UIDims.WINDOW_REPLACE_H)
        self.setWindowModality(Qt.ApplicationModal)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setStyleSheet(UIStyles.REPLACE_SCROLL_AREA)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(10)
        self.list_layout.setContentsMargins(0, 0, 8, 0)

        # 提示框
        warning_box = QFrame()
        warning_box.setStyleSheet(UIStyles.REPLACE_WARNING_BOX)
        warning_box.setMinimumHeight(UIDims.REPLACE_WARNING_MIN_H)
        warning_layout = QVBoxLayout(warning_box)
        warning_layout.setContentsMargins(10, 6, 10, 6)

        lbl_warning = QLabel(
            "注意：\n\n"
            "本功能将且仅将：自动更新所选【任务文件夹】下的【图片文件】，以及 script.json 中的【分辨率】标签 ( env_w/env_h )。\n\n"
            "若进行跨分辨率（如 1080P 到 2K ）迁移脚本，原指令中设置的【识别区域】和【 X/Y 轴偏移量】"
            "由于分辨率环境不一样可能会失效，请在替换图片后，手动检查并修正这部分参数！"
        )
        lbl_warning.setStyleSheet(UIStyles.REPLACE_WARNING_TEXT)
        lbl_warning.setWordWrap(True)
        warning_layout.addWidget(lbl_warning)
        self.list_layout.addWidget(warning_box)

        # 状态摘要
        lbl_summary = QLabel(
            f"当前系统分辨率: {self.current_screen_w} x {self.current_screen_h}  (浅红色代表分辨率不匹配，建议重新截图)"
        )
        lbl_summary.setStyleSheet(UIStyles.REPLACE_SUMMARY_TEXT)
        self.list_layout.addWidget(lbl_summary)

        # 遍历数据字典，渲染卡片
        for img_filename, info in self.image_data_map.items():
            card = self._create_image_card(img_filename, info)
            self.list_layout.addWidget(card)

        self.list_layout.addStretch()
        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area)

    def _create_image_card(self, img_filename, info):
        """创建单张图片的信息卡片"""
        card = QFrame()

        env_w = info.get("env_w", 0)
        env_h = info.get("env_h", 0)
        ref_lines = info.get("ref_lines", [])
        total_refs = info.get("total_refs", 0)

        # 根据分辨率一致与否决定卡片背景色
        is_matched = env_w == self.current_screen_w and env_h == self.current_screen_h
        card.setStyleSheet(UIStyles.REPLACE_CARD_MATCHED if is_matched else UIStyles.REPLACE_CARD_UNMATCHED)

        card.setMinimumHeight(UIDims.REPLACE_CARD_MIN_H)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)

        # 左侧：图片缩略图
        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(UIDims.REPLACE_THUMB_SIZE, UIDims.REPLACE_THUMB_SIZE)
        lbl_thumb.setStyleSheet(UIStyles.REPLACE_THUMBNAIL)
        lbl_thumb.setAlignment(Qt.AlignCenter)

        img_path = os.path.join(self.task_path, img_filename)
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            lbl_thumb.setPixmap(
                pixmap.scaled(
                    UIDims.REPLACE_THUMB_SIZE - 4,
                    UIDims.REPLACE_THUMB_SIZE - 4,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            thumb_inner = UIDims.REPLACE_THUMB_SIZE - 2
            lbl_thumb.setPixmap(pixmap.scaled(thumb_inner, thumb_inner, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            lbl_thumb.setText("图片丢失")
            lbl_thumb.setStyleSheet(UIStyles.REPLACE_THUMBNAIL_ERROR)

        card_layout.addWidget(lbl_thumb)

        # 中间：图片信息
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(24, 0, 0, 0)
        lbl_name = QLabel(f"文件名: {img_filename}")
        lbl_name.setStyleSheet(UIStyles.REPLACE_LBL_NAME)
        lbl_res = QLabel(f"原图分辨率: {env_w} x {env_h}")
        lbl_res.setStyleSheet(UIStyles.REPLACE_LBL_RES)

        display_lines = ", ".join(map(str, ref_lines[:10]))
        if len(ref_lines) > 10:
            display_lines += " 等"
        lbl_refs = QLabel(f"被 {total_refs} 个指令引用：第 {display_lines} 行")
        lbl_refs.setStyleSheet(UIStyles.REPLACE_LBL_REFS)
        lbl_refs.setWordWrap(True)

        info_layout.addWidget(lbl_name)
        info_layout.addWidget(lbl_res)
        info_layout.addWidget(lbl_refs)
        info_layout.addStretch()

        card_layout.addLayout(info_layout)
        card_layout.addStretch()

        # 右侧：快捷截图按钮
        btn_reshot = QPushButton("快捷截图")
        btn_reshot.setCursor(Qt.PointingHandCursor)
        btn_reshot.setStyleSheet(UIStyles.BTN_REPLACE_ACTION)
        btn_reshot.setFixedSize(UIDims.REPLACE_BTN_W, UIDims.REPLACE_BTN_H)
        btn_reshot.clicked.connect(lambda checked, fname=img_filename: self.start_quick_shot(fname))
        card_layout.addWidget(btn_reshot)
        return card

    def start_quick_shot(self, img_filename):
        """隐藏窗口 -> 开启截图 -> 处理结果 -> 恢复显示"""
        # 1. 静默隐藏当前弹窗，避免遮挡截图视线
        self.hide()

        # 2. 实例化并配置截图工具
        self.tool_window = ScreenTool(mode="screenshot")

        # 信号 A：成功完成框选截图
        self.tool_window.screenshot_created.connect(lambda pixmap: self._handle_capture_success(pixmap, img_filename))

        # 信号 B：工具窗口关闭
        self.tool_window.setAttribute(Qt.WA_DeleteOnClose)  # 关闭时释放内存
        self.tool_window.destroyed.connect(lambda: self.show())
        self.tool_window.show()

    def _handle_capture_success(self, pixmap, img_filename):
        """截图完成后的数据覆写工作"""
        full_path = os.path.join(self.task_path, img_filename)

        try:
            # 物理覆盖所选任务文件夹的旧图片文件
            pixmap.save(full_path, "PNG")
            print(f"文件已覆盖: {full_path}")

            # 覆写 script.json 分辨率数据
            script_data = self.task_manager.load_script(self.task_name)
            update_count = 0

            for step in script_data:
                params = step.get("params", {})
                # 检查此条指令是否引用了当前正在替换的图片
                if params.get("image_path") == img_filename:
                    params["env_w"] = self.current_screen_w
                    params["env_h"] = self.current_screen_h
                    update_count += 1

            self.task_manager.save_script(self.task_name, script_data)
            print(f"JSON 数据已同步更新，共修改 {update_count} 处指令的分辨率记录。")
            # 更新本地内存中的 image_data_map，实时刷新窗口状态，同步任务编辑器信息
            if img_filename in self.image_data_map:
                self.image_data_map[img_filename]["env_w"] = self.current_screen_w
                self.image_data_map[img_filename]["env_h"] = self.current_screen_h
            self._refresh_list_ui()
            self.parent_editor.open_task(self.task_name)

        except Exception as e:
            QMessageBox.critical(self, "替换失败", f"在处理文件时发生错误:\n{str(e)}")

    def _refresh_list_ui(self):
        """重新渲染卡片列表，刷新状态"""
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # 重新插入卡片
        for img_filename, info in self.image_data_map.items():
            card = self._create_image_card(img_filename, info)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)


# ========================================================================
#  任务编辑器页面：工具箱 + 任务编排编排 + 属性面板 + 说明 + 批量编辑
# ========================================================================


class TaskEditorWidget(QWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.current_task_name = None  # 当前打开的任务名
        self.is_dirty = False  # 是否有未保存修改
        self._init_ui()

    # ----- UI 构建 -----

    def _init_ui(self):
        layout = QVBoxLayout(self)
        UIDims.apply_page_layout(layout)

        # --- 顶部信息栏 ---
        top_bar = QHBoxLayout()
        self.lbl_info = QLabel("当前未选择任务")
        self.lbl_info.setStyleSheet(UIStyles.LBL_EDITOR_TITLE)

        # 撤销/重做状态标签
        history_widget = QWidget()
        v_layout = QVBoxLayout(history_widget)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(2)
        self.lbl_undo = QLabel("↩️ 上一步: 无")
        self.lbl_undo.setStyleSheet(UIStyles.LBL_HISTORY_INACTIVE)
        self.lbl_redo = QLabel("↪️ 下一步: 无")
        self.lbl_redo.setStyleSheet(UIStyles.LBL_HISTORY_INACTIVE)
        v_layout.addWidget(self.lbl_undo)
        v_layout.addWidget(self.lbl_redo)

        # 快捷替换已引用图片按钮
        self.btn_quick_replace = QPushButton("快捷替换已引用图片")
        self.btn_quick_replace.clicked.connect(self.open_quick_replace_window)
        self.btn_quick_replace.setEnabled(False)
        self.btn_quick_replace.setStyleSheet(UIStyles.BTN_QUICK_REPLACE)

        # 删除未引用图片按钮
        self.btn_clean_imgs = QPushButton("删除未引用图片")
        self.btn_clean_imgs.clicked.connect(self.clean_unreferenced_images)
        self.btn_clean_imgs.setEnabled(False)
        self.btn_clean_imgs.setStyleSheet(UIStyles.BTN_DELETE_DANGER)

        # 保存按钮
        self.btn_save = QPushButton("保存当前任务")
        self.btn_save.clicked.connect(self.save_current_task)
        self.btn_save.setEnabled(False)
        self.reset_save_btn_style()

        top_bar.addWidget(self.lbl_info)
        top_bar.addSpacing(30)
        top_bar.addWidget(history_widget)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_quick_replace)
        top_bar.addWidget(self.btn_clean_imgs)
        top_bar.addWidget(self.btn_save)
        layout.addLayout(top_bar)

        # --- 三栏分割器 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：工具箱
        self.toolbox = ToolboxList(enable_drag=True)
        left_box = QGroupBox("工具箱")
        left_box.setStyleSheet(UIStyles.PANEL_EDITOR)
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)
        left_layout.addWidget(self.toolbox)

        # 中间：任务编排
        self.props = PropertyEditor()
        self.timeline = ScriptTimeline(self.props)

        mid_box = QGroupBox("任务编排")
        mid_box.setStyleSheet(UIStyles.PANEL_EDITOR)
        mid_box.setMinimumWidth(320)

        # 全选/全不选按钮（浮动在右上角）
        self.btn_container = QWidget(mid_box)
        btn_layout = QHBoxLayout(self.btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        btn_select_all = QPushButton("全选")
        btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_select_all.setFixedSize(UIDims.BTN_SELECT_ALL_W, UIDims.BTN_SELECT_ALL_H)
        btn_select_all.setStyleSheet(UIStyles.BTN_SELECT_ALL)
        btn_select_all.clicked.connect(lambda: self.timeline.set_all_items_checked(True))

        btn_unselect_all = QPushButton("全不选")
        btn_unselect_all.setCursor(Qt.PointingHandCursor)
        btn_unselect_all.setFixedSize(UIDims.BTN_UNSELECT_ALL_W, UIDims.BTN_UNSELECT_ALL_H)
        btn_unselect_all.setStyleSheet(UIStyles.BTN_UNSELECT_ALL)
        btn_unselect_all.clicked.connect(lambda: self.timeline.set_all_items_checked(False))

        btn_layout.addWidget(btn_select_all)
        btn_layout.addWidget(btn_unselect_all)

        # 事件过滤器：使按钮容器始终贴在 GroupBox 右上角
        class TopRightAlignFilter(QObject):
            def __init__(self, container, parent=None):
                super().__init__(parent)
                self.container = container
                self.min_x = 150

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Resize:
                    self.container.resize(self.container.sizeHint())
                    ideal_x = obj.width() - self.container.width() - 20
                    final_x = max(self.min_x, ideal_x)
                    self.container.move(final_x, 10)
                return super().eventFilter(obj, event)

        self._mid_box_filter = TopRightAlignFilter(self.btn_container, mid_box)
        mid_box.installEventFilter(self._mid_box_filter)

        mid_layout = QVBoxLayout(mid_box)
        mid_layout.setContentsMargins(5, 5, 5, 5)
        mid_layout.setSpacing(5)
        mid_layout.addWidget(self.timeline)

        # 右侧：属性设置 / 同步调整 / 任务说明 三个子标签页
        self.readme_widget = TaskReadmeWidget()

        self.batch_edit_widget = BatchEditWidget(self.timeline)
        self.batch_edit_widget.data_changed.connect(self.mark_dirty)
        self.batch_edit_widget.data_changed.connect(self.on_batch_data_changed)

        right_box = QGroupBox("")
        custom_right_style = UIStyles.PANEL_EDITOR.replace(
            "padding: 48px 12px 12px 12px;", "padding: 0px 12px 12px 12px;"
        )
        right_box.setStyleSheet(custom_right_style)
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(5, 0, 5, 5)

        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet(UIStyles.PANEL_EDITOR_RIGHT_TABS)
        self.right_tabs.addTab(self.props, "属性设置")
        self.right_tabs.addTab(self.batch_edit_widget, "同步调整")
        self.right_tabs.addTab(self.readme_widget, "任务说明")
        self.right_tabs.currentChanged.connect(self.on_right_tab_changed)
        right_layout.addWidget(self.right_tabs)

        # --- 信号连接 ---
        self.timeline.structure_changed.connect(self.mark_dirty)
        self.props.data_changed.connect(self.mark_dirty)
        self.readme_widget.text_changed.connect(self.mark_dirty)
        self.toolbox.itemClicked.connect(self.on_toolbox_clicked)
        self.timeline.itemClicked.connect(self.on_timeline_clicked)
        self.timeline.history_changed.connect(self.update_history_labels)

        splitter.addWidget(left_box)
        splitter.addWidget(mid_box)
        splitter.addWidget(right_box)
        splitter.setSizes([260, 450, 500])
        layout.addWidget(splitter)

        # 保存快捷键
        self.shortcut_save = None
        self.reload_save_shortcut()

    # ----- 工具箱 / 任务编排点击 -----

    def on_toolbox_clicked(self, item):
        """点击工具箱条目时，在属性面板预览该指令的默认参数"""
        cmd_type = item.data(Qt.UserRole)
        if not cmd_type:
            return
        self.timeline.clearSelection()
        self.right_tabs.setCurrentIndex(0)
        self.props.load_preview(cmd_type)

    def on_timeline_clicked(self, item):
        """点击编排中的指令时，在属性面板加载其参数进行编辑"""
        self.toolbox.clearSelection()
        self.right_tabs.setCurrentIndex(0)
        task_data = item.data(Qt.UserRole)
        task_path = self.task_manager.get_task_path(self.current_task_name) if self.current_task_name else None
        self.props.load_properties(item, task_data, task_path)

    def on_right_tab_changed(self, index):
        """切换右侧标签页时，若切到批量编辑则刷新选中状态"""
        if index == 1:
            self.batch_edit_widget.refresh_selection()

    def on_batch_data_changed(self):
        """批量编辑数据变动后，同步刷新属性面板"""
        current = self.timeline.currentItem()
        if current:
            task_data = current.data(Qt.UserRole)
            task_path = self.task_manager.get_task_path(self.current_task_name) if self.current_task_name else None
            self.props.load_properties(current, task_data, task_path)

    # ----- 脏标记 / 保存状态 -----

    def mark_dirty(self):
        """标记任务为"已修改未保存"状态"""
        if not self.is_dirty:
            self.is_dirty = True
            self.btn_clean_imgs.setEnabled(False)
            self.btn_quick_replace.setEnabled(False)
            if self.current_task_name == TaskManager.DRAFT_TASK_NAME:
                self.btn_save.setText("另存为新任务")
            else:
                self.btn_save.setText("保存当前任务")
            self.btn_save.setStyleSheet(UIStyles.BTN_SAVE_DIRTY)

    def reset_save_btn_style(self):
        """重置保存按钮为"已保存"样式"""
        self.is_dirty = False
        if self.current_task_name and self.current_task_name != TaskManager.DRAFT_TASK_NAME:
            self.btn_clean_imgs.setEnabled(True)
            self.btn_quick_replace.setEnabled(True)
        else:
            self.btn_clean_imgs.setEnabled(False)
            self.btn_quick_replace.setEnabled(False)
        if self.current_task_name == TaskManager.DRAFT_TASK_NAME:
            self.btn_save.setText("另存为新任务")
        else:
            self.btn_save.setText("保存当前任务")
        self.btn_save.setStyleSheet(UIStyles.BTN_SAVE_NORMAL)

    def check_unsaved_changes(self):
        """检查是否有未保存修改，弹窗询问用户处理方式，返回 True 表示可以继续后续操作"""
        if not self.is_dirty:
            return True
        task_disp_name = "草稿任务" if self.current_task_name == TaskManager.DRAFT_TASK_NAME else self.current_task_name
        reply = QMessageBox.question(
            self,
            "未保存的修改",
            f"任务 '{task_disp_name}' 有未保存的修改。\n是否立即保存？",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self.save_current_task()
            return not self.is_dirty
        elif reply == QMessageBox.No:
            if self.current_task_name == TaskManager.DRAFT_TASK_NAME:
                self.task_manager.reset_draft_task()
                self.open_task(TaskManager.DRAFT_TASK_NAME)
            self.is_dirty = False
            return True
        else:
            return False

    # ----- 保存快捷键 -----

    def reload_save_shortcut(self):
        """根据配置重新绑定保存快捷键"""
        if self.shortcut_save:
            self.shortcut_save.setEnabled(False)
            self.shortcut_save.setParent(None)

        try:
            self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
            self.shortcut_save.setContext(Qt.WindowShortcut)
            self.shortcut_save.activated.connect(self.save_via_shortcut)
            if self.current_task_name == TaskManager.DRAFT_TASK_NAME:
                self.btn_save.setText("另存为新任务")
            else:
                self.btn_save.setText("保存当前任务")
        except:
            print("快捷键 Ctrl+S 绑定失败")

    def save_via_shortcut(self):
        """通过快捷键触发保存"""
        if self.btn_save.isEnabled():
            self.save_current_task()

    # ----- 撤销/重做历史标签更新 -----

    def _truncate_text(self, text, max_len=40):
        """截断文本，超长部分用省略号代替"""
        return text[:max_len] + "..." if len(text) > max_len else text

    def update_history_labels(self):
        """根据历史管理器状态刷新撤销/重做标签"""
        undo_text, redo_text = self.timeline.history_mgr.get_status_text()
        undo_display = self._truncate_text(undo_text, 45)
        redo_display = self._truncate_text(redo_text, 45)
        if undo_text != "无":
            self.lbl_undo.setText(f"↩️ 上一步: {undo_display}")
            self.lbl_undo.setStyleSheet(UIStyles.LBL_HISTORY_ACTIVE)
        else:
            self.lbl_undo.setText("↩️ 上一步: 无")
            self.lbl_undo.setStyleSheet(UIStyles.LBL_HISTORY_INACTIVE)
        if redo_text != "无":
            self.lbl_redo.setText(f"↪️ 下一步: {redo_display}")
            self.lbl_redo.setStyleSheet(UIStyles.LBL_HISTORY_ACTIVE)
        else:
            self.lbl_redo.setText("↪️ 下一步: 无")
            self.lbl_redo.setStyleSheet(UIStyles.LBL_HISTORY_INACTIVE)

    # ----- 打开 / 保存任务 -----

    def open_task(self, task_name):
        """打开指定任务：加载脚本数据、任务说明，重置编辑状态"""
        self.current_task_name = task_name
        if task_name == TaskManager.DRAFT_TASK_NAME:
            self.lbl_info.setText("正在编辑: [草稿任务] (未保存)")
            self.lbl_info.setStyleSheet(UIStyles.LBL_EDITOR_TITLE_DRAFT)
        else:
            self.lbl_info.setText(f"正在编辑: {task_name}")
            self.lbl_info.setStyleSheet(UIStyles.LBL_EDITOR_TITLE)
        self.btn_save.setEnabled(True)
        script_data = self.task_manager.load_script(task_name)
        self.timeline.load_from_data(script_data)
        readme_content = self.task_manager.load_task_info(task_name)
        self.readme_widget.set_content(readme_content)
        self.reset_save_btn_style()
        self.props.clear_panel()
        self.update_history_labels()

    def save_current_task(self):
        """保存当前任务。若为草稿则弹窗输入名称后另存为正式任务"""
        if not self.current_task_name:
            return
        data = self.timeline.get_all_data()
        readme_text = self.readme_widget.get_content()

        # 草稿任务需要另存为
        if self.current_task_name == TaskManager.DRAFT_TASK_NAME:
            new_name, ok = QInputDialog.getText(self, " ", "请输入新任务名称:", text="新建任务")
            if ok and new_name:
                self.task_manager.save_script(self.current_task_name, data)
                self.task_manager.save_task_info(self.current_task_name, readme_text)
                success, msg = self.task_manager.publish_draft_task(new_name)
                if success:
                    QMessageBox.information(self, "成功", f"草稿已保存为: {new_name}")
                    self.open_task(new_name)
                else:
                    QMessageBox.warning(self, "保存失败", msg)
            return

        # 正式任务直接保存
        res1 = self.task_manager.save_script(self.current_task_name, data)
        res2 = self.task_manager.save_task_info(self.current_task_name, readme_text)
        if res1 and res2:
            self.reset_save_btn_style()
            print(f"任务 {self.current_task_name} 已保存")
        else:
            QMessageBox.critical(self, "失败", "保存失败，请检查文件权限。")

    def _extract_image_references(self):
        """遍历当前脚本，提取所有引用的图片信息"""
        # 加载最新保存的脚本数据
        script_data = self.task_manager.load_script(self.current_task_name)
        image_dict = {}
        for index, step in enumerate(script_data):
            params = step.get("params", {})
            image_path = params.get("image_path")
            # 如果该指令包含 image_path 参数且不为空
            if image_path:
                line_num = index + 1
                env_w = params.get("env_w", 0)
                env_h = params.get("env_h", 0)
                # 如果是第一次遇到这张图，初始化字典
                # 如果在多处引用时 env_w/h 不一致，默认保留第一次遇到的分辨率（理论上应该是一致的）
                if image_path not in image_dict:
                    image_dict[image_path] = {"env_w": env_w, "env_h": env_h, "ref_lines": [], "total_refs": 0}
                # 追加引用信息
                image_dict[image_path]["ref_lines"].append(line_num)
                image_dict[image_path]["total_refs"] += 1
        return image_dict

    # ----- 快捷替换图片 -----
    def open_quick_replace_window(self):
        """打开快捷替换图片的独立窗口"""
        if self.is_dirty or not self.current_task_name or self.current_task_name == TaskManager.DRAFT_TASK_NAME:
            return
        image_data_map = self._extract_image_references()

        if not image_data_map:
            QMessageBox.information(self, "提示", "当前脚本中没有任何需要识图的指令，无需替换。")
            return

        self.quick_replace_window = QuickReplaceWindow(self.current_task_name, image_data_map, self.task_manager, self)
        self.quick_replace_window.show()

    # ----- 清理未引用图片 -----
    def clean_unreferenced_images(self):
        """扫描任务文件夹，找出未被脚本引用的图片并提供删除选项"""
        if self.is_dirty or not self.current_task_name or self.current_task_name == TaskManager.DRAFT_TASK_NAME:
            return

        task_dir = self.task_manager.get_task_path(self.current_task_name)
        if not os.path.exists(task_dir):
            return

        # 收集文件夹中的所有图片
        valid_extensions = (".png", ".jpg", ".jpeg", ".bmp")
        all_files = os.listdir(task_dir)
        local_images = set(f for f in all_files if f.lower().endswith(valid_extensions))

        # 收集脚本中实际引用的图片
        script_data = self.task_manager.load_script(self.current_task_name)
        referenced_images = set()
        for step in script_data:
            params = step.get("params", {})
            if "image_path" in params and params["image_path"]:
                referenced_images.add(os.path.basename(params["image_path"]))

        unreferenced_images = local_images - referenced_images
        if not unreferenced_images:
            QMessageBox.information(self, "清理未引用图片", "当前任务文件夹很干净，没有未引用的多余图片。")
            return

        reply = QMessageBox.question(
            self,
            "清理未引用图片",
            f"共检测到 {len(unreferenced_images)} 张未被引用的图片。\n\n是否确认永久删除它们？\n(此操作不可恢复)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for img in unreferenced_images:
                try:
                    os.remove(os.path.join(task_dir, img))
                    deleted_count += 1
                except Exception as e:
                    print(f"删除图片 {img} 失败: {e}")
            QMessageBox.information(self, "清理成功", f"已删除 {deleted_count} 张未引用的图片。")


# ========================================================================
#  任务执行页面：选择任务 → 配置运行参数 → 运行/停止 → 查看日志
# ========================================================================


class ExecuteWidget(QWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.scheduler = TaskScheduler()  # 任务调度引擎
        self.signal_bridge = SignalBridge()  # 线程→主线程日志信号
        self.signal_bridge.log_signal.connect(self.handle_log)
        self._last_valid_loop_count = 1
        self.current_log_file_path = None  # 当前任务日志文件路径
        self.current_task_dir = None  # 当前任务文件夹路径
        self.memory_task_name = global_config.get_app_setting("last_exec_task", None)  # 读取并记忆最后一次选中的任务名
        self._init_ui()

    # ----- UI 构建 -----

    def _init_ui(self):
        layout = QHBoxLayout(self)
        UIDims.apply_page_layout(layout)

        # --- 左侧：任务列表 ---
        left_panel = QGroupBox("选择任务")
        left_panel.setStyleSheet(UIStyles.PANEL_EXEC)
        l_layout = QVBoxLayout()
        self.list_tasks = QListWidget()
        self.list_tasks.currentItemChanged.connect(self.on_task_selected)
        self.btn_refresh = QPushButton("刷新列表")
        self.btn_refresh.clicked.connect(self.refresh_list)
        l_layout.addWidget(self.list_tasks)
        l_layout.addWidget(self.btn_refresh)
        left_panel.setLayout(l_layout)

        # --- 右侧面板 ---
        right_panel = QWidget()
        r_layout = QVBoxLayout()
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(UIDims.PAGE_SPACING)

        # 任务说明区域
        group_desc = QGroupBox("任务说明")
        group_desc.setStyleSheet(UIStyles.PANEL_EXEC)
        d_layout = QVBoxLayout()
        self.readme_display = QTextEdit()
        self.readme_display.setReadOnly(True)
        self.readme_display.setStyleSheet(UIStyles.PANEL_READONLY_DISPLAY)
        self.readme_display.setMaximumHeight(200)
        d_layout.addWidget(self.readme_display)
        group_desc.setLayout(d_layout)

        # 运行控制区域（循环次数、超时、运行/停止按钮）
        group_ctrl = QGroupBox("运行控制")
        group_ctrl.setStyleSheet(UIStyles.PANEL_EXEC)
        c_layout = QGridLayout()
        c_layout.setHorizontalSpacing(12)
        c_layout.setVerticalSpacing(12)

        lbl_loop_setting = QLabel("重复执行次数:")
        lbl_loop_setting.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_loop_setting.setStyleSheet(UIStyles.LBL_CTRL_TITLE)

        self.spin_run_times = QSpinBox()
        self.spin_run_times.setRange(1, 9999)
        self.spin_run_times.setValue(1)
        self.spin_run_times.setFixedWidth(160)
        self.spin_run_times.setToolTip("设置所选任务需要完整重复执行的轮次")
        self.spin_run_times.editingFinished.connect(self._validate_loop_count)
        self.spin_run_times.lineEdit().returnPressed.connect(self.spin_run_times.clearFocus)
        self.spin_run_times.installEventFilter(self)
        self.spin_run_times.valueChanged.connect(self.save_run_settings)

        lbl_timeout_setting = QLabel("超时重启(秒):")
        lbl_timeout_setting.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_timeout_setting.setStyleSheet(UIStyles.LBL_CTRL_TITLE)

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(0, 999999)
        self.spin_timeout.setValue(3600)
        self.spin_timeout.setFixedWidth(160)
        self.spin_timeout.setToolTip("当前轮次执行超过该时间将强制中断并从头开始")
        self.spin_timeout.lineEdit().returnPressed.connect(self.spin_timeout.clearFocus)
        self.spin_timeout.installEventFilter(self)
        self.spin_timeout.valueChanged.connect(self.save_run_settings)

        self.btn_run = QPushButton("开始运行")
        self.btn_run.setStyleSheet(UIStyles.BTN_RUN)
        self.btn_run.setFixedWidth(280)
        self.btn_run.clicked.connect(self.run_task)

        self.lbl_run_hint = QLabel()
        self.lbl_run_hint.setStyleSheet(UIStyles.LBL_CTRL_TITLE)

        self.btn_stop = QPushButton("停止运行")
        self.btn_stop.setStyleSheet(UIStyles.BTN_STOP)
        self.btn_stop.setFixedWidth(280)
        self.btn_stop.clicked.connect(self.stop_task)
        self.btn_stop.setEnabled(False)

        self.lbl_stop_hint = QLabel()
        self.lbl_stop_hint.setStyleSheet(UIStyles.LBL_CTRL_TITLE)

        c_layout.addWidget(lbl_loop_setting, 0, 0)
        c_layout.addWidget(self.spin_run_times, 0, 1)
        c_layout.addWidget(self.btn_run, 0, 2)
        c_layout.addWidget(self.lbl_run_hint, 0, 3)
        c_layout.addWidget(lbl_timeout_setting, 1, 0)
        c_layout.addWidget(self.spin_timeout, 1, 1)
        c_layout.addWidget(self.btn_stop, 1, 2)
        c_layout.addWidget(self.lbl_stop_hint, 1, 3)
        c_layout.setColumnStretch(4, 1)

        self.lbl_video_hint = QLabel(
            '请参考 <a href="https://www.bilibili.com/video/BV1nAX8B7Eyt/?t=116" style="color: #3B82F6; text-decoration: none;">'
            "教程</a> 中关于上方设置的说明"
        )
        self.lbl_video_hint.setOpenExternalLinks(True)
        self.lbl_video_hint.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_video_hint.setStyleSheet(f"font-size: 20px; color: {UIStyles.S.TEXT_SECONDARY};")
        c_layout.addWidget(self.lbl_video_hint, 2, 0, 1, 4)
        group_ctrl.setLayout(c_layout)

        # 日志区域（摘要栏 + 详细日志框）
        group_log = QGroupBox("运行日志")
        group_log.setStyleSheet(UIStyles.PANEL_EXEC)
        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)

        # 摘要栏：当前步骤概况 + 操作按钮
        self.brief_frame = QFrame()
        self.brief_frame.setStyleSheet(UIStyles.PANEL_BRIEF_FRAME)
        self.brief_frame.setFixedHeight(UIDims.BRIEF_FRAME_HEIGHT)

        brief_outer_layout = QHBoxLayout(self.brief_frame)
        brief_outer_layout.setContentsMargins(10, 5, 10, 5)

        brief_inner_layout = QVBoxLayout()
        brief_inner_layout.setSpacing(2)
        self.lbl_log_line1 = QLabel("任务就绪")
        self.lbl_log_line1.setStyleSheet(UIStyles.LBL_BRIEF_TITLE)
        self.lbl_log_line2 = QLabel("等待开始...")
        self.lbl_log_line2.setStyleSheet(UIStyles.LBL_BRIEF_DETAIL)
        brief_inner_layout.addWidget(self.lbl_log_line1)
        brief_inner_layout.addWidget(self.lbl_log_line2)

        brief_outer_layout.addLayout(brief_inner_layout)
        brief_outer_layout.addStretch()

        self.btn_open_folder = QPushButton("打开任务所在文件夹")
        self.btn_open_folder.setStyleSheet(UIStyles.BTN_LOG_BLUE)
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.open_task_folder)
        brief_outer_layout.addWidget(self.btn_open_folder)

        self.btn_clear_log = QPushButton("清除本地日志记录")
        self.btn_clear_log.setStyleSheet(UIStyles.BTN_LOG_RED)
        self.btn_clear_log.setCursor(Qt.PointingHandCursor)
        self.btn_clear_log.setEnabled(False)
        self.btn_clear_log.clicked.connect(self.clear_local_log)
        brief_outer_layout.addWidget(self.btn_clear_log)

        # 详细日志文本框
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(UIStyles.PANEL_LOG_AREA)

        log_layout.addWidget(self.brief_frame)
        log_layout.addWidget(self.log_area)
        group_log.setLayout(log_layout)

        r_layout.addWidget(group_desc, 1)
        r_layout.addWidget(group_ctrl, 0)
        r_layout.addWidget(group_log, 2)
        right_panel.setLayout(r_layout)

        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)

        # self.refresh_list()
        # self.refresh_shortcut_hints()

    # ----- 列表 / 任务选择 -----

    def refresh_list(self):
        """刷新左侧任务列表（排除草稿任务）"""
        self.list_tasks.blockSignals(True)
        self.list_tasks.clear()
        tasks = self.task_manager.get_all_tasks()
        if TaskManager.DRAFT_TASK_NAME in tasks:
            tasks.remove(TaskManager.DRAFT_TASK_NAME)
        self.list_tasks.addItems(tasks)
        # 恢复之前的选中状态
        if self.memory_task_name and self.memory_task_name in tasks:
            items = self.list_tasks.findItems(self.memory_task_name, Qt.MatchExactly)
            if items:
                self.list_tasks.setCurrentItem(items[0])
                self.on_task_selected(items[0], None)
        else:
            self.memory_task_name = None  # 任务可能被删除了，清除记忆
        self.list_tasks.blockSignals(False)

    def on_task_selected(self, current, previous):
        """选中任务时加载说明和运行配置"""
        if not current:
            return
        task_name = current.text()
        # 更新记忆并写入全局配置
        self.memory_task_name = task_name
        global_config.set_app_setting("last_exec_task", task_name)

        # 更新界面标签和 OSD 悬浮窗
        title = f"当前已选中任务: {task_name}"
        subtitle = "状态: 尚未开始"
        self.lbl_log_line1.setText(title)
        self.lbl_log_line2.setText(subtitle)
        self.signal_bridge.status_signal.emit(title, subtitle)

        info = self.task_manager.load_task_info(task_name)
        self.readme_display.setPlainText(info)
        task_dir = self.task_manager.get_task_path(task_name)
        self.current_task_dir = task_dir
        self.current_log_file_path = os.path.join(task_dir, "run_log.txt")
        self.btn_clear_log.setEnabled(True)
        self.btn_open_folder.setEnabled(True)
        self.load_run_settings(task_dir)

    # ----- 运行配置持久化 -----

    def load_run_settings(self, task_dir):
        """从任务文件夹中读取上次的运行次数和超时设置"""
        settings_path = os.path.join(task_dir, "run_settings.json")
        times, timeout = 1, 3600
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    times = data.get("run_times", 1)
                    timeout = data.get("timeout_sec", 3600)
            except Exception as e:
                print(f"读取任务运行配置失败: {e}")
        # 阻塞信号防止触发 save
        self.spin_run_times.blockSignals(True)
        self.spin_timeout.blockSignals(True)
        self.spin_run_times.setValue(times)
        self.spin_timeout.setValue(timeout)
        self.spin_run_times.blockSignals(False)
        self.spin_timeout.blockSignals(False)

    def save_run_settings(self, *_):
        """将运行次数和超时设置保存到任务文件夹"""
        if not getattr(self, "current_task_dir", None):
            return
        settings_path = os.path.join(self.current_task_dir, "run_settings.json")
        data = {"run_times": self.spin_run_times.value(), "timeout_sec": self.spin_timeout.value()}
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务运行配置失败: {e}")

    # ----- 日志相关 -----

    def refresh_shortcut_hints(self):
        """更新运行/停止按钮旁的快捷键提示文本"""
        shortcuts = global_config.get_shortcuts()
        run_key = shortcuts.get("run_task", "f8").upper()
        stop_key = shortcuts.get("stop_task", "f9").upper()
        self.lbl_run_hint.setText(f"运行: {run_key}")
        self.lbl_stop_hint.setText(f"停止: {stop_key}")

    def handle_log(self, title, detail, brief_line2, is_detail_only):
        """处理来自调度线程的日志信号，更新摘要栏和日志文本框"""
        is_detail_mode = global_config.get_app_setting("detailed_log", False)
        timestamp = time.strftime("%H:%M:%S")
        if not is_detail_only:
            self.lbl_log_line1.setText(title)
            self.lbl_log_line2.setText(brief_line2)
        if is_detail_mode:
            # 详细模式：所有消息都输出
            if title and title != detail:
                log_text = f"[{timestamp}] {title} >> {detail}"
            else:
                log_text = f"[{timestamp}] {detail}"
            self.log_area.append(log_text)
            self._append_to_file(log_text)
            sb = self.log_area.verticalScrollBar()
            sb.setValue(sb.maximum())
        else:
            # 精简模式：仅输出非 DEBUG 消息
            if not is_detail_only:
                if brief_line2 and brief_line2 != title:
                    log_text = f"[{timestamp}] {title} -> {brief_line2}"
                else:
                    log_text = f"[{timestamp}] {title}"
                self.log_area.append(log_text)
                self._append_to_file(log_text)
                sb = self.log_area.verticalScrollBar()
                sb.setValue(sb.maximum())

    def _append_to_file(self, text):
        """将日志文本追加写入本地日志文件"""
        if self.current_log_file_path:
            try:
                with open(self.current_log_file_path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
            except Exception as e:
                print(f"写入本地日志失败: {e}")

    def open_task_folder(self):
        """用系统文件管理器打开当前任务所在文件夹"""
        if self.current_task_dir and os.path.exists(self.current_task_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_task_dir))
        else:
            QMessageBox.warning(self, "错误", "无法找到当前任务的文件夹！")

    def clear_local_log(self):
        """清空当前任务的本地日志文件"""
        if not self.current_log_file_path:
            return
        reply = QMessageBox.question(
            self,
            "清理日志",
            "确定要清空该任务的本地日志记录吗？\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                with open(self.current_log_file_path, "w", encoding="utf-8") as f:
                    pass
                QMessageBox.information(self, " ", "本地日志记录已清空！")
                self.log_area.append("\n>>> 本地日志记录已被手动清空 <<<\n")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空日志失败: {e}")

    # ----- 运行 / 停止任务 -----

    def run_task(self):
        """开始执行所选任务（在子线程中运行调度器）"""
        # 不再依赖 UI 组件的选中状态，直接读取记忆变量
        task_name = self.memory_task_name
        if not task_name:
            self.log_area.append("[Warning] 请先在左侧选择一个任务")
            return
        # 二次校验任务是否还存在于硬盘上
        tasks = self.task_manager.get_all_tasks()
        if task_name not in tasks:
            self.log_area.append(f"[Error] 任务 '{task_name}' 已不存在，请重新选择")
            self.memory_task_name = None
            self.refresh_list()
            return

        script_data = self.task_manager.load_script(task_name)
        task_dir = self.task_manager.get_task_path(task_name)
        self.current_task_dir = task_dir
        self.current_log_file_path = os.path.join(task_dir, "run_log.txt")
        if not script_data:
            self.log_area.append("[Error] 任务脚本为空")
            return

        run_times = max(self.spin_run_times.value(), 1)
        timeout_sec = self.spin_timeout.value()
        processed_script = self._preprocess_script(script_data, task_dir)

        start_msg = f"--- 开始任务: {task_name} (计划执行 {run_times} 次) ---"
        self.log_area.clear()
        self.log_area.append(start_msg)
        start_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        self._append_to_file(f"\n\n{'=' * 40} {start_time_str} {'=' * 40}")
        self._append_to_file(start_msg)

        # 禁用界面控件，防止运行中误操作
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.list_tasks.setEnabled(False)
        self.spin_run_times.setEnabled(False)
        self.spin_timeout.setEnabled(False)
        self.log_area.setFocus()

        t = threading.Thread(target=self._thread_runner, args=(processed_script, run_times, timeout_sec))
        t.daemon = True
        t.start()

    def stop_task(self):
        """发送停止指令给调度器"""
        self.scheduler.stop()
        self.signal_bridge.log_signal.emit("正在停止", ">>> 发送停止指令...", "正在停止...", False)

    def _preprocess_script(self, script_data, task_dir):
        """将脚本中的相对图片路径拼接为绝对路径"""
        import copy

        new_data = copy.deepcopy(script_data)
        for step in new_data:
            params = step.get("params", {})
            if "image_path" in params:
                params["image_path"] = os.path.join(task_dir, params["image_path"])
        return new_data

    def _thread_runner(self, script_data, run_times, timeout_sec):
        """子线程：运行调度器并通过信号桥回传日志"""

        def event_adapter(event_type, message, data):
            """将调度器的事件格式转换为日志信号"""
            step_desc = data.get("step_desc", "")
            loop_ctx = data.get("loop_context", "")
            title = step_desc if step_desc else message
            if loop_ctx:
                title += f"  [{loop_ctx}]"
            detail_msg = message
            brief_line2 = message
            is_detail_only = event_type == "DEBUG"
            self.signal_bridge.log_signal.emit(title, detail_msg, brief_line2, is_detail_only)

        self.scheduler.set_event_listener(event_adapter)
        self.signal_bridge.log_signal.emit(
            "任务启动", f">>> 任务引擎已启动... (共 {run_times} 轮)", "正在初始化...", False
        )
        try:
            self.scheduler.run_script(script_data, run_times=run_times, timeout_sec=timeout_sec)
        except Exception as e:
            self.signal_bridge.log_signal.emit("异常停止", f"[Error] {e}", f"发生错误: {e}", False)
        finally:
            self.signal_bridge.log_signal.emit("任务结束", "--- 任务运行结束 ---", "任务已完成或被停止", False)
            QApplication.instance().postEvent(self, MyFinishEvent())

    def customEvent(self, e):
        """接收 MyFinishEvent，恢复界面控件状态"""
        if e.type() == QEvent.User + 1:
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.list_tasks.setEnabled(True)
            self.spin_run_times.setEnabled(True)
            self.spin_timeout.setEnabled(True)
            # 读取记忆的任务名，更新 OSD 状态
            task_name = getattr(self, "memory_task_name", "未知任务")
            title = f"任务已结束: {task_name}"
            subtitle = "状态: 等待下一次运行..."

            self.lbl_log_line1.setText(title)
            self.lbl_log_line2.setText(subtitle)
            self.signal_bridge.status_signal.emit(title, subtitle)

    # ----- 辅助事件过滤 -----

    def eventFilter(self, source, event):
        """SpinBox 鼠标释放时取消焦点，避免滚轮误改值"""
        if source == self.spin_run_times and event.type() == QEvent.MouseButtonRelease:
            self.spin_run_times.clearFocus()
        return super().eventFilter(source, event)

    def _validate_loop_count(self):
        """校验循环次数，确保不小于 1"""
        try:
            val = int(self.spin_run_times.value())
            if val < 1:
                self.spin_run_times.setValue(self._last_valid_loop_count)
            else:
                self._last_valid_loop_count = val
        except:
            self.spin_run_times.setValue(self._last_valid_loop_count)


# ========================================================================
#  任务管理页面：创建新任务、查看/重命名/编辑已有任务
# ========================================================================


class ManageTaskWidget(QWidget):
    def __init__(self, task_manager, main_window):
        super().__init__()
        self.task_manager = task_manager
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        UIDims.apply_page_layout(layout)

        # 创建新任务区域
        create_box = QGroupBox("创建新任务")
        create_box.setStyleSheet(UIStyles.PANEL_MANAGE)
        c_layout = QHBoxLayout()
        self.input_new_name = QLineEdit()
        self.input_new_name.setPlaceholderText("请输入新任务名称...")
        self.input_new_name.setMinimumHeight(UIDims.MANAGE_INPUT_HEIGHT)
        self.input_new_name.setStyleSheet(UIStyles.INPUT_MANAGE_NAME)
        btn_create = QPushButton("创建并编辑")
        btn_create.setMinimumHeight(UIDims.MANAGE_INPUT_HEIGHT)
        btn_create.setStyleSheet(UIStyles.BTN_CREATE_TASK)
        btn_create.clicked.connect(self.create_task)
        c_layout.addWidget(self.input_new_name)
        c_layout.addWidget(btn_create)
        create_box.setLayout(c_layout)

        # 已有任务列表区域
        edit_box = QGroupBox("已有任务")
        edit_box.setStyleSheet(UIStyles.PANEL_MANAGE)
        e_layout = QVBoxLayout()
        self.list_tasks = QListWidget()
        self.list_tasks.itemDoubleClicked.connect(self.go_to_edit)
        btn_layout = QHBoxLayout()
        btn_edit = QPushButton("编辑选中任务")
        btn_edit.clicked.connect(self.go_to_edit)
        btn_rename = QPushButton("重命名")
        btn_rename.clicked.connect(self.rename_task)
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self.refresh_list)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_rename)
        btn_layout.addWidget(btn_refresh)
        e_layout.addWidget(self.list_tasks)
        e_layout.addLayout(btn_layout)
        edit_box.setLayout(e_layout)

        layout.addWidget(create_box)
        layout.addWidget(edit_box)
        self.refresh_list()

    def refresh_list(self):
        """刷新已有任务列表"""
        self.list_tasks.clear()
        tasks = self.task_manager.get_all_tasks()
        if TaskManager.DRAFT_TASK_NAME in tasks:
            tasks.remove(TaskManager.DRAFT_TASK_NAME)
        self.list_tasks.addItems(tasks)

    def create_task(self):
        """创建新任务并跳转到编辑器"""
        name = self.input_new_name.text().strip()
        if not name:
            return
        if not self.main_window.confirm_discard_changes():
            return
        success, msg = self.task_manager.create_task(name)
        if success:
            self.input_new_name.clear()
            self.refresh_list()
            self.main_window.switch_to_editor(name)
        else:
            QMessageBox.warning(self, "错误", msg)

    def rename_task(self):
        """重命名选中的任务"""
        item = self.list_tasks.currentItem()
        if not item:
            return
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            success, msg = self.task_manager.rename_task(old_name, new_name)
            if success:
                self.refresh_list()
            else:
                QMessageBox.warning(self, "错误", msg)

    def go_to_edit(self):
        """跳转到编辑器编辑选中任务"""
        item = self.list_tasks.currentItem()
        if not item:
            QMessageBox.warning(self, " ", "请选择要编辑的任务")
            return
        if not self.main_window.confirm_discard_changes():
            return
        self.main_window.switch_to_editor(item.text())


# ========================================================================
#  主窗口：承载所有标签页，管理全局快捷键和悬浮日志
# ========================================================================


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evethan")
        self.resize(UIDims.WINDOW_MAIN_W, UIDims.WINDOW_MAIN_H)
        self.floating_osd = FloatingOSD()  # 悬浮日志窗口
        self.task_manager = TaskManager()
        self.task_manager.ensure_draft_task()  # 确保草稿任务目录存在

        # --- 中心容器 ---
        central_container = QWidget()
        self.setCentralWidget(central_container)
        main_layout = QVBoxLayout(central_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 标签页 ---
        self.tabs = QTabWidget()

        self.tab_execute = ExecuteWidget(self.task_manager)
        self.tabs.addTab(self.tab_execute, "执行任务")

        self.tab_manage = ManageTaskWidget(self.task_manager, self)
        self.tabs.addTab(self.tab_manage, "任务管理")

        self.tab_editor = TaskEditorWidget(self.task_manager)
        self.tabs.addTab(self.tab_editor, "任务编辑器")

        self.tab_config = DefaultSettingsWidget()
        self.tabs.addTab(self.tab_config, "指令参数配置")

        self.tab_settings = SettingsWidget()
        self.tabs.addTab(self.tab_settings, "其它设置")
        self.tab_settings.settings_changed.connect(self.on_settings_changed)

        # --- 右上角工具按钮（定位仪、测距仪） ---
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 8, 0)
        corner_layout.setSpacing(8)

        btn_global_pick = QPushButton("定位仪")
        btn_global_pick.setCursor(Qt.PointingHandCursor)
        btn_global_pick.setStyleSheet(UIStyles.BTN_CORNER_TOOL)
        btn_global_pick.clicked.connect(self.open_global_locator)

        btn_global_rule = QPushButton("测距仪")
        btn_global_rule.setCursor(Qt.PointingHandCursor)
        btn_global_rule.setStyleSheet(UIStyles.BTN_CORNER_TOOL)
        btn_global_rule.clicked.connect(self.open_global_ruler)

        corner_layout.addWidget(btn_global_pick)
        corner_layout.addWidget(btn_global_rule)
        self.tabs.setCornerWidget(corner_widget, Qt.TopRightCorner)

        main_layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # 将执行日志同步到悬浮日志窗口
        self.tab_execute.signal_bridge.log_signal.connect(self.floating_osd.update_text)
        # 将状态信号连接到 OSD
        self.tab_execute.signal_bridge.status_signal.connect(
            lambda line1, line2: self.floating_osd.update_text(line1, "", line2, False)
        )

        self.tab_execute.refresh_list()
        self.tab_execute.refresh_shortcut_hints()

        # 默认打开草稿任务
        self.tab_editor.open_task(TaskManager.DRAFT_TASK_NAME)

        # --- 全局快捷键 ---
        self.hotkey_handler = GlobalHotkeyHandler()
        self.hotkey_handler.start()
        self.hotkey_handler.sig_run.connect(self.on_global_run)
        self.hotkey_handler.sig_stop.connect(self.on_global_stop)
        self.hotkey_handler.sig_toggle_osd.connect(self.floating_osd.toggle_visibility)

    # ----- 设置变更回调 -----

    def on_settings_changed(self):
        """配置页面变更后刷新全局快捷键、保存快捷键和悬浮日志"""
        print("配置变更，正在刷新快捷键和OSD...")
        self.hotkey_handler.reload()
        self.tab_editor.reload_save_shortcut()
        self.floating_osd.reload_config()
        self.tab_execute.refresh_shortcut_hints()

    # ----- 全局快捷键回调 -----

    def on_global_run(self):
        print(">>> 全局快捷键: 运行任务")
        self.tab_execute.run_task()

    def on_global_stop(self):
        print(">>> 全局快捷键: 停止任务")
        self.tab_execute.stop_task()

    # ----- 屏幕工具 -----

    def open_global_locator(self):
        """打开定位仪（屏幕取点工具）"""
        self.global_tool = ScreenTool(mode="picker")
        self.global_tool.finished.connect(self.show_global_pick_result)
        self.global_tool.show()

    def show_global_pick_result(self, x, y, dx, dy):
        QMessageBox.information(self, "定位结果", f"坐标点: ({x}, {y})")

    def open_global_ruler(self):
        """打开测距仪（屏幕测距工具）"""
        self.global_tool = ScreenTool(mode="ruler")
        self.global_tool.finished.connect(self.show_global_rule_result)
        self.global_tool.show()

    def show_global_rule_result(self, x, y, dx, dy):
        QMessageBox.information(self, "测距结果", f"终点坐标: ({x}, {y})\n相对偏移: dx={dx}, dy={dy}")

    # ----- 标签页切换 -----

    def on_tab_changed(self, index):
        """切换标签页时自动刷新对应列表"""
        if index == 0:
            self.tab_execute.refresh_list()
        elif index == 1:
            self.tab_manage.refresh_list()
        if index == 2 and not self.tab_editor.current_task_name:
            self.tab_editor.open_task(TaskManager.DRAFT_TASK_NAME)

    # ----- 跨页面协调方法 -----

    def confirm_discard_changes(self):
        """由管理页面调用：在切换任务前确认编辑器的未保存修改"""
        return self.tab_editor.check_unsaved_changes()

    def switch_to_editor(self, task_name):
        """打开指定任务并切换到编辑器标签页"""
        self.tab_editor.open_task(task_name)
        self.tabs.setCurrentIndex(2)

    # ----- 关闭窗口 -----

    def closeEvent(self, event: QCloseEvent):
        """关闭主窗口前检查未保存修改，并关闭悬浮日志"""
        self.floating_osd.close()
        if self.tab_editor.check_unsaved_changes():
            event.accept()
        else:
            event.ignore()


# ========================================================================
#  程序入口
# ========================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 临时方案，屏蔽深色模式干扰
    if hasattr(app.styleHints(), "setColorScheme"):
        # PySide6 6.5 及以上版本
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    else:
        # 低版本 PySide6
        app.setStyle("Fusion")

    # 确定基础目录
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # 设置窗口图标
    icon_path = os.path.join(base_dir, "assets", "logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"错误：找不到图标文件 {icon_path}")

    # 应用全局字体和样式
    app.setFont(UIFonts.app_default())
    combined_style = UIStyles.APP_GLOBAL + UIStyles.APP_SPINBOX
    app.setStyleSheet(combined_style)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

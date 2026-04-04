# ui_styles.py
# UI 样式定义模块：集中管理应用的颜色、字体、尺寸和 QSS 样式表


from PySide6.QtGui import QColor, QFont, Qt


# ═══════════════════════════════════════════════════════════
# 基础调色板 —— 定义所有原始色值
# ═══════════════════════════════════════════════════════════
class Palette:
    # 黑白
    WHITE = "#FFFFFF"
    BLACK = "#000000"
    # 灰色系列（数字越大越深）
    GRAY_100 = "#F8FAFC"
    GRAY_200 = "#F1F5F9"
    GRAY_300 = "#E2E8F0"
    GRAY_500 = "#64748B"
    GRAY_700 = "#1E293B"
    GRAY_900 = "#0F172A"
    # 蓝色系列
    BLUE_100 = "#EFF6FF"
    BLUE_300 = "#BFDBFE"
    BLUE_500 = "#3B82F6"
    BLUE_700 = "#1D4ED8"
    BLUE_900 = "#1E3A8A"
    # 绿色系列
    GREEN_100 = "#F0FDF4"
    GREEN_300 = "#BBF7D0"
    GREEN_500 = "#22C55E"
    GREEN_700 = "#15803D"
    GREEN_900 = "#14532D"
    # 橙色系列
    ORANGE_100 = "#FFF7ED"
    ORANGE_300 = "#FED7AA"
    ORANGE_500 = "#F59E0B"
    ORANGE_700 = "#C2410C"
    ORANGE_900 = "#7C2D12"
    # 红色系列
    RED_100 = "#FEF2F2"
    RED_300 = "#FECACA"
    RED_500 = "#EF4444"
    RED_700 = "#B91C1C"
    RED_900 = "#7F1D1D"
    # 紫色系列
    PURPLE_100 = "#FAF5FF"
    PURPLE_300 = "#E9D5FF"
    PURPLE_500 = "#A855F7"
    PURPLE_700 = "#7E22CE"
    PURPLE_900 = "#581C87"


# ═══════════════════════════════════════════════════════════
# 语义色 —— 将调色板映射为具有业务含义的名称
# ═══════════════════════════════════════════════════════════
class Semantic:
    GRAY_900 = Palette.GRAY_900

    # --- 通用背景 / 边框 / 文字 ---
    BG_BASE = Palette.GRAY_300          # 页面底色
    BG_SURFACE = Palette.WHITE          # 卡片 / 面板底色
    BG_SURFACE_ALT = Palette.GRAY_100   # 次级面板底色
    BG_HOVER = Palette.GRAY_200         # 悬停高亮
    BORDER_DEFAULT = Palette.GRAY_300   # 默认边框
    BORDER_HOVER = Palette.GRAY_500     # 悬停边框
    TEXT_PRIMARY = Palette.GRAY_700     # 主要文字
    TEXT_SECONDARY = Palette.GRAY_500   # 次要文字
    TEXT_INVERSE = Palette.WHITE        # 反色文字（深色背景上）
    TEXT_DISABLED = Palette.GRAY_500    # 禁用文字

    # --- 代码块 ---
    BG_CODE = Palette.GRAY_900
    TEXT_CODE = Palette.GRAY_300
    BORDER_CODE = Palette.GRAY_700

    # --- 主色（蓝） ---
    PRIMARY_BG = Palette.BLUE_500
    PRIMARY_HOVER = Palette.BLUE_300
    PRIMARY_PRESSED = Palette.BLUE_700
    PRIMARY_TEXT = Palette.WHITE
    PRIMARY_LIGHT_BG = Palette.BLUE_100
    PRIMARY_LIGHT_BORDER = Palette.BLUE_300
    PRIMARY_LIGHT_TEXT = Palette.BLUE_700
    PRIMARY_DARK_TEXT = Palette.BLUE_900

    # --- 成功色（绿） ---
    SUCCESS_BG = Palette.GREEN_500
    SUCCESS_HOVER = Palette.GREEN_300
    SUCCESS_PRESSED = Palette.GREEN_700
    SUCCESS_TEXT = Palette.WHITE
    SUCCESS_LIGHT_BG = Palette.GREEN_100
    SUCCESS_LIGHT_BORDER = Palette.GREEN_300
    SUCCESS_LIGHT_TEXT = Palette.GREEN_700
    SUCCESS_DARK_TEXT = Palette.GREEN_900

    # --- 警告色（橙） ---
    WARNING_BG = Palette.ORANGE_500
    WARNING_HOVER = Palette.ORANGE_300
    WARNING_PRESSED = Palette.ORANGE_700
    WARNING_TEXT = Palette.WHITE
    WARNING_LIGHT_BG = Palette.ORANGE_100
    WARNING_LIGHT_BORDER = Palette.ORANGE_300
    WARNING_LIGHT_TEXT = Palette.ORANGE_700
    WARNING_DARK_TEXT = Palette.ORANGE_900

    # --- 危险色（红） ---
    DANGER_BG = Palette.RED_500
    DANGER_HOVER = Palette.RED_300
    DANGER_PRESSED = Palette.RED_700
    DANGER_TEXT = Palette.WHITE
    DANGER_LIGHT_BG = Palette.RED_100
    DANGER_LIGHT_BORDER = Palette.RED_300
    DANGER_LIGHT_TEXT = Palette.RED_700
    DANGER_DARK_TEXT = Palette.RED_900

    # --- 辅助色（紫） ---
    AUX_BG = Palette.PURPLE_500
    AUX_HOVER = Palette.PURPLE_300
    AUX_PRESSED = Palette.PURPLE_700
    AUX_TEXT = Palette.WHITE
    AUX_LIGHT_BG = Palette.PURPLE_100
    AUX_LIGHT_BORDER = Palette.PURPLE_300
    AUX_LIGHT_TEXT = Palette.PURPLE_700
    AUX_DARK_TEXT = Palette.PURPLE_900


# ═══════════════════════════════════════════════════════════
# QColor 实例 —— 供绘制代码直接使用的颜色对象
# ═══════════════════════════════════════════════════════════
class UIColors:
    Palette = Palette
    Semantic = Semantic

    # --- 基础灰色 ---
    WHITE = QColor(Palette.WHITE)
    BLACK = QColor(Palette.BLACK)
    GRAY_BG = QColor(Semantic.BG_SURFACE_ALT)
    GRAY_HOVER = QColor(Semantic.BG_HOVER)
    GRAY_BORDER = QColor(Semantic.BORDER_DEFAULT)
    GRAY_TEXT_SEC = QColor(Semantic.TEXT_SECONDARY)
    GRAY_TEXT_PRI = QColor(Semantic.TEXT_PRIMARY)

    # --- 列表行左侧色带 / 底部分隔线 / 缩进引导线 ---
    STRIP_BG = QColor(Semantic.BG_SURFACE_ALT)
    STRIP_LINE = QColor(Semantic.BORDER_DEFAULT)
    ITEM_BOTTOM_BORDER = QColor(Semantic.BORDER_DEFAULT)
    GUIDE_LINE = QColor(Semantic.BORDER_DEFAULT)
    GUIDE_LINE_SOLID = QColor(Semantic.DANGER_HOVER)

    # --- 拖放指示线 ---
    DROP_LINE = QColor(Semantic.PRIMARY_BG)

    # --- 行背景（普通 / 循环 / 分组 / 条件 / 分隔符） ---
    BG_NORMAL = QColor(Semantic.BG_SURFACE)
    BG_NORMAL_SEL = QColor(Semantic.PRIMARY_LIGHT_BG)
    BG_LOOP = QColor(Semantic.WARNING_LIGHT_BG)
    BG_LOOP_SEL = QColor(Semantic.WARNING_LIGHT_BORDER)
    BG_GROUP = QColor(Semantic.SUCCESS_LIGHT_BG)
    BG_GROUP_SEL = QColor(Semantic.SUCCESS_LIGHT_BORDER)
    BG_IF = QColor(Semantic.PRIMARY_LIGHT_BG)
    BG_IF_SEL = QColor(Semantic.PRIMARY_LIGHT_BORDER)
    SEPARATOR_BG = QColor(Semantic.AUX_LIGHT_BG)
    SEPARATOR_TEXT = QColor(Semantic.AUX_LIGHT_TEXT)
    SEPARATOR_LINE = QColor(Semantic.AUX_LIGHT_BORDER)

    # --- 折叠按钮 ---
    FOLD_BTN_BORDER = QColor(Semantic.TEXT_SECONDARY)
    FOLD_BTN_SYMBOL = QColor(Semantic.TEXT_PRIMARY)
    FOLD_BTN_BG = QColor(Semantic.BG_SURFACE)

    # --- 录制按钮 ---
    BTN_RECORD_BG = QColor(Semantic.SUCCESS_LIGHT_BG)
    BTN_RECORD_BORDER = QColor(Semantic.SUCCESS_BG)
    BTN_RECORD_TEXT = QColor(Semantic.SUCCESS_PRESSED)

    # --- 录制面板边框 ---
    REC_DISPLAY_BORDER = QColor(Semantic.BORDER_DEFAULT)

    # --- 工具箱标题 ---
    TOOLBOX_HEADER_BG = QColor(Semantic.BORDER_DEFAULT)
    TOOLBOX_HEADER_TEXT = QColor(Semantic.TEXT_PRIMARY)

    # --- 通用文本颜色 ---
    TEXT_NORMAL = QColor(Semantic.TEXT_PRIMARY)
    TEXT_INVERSE = QColor(Semantic.TEXT_INVERSE)
    TEXT_KEYWORD = QColor(Semantic.DANGER_BG)

    # --- 内嵌框背景 ---
    BG_INNER_BOX = QColor(Semantic.BG_SURFACE)

    # --- 工具箱分类项（鼠标 / 键盘 / 控制流） ---
    TOOLBOX_ITEM_MOUSE = QColor(Semantic.WARNING_LIGHT_BG)
    TOOLBOX_ITEM_KEYBOARD = QColor(Semantic.SUCCESS_LIGHT_BG)
    TOOLBOX_ITEM_CONTROL = QColor(Semantic.DANGER_LIGHT_BG)
    TOOLBOX_HEADER_MOUSE_BG = QColor(Semantic.WARNING_LIGHT_BORDER)
    TOOLBOX_HEADER_MOUSE_TEXT = QColor(Semantic.WARNING_LIGHT_TEXT)
    TOOLBOX_HEADER_KEYBOARD_BG = QColor(Semantic.SUCCESS_LIGHT_BORDER)
    TOOLBOX_HEADER_KEYBOARD_TEXT = QColor(Semantic.SUCCESS_LIGHT_TEXT)
    TOOLBOX_HEADER_CONTROL_BG = QColor(Semantic.DANGER_LIGHT_BORDER)
    TOOLBOX_HEADER_CONTROL_TEXT = QColor(Semantic.DANGER_LIGHT_TEXT)

    # --- 纯色 ---
    PURE_GREEN = QColor(0, 255, 0)
    PURE_YELLOW = QColor(255, 255, 0)

    # --- OSD（屏幕叠加层）颜色 ---
    OSD_TEXT_FILL = PURE_GREEN
    OSD_TEXT_OUTLINE = QColor(0, 0, 0, 240)
    OSD_OVERLAY = QColor(0, 0, 0, 150)
    OSD_CROSSHAIR = QColor(255, 255, 255, 100)
    OSD_BTN_BG = QColor(255, 255, 255, 200)

    # --- 工具模式叠加层颜色 ---
    TOOL_OVERLAY = QColor(0, 0, 0, 100)
    TOOL_CROSSHAIR = PURE_GREEN
    TOOL_RECT_SCREENSHOT = QColor(0, 255, 255)
    TOOL_RECT_SELECT = QColor(255, 165, 0)
    TOOL_RULER_LINE = PURE_YELLOW
    TOOL_COORD_TEXT = TEXT_INVERSE
    TOOL_HINT_TEXT = PURE_YELLOW


# ═══════════════════════════════════════════════════════════
# 字体工厂 —— 统一管理字体创建
# ═══════════════════════════════════════════════════════════
class UIFonts:
    FAMILY_DEFAULT = "Microsoft YaHei"   # 默认字体
    FAMILY_MONO = "Consolas"             # 等宽字体

    # ---------- 应用全局默认字体 ----------

    @staticmethod
    def app_default() -> QFont:
        """应用默认字体"""
        return QFont(UIFonts.FAMILY_DEFAULT, 14)

    # ---------- OSD 相关字体 ----------

    @staticmethod
    def osd(size: int, bold: bool = True) -> QFont:
        """OSD 通用字体，可指定大小和粗细"""
        return QFont(UIFonts.FAMILY_DEFAULT, size, QFont.Bold if bold else QFont.Normal)

    @staticmethod
    def osd_config_hint() -> QFont:
        """OSD 配置提示文字字体"""
        return QFont(UIFonts.FAMILY_DEFAULT, 20, QFont.Bold)

    @staticmethod
    def osd_config_btn() -> QFont:
        """OSD 配置按钮字体"""
        return QFont(UIFonts.FAMILY_DEFAULT, 24, QFont.Bold)

    # ---------- 工具叠加层字体 ----------

    @staticmethod
    def tool_overlay() -> QFont:
        """工具叠加层文字字体"""
        return QFont(UIFonts.FAMILY_DEFAULT, 14, QFont.Bold)

    # ---------- 列表委托相关字体 ----------

    @staticmethod
    def delegate_separator(base_font: QFont) -> QFont:
        """分隔行字体（比基准大 3pt，加粗）"""
        f = QFont(base_font)
        f.setPointSize(base_font.pointSize() + 3)
        f.setBold(True)
        return f

    @staticmethod
    def delegate_rec_btn(base_font: QFont) -> QFont:
        """录制按钮字体"""
        return QFont(base_font.family(), 11)

    @staticmethod
    def delegate_bold(base_font: QFont) -> QFont:
        """加粗委托字体"""
        return QFont(base_font.family(), base_font.pointSize(), QFont.Bold)

    # ---------- 工具箱标题字体 ----------

    @staticmethod
    def toolbox_header(base_font: QFont) -> QFont:
        """工具箱分类标题字体（加粗）"""
        f = QFont(base_font)
        f.setBold(True)
        return f


# ═══════════════════════════════════════════════════════════
# 尺寸常量 —— 统一管理各处固定数值
# ═══════════════════════════════════════════════════════════
class UIDims:
    # --- 行高 ---
    ITEM_H_NORMAL = 50       # 普通步骤行高
    ITEM_H_KEY = 60          # 按键步骤行高
    ITEM_H_SEPARATOR = 60    # 分隔符行高
    ITEM_H_STRUCTURE = 40    # 结构行（循环/分组头尾）行高

    # --- 工具箱 ---
    TOOLBOX_HEADER_H = 44
    TOOLBOX_ITEM_H = 40

    # --- 委托绘制 ---
    DELEGATE_STRIP_WIDTH = 60       # 左侧色带宽度
    DELEGATE_CHECKBOX_SIZE = 22     # 复选框大小
    DELEGATE_CHECKBOX_MARGIN_LEFT = 8
    DELEGATE_FOLD_BTN_SIZE = 20     # 折叠按钮大小
    DELEGATE_INDENT_STEP = 20       # 缩进步长
    DELEGATE_INNER_MARGIN_TOP = 32  # 内嵌框顶部偏移

    # --- 录制按钮 ---
    BTN_REC_WIDTH = 50
    BTN_REC_HEIGHT = 22

    # --- 简要信息框 ---
    BRIEF_FRAME_HEIGHT = 65

    # --- 管理页输入框 ---
    MANAGE_INPUT_HEIGHT = 48

    # --- 全选 / 取消全选按钮 ---
    BTN_SELECT_ALL_W = 65
    BTN_SELECT_ALL_H = 28
    BTN_UNSELECT_ALL_W = 75
    BTN_UNSELECT_ALL_H = 28

    # --- 设置页快捷键输入 ---
    SETTINGS_KEY_INPUT_MAX_W = 200
    SETTINGS_FIXED_KEY_INPUT_MAX_W = 280
    SETTINGS_KEY_REC_BTN_W = 90

    # --- 窗口默认尺寸 ---
    WINDOW_MAIN_W = 1440
    WINDOW_MAIN_H = 960
    WINDOW_RECORDER_W = 440
    WINDOW_RECORDER_H = 220

    # --- 通用间距 ---
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL = 4, 8, 12, 16, 24

    # --- 工具模式文字偏移 ---
    TOOL_TEXT_OFFSET_X = 5
    TOOL_TEXT_OFFSET_Y = 15
    TOOL_CURSOR_OFFSET = 25

    # --- 页面布局边距 ---
    PAGE_MARGIN_LEFT = 8
    PAGE_MARGIN_TOP = 8
    PAGE_MARGIN_RIGHT = 8
    PAGE_MARGIN_BOTTOM = 8
    PAGE_SPACING = 8

    @staticmethod
    def apply_page_layout(layout):
        """将统一的页面边距和间距应用到布局"""
        layout.setContentsMargins(
            UIDims.PAGE_MARGIN_LEFT, UIDims.PAGE_MARGIN_TOP,
            UIDims.PAGE_MARGIN_RIGHT, UIDims.PAGE_MARGIN_BOTTOM,
        )
        layout.setSpacing(UIDims.PAGE_SPACING)


# ═══════════════════════════════════════════════════════════
# QSS 样式表集合 —— 所有控件的样式字符串
# ═══════════════════════════════════════════════════════════
class UIStyles:
    S = Semantic

    # 各面板的背景/边框/标题颜色预设
    _EXEC_BG, _EXEC_BD, _EXEC_TT = S.PRIMARY_LIGHT_BG, S.PRIMARY_LIGHT_BORDER, S.PRIMARY_DARK_TEXT
    _MANAGE_BG, _MANAGE_BD, _MANAGE_TT = S.WARNING_LIGHT_BG, S.WARNING_LIGHT_BORDER, S.WARNING_DARK_TEXT
    _EDITOR_BG, _EDITOR_BD, _EDITOR_TT = S.BG_SURFACE_ALT, S.BORDER_DEFAULT, S.GRAY_900
    _CONFIG_BG, _CONFIG_BD, _CONFIG_TT = S.SUCCESS_LIGHT_BG, S.SUCCESS_LIGHT_BORDER, S.SUCCESS_DARK_TEXT

    # ──────────── 工厂方法 ────────────

    @staticmethod
    def _btn_factory(bg, text_col, border, bg_hover, extra=""):
        """生成 QPushButton 的完整 QSS（含 hover / pressed / disabled 状态）"""
        return (
            f"QPushButton {{ background-color: {bg}; color: {text_col}; "
            f"border: 1px solid {border}; outline: none; {extra} }}"
            f"QPushButton:hover {{ background-color: {bg_hover}; }}"
            f"QPushButton:pressed {{ background-color: {border}; color: {Semantic.TEXT_INVERSE}; }}"
            f"QPushButton:disabled {{ background-color: {Semantic.BG_BASE}; color: {Semantic.TEXT_DISABLED}; "
            f"border: 1px solid {Semantic.BORDER_DEFAULT}; }}"
        )

    @staticmethod
    def _input_factory(bg, color, border, extra=""):
        """生成输入框（QLineEdit / QPlainTextEdit / QTextEdit）QSS"""
        return (
            f"QLineEdit, QPlainTextEdit, QTextEdit {{ background-color: {bg}; color: {color}; "
            f"border: 1px solid {border}; border-radius: 4px; padding: 6px; {extra} }}"
            f"QPlainTextEdit::viewport, QTextEdit::viewport {{ background-color: transparent; }}"
            f"QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {Semantic.PRIMARY_BG}; "
            f"background-color: {Semantic.BG_SURFACE}; }}"
            f"QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{ background-color: {Semantic.BG_HOVER}; "
            f"color: {Semantic.TEXT_DISABLED}; border: 1px solid {Semantic.BORDER_DEFAULT}; }}"
        )

    @staticmethod
    def _text_factory(color, size=None, weight="normal", extra=""):
        """生成纯文本标签的内联样式"""
        sz = f"font-size: {size};" if size else ""
        return f"color: {color}; font-weight: {weight}; {sz} {extra}"

    @staticmethod
    def _groupbox_factory(bg, border, title_color, radius=8, extra="", inner_bg=None):
        """生成 QGroupBox 面板样式，可选内嵌控件统一底色"""
        style = (
            f"QGroupBox {{"
            f"  background-color: {bg}; border: 1px solid {border};"
            f"  border-radius: {radius}px; margin-top: 0px;"
            f"  padding: 48px 12px 12px 12px; {extra} }}"
            f"QGroupBox::title {{"
            f"  subcontrol-origin: margin; subcontrol-position: top left;"
            f"  left: 16px; top: 12px; padding: 0 4px;"
            f"  color: {title_color}; font-size: 24px; font-weight: bold; }}"
        )
        if inner_bg:
            style += (
                f" QListWidget, QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{"
                f" background-color: {inner_bg}; border: 1px solid {border}; border-radius: 4px; }}"
                f" QListWidget::viewport, QTextEdit::viewport, QPlainTextEdit::viewport {{"
                f" background-color: transparent; }}"
            )
        return style

    # ──────────── 全局基础样式 ────────────

    APP_GLOBAL = f"""
        * {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }}
        QMainWindow, QDialog {{ background-color: {S.BG_BASE}; }}
        QCheckBox {{
            min-height: 32px;
            spacing: 8px;
            outline: none;
        }}
        QCheckBox::indicator {{
            width: {UIDims.DELEGATE_CHECKBOX_SIZE}px;
            height: {UIDims.DELEGATE_CHECKBOX_SIZE}px;
        }}
        QGroupBox {{
            background-color: {S.BG_SURFACE_ALT};
            border: 1px solid {S.BORDER_DEFAULT};
            border-radius: 8px;
            margin-top: 0px;
            padding: 48px 12px 12px 12px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            left: 16px; top: 12px; padding: 0 4px;
            color: {S.GRAY_900}; font-size: 24px; font-weight: bold;
        }}
        QGroupBox#compactPanel {{ padding: 8px; }}
        QSplitter::handle {{ background-color: transparent; margin: 0 4px; }}
        QSplitter::handle:horizontal:hover {{ background-color: {S.BORDER_DEFAULT}; border-radius: 2px; }}
        QTabWidget::pane {{ border: none; background-color: transparent; }}
        QTabBar::tab {{
            background: transparent; color: {S.TEXT_SECONDARY};
            padding: 12px 24px; border: none; font-size: 24px; font-weight: bold;
            border-bottom: 3px solid transparent; margin-right: 8px;
        }}
        QTabBar::tab:hover {{ color: {S.TEXT_PRIMARY}; background: {S.BG_HOVER}; border-radius: 6px 6px 0 0; }}
        QTabBar::tab:selected {{ color: {S.PRIMARY_BG}; border-bottom: 3px solid {S.PRIMARY_BG}; }}
        QScrollArea {{ border: none; background-color: transparent; }}
        QScrollArea::viewport {{ background-color: transparent; }}
        QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
        QScrollBar:vertical {{ border: none; background: transparent; width: 10px; margin: 0px; }}
        QScrollBar::handle:vertical {{ background: {S.BORDER_DEFAULT}; min-height: 20px; border-radius: 5px; margin: 2px; }}
        QScrollBar::handle:vertical:hover {{ background: {S.TEXT_SECONDARY}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        QScrollBar:horizontal {{ border: none; background: transparent; height: 10px; margin: 0px; }}
        QScrollBar::handle:horizontal {{ background: {S.BORDER_DEFAULT}; min-width: 20px; border-radius: 5px; margin: 2px; }}
        QScrollBar::handle:horizontal:hover {{ background: {S.TEXT_SECONDARY}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
    """

    # SpinBox / ComboBox 全局样式
    APP_SPINBOX = f"""
        QSpinBox, QDoubleSpinBox, QComboBox {{
            padding: 4px 26px 4px 8px; min-height: 28px;
            border: 1px solid {S.BORDER_DEFAULT}; border-radius: 4px;
            background: {S.BG_SURFACE}; color: {S.TEXT_PRIMARY};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: border; subcontrol-position: top right;
            width: 24px; border-left: 1px solid {S.BORDER_DEFAULT};
            background: {S.BG_SURFACE_ALT};
            border-top-right-radius: 3px; border-bottom-right-radius: 3px;
            margin-top: 1px; margin-right: 1px; margin-bottom: 1px;
        }}
        QComboBox::drop-down:hover {{ background: {S.BG_HOVER}; }}
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border; width: 24px; border-left: 1px solid {S.BORDER_DEFAULT};
            background: {S.BG_SURFACE_ALT};
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {S.BG_HOVER}; }}
        QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
        QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{ background: {S.BORDER_DEFAULT}; }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-position: top right; border-top-right-radius: 3px; border-bottom: 1px solid {S.BORDER_DEFAULT};
            margin-top: 1px; margin-right: 1px;
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-position: bottom right; border-bottom-right-radius: 3px;
            margin-bottom: 1px; margin-right: 1px;
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: none; width: 0px; height: 0px;
            border-left: 5px solid rgba(255, 255, 255, 0); border-right: 5px solid rgba(255, 255, 255, 0);
            border-bottom: 5px solid {S.TEXT_SECONDARY}; margin-bottom: 1px;
        }}
        QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{ border-bottom-color: {S.TEXT_PRIMARY}; }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QComboBox::down-arrow {{
            image: none; width: 0px; height: 0px;
            border-left: 5px solid rgba(255, 255, 255, 0); border-right: 5px solid rgba(255, 255, 255, 0);
            border-top: 5px solid {S.TEXT_SECONDARY}; margin-top: 1px;
        }}
        QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover, QComboBox::down-arrow:hover {{ border-top-color: {S.TEXT_PRIMARY}; }}
        QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{ border-bottom-color: {S.BORDER_DEFAULT}; }}
        QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled, QComboBox::down-arrow:disabled {{ border-top-color: {S.BORDER_DEFAULT}; }}
        QComboBox QAbstractItemView {{
            background-color: {S.BG_SURFACE};
            border: 1px solid {S.BORDER_DEFAULT};
            border-radius: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 28px;
            padding-left: 8px;
            color: {S.TEXT_PRIMARY};
        }}
        QComboBox QAbstractItemView::item:hover,
        QComboBox QAbstractItemView::item:selected {{
            background-color: {S.PRIMARY_LIGHT_BG};
            color: {S.PRIMARY_PRESSED};
        }}
    """

    # ──────────── 列表控件 ────────────

    # 透明无边框列表
    LIST_WIDGET_BASE = (
        "QListWidget { background-color: transparent; border: none; outline: none; } "
        "QListWidget::viewport { background-color: transparent; }"
    )

    # 任务编排列表（带边框圆角）
    TIMELINE_BASE = f"""
        QListWidget {{
            background-color: {S.BG_SURFACE}; border: 1px solid {S.BORDER_DEFAULT};
            border-radius: 6px; outline: none;
        }}
        QListWidget::viewport {{ background-color: transparent; }}
    """

    # ──────────── 文本标签样式 ────────────

    LBL_EDITOR_TITLE = _text_factory(S.TEXT_PRIMARY, "20px", "bold")               # 编辑器标题
    LBL_EDITOR_TITLE_DRAFT = _text_factory(S.WARNING_BG, "20px", "bold")           # 编辑器标题（草稿态）
    RECORDER_TITLE = _text_factory(S.PRIMARY_PRESSED, "26px", "bold")              # 录制窗口标题
    RECORDER_DISPLAY_ACTIVE = _text_factory(S.DANGER_BG, "26px", "bold")           # 录制中显示
    LBL_EDITOR_MID_TITLE = _text_factory(S.TEXT_PRIMARY, "24px", "bold")           # 编辑器中间标题
    LBL_CTRL_TITLE = _text_factory(S.TEXT_PRIMARY, "24px", "bold")                 # 控制区标题
    LBL_SETTINGS_SECTION_TITLE = _text_factory(                                    # 设置页分区标题
        S.PRIMARY_PRESSED, "20px", "bold", "margin-bottom: 12px;"
    )
    LBL_SETTINGS_FIXED_TITLE = _text_factory(                                      # 设置页固定标题
        S.TEXT_PRIMARY, "20px", "bold", "margin-bottom: 12px;"
    )
    LBL_BRIEF_TITLE = _text_factory(S.PRIMARY_PRESSED, "20px", "bold", "border: none;")  # 简要信息标题
    RECORDER_DISPLAY = _text_factory(S.TEXT_PRIMARY, "16px", "normal", "margin: 12px;")  # 录制显示文字

    # ──────────── 执行 / 停止按钮 ────────────

    _EXEC_BTN = "padding: 6px; font-weight: bold; border-radius: 8px; font-size: 28px;"
    BTN_RUN = _btn_factory(S.SUCCESS_BG, S.SUCCESS_TEXT, S.SUCCESS_PRESSED, S.SUCCESS_HOVER, _EXEC_BTN)   # 运行
    BTN_STOP = _btn_factory(S.DANGER_BG, S.DANGER_TEXT, S.DANGER_PRESSED, S.DANGER_HOVER, _EXEC_BTN)     # 停止

    # ──────────── 主操作按钮 ────────────

    _MAIN_BTN = "padding: 12px; font-weight: bold; border-radius: 6px; font-size: 15px;"
    BTN_PRIMARY = _btn_factory(S.PRIMARY_BG, S.PRIMARY_TEXT, S.PRIMARY_PRESSED, S.PRIMARY_HOVER, _MAIN_BTN)
    BTN_CREATE_TASK = _btn_factory(
        S.PRIMARY_BG, S.PRIMARY_TEXT, S.PRIMARY_PRESSED, S.PRIMARY_HOVER,
        "font-size: 15px; font-weight: bold; border-radius: 6px; padding: 10px;",
    )

    # ──────────── 通用操作按钮 ────────────

    _BASE_BTN = "padding: 2px 12px; border-radius: 4px; font-size: 22px; font-weight: bold;"
    _LARGE_ACTION_BTN = "padding: 10px 16px; border-radius: 6px; font-size: 16px; font-weight: bold;"

    # 日志区按钮
    BTN_LOG_BLUE = _btn_factory(
        S.PRIMARY_LIGHT_BG, S.PRIMARY_LIGHT_TEXT, S.PRIMARY_LIGHT_BORDER, S.PRIMARY_HOVER, _LARGE_ACTION_BTN
    )
    BTN_LOG_RED = _btn_factory(
        S.DANGER_LIGHT_BG, S.DANGER_LIGHT_TEXT, S.DANGER_LIGHT_BORDER, S.DANGER_HOVER, _LARGE_ACTION_BTN
    )

    # 保存按钮（正常态 / 脏数据态）
    BTN_SAVE_NORMAL = _btn_factory(
        S.BG_SURFACE_ALT, S.TEXT_SECONDARY, S.BORDER_DEFAULT, S.BG_HOVER,
        "font-weight: bold; border-radius: 6px; padding: 8px 16px; font-size: 24px;",
    )
    BTN_SAVE_DIRTY = _btn_factory(
        S.WARNING_BG, S.WARNING_TEXT, S.WARNING_PRESSED, S.WARNING_HOVER,
        "font-weight: bold; border-radius: 6px; padding: 8px 16px; font-size: 24px;",
    )

    # 删除按钮
    BTN_DELETE_DANGER = (
        _btn_factory(
            S.DANGER_LIGHT_BG, S.DANGER_LIGHT_TEXT, S.DANGER_LIGHT_BORDER, S.DANGER_HOVER,
            "font-weight: bold; border-radius: 6px; padding: 8px 16px; font-size: 24px;",
        )
        + f"QPushButton:disabled {{ background-color: {S.BG_SURFACE_ALT}; color: {S.TEXT_DISABLED}; "
          f"border: 1px solid {S.BORDER_DEFAULT}; }}"
    )

    # 彩色操作按钮组
    BTN_ACTION_BLUE = _btn_factory(
        S.PRIMARY_LIGHT_BG, S.PRIMARY_LIGHT_TEXT, S.PRIMARY_LIGHT_BORDER, S.PRIMARY_HOVER, _BASE_BTN
    )
    BTN_ACTION_RED = _btn_factory(
        S.DANGER_LIGHT_BG, S.DANGER_LIGHT_TEXT, S.DANGER_LIGHT_BORDER, S.DANGER_HOVER, _BASE_BTN
    )
    BTN_ACTION_GREEN = _btn_factory(
        S.SUCCESS_LIGHT_BG, S.SUCCESS_LIGHT_TEXT, S.SUCCESS_LIGHT_BORDER, S.SUCCESS_HOVER, _BASE_BTN
    )
    BTN_ACTION_ORANGE = _btn_factory(
        S.WARNING_LIGHT_BG, S.WARNING_LIGHT_TEXT, S.WARNING_LIGHT_BORDER, S.WARNING_HOVER, _BASE_BTN
    )
    BTN_ACTION_PURPLE = _btn_factory(
        S.AUX_LIGHT_BG, S.AUX_LIGHT_TEXT, S.AUX_LIGHT_BORDER, S.AUX_HOVER, _BASE_BTN
    )
    BTN_ACTION_DEEP_PURPLE = _btn_factory(
        S.AUX_LIGHT_BG, S.AUX_PRESSED, S.AUX_LIGHT_BORDER, S.AUX_HOVER, _BASE_BTN
    )

    # ──────────── 特殊用途按钮 ────────────

    # OSD 调整按钮
    BTN_OSD_ADJUST = _btn_factory(
        S.SUCCESS_LIGHT_BG, S.SUCCESS_PRESSED, S.SUCCESS_BG, S.SUCCESS_HOVER,
        "padding: 6px; font-size: 20px; font-weight: bold; border-radius: 6px; "
        "margin-left: 20px; max-width: 220px;",
    )
    # 重置按钮
    BTN_RESET_DANGER = _btn_factory(
        "transparent", S.DANGER_BG, S.DANGER_BG, S.DANGER_LIGHT_BG,
        "border-radius: 6px; padding: 8px; font-size: 14px;",
    )
    # 设置页录制按钮
    BTN_SETTINGS_RECORD = _btn_factory(
        S.SUCCESS_LIGHT_BG, S.SUCCESS_PRESSED, S.SUCCESS_LIGHT_BORDER, S.SUCCESS_HOVER,
        "border-radius: 4px; font-size: 20px; padding: 4px 16px;",
    )
    # 角落工具按钮
    BTN_CORNER_TOOL = _btn_factory(
        S.PRIMARY_LIGHT_BG, S.PRIMARY_PRESSED, S.PRIMARY_LIGHT_BORDER, S.PRIMARY_HOVER,
        "padding: 6px 18px; border-radius: 6px; font-weight: bold; font-size: 24px; "
        "margin-bottom: 4px; margin-top: 4px;",
    )

    # 全选 / 取消全选按钮
    BTN_SELECT_ALL = _btn_factory(
        S.PRIMARY_LIGHT_BG, S.PRIMARY_PRESSED, S.PRIMARY_LIGHT_BORDER, S.PRIMARY_HOVER,
        "border-radius: 4px; font-size: 13px;",
    )
    BTN_UNSELECT_ALL = _btn_factory(
        S.BG_SURFACE_ALT, S.TEXT_SECONDARY, S.BORDER_DEFAULT, S.BG_HOVER,
        "border-radius: 4px; font-size: 13px;",
    )

    # ──────────── 输入框样式 ────────────

    READONLY_INPUT = _input_factory(S.BG_SURFACE_ALT, S.TEXT_SECONDARY, S.BORDER_DEFAULT, "font-size: 14px;")

    SETTINGS_KEY_INPUT_READONLY = (
        f"QLineEdit {{ background-color: transparent; color: {S.TEXT_PRIMARY}; "
        f"border: none; font-size: 20px; font-weight: bold; }}"
    )
    SETTINGS_KEY_INPUT_EDITABLE = _input_factory(
        S.BG_SURFACE, S.TEXT_PRIMARY, S.BORDER_DEFAULT, "font-size: 20px; padding: 2px 8px;"
    )

    INPUT_MANAGE_NAME = (
        f"font-size: 14px; padding: 8px; border: 1px solid {S.BORDER_DEFAULT}; border-radius: 6px;"
    )

    # ──────────── 标签 / 提示文本样式 ────────────

    LBL_SETTINGS_CHECKBOX = f"font-size: 20px; font-weight: normal; color: {S.TEXT_PRIMARY};"
    LBL_SETTINGS_HINT = _text_factory(S.TEXT_SECONDARY, "20px", "normal", "margin-left: 24px;")
    LBL_DISABLED = _text_factory(S.TEXT_DISABLED, "20px", "normal", "font-style: italic; margin: 12px;")
    LBL_BRIEF_DETAIL = _text_factory(S.TEXT_SECONDARY, "14px", "normal", "border: none;")
    LBL_INFO_ERROR = _text_factory(S.DANGER_BG, "14px", "bold")
    LBL_INFO_SUCCESS = _text_factory(S.SUCCESS_PRESSED, "14px", "bold")
    LBL_INFO_GRAY = _text_factory(S.TEXT_SECONDARY, "14px", "normal", "padding: 12px;")
    LBL_HINT_ITALIC = _text_factory(S.TEXT_SECONDARY, "13px", "normal", "font-style: italic; padding: 8px 4px;")
    RECORDER_HINT = _text_factory(S.TEXT_SECONDARY, "13px")
    LBL_HISTORY_ACTIVE = _text_factory(S.TEXT_PRIMARY, "13px")
    LBL_HISTORY_INACTIVE = _text_factory(S.TEXT_DISABLED, "13px")

    # ──────────── 面板 / 容器样式 ────────────

    # 简要信息卡片
    PANEL_BRIEF_FRAME = f"""
        QFrame {{ background-color: {S.BG_HOVER}; border: 1px solid {S.BORDER_DEFAULT}; border-radius: 8px; }}
    """

    # 日志区
    PANEL_LOG_AREA = f"""
        QTextEdit {{ background-color: {S.BG_CODE}; color: {S.TEXT_CODE};
        font-family: Consolas, 'Courier New', monospace; font-size: 14px;
        line-height: 1.5; border: 1px solid {S.BORDER_CODE}; border-radius: 8px; padding: 12px; }}
        QTextEdit::viewport {{ background-color: transparent; }}
    """

    # 只读展示区
    PANEL_READONLY_DISPLAY = f"""
        QTextEdit {{ background-color: {S.BG_SURFACE_ALT}; color: {S.TEXT_PRIMARY};
        font-family: Consolas, 'Courier New', monospace; font-size: 14px;
        border: 1px solid {S.BORDER_DEFAULT}; border-radius: 6px; padding: 10px; }}
        QTextEdit::viewport {{ background-color: transparent; }}
    """

    # README 编辑器
    README_EDITOR = f"""
        QPlainTextEdit {{ background-color: {S.BG_SURFACE}; color: {S.TEXT_PRIMARY};
        font-family: Consolas, 'Courier New', monospace; font-size: 14px;
        border: 1px solid {S.BORDER_DEFAULT}; border-radius: 6px; padding: 10px; }}
        QPlainTextEdit::viewport {{ background-color: transparent; }}
    """

    # 各功能区 GroupBox 面板
    PANEL_EXEC = _groupbox_factory(_EXEC_BG, _EXEC_BD, _EXEC_TT, inner_bg=S.BG_SURFACE_ALT)     # 执行区
    PANEL_MANAGE = _groupbox_factory(_MANAGE_BG, _MANAGE_BD, _MANAGE_TT, inner_bg=S.BG_SURFACE)  # 管理区
    PANEL_EDITOR = _groupbox_factory(_EDITOR_BG, _EDITOR_BD, _EDITOR_TT, inner_bg=S.BG_SURFACE)  # 编辑区

    # 编辑器右侧标签页
    PANEL_EDITOR_RIGHT_TABS = f"""
        QTabWidget::pane {{
            background-color: transparent; border: none;
        }}
        QTabBar::tab {{
            background: transparent; color: {S.TEXT_SECONDARY}; padding: 8px 16px;
            border: none; font-size: 20px; font-weight: bold; margin-right: 4px;
            border-bottom: 3px solid transparent;
        }}
        QTabBar::tab:hover {{
            color: {S.TEXT_PRIMARY}; background: {S.BG_HOVER}; border-radius: 6px 6px 0 0;
        }}
        QTabBar::tab:selected {{
            color: {S.PRIMARY_BG}; background: transparent;
            border-bottom: 3px solid {S.PRIMARY_BG};
        }}
    """

    # 设置页各分区面板
    PANEL_CONFIG = _groupbox_factory(_CONFIG_BG, _CONFIG_BD, _CONFIG_TT, inner_bg=S.BG_SURFACE)          # 配置区
    PANEL_SETTINGS_LOG = _groupbox_factory(                                                               # 日志设置
        S.WARNING_LIGHT_BG, S.WARNING_LIGHT_BORDER, S.WARNING_DARK_TEXT, inner_bg=S.BG_SURFACE
    )
    PANEL_SETTINGS_HW = _groupbox_factory(                                                                # 硬件设置
        S.SUCCESS_LIGHT_BG, S.SUCCESS_LIGHT_BORDER, S.SUCCESS_DARK_TEXT, inner_bg=S.BG_SURFACE
    )
    PANEL_SETTINGS_KEY = _groupbox_factory(                                                               # 快捷键设置
        S.PRIMARY_LIGHT_BG, S.PRIMARY_LIGHT_BORDER, S.PRIMARY_DARK_TEXT, inner_bg=S.BG_SURFACE
    )

    # 垂直分割线颜色
    SEPARATOR_VLINE = f"color: {S.BORDER_DEFAULT};"

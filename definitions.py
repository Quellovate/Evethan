# definitions.py
# 全局定义文件：应用默认设置、动作工厂配置、参数翻译、按键别名等

# ============================================================
# 应用默认设置
# ============================================================
DEFAULT_APP_SETTINGS = {
    "use_hardware": False,  # 是否使用硬件级输入
    "detailed_log": False,  # 是否启用详细日志
    "last_exec_task": "",  # 上一次所选的任务名称
    "osd_visible": False,  # OSD 启用状态
    "osd_font_size": 24,  # OSD 字体大小
    "osd_center_x": 960,  # OSD 水平中心位置
    "osd_center_y": 100,  # OSD 垂直中心位置
    "shortcuts": {  # 全局快捷键
        "run_task": "f8",
        "stop_task": "f9",
        "toggle_osd": "f10",
        "save_task": "ctrl+s",
        "move_up": "w",
        "move_down": "s",
    },
}

# ============================================================
# 动作工厂配置（每种动作的元信息与默认参数）
# 格式：参数名 -> (类型, 默认值)

# traits 特征:
# "start"      : 结构起点
# "end"        : 结构终点
# "branch"     : 结构分支
# "fold"       : 可折叠
# "key_record" : 按键录制
# "flow"       : 流程控制
# "separator"  : 分割线
#
# ui_bg 背景色:
# "normal"     : 普通操作：白色
# "loop"       : 循环：橙色
# "group"      : 分组：绿色
# "if"         : 条件判断：蓝色
# "hold"       : 鼠标/键盘长按：紫色
# "flow"       : 跳转/中断：红色
# "subtask"    : 子任务：青色
# "separator"  : 分割线：紫色
# ============================================================
FACTORY_CONFIG = {
    # ---- 鼠标移动 / 滚轮 ----
    "mouse_move": {
        "label": "🖱️ 鼠标移动",
        "desc": "将鼠标移动到指定坐标",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "x": (int, 0),
            "y": (int, 0),
            "random_range": (int, 5),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "camera_turn": {
        "label": "🔄 视角转动",
        "desc": "用于 3D 游戏的视角旋转",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "drag_dx": (int, 200),
            "drag_dy": (int, 0),
            "random_range": (int, 10),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "scroll": {
        "label": "🖱️ 滚轮滚动",
        "desc": "滚动鼠标滚轮（正数向上, 负数向下）",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "scroll_amount": (int, -100),
            "random_range": (int, 10),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    # ---- 点击（固定坐标 / 相对偏移 / 识图） ----
    "fixed_click": {
        "label": "👆 固定坐标点击",
        "desc": "将鼠标移动到指定坐标后点击",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "x": (int, 0),
            "y": (int, 0),
            "button": (str, "left"),
            "random_range": (int, 5),
            "repeat": (int, 1),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "offset_click": {
        "label": "👆 相对偏移点击",
        "desc": "相对于当前鼠标位置偏移后点击",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "off_x": (int, 0),
            "off_y": (int, 0),
            "button": (str, "left"),
            "random_range": (int, 5),
            "repeat": (int, 1),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "image_click": {
        "label": "👆 识图点击",
        "desc": "成功识别图片后点击（默认点击图片中心）",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "image_path": (str, "target.png"),
            "region": (list, [0, 0, 0, 0]),
            "confidence": (float, 0.7),
            "off_x": (int, 0),
            "off_y": (int, 0),
            "button": (str, "left"),
            "random_range": (int, 5),
            "repeat": (int, 1),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
            "env_w": (int, 0),  # 截图时的参考分辨率宽
            "env_h": (int, 0),  # 截图时的参考分辨率高
        },
    },
    # ---- 长按（固定坐标 / 相对偏移 / 识图） ----
    "fixed_long_press": {
        "label": "⏱️ 固定坐标长按",
        "desc": "将鼠标移动到指定坐标后长按",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "x": (int, 0),
            "y": (int, 0),
            "button": (str, "left"),
            "random_range": (int, 5),
            "duration_s": (float, 3.0),
            "repeat": (int, 1),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "offset_long_press": {
        "label": "⏱️ 相对偏移长按",
        "desc": "相对于当前鼠标位置偏移后长按",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "off_x": (int, 0),
            "off_y": (int, 0),
            "button": (str, "left"),
            "random_range": (int, 5),
            "duration_s": (float, 3.0),
            "repeat": (int, 1),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "image_long_press": {
        "label": "⏱️ 识图长按",
        "desc": "成功识别图片后长按（默认长按图片中心）",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "image_path": (str, "target.png"),
            "region": (list, [0, 0, 0, 0]),
            "confidence": (float, 0.7),
            "off_x": (int, 0),
            "off_y": (int, 0),
            "button": (str, "left"),
            "random_range": (int, 5),
            "duration_s": (float, 3.0),
            "repeat": (int, 1),
            "move_enable": (bool, True),
            "move_time_min": (int, 200),
            "move_time_max": (int, 800),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
            "env_w": (int, 0),
            "env_h": (int, 0),
        },
    },
    # ---- 拖拽（坐标拖拽 / 识图拖拽） ----
    "mouse_drag": {
        "label": "✋ 鼠标拖拽",
        "desc": "将鼠标从指定起点按住拖拽到指定终点",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "x1": (int, 0),
            "y1": (int, 0),
            "x2": (int, 100),
            "y2": (int, 100),
            "move_time_min": (int, 500),
            "move_time_max": (int, 1500),
            "button": (str, "left"),
            "random_range": (int, 5),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "image_drag": {
        "label": "✋ 识图拖拽",
        "desc": "成功识别图片后相对拖拽指定距离",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "image_path": (str, "target.png"),
            "region": (list, [0, 0, 0, 0]),
            "confidence": (float, 0.7),
            "off_x": (int, 0),
            "off_y": (int, 0),
            "drag_dx": (int, 200),
            "drag_dy": (int, 0),
            "move_time_min": (int, 500),
            "move_time_max": (int, 1500),
            "button": (str, "left"),
            "random_range": (int, 5),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
            "env_w": (int, 0),
            "env_h": (int, 0),
        },
    },
    # ---- 键盘操作 ----
    "key_press": {
        "label": "⌨️ 键盘按键",
        "desc": "敲击键盘按键",
        "traits": ["key_record"],
        "ui_bg": "normal",
        "params": {
            "key_code": (str, "space"),
            "repeat": (int, 1),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    "key_long_press": {
        "label": "⌨️ 键盘长按",
        "desc": "长按键盘按键",
        "traits": ["key_record"],
        "ui_bg": "normal",
        "params": {
            "key_code": (str, "w"),
            "duration_s": (float, 1.5),
            "repeat": (int, 1),
            "interval_min": (int, 80),
            "interval_max": (int, 160),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
        },
    },
    # ---- 状态控制：按下与抬起 ----
    "mouse_hold_start": {
        "label": "🖱️ 鼠标按下 (开始)",
        "desc": "按下鼠标按键并保持，直到遇到结束节点",
        "traits": ["start"],
        "ui_bg": "hold",
        "params": {"button": (str, "left"), "link_id": (str, ""), "wait_min": (int, 50), "wait_max": (int, 200)},
    },
    "mouse_hold_end": {
        "label": "🖱️ 鼠标抬起 (结束)",
        "desc": "释放前面按住的鼠标按键",
        "traits": ["end"],
        "ui_bg": "hold",
        "params": {"link_id": (str, "")},
    },
    "key_hold_start": {
        "label": "⌨️ 键盘按下 (开始)",
        "desc": "按下键盘按键并保持，支持修饰键",
        "traits": ["start", "key_record"],
        "ui_bg": "hold",
        "params": {"key_code": (str, "shift"), "link_id": (str, ""), "wait_min": (int, 50), "wait_max": (int, 200)},
    },
    "key_hold_end": {
        "label": "⌨️ 键盘抬起 (结束)",
        "desc": "释放前面按住的键盘按键",
        "traits": ["end"],
        "ui_bg": "hold",
        "params": {"link_id": (str, "")},
    },
    # ---- 等待 / 找图 ----
    "wait": {
        "label": "⏳ 延时等待",
        "desc": "任务暂停等待一段时间",
        "traits": [],
        "ui_bg": "normal",
        "params": {"time_s": (float, 2.0), "random_add_s": (float, 0.5)},
    },
    "find_image": {
        "label": "🔍 寻找图片",
        "desc": "循环找图直到成功识别，再执行下一步",
        "traits": [],
        "ui_bg": "normal",
        "params": {
            "image_path": (str, "check.png"),
            "region": (list, [0, 0, 0, 0]),
            "confidence": (float, 0.7),
            "wait_min": (int, 50),
            "wait_max": (int, 200),
            "env_w": (int, 0),
            "env_h": (int, 0),
        },
    },
    # ---- 流程控制 ----
    "break_loop": {
        "label": "🛑 跳出循环",
        "desc": "强制退出当前所在的循环层（只跳一层）",
        "traits": ["flow"],
        "ui_bg": "flow",
        "params": {},
    },
    "stop_task": {
        "label": "🛑 停止任务",
        "desc": "强制终止整个任务，不再运行",
        "traits": ["flow"],
        "ui_bg": "flow",
        "params": {},
    },
    "loop_start": {
        "label": "🔁 For 循环开始",
        "desc": "设定循环次数",
        "traits": ["start", "fold"],
        "ui_bg": "loop",
        "params": {"count": (int, 5), "link_id": (str, ""), "collapsed": (bool, False)},  # link_id 用于配对循环结束
    },
    "loop_end": {
        "label": "🔁 循环结束",
        "desc": "循环回跳点",
        "traits": ["end"],
        "ui_bg": "loop",
        "params": {"link_id": (str, "")},
    },
    "if_start": {
        "label": "🔀 判断:若识图成功",
        "desc": "限时循环找图，成功则执行下方指令，失败则跳过或执行Else",
        "traits": ["start", "fold"],
        "ui_bg": "if",
        "params": {
            "image_path": (str, "cond.png"),
            "region": (list, [0, 0, 0, 0]),
            "confidence": (float, 0.7),
            "timeout": (float, 5),
            "link_id": (str, ""),
            "env_w": (int, 0),
            "env_h": (int, 0),
            "collapsed": (bool, False),
        },
    },
    "if_end": {
        "label": "🔀 判断结束",
        "desc": "逻辑分支结束点",
        "traits": ["end"],
        "ui_bg": "if",
        "params": {"link_id": (str, "")},
    },
    "else_branch": {
        "label": "🔀 否则 (Else)",
        "desc": "当判断条件不满足时执行此处的指令",
        "traits": ["branch"],
        "ui_bg": "if",
        "params": {"link_id": (str, "")},
    },
    "anchor": {
        "label": "📌 锚点",
        "desc": "设置可供跳转的锚点位置",
        "traits": [],
        "ui_bg": "flow",
        "params": {"anchor_id": (str, ""), "wait_min": (int, 50), "wait_max": (int, 100)},
    },
    "jump": {
        "label": "🚀 跳转至锚点",
        "desc": "跳转到指定的锚点位置",
        "traits": [],
        "ui_bg": "flow",
        "params": {"target_id": (str, "")},
    },
    # ---- 分组 / 分割线 ----
    "group_start": {
        "label": "📂 任务分组",
        "desc": "折叠管理过长任务 (点击 + 号展开)",
        "traits": ["start", "fold"],
        "ui_bg": "group",
        "params": {"label": (str, "新分组"), "link_id": (str, ""), "collapsed": (bool, False)},
    },
    "group_end": {
        "label": "📂 分组结束",
        "desc": "分组结束点",
        "traits": ["end"],
        "ui_bg": "group",
        "params": {"link_id": (str, "")},
    },
    "separator": {
        "label": "➖ —— 分割线 ——",
        "desc": "纯视觉分割",
        "traits": ["separator"],
        "ui_bg": "separator",
        "params": {"label": (str, "—— 分割线 ——")},
    },
    # ---- 子任务 ----
    "call_subtask": {
        "label": "📦 调用子任务",
        "desc": "将另一个任务作为子任务在此处执行",
        "traits": [],
        "ui_bg": "subtask",
        "params": {"task_id": (str, ""), "task_name": (str, "")},
    },
}

# ============================================================
# 参数名 -> 中文显示名（ UI 展示）
# ============================================================
PARAM_TRANSLATIONS = {
    "x": "X 坐标",
    "y": "Y 坐标",
    "x1": "起点 X 坐标",
    "y1": "起点 Y 坐标",
    "x2": "终点 X 坐标",
    "y2": "终点 Y 坐标",
    "off_x": "X 轴偏移量",
    "off_y": "Y 轴偏移量",
    "image_path": "图片文件名",
    "confidence": "匹配相似度",
    "region": "识别区域 [x,y,w,h]",
    "random_range": "随机偏差范围 (像素)",
    "repeat": "重复次数",
    "move_enable": "启用拟人移动",
    "move_time_min": "移动最小耗时 (ms)",
    "move_time_max": "移动最大耗时 (ms)",
    "interval_min": "点击/按键最小间隔 (ms)",
    "interval_max": "点击/按键最大间隔 (ms)",
    "wait_min": "操作后最小等待 (ms)",
    "wait_max": "操作后最大等待 (ms)",
    "duration_s": "持续时长 (秒)",
    "scroll_amount": "滚动量 (+上/-下)",
    "drag_dx": "拖拽水平距离",
    "drag_dy": "拖拽垂直距离",
    "button": "鼠标按键类型 (左/中/右)",
    "key_code": "按键代码 (如ctrl+c)",
    "time_s": "基础等待时长 (秒)",
    "random_add_s": "额外随机时长 (秒)",
    "count": "循环次数",
    "timeout": "超时时间 (秒)",
    "label": "分组名称",
    "collapsed": "默认折叠状态",
    "anchor_id": "当前锚点 ID",
    "target_id": "目标锚点 ID",
    "task_id": "子任务 ID",
    "task_name": "子任务名称",
}

# ============================================================
# 按键名称别名映射（统一不同写法到标准键名）
# ============================================================
KEY_NAME_ALIAS = {
    "control": "ctrl",
    "ctl": "ctrl",
    "escape": "esc",
    "return": "enter",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "spacebar": "space",
    "command": "win",
    "windows": "win",
    "option": "alt",
    "semicolon": ";",
    "colon": ":",
    "plus": "+",
    "minus": "-",
    "underscore": "_",
    "equal": "=",
    "question": "?",
    "slash": "/",
    "backslash": "\\",
    "pipe": "|",
    "quote": "'",
    "doublequote": '"',
    "apostrophe": "'",
    "grave": "`",
    "backtick": "`",
    "tilde": "~",
    "comma": ",",
    "period": ".",
    "dot": ".",
    "leftbracket": "[",
    "rightbracket": "]",
    "leftbrace": "{",
    "rightbrace": "}",
    "exclaim": "!",
    "bang": "!",
    "at": "@",
    "hash": "#",
    "dollar": "$",
    "percent": "%",
    "caret": "^",
    "amp": "&",
    "asterisk": "*",
}

# ============================================================
# 需要 Shift 组合才能输入的特殊字符映射
# 键 -> [修饰键, 基础键]
# ============================================================
SHIFT_CHAR_MAP = {
    "!": ["shift", "1"],
    "@": ["shift", "2"],
    "#": ["shift", "3"],
    "$": ["shift", "4"],
    "%": ["shift", "5"],
    "^": ["shift", "6"],
    "&": ["shift", "7"],
    "*": ["shift", "8"],
    "(": ["shift", "9"],
    ")": ["shift", "0"],
    "_": ["shift", "-"],
    "+": ["shift", "="],
    "{": ["shift", "["],
    "}": ["shift", "]"],
    "|": ["shift", "\\"],
    ":": ["shift", ";"],
    '"': ["shift", "'"],
    "<": ["shift", ","],
    ">": ["shift", "."],
    "?": ["shift", "/"],
    "~": ["shift", "`"],
}

# ============================================================
# 配对结构在 UI 中的显示名覆盖（用于标题栏等场景）
# ============================================================
DISPLAY_NAME_OVERRIDE = {
    "loop_start": "🔁 For 循环模块",
    "group_start": "📂 分组模块",
    "if_start": "🔀 识图判断模块 (If)",
    "else_branch": "🔀 否则 (Else)",
    "mouse_hold_start": "🖱️ 鼠标按下&抬起",
    "key_hold_start": "⌨️ 键盘按下&抬起",
    "call_subtask": "📦 调用子任务",
}

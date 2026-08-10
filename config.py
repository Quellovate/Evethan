# config.py
# 全局配置管理器与任务工程文件 (JSON) 读写管理。

import copy
import json
import os
import sys
import uuid
from definitions import FACTORY_CONFIG, DEFAULT_APP_SETTINGS


class GlobalConfigManager:
    """全局配置管理器：负责指令参数配置和应用设置的读取、保存、重置"""

    USER_SETTINGS_FILE = "user_settings.json"

    def __init__(self):
        # 根据是否打包确定基础路径
        if getattr(sys, "frozen", False):
            _base = os.path.dirname(sys.executable)
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        self.USER_SETTINGS_FILE = os.path.join(_base, "user_settings.json")
        # 用工厂默认值初始化当前配置和应用设置
        self._current_config = copy.deepcopy(FACTORY_CONFIG)
        self._app_settings = copy.deepcopy(DEFAULT_APP_SETTINGS)
        self.load_user_settings()

    @staticmethod
    def _coerce_value(type_cls, value):
        """强制类型转换，转换失败则原样返回"""
        try:
            if type_cls is bool:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            if type_cls is int:
                return int(value)
            if type_cls is float:
                return float(value)
            if type_cls is str or type_cls == "str":
                return str(value)
            if type_cls is list:
                if isinstance(value, list):
                    return value
                if isinstance(value, str):
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, list) else [parsed]
                return list(value)
            return value
        except (ValueError, TypeError, json.JSONDecodeError):
            return value

    def get_config(self):
        """返回当前完整配置字典"""
        return self._current_config

    def get_cmd_def(self, cmd_type):
        """获取指定指令类型的定义"""
        return self._current_config.get(cmd_type)

    def get_app_setting(self, key, default=None):
        """获取某项应用设置"""
        return self._app_settings.get(key, default)

    def get_shortcuts(self):
        """获取快捷键映射表"""
        return self._app_settings.get("shortcuts", DEFAULT_APP_SETTINGS["shortcuts"])

    def set_app_setting(self, key, value):
        """设置一项应用设置并保存到文件"""
        self._app_settings[key] = value
        self._save_app_settings_to_file()

    def set_shortcut(self, action_name, key_str):
        """设置某个动作的快捷键并保存"""
        if "shortcuts" not in self._app_settings:
            self._app_settings["shortcuts"] = copy.deepcopy(DEFAULT_APP_SETTINGS["shortcuts"])
        self._app_settings["shortcuts"][action_name] = key_str
        self._save_app_settings_to_file()

    def save_user_setting(self, cmd_type, param_key, value):
        """保存用户对某条指令某个参数的修改（同时更新内存和文件）"""
        if cmd_type not in self._current_config:
            print(f"save_user_setting 跳过: 未知指令类型 '{cmd_type}'")
            return
        if param_key not in self._current_config[cmd_type]["params"]:
            print(f"save_user_setting 跳过: 指令 '{cmd_type}' 无参数 '{param_key}'")
            return

        type_cls, _ = self._current_config[cmd_type]["params"][param_key]
        coerced_value = self._coerce_value(type_cls, value)
        # 更新内存中的配置
        self._current_config[cmd_type]["params"][param_key] = (type_cls, coerced_value)

        # 更新持久化文件
        current_file_data = self._read_file()
        if "cmds" not in current_file_data:
            current_file_data["cmds"] = {}
        if cmd_type not in current_file_data["cmds"]:
            current_file_data["cmds"][cmd_type] = {"params": {}}
        current_file_data["cmds"][cmd_type]["params"][param_key] = coerced_value
        self._write_json(current_file_data)

    def load_user_settings(self):
        """从 user_settings.json 加载用户配置，覆盖到当前内存配置上"""
        if not os.path.exists(self.USER_SETTINGS_FILE):
            return
        try:
            with open(self.USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            # 加载指令参数覆盖
            if "cmds" in user_data:
                for cmd, cmd_data in user_data["cmds"].items():
                    if cmd in self._current_config and "params" in cmd_data:
                        for param_key, param_val in cmd_data["params"].items():
                            if param_key in self._current_config[cmd]["params"]:
                                type_cls, _ = self._current_config[cmd]["params"][param_key]
                                coerced_val = self._coerce_value(type_cls, param_val)
                                self._current_config[cmd]["params"][param_key] = (type_cls, coerced_val)

            # 加载应用设置覆盖
            if "app_settings" in user_data:
                for k, v in user_data["app_settings"].items():
                    if k == "shortcuts" and isinstance(v, dict):
                        for sk, sv in v.items():
                            self._app_settings["shortcuts"][sk] = sv
                    else:
                        self._app_settings[k] = v
        except Exception as e:
            print(f"加载用户配置失败: {e}")

    def reset_to_factory(self, cmd_type=None):
        """恢复出厂设置，重置指定 cmd_type 指令"""
        if cmd_type:
            if cmd_type in FACTORY_CONFIG:
                self._current_config[cmd_type] = copy.deepcopy(FACTORY_CONFIG[cmd_type])
                self._remove_cmd_setting_from_file(cmd_type)
        else:
            self._current_config = copy.deepcopy(FACTORY_CONFIG)
            self._app_settings = copy.deepcopy(DEFAULT_APP_SETTINGS)
            if os.path.exists(self.USER_SETTINGS_FILE):
                os.remove(self.USER_SETTINGS_FILE)

    def _read_file(self):
        """读取用户配置文件，失败时返回空字典"""
        if not os.path.exists(self.USER_SETTINGS_FILE):
            return {}
        try:
            with open(self.USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_json(self, data):
        """将数据写入用户配置文件"""
        try:
            with open(self.USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存失败: {e}")

    def _save_app_settings_to_file(self):
        """将当前应用设置写入文件"""
        current_file_data = self._read_file()
        current_file_data["app_settings"] = self._app_settings
        self._write_json(current_file_data)

    def _remove_cmd_setting_from_file(self, cmd_type):
        """从文件中删除某条指令的用户覆盖"""
        if not os.path.exists(self.USER_SETTINGS_FILE):
            return
        try:
            with open(self.USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "cmds" in data and cmd_type in data["cmds"]:
                del data["cmds"][cmd_type]
                self._write_json(data)
        except Exception:
            pass


class TaskManager:
    """任务管理器：管理 tasks 目录下的任务文件夹，包括脚本具体操作内容和说明文件"""

    DRAFT_TASK_NAME = "草稿任务"

    def __init__(self):
        # 确定基础路径
        if getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.tasks_dir = os.path.join(self.base_dir, "tasks")
        self._ensure_root()

        self.task_id_map = {}
        self.task_name_map = {}
        self._build_index()

    def _build_index(self):
        """扫描 tasks 目录，建立任务 ID 映射"""
        self.task_id_map.clear()
        self.task_name_map.clear()
        if not os.path.exists(self.tasks_dir):
            return

        for task_name in os.listdir(self.tasks_dir):
            task_path = os.path.join(self.tasks_dir, task_name)
            if not os.path.isdir(task_path):
                continue

            script_path = os.path.join(task_path, "script.json")
            task_id = None
            steps = []
            need_save = False

            if os.path.exists(script_path):
                try:
                    with open(script_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, list):
                        # 旧版无 task_id ，则自动赋值
                        steps = data
                        task_id = str(uuid.uuid4())
                        need_save = True
                    elif isinstance(data, dict):
                        # 读取 task_id
                        task_id = data.get("task_id")
                        steps = data.get("steps", [])
                        if not task_id:
                            task_id = str(uuid.uuid4())
                            need_save = True
                except:
                    task_id = str(uuid.uuid4())
                    need_save = True
            else:
                task_id = str(uuid.uuid4())
                need_save = True

            self.task_id_map[task_id] = task_name
            self.task_name_map[task_name] = task_id

            # 如果是旧数据，覆写为新格式
            if need_save:
                try:
                    with open(script_path, "w", encoding="utf-8") as f:
                        json.dump({"task_id": task_id, "steps": steps}, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"任务 {task_name} 格式更新失败: {e}")

    def _ensure_root(self):
        """确保 tasks 根目录存在"""
        if not os.path.exists(self.tasks_dir):
            os.makedirs(self.tasks_dir)

    # ── 查询任务 ──
    def get_all_tasks(self):
        """获取所有任务名（即 tasks 目录下的子文件夹名）"""
        if not os.path.exists(self.tasks_dir):
            return []
        return [d for d in os.listdir(self.tasks_dir) if os.path.isdir(os.path.join(self.tasks_dir, d))]

    def get_display_tasks(self):
        """获取用于显示的任务列表（排除草稿任务）"""
        tasks = self.get_all_tasks()
        if self.DRAFT_TASK_NAME in tasks:
            tasks.remove(self.DRAFT_TASK_NAME)
        return tasks

    def get_task_path(self, task_name):
        """返回指定任务的文件夹路径"""
        return os.path.join(self.tasks_dir, task_name)

    def _is_name_exists_case_insensitive(self, target_name):
        """不区分大小写地检查任务名是否已存在"""
        if not os.path.exists(self.tasks_dir):
            return False
        existing_tasks = [
            d.lower() for d in os.listdir(self.tasks_dir) if os.path.isdir(os.path.join(self.tasks_dir, d))
        ]
        return target_name.lower() in existing_tasks

    # 创建 / 重命名 / 删除
    def create_task(self, task_name):
        """创建新任务：建文件夹、空脚本、默认说明"""
        path = os.path.join(self.tasks_dir, task_name)
        if os.path.exists(path):
            return False, "该任务名称已存在"
        try:
            os.makedirs(path)
            new_id = str(uuid.uuid4())
            self.task_name_map[task_name] = new_id
            self.task_id_map[new_id] = task_name

            self.save_script(task_name, [])
            self.save_task_info(task_name, "在此处编写任务说明...")
            return True, path
        except Exception as e:
            return False, str(e)

    def rename_task(self, old_name, new_name):
        """重命名任务文件夹，支持仅改大小写的情况"""
        if old_name == new_name:
            return True, "成功"
        is_case_change_only = old_name.lower() == new_name.lower()
        if not is_case_change_only and self._is_name_exists_case_insensitive(new_name):
            return False, "该任务名称已存在"
        old_path = os.path.join(self.tasks_dir, old_name)
        new_path = os.path.join(self.tasks_dir, new_name)
        try:
            os.rename(old_path, new_path)
            task_id = self.task_name_map.pop(old_name, None)
            if task_id:
                self.task_name_map[new_name] = task_id
                self.task_id_map[task_id] = new_name
            return True, "成功"
        except Exception as e:
            return False, str(e)

    def delete_task(self, task_name):
        """删除指定任务及其所有文件"""
        if task_name == self.DRAFT_TASK_NAME:
            return False, "草稿任务不可删除"
        path = os.path.join(self.tasks_dir, task_name)
        if not os.path.exists(path):
            return False, "该任务不存在"
        try:
            import shutil

            shutil.rmtree(path)
            task_id = self.task_name_map.pop(task_name, None)
            if task_id:
                self.task_id_map.pop(task_id, None)
            return True, "成功"
        except Exception as e:
            return False, str(e)

    # 草稿任务
    def ensure_draft_task(self):
        """确保草稿任务存在，不存在则创建"""
        path = os.path.join(self.tasks_dir, self.DRAFT_TASK_NAME)
        if not os.path.exists(path):
            self.create_task(self.DRAFT_TASK_NAME)

    def reset_draft_task(self):
        """重置草稿任务：清空脚本、说明，并删除图片文件"""
        self.save_script(self.DRAFT_TASK_NAME, [])
        self.save_task_info(self.DRAFT_TASK_NAME, "在此处编写任务说明...")
        draft_path = self.get_task_path(self.DRAFT_TASK_NAME)
        for f in os.listdir(draft_path):
            if f.endswith(".png") or f.endswith(".jpg"):
                try:
                    os.remove(os.path.join(draft_path, f))
                except:
                    pass

    def publish_draft_task(self, new_name):
        """将草稿任务发布为正式任务（重命名后重建草稿）"""
        draft_path = os.path.join(self.tasks_dir, self.DRAFT_TASK_NAME)
        new_path = os.path.join(self.tasks_dir, new_name)
        if os.path.exists(new_path):
            return False, "该任务名称已存在"
        try:
            os.rename(draft_path, new_path)
            draft_id = self.task_name_map.pop(self.DRAFT_TASK_NAME, None)
            if draft_id:
                self.task_name_map[new_name] = draft_id
                self.task_id_map[draft_id] = new_name
            self.create_task(self.DRAFT_TASK_NAME)
            return True, "成功"
        except Exception as e:
            return False, str(e)

    # 脚本与说明文件读写
    def save_script(self, task_name, script_data):
        """保存任务脚本（JSON）"""
        path = os.path.join(self.tasks_dir, task_name, "script.json")
        task_id = self.task_name_map.get(task_name)
        if not task_id:
            task_id = str(uuid.uuid4())
            self.task_name_map[task_name] = task_id
            self.task_id_map[task_id] = task_name

        save_obj = {"task_id": task_id, "steps": script_data}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(save_obj, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Save Script Error: {e}")
            return False

    def load_script(self, task_name):
        """加载任务脚本，仅返回 steps 列表"""
        path = os.path.join(self.tasks_dir, task_name, "script.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data.get("steps", [])
            elif isinstance(data, list):
                return data
            return []
        except:
            return []

    def save_task_info(self, task_name, content):
        """保存任务说明文本"""
        path = os.path.join(self.tasks_dir, task_name, "readme.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Save Readme Error: {e}")
            return False

    def load_task_info(self, task_name):
        """加载任务说明文本，不存在则返回空串"""
        path = os.path.join(self.tasks_dir, task_name, "readme.txt")
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return ""


global_config = GlobalConfigManager()

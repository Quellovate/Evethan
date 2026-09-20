# scheduler.py
# 脚本调度器：负责解析脚本指令列表，按顺序执行指令，处理循环、条件分支、中断等控制流

import time
import os
from executor import ScriptExecutor, ExecutionEvent
from utils import ScriptParser


class TaskScheduler:
    """脚本任务调度器，管理脚本的多轮执行、循环/分支控制流、超时检测等"""

    def __init__(self, task_manager=None):
        self.task_manager = task_manager
        self.executor = ScriptExecutor()
        self.is_running = False
        self.call_stack = []  # 调用栈，用于子任务嵌套
        self.ctx = None  # 当前执行上下文
        self.event_listener = None

        self._handlers = {
            "call_subtask": self._handle_call_subtask,
            "loop_start": self._handle_loop_start,
            "loop_end": self._handle_loop_end,
            "if_image_start": self._handle_if_start,
            "if_color_start": self._handle_if_start,
            "else_branch": self._handle_else_branch,
            "if_end": self._handle_if_end,
            "jump": self._handle_jump,
            "break_loop": self._handle_break_loop,
            "stop_task": self._handle_stop_task,
        }

    # ──────────────────────────────────────────────
    #  事件与状态
    # ──────────────────────────────────────────────

    def set_event_listener(self, callback):
        """设置事件回调，同时传递给底层执行器"""
        self.event_listener = callback
        self.executor.set_event_listener(callback)

    def _emit(self, event_type, message, data=None):
        """发送事件通知，自动附带当前循环层级上下文"""
        if data is None:
            data = {}
        data["loop_context"] = self.get_loop_chain_str()
        if hasattr(self, "event_listener") and self.event_listener:
            self.event_listener(event_type, message, data)

    def stop(self):
        """外部调用：发出停止指令"""
        self.is_running = False
        if hasattr(self.executor, "cleanup_all_holds"):
            self.executor.cleanup_all_holds()
        self._emit(ExecutionEvent.INFO, "收到停止指令，正在终止...")

    # ──────────────────────────────────────────────
    #  循环栈辅助
    # ──────────────────────────────────────────────

    def get_loop_chain_str(self):
        """将当前循环嵌套栈格式化为可读字符串，如 "外层循环(1/3) > 内层循环(2/5)" """
        parts = []
        # 遍历调用栈
        for frame in self.call_stack:
            parts.append(f"[{frame['task_name']}]")
            for item in frame["loop_stack"]:
                parts.append(f"{item['label']}({item['current']}/{item['total']})")

        # 加上当前上下文
        if self.ctx:
            if self.call_stack:  # 如果在子任务中，显示当前子任务名
                parts.append(f"[{self.ctx['task_name']}]")
            for item in self.ctx["loop_stack"]:
                parts.append(f"{item['label']}({item['current']}/{item['total']})")

        return " > ".join(parts)

    def _update_loop_stack_on_break(self, link_id):
        """break 时从循环栈中移除对应循环"""
        if self.ctx and self.ctx["loop_stack"] and self.ctx["loop_stack"][-1]["id"] == link_id:
            self.ctx["loop_stack"].pop()
        elif self.ctx:
            self.ctx["loop_stack"] = [x for x in self.ctx["loop_stack"] if x["id"] != link_id]

    # ──────────────────────────────────────────────
    #  控制流处理方法
    # ──────────────────────────────────────────────

    #  所有 handler 统一签名：handler(cmd_type, params, step_desc) -> bool
    #  返回值：
    #  True  = 当前指令处理完成，主循环（轮次）继续执行
    #  False = 立即退出当前执行循环（轮次）

    def _handle_call_subtask(self, cmd_type, params, step_desc):
        """子任务调用"""
        sub_id = params.get("task_id")
        sub_name_fallback = params.get("task_name", "未知子任务")

        # 深度限制
        if len(self.call_stack) >= 10:
            self._emit(ExecutionEvent.ERROR, "调用栈溢出：检测到过深的子任务嵌套或死循环，即将停止！")
            self.is_running = False
            return False

        if not self.task_manager:
            self._emit(ExecutionEvent.ERROR, "无法解析子任务")
            self.ctx["index"] += 1
            return True

        # 寻址
        actual_name = self.task_manager.task_id_map.get(sub_id)
        if not actual_name:
            self._emit(ExecutionEvent.ERROR, f"调用失败：找不到子任务[{sub_name_fallback}]")
            self.ctx["index"] += 1
            return True

        sub_script = self.task_manager.load_script(actual_name)
        sub_dir = self.task_manager.get_task_path(actual_name)
        sub_errors, sub_jump_table = ScriptParser.parse(sub_script)

        if sub_errors:
            self._emit(
                ExecutionEvent.WARNING,
                f"警告：子任务 [{actual_name}] 存在 {len(sub_errors)} 处结构错误，可能会导致运行异常！",
            )
        self._emit(ExecutionEvent.INFO, f"进入子任务: {actual_name}")

        # 上下文先移动到下一条指令，再压栈
        self.ctx["index"] += 1
        self.call_stack.append(self.ctx)
        self.ctx = {
            "task_name": actual_name,
            "task_dir": sub_dir,
            "task_list": sub_script,
            "index": 0,
            "loop_counters": {},
            "loop_stack": [],
            "jump_table": sub_jump_table,
        }
        return True

    def _handle_loop_start(self, cmd_type, params, step_desc):
        """循环开始"""
        link_id = params.get("link_id")
        count = params.get("count", 1)

        # 首次进入该循环时初始化计数器和循环显示栈
        if link_id not in self.ctx["loop_counters"]:
            self.ctx["loop_counters"][link_id] = 0
            label = "循环" if step_desc == "For 循环开始" else step_desc
            self.ctx["loop_stack"].append({"id": link_id, "label": label, "current": 1, "total": count})

        runtime_params = params.copy()
        runtime_params["current_loop_index"] = self.ctx["loop_counters"][link_id]
        self.executor.exec_loop_start(**runtime_params)
        self.ctx["index"] += 1
        return True

    def _handle_loop_end(self, cmd_type, params, step_desc):
        """循环结束：决定回跳或离开循环"""
        link_id = params.get("link_id")
        start_index = self.ctx["jump_table"].get(self.ctx["index"], {}).get("start")
        if start_index is None:
            self.ctx["index"] += 1
            return True

        target_count = self.ctx["task_list"][start_index].get("params", {}).get("count", 1)
        if link_id not in self.ctx["loop_counters"]:
            self.ctx["loop_counters"][link_id] = 0
        self.ctx["loop_counters"][link_id] += 1

        # 未达目标次数 -> 跳回循环体开头
        if self.ctx["loop_counters"][link_id] < target_count:
            for item in reversed(self.ctx["loop_stack"]):
                if item["id"] == link_id:
                    item["current"] = self.ctx["loop_counters"][link_id] + 1
                    break
            self._emit(ExecutionEvent.DEBUG, f"循环回跳: {self.ctx['loop_counters'][link_id]}/{target_count}")
            self.ctx["index"] = start_index + 1

        #  已达目标次数 -> 循环结束，清理
        else:
            self._emit(ExecutionEvent.DEBUG, f"循环完成: {link_id}")
            del self.ctx["loop_counters"][link_id]
            if self.ctx["loop_stack"] and self.ctx["loop_stack"][-1]["id"] == link_id:
                self.ctx["loop_stack"].pop()
            self.ctx["index"] += 1
        return True

    def _handle_if_start(self, cmd_type, params, step_desc):
        """条件判断开始"""
        func_name = f"exec_{cmd_type}"
        func = getattr(self.executor, func_name, None)

        if callable(func):
            condition_met = func(**params)
        else:
            self._emit(ExecutionEvent.ERROR, f"未知判断指令: {cmd_type}")
            self.ctx["index"] += 1
            return True

        if condition_met:  # 条件成立：顺序进入 if 体
            self.ctx["index"] += 1
        else:  # 跳转到 Else 或 End
            targets = self.ctx["jump_table"].get(self.ctx["index"], {})
            target_index = targets.get("else", targets.get("end"))
            if target_index is not None:
                if targets.get("else") is not None:
                    self._emit(ExecutionEvent.DEBUG, f"条件不成立，跳转到 Else 分支 (行 {target_index + 1})")
                else:
                    self._emit(ExecutionEvent.DEBUG, f"条件不成立，跳过 If 模块 (行 {target_index + 1})")
                self.ctx["index"] = target_index + 1
            else:
                self._emit(ExecutionEvent.ERROR, "结构错误：找不到 if_end")
                self.ctx["index"] += 1
        return True

    def _handle_else_branch(self, cmd_type, params, step_desc):
        """Else 分支：若能顺序执行到 Else 节点，说明 If 条件成立，直接跳过 Else 分支"""
        target_end = self.ctx["jump_table"].get(self.ctx["index"], {}).get("end")
        if target_end is not None:
            self.ctx["index"] = target_end + 1
        else:
            self._emit(ExecutionEvent.ERROR, "结构错误：Else 后找不到 if_end")
            self.ctx["index"] += 1
        return True

    def _handle_if_end(self, cmd_type, params, step_desc):
        """条件判断结束"""
        self.executor.exec_if_end(**params)
        self.ctx["index"] += 1
        return True

    def _handle_jump(self, cmd_type, params, step_desc):
        """锚点跳转"""
        target_raw = params.get("target_id", "")
        target = target_raw.split()[0] if target_raw else ""
        self.executor.exec_jump(target)

        # 查表找目标锚点
        target_index = self.ctx["jump_table"].get(self.ctx["index"], {}).get("target")
        if target_index is not None:
            self._emit(ExecutionEvent.INFO, f"跳转成功，前往第 {target_index + 1} 行")
            self.ctx["index"] = target_index
        else:
            self._emit(ExecutionEvent.WARNING, f"跳转失败：未找到目标 '{target}'")
            self.ctx["index"] += 1
        return True

    def _handle_break_loop(self, cmd_type, params, step_desc):
        """跳出循环：只跳出最内层"""
        self.executor.exec_break()
        # 查表找外层 loop_end
        target_end = self.ctx["jump_table"].get(self.ctx["index"], {}).get("end")
        if target_end is not None:
            end_step_data = self.ctx["task_list"][target_end]
            link_id = end_step_data.get("params", {}).get("link_id")
            if link_id in self.ctx["loop_counters"]:
                del self.ctx["loop_counters"][link_id]
            self._update_loop_stack_on_break(link_id)
            self._emit(ExecutionEvent.DEBUG, f"跳出循环 (跳转至行 {target_end + 1})")
            self.ctx["index"] = target_end + 1
        else:
            self._emit(ExecutionEvent.WARNING, "当前不在循环内，无法跳出")
            self.ctx["index"] += 1
        return True

    def _handle_stop_task(self, cmd_type, params, step_desc):
        """停止任务"""
        self.executor.exec_stop_task()
        self.is_running = False
        return False

    def _handle_normal_cmd(self, cmd_type, params, step_desc):
        """执行普通指令"""
        func_name = f"exec_{cmd_type}"
        func = getattr(self.executor, func_name, None)
        if callable(func):
            try:
                func(**params)
                if not self.is_running:
                    return False
            except Exception as e:
                self._emit(ExecutionEvent.ERROR, f"执行异常: {e}")
                self.is_running = False
                return False
        else:
            self._emit(ExecutionEvent.WARNING, f"未知指令类型: {cmd_type}")
        self.ctx["index"] += 1
        return True

    # ──────────────────────────────────────────────
    #  主执行入口
    # ──────────────────────────────────────────────

    def run_script(self, task_list, task_name, task_dir, run_times=1, timeout_sec=36000):
        """
        执行脚本主循环
        :param task_list: 指令列表
        :param run_times: 总轮数
        :param timeout_sec: 单轮超时秒数，<=0 表示不限时
        """
        # 打印启动信息
        if timeout_sec > 0:
            self._emit(
                ExecutionEvent.INFO,
                f"脚本开始执行，共 {len(task_list)} 个指令，计划执行 {run_times} 轮，单轮超时设为 {timeout_sec}s",
            )
        else:
            self._emit(
                ExecutionEvent.INFO, f"脚本开始执行，共 {len(task_list)} 个指令，计划执行 {run_times} 轮 (无超时限制)"
            )
        self.is_running = True

        # 停止检查函数：同时检测手动停止和超时
        def combined_stop_check():
            if not self.is_running:
                return False
            if hasattr(self, "current_round_deadline") and time.time() > self.current_round_deadline:
                return False
            return True

        self.executor.set_stop_check(combined_stop_check)
        if hasattr(self.executor, "set_context_provider"):
            self.executor.set_context_provider(self.get_loop_chain_str)

        current_round = 0

        try:
            errors, jump_table = ScriptParser.parse(task_list)
            if errors:
                self._emit(ExecutionEvent.WARNING, f"警告：脚本存在 {len(errors)} 处结构错误，可能会导致运行异常！")
            # ── 外层：多轮循环 ──
            while self.is_running and current_round < run_times:
                current_round += 1
                # 设置本轮截止时间
                self.current_round_deadline = (time.time() + timeout_sec) if timeout_sec > 0 else float("inf")
                self._emit(ExecutionEvent.INFO, f"=== 开始第 {current_round}/{run_times} 轮 ===")

                # 初始化根上下文
                self.call_stack = []
                self.ctx = {
                    "task_name": task_name,
                    "task_dir": task_dir,
                    "task_list": task_list,
                    "index": 0,
                    "loop_counters": {},
                    "loop_stack": [],
                    "jump_table": jump_table,
                }

                # ── 内层：逐步执行 ──
                while True:
                    # 检查是否被手动停止
                    if not self.is_running:
                        self._emit(ExecutionEvent.WARNING, "任务被用户强行中止")
                        break
                    # 检查单轮超时
                    if time.time() > self.current_round_deadline:
                        self._emit(ExecutionEvent.WARNING, f"🚨 触发超时重置 (超过 {timeout_sec} 秒)，中断当前轮次...")
                        break

                    # 检查当前任务/子任务是否执行到底部
                    if self.ctx["index"] >= len(self.ctx["task_list"]):
                        if not self.call_stack:  # 根任务执行完毕
                            break
                        else:
                            # 子任务执行完毕：退栈返回上一层
                            self._emit(ExecutionEvent.INFO, f"⤴️ 子任务 [{self.ctx['task_name']}] 执行完毕，返回上一层")
                            self.ctx = self.call_stack.pop()
                            continue

                    step_data = self.ctx["task_list"][self.ctx["index"]]
                    cmd_type = step_data.get("type")
                    params = step_data.get("params", {}).copy()
                    step_desc = step_data.get("desc", cmd_type)

                    display_desc = f"[{current_round}/{run_times}] {self.ctx['index'] + 1}. {step_desc}"
                    if hasattr(self.executor, "set_current_step_desc"):
                        self.executor.set_current_step_desc(display_desc)

                    # 动态解析图片的绝对路径
                    if "image_path" in params and params["image_path"]:
                        if not os.path.isabs(params["image_path"]):
                            params["image_path"] = os.path.join(self.ctx["task_dir"], params["image_path"])

                    # 分发执行任务指令
                    handler = self._handlers.get(cmd_type, self._handle_normal_cmd)
                    if not handler(cmd_type, params, step_desc):
                        break

                # 本轮结束后的收尾
                if self.is_running:
                    if time.time() <= getattr(self, "current_round_deadline", float("inf")):
                        self._emit(ExecutionEvent.INFO, f"第 {current_round} 轮执行完成")
                    if current_round < run_times:
                        time.sleep(0.5)

        except KeyboardInterrupt:
            self._emit(ExecutionEvent.WARNING, "脚本被键盘中断")
        except Exception as e:
            self._emit(ExecutionEvent.ERROR, f"调度器发生严重错误: {e}")
        finally:
            self.is_running = False
            self.call_stack = []
            self.ctx = None
            # 无论任务是因为完成、报错还是手动中止，都强制复位所有硬件/软件级的按键残留
            if hasattr(self.executor, "cleanup_all_holds"):
                try:
                    self.executor.cleanup_all_holds()
                except Exception as cleanup_err:
                    print(f"清理外设状态时发生异常: {cleanup_err}")
            self._emit(ExecutionEvent.INFO, "脚本运行结束")

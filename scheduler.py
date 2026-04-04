# scheduler.py
# 脚本调度器：负责解析脚本步骤列表，按顺序执行指令，处理循环、条件分支、中断等控制流

import time
import threading
from executor import ScriptExecutor, ExecutionEvent


class TaskScheduler:
    """脚本任务调度器，管理脚本的多轮执行、循环/分支控制流、超时检测等"""

    def __init__(self):
        self.executor = ScriptExecutor()
        self.is_running = False
        self.loop_stack = []  # 循环嵌套栈，用于显示当前循环层级信息
        # 指令类型 -> 执行函数的映射表
        self.function_map = {
            "mouse_move": self.executor.exec_mouse_move,
            "camera_turn": self.executor.exec_camera_turn,
            "fixed_click": self.executor.exec_fixed_click,
            "offset_click": self.executor.exec_offset_click,
            "image_click": self.executor.exec_image_click,
            "mouse_drag": self.executor.exec_mouse_drag,
            "image_drag": self.executor.exec_image_drag,
            "fixed_long_press": self.executor.exec_fixed_long_press,
            "offset_long_press": self.executor.exec_offset_long_press,
            "image_long_press": self.executor.exec_image_long_press,
            "key_press": self.executor.exec_key_press,
            "key_long_press": self.executor.exec_key_long_press,
            "scroll": self.executor.exec_scroll,
            "wait": self.executor.exec_wait,
            "find_image": self.executor.exec_find_image,
            "loop_start": self.executor.exec_loop_start,
            "loop_end": self.executor.exec_loop_end,
            "group_start": self.executor.exec_group_start,
            "group_end": self.executor.exec_group_end,
            "separator": self.executor.exec_separator,
            "if_start": self.executor.exec_if_start,
            "else_branch": self.executor.exec_else_branch,
            "if_end": self.executor.exec_if_end,
            "break_loop": self.executor.exec_break,
            "stop_task": self.executor.exec_stop_task,
            "mouse_hold_start": self.executor.exec_mouse_hold_start,
            "mouse_hold_end": self.executor.exec_mouse_hold_end,
            "key_hold_start": self.executor.exec_key_hold_start,
            "key_hold_end": self.executor.exec_key_hold_end,
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
        if not self.loop_stack:
            return ""
        parts = []
        for item in self.loop_stack:
            parts.append(f"{item['label']}({item['current']}/{item['total']})")
        return " > ".join(parts)

    def _update_loop_stack_on_break(self, link_id):
        """break 时从循环栈中移除对应循环"""
        if self.loop_stack and self.loop_stack[-1]["id"] == link_id:
            self.loop_stack.pop()
        else:
            self.loop_stack = [x for x in self.loop_stack if x["id"] != link_id]

    # ──────────────────────────────────────────────
    #  步骤索引查找（用于控制流跳转）
    # ──────────────────────────────────────────────

    def _find_loop_start_index(self, task_list, link_id):
        """根据 link_id 查找对应的 loop_start 步骤索引"""
        for i, step in enumerate(task_list):
            if step.get("type") == "loop_start" and step.get("params", {}).get("link_id") == link_id:
                return i
        return None

    def _find_target_node(self, task_list, start_index, target_type, link_id):
        """从 start_index 之后查找指定类型和 link_id 的步骤索引（用于 if/else/if_end 跳转）"""
        for i in range(start_index + 1, len(task_list)):
            step = task_list[i]
            if step.get("type") == target_type and step.get("params", {}).get("link_id") == link_id:
                return i
            # 查找 else_branch 时若先遇到 if_end，说明没有 else 分支
            if (
                target_type == "else_branch"
                and step.get("type") == "if_end"
                and step.get("params", {}).get("link_id") == link_id
            ):
                return None
        return None

    def _find_enclosing_loop_end(self, task_list, current_index):
        """从当前位置向后查找最近一层包裹的 loop_end（考虑嵌套深度）"""
        depth = 0
        for i in range(current_index + 1, len(task_list)):
            t_type = task_list[i].get("type")
            if t_type == "loop_start":
                depth += 1
            elif t_type == "loop_end":
                if depth == 0:
                    return i
                depth -= 1
        return None

    # ──────────────────────────────────────────────
    #  主执行入口
    # ──────────────────────────────────────────────

    def run_script(self, task_list, run_times=1, timeout_sec=3600):
        """
        执行脚本主循环
        :param task_list: 步骤列表
        :param run_times: 总轮数
        :param timeout_sec: 单轮超时秒数，<=0 表示不限时
        """
        # 打印启动信息
        if timeout_sec > 0:
            self._emit(
                ExecutionEvent.INFO,
                f"脚本开始执行，共 {len(task_list)} 个步骤，计划执行 {run_times} 轮，单轮超时设为 {timeout_sec}s",
            )
        else:
            self._emit(
                ExecutionEvent.INFO, f"脚本开始执行，共 {len(task_list)} 个步骤，计划执行 {run_times} 轮 (无超时限制)"
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
            # ── 外层：多轮循环 ──
            while self.is_running and current_round < run_times:
                current_round += 1
                # 设置本轮截止时间
                self.current_round_deadline = (time.time() + timeout_sec) if timeout_sec > 0 else float("inf")
                self._emit(ExecutionEvent.INFO, f"=== 开始第 {current_round}/{run_times} 轮 ===")

                self.loop_stack = []
                loop_counters = {}  # link_id -> 已完成迭代次数
                index = 0
                total_steps = len(task_list)

                # ── 内层：逐步执行 ──
                while index < total_steps:
                    # 检查是否被手动停止
                    if not self.is_running:
                        self._emit(ExecutionEvent.WARNING, "任务被用户强行中止")
                        break
                    # 检查单轮超时
                    if time.time() > self.current_round_deadline:
                        self._emit(
                            ExecutionEvent.WARNING,
                            f"🚨 触发超时重置 (超过 {timeout_sec} 秒)，中断当前执行，准备重开...",
                        )
                        break

                    step_data = task_list[index]
                    cmd_type = step_data.get("type")
                    params = step_data.get("params", {})
                    step_desc = step_data.get("desc", cmd_type)
                    display_desc = f"[{current_round}/{run_times}] {index + 1}. {step_desc}"
                    if hasattr(self.executor, "set_current_step_desc"):
                        self.executor.set_current_step_desc(display_desc)

                    # ── 循环开始 ──
                    if cmd_type == "loop_start":
                        link_id = params.get("link_id")
                        count = params.get("count", 1)
                        # 首次进入时初始化计数器并压栈
                        if link_id not in loop_counters:
                            loop_counters[link_id] = 0
                            label = "循环" if step_desc == "For 循环开始" else step_desc
                            self.loop_stack.append({"id": link_id, "label": label, "current": 1, "total": count})
                        runtime_params = params.copy()
                        runtime_params["current_loop_index"] = loop_counters[link_id]
                        self.executor.exec_loop_start(**runtime_params)
                        index += 1

                    # ── 循环结束 ──
                    elif cmd_type == "loop_end":
                        link_id = params.get("link_id")
                        start_index = self._find_loop_start_index(task_list, link_id)
                        if start_index is None:
                            index += 1
                            continue
                        target_count = task_list[start_index].get("params", {}).get("count", 1)
                        if link_id not in loop_counters:
                            loop_counters[link_id] = 0
                        loop_counters[link_id] += 1
                        # 未达目标次数 -> 跳回循环体开头
                        if loop_counters[link_id] < target_count:
                            for item in reversed(self.loop_stack):
                                if item["id"] == link_id:
                                    item["current"] = loop_counters[link_id] + 1
                                    break
                            self._emit(
                                ExecutionEvent.DEBUG,
                                f"循环回跳: {loop_counters[link_id]}/{target_count}",
                                {"link_id": link_id},
                            )
                            index = start_index + 1
                        # 已达目标次数 -> 循环结束，清理
                        else:
                            self._emit(ExecutionEvent.DEBUG, f"循环完成: {link_id}", {"link_id": link_id})
                            del loop_counters[link_id]
                            if self.loop_stack and self.loop_stack[-1]["id"] == link_id:
                                self.loop_stack.pop()
                            index += 1

                    # ── 条件判断开始 ──
                    elif cmd_type == "if_start":
                        condition_met = self.executor.exec_if_start(**params)
                        if condition_met:
                            # 条件成立：顺序进入 if 体
                            index += 1
                        else:
                            link_id = params.get("link_id")
                            # 条件不成立：尝试跳到 else 分支
                            else_index = self._find_target_node(task_list, index, "else_branch", link_id)
                            if else_index is not None:
                                self._emit(ExecutionEvent.DEBUG, f"跳转到 Else 分支 (行 {else_index + 1})")
                                index = else_index + 1
                            else:
                                # 没有 else 分支则跳到 if_end
                                end_index = self._find_target_node(task_list, index, "if_end", link_id)
                                if end_index is not None:
                                    self._emit(ExecutionEvent.DEBUG, f"跳过 If 模块 (跳转至行 {end_index + 1})")
                                    index = end_index + 1
                                else:
                                    self._emit(ExecutionEvent.ERROR, "结构错误：找不到 if_end")
                                    index += 1

                    # ── Else 分支标记（从 if 体执行完毕到达此处，应跳过 else 体）──
                    elif cmd_type == "else_branch":
                        link_id = params.get("link_id")
                        end_index = self._find_target_node(task_list, index, "if_end", link_id)
                        if end_index is not None:
                            index = end_index + 1
                        else:
                            self._emit(ExecutionEvent.ERROR, "结构错误：Else 后找不到 if_end")
                            index += 1

                    # ── 跳出循环 (break) ──
                    elif cmd_type == "break_loop":
                        self.executor.exec_break()
                        loop_end_index = self._find_enclosing_loop_end(task_list, index)
                        if loop_end_index is not None:
                            end_step_data = task_list[loop_end_index]
                            link_id = end_step_data.get("params", {}).get("link_id")
                            if link_id in loop_counters:
                                del loop_counters[link_id]
                            self._update_loop_stack_on_break(link_id)
                            self._emit(ExecutionEvent.DEBUG, f"跳出循环 (跳转至行 {loop_end_index + 1})")
                            index = loop_end_index + 1
                        else:
                            self._emit(ExecutionEvent.WARNING, "当前不在循环内，无法跳出")
                            index += 1

                    # ── 停止任务 ──
                    elif cmd_type == "stop_task":
                        self.executor.exec_stop_task()
                        self.is_running = False
                        break

                    # ── 其余普通指令：查表执行 ──
                    else:
                        func = self.function_map.get(cmd_type)
                        if func:
                            try:
                                func(**params)
                                if not self.is_running:
                                    break
                            except Exception as e:
                                self._emit(ExecutionEvent.ERROR, f"执行异常: {e}")
                                import traceback

                                traceback.print_exc()
                                self.is_running = False
                                break
                        else:
                            self._emit(ExecutionEvent.WARNING, f"未知指令类型: {cmd_type}")
                        index += 1

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
            import traceback

            traceback.print_exc()
        finally:
            self.is_running = False
            self.loop_stack = []
            # 无论任务是因为完成、报错还是手动中止，都强制复位所有硬件/软件级的按键残留
            if hasattr(self.executor, "cleanup_all_holds"):
                try:
                    self.executor.cleanup_all_holds()
                except Exception as cleanup_err:
                    print(f"清理外设状态时发生异常: {cleanup_err}")
            self._emit(ExecutionEvent.INFO, "脚本运行结束")

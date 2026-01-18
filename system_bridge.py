"""
System Bridge Module
负责底层系统交互与自动化操作。
实现对目标应用程序的窗口控制与内容注入。
"""

import logging
import time
import sys
import io
import re
import asyncio
from typing import Any, Dict, Optional, List

import psutil
import pyautogui
import win32api
import win32con
import win32gui
import win32clipboard
import ctypes
from ctypes import windll

class SystemBridge:
    """系统桥接器：处理底层自动化指令。"""
    
    def __init__(self):
        self.logger = logging.getLogger("SystemBridge")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 调整标准输出编码
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding='utf-8')

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.3

        self.env_signature: Optional[str] = None
        self.is_compatible_env: bool = False
        self._last_interface_type: Optional[str] = None
        self._scan_environment_signature()

    def _scan_environment_signature(self) -> Optional[str]:
        """扫描运行环境特征（版本检测）。"""
        try:
            target_handle = self._locate_target_application()
            interface_match = self._last_interface_type == "modern" and target_handle is not None

            for process in psutil.process_iter(['name', 'exe']):
                proc_name = process.info.get('name') or ""
                if 'wechat' not in proc_name.lower():
                    continue

                exe_path = process.info.get('exe')
                if not exe_path:
                    continue

                try:
                    ver_info = win32api.GetFileVersionInfo(exe_path, "\\")
                    ver_str = f"{ver_info['FileVersionMS'] >> 16}.{ver_info['FileVersionMS'] & 0xFFFF}.{ver_info['FileVersionLS'] >> 16}.{ver_info['FileVersionLS'] & 0xFFFF}"
                    self.env_signature = ver_str
                    
                    major_ver = int(ver_str.split('.')[0])
                    self.is_compatible_env = interface_match or major_ver >= 4
                    
                    if self.is_compatible_env:
                        self.logger.info(f"Environment Signature Verified: {ver_str}")
                    else:
                        self.logger.info(f"Legacy Environment Detected: {ver_str}")
                    return ver_str
                except Exception:
                    continue

            self.logger.warning("Target process signature not found.")
            self.env_signature = None
            self.is_compatible_env = interface_match
            return None
        except Exception as e:
            self.logger.error(f"Signature scan failed: {e}")
            self.env_signature = None
            self.is_compatible_env = False
            return None

    def _locate_target_application(self) -> Optional[int]:
        """定位目标应用程序窗口句柄。"""
        modern_handles = []
        legacy_handles = []

        def enumeration_callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            cls_name = win32gui.GetClassName(hwnd)
            wnd_title = win32gui.GetWindowText(hwnd)

            if cls_name == "WeChatMainWndForPC":
                modern_handles.insert(0, hwnd)
                return True
            
            # 匹配现代UI框架特征
            modern_patterns = [r"ChatWnd", r"Qt\d+QWindowIcon"]
            for ptrn in modern_patterns:
                if re.match(ptrn, cls_name):
                    if "WeChat" in wnd_title or "微信" in wnd_title:
                        modern_handles.append(hwnd)
                        return True

            if "微信" in wnd_title or "WeChat" in wnd_title:
                legacy_handles.append(hwnd)
            return True

        win32gui.EnumWindows(enumeration_callback, None)
        if modern_handles:
            self._last_interface_type = "modern"
            return modern_handles[0]
        if legacy_handles:
            self._last_interface_type = "legacy"
            return legacy_handles[0]
        self._last_interface_type = None
        return None

    def _release_control_keys(self):
        """释放控制键状态。"""
        ctrl_keys = [0x10, 0x11, 0x12] # Shift, Ctrl, Alt
        for k in ctrl_keys:
            if ctypes.windll.user32.GetKeyState(k) & 0x8000:
                ctypes.windll.user32.keybd_event(k, 0, 0x0002, 0)

    def _focus_application_interface(self, handle_id: int) -> bool:
        """聚焦目标界面。"""
        try:
            self._release_control_keys()
            
            if win32gui.IsIconic(handle_id):
                win32gui.ShowWindow(handle_id, win32con.SW_RESTORE)
            
            try:
                win32gui.SetForegroundWindow(handle_id)
            except Exception:
                pass

            if win32gui.GetForegroundWindow() == handle_id:
                return True

            # 尝试强制输入挂载
            try:
                import win32process
                fg_hwnd = win32gui.GetForegroundWindow()
                if fg_hwnd != 0:
                    fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
                    curr_tid = windll.kernel32.GetCurrentThreadId()
                    
                    if fg_tid != curr_tid:
                        windll.user32.AttachThreadInput(curr_tid, fg_tid, True)
                        try:
                            win32gui.SetForegroundWindow(handle_id)
                            win32gui.SetFocus(handle_id)
                        except Exception:
                            pass
                        windll.user32.AttachThreadInput(curr_tid, fg_tid, False)
            except Exception as e:
                self.logger.error(f"Input attachment failed: {e}")

            for _ in range(10):
                if win32gui.GetForegroundWindow() == handle_id:
                    return True
                time.sleep(0.1)
                try:
                    win32gui.SetForegroundWindow(handle_id)
                except Exception:
                    pass
            
            if win32gui.GetForegroundWindow() != handle_id:
                self.logger.error("Focus acquisition failed.")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Focus operation error: {e}")
            return False

    def _locate_and_engage_input_field(self) -> bool:
        """定位并激活输入区域。"""
        try:
            handle_id = self._locate_target_application()
            if not handle_id:
                return False

            rect = win32gui.GetWindowRect(handle_id)
            x1, y1, x2, y2 = rect
            w = x2 - x1

            # 预设的点击坐标策略
            click_vectors = [
                (x1 + w // 2, y2 - 80),
                (x1 + w // 2, y2 - 120),
                (x1 + w // 3, y2 - 100),
                (x1 + w * 2 // 3, y2 - 100),
                (pyautogui.size()[0] // 2, int(pyautogui.size()[1] * 0.85)),
            ]

            for cx, cy in click_vectors:
                try:
                    pyautogui.click(int(cx), int(cy))
                    time.sleep(0.4)
                    # 测试输入焦点
                    pyautogui.typewrite('a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    return True
                except Exception:
                    continue

            return False
        except Exception as e:
            self.logger.error(f"Input field engagement error: {e}")
            return False

    def _inject_content_via_buffer(self, content: str) -> Optional[str]:
        """通过剪贴板缓冲区注入内容。"""
        previous_buffer: Optional[str] = None
        win32clipboard.OpenClipboard()
        try:
            try:
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                if isinstance(data, str):
                    previous_buffer = data
            except Exception:
                previous_buffer = None
        finally:
            win32clipboard.CloseClipboard()

        # 清除当前选中内容（如果有）
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.12)
        pyautogui.press('delete')
        time.sleep(0.25)

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(content, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

        time.sleep(0.25)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.6)
        return previous_buffer

    def _recover_buffer_state(self, preserved_data: Optional[str]) -> None:
        """恢复剪贴板缓冲区状态。"""
        if not preserved_data:
            return
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(preserved_data, win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            pass

    def _query_target_identifier(self, identifier: str) -> bool:
        """查询目标标识（联系人搜索）。"""
        handle_id = self._locate_target_application()
        if not handle_id or win32gui.GetForegroundWindow() != handle_id:
            return False

        backup_buffer: Optional[str] = None
        try:
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(1.0)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyautogui.press('delete')
            time.sleep(0.2)

            backup_buffer = self._inject_content_via_buffer(identifier)

            pyautogui.press('enter')
            time.sleep(1.0)

            return True
        except Exception as e:
            self.logger.error(f"Query failed: {e}")
            return False
        finally:
            self._recover_buffer_state(backup_buffer)

    def _execute_transmission_sequence(self, payload: str) -> bool:
        """执行传输序列（发送操作）。"""
        try:
            if not self._locate_and_engage_input_field():
                time.sleep(0.5)
                if not self._locate_and_engage_input_field():
                    return False

            backup_buffer = self._inject_content_via_buffer(payload)

            # 尝试多种发送快捷键
            triggers = [
                lambda: pyautogui.press('enter'),
                lambda: pyautogui.hotkey('ctrl', 'enter'),
                lambda: pyautogui.hotkey('alt', 's')
            ]

            for trigger in triggers:
                try:
                    trigger()
                    time.sleep(0.6)
                    try:
                        self._recover_buffer_state(backup_buffer)
                    except Exception:
                        pass
                    return True
                except Exception:
                    continue
            
            return False
        except Exception as e:
            self.logger.error(f"Transmission sequence error: {e}")
            return False

    async def dispatch_payload(self, target_identifier: str, payload_content: str) -> Dict[str, Any]:
        """调度并发送数据载荷。"""
        report: Dict[str, Any] = {
            "success_flag": False,
            "target": target_identifier,
            "env_signature": None,
            "is_compatible": False,
            "phase": None,
            "error_detail": None,
        }
        try:
            sig = self._scan_environment_signature()
            report["env_signature"] = sig
            report["is_compatible"] = self.is_compatible_env

            if not self.is_compatible_env:
                report["phase"] = "compatibility_check"
                report["error_detail"] = "incompatible_environment"
                return report

            h_id = self._locate_target_application()
            if not h_id:
                report["phase"] = "app_location"
                report["error_detail"] = "app_not_found"
                return report

            if not self._focus_application_interface(h_id):
                report["phase"] = "interface_focus"
                report["error_detail"] = "focus_failed"
                return report
                
            if not self._query_target_identifier(target_identifier):
                report["phase"] = "target_query"
                report["error_detail"] = "query_failed"
                return report

            if self._execute_transmission_sequence(payload_content):
                report["success_flag"] = True
                report["phase"] = "transmission"
                report["error_detail"] = None
                return report

            report["phase"] = "transmission"
            report["error_detail"] = "sequence_failed"
            return report

        except Exception as e:
            self.logger.error(f"Dispatch error: {e}")
            report["phase"] = report["phase"] or "unknown_exception"
            report["error_detail"] = str(e)
            return report


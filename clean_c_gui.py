import os
import shutil
import tempfile
import threading
import ctypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# ----------------- 工具函数 -----------------
def human_readable(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    num = float(size)
    idx = 0
    while num >= 1024 and idx < len(units) - 1:
        num /= 1024
        idx += 1
    return f"{num:.2f} {units[idx]}"

def safe_get_size(path: Path) -> int:
    total = 0
    try:
        if not path.exists():
            return 0
        if path.is_file():
            return path.stat().st_size
        for root, dirs, files in os.walk(path, topdown=True):
            for f in files:
                fp = Path(root) / f
                try:
                    total += fp.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total

def remove_child(child: Path) -> int:
    freed = 0
    try:
        if not child.exists():
            return 0
        freed = safe_get_size(child)
        if child.is_file():
            child.unlink(missing_ok=True)
        else:
            shutil.rmtree(child, ignore_errors=True)
    except Exception:
        pass
    return freed

def clear_directory_contents(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    freed = 0
    try:
        for child in path.iterdir():
            freed += remove_child(child)
    except Exception:
        pass
    return freed

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def empty_recycle_bin() -> bool:
    """
    清空回收站（Windows API）
    返回 True 表示调用成功（不代表一定有文件）
    """
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        # 0 通常表示成功
        return res == 0
    except Exception:
        return False

# ----------------- GUI 主程序 -----------------
class CleanerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C盘安全清理助手")
        self.geometry("760x520")
        self.minsize(700, 480)

        self.running = False
        self.targets = self.build_targets()

        self.create_widgets()
        self.refresh_status("准备就绪。建议先点击“扫描可清理空间”。")

    def build_targets(self):
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        windows_temp = Path(r"C:\Windows\Temp")
        temp_dir = Path(tempfile.gettempdir())

        return [
            {
                "name": "用户临时文件 (Temp)",
                "path": temp_dir,
                "safe": True,
            },
            {
                "name": "LocalAppData Temp",
                "path": local_app_data / "Temp",
                "safe": True,
            },
            {
                "name": "系统临时文件 (C:\\Windows\\Temp)",
                "path": windows_temp,
                "safe": True,
            },
        ]

    def create_widgets(self):
        top_frame = ttk.Frame(self, padding=12)
        top_frame.pack(fill="x")

        title = ttk.Label(top_frame, text="C盘安全清理助手", font=("Microsoft YaHei", 16, "bold"))
        title.pack(anchor="w")

        admin_text = "管理员权限：是" if is_admin() else "管理员权限：否（建议右键管理员运行）"
        self.admin_label = ttk.Label(top_frame, text=admin_text)
        self.admin_label.pack(anchor="w", pady=(4, 0))

        options_frame = ttk.LabelFrame(self, text="清理选项", padding=12)
        options_frame.pack(fill="x", padx=12, pady=(6, 8))

        self.var_temp1 = tk.BooleanVar(value=True)
        self.var_temp2 = tk.BooleanVar(value=True)
        self.var_temp3 = tk.BooleanVar(value=True)
        self.var_recycle = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text="清理 用户临时文件 (Temp)", variable=self.var_temp1).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(options_frame, text="清理 LocalAppData Temp", variable=self.var_temp2).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(options_frame, text="清理 系统临时文件 (C:\\Windows\\Temp)", variable=self.var_temp3).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(options_frame, text="清空回收站", variable=self.var_recycle).grid(row=3, column=0, sticky="w", pady=2)

        btn_frame = ttk.Frame(self, padding=(12, 0))
        btn_frame.pack(fill="x")

        self.scan_btn = ttk.Button(btn_frame, text="扫描可清理空间", command=self.start_scan)
        self.scan_btn.pack(side="left")

        self.clean_btn = ttk.Button(btn_frame, text="开始清理", command=self.start_clean)
        self.clean_btn.pack(side="left", padx=8)

        self.exit_btn = ttk.Button(btn_frame, text="退出", command=self.destroy)
        self.exit_btn.pack(side="right")

        progress_frame = ttk.Frame(self, padding=12)
        progress_frame.pack(fill="x")

        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.pack(fill="x")

        result_frame = ttk.LabelFrame(self, text="扫描/清理结果", padding=12)
        result_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.text = tk.Text(result_frame, height=14, wrap="word")
        self.text.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.text.yview)
        scrollbar.pack(fill="y", side="right")
        self.text.configure(yscrollcommand=scrollbar.set)

        status_frame = ttk.Frame(self, padding=(12, 0, 12, 10))
        status_frame.pack(fill="x")
        self.status_label = ttk.Label(status_frame, text="")
        self.status_label.pack(anchor="w")

    def log(self, msg: str):
        self.text.insert("end", msg + "\n")
        self.text.see("end")
        self.update_idletasks()

    def refresh_status(self, msg: str):
        self.status_label.config(text=msg)
        self.update_idletasks()

    def selected_targets(self):
        selected = []
        checks = [self.var_temp1.get(), self.var_temp2.get(), self.var_temp3.get()]
        for i, checked in enumerate(checks):
            if checked:
                selected.append(self.targets[i])
        return selected

    def set_running(self, running: bool):
        self.running = running
        if running:
            self.progress.start(10)
            self.scan_btn.config(state="disabled")
            self.clean_btn.config(state="disabled")
        else:
            self.progress.stop()
            self.scan_btn.config(state="normal")
            self.clean_btn.config(state="normal")

    def start_scan(self):
        if self.running:
            return
        self.text.delete("1.0", "end")
        self.set_running(True)
        self.refresh_status("正在扫描可清理空间...")
        threading.Thread(target=self.scan_task, daemon=True).start()

    def scan_task(self):
        total = 0
        selected = self.selected_targets()

        if not selected and not self.var_recycle.get():
            self.after(0, lambda: self.log("未选择任何清理项。"))
            self.after(0, lambda: self.refresh_status("请选择至少一个清理项。"))
            self.after(0, lambda: self.set_running(False))
            return

        self.after(0, lambda: self.log("开始扫描...\n"))
        for item in selected:
            p = item["path"]
            size = safe_get_size(p)
            total += size
            self.after(0, lambda n=item["name"], path=str(p), s=size: self.log(f"{n}\n  路径: {path}\n  可清理: {human_readable(s)}\n"))

        if self.var_recycle.get():
            self.after(0, lambda: self.log("回收站\n  可清理: 无法精确预估（清理时执行）\n"))

        self.after(0, lambda: self.log(f"预计可释放空间（不含回收站预估）：{human_readable(total)}"))
        self.after(0, lambda: self.refresh_status("扫描完成。可点击“开始清理”。"))
        self.after(0, lambda: self.set_running(False))

    def start_clean(self):
        if self.running:
            return

        selected = self.selected_targets()
        if not selected and not self.var_recycle.get():
            messagebox.showwarning("提示", "请至少选择一个清理项。")
            return

        ok = messagebox.askyesno(
            "确认清理",
            "即将清理所选临时文件与回收站。\n"
            "建议先关闭浏览器、聊天软件和编辑器。\n\n确定继续吗？"
        )
        if not ok:
            return

        self.text.delete("1.0", "end")
        self.set_running(True)
        self.refresh_status("正在清理，请稍候...")
        threading.Thread(target=self.clean_task, daemon=True).start()

    def clean_task(self):
        total_freed = 0
        selected = self.selected_targets()

        self.after(0, lambda: self.log("开始清理...\n"))

        for item in selected:
            name = item["name"]
            path = item["path"]

            if "Windows\\Temp" in str(path) and not is_admin():
                self.after(0, lambda n=name: self.log(f"{n}\n  跳过：需要管理员权限\n"))
                continue

            before = safe_get_size(path)
            freed = clear_directory_contents(path)
            after = safe_get_size(path)
            # freed 可能与 before-after 有偏差（占用文件、权限问题），取更稳妥估算
            estimate = max(freed, max(0, before - after))
            total_freed += estimate

            self.after(0, lambda n=name, b=before, a=after, e=estimate: self.log(
                f"{n}\n  清理前: {human_readable(b)}\n  清理后: {human_readable(a)}\n  释放约: {human_readable(e)}\n"
            ))

        if self.var_recycle.get():
            ok = empty_recycle_bin()
            if ok:
                self.after(0, lambda: self.log("回收站\n  清空完成\n"))
            else:
                self.after(0, lambda: self.log("回收站\n  清空失败（可能权限不足或被系统阻止）\n"))

        self.after(0, lambda: self.log(f"清理完成，合计释放约：{human_readable(total_freed)}"))
        self.after(0, lambda: self.refresh_status("清理完成。"))
        self.after(0, lambda: self.set_running(False))
        self.after(0, lambda: messagebox.showinfo("完成", f"清理完成！\n合计释放约：{human_readable(total_freed)}"))

if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()

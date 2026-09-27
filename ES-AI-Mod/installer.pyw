#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ES AI Mod — GUI-установщик (без консоли, двойной клик по файлу).

Копирует mod/ и server/ в <игра>/game/mods/es_ai, проверяет Python,
умеет открыть keys.json и удалить мод. Стандартная библиотека, tkinter.

Режим для автоматизации:  python installer.pyw --install "C:\\путь\\к игре"
"""
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = os.path.dirname(os.path.abspath(__file__))
MOD_DIR = os.path.join(ROOT, "mod")
SERVER_DIR = os.path.join(ROOT, "server")

CANDIDATES = [
    r"D:\Program Files (x86)\Steam\steamapps\common\Everlasting Summer",
    r"C:\Program Files (x86)\Steam\steamapps\common\Everlasting Summer",
    r"E:\Program Files (x86)\Steam\steamapps\common\Everlasting Summer",
    r"D:\SteamLibrary\steamapps\common\Everlasting Summer",
    r"C:\SteamLibrary\steamapps\common\Everlasting Summer",
]


def find_default_game():
    for c in CANDIDATES:
        if os.path.isdir(os.path.join(c, "game")):
            return c
    return ""


def dest_for(game_dir):
    return os.path.join(game_dir, "game", "mods", "es_ai")


def install(game_dir, log):
    if not os.path.isdir(os.path.join(game_dir, "game")):
        raise RuntimeError("В папке нет game\\ — это не папка игры?")
    dest = dest_for(game_dir)
    dest_server = os.path.join(dest, "server")
    log("Копирую мод → %s" % dest)

    # Бэкап пользовательских данных (ключи, конфиг, память диалогов)
    keep_names = ("keys.json", "config.json")
    keep_dir = "memory"
    backup = {}
    if os.path.isdir(dest_server):
        for n in keep_names:
            p = os.path.join(dest_server, n)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    backup[n] = f.read()
        mem = os.path.join(dest_server, keep_dir)
        if os.path.isdir(mem):
            shutil.copytree(mem, os.path.join(dest, "es_ai_mem_backup"),
                            dirs_exist_ok=True)

    # Если сервер мода ещё жив — просим его завершиться и ждём (порт берём из его конфига)
    import time as _t
    import urllib.request as _ur
    for _port in (33147, 4999):
        try:
            _ur.urlopen(_ur.Request("http://127.0.0.1:%s/shutdown" % _port,
                                    data=b"{}", headers={"Content-Type": "application/json"}),
                        timeout=3)
            log("Работающий сервер остановлен (порт %s)." % _port)
            _t.sleep(1.5)
            break
        except Exception:
            continue

    # Полная чистка старой установки (папку может держать живой процесс — ретраи)
    if os.path.isdir(dest):
        last_err = None
        for attempt in range(5):
            try:
                shutil.rmtree(dest)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                log("Папка занята (попытка %d/5) — закрой игру/сервер, повторяю…" % (attempt + 1))
                _t.sleep(2)
        if last_err is not None:
            raise RuntimeError(
                "Не удалось удалить старую папку мода: %s. "
                "Закрой игру и сервер (диспетчер задач: python.exe), затем повтори установку." % last_err)
    os.makedirs(dest, exist_ok=True)

    shutil.copytree(MOD_DIR, dest, dirs_exist_ok=True)

    def ignore(folder, names):
        return [n for n in names
                if n == "__pycache__" or n.endswith(".pyc")
                or n in ("memory", "cache_tts", "server_out.log")]

    log("Копирую сервер → %s" % dest_server)
    shutil.copytree(SERVER_DIR, dest_server, ignore=ignore, dirs_exist_ok=True)

    # Восстановление пользовательских данных
    restored = []
    for n, content in backup.items():
        with open(os.path.join(dest_server, n), "w", encoding="utf-8") as f:
            f.write(content)
        restored.append(n)
    mem_bak = os.path.join(dest, "es_ai_mem_backup")
    if os.path.isdir(mem_bak):
        shutil.move(mem_bak, os.path.join(dest_server, keep_dir))
        restored.append("memory/")
    if restored:
        log("Сохранены пользовательские данные: %s" % ", ".join(restored))

    fix_pyw_association(log)

    py_ok = check_python()
    log("Python 3: %s" % ("найден ✓" if py_ok else "НЕ НАЙДЕН — установи с python.org"))
    keys_path = os.path.join(dest_server, "keys.json")
    try:
        with open(keys_path, "r", encoding="utf-8") as f:
            keys = json.load(f)
        if not keys.get("groq_api_key") and not keys.get("llm_api_key"):
            log("ВНИМАНИЕ: ключ LLM ещё не задан. Нажми «Открыть keys.json» и впиши groq_api_key.")
        else:
            log("Ключ LLM: задан ✓")
    except Exception:
        pass
    log("Готово! Запусти игру → Моды → «AI Совёнок».")
    return dest


def uninstall(game_dir, log):
    dest = dest_for(game_dir)
    if not os.path.isdir(dest):
        raise RuntimeError("Мод не найден в %s" % dest)
    log("Удаляю %s" % dest)
    shutil.rmtree(dest)
    log("Готово. Перезапусти игру.")


def fix_pyw_association(log):
    """HKCU-ассоциация .pyw -> pythonw, чтобы двойной клик открывал окно настроек."""
    try:
        import winreg
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.pyw") as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "Python.NoConFile")
        base = r"Software\Classes\Python.NoConFile"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, '"%s" "%%1" %%*' % pythonw)
        log("Ассоциация .pyw настроена: двойной клик запускает окно настроек.")
    except Exception as e:
        log("Не удалось настроить ассоциацию .pyw: %s" % e)


def check_python():
    try:
        p = subprocess.run([sys.executable, "-c", "print(1)"],
                           capture_output=True, timeout=10)
        return p.returncode == 0
    except Exception:
        return False


def open_keys(game_dir):
    p = os.path.join(dest_for(game_dir), "server", "keys.json")
    if os.path.exists(p):
        os.startfile(p)  # noqa
    else:
        messagebox.showinfo("ES AI Mod", "Сначала установи мод.")


# ----------------------------------------------------------------- CLI ----
def cli():
    if "--install" in sys.argv:
        path = sys.argv[sys.argv.index("--install") + 1]
        def log(m):
            print(m)
        install(path, log)
        return 0
    if "--uninstall" in sys.argv:
        path = sys.argv[sys.argv.index("--uninstall") + 1]
        def log(m):
            print(m)
        uninstall(path, log)
        return 0
    return None


# ----------------------------------------------------------------- GUI ----
def gui():
    root = tk.Tk()
    root.title("ES AI Mod — установщик «AI Совёнок»")
    root.geometry("680x520")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Установка AI-мода для «Бесконечного лета»",
              font=("Segoe UI", 13, "bold")).pack(anchor="w")

    pathrow = ttk.Frame(frm)
    pathrow.pack(fill="x", pady=8)
    ttk.Label(pathrow, text="Папка игры:").pack(side="left")
    var_path = tk.StringVar(value=find_default_game())
    ent = ttk.Entry(pathrow, textvariable=var_path)
    ent.pack(side="left", fill="x", expand=True, padx=6)

    def browse():
        d = filedialog.askdirectory(title="Папка Everlasting Summer")
        if d:
            var_path.set(d)

    ttk.Button(pathrow, text="Обзор…", command=browse).pack(side="left")

    status = tk.Text(frm, height=20, state="disabled", bg="#101418",
                     fg="#cfe8cf", font=("Consolas", 9))
    status.pack(fill="both", expand=True, pady=8)

    def log(msg):
        status.configure(state="normal")
        status.insert("end", msg + "\n")
        status.see("end")
        status.configure(state="disabled")
        root.update_idletasks()

    def do_install():
        try:
            install(var_path.get().strip('" '), log)
        except Exception as e:
            log("ОШИБКА: %s" % e)
            messagebox.showerror("ES AI Mod", str(e))

    def do_uninstall():
        if not messagebox.askyesno("ES AI Mod", "Удалить мод из игры?"):
            return
        try:
            uninstall(var_path.get().strip('" '), log)
        except Exception as e:
            messagebox.showerror("ES AI Mod", str(e))

    def do_keys():
        open_keys(var_path.get().strip('" '))

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(4, 0))
    ttk.Button(btns, text="Установить / обновить мод", command=do_install).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Открыть keys.json", command=do_keys).pack(side="left", padx=(0, 8))
    ttk.Button(btns, text="Удалить мод", command=do_uninstall).pack(side="left")

    log("Выбери папку игры и нажми «Установить».")
    log("После установки: ключ нейросети — кнопкой «Открыть keys.json» (Groq бесплатно: platform.groq.com).")
    root.mainloop()
    return 0


if __name__ == "__main__":
    code = cli()
    sys.exit(code if code is not None else gui())

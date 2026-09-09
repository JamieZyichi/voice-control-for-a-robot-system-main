"""Isolated visual smoke check: no model, microphone or command-file writes."""
import ast
import pathlib
import subprocess
import sys
import types
import tkinter as tk
from tkinter import ttk

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / 'main_voice_app.py').read_text(encoding='utf-8')
baseline = subprocess.check_output(
    ['git', 'show', 'HEAD:main_voice_app.py'], cwd=ROOT).decode('utf-8')
before, after = ast.parse(baseline), ast.parse(source)
allowed = {'_setup_styles', '_style_content', '_build_ui', '_init_logo',
           '_init_logo_static', '_build_listen_tab', '_build_commands_tab',
           '_build_training_tab', '_build_system_tab', '_show_health_report'}
def methods(tree):
    return {n.name: n for c in tree.body if isinstance(c, ast.ClassDef)
            for n in c.body if isinstance(n, ast.FunctionDef)}
for name, method in methods(before).items():
    if name not in allowed:
        assert ast.dump(method) == ast.dump(methods(after)[name]), name

def bindings(tree):
    commands = []
    events = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == 'command':
                    commands.append(ast.dump(kw.value))
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'bind':
                events.append(ast.dump(node))
    return sorted(commands), events
old_commands, old_events = bindings(before)
new_commands, new_events = bindings(after)
assert old_commands == new_commands, 'Button callback changed'
assert all(event in new_events for event in old_events), 'Existing event binding changed'
print('PASS: business methods, button callbacks and existing event bindings unchanged', flush=True)

audio = types.ModuleType('audio_engine_v2')
audio.AudioEngine = object
sys.modules['audio_engine_v2'] = audio
models = types.ModuleType('model_manager')
models.SUPPORTED_MODELS = dict.fromkeys(['tiny', 'base', 'small', 'medium', 'large'])
sys.modules['model_manager'] = models
namespace = {'__name__': 'gui_preview', '__file__': str(ROOT / 'main_voice_app.py')}
exec(compile(source, str(ROOT / 'main_voice_app.py'), 'exec'), namespace)
App = namespace['VoiceControlApp']
App._init_system_async = lambda self: None
App._start_ui_updates = lambda self: None
App._start_auto_refresh = lambda self: None
root = tk.Tk()
callback_errors = []
root.report_callback_exception = lambda *args: callback_errors.append(args)
clicked = []
App._start_listening = lambda self: clicked.append('start')
App._stop_listening = lambda self: clicked.append('stop')
app = App(root)
root.title('Voice Control System - GUI preview (no audio)')
app._update_status('Ready')
app._update_detailed_status('System ready! Click \'Start Listening\' to begin.')
app.btn_start.config(state=tk.NORMAL)
app._log('[PREVIEW] GUI only - no microphone or model loaded.')
app._log("[14:38:10] Command: 'open camera 2' -> output.txt")
app._log('[PREVIEW] Chinese display: 打开机器人工作单元 / English display')
for cmd in ['open robot cell', 'open camera 2', '打开机器人工作单元']:
    app.cmd_tree.insert('', tk.END, values=(cmd, '1.00', 2))
    app.train_tree.insert('', tk.END, values=(cmd, 2, '1.00'))
app._refresh_system_status()

notebook = next(w for w in root.winfo_children() if isinstance(w, ttk.Notebook))
for geometry in ['1000x750', '900x650']:
    root.geometry(geometry)
    for tab in notebook.tabs():
        notebook.select(tab)
        root.update()
        def check_bounds(parent):
            for widget in parent.winfo_children():
                if isinstance(widget, ttk.Button):
                    assert widget.winfo_viewable(), (geometry, widget.cget('text'), 'hidden')
                    assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height(), (geometry, widget.cget('text'), 'clipped')
                    assert widget.winfo_rootx() >= root.winfo_rootx(), (geometry, widget.cget('text'), 'left clipped')
                    assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width(), (geometry, widget.cget('text'), 'right clipped')
                check_bounds(widget)
        check_bounds(root.nametowidget(tab))
    print('PASS: all page buttons visible at ' + geometry, flush=True)
    notebook.select(0)
    for status in ['Ready', "Listening for 'susie'...", 'Initialization Failed', 'Shutting down...']:
        app._update_status(status)
        root.update()
        labels = [app.header.bbox(item) for item in app.header.find_all() if app.header.type(item) == 'text']
        assert labels[0][2] < labels[1][0], ('Header text overlaps', geometry, status, labels)
    app._update_detailed_status('中文识别状态：等待机器人命令。' * 5)
    root.update()
    assert app.result_text.winfo_height() >= 40, ('Log squeezed by wrapped text', geometry,
        app.result_text.winfo_height(), [(w.winfo_class(), w.winfo_height(), w.winfo_reqheight()) for w in app.tab_listen.winfo_children()])
    app._update_detailed_status('System ready! Click Start Listening to begin.')
root.geometry('1000x750')
notebook.select(0)
app.btn_start.config(state=tk.DISABLED)
app.btn_stop.config(state=tk.NORMAL)
assert app.btn_start.instate(['disabled'])
assert not app.btn_stop.instate(['disabled'])
app.btn_start.invoke()
assert clicked == [], 'Disabled Start invoked its callback'
app.btn_stop.invoke()
assert clicked == ['stop']
app.btn_stop.config(state=tk.DISABLED)
app.btn_start.config(state=tk.NORMAL)
app.btn_start.invoke()
assert clicked == ['stop', 'start']
print('PASS: existing config(state=...) works with themed buttons', flush=True)

# Native Notebook bindings must still handle keyboard page switching.
notebook.focus_force()
notebook.select(0)
root.update()
notebook.event_generate('<Control-Tab>')
root.update()
assert notebook.index(notebook.select()) == 1
print('PASS: native keyboard page switching and enabled/disabled callbacks', flush=True)

app.result_text.delete('1.0', tk.END)
sample = "[14:38:10] Command: 'open camera 2' -> output.txt\n[14:38:11] 中文测试 -> No match\n"
app.result_text.insert(tk.END, sample)
assert app.result_text.get('1.0', 'end-1c') == sample
assert app.result_text.tag_ranges('success')
assert app.result_text.tag_ranges('warning')
assert app.result_text.tag_ranges('timestamp')
app.result_text.insert(tk.END, 'editable')
assert app.result_text.get('end-9c', 'end-1c') == 'editable'
app.result_text.delete('1.0', tk.END)
assert app.result_text.get('1.0', 'end-1c') == ''
assert not callback_errors, callback_errors
print('PASS: log colors preserve exact text, editing and clearing; no Tk callback errors', flush=True)
root.destroy()

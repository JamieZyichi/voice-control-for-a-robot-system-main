"""English/Chinese presentation catalog. Never translates commands or activity logs."""
import re
import tkinter as tk
from tkinter import ttk
from weakref import WeakKeyDictionary

ZH = {
    'Voice Control System': '语音控制系统',
    'Listen': '监听', 'Commands': '命令', 'Training': '训练', 'System': '系统',
    'Voice Recognition': '语音识别', 'RECOGNITION STATUS': '识别状态',
    'Start Listening': '开始监听', 'Stop Listening': '停止监听',
    'Activity Log': '活动日志', 'Clear Log': '清空日志',
    'Command Management': '命令管理', 'New Command:': '新命令：',
    'Add Command': '添加命令', 'Command': '命令', 'Weight': '权重',
    'Usage Count': '使用次数', 'Refresh': '刷新', 'Delete Selected': '删除所选',
    'Reload JSON': '重新加载 JSON', 'Command Training': '命令训练',
    'Training Progress': '训练进度', 'Train Selected': '训练所选',
    'System Configuration': '系统配置', 'STT Model:': '识别模型：',
    'TTS Voice:': '播报声音：', 'Test Voice': '测试声音',
    'System Status': '系统状态', 'Refresh Status': '刷新状态',
    'Health Check': '健康检查', 'Save Log': '保存日志',
    'System Health Report': '系统健康报告', 'Close': '关闭',
    'Ready': '就绪', 'Initializing': '初始化中', 'Initializing...': '初始化中…',
    'System starting up...': '系统正在启动…', 'Partially Ready': '部分就绪',
    'Initialization Failed': '初始化失败', 'Command Mode': '命令模式',
    'Listening...': '正在监听…', "Listening for 'susie'...": '正在监听“susie”…',
    "Listening for wake word 'susie'...": '正在监听唤醒词“susie”…',
    'Shutting down...': '正在关闭…',
    'Cleaning up resources, please wait...': '正在清理资源，请稍候…',
    "System ready! Click 'Start Listening' to begin.": '系统已就绪！点击“开始监听”即可开始。',
    'System ready. Click Start Listening to begin.': '系统已就绪。点击“开始监听”即可开始。',
    "System is listening for the wake word 'susie'. Speak clearly.": '正在监听唤醒词“susie”，请清晰说话。',
    'Wake word detected! Command mode active.': '已检测到唤醒词！命令模式已启用。',
    'Recognition stopped. System ready to start again.': '识别已停止，系统可再次开始监听。',
    'Too many failures. Returned to standby.': '未匹配次数过多，已返回待机状态。',
    'Step 1/5: Initializing audio engine...': '步骤 1/5：正在初始化音频引擎…',
    'Step 2/5: Loading speech recognition model...': '步骤 2/5：正在加载语音识别模型…',
    'Step 3/5: Verifying model manager...': '步骤 3/5：正在检查模型管理器…',
    'Step 4/5: Loading command manager...': '步骤 4/5：正在加载命令管理器…',
    'Step 5/5: Initializing TTS engine...': '步骤 5/5：正在初始化语音播报引擎…',
    'Error': '错误', 'Success': '成功', 'Confirm': '确认', 'No Selection': '未选择项目',
    'System Not Ready': '系统尚未就绪', 'OK': '确定', 'Yes': '是', 'No': '否',
    'Command manager not available': '命令管理器不可用',
    'Commands reloaded from JSON file': '已从 JSON 文件重新加载命令',
    'System is not fully initialized. Please wait.': '系统尚未完成初始化，请稍候。',
    'Please select a command to delete.': '请选择要删除的命令。',
    'Please select a command to train.': '请选择要训练的命令。',
    'Audio engine not initialized.': '音频引擎尚未初始化。',
    'Please wait for system initialization to complete.': '请等待系统初始化完成。',
    '=== ENHANCED VOICE CONTROL SYSTEM STATUS ===': '=== 语音控制系统状态 ===',
    '=== SYSTEM INITIALIZATION REPORT ===': '=== 系统初始化报告 ===',
    'Most Used Commands:': '最常使用的命令：', 'Features:': '功能：',
    'True': '是', 'False': '否', 'Enabled': '已启用', 'Disabled': '已禁用',
    'UNKNOWN': '未知', 'unknown': '未知', 'INACTIVE': '未激活', 'ACTIVE': '已激活',
    'PENDING': '等待中', 'READY': '就绪', 'FAILED': '失败', 'WARNING': '警告',
    'audio_engine': '音频引擎', 'model_manager': '模型管理器',
    'command_manager': '命令管理器', 'tts_engine': '语音播报引擎', 'model_loaded': '模型加载',
    'Audio Engine': '音频引擎', 'Model Loading': '模型加载',
    'tts_enabled': '语音播报', 'hotwords_enabled': '热词', 'offline_mode': '离线模式',
    'Timeout waiting for model': '等待模型加载超时', 'TTS not available': '语音播报不可用',
    'Model manager not available': '模型管理器不可用',
}

# Patterns translate application-authored wording, keeping identifiers and values intact.
PATTERNS = [
    (r'Listening for command\.\.\. \(Failures: (\d+)/(\d+)\)', r'正在监听命令…（未匹配：\1/\2）'),
    (r"Success! Command '(.*)' executed", r'成功！命令“\1”已执行'),
    (r"No matching command: '(.*)'", r'未找到匹配命令：“\1”'),
    (r'Switching to (.*) model\.\.\.', r'正在切换到 \1 模型…'),
    (r"Command '(.*)' added", r'已添加命令“\1”'),
    (r"Failed to add command '(.*)'", r'无法添加命令“\1”'),
    (r"Delete command '(.*)'\?", r'是否删除命令“\1”？'),
    (r"Command '(.*)' trained\. Weight: (.*)", r'命令“\1”已训练。权重：\2'),
    (r'Log saved as (.*)', r'日志已保存为 \1'),
    (r'Failed to save log: (.*)', r'保存日志失败：\1'),
    (r'Failed to reload JSON: (.*)', r'重新加载 JSON 失败：\1'),
    (r'Audio engine initialization failed: (.*)', r'音频引擎初始化失败：\1'),
    (r'Critical system initialization error: (.*)', r'系统初始化严重错误：\1'),
    (r'Error getting system status: (.*)', r'获取系统状态失败：\1'),
    (r'Elapsed Time: (.*)s', r'已用时间：\1 秒'),
    (r'Commands: (.*) total', r'命令总数：\1'),
    (r"  '(.*)': (.*) times", r'  “\1”：\2 次'),
]
FIELDS = {
    'System Status': '系统状态', 'Wake State': '唤醒状态', 'Processing': '处理中',
    'Recording': '录音中', 'Backend': '识别后端', 'Current Model': '当前模型',
    'Model Loaded': '模型已加载', 'Total Usage': '使用总次数',
    'TTS Engine': '语音播报引擎', 'TTS Running': '语音播报运行中', 'Voice Count': '声线数量',
    'System Ready': '系统已就绪', 'Error': '错误',
}

class UILanguage:
    def __init__(self, root):
        self.root = root
        self.language = 'en'
        self._widgets = WeakKeyDictionary()
        self._texts = WeakKeyDictionary()
        self._variables = []

    def text(self, source):
        source = str(source)
        if self.language == 'en':
            return source
        if source in ZH:
            return ZH[source]
        if '\n' in source:
            return '\n'.join(self.text(line) for line in source.split('\n'))
        for expression, replacement in PATTERNS:
            match = re.fullmatch(expression, source)
            if match:
                return match.expand(replacement)
        match = re.fullmatch(r'(.*) Failed', source)
        if match:
            return self.text(match[1]) + '失败'
        match = re.fullmatch(r'Failed to initialize (.*)\. Check console for details\.', source)
        if match:
            return f'{self.text(match[1])}初始化失败，请查看控制台详情。'
        for prefix in ('System partially initialized. Failed components: ', 'Failed Components: '):
            if source.startswith(prefix):
                names = '、'.join(self.text(name) for name in source[len(prefix):].split(', '))
                return ('系统部分初始化，失败组件：' if prefix.startswith('System') else '失败组件：') + names
        # Structured status/health-report lines. Do not translate command/model data.
        match = re.fullmatch(r'(\s*)([^:]+): (.*)', source)
        if match and (match[2] in FIELDS or match[2] in ZH):
            label = FIELDS.get(match[2], ZH.get(match[2]))
            return match[1] + label + '：' + ZH.get(match[3], match[3])
        return source  # Raw third-party diagnostics and proper names stay authentic.

    def variable(self, value):
        variable = UIStringVar(self, value)
        self._variables.append(variable)
        return variable

    def register_tree(self, parent):
        """Remember original static strings once; never rebuild controls or rows."""
        if parent not in self._widgets:
            data = {}
            if isinstance(parent, (tk.Tk, tk.Toplevel)):
                data['title'] = parent.title()
            if isinstance(parent, (tk.Label, tk.LabelFrame, ttk.Button)):
                if 'textvariable' not in parent.keys() or not parent.cget('textvariable'):
                    data['text'] = str(parent.cget('text'))
            if isinstance(parent, ttk.Notebook):
                data['tabs'] = {tab: parent.tab(tab, 'text') for tab in parent.tabs()}
            if isinstance(parent, ttk.Treeview):
                data['headings'] = {column: parent.heading(column, 'text') for column in parent['columns']}
            if data:
                self._widgets[parent] = data
        self._refresh_widget(parent)
        for child in parent.winfo_children():
            self.register_tree(child)

    def _refresh_widget(self, widget):
        if not widget.winfo_exists():
            return
        data = self._widgets.get(widget, {})
        if 'title' in data:
            widget.title(self.text(data['title']))
        if 'text' in data:
            widget.configure(text=self.text(data['text']))
        for tab, source in data.get('tabs', {}).items():
            widget.tab(tab, text=self.text(source))
        for column, source in data.get('headings', {}).items():
            widget.heading(column, text=self.text(source))

    def set_text(self, widget, source):
        """Only for read-only system/report text, never ActivityText."""
        self._texts[widget] = source
        self._refresh_text(widget, source)

    def _refresh_text(self, widget, source):
        if not widget.winfo_exists():
            return
        state, position = widget.cget('state'), widget.yview()
        widget.configure(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        widget.insert('1.0', self.text(source))
        widget.configure(state=state)
        if position:
            widget.yview_moveto(position[0])

    def toggle(self):
        self.language = 'zh' if self.language == 'en' else 'en'
        for widget in list(self._widgets):
            self._refresh_widget(widget)
        for variable in self._variables:
            variable.refresh()
        for widget, source in list(self._texts.items()):
            self._refresh_text(widget, source)

class UIStringVar(tk.StringVar):
    """Store English source separately so future updates use the current language."""
    def __init__(self, catalog, value):
        self.catalog, self.source = catalog, str(value)
        super().__init__(master=catalog.root, value=catalog.text(value))

    def set(self, value):
        self.source = str(value)
        super().set(self.catalog.text(self.source))

    def refresh(self):
        super().set(self.catalog.text(self.source))

class UIDialogs:
    """Localized modal buttons independent of Windows' installed display language."""
    def __init__(self, catalog):
        self.catalog = catalog

    def _show(self, title, message, question=False):
        root = self.catalog.root
        previous_focus, previous_grab = root.focus_get(), root.grab_current()
        popup = tk.Toplevel(root)
        popup.title(title)
        popup.transient(root)
        popup.configure(bg='#F0F3FA')
        popup.resizable(False, False)
        message_variable = self.catalog.variable(message)
        popup.bind('<Destroy>', lambda event: self.catalog._variables.remove(message_variable)
                   if event.widget is popup else None, add='+')
        label = tk.Label(popup, textvariable=message_variable, wraplength=430,
                         justify=tk.LEFT, bg='#F0F3FA', fg='#0D203F', font=('Segoe UI', 11))
        label.pack(padx=26, pady=(24, 18))
        controls = tk.Frame(popup, bg='#F0F3FA')
        controls.pack(padx=24, pady=(0, 20))
        result = [False if question else 'ok']
        def finish(value):
            result[0] = value
            popup.destroy()
        default = ttk.Button(controls, text='Yes' if question else 'OK', style='Primary.TButton',
                             command=lambda: finish(True if question else 'ok'))
        default.pack(side=tk.LEFT, padx=6)
        if question:
            ttk.Button(controls, text='No', style='Secondary.TButton',
                       command=lambda: finish(False)).pack(side=tk.LEFT, padx=6)
        popup.protocol('WM_DELETE_WINDOW', lambda: finish(False if question else 'ok'))
        popup.bind('<Escape>', lambda event: finish(False if question else 'ok'))
        popup.bind('<Return>', lambda event: (popup.focus_get().invoke()
                   if isinstance(popup.focus_get(), ttk.Button) else default.invoke()))
        self.catalog.register_tree(popup)
        popup.update_idletasks()
        popup.geometry(f'+{root.winfo_rootx() + max(0, (root.winfo_width() - popup.winfo_reqwidth()) // 2)}'
                       f'+{root.winfo_rooty() + max(0, (root.winfo_height() - popup.winfo_reqheight()) // 2)}')
        popup.grab_set()
        default.focus_set()
        root.wait_window(popup)
        if previous_grab is not None and previous_grab.winfo_exists():
            previous_grab.grab_set()
        if previous_focus is not None and previous_focus.winfo_exists():
            previous_focus.focus_set()
        return result[0]

    def showinfo(self, title, message):
        return self._show(title, message)

    def showwarning(self, title, message):
        return self._show(title, message)

    def showerror(self, title, message):
        return self._show(title, message)

    def askyesno(self, title, message):
        return self._show(title, message, question=True)

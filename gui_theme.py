"""iOS-inspired presentation for the existing Tkinter application.

Uses native ttk controls and generated in-memory PNG surfaces (stdlib only).
No audio, command processing, persistence or application state lives here.
"""
import math
import re
import struct
import zlib
import tkinter as tk
from tkinter import ttk, scrolledtext
import tkinter.font as tkfont

COLORS = {
    'bg': '#F0F3FA', 'surface': '#FFFFFF', 'bg_dark': '#334D72',
    'primary': '#087CFA', 'primary_hover': '#0068E5', 'success': '#16B85B',
    'danger': '#BC3546', 'warning': '#C77B08', 'secondary': '#52627D',
    'light': '#F4F7FC', 'dark': '#0D203F', 'text': '#0D203F',
    'border': '#DCE4F0', 'muted': '#8592AA', 'disabled_bg': '#E9EDF3',
    'selection': '#E1EEFF',
}
FONTS = {
    'title': ('Segoe UI', 18, 'bold'),
    'section': ('Segoe UI', 15, 'bold'),
    'body': ('Segoe UI', 11), 'small': ('Segoe UI', 10),
    'mono': ('Consolas', 10),
}

def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))

def surface(master, width, height, radius, top, bottom=None, border=None):
    """Antialiased rounded gradient PNG. Small surfaces are nine-sliced by ttk."""
    width, height = max(2, int(width)), max(2, int(height))
    radius = min(radius, width / 2, height / 2)
    first, last = _rgb(top), _rgb(bottom or top)
    edge = _rgb(border) if border else None
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        mix = y / max(1, height - 1)
        color = tuple(round(a + (b - a) * mix) for a, b in zip(first, last))
        dy = max(radius - y - .5, y + .5 - (height - radius), 0)
        for x in range(width):
            dx = max(radius - x - .5, x + .5 - (width - radius), 0)
            distance = math.hypot(dx, dy)
            alpha = max(0, min(1, radius - distance + .5))
            near_edge = min(x, y, width - 1 - x, height - 1 - y) < 1 or distance > radius - 1.2
            rows.extend((*((edge if edge and near_edge else color)), round(255 * alpha)))
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(bytes(rows))) + chunk(b'IEND', b''))
    return tk.PhotoImage(master=master, data=png)

def install_theme(root):
    """Style native widgets without replacing their class bindings."""
    style = ttk.Style(root)
    style.theme_use('clam')
    # Keep image references alive for the lifetime of this Tcl interpreter.
    images = root._voice_theme_images = []
    def rounded(name, top, bottom=None, radius=16, border=None, size=64):
        image = surface(root, size, size, radius, top, bottom, border)
        images.append(image)
        return image
    for name, top, bottom, radius, border in (
        ('Card', '#FFFFFF', '#FFFFFF', 22, None),
        ('Inset', '#FFFFFF', '#FFFFFF', 12, COLORS['border']),
        ('Status', '#3A5275', '#30486A', 14, None),
    ):
        element = 'Voice' + name + '.surface'
        image = rounded(name, top, bottom, radius, border)
        if element not in style.element_names():
            style.element_create(element, 'image', image, border=24, padding=0, sticky='nsew')
        style.layout(name + '.TFrame', [(element, {'sticky': 'nsew', 'children': [
            ('Frame.padding', {'sticky': 'nsew'})]})])
        style.configure(name + '.TFrame', background=COLORS['bg'])

    for name, top, bottom, fg, active in (
        ('Primary', '#3699FF', '#087CFA', 'white', '#066CDF'),
        ('Start', '#30CF6A', '#0DA951', 'white', '#119847'),
        ('Secondary', '#FAFCFF', '#E5F0FF', '#006CE5', '#D7E9FF'),
        ('Danger', '#FFF5F5', '#FFE7E9', '#BD3045', '#FFD5DB'),
    ):
        normal = rounded(name, top, bottom, 14, '#D5E3F6' if name in ('Secondary', 'Danger') else None, size=40)
        hover = rounded(name, active, active, 14, size=40)
        disabled = rounded(name, '#EEF1F6', '#E5E9F0', 14, '#E1E6EF', size=40)
        element = 'Voice' + name + '.button'
        if element not in style.element_names():
            style.element_create(element, 'image', normal, ('disabled', disabled),
                                 ('pressed', hover), ('active', hover), border=18, padding=0, sticky='nsew')
        style.layout(name + '.TButton', [(element, {'sticky': 'nsew', 'children': [
            ('Button.focus', {'sticky': 'nsew', 'children': [
                ('Button.padding', {'sticky': 'nsew', 'children': [
                    ('Button.label', {'sticky': 'nsew'})]})]})]})])
        style.configure(name + '.TButton', font=FONTS['body'], padding=(18, 10),
                        foreground=fg, background=COLORS['surface'], borderwidth=0,
                        focuscolor=fg, focusthickness=1, anchor='center')
        style.map(name + '.TButton', foreground=[('disabled', '#98A3B6')])
    style.configure('Start.TButton', font=('Segoe UI', 12, 'bold'), padding=(20, 13))
    style.configure('Stop.Danger.TButton', font=('Segoe UI', 12, 'bold'), padding=(20, 13))

    # Identical radius, gradient, border and font to BrandHeader's Ready capsule.
    normal = surface(root, 64, 36, 18, '#429DFC', '#2E8DF5', '#6DAFFC')
    hover = surface(root, 64, 36, 18, '#57AAFF', '#3D99FC', '#91C1FF')
    images.extend((normal, hover))
    if 'VoiceLanguage.button' not in style.element_names():
        style.element_create('VoiceLanguage.button', 'image', normal,
                             ('pressed', hover), ('active', hover),
                             border=18, padding=0, sticky='nsew')
    style.layout('Language.TButton', [('VoiceLanguage.button', {'sticky': 'nsew', 'children': [
        ('Button.focus', {'sticky': 'nsew', 'children': [
            ('Button.padding', {'sticky': 'nsew', 'children': [
                ('Button.label', {'sticky': 'nsew'})]})]})]})])
    style.configure('Language.TButton', font=FONTS['small'], foreground='white',
                    background='#2588F6', focuscolor='white', focusthickness=1,
                    padding=(10, 3), anchor='center')

    selected = rounded('tab', '#FFFFFF', '#FFFFFF', 20, '#E4EBF6', size=44)
    unfocused = rounded('track', '#E9EEF7', '#E5EBF5', 20, '#F9FBFF', size=44)
    hover = rounded('hover', '#F2F6FC', '#EEF3FA', 20, size=44)
    element = 'Voice.tab'
    if element not in style.element_names():
        style.element_create(element, 'image', unfocused, ('selected', selected),
                             ('active', hover), border=20, padding=0, sticky='nsew')
    style.layout('TNotebook.Tab', [(element, {'sticky': 'nsew', 'children': [
        ('Notebook.padding', {'sticky': 'nsew', 'children': [
            ('Notebook.focus', {'sticky': 'nsew', 'children': [
                ('Notebook.label', {'sticky': 'nsew'})]})]})]})])
    style.configure('TNotebook', background=COLORS['bg'], borderwidth=0, tabmargins=(4, 0, 0, 12))
    style.configure('TNotebook.Tab', font=FONTS['body'], padding=(26, 9),
                    background=COLORS['bg'], foreground=COLORS['secondary'], focuscolor=COLORS['primary'])
    style.map('TNotebook.Tab', foreground=[('selected', '#007AFF')])
    style.configure('Treeview', font=FONTS['body'],
                    rowheight=tkfont.Font(root=root, font=FONTS['body']).metrics('linespace') + 12,
                    background='white', fieldbackground='white', foreground=COLORS['text'], borderwidth=0)
    style.configure('Treeview.Heading', font=('Segoe UI', 11, 'bold'), padding=(10, 10),
                    background=COLORS['light'], foreground=COLORS['secondary'], relief='flat')
    style.map('Treeview', background=[('selected', COLORS['selection'])],
              foreground=[('selected', COLORS['text'])])
    style.configure('TCombobox', padding=7, arrowsize=12, bordercolor=COLORS['border'])
    style.map('TCombobox', fieldbackground=[('readonly', 'white')],
              foreground=[('readonly', COLORS['text'])], selectbackground=[('readonly', 'white')],
              selectforeground=[('readonly', COLORS['text'])])
    style.configure('Vertical.TScrollbar', background='#CCD4E1', troughcolor='#F5F7FB',
                    borderwidth=0, arrowsize=10)

class BrandHeader(tk.Canvas):
    """Paint branding and a status badge; the existing StringVar remains authoritative."""
    def __init__(self, parent, status_var, logo=None, translate=str, on_language=None):
        super().__init__(parent, height=80, bg=COLORS['bg'], bd=0, highlightthickness=0)
        self.status_var, self.logo = status_var, logo
        self.translate = translate
        self._size = None
        self._gradient = None
        self._font = tkfont.Font(root=parent, family='Segoe UI', size=18, weight='bold')
        self._badge_font = tkfont.Font(root=parent, font=FONTS['small'])
        self.language_button = ttk.Button(self, text='中/EN', style='Language.TButton',
                                          command=on_language, cursor='hand2', takefocus=True)
        self.language_button.bind('<Return>', lambda event: self.language_button.invoke())
        self.bind('<Configure>', self._paint)
        self._trace = status_var.trace_add('write', self._paint)
        self.bind('<Destroy>', self._dispose, add='+')

    def _dispose(self, event):
        if event.widget is self:
            self.status_var.trace_remove('write', self._trace)

    def _paint(self, *_):
        width, height = self.winfo_width(), self.winfo_height()
        if width < 2:
            return
        self.delete('all')
        if self._size != (width, height):
            self._gradient = surface(self, width, height, 22, '#3797FF', '#1579ED')
            self._size = (width, height)
        self.create_image(0, 0, image=self._gradient, anchor='nw')
        if self.logo:
            self.create_image(30, height / 2, image=self.logo, anchor='w')
        text = self.status_var.get()
        badge_width = min(220, max(105, self._badge_font.measure(text) + 42))
        toggle_width, gap = 80, 10
        toggle_x = width - badge_width - 26 - toggle_width - gap
        left_edge = (self.logo.width() + 48) if self.logo else 24
        right_edge = toggle_x - 18
        title = self.translate('Voice Control System')
        title_room = max(80, right_edge - left_edge)
        for size in range(18, 8, -1):
            self._font.configure(size=size)
            if self._font.measure(title) <= title_room:
                break
        title_width = self._font.measure(title)
        title_x = min(max(width / 2, left_edge + title_width / 2), right_edge - title_width / 2)
        self.create_text(title_x, height / 2, text=title, tags='brand_title',
                         font=self._font, fill='white')
        lines = max(1, math.ceil(self._badge_font.measure(text) / (badge_width - 40)))
        badge_height = max(36, lines * self._badge_font.metrics('linespace') + 10)
        badge = surface(self, badge_width, badge_height, 18, '#429DFC', '#2E8DF5', '#6DAFFC')
        self._badge_image = badge
        x = width - badge_width - 26
        self.create_image(x, height / 2, image=badge, anchor='w')
        dot = '#20DF85' if getattr(self.status_var, 'source', text) == 'Ready' else '#DCEBFF'
        self.create_oval(x + 14, height / 2 - 5, x + 24, height / 2 + 5, fill=dot, outline='')
        self.create_text(x + 32, height / 2, text=text, anchor='w',
                         width=badge_width - 40, font=self._badge_font, fill='white', tags='status_text')
        self.language_button.place(x=toggle_x, y=(height - badge_height) / 2,
                                   width=toggle_width, height=badge_height)

class StatusPanel(tk.Canvas):
    """Rounded gradient behind the unchanged detailed-status text."""
    def __init__(self, parent, textvariable, translate=str):
        super().__init__(parent, bg='white', height=86, bd=0, highlightthickness=0)
        self.variable = textvariable
        self.translate = translate
        self._size = None
        self._gradient = None
        self._trace = self.variable.trace_add('write', self._paint)
        self.bind('<Configure>', self._paint)
        self.bind('<Destroy>', self._dispose, add='+')

    def _dispose(self, event):
        if event.widget is self:
            self.variable.trace_remove('write', self._trace)

    def _paint(self, *_):
        width = self.winfo_width()
        if width < 2:
            return
        self.delete('all')
        self.create_text(22, 16, anchor='nw', text=self.translate('RECOGNITION STATUS'),
                         font=('Segoe UI', 9, 'bold'), fill='#B9C5D7')
        caption = self.create_text(22, 40, anchor='nw', text=self.variable.get(),
                                   width=max(120, width - 44),
                                   font=('Segoe UI', 11 if width < 830 else 13, 'bold'), fill='white')
        height = max(86, self.bbox(caption)[3] + 18)
        if int(self.cget('height')) != height:
            self.configure(height=height)
        if self._size != (width, height):
            self._gradient = surface(self, width, height, 14, '#3D567B', '#2E466A')
            self._size = (width, height)
        background = self.create_image(0, 0, image=self._gradient, anchor='nw')
        self.tag_lower(background)


class ActivityText(scrolledtext.ScrolledText):
    """Retain editable/scrollable Text behavior; color only the inserted log lines."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag_configure('timestamp', foreground='#8592AA')
        self.tag_configure('success', foreground='#15984F')
        self.tag_configure('warning', foreground='#CE8509')
        self.tag_configure('error', foreground='#BE3548')
        self.tag_raise('timestamp')
        self.tag_raise('sel')

    def insert(self, index, chars, *tags):
        start = self.index('end-1c' if str(index) == 'end' else index)
        super().insert(index, chars, *tags)
        offset = 0
        for line in chars.splitlines(keepends=True):
            begin, end = f'{start}+{offset}c', f'{start}+{offset + len(line)}c'
            lower = line.lower()
            tag = ('error' if '[error]' in lower or '[critical]' in lower or 'write failed' in lower else
                   'warning' if 'no match' in lower or '[warning]' in lower else
                   'success' if 'command:' in lower or '[success]' in lower else None)
            if tag:
                self.tag_add(tag, begin, end)
            stamp = re.match(r'\[\d{2}:\d{2}:\d{2}\]', line)
            if stamp:
                self.tag_add('timestamp', begin, f'{start}+{offset + stamp.end()}c')
            offset += len(line)

def button_icon(master, kind, color):
    """Small vector-style icons, rendered as transparent Tk images."""
    image = tk.PhotoImage(master=master, width=26, height=24)
    def pixel(x, y):
        image.put(color, (x, y))
    if kind == 'stop':
        for y in range(5, 19):
            for x in range(3, 17):
                if not ((x in (3, 16)) and (y in (5, 18))):
                    pixel(x, y)
    else:
        for y in range(2, 16):
            for x in range(7, 15):
                if (x in (7, 8, 13, 14) and 5 <= y <= 12) or (y in (2, 3, 14, 15) and 9 <= x <= 12):
                    pixel(x, y)
        for x, y in [(4, y) for y in range(10, 16)] + [(17, y) for y in range(10, 16)]:
            pixel(x, y)
        for x, y in [(5, 16), (6, 17), (7, 18), (8, 19), (9, 19), (10, 19), (11, 19),
                     (12, 19), (13, 19), (14, 18), (15, 17), (16, 16)]:
            pixel(x, y)
        for y in range(19, 23):
            pixel(10, y)
            pixel(11, y)
        for x in range(7, 15):
            pixel(x, 23)
    return image

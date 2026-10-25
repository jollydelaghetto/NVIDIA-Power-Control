#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""NVIDIA Power Control: graphical power limit profiles for KDE / CachyOS."""
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from PySide6.QtCore import Qt, QProcess, QTimer, QSize
from PySide6.QtGui import QIcon, QAction, QPainter, QColor, QPixmap, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QMessageBox, QSystemTrayIcon, QMenu,
    QLineEdit, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog
)

ROOT = Path(__file__).resolve().parent
CONFIG = Path.home() / '.config' / 'gpu-profiles' / 'config.json'
SMI = shutil.which('nvidia-smi') or '/usr/bin/nvidia-smi'
PKEXEC = shutil.which('pkexec') or '/usr/bin/pkexec'
PROFILES = [(280, 'leaf', 'Menos ruido y consumo'),
            (320, 'sliders', 'Balance de FPS y eficiencia'),
            (360, 'bolt', 'Toda la potencia disponible')]
DEFAULT = {
    'names': {'280': 'Eficiente', '320': 'Equilibrado', '360': 'Máximo rendimiento'},
    'auto': False, 'games': []
}

def load_config():
    cfg = json.loads(json.dumps(DEFAULT))
    try:
        saved = json.loads(CONFIG.read_text(encoding='utf-8'))
        if isinstance(saved, dict):
            names = saved.get('names', {})
            if isinstance(names, dict):
                cfg['names'].update({str(k): str(v)[:40] for k, v in names.items()
                                     if str(k) in cfg['names']})
            cfg['auto'] = saved.get('auto') is True
            games = saved.get('games', [])
            if isinstance(games, list):
                cfg['games'] = [x for x in games if isinstance(x, dict)][:30]
    except (OSError, ValueError, TypeError):
        pass
    return cfg

def save_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG.with_suffix('.tmp')
    temp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    os.chmod(temp, 0o600)
    temp.replace(CONFIG)

def gpu():
    command = [SMI, '-i', '0', '--query-gpu=name,power.limit,power.draw,temperature.gpu,utilization.gpu',
               '--format=csv,noheader,nounits']
    out = subprocess.run(command, check=True, capture_output=True, text=True, timeout=6)
    values = next(csv.reader(io.StringIO(out.stdout)))
    if len(values) != 5:
        raise ValueError('Respuesta de nvidia-smi inesperada')
    return values[0].strip(), *(float(v.strip()) for v in values[1:])

def glyph(kind, size=32, color='#76B900'):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.scale(size / 32, size / 32)
    if kind == 'leaf':
        from PySide6.QtGui import QPainterPath
        p = QPainterPath()
        p.moveTo(6, 25)
        p.cubicTo(4, 12, 15, 5, 27, 5)
        p.cubicTo(28, 20, 19, 29, 6, 25)
        painter.drawPath(p)
        painter.drawLine(8, 25, 22, 12)
    elif kind == 'bolt':
        from PySide6.QtCore import QPointF
        painter.drawPolyline([QPointF(x, y) for x, y in
                              [(19, 3), (7, 18), (16, 18), (12, 29),
                               (26, 13), (17, 13), (19, 3)]])
    elif kind == 'thermo':
        painter.drawRoundedRect(12, 4, 8, 21, 4, 4)
        painter.drawEllipse(9, 21, 14, 9)
        painter.drawLine(16, 12, 16, 26)
    elif kind == 'chip':
        painter.drawRoundedRect(7, 7, 18, 18, 3, 3)
        painter.drawRect(12, 12, 8, 8)
        for v in (11, 21):
            painter.drawLine(v, 3, v, 7)
            painter.drawLine(v, 25, v, 29)
            painter.drawLine(3, v, 7, v)
            painter.drawLine(25, v, 29, v)
    elif kind == 'refresh':
        painter.drawArc(6, 6, 20, 20, 25 * 16, 290 * 16)
        painter.drawLine(23, 6, 27, 13)
        painter.drawLine(27, 13, 19, 13)
    elif kind == 'settings':
        painter.drawEllipse(7, 7, 18, 18)
        painter.drawEllipse(13, 13, 6, 6)
    else:
        painter.drawLine(5, 9, 27, 9)
        painter.drawLine(5, 23, 27, 23)
        painter.drawEllipse(10, 5, 8, 8)
        painter.drawEllipse(18, 19, 8, 8)
    painter.end()
    return QIcon(pix)

def app_icon():
    return glyph('chip', 96)

class RulesDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Personalización y detección de juegos')
        self.setMinimumWidth(530)
        self.rules = [dict(x) for x in cfg['games']]
        self.fields = {}
        layout = QVBoxLayout(self)
        for watts, _, _ in PROFILES:
            edit = QLineEdit(cfg['names'][str(watts)])
            edit.setMaxLength(40)
            self.fields[watts] = edit
            layout.addWidget(QLabel(f'Nombre del perfil {watts} W'))
            layout.addWidget(edit)
        self.auto = QCheckBox('Detectar juegos (experimental; pide confirmación)')
        self.auto.setChecked(cfg['auto'])
        layout.addWidget(self.auto)
        form = QFormLayout()
        self.process = QLineEdit()
        self.process.setPlaceholderText('Ej.: Cyberpunk2077.exe')
        self.selected = QComboBox()
        for watts, _, _ in PROFILES:
            self.selected.addItem(f'{watts} W', watts)
        form.addRow('Proceso:', self.process)
        form.addRow('Perfil:', self.selected)
        layout.addLayout(form)
        add = QPushButton('Añadir regla')
        add.clicked.connect(self.add_rule)
        layout.addWidget(add)
        self.rule_label = QLabel()
        self.rule_label.setWordWrap(True)
        layout.addWidget(self.rule_label)
        clear = QPushButton('Borrar reglas')
        clear.clicked.connect(self.clear_rules)
        layout.addWidget(clear)
        actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)
        self.display_rules()

    def display_rules(self):
        entries = [f"{r.get('process', '')} → {r.get('watts', '')} W" for r in self.rules]
        self.rule_label.setText('Reglas:\n' + ('\n'.join(entries) if entries else '(ninguna)'))

    def add_rule(self):
        name = self.process.text().strip()
        if not name or '/' in name or '\\' in name or len(name) > 80:
            QMessageBox.warning(self, 'Proceso inválido', 'Introduce solo el nombre del proceso.')
            return
        self.rules = [r for r in self.rules if str(r.get('process', '')).lower() != name.lower()]
        self.rules.append({'process': name, 'watts': int(self.selected.currentData())})
        self.process.clear()
        self.display_rules()

    def clear_rules(self):
        self.rules.clear()
        self.display_rules()

class Window(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cfg = load_config()
        self.proc = None
        self.busy = False
        self.last_limit = None
        self.last_rule = None
        self.suppressed_until = 0
        self.tray = None
        self.setWindowTitle('NVIDIA Power Control')
        self.setMinimumSize(610, 660)
        self.setWindowIcon(app_icon())
        self.build()
        self.setup_tray()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(3000)
        self.rule_timer = QTimer(self)
        self.rule_timer.timeout.connect(self.check_games)
        self.rule_timer.start(8000)

    def build(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(17)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(56, 56))
        top.addWidget(logo)
        titles = QVBoxLayout()
        title = QLabel('NVIDIA POWER CONTROL')
        title.setObjectName('heading')
        titles.addWidget(title)
        titles.addWidget(QLabel('RTX 5080 · CachyOS'))
        top.addLayout(titles)
        top.addStretch()
        settings = QPushButton()
        settings.setIcon(glyph('settings'))
        settings.setFixedSize(46, 46)
        settings.setToolTip('Personalizar y gestionar juegos')
        settings.clicked.connect(self.configure)
        top.addWidget(settings)
        layout.addLayout(top)
        self.name = QLabel('Consultando GPU…')
        self.name.setObjectName('sub')
        layout.addWidget(self.name)
        stats = QFrame()
        stats.setObjectName('stats')
        grid = QGridLayout(stats)
        self.metrics = {}
        for i, (key, caption, symbol) in enumerate([
            ('limit', 'LÍMITE', 'bolt'), ('power', 'CONSUMO', 'chip'),
            ('temp', 'TEMPERATURA', 'thermo'), ('load', 'UTILIZACIÓN', 'sliders')
        ]):
            tile = QFrame()
            tile.setObjectName('tile')
            col = QVBoxLayout(tile)
            line = QHBoxLayout()
            ico = QLabel()
            ico.setPixmap(glyph(symbol).pixmap(20,20))
            line.addWidget(ico)
            line.addWidget(QLabel(caption))
            line.addStretch()
            col.addLayout(line)
            value = QLabel('—')
            value.setObjectName('number')
            col.addWidget(value)
            self.metrics[key] = value
            grid.addWidget(tile, i // 2, i % 2)
        layout.addWidget(stats)
        layout.addWidget(QLabel('PERFILES DE POTENCIA · 280—360 W'))
        self.buttons = {}
        for watts, symbol, desc in PROFILES:
            button = QPushButton()
            button.setObjectName('profile')
            button.setIcon(glyph(symbol))
            button.setIconSize(QSize(34,34))
            button.setMinimumHeight(70)
            button.clicked.connect(lambda checked=False, w=watts: self.apply(w))
            layout.addWidget(button)
            self.buttons[watts] = button
        self.update_labels()
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        refresh = QPushButton('Actualizar')
        refresh.setIcon(glyph('refresh'))
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        footer = QLabel('Cambios temporales con autorización Polkit; no se alteran los voltajes.')
        footer.setWordWrap(True)
        layout.addWidget(footer)
        layout.addStretch()
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#111714; color:#e9f1e8;
                font-family:"Noto Sans",sans-serif; font-size:13px; }
            QLabel#heading { color:#f2f8ef; font-size:23px; font-weight:800; }
            QLabel#sub { color:#9eafa2; }
            QFrame#stats { background:#1a241b; border-radius:16px; }
            QFrame#tile { background:#222d23; border:1px solid #354a32; border-radius:11px; }
            QLabel#number { font-size:26px; font-weight:800; }
            QPushButton { color:#ebf9e5; background:#243025; border:1px solid #3c523a;
                border-radius:12px; padding:11px; }
            QPushButton:hover { background:#314a2d; border-color:#76b900; }
            QPushButton:disabled { background:#294525; border:2px solid #76b900; }
            QPushButton#profile { font-size:15px; text-align:left; font-weight:700; }
            QDialog { background:#19201a; }
            QLineEdit, QComboBox { background:#273329; padding:7px; }
        """)

    def update_labels(self):
        for watts, _, desc in PROFILES:
            self.buttons[watts].setText(f"   {self.cfg['names'][str(watts)]}    {watts} W\n   {desc}")

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu(self)
        show = menu.addAction('Mostrar ventana')
        show.triggered.connect(self.show_normal)
        menu.addSeparator()
        for watts, _, _ in PROFILES:
            action = QAction(f"{self.cfg['names'][str(watts)]} · {watts} W", menu)
            action.triggered.connect(lambda checked=False, w=watts: self.apply(w))
            menu.addAction(action)
        menu.addSeparator()
        option = menu.addAction('Personalizar')
        option.triggered.connect(self.configure)
        close = menu.addAction('Salir')
        close.triggered.connect(self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_normal() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def show_normal(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def quit_app(self):
        if self.tray:
            self.tray.hide()
        self.app.quit()

    def refresh(self):
        if self.busy:
            return
        try:
            name, limit, power, temperature, load = gpu()
            self.last_limit = limit
            self.name.setText(name)
            for key, value, unit in [('limit',limit,'W'),('power',power,'W'),
                                     ('temp',temperature,'°C'),('load',load,'%')]:
                self.metrics[key].setText(f'{value:.1f} {unit}' if key == 'power' else f'{value:.0f} {unit}')
            for watts, button in self.buttons.items():
                button.setEnabled(abs(limit - watts) >= .5)
            if self.tray:
                self.tray.setToolTip(f'GPU · {limit:.0f} W · {temperature:.0f} °C')
        except (OSError, ValueError, StopIteration, subprocess.SubprocessError) as exc:
            self.status.setText(f'Error al consultar NVIDIA: {exc}')
            for button in self.buttons.values():
                button.setEnabled(False)

    def apply(self, watts, automatic=False):
        if self.busy or watts not in (280, 320, 360):
            return
        if self.last_limit is not None and abs(self.last_limit - watts) < .5:
            return
        question = f'¿Aplicar el límite {watts} W a la GPU 0?\n\nKDE pedirá permisos de administrador.'
        if QMessageBox.question(self, 'Confirmar perfil', question,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) != QMessageBox.Yes:
            if automatic:
                self.suppressed_until = time.monotonic() + 300
            return
        self.busy = True
        self.status.setText(f'Aplicando {watts} W…')
        for button in self.buttons.values():
            button.setEnabled(False)
        self.proc = QProcess(self)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        self.proc.start(PKEXEC, [SMI, '-i', '0', '-pl', str(watts)])

    def process_error(self, _):
        if self.proc and self.proc.state() == QProcess.NotRunning:
            self.status.setText(f'Error de autorización: {self.proc.errorString()}')
            self.busy = False
            self.refresh()

    def finished(self, code, _):
        errors = bytes(self.proc.readAllStandardError()).decode(errors='replace').strip()
        self.status.setText('Perfil aplicado.' if code == 0 else
                            f'No se pudo aplicar ({code}): {errors[:180]}')
        self.busy = False
        self.proc.deleteLater()
        self.proc = None
        self.refresh()

    def configure(self):
        dlg = RulesDialog(self.cfg, self)
        if dlg.exec() != QDialog.Accepted:
            return
        for watts, edit in dlg.fields.items():
            if edit.text().strip():
                self.cfg['names'][str(watts)] = edit.text().strip()[:40]
        self.cfg['auto'] = dlg.auto.isChecked()
        self.cfg['games'] = dlg.rules
        save_config(self.cfg)
        self.update_labels()
        self.status.setText('Preferencias guardadas.')

    def check_games(self):
        if not self.cfg['auto'] or self.busy or time.monotonic() < self.suppressed_until:
            return
        rules = [r for r in self.cfg['games']
                 if str(r.get('process','')).strip() and r.get('watts') in (280,320,360)]
        if not rules:
            return
        matches = set()
        try:
            for pid in os.listdir('/proc'):
                if not pid.isdecimal():
                    continue
                try:
                    matches.add((Path('/proc') / pid / 'comm').read_text().strip().lower())
                except OSError:
                    pass
        except OSError:
            return
        selected = next((r for r in rules
                         if r['process'].lower()[:15] in matches or
                            r['process'].lower() in matches), None)
        key = (selected['process'].lower(), selected['watts']) if selected else None
        if key != self.last_rule:
            self.last_rule = key
            if selected and (self.last_limit is None or
                             abs(self.last_limit - selected['watts']) >= .5):
                self.apply(selected['watts'], automatic=True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('NVIDIA Power Control')
    app.setDesktopFileName('local.gpu-profiles')
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    window = Window(app)
    window.show()
    sys.exit(app.exec())

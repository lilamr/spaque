"""
dialogs/connection_dialog.py — PostGIS connection setup dialog
"""

from __future__ import annotations
from typing import Optional, Tuple

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel, QFrame,
    QApplication,
)

from core.domain.value_objects import ConnectionParams
from utils.logger import get_logger

logger = get_logger("spaque.dialogs.connection")


class _PingWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, params: ConnectionParams, parent=None):
        super().__init__(parent)
        self._params = params

    def run(self):
        import psycopg2
        p = self._params
        try:
            conn = psycopg2.connect(
                host=p.host, port=p.port, dbname=p.dbname,
                user=p.user, password=p.password, connect_timeout=6,
            )
            cur = conn.cursor()
            cur.execute("SELECT PostGIS_Version()")
            ver = cur.fetchone()[0].split()[0]
            conn.close()
            self.done.emit(True, f"PostGIS {ver}")
        except Exception as exc:
            self.done.emit(False, str(exc))


class ConnectionDialog(QDialog):

    params_accepted = pyqtSignal(ConnectionParams)

    def __init__(self, initial: Optional[ConnectionParams] = None, parent=None):
        super().__init__(parent)
        self._initial = initial
        self.setWindowTitle("Koneksi ke PostGIS")
        self.setFixedSize(440, 410)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()
        if initial:
            self._fill(initial)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(88)
        hdr.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #1e2a4a,stop:1 #13151a);"
            "border-bottom:1px solid #2d3340;}"
        )
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(24, 18, 24, 18)
        t1 = QLabel("🗄️  Koneksi Database PostGIS")
        t1.setStyleSheet(
            "font-size:16px;font-weight:bold;color:#e0e6f0;"
            "background:transparent;border:none;"
        )
        t2 = QLabel("Masukkan kredensial PostgreSQL + PostGIS")
        t2.setStyleSheet("font-size:11px;color:#6a7590;background:transparent;border:none;")
        hl.addWidget(t1)
        hl.addWidget(t2)
        layout.addWidget(hdr)

        # Form
        body = QFrame()
        body.setStyleSheet("QFrame{background:#1a1d23;border:none;}")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        lbl = lambda t: self._lbl(t)

        self.host_edit  = QLineEdit("localhost")
        self.port_spin  = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(5432)
        self.port_spin.setFixedWidth(100)
        self.db_edit    = QLineEdit()
        self.db_edit.setPlaceholderText("nama_database")
        self.user_edit  = QLineEdit("postgres")
        self.pass_edit  = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("••••••••")

        form.addRow(lbl("Host"), self.host_edit)
        form.addRow(lbl("Port"), self.port_spin)
        form.addRow(lbl("Database"), self.db_edit)
        form.addRow(lbl("Username"), self.user_edit)
        form.addRow(lbl("Password"), self.pass_edit)
        bl.addLayout(form)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size:11px;color:#6a7590;")
        bl.addWidget(self._status)

        # Buttons
        br = QHBoxLayout()
        br.setSpacing(8)
        cancel = QPushButton("Batal")
        cancel.setObjectName("secondary")
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)

        self._test_btn = QPushButton("Test Koneksi")
        self._test_btn.setObjectName("secondary")
        self._test_btn.setFixedHeight(38)
        self._test_btn.clicked.connect(self._test)

        self._conn_btn = QPushButton("  Hubungkan")
        self._conn_btn.setFixedHeight(38)
        self._conn_btn.setDefault(True)
        self._conn_btn.clicked.connect(self._connect)

        br.addWidget(cancel)
        br.addStretch()
        br.addWidget(self._test_btn)
        br.addWidget(self._conn_btn)
        bl.addLayout(br)

        layout.addWidget(body)
        self.pass_edit.returnPressed.connect(self._connect)

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
        return lbl

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _current_params(self) -> ConnectionParams:
        return ConnectionParams(
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            dbname=self.db_edit.text().strip(),
            user=self.user_edit.text().strip(),
            password=self.pass_edit.text(),
        )

    def _fill(self, p: ConnectionParams):
        self.host_edit.setText(p.host)
        self.port_spin.setValue(p.port)
        self.db_edit.setText(p.dbname)
        self.user_edit.setText(p.user)

    def _set_status(self, msg: str, ok: Optional[bool] = None):
        self._status.setText(msg)
        if ok is True:
            color = "#1e9e6a"
        elif ok is False:
            color = "#e03c4a"
        else:
            color = "#a0aab8"
        self._status.setStyleSheet(f"font-size:11px;color:{color};")

    def _test(self):
        self._set_status("⏳ Menguji koneksi…")
        QApplication.processEvents()
        params = self._current_params()
        self._set_buttons_enabled(False)
        self._worker = _PingWorker(params)
        self._worker.done.connect(self._on_test_done)
        self._worker.start()

    def _on_test_done(self, ok: bool, msg: str):
        self._set_buttons_enabled(True)
        if ok:
            self._set_status(f"✅ Berhasil — {msg}", ok=True)
        else:
            self._set_status(f"❌ {msg[:140]}", ok=False)

    def _connect(self):
        params = self._current_params()
        if not params.dbname:
            self._set_status("⚠️ Nama database tidak boleh kosong", ok=False)
            return
        self._set_buttons_enabled(False)
        self._conn_btn.setText("Menghubungkan…")
        self._set_status("⏳ Menghubungkan…")
        QApplication.processEvents()
        self._worker = _PingWorker(params)
        self._worker.done.connect(
            lambda ok, msg: self._on_connect_done(ok, msg, params))
        self._worker.start()

    def _on_connect_done(self, ok: bool, msg: str, params: ConnectionParams):
        self._set_buttons_enabled(True)
        self._conn_btn.setText("  Hubungkan")
        if ok:
            self._set_status(f"✅ {msg}", ok=True)
            QApplication.processEvents()
            self.params_accepted.emit(params)
            self.accept()
        else:
            self._set_status(f"❌ {msg[:140]}", ok=False)

    def _set_buttons_enabled(self, enabled: bool):
        self._conn_btn.setEnabled(enabled)
        self._test_btn.setEnabled(enabled)

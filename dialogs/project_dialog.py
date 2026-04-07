"""
dialogs/project_dialog.py
Dua dialog:
  1. ProjectPropertiesDialog  — edit nama & deskripsi project
  2. RecentProjectsDialog     — pilih dari daftar project terakhir
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QFrame, QListWidget, QListWidgetItem,
    QMessageBox, QSizePolicy,
)

from core.project.model import ProjectState
from core.project.serializer import ProjectSerializer


# ── 1. Project Properties ─────────────────────────────────────────────────────

class ProjectPropertiesDialog(QDialog):
    """Edit nama dan deskripsi project."""

    def __init__(self, state: ProjectState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setWindowTitle("Properti Project")
        self.setFixedSize(460, 300)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(70)
        hdr.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #1e2a4a,stop:1 #13151a);"
            "border-bottom:1px solid #2d3340;"
        )
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(20, 14, 20, 14)
        t1 = QLabel("📁  Properti Project")
        t1.setStyleSheet(
            "font-size:15px;font-weight:bold;color:#e0e6f0;"
            "background:transparent;border:none;"
        )
        t2 = QLabel(f"Dibuat: {self._state.created_at[:10]}   ·   "
                    f"Diupdate: {self._state.updated_at[:10]}")
        t2.setStyleSheet("font-size:10px;color:#6a7590;background:transparent;border:none;")
        hl.addWidget(t1)
        hl.addWidget(t2)
        layout.addWidget(hdr)

        # Form
        body = QFrame()
        body.setStyleSheet("background:#1a1d23;border:none;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
            return l

        self._name_edit = QLineEdit(self._state.name)
        self._name_edit.setFixedHeight(32)
        self._name_edit.setPlaceholderText("Nama project…")

        self._desc_edit = QTextEdit(self._state.description)
        self._desc_edit.setFixedHeight(70)
        self._desc_edit.setPlaceholderText("Deskripsi singkat (opsional)…")

        form.addRow(lbl("Nama:"), self._name_edit)
        form.addRow(lbl("Deskripsi:"), self._desc_edit)
        bl.addLayout(form)

        # Buttons
        br = QHBoxLayout()
        cancel = QPushButton("Batal")
        cancel.setObjectName("secondary")
        cancel.setFixedHeight(34)
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Simpan")
        ok.setFixedHeight(34)
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        br.addStretch()
        br.addWidget(cancel)
        br.addWidget(ok)
        bl.addLayout(br)

        layout.addWidget(body)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Peringatan", "Nama project tidak boleh kosong")
            return
        self._state.name        = name
        self._state.description = self._desc_edit.toPlainText().strip()
        self.accept()


# ── 2. Recent Projects ────────────────────────────────────────────────────────

class RecentProjectsDialog(QDialog):
    """Tampilkan daftar project yang baru dibuka, pilih salah satu."""

    file_selected = pyqtSignal(Path)

    def __init__(self, recent_paths: List[Path], parent=None):
        super().__init__(parent)
        self._paths = recent_paths
        self.setWindowTitle("Buka Project Terakhir")
        self.resize(580, 420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(
            "background:#13151a;border-bottom:1px solid #2d3340;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("🕐  Project Terakhir")
        t.setStyleSheet(
            "font-size:15px;font-weight:bold;color:#e0e6f0;background:transparent;"
        )
        hl.addWidget(t)
        layout.addWidget(hdr)

        # List
        body = QFrame()
        body.setStyleSheet("background:#1a1d23;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(8)

        if not self._paths:
            empty = QLabel("Belum ada project yang pernah dibuka.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#6a7590;font-size:12px;")
            bl.addWidget(empty)
        else:
            self._list = QListWidget()
            self._list.setAlternatingRowColors(True)
            self._list.setStyleSheet("""
                QListWidget {
                    background:#13151a;border:1px solid #2d3340;
                    border-radius:6px;outline:none;
                }
                QListWidget::item {
                    padding:10px 12px;border-bottom:1px solid #1e2229;
                }
                QListWidget::item:hover    { background:#1e2229; }
                QListWidget::item:selected { background:#2e5bff22; color:#6699ff; }
                QListWidget::item:alternate { background:#161920; }
            """)
            self._list.itemDoubleClicked.connect(self._open_selected)

            for path in self._paths:
                meta  = ProjectSerializer.peek_metadata(path)
                name  = meta.get("name", path.stem)
                db    = meta.get("db_name", "")
                date  = meta.get("updated_at", "")[:16].replace("T", "  ")
                item  = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setText(
                    f"📁  {name}\n"
                    f"    {path}   ·   {db}   ·   {date}"
                )
                self._list.addItem(item)

            bl.addWidget(self._list, 1)

        layout.addWidget(body, 1)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(52)
        footer.setStyleSheet("background:#13151a;border-top:1px solid #2d3340;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 8, 16, 8)

        cancel = QPushButton("Batal")
        cancel.setObjectName("secondary")
        cancel.setFixedHeight(34)
        cancel.clicked.connect(self.reject)

        open_btn = QPushButton("Buka Project")
        open_btn.setFixedHeight(34)
        open_btn.clicked.connect(self._open_selected)

        fl.addStretch()
        fl.addWidget(cancel)
        fl.addWidget(open_btn)
        layout.addWidget(footer)

    def _open_selected(self):
        if not hasattr(self, "_list"):
            self.reject()
            return
        items = self._list.selectedItems()
        if not items:
            QMessageBox.information(self, "Info", "Pilih project dari daftar")
            return
        path: Path = items[0].data(Qt.ItemDataRole.UserRole)
        self.file_selected.emit(path)
        self.accept()


# ── 3. Save confirmation (unsaved changes) ────────────────────────────────────

def ask_save_changes(parent, project_name: str) -> str:
    """
    Show 'unsaved changes' dialog.
    Returns: 'save' | 'discard' | 'cancel'
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle("Simpan Perubahan?")
    msg.setText(f"Project <b>{project_name}</b> mempunyai perubahan yang belum disimpan.")
    msg.setInformativeText("Simpan sebelum menutup?")
    msg.setIcon(QMessageBox.Icon.Question)

    save_btn    = msg.addButton("💾  Simpan",  QMessageBox.ButtonRole.AcceptRole)
    discard_btn = msg.addButton("Buang",       QMessageBox.ButtonRole.DestructiveRole)
    cancel_btn  = msg.addButton("Batal",       QMessageBox.ButtonRole.RejectRole)

    msg.exec()
    clicked = msg.clickedButton()
    if clicked == save_btn:
        return "save"
    if clicked == discard_btn:
        return "discard"
    return "cancel"

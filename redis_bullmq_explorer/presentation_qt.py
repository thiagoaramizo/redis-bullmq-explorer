import os
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QMessageBox,
    QProgressBar,
    QHeaderView,
    QFrame,
    QSizePolicy,
    QDialog,
    QPlainTextEdit,
    QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QCursor, QGuiApplication

from redis_bullmq_explorer.application_explorer import ExplorerService
from redis_bullmq_explorer.domain_models import Queue
from redis_bullmq_explorer.theme import Theme


class StatusCard(QFrame):
    clicked = Signal(str) # Emits status name when clicked

    def __init__(self, status: str, color: str, count: int = 0):
        super().__init__()
        self.status = status
        self.base_color = color
        self.count = count
        self.is_selected = False
        
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(140, 45) # Adjusted for horizontal layout
        
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        self.status_label = QLabel(self.status.upper())
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # Use system font instead of Segoe UI which might be missing
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        self.status_label.setFont(font)
        
        self.count_label = QLabel(str(self.count))
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font_count = QFont()
        font_count.setBold(True)
        font_count.setPointSize(12)
        self.count_label.setFont(font_count)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.count_label, 1)

    def set_count(self, count: int):
        self.count = count
        self.count_label.setText(str(count))

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            bg = self.base_color
            text_color = "white"
            border = f"2px solid {self.base_color}"
        else:
            bg = Theme.INPUT_BG
            text_color = self.base_color
            border = f"1px solid {Theme.BORDER}"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
                border: none;
            }}
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.status)


class Worker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class JobDetailDialog(QDialog):
    def __init__(self, job_id: str, job_state: str, job_name: str, job_data: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.job_data = job_data
        self.setWindowTitle("Job details")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        header_layout = QHBoxLayout()
        id_label = QLabel(f"ID: {job_id}")
        name_label = QLabel(f"Name: {job_name}")
        state_label = QLabel(f"State: {job_state}")
        header_layout.addWidget(id_label)
        header_layout.addStretch()
        header_layout.addWidget(state_label)
        layout.addLayout(header_layout)
        name_row = QHBoxLayout()
        name_row.addWidget(name_label)
        layout.addLayout(name_row)
        self.data_edit = QPlainTextEdit()
        self.data_edit.setReadOnly(True)
        self.data_edit.setPlainText(job_data)
        layout.addWidget(self.data_edit)
        buttons_layout = QHBoxLayout()
        copy_id_btn = QPushButton("Copy ID")
        copy_id_btn.clicked.connect(self.copy_id)
        copy_data_btn = QPushButton("Copy Data")
        copy_data_btn.clicked.connect(self.copy_data)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(copy_id_btn)
        buttons_layout.addWidget(copy_data_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {Theme.WINDOW_BG};
                color: {Theme.WINDOW_TEXT};
            }}
            QPlainTextEdit {{
                background-color: {Theme.INPUT_BG};
                border: 1px solid {Theme.BORDER};
                color: {Theme.WINDOW_TEXT};
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 12px;
            }}
            """
        )

    def copy_id(self):
        QGuiApplication.clipboard().setText(self.job_id)

    def copy_data(self):
        QGuiApplication.clipboard().setText(self.job_data)


class MainWindow(QWidget):
    def __init__(self, service: ExplorerService):
        super().__init__()
        self.service = service
        self.current_queue: Queue | None = None
        self.redis_info_label: QLabel | None = None
        self.worker = None
        self._zombie_workers = set()
        
        # Pagination & Search State
        self.current_page = 1
        self.page_size = 20
        self.total_jobs = 0
        self.current_search = ""
        self.current_status_filter = ""
        self.current_sort_column = "timestamp"
        self.current_sort_descending = True
        
        self.status_colors = {
            "wait": Theme.STATUS_WAIT,
            "active": Theme.STATUS_ACTIVE,
            "delayed": Theme.STATUS_DELAYED,
            "completed": Theme.STATUS_COMPLETED,
            "failed": Theme.STATUS_FAILED,
        }
        self.status_cards = {}
        self.auto_refresh_indicator: QLabel | None = None
        self.auto_refresh_loading = False
        self._last_refresh_was_auto = False
        
        # Auto Refresh
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(3000)
        self.auto_refresh_timer.timeout.connect(lambda: self.refresh_jobs(silent=True, auto=True))
        
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("BullMQ Explorer")
        
        # Setup Icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.resize(1200, 800)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {Theme.WINDOW_BG};
                color: {Theme.WINDOW_TEXT};
                font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
                font-size: 13px;
            }}
            QLineEdit {{
                background-color: {Theme.INPUT_BG};
                border: 1px solid {Theme.BORDER};
                padding: 8px 12px;
                border-radius: 6px;
                selection-background-color: {Theme.SELECTION_BG};
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.FOCUS_BORDER};
            }}
            QPushButton {{
                background-color: {Theme.PRIMARY};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {Theme.PRIMARY_PRESSED};
            }}
            QPushButton#RefreshBtn {{
                background-color: {Theme.WINDOW_BG};
                color: {Theme.WINDOW_OFF_TEXT};
            }}
            QPushButton#RefreshBtn:hover {{
                background-color: {Theme.PRIMARY_PRESSED};
                color: {Theme.WINDOW_TEXT};
            }}
            QPushButton#ViewBtn {{
                background-color: {Theme.TABLE_BG};
                padding: 4px 10px;
                font-size: 10px;
                border-radius: 0px;
                color: white;
            }}
            QPushButton#ViewBtn:hover {{
                background-color: {Theme.PRIMARY};
            }}
            QPushButton#DeleteBtn {{
                background-color: {Theme.DANGER};
                padding: 4px 10px;
                font-size: 10px;
                border-radius: 0px;
            }}
            QPushButton#DeleteBtn:hover {{
                background-color: {Theme.DANGER_HOVER};
            }}
            QTableWidget {{
                background-color: {Theme.TABLE_BG};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                gridline-color: {Theme.GRIDLINE};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableWidget::item:selected {{
                background-color: {Theme.PRIMARY};
                color: white;
            }}
            QHeaderView::section {{
                background-color: {Theme.HEADER_BG};
                color: {Theme.HEADER_TEXT};
                border: none;
                padding: 8px;
                font-weight: bold;
                border-bottom: 1px solid {Theme.BORDER};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {Theme.SCROLLBAR_BG};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.SCROLLBAR_HANDLE};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Theme.SCROLLBAR_HANDLE_HOVER};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {Theme.SCROLLBAR_BG};
                height: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {Theme.SCROLLBAR_HANDLE};
                min-width: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {Theme.SCROLLBAR_HANDLE_HOVER};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QSplitter::handle {{
                background-color: {Theme.SPLITTER_HANDLE};
            }}
            QCheckBox#AutoRefreshCb {{
                margin-right: 6px;
            }}
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(15)

        # Header
        header_frame = QFrame()
        header_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.conn_edit = QLineEdit()
        self.conn_edit.setPlaceholderText("redis://localhost:6379/0")
        self.conn_edit.setText("redis://localhost:6379/0")  # Default convenient value
        
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Prefix (e.g. bull)")
        self.prefix_edit.setText("bull")
        self.prefix_edit.setFixedWidth(120)
        
        connect_btn = QPushButton("Connect")
        connect_btn.setCursor(Qt.PointingHandCursor)
        connect_btn.clicked.connect(self.on_connect_clicked)
        
        header_layout.addWidget(QLabel("Redis URL:"))
        header_layout.addWidget(self.conn_edit, 1)
        header_layout.addWidget(QLabel("Prefix:"))
        header_layout.addWidget(self.prefix_edit)
        header_layout.addWidget(connect_btn)
        
        root_layout.addWidget(header_frame, 0)

        info_frame = QFrame()
        info_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        self.redis_info_label = QLabel("Redis: not connected")
        self.redis_info_label.setStyleSheet(
            f"color: {Theme.WINDOW_OFF_TEXT}; font-size: 11px;"
        )
        info_layout.addWidget(self.redis_info_label)
        info_layout.addStretch()
        root_layout.addWidget(info_frame, 0)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: transparent; border: 0px; }} QProgressBar::chunk {{ background-color: {Theme.PRIMARY}; }}"
        )
        self.progress_bar.hide()
        root_layout.addWidget(self.progress_bar, 0)

        # Main Content
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(10) # Increased handle width for spacing
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
            }
        """)

        # Queues Table
        self.queues_table = QTableWidget()
        self.queues_table.setColumnCount(1)
        self.queues_table.setHorizontalHeaderLabels(["Queues"])
        self.queues_table.verticalHeader().setVisible(False)
        self.queues_table.horizontalHeader().setStretchLastSection(True)
        self.queues_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queues_table.setSelectionMode(QTableWidget.SingleSelection)
        self.queues_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.queues_table.setShowGrid(False)
        self.queues_table.setAlternatingRowColors(True)
        self.queues_table.setStyleSheet(
            f"QTableWidget {{ alternate-background-color: {Theme.ALT_ROW_BG}; }}"
        )
        self.queues_table.cellClicked.connect(self.on_queue_selected)

        # Jobs Area Container
        jobs_widget = QWidget()
        jobs_layout = QVBoxLayout(jobs_widget)
        jobs_layout.setContentsMargins(0, 0, 0, 0)
        jobs_layout.setSpacing(15)

        # Status Cards
        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(10)
        
        # Initialize cards (hidden or with 0 count)
        for status, color in self.status_colors.items():
            card = StatusCard(status, color, 0)
            card.clicked.connect(self.on_status_card_clicked)
            self.status_layout.addWidget(card)
            self.status_cards[status] = card
            
        self.status_layout.addStretch()
        
        self.auto_refresh_cb = QCheckBox()
        self.auto_refresh_cb.setObjectName("AutoRefreshCb")
        self.auto_refresh_cb.setCursor(Qt.PointingHandCursor)
        self.auto_refresh_cb.stateChanged.connect(self.on_auto_refresh_toggled)
        
        self.auto_refresh_indicator = QLabel()
        self.auto_refresh_indicator.setFixedSize(8, 8)
        self.auto_refresh_indicator.setStyleSheet(f"background-color: {Theme.WINDOW_OFF_TEXT}; border-radius: 4px;")
        
        auto_label = QLabel("Auto-refresh (3s)")
        auto_label.setStyleSheet(f"color: {Theme.WINDOW_OFF_TEXT}; font-size: 11px;")
        
        auto_layout = QHBoxLayout()
        auto_layout.setContentsMargins(0, 0, 0, 0)
        auto_layout.setSpacing(6)
        auto_layout.addWidget(self.auto_refresh_cb)
        auto_layout.addWidget(self.auto_refresh_indicator)
        auto_layout.addWidget(auto_label)
        
        auto_widget = QWidget()
        auto_widget.setLayout(auto_layout)
        
        self.status_layout.addWidget(auto_widget)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("RefreshBtn")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_jobs)
        self.status_layout.addWidget(refresh_btn)
        
        jobs_layout.addLayout(self.status_layout)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in Data...")
        self.search_input.returnPressed.connect(self.on_search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.on_search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        jobs_layout.addLayout(search_layout)

        # Jobs Table
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(6)
        self.jobs_table.setHorizontalHeaderLabels(["ID", "Name", "State", "Created At", "Data", "Actions"])
        self.jobs_table.verticalHeader().setVisible(False)
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.jobs_table.setSelectionMode(QTableWidget.SingleSelection)
        self.jobs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.jobs_table.setShowGrid(False)
        self.jobs_table.setAlternatingRowColors(True)
        # Disable client-side sorting as we will use server-side
        self.jobs_table.setSortingEnabled(False)
        self.jobs_table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.jobs_table.setStyleSheet(
            f"QTableWidget {{ alternate-background-color: {Theme.ALT_ROW_BG}; }}"
        )
        
        header = self.jobs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # State
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Created At
        header.setSectionResizeMode(4, QHeaderView.Stretch)          # Data
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.jobs_table.setColumnWidth(5, 140)
        
        jobs_layout.addWidget(self.jobs_table)

        # Pagination Controls
        pag_layout = QHBoxLayout()
        self.prev_btn = QPushButton("<< Prev")
        self.prev_btn.setFixedWidth(80)
        self.prev_btn.clicked.connect(self.on_prev_page)
        
        self.next_btn = QPushButton("Next >>")
        self.next_btn.setFixedWidth(80)
        self.next_btn.clicked.connect(self.on_next_page)
        
        self.page_label = QLabel("Page 1")
        self.page_label.setStyleSheet(
            f"color: {Theme.PAGE_LABEL_COLOR}; font-weight: bold;"
        )
        self.page_label.setAlignment(Qt.AlignCenter)
        
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet(f"color: {Theme.TOTAL_LABEL_COLOR};")
        self.total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        pag_layout.addWidget(self.prev_btn)
        pag_layout.addWidget(self.page_label)
        pag_layout.addWidget(self.next_btn)
        pag_layout.addStretch()
        pag_layout.addWidget(self.total_label)
        
        jobs_layout.addLayout(pag_layout)

        splitter.addWidget(self.queues_table)
        splitter.addWidget(jobs_widget)
        
        # Set better initial sizes (roughly 33% queues, 67% jobs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setCollapsible(0, False)

        root_layout.addWidget(splitter, 1)

        footer_frame = QFrame()
        footer_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)

        footer_left = QLabel("BullMQ Explorer V0.1.0")
        footer_left.setStyleSheet(
            f"color: {Theme.WINDOW_OFF_TEXT}; font-size: 11px;"
        )
        footer_layout.addWidget(footer_left)

        footer_layout.addStretch()

        footer_right = QLabel(
            '<a href="https://github.com/thiagoaramizo/redis-bullmq-explorer">Contribute on GitHub</a>'
        )
        footer_right.setTextFormat(Qt.RichText)
        footer_right.setTextInteractionFlags(Qt.TextBrowserInteraction)
        footer_right.setOpenExternalLinks(True)
        footer_right.setStyleSheet(
            f"color: {Theme.WINDOW_OFF_TEXT}; font-size: 11px;"
        )
        footer_layout.addWidget(footer_right)

        root_layout.addWidget(footer_frame, 0)

    def show_error(self, text: str):
        QMessageBox.critical(self, "Error", text)

    def set_loading(self, loading: bool):
        if loading:
            self.progress_bar.show()
            self.setEnabled(False)
        else:
            self.progress_bar.hide()
            self.setEnabled(True)

    def on_connect_clicked(self):
        url = self.conn_edit.text().strip()
        if not url:
            self.show_error("Please enter a Redis connection string.")
            return
        prefix = self.prefix_edit.text().strip() or "bull"
        
        self.set_loading(True)
        worker = Worker(self._connect_and_list, url, prefix)
        self._start_worker(worker, self.on_connect_finished)

    def closeEvent(self, event):
        self.auto_refresh_timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        
        # Cleanup zombies
        for w in self._zombie_workers:
            if w.isRunning():
                w.quit()
                w.wait()
        
        # Close Redis connection
        self.service.disconnect()
        
        super().closeEvent(event)

    def _start_worker(self, worker: Worker, on_finished=None, on_error=None):
        """Helper to start a worker safely managing previous threads"""
        # If there's an existing worker running
        if self.worker and self.worker.isRunning():
            # Disconnect signals to prevent UI updates from old worker
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except Exception:
                pass
            
            # Move to zombies to keep reference alive until it finishes
            old_worker = self.worker
            self._zombie_workers.add(old_worker)
            old_worker.finished.connect(lambda: self._cleanup_zombie(old_worker))
            # Also cleanup on error just in case
            old_worker.error.connect(lambda: self._cleanup_zombie(old_worker))
        
        self.worker = worker
        if on_finished:
            self.worker.finished.connect(on_finished)
        if on_error:
            self.worker.error.connect(on_error)
        else:
            self.worker.error.connect(self.on_worker_error)
            
        self.worker.start()

    def _cleanup_zombie(self, worker):
        if worker in self._zombie_workers:
            self._zombie_workers.remove(worker)
            # Ensure thread is properly quit
            worker.quit()
            worker.wait()

    def _connect_and_list(self, url, prefix):
        self.service.connect(url, prefix)
        queues = self.service.list_queues()
        info = self.service.get_redis_info()
        return queues, info

    def on_connect_finished(self, result):
        self.set_loading(False)
        queues, info = result
        self.update_queues_list(queues)
        self.update_redis_info(info)

    def on_worker_error(self, error_msg):
        self.set_loading(False)
        self._update_auto_refresh_indicator(False)
        self._last_refresh_was_auto = False
        self.show_error(f"Operation failed: {error_msg}")

    def update_queues_list(self, queues):
        self.queues_table.setRowCount(len(queues))
        for row, queue in enumerate(queues):
            item = QTableWidgetItem(queue.name)
            item.setData(Qt.UserRole, queue)
            self.queues_table.setItem(row, 0, item)
        self.current_queue = None
        self.jobs_table.setRowCount(0)

    def update_redis_info(self, info: dict | None):
        if self.redis_info_label is None:
            return
        if not info:
            self.redis_info_label.setText("Redis: not connected")
            return
        version = info.get("version", "-")
        mode = info.get("mode", "-")
        used = info.get("used_memory", "-")
        total = info.get("total_memory", "-")
        clients = info.get("clients", "-")
        text = (
            f"Redis {version} • Mode: {mode} • "
            f"Used: {used} / {total} • Clients: {clients}"
        )
        self.redis_info_label.setText(text)

    def on_queue_selected(self, row: int, column: int):
        item = self.queues_table.item(row, 0)
        if not item:
            return
        queue = item.data(Qt.UserRole)
        self.current_queue = queue
        
        # Reset Pagination & Search & Status
        self.current_page = 1
        self.current_search = ""
        self.current_status_filter = ""
        self.search_input.setText("")
        
        self.current_sort_column = "timestamp"
        self.current_sort_descending = True
        header = self.jobs_table.horizontalHeader()
        header.setSortIndicator(3, Qt.DescendingOrder)
        header.setSortIndicatorShown(True)
        self._update_auto_refresh_indicator(False)
        self._last_refresh_was_auto = False
        
        # Reset cards selection
        for card in self.status_cards.values():
            card.set_selected(False)
            card.set_count(0)
        
        self.refresh_jobs()

    def on_auto_refresh_toggled(self, state):
        if state == Qt.Checked.value:
            self.auto_refresh_timer.start()
        else:
            self.auto_refresh_timer.stop()
            self._update_auto_refresh_indicator(False)
            self._last_refresh_was_auto = False
    
    def _update_auto_refresh_indicator(self, active: bool):
        if self.auto_refresh_indicator is None:
            return
        color = Theme.PRIMARY if active else Theme.WINDOW_OFF_TEXT
        self.auto_refresh_indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 4px;"
        )
            
    def refresh_jobs(self, silent: bool = False, auto: bool = False):
        if not self.current_queue:
            return

        if self.worker and self.worker.isRunning():
            if silent:
                return
            
        if auto:
            self._last_refresh_was_auto = True
            self._update_auto_refresh_indicator(True)
        
        if not silent:
            self.set_loading(True)
        # Pass pagination params
        worker = Worker(
            self.service.list_jobs, 
            self.current_queue, 
            page=self.current_page, 
            page_size=self.page_size, 
            search_term=self.current_search,
            status_filter=self.current_status_filter,
            sort_by=self.current_sort_column,
            descending=self.current_sort_descending
        )
        self._start_worker(worker, self.on_jobs_loaded)

    def on_header_clicked(self, logical_index):
        # 0: ID, 3: Created At
        new_sort_column = "id"
        if logical_index == 3:
            new_sort_column = "timestamp"
        elif logical_index == 0:
            new_sort_column = "id"
        else:
            # Other columns not supported for server-side sort yet
            return
            
        if self.current_sort_column == new_sort_column:
            self.current_sort_descending = not self.current_sort_descending
        else:
            self.current_sort_column = new_sort_column
            self.current_sort_descending = True # Default to desc for new column (usually better for time/id)
            
        # Update header UI
        self.jobs_table.horizontalHeader().setSortIndicator(
            logical_index, 
            Qt.DescendingOrder if self.current_sort_descending else Qt.AscendingOrder
        )
        self.jobs_table.horizontalHeader().setSortIndicatorShown(True)
        
        self.current_page = 1
        self.refresh_jobs()

    def on_status_card_clicked(self, status: str):
        if self.current_status_filter == status:
            # Deselect if already selected
            self.current_status_filter = ""
            self.status_cards[status].set_selected(False)
        else:
            # Deselect previous
            if self.current_status_filter:
                self.status_cards[self.current_status_filter].set_selected(False)
            
            # Select new
            self.current_status_filter = status
            self.status_cards[status].set_selected(True)
            
        self.current_page = 1
        self.refresh_jobs()

    def on_search(self):
        term = self.search_input.text().strip()
        if term == self.current_search:
            return
        self.current_page = 1
        self.current_search = term
        self.refresh_jobs()

    def on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_jobs()

    def on_next_page(self):
        # Check if we have more pages
        max_pages = max(1, ((self.total_jobs - 1) // self.page_size) + 1)
        if self.current_page < max_pages:
            self.current_page += 1
            self.refresh_jobs()

    def on_jobs_loaded(self, result):
        # Unpack tuple
        jobs, total_count, counts = result
        self.total_jobs = total_count
        
        # Update Status Cards
        for status, count in counts.items():
            if status in self.status_cards:
                self.status_cards[status].set_count(count)
        
        self.set_loading(False)
        if self._last_refresh_was_auto:
            self._update_auto_refresh_indicator(False)
            self._last_refresh_was_auto = False
        self.jobs_table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self.jobs_table.setItem(row, 0, QTableWidgetItem(job.id))
            self.jobs_table.setItem(row, 1, QTableWidgetItem(job.name))
            
            state_item = QTableWidgetItem(job.state)
            if "failed" in job.state:
                state_item.setForeground(Qt.red)
            elif "active" in job.state:
                state_item.setForeground(Qt.green)
            elif "completed" in job.state:
                state_item.setForeground(Qt.cyan)
                
            self.jobs_table.setItem(row, 2, state_item)
            self.jobs_table.setItem(row, 3, QTableWidgetItem(job.timestamp))
            self.jobs_table.setItem(row, 4, QTableWidgetItem(job.data_preview))
            
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(2, 2, 2, 2)
            view_btn = QPushButton("View")
            view_btn.setObjectName("ViewBtn")
            view_btn.setCursor(Qt.PointingHandCursor)
            view_btn.clicked.connect(lambda checked=False, r=row: self.on_view_clicked(r))
            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("DeleteBtn")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.clicked.connect(lambda checked=False, r=row: self.on_delete_clicked(r))
            layout.addWidget(view_btn)
            layout.addWidget(delete_btn)
            self.jobs_table.setCellWidget(row, 5, container)
        
        # self.jobs_table.setSortingEnabled(True) # Removed client-side sort enable

        # Update Pagination UI
        total_pages = max(1, ((self.total_jobs - 1) // self.page_size) + 1)
        self.page_label.setText(f"Page {self.current_page} / {total_pages}")
        self.total_label.setText(f"Total: {self.total_jobs}")
        
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

    def on_view_clicked(self, row: int):
        if self.current_queue is None:
            return
        id_item = self.jobs_table.item(row, 0)
        name_item = self.jobs_table.item(row, 1)
        state_item = self.jobs_table.item(row, 2)
        if not id_item:
            return
        job_id = id_item.text()
        job_name = name_item.text() if name_item else ""
        job_state = state_item.text() if state_item else ""
        self.set_loading(True)
        worker = Worker(self._load_job_detail, self.current_queue, job_id, job_state, job_name)
        self._start_worker(worker, self.on_job_detail_loaded)

    def _load_job_detail(self, queue, job_id, job_state, job_name):
        detail = self.service.get_job_detail(queue, job_id)
        if not detail:
            return {
                "id": job_id,
                "name": job_name,
                "state": job_state,
                "data_json": "",
            }
        if not detail.get("state"):
            detail["state"] = job_state
        if not detail.get("name"):
            detail["name"] = job_name
        return detail

    def on_job_detail_loaded(self, detail):
        self.set_loading(False)
        data_text = detail.get("data_json") or detail.get("data_raw") or ""
        dialog = JobDetailDialog(
            detail.get("id", ""),
            detail.get("state", ""),
            detail.get("name", ""),
            data_text,
            self,
        )
        dialog.exec()

    def on_delete_clicked(self, row: int):
        if self.current_queue is None:
            return
        id_item = self.jobs_table.item(row, 0)
        if not id_item:
            return
        job_id = id_item.text()
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete job {job_id} from {self.current_queue.name}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
            
        self.set_loading(True)
        worker = Worker(
            self._delete_and_reload, 
            self.current_queue, 
            job_id,
            self.current_page,
            self.page_size,
            self.current_search,
            self.current_status_filter
        )
        self._start_worker(worker, self.on_jobs_loaded)

    def _delete_and_reload(self, queue, job_id, page, page_size, search_term, status_filter):
        self.service.delete_job(queue, job_id)
        return self.service.list_jobs(queue, page, page_size, search_term, status_filter)

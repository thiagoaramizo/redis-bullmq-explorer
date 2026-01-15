import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from redis_bullmq_explorer.application_explorer import ExplorerService
from redis_bullmq_explorer.infrastructure_redis_bullmq import RedisBullMQRepository
from redis_bullmq_explorer.presentation_qt import MainWindow


def main():
    app = QApplication(sys.argv)
    
    # Setup App Icon
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    repository = RedisBullMQRepository()
    service = ExplorerService(repository)
    window = MainWindow(service)
    window.show()
    app.exec()


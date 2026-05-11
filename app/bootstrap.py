"""Bootstrap da aplicação: setup de logging, DB e ciclo Qt."""
from __future__ import annotations

import sys

from app.database import init_db
from app.utils.logger import get_logger, setup_logging


def run() -> int:
    setup_logging()
    log = get_logger("boot")
    log.info("Inicializando Brainy Prospect…")
    init_db()

    # importa Qt apenas após o setup
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_dark_theme

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Brainy Prospect")
    app.setOrganizationName("BrainyProspect")

    from app.paths import LOGO_PATH
    if LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))

    apply_dark_theme(app)

    window = MainWindow()
    window.show()

    # cleanup global de QThreads ao sair (evita SIGABRT no shutdown)
    def _shutdown_threads() -> None:
        try:
            from PySide6.QtCore import QThread
            from PySide6.QtWidgets import QApplication as _QA
            app_ref = _QA.instance()
            if app_ref is None:
                return
            for obj in app_ref.findChildren(QThread):
                try:
                    if obj.isRunning():
                        obj.requestInterruption()
                        obj.quit()
                        obj.wait(2000)
                except Exception:
                    pass
        except Exception:
            pass

    app.aboutToQuit.connect(_shutdown_threads)

    # onboarding na primeira execução
    try:
        from app.ui.onboarding import maybe_run
        maybe_run(window)
    except Exception as e:  # noqa: BLE001
        log.debug(f"onboarding falhou: {e}")

    return app.exec()

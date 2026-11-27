"""UI side of the updater: background check, banner, download with progress."""
from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QProgressBar

from ui.widgets import Dialog, label, message
from utils import updater


class _Check(QThread):
    found = Signal(dict)

    def run(self):
        update = updater.fetch_update()
        if update:
            self.found.emit(update)


class _Download(QThread):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, update, parent=None):
        super().__init__(parent)
        self.update_info = update

    def run(self):
        try:
            self.done.emit(updater.download_update(self.update_info, lambda a, b: self.progress.emit(a, b)))
        except updater.UpdateError as e:
            self.failed.emit(str(e))
        except Exception as e:  # never let a worker thread crash the app
            self.failed.emit(f"Unexpected error: {e}")


def check_in_background(window, on_none=None):
    """Look for an update without blocking; show a banner if there is one."""
    thread = _Check(window)
    thread.found.connect(lambda u: _offer(window, u))
    if on_none:
        found = []
        thread.found.connect(lambda u: found.append(u))
        thread.finished.connect(lambda: None if found else on_none())
    thread.start()
    window._update_check = thread


def _offer(window, update):
    version = update["version"]
    if updater.can_self_update():
        window.show_banner(f"Plywood Pro {version} is available.", "Update now",
                           lambda: _download(window, update))
    else:
        window.show_banner(f"Plywood Pro {version} is available.", "Open download page",
                           lambda: QDesktopServices.openUrl(QUrl(updater.RELEASES_PAGE)))


def _download(window, update):
    dlg = Dialog(window, f"Updating to {update['version']}", "Downloading and verifying the update…",
                 ok_text="", cancel_text="Cancel", width=420)
    dlg.ok_button.hide()
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setTextVisible(False)
    status = label("Starting…", "hint")
    dlg.body.addWidget(bar)
    dlg.body.addWidget(status)
    worker = _Download(update, window)

    def on_progress(done, total):
        bar.setValue(int(done / total * 100))
        status.setText(f"{done / 1e6:.1f} MB of {total / 1e6:.1f} MB")

    def on_done(zip_path):
        dlg.accept()
        try:
            updater.apply_update(zip_path)
        except updater.UpdateError as e:
            message(window, "Update not installed", str(e))
            return
        window.close()
        QApplication.quit()

    def on_failed(text):
        dlg.reject()
        message(window, "Update not installed", text + "\n\nYour current version is unchanged.")

    worker.progress.connect(on_progress)
    worker.done.connect(on_done)
    worker.failed.connect(on_failed)
    dlg.rejected.connect(lambda: worker.done.disconnect())
    worker.start()
    dlg.exec()

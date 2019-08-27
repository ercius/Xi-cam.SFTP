from xicam.plugins import DataResourcePlugin
from urllib import parse
import pysftp
import tempfile
import os
import stat
from functools import partial
from xicam.core import threads
from xicam.gui.connections import CredentialDialog

cnopts = pysftp.CnOpts()
cnopts.hostkeys = None

from xicam.core import msg

class SFTPDataResourcePlugin(DataResourcePlugin):
    name = 'SFTP'
    def __init__(self, host=None, user=None, password=None, path=''):
        if not user or not password or not host:
            dialog = CredentialDialog(addmode=False)
            dialog.exec_()
            user = dialog.username.text()
            password = dialog.password.text()
            host = dialog.host.text()

        scheme = 'sftp'
        self.name = host
        self.config = {'scheme': scheme, 'host': host, 'path': path, 'user': user, 'password': password}
        super(SFTPDataResourcePlugin, self).__init__(**self.config)

        self._data = []

        self.refresh()

    def columnCount(self, index=None):
        return len(self._data[0])

    def rowCount(self, index=None):
        return len(self._data)

    def data(self, index, role):
        from qtpy.QtCore import Qt, QVariant
        if index.isValid():
            if role == Qt.DisplayRole:
                return QVariant(self._data[index.row()].filename)
            elif role == Qt.DecorationRole:
                from qtpy.QtWidgets import QStyle, QApplication
                if self.isdir(index):
                    return QApplication.instance().style().standardIcon(QStyle.SP_DirIcon)
                else:
                    return QApplication.instance().style().standardIcon(QStyle.SP_FileIcon)

            else:
                return QVariant()

            # TODO: remove qtcore dependence

    def isdir(self, index):
        return stat.S_ISDIR(self._data[index.row()].st_mode)

    @property
    def uri(self):
        return '', '', self.config['path'], '', '', ''

    @uri.setter
    def uri(self, value):
        _, _, self.config['path'], _, _, _ = value

    def refresh(self):
        oldrows = self.rowCount()
        try:
            with pysftp.Connection(self.config['host'],
                                   username=self.config['user'],
                                   password=self.config['password'],
                                   cnopts=cnopts) as connection:
                self._data = connection.listdir_attr(remotepath=self.config['path'] or '.')

            if self.model:
                self.dataChanged(self.model.createIndex(0, 0), self.model.createIndex(max(self.rowCount(), oldrows), 0))
        except FileNotFoundError:
            pass

    def pull(self, index):
        if index.isValid():
            tmpdir = tempfile.mkdtemp()
            filename = self._data[index.row()].filename
            with pysftp.Connection(self.config['host'],
                                   username=self.config['user'],
                                   password=self.config['password'],
                                   cnopts=cnopts) as connection:
                connection.get(remotepath=os.path.join(self.config['path'], filename),
                               localpath=os.path.join(tmpdir, filename), callback=self._showProgress)
            return os.path.join(tmpdir, filename)

    def _showProgress(self, progress: int, maxprogress: int):
        threads.invoke_in_main_thread(msg.showProgress, progress, 0, maxprogress)

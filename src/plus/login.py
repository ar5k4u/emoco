#
# login.py
#
# Copyright (c) 2023, Paul Holleis, Marko Luther
# All rights reserved.
#
#
# ABOUT
# This module connects to the artisan.plus inventory management service

# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt6.QtWidgets import (QApplication, QCheckBox, QGroupBox, QHBoxLayout,
    QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QWidget)
from PyQt6.QtCore import Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QKeySequence, QAction, QDesktopServices

import logging
import requests
from artisanlib import __version__
from artisanlib.dialogs import ArtisanDialog
from plus import config, connection
from typing import Final, TYPE_CHECKING
try:
    from typing import override
except ImportError:
    from typing_extensions import override

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # noqa: F401 # pylint: disable=unused-import

_log: Final[logging.Logger] = logging.getLogger(__name__)

class Login(ArtisanDialog):

    __slots__ = [ 'login', 'passwd', 'remember', 'linkRegister', 'linkResetPassword', 'textPass', 'textName', 'rememberCheckbox' ]


    def __init__(
        self,
        parent:QWidget,
        aw:'ApplicationWindow',
        email:str|None = None,
        saved_password:str|None = None,
        remember_credentials: bool = True,
    ) -> None:
        super().__init__(parent,aw)

        self.login:str|None = None
        self.passwd:str|None = None
        self.remember:bool = remember_credentials

        register_text = QApplication.translate('Plus', 'Register')
        # registration is only possible via a one-time ticket link requested from the server by the app
        self.linkRegister = QLabel(
            f'<small><a href="#register">{register_text}</a></small>'
        )
        self.linkRegister.setOpenExternalLinks(False)
        self.linkRegister.linkActivated.connect(self.requestSignupTicket)
        self.linkRegister.setToolTip(
            QApplication.translate('Plus', 'Opens the registration page of {} in your browser').format(config.app_name)
        )
        reset_text = QApplication.translate('Plus', 'Reset Password')
        self.linkResetPassword = QLabel(
            f'<small><a href="{config.reset_passwd_url}">{reset_text}</a></small>'
        )
        self.linkResetPassword.setOpenExternalLinks(True)

        self.dialogbuttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.setButtonTranslations(
            self.dialogbuttons.button(QDialogButtonBox.StandardButton.Ok),
            'OK',
            QApplication.translate('Button', 'OK'),
        )
        self.setButtonTranslations(
            self.dialogbuttons.button(QDialogButtonBox.StandardButton.Cancel),
            'Cancel',
            QApplication.translate('Button', 'Cancel'),
        )

        self.dialogbuttons.accepted.connect(self.setCredentials)
        self.dialogbuttons.rejected.connect(self.reject)
        self.ok_button = self.dialogbuttons.button(QDialogButtonBox.StandardButton.Ok)
        if self.ok_button is not None:
            self.ok_button.setEnabled(False)
            self.ok_button.setFocusPolicy(
                Qt.FocusPolicy.StrongFocus
            )
        self.cancel_button = self.dialogbuttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.cancel_button is not None:
            self.cancel_button.setDefault(True)
            # add additional CMD-. shortcut to close the dialog
            self.cancel_button.setShortcut(
                QKeySequence('Ctrl+.')
            )
            # add additional CMD-W shortcut to close this dialog
            cancelAction:QAction = QAction(self)
            cancelAction.triggered.connect(self.reject)
            cancelAction.setShortcut(QKeySequence.StandardKey.Cancel)
            self.cancel_button.addActions(
                [cancelAction]
            )

        self.textPass:QLineEdit = QLineEdit(self)
        self.textPass.setEchoMode(QLineEdit.EchoMode.Password)
        self.textPass.setPlaceholderText(
            QApplication.translate('Plus', 'Password')
        )

        self.textName:QLineEdit = QLineEdit(self)
        self.textName.setPlaceholderText(
            QApplication.translate('Plus', 'Email')
        )
        self.textName.textChanged.connect(self.textChanged)
        if email is not None:
            self.textName.setText(email)

        self.textPass.textChanged.connect(self.textChanged)

        self.rememberCheckbox = QCheckBox(
            QApplication.translate('Plus', 'Remember')
        )
        self.rememberCheckbox.setChecked(self.remember)
        self.rememberCheckbox.stateChanged.connect(self.rememberCheckChanged)

        credentialsLayout:QVBoxLayout = QVBoxLayout(self)
        credentialsLayout.addWidget(self.textName)
        credentialsLayout.addWidget(self.textPass)
        credentialsLayout.addWidget(self.rememberCheckbox)

        credentialsGroup:QGroupBox = QGroupBox()
        credentialsGroup.setLayout(credentialsLayout)

        buttonLayout:QHBoxLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.dialogbuttons)
        buttonLayout.addStretch()

        linkLayout:QHBoxLayout = QHBoxLayout()
        linkLayout.addStretch()
        linkLayout.addWidget(self.linkRegister)
        linkLayout.addStretch()
        linkLayout.addWidget(self.linkResetPassword)
        linkLayout.addStretch()

        layout:QVBoxLayout = QVBoxLayout(self)
        layout.addWidget(credentialsGroup)
        layout.addLayout(linkLayout)
        layout.addLayout(buttonLayout)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        if saved_password is not None:
            self.passwd = saved_password
            self.textPass.setText(self.passwd)
            if self.cancel_button is not None:
                self.cancel_button.setDefault(False)
            if self.ok_button is not None:
                self.ok_button.setDefault(True)
                self.ok_button.setEnabled(True)

    @pyqtSlot()
    @override
    def reject(self) -> None:
        self.login = self.textName.text()
        super().reject()

    @pyqtSlot(int)
    def rememberCheckChanged(self, i:int) -> None:
        self.remember = bool(i)

    # requests a one-time signup ticket from the server and opens the registration page with it
    @pyqtSlot(str)
    def requestSignupTicket(self, _link:str = '') -> None:
        try:
            machine = ''
            try:
                machine = self.aw.qmc.roastertype_setup
            except Exception: # pylint: disable=broad-except
                pass
            r = requests.post(
                config.signup_ticket_url,
                json={'machine': machine, 'app_version': __version__},
                headers=connection.getHeaders(authorized=False),
                verify=config.verify_ssl,
                timeout=(config.connect_timeout, config.read_timeout),
            )
            _log.debug('-> signup ticket reply status code: %s', r.status_code)
            res = r.json() if r.headers.get('content-type', '').strip().startswith('application/json') else {}
            if r.status_code == 200 and res.get('success') and 'result' in res and 'ticket' in res['result']:
                url = res['result'].get('register_url') or f"{config.register_url}?ticket={res['result']['ticket']}"
                QDesktopServices.openUrl(QUrl(url, QUrl.ParsingMode.TolerantMode))
                return
            if r.status_code == 429:
                message = QApplication.translate('Plus', 'Too many registration requests. Please try again later.')
            else:
                message = res.get('error') or QApplication.translate('Plus', 'Registration is currently not available')
        except requests.exceptions.RequestException as e:
            _log.info(e)
            message = QApplication.translate('Plus', "Couldn't connect to {}").format(config.app_name)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            message = QApplication.translate('Plus', 'Registration is currently not available')
        self.aw.sendmessage(message)

    def isInputReasonable(self) -> bool:
        login = self.textName.text()
        passwd = self.textPass.text()
        return (
            len(passwd) >= config.min_passwd_len
            and len(login) >= config.min_login_len
            and '@' in login
            and '.' in login
        )

    @pyqtSlot(str)
    def textChanged(self, _:str) -> None:
        if self.isInputReasonable():
            if self.cancel_button is not None:
                self.cancel_button.setDefault(False)
            if self.ok_button is not None:
                self.ok_button.setDefault(True)
                self.ok_button.setEnabled(True)
        else:
            if self.cancel_button is not None:
                self.cancel_button.setDefault(True)
            if self.ok_button is not None:
                self.ok_button.setDefault(False)
                self.ok_button.setEnabled(False)

    @pyqtSlot()
    def setCredentials(self) -> None:
        self.login = self.textName.text()
        self.passwd = self.textPass.text()
        self.accept()


def plus_login(
    window: QWidget,
    aw: 'ApplicationWindow',
    email: str|None = None,
    saved_password: str|None = None,
    remember_credentials: bool = True
) -> tuple[str|None, str|None, bool, int]:
    _log.debug('plus_login()')
    ld = Login(window, aw, email, saved_password, remember_credentials)
    ld.setWindowTitle('plus')
    ld.setWindowFlags(Qt.WindowType.Sheet)
    ld.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    res:int = ld.exec()
    login_processed:str|None = ld.login.strip() if ld.login is not None else None
    return login_processed, ld.passwd, ld.remember, res

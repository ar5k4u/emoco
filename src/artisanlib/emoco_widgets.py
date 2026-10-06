#
# ABOUT
# Emoco UI widgets: the phases bar card shown below the roast graph

# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License for more details.

import logging
from typing import Final, TYPE_CHECKING

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QPaintEvent, QFont, QFontMetrics
from PyQt6.QtWidgets import QFrame, QApplication, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QSizePolicy
from PyQt6.QtCore import QSize

from artisanlib import emoco_theme
from artisanlib.util import stringfromseconds

if TYPE_CHECKING:
    from artisanlib.canvas import tgraphcanvas # pylint: disable=unused-import

_log: Final[logging.Logger] = logging.getLogger(__name__)


class PhaseSegment:
    __slots__ = ['name', 'seconds', 'active', 'known']

    def __init__(self, name:str, seconds:float, active:bool, known:bool) -> None:
        self.name = name
        self.seconds = seconds
        self.active = active   # phase is still running
        self.known = known     # phase has started (start event or threshold reached)


class PhaseBar(QFrame): # pyrefly:ignore[invalid-inheritance] # pyright: ignore [reportGeneralTypeIssues]
    """A card showing the drying, maillard and development phase as one proportional bar with their durations."""

    BAR_HEIGHT: Final[int] = 10
    GAP: Final[int] = 3

    def __init__(self, parent=None) -> None: # type: ignore[no-untyped-def]
        super().__init__(parent) # pyrefly: ignore
        self.setObjectName('phaseCard')
        self.segments:list[PhaseSegment] = []
        self.dev_ratio:float|None = None
        # incremental drying-end estimation state (see _threshold_index): scanned up to index, turning point, result
        self._scan_key:tuple[int,object,int,float]|None = None
        self._scan_pos:int = 0
        self._tp_idx:int = 0
        self._tp_val:float|None = None
        self._dry_idx:int|None = None
        self.setMinimumHeight(66)
        self.setMaximumHeight(66)
        self.setVisible(False)
        self.refreshStyle()

    def refreshStyle(self) -> None:
        self.setStyleSheet(emoco_theme.lcd_card_style().replace('lcdCard', 'phaseCard').replace('}', ' margin: 4px 2px 4px 2px; }'))
        self.update()

    # recomputes the phases from the given graph canvas data; hides the card if there is no data
    def refresh(self, qmc:'tgraphcanvas') -> None:
        try:
            timex = qmc.timex
            timeindex = qmc.timeindex
            if len(timex) < 2 or len(timeindex) < 7 or not (qmc.flagstart or timeindex[0] > -1 or timeindex[6] > 0):
                if not self.isHidden():
                    self.setVisible(False)
                return
            n = len(timex)
            if qmc.flagstart and not -1 < timeindex[0] < n:
                # recording but CHARGE not marked yet: the phases are relative to CHARGE, nothing to show
                if not self.isHidden():
                    self.setVisible(False)
                return
            charge = timeindex[0] if -1 < timeindex[0] < n else 0
            last = n - 1
            end = timeindex[6] if 0 < timeindex[6] < n else last
            finished = 0 < timeindex[6] < n
            start_t = timex[charge]
            # dry end: marked, or the moment BT first reaches the drying phase limit after the turning point
            dry_end:int|None = timeindex[1] if 0 < timeindex[1] < n else None
            if dry_end is None:
                dry_end = self._threshold_index(qmc, charge, end, qmc.phases[1])
            fcs:int|None = timeindex[2] if 0 < timeindex[2] < n else None
            segments:list[PhaseSegment] = []
            dry_name = QApplication.translate('Label', 'Drying')
            mid_name = QApplication.translate('Label', 'Maillard')
            dev_name = QApplication.translate('Label', 'Development')
            if dry_end is not None and (fcs is None or dry_end <= fcs):
                segments.append(PhaseSegment(dry_name, timex[dry_end] - start_t, False, True))
                if fcs is not None:
                    segments.append(PhaseSegment(mid_name, timex[fcs] - timex[dry_end], False, True))
                    segments.append(PhaseSegment(dev_name, timex[end] - timex[fcs], not finished, True))
                else:
                    segments.append(PhaseSegment(mid_name, timex[end] - timex[dry_end], not finished, True))
                    segments.append(PhaseSegment(dev_name, 0, False, False))
            elif fcs is not None:
                # no drying end known but FCs is: drying runs to FCs
                segments.append(PhaseSegment(dry_name, timex[fcs] - start_t, False, True))
                segments.append(PhaseSegment(mid_name, 0, False, False))
                segments.append(PhaseSegment(dev_name, timex[end] - timex[fcs], not finished, True))
            else:
                segments.append(PhaseSegment(dry_name, timex[end] - start_t, not finished, True))
                segments.append(PhaseSegment(mid_name, 0, False, False))
                segments.append(PhaseSegment(dev_name, 0, False, False))
            total = timex[end] - start_t
            dev = segments[2].seconds if segments[2].known else 0
            self.dev_ratio = (dev / total * 100.0) if total > 0 and segments[2].known else None
            self.segments = segments
            if self.isHidden():
                self.setVisible(True)
            self.update()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)

    # index where BT first reaches the drying phase limit after the turning point (minimum BT after CHARGE), or None.
    # The scan is incremental: only samples added since the last call are visited, so the per-sample cost stays constant.
    def _threshold_index(self, qmc:'tgraphcanvas', charge:int, end:int, limit:float) -> int|None:
        temp = qmc.temp2
        if len(temp) <= charge:
            return None
        # the cache is bound to this profile's data list and roast; cached indices are re-validated against the data
        key = (id(temp), getattr(qmc, 'roastUUID', None), charge, float(limit))
        stale = (self._scan_key != key or self._scan_pos > len(temp) or self._scan_pos < charge
                 or (self._tp_val is not None and (self._tp_idx >= len(temp) or temp[self._tp_idx] != self._tp_val))
                 or (self._dry_idx is not None and (self._dry_idx >= len(temp) or temp[self._dry_idx] is None or temp[self._dry_idx] < limit)))
        if stale:
            # new profile, new CHARGE, changed limit, replaced data or the data shrank (RESET): start over
            self._scan_key = key
            self._scan_pos = charge
            self._tp_idx = charge
            self._tp_val = None
            self._dry_idx = None
        if self._dry_idx is not None and self._dry_idx <= end:
            return self._dry_idx
        stop = min(end, len(temp) - 1)
        # the sampling filter may still adjust the last few BT values, so those are scanned again
        i = max(self._tp_idx, self._scan_pos - 3)
        while i <= stop:
            v = temp[i]
            if v is not None and v != -1:
                if self._tp_val is None or v < self._tp_val:
                    self._tp_val = v
                    self._tp_idx = i
                elif v >= limit and i > self._tp_idx:
                    self._dry_idx = i
                    self._scan_pos = i + 1
                    return i
            i += 1
        self._scan_pos = stop + 1
        return None

    def paintEvent(self, a0:QPaintEvent|None) -> None: # pylint: disable=unused-argument
        super().paintEvent(a0)
        if not self.segments:
            return
        t = emoco_theme.tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            margin = 12
            w = self.width() - 2 * margin
            y_title = 8
            bar_y = 30
            label_y = bar_y + self.BAR_HEIGHT + 6
            font = QFont(self.font())
            font.setPointSizeF(max(9.0, self.font().pointSizeF() - 1))
            p.setFont(font)
            bold = QFont(font)
            bold.setBold(True)
            # title
            p.setPen(QPen(QColor(t['text'])))
            p.setFont(bold)
            p.drawText(QRectF(margin, y_title, w / 2, 16), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), QApplication.translate('Table', 'Phases'))
            if self.dev_ratio is not None:
                p.setFont(font)
                p.setPen(QPen(QColor(t['muted'])))
                dev_label = QApplication.translate('Label', 'DEV%') + f'  {self.dev_ratio:.1f}%'
                p.drawText(QRectF(margin + w / 2, y_title, w / 2, 16), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), dev_label)
            # bar: segment widths are proportional to their durations; unknown phases get a small dashed placeholder
            total = sum(s.seconds for s in self.segments if s.known)
            unknown = [s for s in self.segments if not s.known]
            placeholder = 0.08 * w if unknown else 0
            avail = w - self.GAP * (len(self.segments) - 1) - placeholder * len(unknown)
            colors = [t['input_border'], t['muted'], t['text']]
            x = float(margin)
            for i, s in enumerate(self.segments):
                if s.known and total > 0:
                    sw = max(4.0, avail * s.seconds / total)
                else:
                    sw = placeholder
                rect = QRectF(x, bar_y, sw, self.BAR_HEIGHT)
                if s.known:
                    c = QColor(colors[i])
                    if s.active:
                        c.setAlphaF(0.55)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(c)
                    p.drawRoundedRect(rect, 3, 3)
                else:
                    pen = QPen(QColor(t['input_border']))
                    pen.setStyle(Qt.PenStyle.DashLine)
                    p.setPen(pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
                # label under the segment, shortened to the segment width (drop 'ongoing' first, then elide)
                p.setFont(font)
                fm = QFontMetrics(font)
                if s.known:
                    short = f'{s.name} {stringfromseconds(s.seconds, False)}'
                    label = short + (' ' + QApplication.translate('Label', 'ongoing') if s.active else '')
                    if fm.horizontalAdvance(label) > sw:
                        label = short
                    p.setPen(QPen(QColor(t['text'])))
                else:
                    label = s.name
                    p.setPen(QPen(QColor(t['muted'])))
                label = fm.elidedText(label, Qt.TextElideMode.ElideRight, max(int(sw), 10))
                align = Qt.AlignmentFlag.AlignLeft
                if i == 2:
                    align = Qt.AlignmentFlag.AlignRight
                elif i == 1:
                    align = Qt.AlignmentFlag.AlignHCenter
                p.drawText(QRectF(x, label_y, max(sw, 10.0), 16), int(align | Qt.AlignmentFlag.AlignVCenter), label)
                x += sw + self.GAP
        finally:
            p.end()


class TimerCard(QFrame): # pyrefly:ignore[invalid-inheritance] # pyright: ignore [reportGeneralTypeIssues]
    """A card holding the roast timer LCD with the recording state above and the current phase below."""

    def __init__(self, lcd:QWidget, parent=None) -> None: # type: ignore[no-untyped-def]
        super().__init__(parent) # pyrefly: ignore
        self.setObjectName('timerCard')
        self.state_label = QLabel()
        self.state_label.setObjectName('timerState')
        self.sampling_label = QLabel()
        self.sampling_label.setObjectName('timerSampling')
        self.sampling_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.phase_label = QLabel()
        self.phase_label.setObjectName('timerPhase')
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self.state_label)
        top.addStretch()
        top.addWidget(self.sampling_label)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(2)
        layout.addLayout(top)
        layout.addWidget(lcd)
        layout.addWidget(self.phase_label)
        self.setLayout(layout)
        self._last:tuple[str, str, str]|None = None
        self.refreshStyle()

    def refreshStyle(self) -> None:
        t = emoco_theme.tokens()
        self.setStyleSheet(
            f"QFrame#timerCard {{ background-color: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; }}"
            f" QLabel#timerState {{ color: {t['muted']}; font-weight: bold; }}"
            f" QLabel#timerState[recording=\"true\"] {{ color: {t['danger_text']}; }}"
            f" QLabel#timerSampling, QLabel#timerPhase {{ color: {t['muted']}; }}")
        self.update()

    # updates the state line (recording / monitoring / off), the sampling interval and the current phase
    def refresh(self, qmc:'tgraphcanvas', phases:'PhaseBar') -> None:
        try:
            if qmc.flagstart:
                state = '\u25cf ' + QApplication.translate('Label', 'Recording')
                recording = 'true'
            elif qmc.flagon:
                state = '\u25cf ' + QApplication.translate('Label', 'Monitoring')
                recording = 'false'
            else:
                state = QApplication.translate('Label', 'Standby')
                recording = 'false'
            sampling = QApplication.translate('Label', 'Sampling') + f' {qmc.delay/1000:g}s'
            phase = ''
            if phases.isVisible():
                active = next((seg for seg in phases.segments if seg.active), None)
                if active is not None:
                    phase = f'{active.name} \u00b7 {stringfromseconds(active.seconds, False)}'
                elif phases.segments and phases.segments[-1].known:
                    phase = QApplication.translate('Label', 'Total') + f' \u00b7 {stringfromseconds(sum(seg.seconds for seg in phases.segments if seg.known), False)}'
            current = (state, sampling, phase)
            if current == self._last:
                return
            self._last = current
            self.state_label.setText(state)
            if self.state_label.property('recording') != recording:
                self.state_label.setProperty('recording', recording)
                self.state_label.setStyleSheet(self.state_label.styleSheet()) # re-polish for the property selector
            self.sampling_label.setText(sampling)
            self.phase_label.setText(phase)
            self.phase_label.setVisible(phase != '')
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


class InfoCard(QFrame): # pyrefly:ignore[invalid-inheritance] # pyright: ignore [reportGeneralTypeIssues]
    """A card in the readings column holding the phase prediction LCDs (TP, DRY, FCs), the AUC LCD and the BT
    difference to the background profile. It is visible while any of them is."""

    def __init__(self, phases_lcds:QWidget, auc_lcd:QWidget, parent=None) -> None: # type: ignore[no-untyped-def]
        super().__init__(parent) # pyrefly: ignore
        self.setObjectName('infoCard')
        self.phases_lcds = phases_lcds
        self.auc_lcd = auc_lcd
        self.title_label = QLabel(QApplication.translate('Label', 'Prediction'))
        self.title_label.setObjectName('infoTitle')
        self.delta_label = QLabel()
        self.delta_label.setObjectName('infoDelta')
        self.delta_label.setVisible(False)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)
        layout.addWidget(self.title_label)
        layout.addWidget(phases_lcds)
        layout.addWidget(auc_lcd)
        layout.addWidget(self.delta_label)
        self.setLayout(layout)
        self._last_delta:str|None = None
        self.setVisible(False)
        self.refreshStyle()

    def refreshStyle(self) -> None:
        t = emoco_theme.tokens()
        self.setStyleSheet(
            f"QFrame#infoCard {{ background-color: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; }}"
            f" QLabel#infoTitle {{ color: {t['text']}; font-weight: bold; }}"
            f" QLabel#infoDelta {{ color: {t['muted']}; }}")
        self.update()

    # BT difference to the (time aligned) background profile at the latest sample, or None
    @staticmethod
    def background_delta(qmc:'tgraphcanvas') -> float|None:
        try:
            if not qmc.background or qmc.backgroundprofile is None or not qmc.flagon:
                return None
            timex, temp, timeB, tempB = qmc.timex, qmc.temp2, qmc.timeB, qmc.temp2B
            if len(timex) == 0 or len(timeB) < 2 or len(tempB) != len(timeB):
                return None
            t = timex[-1]
            v = temp[-1] if len(temp) == len(timex) else None
            if v is None or v == -1 or t < timeB[0] or t > timeB[-1]:
                return None
            import bisect # pylint: disable=import-outside-toplevel
            i = bisect.bisect_left(timeB, t)
            i = max(1, min(i, len(timeB) - 1))
            t0, t1 = timeB[i - 1], timeB[i]
            b0, b1 = tempB[i - 1], tempB[i]
            if b0 is None or b1 is None or b0 == -1 or b1 == -1:
                return None
            b = b0 if t1 == t0 else b0 + (b1 - b0) * (t - t0) / (t1 - t0)
            return float(v - b)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            return None

    def refresh(self, qmc:'tgraphcanvas') -> None:
        try:
            delta = self.background_delta(qmc)
            text = '' if delta is None else QApplication.translate('Label', 'BT vs background') + f'  {delta:+.1f}\u00b0'
            if text != self._last_delta:
                self._last_delta = text
                self.delta_label.setText(text)
                self.delta_label.setVisible(text != '')
            visible = self.phases_lcds.isVisibleTo(self) or self.auc_lcd.isVisibleTo(self) or text != ''
            if visible == self.isHidden(): # compare with the card's own state, not with the (maybe hidden) ancestors
                self.setVisible(visible)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


class ColumnScrollArea(QScrollArea): # pyrefly:ignore[invalid-inheritance] # pyright: ignore [reportGeneralTypeIssues]
    """A vertical-only scroll area whose width follows its content (used for the readings column)."""

    def __init__(self, content:QWidget, parent=None) -> None: # type: ignore[no-untyped-def]
        super().__init__(parent) # pyrefly: ignore
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        self.setStyleSheet('QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }')
        self.setWidget(content)
        # the width depends on whether the scrollbar is shown: tell the parent layout whenever that may change
        bar = self.verticalScrollBar()
        if bar is not None:
            bar.rangeChanged.connect(self._bar_changed)

    def _bar_changed(self, _minimum:int = 0, _maximum:int = 0) -> None:
        self.updateGeometry()

    def _content_width(self) -> int:
        w = self.widget()
        width = w.sizeHint().width() if w is not None else 0
        bar = self.verticalScrollBar()
        if bar is not None and bar.isVisible():
            width += bar.sizeHint().width()
        return width + 4 # a little slack so the right card border is never clipped

    def sizeHint(self) -> QSize: # pylint: disable=invalid-name
        w = self.widget()
        return QSize(self._content_width(), w.sizeHint().height() if w is not None else 0)

    def minimumSizeHint(self) -> QSize: # pylint: disable=invalid-name
        return QSize(self._content_width(), 0)

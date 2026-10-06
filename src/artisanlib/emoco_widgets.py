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
from PyQt6.QtGui import QPainter, QColor, QPen, QPaintEvent, QFont
from PyQt6.QtWidgets import QFrame, QApplication

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
                if self.isVisible():
                    self.setVisible(False)
                return
            n = len(timex)
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
            if not self.isVisible():
                self.setVisible(True)
            self.update()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)

    @staticmethod
    def _threshold_index(qmc:'tgraphcanvas', charge:int, end:int, limit:float) -> int|None:
        temp = qmc.temp2
        if len(temp) <= charge:
            return None
        # turning point: minimum BT after CHARGE
        tp = charge
        tp_v = None
        for i in range(charge, min(end, len(temp) - 1) + 1):
            v = temp[i]
            if v is not None and v != -1 and (tp_v is None or v < tp_v):
                tp_v = v
                tp = i
        for i in range(tp, min(end, len(temp) - 1) + 1):
            v = temp[i]
            if v is not None and v != -1 and v >= limit:
                return i
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
                # label under the segment
                p.setFont(font)
                if s.known:
                    label = f'{s.name} {stringfromseconds(s.seconds, False)}'
                    if s.active:
                        label += ' ' + QApplication.translate('Label', 'ongoing')
                    p.setPen(QPen(QColor(t['text'])))
                else:
                    label = s.name
                    p.setPen(QPen(QColor(t['muted'])))
                align = Qt.AlignmentFlag.AlignLeft
                if i == 2:
                    align = Qt.AlignmentFlag.AlignRight
                elif i == 1:
                    align = Qt.AlignmentFlag.AlignHCenter
                p.drawText(QRectF(x, label_y, max(sw, 10.0), 16), int(align | Qt.AlignmentFlag.AlignVCenter), label)
                x += sw + self.GAP
        finally:
            p.end()

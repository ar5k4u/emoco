#
# ABOUT
# Emoco light/dark color themes

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

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QActionGroup, QColor, QPalette
from PyQt6.QtWidgets import QMenu


if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # pylint: disable=unused-import
    from artisanlib.canvas import tgraphcanvas # pylint: disable=unused-import

_log: Final[logging.Logger] = logging.getLogger(__name__)

SETTINGS_KEY: Final[str] = 'emocoTheme'
THEME_NAMES: Final[tuple[str, str]] = ('light', 'dark')

# the color tokens of the two themes
THEMES: Final[dict[str, dict[str, str]]] = {
    'dark': {
        'bg': '#111315',            # main window and figure background
        'surface': '#1A1D21',       # plot area, cards, LCD backgrounds
        'surface2': '#22262B',      # selected items, completed buttons
        'border': '#2E333A',        # card borders, grid lines
        'input_border': '#5B6370',  # input fields, secondary buttons
        'text': '#E8EAED',
        'muted': '#9AA3AE',
        'disabled': '#6B7480',
        'window': '#1A1D21',        # dialog background
        'base': '#111315',          # input field background
        'bt': '#FFB454',
        'et': '#5C9BFF',
        'deltabt': '#FFD9A0',
        'deltaet': '#B5D0FF',
        'accent': '#FFB454',
        'accent_hover': '#FFC57A',
        'accent_pressed': '#E89A35',
        'accent_text': '#111315',
        'danger': '#FF6B6B',
        'danger_text': '#FF8A8A',
        'ok': '#5BD08A',
        'rect1': '#1F2225',         # drying phase band
        'rect2': '#25282C',         # maillard phase band
        'rect3': '#2C2F33',         # finishing phase band
        'rect4': '#1F2225',         # cooling phase band
        'rect5': '#22262B',
        'watermarks': '#3A4048',
        'event1': '#6EC1E4',
        'event2': '#7BD389',
        'event3': '#C792EA',
        'event4': '#FF8A8A',
        'event_text': '#111315',
    },
    'light': {
        'bg': '#F4F5F7',
        'surface': '#FFFFFF',
        'surface2': '#ECEEF1',
        'border': '#D5D9DF',
        'input_border': '#8A94A3',
        'text': '#1A1D21',
        'muted': '#5B6370',
        'disabled': '#9AA3AE',
        'window': '#F4F5F7',
        'base': '#FFFFFF',
        'bt': '#C2620A',
        'et': '#1F6FEB',
        'deltabt': '#D98324',
        'deltaet': '#5B95F0',
        'accent': '#FFB454',
        'accent_hover': '#FFC57A',
        'accent_pressed': '#F0962A',
        'accent_text': '#111315',
        'danger': '#D93025',
        'danger_text': '#C5221F',
        'ok': '#1E9E57',
        'rect1': '#F7F8F9',
        'rect2': '#EFF1F3',
        'rect3': '#E6E9EC',
        'rect4': '#F7F8F9',
        'rect5': '#ECEEF1',
        'watermarks': '#D5D9DF',
        'event1': '#1C7FA6',
        'event2': '#2E8B57',
        'event3': '#8E44AD',
        'event4': '#C0392B',
        'event_text': '#FFFFFF',
    },
}

_current: str = 'light'


def current() -> str:
    return _current

def is_dark() -> bool:
    return _current == 'dark'

# returns the color tokens of the given theme (of the active theme if name is None)
def tokens(name:str|None = None) -> dict[str, str]:
    return THEMES[name if name in THEMES else _current]

# returns the color of the given token of the active theme
def token(key:str) -> str:
    return THEMES[_current][key]


#### contrast helpers

def _luminance(color:str) -> float:
    c = QColor(color)
    def lin(v:float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c.redF()) + 0.7152 * lin(c.greenF()) + 0.0722 * lin(c.blueF())

def contrast(c1:str, c2:str) -> float:
    l1 = _luminance(c1)
    l2 = _luminance(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

# returns the given color, or a readable substitute if it cannot be told apart from the plot background of the active theme
def readable(color:str) -> str:
    try:
        if not QColor.isValidColor(color):
            return color
        background = token('surface')
        if contrast(color, background) >= 1.8:
            return color
        # near-black on dark or near-white on light: flip to the text color of the theme
        return token('text')
    except Exception as e: # pylint: disable=broad-except
        _log.exception(e)
        return color

# replaces extra device curve colors that are unreadable on the plot background of the active theme
def fix_extra_curve_colors(qmc:'tgraphcanvas') -> None:
    try:
        for colors in (qmc.extradevicecolor1, qmc.extradevicecolor2):
            for i, c in enumerate(colors):
                r = readable(c)
                if r != c:
                    colors[i] = r
    except Exception as e: # pylint: disable=broad-except
        _log.exception(e)


#### stylesheets

def _button(min_width:str, font_size:str, fg:str, bg:str, hover:str, pressed:str, border:str, t:dict[str, str]) -> str:
    return f"""
                QPushButton {{
                    min-width: {min_width};
                    border-style:solid; border-radius:8px; border-width:1px; border-color:{border};
                    font-size: {font_size};
                    font-weight: bold;
                    color: {fg};
                    background-color: {bg};
                }}
                QPushButton:!enabled {{
                    color: {t['disabled']};
                    background-color: {t['surface2']};
                    border-color: {t['border']};
                }}
                QPushButton:pressed {{
                    background-color: {pressed};
                }}
                QPushButton:hover:!pressed {{
                    background-color: {hover};
                }}
            """

# returns the styles of the main buttons (RESET, ON/OFF, START/STOP, PID, SV) in regular and simulator mode
def pushbutton_styles(aw:'ApplicationWindow', name:str|None = None) -> tuple[dict[str, str], dict[str, str]]:
    t = tokens(name)
    main_w = aw.main_button_min_width_str
    std_w = f'{aw.standard_button_min_width_px}px'
    size = aw.button_font_size
    small = aw.button_font_size_small
    secondary = _button(main_w, size, t['text'], t['surface'], t['surface2'], t['border'], t['input_border'], t)
    primary = _button(main_w, size, t['accent_text'], t['accent'], t['accent_hover'], t['accent_pressed'], t['accent'], t)
    recording = _button(main_w, size, t['danger_text'], t['surface'], t['surface2'], t['border'], t['danger'], t)
    active = _button(main_w, size, t['accent_text'], t['et'], t['deltaet'], t['et'], t['et'], t)
    simulator = _button(main_w, size, t['et'], t['surface'], t['surface2'], t['border'], t['et'], t)
    simulator_on = _button(main_w, size, t['danger_text'], t['surface'], t['surface2'], t['border'], t['et'], t)
    styles = {
        'RESET': secondary,
        'OFF': secondary,
        'ON': recording,
        'STOP': primary,
        'START': recording,
        'PID': secondary,
        'PIDactive': active,
        'SV +': _button(std_w, small, t['text'], t['surface'], t['surface2'], t['border'], t['danger'], t),
        'SV -': _button(std_w, small, t['text'], t['surface'], t['surface2'], t['border'], t['et'], t),
    }
    styles_simulator = {
        'OFF': simulator,
        'ON': simulator_on,
        'STOP': simulator,
        'START': simulator_on,
    }
    return styles, styles_simulator

# returns the style of the event button bar (CHARGE, DRY END, ..) with format placeholders
# min_width, min_height, padding, default_font_size and selected_font_size
def event_button_style(name:str|None = None) -> str:
    t = tokens(name)
    return f"""
            EventPushButton {{{{
                min-width: {{min_width}}px;
                min-height: {{min_height}}px;
                font-size: {{default_font_size}}pt;
                font-weight: bold;
                padding: {{padding}}px;
                border-style:solid;
                border-radius:8px;
                border-color:{t['input_border']};
                border-width:1px;
                color: {t['text']};
            }}}}

            EventPushButton[Selected=true] {{{{
                font-size: {{selected_font_size}}pt;
                color: {t['accent_text']};
                border-color: {t['accent']};
                background-color: {t['accent']};
            }}}}
            EventPushButton[Selected=true]:flat {{{{
                color: {t['muted']};
                border-color: {t['accent']};
                background-color: {t['surface2']};
            }}}}
            EventPushButton[Selected=true]:flat:!pressed:hover {{{{
                color: {t['text']};
                background-color: {t['border']};
            }}}}
            EventPushButton[Selected=true]:flat:pressed {{{{
                color: {t['text']};
                background-color: {t['border']};
            }}}}
            EventPushButton[Selected=true]:!flat:pressed {{{{
                color: {t['accent_text']};
                background-color: {t['accent_pressed']};
            }}}}
            EventPushButton[Selected=true]:!pressed:hover {{{{
                color: {t['accent_text']};
                background-color: {t['accent_hover']};
            }}}}

            EventPushButton[Selected=false]:flat {{{{
                color: {t['muted']};
                border-color: {t['border']};
                background-color: {t['surface2']};
            }}}}
            EventPushButton[Selected=false]:flat:!pressed:hover {{{{
                color: {t['text']};
                background-color: {t['border']};
            }}}}
            EventPushButton[Selected=false]:flat:pressed {{{{
                color: {t['text']};
                background-color: {t['border']};
            }}}}
            EventPushButton[Selected=false]:!flat:pressed {{{{
                background-color: {t['border']};
            }}}}
            EventPushButton[Selected=false]:!pressed:hover {{{{
                background-color: {t['surface2']};
            }}}}
"""

# returns the (horizontal) slider style of the active theme with the format placeholder color (the event color)
def slider_style() -> str:
    t = tokens()
    return f"""
            QSlider::groove:horizontal {{{{
                background: {t['border']};
                border: 0px;
                height: 6px;
                border-radius: 3px;
            }}}}
            QSlider::sub-page:horizontal {{{{
                background: {{color}};
                border: 0px;
                height: 6px;
                border-radius: 3px;
            }}}}
            QSlider::add-page:horizontal {{{{
                background: {t['border']};
                border: 0px;
                height: 6px;
                border-radius: 3px;
            }}}}
            QSlider::handle:horizontal {{{{
                background: {{color}};
                border: 2px solid {t['surface']};
                width: 16px;
                height: 16px;
                margin: -6px 0px;
                border-radius: 9px;
            }}}}
            QSlider::handle:horizontal:hover {{{{
                border: 2px solid {t['text']};
            }}}}
            QSlider::handle:horizontal:focus {{{{
                border: 2px solid {t['accent']};
            }}}}
            QSlider::sub-page:horizontal:disabled, QSlider::handle:horizontal:disabled {{{{
                background: {t['input_border']};
            }}}}
    """

# returns the style of the - / + buttons next to the event sliders
def slider_step_button_style() -> str:
    t = tokens()
    return f"""
            QPushButton#sliderStep {{ border: 1px solid {t['input_border']}; border-radius: 6px; background: {t['surface']}; color: {t['text']}; font-weight: bold; font-size: 14px; padding: 0px; }}
            QPushButton#sliderStep:hover {{ background: {t['surface2']}; }}
            QPushButton#sliderStep:pressed {{ background: {t['border']}; }}
            QPushButton#sliderStep:disabled {{ color: {t['disabled']}; border-color: {t['border']}; }}
    """

# returns the style of the reading cards (frames holding a label and an LCD)
def lcd_card_style() -> str:
    t = tokens()
    return f"QFrame#lcdCard {{ background-color: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; }}"

# returns the style of the phases and AUC LCDs
def phases_lcd_style() -> str:
    t = tokens()
    return f"QLCDNumber{{border-radius:4; border-width: 0; border-color: {t['border']}; border-style:solid; color: {t['text']}; background-color: {t['surface2']};}}"

# returns the application-wide stylesheet of the given theme
def app_stylesheet(name:str|None = None) -> str:
    t = tokens(name)
    return f"""
        QToolTip {{
            color: {t['text']};
            background-color: {t['surface2']};
            border: 1px solid {t['border']};
            padding: 3px;
        }}
        QDialog QPushButton, QMessageBox QPushButton {{
            border: 1px solid {t['input_border']};
            border-radius: 6px;
            padding: 4px 12px;
            color: {t['text']};
            background-color: {t['surface']};
        }}
        QDialog QPushButton:hover, QMessageBox QPushButton:hover {{
            background-color: {t['surface2']};
        }}
        QDialog QPushButton:pressed, QMessageBox QPushButton:pressed {{
            background-color: {t['border']};
        }}
        QDialog QPushButton:checked {{
            border-color: {t['accent']};
            background-color: {t['surface2']};
        }}
        QDialog QPushButton:default, QMessageBox QPushButton:default {{
            color: {t['accent_text']};
            border-color: {t['accent']};
            background-color: {t['accent']};
            font-weight: bold;
        }}
        QDialog QPushButton:default:hover, QMessageBox QPushButton:default:hover {{
            background-color: {t['accent_hover']};
        }}
        QDialog QPushButton:default:pressed, QMessageBox QPushButton:default:pressed {{
            background-color: {t['accent_pressed']};
        }}
        QDialog QPushButton:disabled, QMessageBox QPushButton:disabled {{
            color: {t['disabled']};
            border-color: {t['border']};
            background-color: {t['surface2']};
        }}
        QLineEdit, QPlainTextEdit, QTextEdit {{
            border: 1px solid {t['input_border']};
            border-radius: 4px;
            padding: 1px 3px;
            color: {t['text']};
            background-color: {t['base']};
            selection-color: {t['accent_text']};
            selection-background-color: {t['accent']};
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
            border-color: {t['accent']};
        }}
        QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
            color: {t['disabled']};
            border-color: {t['border']};
        }}
        QAbstractSpinBox QLineEdit, QComboBox QLineEdit, QAbstractItemView QLineEdit {{
            border: 0px;
            border-radius: 0px;
            padding: 0px;
            background-color: transparent;
        }}
        QGroupBox {{
            border: 1px solid {t['border']};
            border-radius: 8px;
            margin-top: 9px;
            padding-top: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0px 4px;
            color: {t['muted']};
        }}
    """

def app_palette(name:str|None = None) -> QPalette:
    t = tokens(name)
    p = QPalette()
    for role, key in (
            (QPalette.ColorRole.Window, 'window'),
            (QPalette.ColorRole.WindowText, 'text'),
            (QPalette.ColorRole.Base, 'base'),
            (QPalette.ColorRole.AlternateBase, 'surface2'),
            (QPalette.ColorRole.ToolTipBase, 'surface2'),
            (QPalette.ColorRole.ToolTipText, 'text'),
            (QPalette.ColorRole.Text, 'text'),
            (QPalette.ColorRole.Button, 'surface2'),
            (QPalette.ColorRole.ButtonText, 'text'),
            (QPalette.ColorRole.BrightText, 'danger'),
            (QPalette.ColorRole.Link, 'et'),
            (QPalette.ColorRole.Highlight, 'accent'),
            (QPalette.ColorRole.HighlightedText, 'accent_text'),
            (QPalette.ColorRole.PlaceholderText, 'muted'),
            (QPalette.ColorRole.Light, 'surface'),
            (QPalette.ColorRole.Midlight, 'surface2'),
            (QPalette.ColorRole.Mid, 'border'),
            (QPalette.ColorRole.Dark, 'input_border'),
            (QPalette.ColorRole.Shadow, 'bg')):
        p.setColor(role, QColor(t[key]))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.HighlightedText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t['disabled']))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(t['border']))
    return p


#### theme application

# sets the graph, LCD and event colors of the given theme
def apply_colors(aw:'ApplicationWindow', name:str|None = None) -> None:
    t = tokens(name)
    qmc = aw.qmc
    qmc.palette.update({
        'background': t['surface'], 'canvas': t['bg'], 'grid': t['border'],
        'ylabel': t['muted'], 'xlabel': t['muted'],
        'title': t['text'], 'title_focus': t['bt'], 'title_hidden': t['muted'],
        'rect1': t['rect1'], 'rect2': t['rect2'], 'rect3': t['rect3'], 'rect4': t['rect4'], 'rect5': t['rect5'],
        'et': t['et'], 'bt': t['bt'], 'xt': t['muted'], 'yt': t['muted'],
        'deltaet': t['deltaet'], 'deltabt': t['deltabt'],
        'markers': t['text'], 'text': t['text'], 'watermarks': t['watermarks'], 'timeguide': t['muted'],
        'legendbg': t['surface2'], 'legendborder': t['border'],
        'specialeventbox': t['accent'], 'specialeventtext': t['accent_text'],
        'bgeventmarker': t['input_border'], 'bgeventtext': t['text'],
        'mettext': t['accent_text'], 'metbox': t['et'],
        'aucguide': t['muted'], 'messages': t['text'], 'aucarea': t['input_border'],
        'analysismask': t['border'], 'statsanalysisbkgnd': t['surface']})
    qmc.alpha['legendbg'] = 0.85
    qmc.backgroundmetcolor = t['et']
    qmc.backgroundbtcolor = t['bt']
    qmc.backgrounddeltaetcolor = t['deltaet']
    qmc.backgrounddeltabtcolor = t['deltabt']
    qmc.backgroundxtcolor = t['muted']
    qmc.backgroundytcolor = t['muted']
    qmc.backgroundalpha = 0.35
    qmc.EvalueColor = [t['event1'], t['event2'], t['event3'], t['event4']]
    qmc.EvalueTextColor = [t['event_text']] * 4
    for k in aw.lcdpaletteB:
        aw.lcdpaletteB[k] = t['surface']
    aw.lcdpaletteF.update({
        'timer': t['text'], 'et': t['et'], 'bt': t['bt'],
        'deltaet': t['deltaet'], 'deltabt': t['deltabt'], 'sv': t['text'],
        'rstimer': t['et'], 'slowcoolingtimer': t['danger_text']})

# applies the styles of the active theme to the main and event buttons according to the current app state
def _apply_button_styles(aw:'ApplicationWindow') -> None:
    from artisanlib.widgets import EventPushButton, AnimatedMajorEventPushButton
    t = tokens()
    aw.pushbuttonstyles, aw.pushbuttonstyles_simulator = pushbutton_styles(aw)
    simulator = aw.simulator is not None
    styles = aw.pushbuttonstyles_simulator if simulator else aw.pushbuttonstyles
    aw.buttonRESET.setStyleSheet(aw.pushbuttonstyles['RESET'])
    aw.buttonONOFF.setStyleSheet(styles['ON' if aw.qmc.flagon else 'OFF'])
    aw.buttonSTARTSTOP.setStyleSheet(styles['STOP'])
    aw.buttonCONTROL.setStyleSheet(aw.pushbuttonstyles['PIDactive' if aw.pidcontrol.pidActive else 'PID'])
    for b in (aw.buttonSVp5, aw.buttonSVp10, aw.buttonSVp20):
        b.setStyleSheet(aw.pushbuttonstyles['SV +'])
    for b in (aw.buttonSVm5, aw.buttonSVm10, aw.buttonSVm20):
        b.setStyleSheet(aw.pushbuttonstyles['SV -'])
    aw.lowerbuttondialog.setStyleSheet(event_button_style().format(**aw.event_button_style_args))
    for b in aw.sliderStepButtons:
        b.setStyleSheet(slider_step_button_style())
    for b in aw.lowerbuttondialog.findChildren(EventPushButton):
        if isinstance(b, AnimatedMajorEventPushButton):
            b.setAnimationColors(QColor(t['accent']), QColor(t['accent_hover']), QColor(t['accent_pressed']), QColor(t['accent']), t['accent_text'])
        b.setDefaultBackgroundColor(t['surface'], gradient=False)

def _apply_lcd_styles(aw:'ApplicationWindow') -> None:
    t = tokens()
    aw.setLCDsColors()
    for card in [aw.LCD2frame, aw.LCD3frame, aw.LCD4frame, aw.LCD5frame, aw.LCD6frame, aw.LCD7frame] + list(aw.extraLCDframe1) + list(aw.extraLCDframe2):
        card.setStyleSheet(lcd_card_style())
    aw.phaseBar.refreshStyle()
    aw.timerCard.refreshStyle()
    for frame in (aw.TPlcdFrame, aw.TP2DRYframe, aw.DRYlcdFrame, aw.DRY2FCsframe, aw.FCslcdFrame, aw.AUClcdFrame):
        frame.setStyleSheet(phases_lcd_style())
    aw.eventlabel.setStyleSheet(f"background-color:{t['surface2']}; color:{t['text']};")

# applies the given theme to the app. If colors is False, the graph and LCD colors are kept as they are and only the app chrome is themed
def apply_theme(aw:'ApplicationWindow', name:str, colors:bool = True, redraw:bool = True) -> None:
    global _current # pylint: disable=global-statement
    if name not in THEMES:
        name = 'light'
    _current = name
    try:
        app = aw.app
        app.darkmode = name == 'dark'
        try:
            hints = app.styleHints()
            if hints is not None:
                hints.setColorScheme(Qt.ColorScheme.Dark if name == 'dark' else Qt.ColorScheme.Light)
        except Exception as e: # pylint: disable=broad-except
            # Qt < 6.8 does not support to set the color scheme
            _log.info(e)
        app.setStyle('Fusion')
        app.setPalette(app_palette(name))
        app.setStyleSheet(app_stylesheet(name))
        if colors:
            apply_colors(aw, name)
        fix_extra_curve_colors(aw.qmc)
        _apply_button_styles(aw)
        _apply_lcd_styles(aw)
        aw.updateCanvasColors(checkColors=False)
        for action in aw.emocoThemeActions:
            action.setChecked(action.data() == name)
        if redraw:
            aw.qmc.redraw(recomputeAllDeltas=False)
    except Exception as e: # pylint: disable=broad-except
        _log.exception(e)

# selects the theme by user request, applies it and remembers the choice
def select_theme(aw:'ApplicationWindow', name:str) -> None:
    QSettings().setValue(SETTINGS_KEY, name)
    apply_theme(aw, name, colors=True, redraw=True)

# applies the remembered theme on app start. On first start the theme follows the color scheme of the system.
def startup(aw:'ApplicationWindow') -> None:
    settings = QSettings()
    first_start = not settings.contains(SETTINGS_KEY)
    if first_start:
        name = 'dark' if aw.app.darkmode else 'light'
        settings.setValue(SETTINGS_KEY, name)
    else:
        name = str(settings.value(SETTINGS_KEY))
    # the graph and LCD colors are only set on first start and on theme changes to keep later customizations done via the Colors dialog
    apply_theme(aw, name, colors=first_start, redraw=False)

# creates the theme selection menu
def create_menu(aw:'ApplicationWindow') -> QMenu:
    korean = aw.locale_str == 'ko'
    menu = QMenu('화면 테마' if korean else 'Appearance', aw)
    group = QActionGroup(menu)
    group.setExclusive(True)
    aw.emocoThemeActions = []
    for name, label in (('light', '밝은 테마' if korean else 'Light'), ('dark', '어두운 테마' if korean else 'Dark')):
        action = QAction(label, menu)
        action.setCheckable(True)
        action.setData(name)
        action.triggered.connect(lambda _checked=False, n=name: select_theme(aw, n))
        group.addAction(action)
        menu.addAction(action)
        aw.emocoThemeActions.append(action)
    return menu

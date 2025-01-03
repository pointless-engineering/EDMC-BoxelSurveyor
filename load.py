"""
Boxel surveyor.
"""
from __future__ import annotations

import logging
import tkinter as tk

import myNotebook as nb  # noqa: N813
from config import appname, config

from utils import boxel

import pyperclip

import typing

import threading
import requests
import re

# This **MUST** match the name of the folder the plugin is in.
PLUGIN_NAME = "EDMCBoxelSurveyor"
PLUGIN_VERSION = boxel.suffix({"MassCode":0,"BoxelZ":1,"BoxelY":0,"BoxelX":0,"Index":0})

logger = logging.getLogger(f"{appname}.{PLUGIN_NAME}")

def get_boxel_stats_edsm_thread(star_prefix, callback_success, callback_failure = None, callback_exception = None):
    try:
        r = requests.get("https://www.edsm.net/api-v1/systems", {'systemName': star_prefix})
        if r.status_code == 200:
            results = r.json()
            callback_success(star_prefix, results)
        elif callback_failure:
            callback_failure(r)
    except BaseException as e:
        callback_exception(e)

class EDMCBoxelSurveyor:
    """
    Boxel surveyor.
    """

    def __init__(self) -> None:
        logger.info(f"{PLUGIN_NAME} {PLUGIN_VERSION} init")

        self.current_idx = 0
        self.current_id64 = 0
        self.current_h = 0
        self.current_max_h = 0
        self.current_offset = 1
        self.known_boxel_idxs = set()

        self.skip_known = tk.BooleanVar(value=True)

        self.frame = None
        self.last_state = None

    def get_boxel_stats(self, star_name):
        m1 = re.fullmatch("([A-Za-z0-9 ]+ [A-Z][A-Z]-[A-Z] [a-h])([0-9]+)", star_name)
        if m1:
            g = m1.groups()
            prefix = g[0]
            index = g[1]
        else:
            m2 = re.fullmatch("([A-Za-z0-9 ]+ [A-Z][A-Z]-[A-Z] [a-h][0-9]+-)([0-9]+)", star_name)
            if m2:
                g = m2.groups()
                prefix = g[0]
                index = g[1]
            else:
                self.known_boxel_idxs.clear()
                self.frame.event_generate("<<Refresh-Boxel-Stats>>")
                return None

        # k = (
        #     parsed_id64['SectorX'], parsed_id64['SectorY'], parsed_id64['SectorZ'],
        #     parsed_id64['MassCode'],
        #     parsed_id64['BoxelX'], parsed_id64['BoxelY'], parsed_id64['BoxelZ']
        # )

        def with_results(star_prefix, results):
            self.known_boxel_idxs.clear()
            for r in results:
                m = re.findall("[-a-h]([0-9]+)$", r['name'])
                if len(m):
                    idx = int(m[0])
                    pfx = r['name'][:-len(m[0])]
                    if pfx == star_prefix:
                        self.known_boxel_idxs.add(int(m[0]))

            if self.frame:
                self.frame.event_generate("<<Refresh-Boxel-Stats>>")

        def with_failure(result: requests.Response):
            logger.warning(f"Couldn't get boxel stats from EDSM (status {result.status_code})")
            self.known_boxel_idxs.clear()
            self.frame.event_generate("<<Refresh-Boxel-Stats>>")

        def with_exception(e: BaseException):
            logger.warning(f"Couldn't get boxel stats from EDSM (exception thrown)", exc_info=e)
            self.known_boxel_idxs.clear()
            self.frame.event_generate("<<Refresh-Boxel-Stats>>")

        threading.Thread(target=get_boxel_stats_edsm_thread, args=[prefix, with_results]).start()

    def offset_inc(self):
        if self.last_state:
            if self.current_h + self.current_offset + (1 if self.current_offset != -1 else 2) <= self.current_max_h:
                self.current_offset += (1 if self.current_offset != -1 else 2)
            self.update_ui(self.last_state)

    def offset_dec(self):
        if self.last_state:
            if self.current_h + self.current_offset - (1 if self.current_offset != 1 else 2) >= 0:
                self.current_offset -= (1 if self.current_offset != 1 else 2)
            self.update_ui(self.last_state)

    def on_load(self) -> str:
        """
        on_load is called by plugin_start3 below.

        It is the first point EDMC interacts with our code after loading our module.

        :return: The name of the plugin, which will be used by EDMC for logging and for the settings window
        """
        self.skip_known.set(config.get_bool(key='boxelsurveyor_skipknown', default=True))
        return PLUGIN_NAME

    def on_unload(self) -> None:
        """
        on_unload is called by plugin_stop below.

        It is the last thing called before EDMC shuts down. Note that blocking code here will hold the shutdown process.
        """
        self.on_preferences_closed("", False)  # Save our prefs

    def setup_preferences(self, parent: nb.Notebook, cmdr: str, is_beta: bool) -> nb.Frame | None:
        """
        setup_preferences is called by plugin_prefs below.

        It is where we can setup our own settings page in EDMC's settings window. Our tab is defined for us.

        :param parent: the tkinter parent that our returned Frame will want to inherit from
        :param cmdr: The current ED Commander
        :param is_beta: Whether or not EDMC is currently marked as in beta mode
        :return: The frame to add to the settings window
        """
        self.skip_known.set(config.get_bool(key='boxelsurveyor_skipknown', default=True))

        frame = nb.Frame(parent)
        nb.Label(frame, text=f'EDMC Boxel Surveyor v. {PLUGIN_VERSION}').grid(row=0, sticky=tk.W)
        nb.Checkbutton(frame, text='Skip known systems', variable=self.skip_known).grid(row=1, sticky=tk.W)
        return frame

    def on_preferences_closed(self, cmdr: str, is_beta: bool) -> None:
        """
        on_preferences_closed is called by prefs_changed below.

        It is called when the preferences dialog is dismissed by the user.

        :param cmdr: The current ED Commander
        :param is_beta: Whether or not EDMC is currently marked as in beta mode
        """
        config.set('boxelsurveyor_skipknown', self.skip_known.get())
        self.update_ui(self.last_state)

    def setup_main_ui(self, parent: tk.Frame) -> tk.Frame:
        """
        Create our entry on the main EDMC UI.

        This is called by plugin_app below.

        :param parent: EDMC main window Tk
        :return: Our frame
        """
        self.frame = tk.Frame(parent)

        frame1 = tk.Frame(self.frame)
        tk.Label(frame1, text=f"Boxel Surveyor").grid(row=0, column=0, sticky=tk.W)

        frame2 = tk.Frame(self.frame)

        current_row = 0

        self.label3 = tk.Label(frame2, text="")
        self.label3.grid(row=current_row, column=1, sticky=tk.W)

        current_row += 1

        self.label = tk.Label(frame2, text="Next Star:")
        self.label.grid(row=current_row, column=0, sticky=tk.W)

        self.button1 = tk.Button(frame2, text="Awaiting Data", state="disabled")
        self.button1.grid(row=current_row, column=1)
        self.button1.bind("<Button-1>", lambda e: pyperclip.copy(self.button1['text']) if self.last_state else None)

        current_row += 1

        self.label2 = tk.Label(frame2, text="Next Boxel:")
        self.label2.grid(row=current_row, column=0, sticky=tk.W)

        self.button2 = tk.Button(frame2, text="Awaiting Data", state="disabled")
        self.button2.grid(row=current_row, column=1)
        self.button2.bind("<Button-1>", lambda e: pyperclip.copy(self.button2['text']) if self.last_state else None)

        current_row += 1

        frame3 = tk.Frame(self.frame)

        self.button_offset_dec = tk.Button(frame3, text="<", state="disabled")
        self.button_offset_dec.grid(row=0, column=0, sticky=tk.W)
        self.button_offset_dec.bind("<Button-1>", lambda e: self.offset_dec())

        self.label_offset = tk.Label(frame3, text="...")
        self.label_offset.grid(row=0, column=1)

        self.button_offset_inc = tk.Button(frame3, text=">", state="disabled")
        self.button_offset_inc.grid(row=0, column=2, sticky=tk.E)
        self.button_offset_inc.bind("<Button-1>", lambda e: self.offset_inc())

        frame1.grid(row=0, sticky=tk.W)
        frame2.grid(row=1, sticky=tk.W)
        frame3.grid(row=2)

        self.frame.bind("<<Refresh-Boxel-Stats>>", lambda e: self.update_ui(self.last_state))

        return self.frame

    def update_ui(self, state):
        if state:
            if self.skip_known.get():
                logger.info("skipping known")
                nextStar = boxel.nextInBoxel(state["SystemAddress"], self.known_boxel_idxs)
            else:
                logger.info("not skipping known")
                nextStar = boxel.nextInBoxel(state["SystemAddress"], set())
            nextBoxel = boxel.nextBoxelInLayer(state["SystemAddress"], self.current_offset)
            self.label.configure(text=f'Next Star:')
            self.button1.configure(text=f'{nextStar}', state="normal")
            self.label2.configure(text=f'Next Boxel:')
            self.button2.configure(text=f'{nextBoxel}', state="normal" if nextBoxel else "disabled")

            if len(self.known_boxel_idxs):
                self.label3.configure(text=f'{len(self.known_boxel_idxs)} Known | {max(self.known_boxel_idxs)+1} Estim.')
            else:
                self.label3.configure(text=f'No Boxel Stats Available')

            self.label_offset.configure(text=f'Boxel {self.current_h} ({self.current_offset:+})')
            if self.current_h + self.current_offset <= 0:
                self.button_offset_dec.configure(state="disabled")
            else:
                self.button_offset_dec.configure(state="normal")
            if self.current_h + self.current_offset >= self.current_max_h:
                self.button_offset_inc.configure(state="disabled")
            else:
                self.button_offset_inc.configure(state="normal")

    def journal_entry(
        self, cmdr: str, is_beta: bool, system: str, station: str, entry: typing.Dict[str, typing.Any], state: typing.Dict[str, typing.Any]
    ) -> typing.Optional[str]:
        self.last_state = state
        if entry['event'] in ['FSDJump', 'StartUp', 'LoadGame', 'Location', 'CarrierJump']:
            # We arrived at a new system!
            if state["SystemAddress"]:
                self.current_id64 = state['SystemAddress']
                self.current_offset = 1

                parsed_id64 = boxel.parse_id64(self.current_id64)
                self.current_h, self.current_max_h = boxel.currentBoxelInLayer(parsed_id64)

                self.update_ui(state)
                self.get_boxel_stats(state["SystemName"])

plugin = EDMCBoxelSurveyor()


# Note that all of these could be simply replaced with something like:
# plugin_start3 = cc.on_load
def plugin_start3(plugin_dir: str) -> str:
    """
    Handle start up of the plugin.

    See PLUGINS.md#startup
    """
    return plugin.on_load()


def plugin_stop() -> None:
    """
    Handle shutdown of the plugin.

    See PLUGINS.md#shutdown
    """
    return plugin.on_unload()


def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> nb.Frame | None:
    """
    Handle preferences tab for the plugin.

    See PLUGINS.md#configuration
    """
    return plugin.setup_preferences(parent, cmdr, is_beta)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Handle any changed preferences for the plugin.

    See PLUGINS.md#configuration
    """
    return plugin.on_preferences_closed(cmdr, is_beta)


def plugin_app(parent: tk.Frame) -> tk.Frame | None:
    """
    Set up the UI of the plugin.

    See PLUGINS.md#display
    """
    return plugin.setup_main_ui(parent)

journal_entry = plugin.journal_entry
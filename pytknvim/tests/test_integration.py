'''
Neovim ui api is likely to change, also i do not understand really how and what it tries to do, it feels very granular and clunky. Makes it hard to do unit testing. Focuising on Integration testing...
'''

import os
import sys
import time
import _thread as thread
from subprocess import Popen, PIPE
from itertools import count

import pytest
from neovim_gui.ui_bridge import UIBridge

from pytknvim.tk_ui import NvimTk
from pytknvim.util import attach_socket, attach_child, attach_headless
from pytknvim.tests.util import compare_screens, send_tk_key
from pytknvim.util import rand_str
from pytknvim.tests.util import MAX_SCROLL

class MockNvimText(NvimTk):

    '''
    Our Nvim capable tkinter text widget
    '''

    def thread_ui(self):
        '''starts our us threaded so we can run tests'''
        # scroll test will always check scrolling
        named_pipe = '/tmp/nvim{0}'.format(rand_str(16))
        nvim = attach_headless('-u', 'NONE', path=named_pipe)
        ui = self
        self._bridge = UIBridge()
        thread.start_new_thread(self._bridge.connect, (nvim, ui) )

        self.test_nvim = attach_headless(path=named_pipe)
        time.sleep(2)
        # Our compare_screen function doesn't work with number set
        self.test_nvim.command("set nonumber")


class VimCommands():
    '''
    Just for readablility
    '''
    def v_insert_mode(self):
        self.send_tk_key('i')

    def v_normal_mode(self):
        self.send_tk_key('Esc')

    def v_back(self):
        self.v_normal_mode()
        self.send_tk_key('b')

    def v_delete_line(self):
        self.v_normal_mode()
        self.send_tk_key('d')
        self.send_tk_key('d')

    def v_up(self):
        self.v_normal_mode()
        self.send_tk_key('k')

    def v_down(self):
        self.v_normal_mode()
        self.send_tk_key('j')

    def v_undo(self):
        self.v_normal_mode()
        self.send_tk_key('u')

    def v_page_down(self):
        self.v_normal_mode()
        self.send_tk_key('G')

    def v_page_up(self):
        self.v_normal_mode()
        self.send_tk_key('g')
        self.send_tk_key('g')


class TestIntegration(VimCommands):


    def setup_class(cls):
        cls.nvimtk = MockNvimText()
        cls.nvimtk.thread_ui()
        # This one has to be used because of threads and locks
        cls.nvim = cls.nvimtk.test_nvim

    def teardown_class(cls):
        # Have to figure out how to teardown properlly
        # Pipes still breaking...
        cls.nvimtk.quit()
        time.sleep(0.2)


    def teardown_method(self, method):
        '''delete everything so we get a clean slate'''
        self.send_tk_key('Esc')
        buf = self.nvimtk.test_nvim.buffers[0]
        buf[:] = [""]


    def send_tk_key(self, *keys, modifyers=None):
        for key in keys:
            mod = None
            if type(key) in (tuple, list):
                key, mod = key
            send_tk_key(self.nvimtk, key, mod)


    def compare_screens(self):
        compare_screens(self.nvimtk)


    def test_load(self):
        self.compare_screens()


    def test_basic_insert(self):
        self.v_insert_mode()
        self.compare_screens()
        self.send_tk_key('a')
        self.compare_screens()
        self.send_tk_key('b', 'c', 'd', 'e')
        self.compare_screens()


    def test_enter_key(self):
        self.v_insert_mode()
        self.send_tk_key('b', 'c', 'd', 'e')
        self.send_tk_key('Enter')
        self.send_tk_key('Enter')
        self.compare_screens()
        self.send_tk_key('f', 'g', 'h')
        self.compare_screens()
        self.v_back()
        self.v_insert_mode()
        self.send_tk_key('1','2','3')
        self.send_tk_key('Enter')
        self.compare_screens()


    def test_delete_line(self):
        self.v_insert_mode()
        self.send_tk_key('o', 'n', 'e')
        self.v_delete_line()
        self.compare_screens()
        self.v_insert_mode()
        self.send_tk_key('o', 'n', 'e')
        self.send_tk_key('Enter')
        self.send_tk_key('t', 'w', 'o')
        self.send_tk_key('Enter')
        self.send_tk_key('t', 'h', 'r', 'e','e')
        self.compare_screens()
        self.v_delete_line()
        self.compare_screens()
        self.v_undo()
        self.compare_screens()


    def test_scroll(self):
        # Force a scroll of a certain amount then compare_screens
        def _do(to_top):
            self.compare_screens()
            for i in range(0, to_top):
                self.v_up()
            self.compare_screens()
            for i in range(0, to_top):
                self.v_down()
            self.compare_screens()

        # TODO GET THIS DYNAMICALLY
        status_bar_height = 3
        for i in count(1):
            self.v_page_down()
            self.v_insert_mode()
            scrolled = i\
                       - self.nvimtk.current_rows\
                       + status_bar_height
            self.send_tk_key(*str(i-1))
            self.send_tk_key('Enter')
            if scrolled in (1, 2, MAX_SCROLL):
                to_top = self.nvimtk.current_rows + scrolled
                _do(to_top)
            if scrolled == MAX_SCROLL:
                break


    def test_page_up_down(self):
        def _do(to_top):
            self.compare_screens()
            print('PAGE UP')
            self.v_page_up()
            self.compare_screens()
            print('PAGE DOWN')
            self.v_page_down()
            self.compare_screens()

        # TODO GET THIS DYNAMICALLY
        status_bar_height = 3
        for i in count(1):
            self.v_page_down()
            self.v_insert_mode()
            scrolled = i\
                       - self.nvimtk.current_rows\
                       + status_bar_height
            self.send_tk_key(*str(i-1))
            self.send_tk_key('Enter')
            if scrolled in (1 , 2, MAX_SCROLL):
                to_top = self.nvimtk.current_rows + scrolled
                _do(to_top)
            if scrolled == MAX_SCROLL:
                break




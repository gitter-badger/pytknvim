import sys
from pprint import pprint
import math
import time

import neovim
from neovim.ui.ui_bridge import UIBridge
from neovim import attach
from neovim.ui.screen import Screen
#from tkquick.gui.tools import rate_limited, delay_call

from pytknvim import tk_util

try:
    import Tkinter as tk
    import tkFont as tkfont
    import ttk
except ImportError:
    import tkinter as tk
    import tkinter.font as tkfont

from threading import Thread
from collections import deque
# import cProfile, pstats, StringIO

tk_modifiers = ('Alt_L', 'Alt_R',
                'Control_L', 'Control_R',
                'Shift_L', 'Shift_R',
                'Win_L', 'Win_R')
                
KEY_TABLE = {
    'slash': '/',
    'backslash': '\\',
    'asciicircumf': '^',
    'at': '@',
    'numbersign': '#',
    'dollar': '$',
    'percent': '%',
    'ampersand': '&',
    'asterisk': '*',
    'parenleft': '(',
    'parenright': ')',
    'underscore': '_',
    'plus': '+',
    'minus': '-',
    'bracketleft': '[',
    'bracketright': ']',
    'braceleft': '{',
    'braceright': '}',
    'quotedbl': '"',
    'apostrophe': "'",
    'less': "<",
    'greater': ">",
    'comma': ",",
    'period': ".",
    'BackSpace': 'BS',
    'Return': 'CR',
    'Escape': 'Esc',
    'Delete': 'Del',
    'Next': 'PageUp',
    'Prior': 'PageDown',
    'Enter': 'CR',
}

def _stringify_key(key, state):
    send = []
    if state:
        if 'Shift' in key:
            send.append('S')
        elif 'Ctrl' in key:
            send.append('C')
        elif 'Alt' in key:
            send.append('A')
    send.append(key)
    return '<' + '-'.join(send) + '>'

class MixTk():
    '''Tkinter actions we bind and use to communicate to neovim'''
    def on_tk_select(self, arg):
        arg.widget.tag_remove('sel', '1.0', 'end')
        # TODO: this should change nvim visual range


    def _tk_key(self,event, **k):
        keysym = event.keysym
        state = event.state
        if event.char not in ('', ' '):
            #if not event.state:
            if event.keysym_num == ord(event.char):
                # Send through normal keys
                print('send normal key', event.char)
                self._bridge.input(event.char)
                return
        if keysym in tk_modifiers:
            # We don't need to track the state of modifier bits
            #print('returning because of modifer')
            return
        if keysym.startswith('KP_'):
            keysym = keysym[3:]

        # Translated so vim understands
        input_str = _stringify_key(KEY_TABLE.get(keysym, keysym), state)
        print('sdenindg in a vim key', input_str)
        self._bridge.input(input_str)
    
    def _tk_quit(self, *args):
        self._bridge.exit()

    
    #@delay_call(1)
    def _tk_resize(self, event):
        '''Let Neovim know we are changing size'''
        if not self._screen:
            return
        cols = int(math.floor(event.width / self._colsize))
        rows = int(math.floor(event.height / self._rowsize))
        if self._screen.columns == cols and self._screen.rows == rows:
            return
        self.current_cols = cols
        self.current_rows = rows
        #self._bridge.resize(cols, rows)
        print('resizing c, r, w, h', cols,rows, event.width, event.height)
        self.root.after_idle(lambda:self._bridge.resize(cols, rows))
        time.sleep(1)

    def _clear_region(self, top, bot, left, right):
        '''
        This is interesting.. maybe only for canvas?
        '''
        print('clear region')
        print('top ',top+1,'  bot ', bot+1,' left ',left,' right ',right)
        self._flush()
        start = "%d.%d" % (top+1, left)
        end = "%d.%d" % (bot+1, right)
        self.text.delete(start, end)
        

class MixNvim():


    '''These methods get called by neovim'''

    #@delay_call(1)
    def _delayed_nvim_resize(self, width, height):
        self.text.master.geometry('%dx%d' % (width, height))
        self.text.master.update_idletasks()# REALLY SLOWS THINGS DOWN...

    def _nvim_resize(self, cols, rows):
        '''Let neovim update tkinter when neovim changes size'''
        #Todo Check all the heights and so on are correct, :)
        # Make sure it works when user changes font,
        # only can support mono font i think..
        # also steal logic from gtk for faster updateing..
        self._screen = Screen(cols, rows)

        # nvim fills all lines with spaces besides the first fml
        #from itertools import cycle
        #self._nvim_cursor_goto(0,0)
        #for r, m in zip( range(rows+1), cycle('123456789')):
        for c in range(cols):
             self._nvim_put(' ')
        #    self._nvim_cursor_goto(r, 0)
        self._flush()

        print('nv resize rows and cols are : ',str(rows),'.',str(cols))
        width = cols * self._colsize
        height = rows * self._rowsize
        def resize():
            self.text.master.geometry('%dx%d' % (width, height))
            #self.text.master.update_idletasks() REALLY SLOWS THINGS DOWN...

        #print('resize', 'cols ',str(cols),'rows ',str(rows))
        self.root.after_idle(resize)
        #self.root.after_idle(self._delayed_nvim_resize, width, height)


    def _nvim_clear(self):
        '''erp?''' # same as gtk and for every case?
        print('doing nothing ..clear!')
        return
        self.text.delete('1.0', 'end')
        #self.text.insert('1.0', ' \n')
        #return
        print('clear!!!')
        self._clear_region(self._screen.top, self._screen.bot + 1,
                           self._screen.left, self._screen.right +1)
        print('top {0} bot {1} left {2} right {3}'.format(self._screen.top, self._screen.bot+1, self._screen.left, self._screen.right+1))
        self._screen.clear()
        return


    def _nvim_eol_clear(self):
        '''delete from index to end of line as well as new line char     and fill with whitespace...'''
        print('doing nothing ...in eol row and cl -> ')
        return
        row, col = self._screen.row, self._screen.col
        print('in eol row and cl -> ', str(self._screen.row), str(col))
        self._clear_region(row, row, col, self._screen.right + 1)
        self._screen.eol_clear()
        #row, col = self.text.get_pos()
        #self.text.delete("{0}.{1}".format(row, col),
                         #"{0}.{1}".format(row, self.current_cols))
        #self.text.insert(tk.INSERT, "".join(" " for i in range(self.current_cols - col)))

        #print('EOL CLEAR from', "{0}.{1}".format(row, col), 'to ',"{0}.{1}".format(row, self.current_cols))


    def _nvim_cursor_goto(self, row, col):
        '''Move gui cursor to position'''
        # Tkinter row starts at 1 while col starts at 0
        #print(self._screen)
        print('goto ','row ',str(row), ' col ', col)
        self._screen.cursor_goto(row, col)
        self.text.mark_set(tk.INSERT, "{0}.{1}".format(row+1, col))


    def _nvim_busy_start(self):
        self._busy = True


    def _nvim_busy_stop(self):
        self._busy = False


    def _nvim_mouse_on(self):
        self.mouse_enabled = True


    def _nvim_mouse_off(self):
        '''er when is this fired?'''
        self.mouse_enabled = False


    def _nvim_mode_change(self, mode):
        self._insert_cursor = mode == 'insert'


    def _nvim_set_scroll_region(self, top, bot, left, right):
        print('set scroll regione -> ')
        self._screen.set_scroll_region(top, bot, left, right)


    def _nvim_scroll(self, count):
        print('scroll count -> ',str(count))
        #col, row = self.text.index(tk.INSERT).split('.')
        #move_to = int(col) + count
        #print(col, move_to)
        #self.text.yview(move_to)

        self._flush()
        top, bot = self._screen.top+1, self._screen.bot + 2
        left, right = self._screen.left, self._screen.right + 1
        # The diagrams below illustrate what will happen, depending on the
        # scroll direction. "=" is used to represent the SR(scroll region)
        # boundaries and "-" the moved rectangles. note that dst and src share
        # a common region
        if count > 0:
            # move an rectangle in the SR up, this can happen while scrolling
            # down
            # +-------------------------+
            # | (clipped above SR)      |            ^
            # |=========================| dst_top    |
            # | dst (still in SR)       |            |
            # +-------------------------+ src_top    |
            # | src (moved up) and dst  |            |
            # |-------------------------| dst_bot    |
            # | src (cleared)           |            |
            # +=========================+ src_bot
            src_top, src_bot = top + count, bot
            dst_top, dst_bot = top, bot - count
            clr_top, clr_bot = dst_bot, src_bot
        else:
            # move a rectangle in the SR down, this can happen while scrolling
            # up
            # +=========================+ src_top
            # | src (cleared)           |            |
            # |------------------------ | dst_top    |
            # | src (moved down) and dst|            |
            # +-------------------------+ src_bot    |
            # | dst (still in SR)       |            |
            # |=========================| dst_bot    |
            # | (clipped below SR)      |            v
            # +-------------------------+
            src_top, src_bot = top, bot + count
            dst_top, dst_bot = top - count, bot
            clr_top, clr_bot = src_top, dst_top
        #self._cairo_surface.flush()
        #self._cairo_context.save()
        # The move is performed by setting the source surface to itself, but
        # with a coordinate transformation.
        #_, y = self._get_coords(dst_top - src_top, 0)
        #self._cairo_context.set_source_surface(self._cairo_surface, 0, y)
        # Clip to ensure only dst is affected by the change
        #self._mask_region(dst_top, dst_bot, left, right)
        # Do the move
        #self._cairo_context.paint()
        #self._cairo_context.restore()
        # Clear the emptied region
        self._clear_region(clr_top, clr_bot, left, right)
        self._screen.scroll(count)


    def _nvim_highlight_set(self, attrs):
        print('highlight_set ', attrs)
        # Apply attrs?
        if not attrs:
            return
        #key = tuple(sorted((k, v) for k, v in (attrs or {}).items()))
        #print(attrs)
        #self.on_nvim_update_line(attrs)


    def _nvim_put(self, text):
        '''
        NEOVIM
        put text into position, we have to also keep track of the
        cursors position manually i.e new lines etc
        neovim is working by sending us lines... so the line is deleted
        '''
        # choose a Font instance
        if self._screen.row != self._pending[0]:
            # write to screen if vim puts stuff on  a new line
            self._flush()

        self._screen.put(text, self._attrs)
        self._pending[1] = min(self._screen.col - 1, self._pending[1])
        self._pending[2] = max(self._screen.col, self._pending[2])
        # print('put', repr(text), self._pending)
        #font = self._fnormal
        #if self._attrs.get('bold', False):
            #font = self._fbold
        #if self._attrs.get('italic', False):
            #jfont = self._fbolditalic if font == self._fbold else self._fitalic
        # colors
        #fg = "#{0:0{1}}".format(self._attrs.get('foreground', self._fg), 6)
        #bg = "#{0:0{1}}".format(self._attrs.get('background', self._bg), 6)
        # Update internal screen
        #return
        #if not self._insert_cursor:
            #status bar text???
            #print('throwing away ->', text)
            #return
        if self._screen.row == 22:
            #import pdb;pdb.set_trace()
            pass


    def _nvim_bell(self):
        pass


    def _nvim_visual_bell(self):
        pass


    def _nvim_update_fg(self, arg):
        self.fg_color = arg


    def _nvim_update_bg(self, arg):
        self.bg_color = arg


    def _nvim_update_suspend(self, arg):
        self.root.iconify()


    def _nvim_set_title(self, title):
        self.root.title(title)


    def _nvim_set_icon(self, icon):
        self._icon = tk.PhotoImage(file=icon)
        self.root.tk.call('wm', 'iconphoto', self.root._w, self._icon)

    def on_nvim_layout(self, arg):
        print('NVIM LAYOUT')
        windows = {}
        # Recursion helper to build a tk frame graph from data received with
        # the layout event
        def build_widget_graph(parent, node, arrange='row'):
            widget = None
            if node['type'] in ['row', 'column']:
                widget = tk.Frame(parent)
            else:
                widget = tk.Text(parent, width=node['width'],
                              height=node['height'], state='normal',
                              font=self.font, exportselection=False,
                              fg=self.fg_color, bg=self.bg_color,
                              wrap='none', undo=False)
                setattr(widget, 'added_tags', {})
                # fill the widget one linefeed per row to simplify updating
                widget.insert('1.0', '\n' * node['height'])
                # We don't want the user to edit
                widget['state'] = 'disabled'
                windows[node['window_id']] = widget
            if 'children' in node:
                for child in node['children']:
                    build_widget_graph(widget, child, arrange=node['type'])
            if arrange == 'row':
                widget.pack(side=tk.LEFT, anchor=tk.NW)
            else:
                widget.pack(side=tk.TOP, anchor=tk.NW)
        
        # build the new toplevel frame
        toplevel = tk.Frame(self.root, takefocus=True)
        build_widget_graph(toplevel, arg)
        # destroy the existing one if exists
        if self.toplevel:
            self.toplevel.destroy()
        self.windows = windows
        self.toplevel = toplevel
        self.toplevel.pack()


    def on_nvim_delete_line(self, arg):
        widget = self.windows[arg['window_id']]
        line = arg['row'] + 1
        count = arg['count']
        startpos = '%d.0' % line
        endpos = '%d.0' % (line + count)
        widget['state'] = 'normal'
        # delete
        widget.delete(startpos, endpos)
        # insert at the end(they will be updated soon
        widget.insert('end', '\n' * count)
        widget['state'] = 'disabled'

    def on_nvim_win_end(self, arg):
        widget = self.windows[arg['window_id']]
        line = arg['row'] + 1
        endline = arg['endrow'] + 1
        marker = arg['marker']
        fill = arg['fill']
        startpos = '%d.0' % line
        endpos = '%d.0' % endline
        widget['state'] = 'normal'
        # delete
        widget.delete(startpos, endpos)
        line_fill = '%s%s\n' % (marker, fill * (widget['width'] - 1))
        # insert markers/fillers
        widget.insert('end', line_fill * (endline - line))
        widget['state'] = 'disabled'

    def on_nvim_update_line(self, arg):
        widget = self.text 
        pprint(arg)
        contents = ''.join(map(lambda c: c['content'], arg['line']))

        row = self.text.index(tk.INSERT).split('.')[1]
        startpos = '%d.0' % int(row) + 1
        endpos = '%d.end' % line
        #widget['state'] = 'normal'
        widget.delete(startpos, endpos)
        widget.insert(startpos, contents)
        #widget['state'] = 'disabled'
        if 'attributes' in arg:
            for name, positions in arg['attributes'].items():
                for position in positions:
                    self.apply_attribute(widget, name, line, position)

    def apply_attribute(self, widget, name, line, position):
        # Ensure the attribute name is associated with a tag configured with
        # the corresponding attribute format
        if name not in widget.added_tags:
            prefix = name[0:2]
            if prefix in ['fg', 'bg']:
                color = name[3:]
                if prefix == 'fg':
                    widget.tag_configure(name, foreground=color)
                else:
                    widget.tag_configure(name, background=color)
            widget.added_tags[name] = True
        # Now clear occurences of the tags in the current line
        ranges = widget.tag_ranges(name)
        for i in range(0, len(ranges), 2):
            start = ranges[i]
            stop = ranges[i+1]
            widget.tag_remove(start, stop)
        if isinstance(position, list):
            start = '%d.%d' % (line, position[0])
            end = '%d.%d' % (line, position[1])
            widget.tag_add(name, start, end)
        else:
            pos = '%d.%d' % (line, position)
            widget.tag_add(name, pos)


    def _flush(self):
        row, startcol, endcol = self._pending
        self._pending[0] = self._screen.row
        self._pending[1] = self._screen.col
        self._pending[2] = self._screen.col
        if startcol == endcol:
            print('startcol is endcol return')
            return
        print('pass the startcolendcol check')
        #self._cairo_context.save()
        ccol = startcol
        buf = []
        bold = False
        for _, col, text, attrs in self._screen.iter(row, row, startcol,
                                                     endcol - 1):
            newbold = attrs and 'bold' in attrs[0]
            if newbold != bold or not text:
                if buf:
                    self._pango_draw(row, ccol, buf)
                bold = newbold
                buf = [(text, attrs,)]
                ccol = col
            else:
                buf.append((text, attrs,))
        if buf:
            self._pango_draw(row, ccol, buf)
        #sys.exit()


    def _pango_draw(self, row, col, data, cr=None, cursor=False):
       # markup = []
        for text, attrs in data:
            text = text + ' ' # otherwise it bumps cursor onto new line
            start = "{0}.{1}".format(row+1, col)
            end = start+'+{0}c'.format(len(text))
            print('replacing ',repr(self.text.get(start, end)), 'with', repr(text), start, end)
            #for n,i in enumerate(self.text.get('1.0', 'end')):
                #print(str(n), i)
            self.text.delete(start, end)
            self.text.insert(start, text)
        self.text.insert("{0}.{1}".format(row+1, col+1), '\n')
        #self.text.insert(end, '\n')
        self.text.mark_set(tk.INSERT, '{0}-2c'.format(end))
            #self.text.mark_set(tk.INSERT, end)
            #if not attrs:
                #attrs = self._get_pango_attrs(None)
            #attrs = attrs[1] if cursor else attrs[0]
            #markup.append('<span {0}>{1}</span>'.format(attrs, text))
        #markup = ''.join(markup)
        #self._pango_layout.set_markup(markup, -1)
        # Draw the text
        
        #if not cr:
            #cr = self._cairo_context
        #x, y = self._get_coords(row, col)
        #if cursor and self._insert_cursor:
            #cr.rectangle(x, y, self._cell_pixel_width / 4,
                         #self._cell_pixel_height)
            #cr.clip()
        #cr.move_to(x, y)
        #PangoCairo.update_layout(cr, self._pango_layout)
        #PangoCairo.show_layout(cr, self._pango_layout)
        #_, r = self._pango_layout.get_pixel_extents()


    def on_nvim_exit(self, arg):
        self.root.destroy()


class NvimTk(MixNvim, MixTk):
    '''
    Business Logic for making a tkinter neovim text widget
    '''
    def __init__(self):
        # we destroy this when the layout changes
        self.toplevel = None
        # windows_id -> text widget map
        self.windows = None
        # pending nvim events
        self.nvim_events = deque()
        self._insert_cursor = False
        self._attrs = {}
        self._pending = []
        self._screen = None
        self._fg = '#000000'
        self._bg = '#ffffff'
        self._pending = [0,0,0]

    def start(self, bridge):
        # MAXIMUM COLS AND ROWS AVALIABLE (UNTIL WE RESIZE THEN THIS CHANGES)
        self.current_cols = 80
        self.current_rows = 24
        bridge.attach(self.current_cols, self.current_rows, True)
        self._bridge = bridge

        self.root = tk.Tk()
        self.root.protocol('WM_DELETE_WINDOW', self._tk_quit)
        text = tk_util.Text(self.root)
        #text = tk.Text(self.root)
        self.text = text
        # Nvim starts its actions on the 2nd line and we need padding to be able to do that in tkinter
        #self.text.insert('1.0',' ' * self.current_cols + ' \n')

        # Remove Default Bindings and what happens on insert etc
        bindtags = list(text.bindtags())
        bindtags.remove("Text")
        text.bindtags(tuple(bindtags))

        text.pack(expand=1, fill=tk.BOTH)
        text.focus_set()

        text.bind('<Key>', self._tk_key)
        text.bind('<Configure>', self._tk_resize)
        #text.bind(
        # The negative number makes it pixels instead of point sizes
        self._fnormal = tkfont.Font(family='Monospace', size=13)
        self._fbold = tkfont.Font(family='Monospace', weight='bold', size=13)
        self._fitalic = tkfont.Font(family='Monospace', slant='italic', size=13)
        self._fbolditalic = tkfont.Font(family='Monospace', weight='bold',
                                 slant='italic', size=13)
        self._colsize = self._fnormal.measure('A')
        self._rowsize = self._fnormal.metrics('linespace')
        
        text.tag_configure('red', background='red')
        text.tag_configure('blue', background='blue')

        self.root.mainloop()

    def schedule_screen_update(self, apply_updates):
        '''This function is called from the bridge,
           apply_updates calls the required nvim actions'''
        def do():
            apply_updates()
            self._flush()
            self.text.tag_remove('blue', '1.0', 'end')
            #self.text.tag_remove('red',"1.0", 'end')
            self.text.highlight_pattern('\n', 'blue')
            #self.text.highlight_pattern(' ', 'red')
        self.root.after_idle(do)

    def quit(self):
        self.root.after_idle(self.root.quit)

class NvimFriendly(NvimTk):
    '''Meant to be subclassed so the user can tweak easily,
    atm im just using it to keep the config code seperate'''

    def __init__(self):

        super().__init__()

    def _nvim_mode_change(self, mode):
        self.text.config(
                        insertwidth=4,
                        insertontime=600,
                        insertofftime=150,
                        insertbackground='#FF2121',
                        insertborderwidth=0) 
        super()._nvim_mode_change(mode)
        if mode  == 'insert':
            pass
            #self.text.config(cursor='left_ptr')
        elif mode == 'normal':
            self.text.config(cursor='hand2')

        

def main(address=None):
    if address:
        nvim = attach('socket', path=address)
    else:
        try:
            address = sys.argv[1]
            nvim = attach('socket', path=address)
        except:
            print('embedding')
            nvim = attach('child', argv=['/usr/bin/nvim', '--embed'])

    ui = NvimFriendly()

    if sys.version_info[0] > 2:
        from neovim.api import DecodeHook
        nvim = nvim.with_hook(DecodeHook())
    bridge = UIBridge()
    bridge.connect(nvim, ui)
    #_thread.start_new_thread(bridge.connect, (nvim, ui) )

if __name__ == '__main__':
    main()
        
'''
so we get keys, mouse movements inside tkinter, using binds,
These binds are handed off to neovim using _input

Neovim interpruts the actions and we get a function that we run in our mainloop, we implement the functions in our gui toolkit

Neovimso far does stuff line by line, so each callback from neovim produces a series of minisucpe actions which in the end updates a line
'''
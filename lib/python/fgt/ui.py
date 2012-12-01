# -*- encoding: utf-8 -*-

"""
https://github.com/lxnt/fgtestbed
Copyright (c) 2012-2012 Alexander Sabourenkov (screwdriver@lxnt.info)

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any
damages arising from the use of this software.

Permission is granted to anyone to use this software for any
purpose, including commercial applications, and to alter it and
redistribute it freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must
not claim that you wrote the original software. If you use this
software in a product, an acknowledgment in the product documentation
would be appreciated but is not required.

2. Altered source versions must be plainly marked as such, and
must not be misrepresented as being the original software.

3. This notice may not be removed or altered from any source
distribution.

"""

import logging

import fgt
from fgt.gl import *

from gi.repository import Pango
from gi.repository import PangoFT2

from OpenGL.GL import *

"""
    UI layout.

    coordinate system is OpenGL-s, that is:
        bottom left is 0,0; top right is win.w, win.h

    items:
        layer - controls z-order
        hbox/vbox ala gtk
        separator ala xfce
        mapview - map view
        textpanel - multi-string text panel.

    layer {
        zlevel = 0
        child = mapview
    }

    layer {
        zlevel = 1
        child = hbox {
            children = [
                vbox {
                    children = [
                        separator { expand = true }
                        panel {
                            margin = 8px
                            padding = 8px
                            child = minimapview { grid = 3x3, pszar = 64x64 }
                        }
                    ]
                }
                separator { expand = true }
                vbox {
                    children = [
                        textpanel { name = renderer, margin = 8px, padding = 8px }
                        textpanel { name = mouse, margin = 8px, padding = 8px }
                        separator { expand = true }
                        textpanel { name = debug, margin = 8px, padding = 8px }
                    ]
                }
            ]
        }
    }

    layer {
        zlevel = 2
        child = hbox {
            children = [
                separator { expand = true }
                vbox {
                    children = [
                        separator { expand = true }
                        textpanel { name = cheatpanel }
                        separator { expand = true }
                    ]
                }
                separator { expand = true }
            ]
        }
    }

    given that data above, the layout code must come up with rects
    for all the drawable stuff.

    layout rules:
     - vbox and hbox eat up all available space in the parent.
     - separator with expand = true also does this.
     - separator with size !=0 and expand = false has a fixed size.
     - multiple expanding separators eat up available space in equal amounts.
     - textpanel does not grow or shrink, its size is determined exclusively by
        its font, paddings, margins and text content.
     - mapview grows, that is respects whatever size the parent assigns to it.
     - minimapview does not grow, its size is determined by its grid and pszar.


    objects:
     - have minimum sizes, and hexpand/vexpand properties.
     - can accept resize within these limits.

     layout: two passes.
     1. query minimum sizes and expand props
     2. lay out and distribute sizes


    rendering: hud shaderset.

    Panel   - a quad textured with an 32x32/16x16 pixel (4K/1K) bg color texture.
    Mapview - a quad textured from some outer texture (TexFBO from the map renderer).
    Text    - a quad textured from the ttf texbunch.

    we can of course do FBO blits, but that's going to end up doing the same thing
    with lots of potentially unneeded state juggling as seen in mesa source.

"""

__all__ = """Text Panel HBox VBox Layer""".split()

class uibase(object):
    hexpand = False
    vexpand = False

    @property
    def size(self):
        raise NotImplemented

    def gather(self, rect):
        raise NotImplemented

    def resize(self, size):
        raise NotImplemented

class PangoFT2Renderer(object):
    init_done = False

    def init(self):
        if self.init_done:
            return

        self.instance = PangoFT2.FontMap.new()
        self.instance.set_resolution(96, 96)
        self.context = self.instance.create_context()
        self.context.set_language(Pango.Language.get_default())
        self.context.set_base_dir(Pango.Direction.LTR)
        self.context.set_base_gravity(Pango.Gravity.SOUTH)
        self.font_description = Pango.FontDescription.from_string(fgt.config.uifont)

        self.layout = Pango.Layout(self.context)
        self.layout.set_auto_dir(True)
        self.layout.set_ellipsize(Pango.EllipsizeMode.NONE)
        self.layout.set_justify(0)
        self.layout.set_single_paragraph_mode(False)
        self.layout.set_wrap(Pango.WrapMode.WORD)
        self.layout.set_height(-1)
        self.layout.set_alignment(Pango.Alignment.LEFT)
        self.layout.set_font_description(self.font_description)

        self.init_done = True

    def size(self, text, max_width, markup):
        self.init()
        if markup:
            self.layout.set_markup(text, -1)
        else:
            self.layout.set_text(text, -1)
        self.layout.set_width(max_width)

        return Size2(*self.layout.get_pixel_size())

    def render(self, target, text, max_width, markup):
        self.init()
        if markup:
            self.layout.set_markup(text, -1)
        else:
            self.layout.set_text(text, -1)
        PangoFT2.render_layout(target, self.layout, 0, 0)

TextRenderer = PangoFT2Renderer()

class Text(uibase):
    """ a chunk of static text, possibly with pango markup
        if max_width is not None, does wrapping there. """

    def __init__(self, text , max_width = -1, markup = False):
        self._size = fgt.ui.TextRenderer.size(text, max_width, markup)
        self.text = text
        self.markup = markup
        self.max_width = max_width

    def __str__(self):
        return "Text({:.12s}...)".format(self.text)
    __repr__ = __str__

    @property
    def size(self):
        return self._size

    def gather(self, rect):
        return [( self, Rect(rect.x, rect.y, self.size.w, self.size.h) )]

    def render(self, dest):
        """ renders bw blended text. tinting is done in the shader. """
        fgt.ui.TextRenderer.render(dest.gob, self.text, self.max_width, self.markup)

class Panel(uibase):
    """ renders the child on a background with padding """
    def __init__(self, child, padding=8, color=(0,0,0,0.68)):
        # currently panels can't be nested.
        self.child = child
        self.padding = padding
        self.margin = padding
        self.color = color

    def __str__(self):
        return "Panel(color={}".format(self.color)
    __repr__ = __str__

    def resize(self, size):
        self.child.resize(size)

    def gather(self, rect):
        panel_rect = Rect(
            rect.x + self.margin, rect.y + self.margin,
            rect.w - 2*self.margin, rect.h - 2*self.margin)
        child_rect = Rect(
            rect.x + self.margin + self.padding,
            rect.y + self.margin + self.padding,
            rect.w - 2*(self.margin + self.padding),
            rect.h - 2*(self.margin + self.padding))
        return [(self, panel_rect)] + self.child.gather(child_rect)

    @property
    def size(self):
        cs = self.child.size
        return Size2(cs.w + 2*(self.margin + self.padding),
            cs.h + 2*(self.margin + self.padding))

    @property
    def hexpand(self):
        return self.child.hexpand

    @property
    def vexpand(self):
        return self.child.vexpand

class Box(uibase):
    hexpand = True
    vexpand = True

    def __init__(self):
        self.children = []

    def cram(self, child, start=True, padding=0):
        self.children.append( (child, start, padding) )

    def resize(self, size):
        self.drawq = []
        if self.vertical:
            total_size = size.h
            uniform_size = size.w
        else:
            total_size = size.w
            uniform_size = size.h
        start_coord = 0
        end_coord = total_size
        expander_count = 0
        used_size = 0

        for child, start, padding in self.children:
            if (self.vertical and child.vexpand) or (not self.vertical and child.hexpand):
                expander_count += 1

            csz = child.size
            if self.vertical:
                zesize = csz.h
            else:
                zesize = csz.w

            used_size += padding + zesize

        if used_size > total_size or expander_count == 0:
            expander_size = 0
        else:
            expander_size = (total_size - used_size) // expander_count

        used_size = 0
        for child, start, padding in self.children:
            if (self.vertical and child.vexpand):
                child.resize(Size2(uniform_size, child.size.h + expander_size))
            elif (not self.vertical and child.hexpand):
                child.resize(Size2(child.size.w + expander_size, uniform_size))

            csz = child.size
            if self.vertical:
                zesize = csz.h
            else:
                zesize = csz.w

            if start:
                self.drawq.append( (child, start_coord + padding, zesize) )
                start_coord += padding + zesize
            else:
                self.drawq.append( (child, end_coord - padding - zesize, zesize) )
                end_coord -= padding + zesize

            used_size += zesize + padding

        if self.vertical:
            self._size = Size2(uniform_size, used_size)
        else:
            self._size = Size2(used_size, uniform_size)

    def gather(self, rect):
        rv = []
        for child, coord, size in self.drawq:
            if self.vertical:
                rv += child.gather(Rect(rect.x, rect.y + coord, rect.w, size))
            else:
                rv += child.gather(Rect(rect.x + coord, rect.y, size, rect.h))
        return rv

    @property
    def size(self):
        """ minimum or preferred size ? """
        w,h = 0,0
        for child, start, padding in self.children:
            csz = child.size
            w += csz.w
            h += csz.h
        return Size2(w,h)

class HBox(Box):
    vertical = False

    def cram_left(self, child, padding=0):
        super(HBox, self).cram(child, True, padding)

    def cram_right(self, child, padding=0):
        super(HBox, self).cram(child, False, padding)

class VBox(Box):
    vertical = True

    def cram_top(self, child, padding=0):
        super(VBox, self).cram(child, False, padding)

    def cram_bottom(self, child, padding=0):
        super(VBox, self).cram(child, True, padding)

class Layer(object):
    def __init__(self, child):
        self.child = child
        self.size = None

    def resize(self, size):
        self.child.resize(size)
        self.size = size

    def gather(self):
        return self.child.gather(Rect(0,0,self.size.w, self.size.h))

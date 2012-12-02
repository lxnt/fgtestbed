#!/usr/bin/python3.2
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

import sys
import logging
import pprint

import fgt
from fgt.gl import *
from fgt.ui import *
from fgt.sdlenums import *

import pygame2.sdl.events as sdlevents
import pygame2.sdl.video as sdlvideo
import pygame2.sdl.keycode as sdlkeys
import pygame2.sdl.timer as sdltimer

from OpenGL.GL import *

class DumbGridShader(Shader0):
    sname = "dumb"
    def __call__(self, grid_size, pszar, **kwargs):
        glUseProgram(self.program)
        glUniform3f(self.uloc[b'pszar'], *pszar)
        glUniform2i(self.uloc[b'grid'], *grid_size)

class DumbGrid(object):
    def __init__(self, size, pszar):
        self.shader = DumbGridShader()
        self.vao = GridVAO()
        self.vao.resize(size)
        self.pszar = pszar

    def render(self):
        self.shader(self.vao.size, self.pszar)
        self.vao()

    def resize(self, size):
        self.vao.resize(size)

    @property
    def grid_size(self):
        return self.vao.size

class Mapview0(object): # should inherit from fgt.ui.uibase, but hey
    pass

class DumbMapview(Mapview0):
    def __init__(self, gridsize = None, pszar = None, resize = False):
        """ either resize=True, then pszar gives initial zoom
            or resize=False and gridsoze*pszar.xy*pszar.z = fixed mapview size """
        self.hexpand = self.vexpand = resize
        self.pszar = pszar
        self.shader = DumbGridShader()
        self.vao = GridVAO()
        if not resize:
            assert gridsize is not None
            self.vao.resize(gridsize)
            self.gridsize = gridsize
            self.pxsize = Size2(int(gridsize.w*pszar.x*pszar.z),
                                int(gridsize.h*pszar.y*pszar.z))
        else:
            self.pxsize = Size2(0, 0)

    def __str__(self):
        return "DumbMapview(grid={} pszar={} resize={})".format(
            self.gridsize, self.pszar, self.hexpand)
    __repr__ = __str__

    @property
    def size(self):
        return self.pxsize

    def resize(self, size):
        self.gridsize = Size2( int(size.w // (self.pszar.x*self.pszar.z)),
                               int(size.h // (self.pszar.y*self.pszar.z)) )
        self.vao.resize(self.gridsize)
        self.pxsize = size

    def gather(self, rect):
        w, h = self.pxsize
        if rect.w < w:
            w = rect.w
        if rect.h < h:
            h = rect.h
        return [(self, Rect(rect.x,rect.y,w,h))]

    def render(self):
        self.shader(self.vao.size, self.pszar)
        self.vao()

class DumbUI(object):
    def __init__(self):
        dumb_minimap = DumbMapview(gridsize = Size2(3,3), pszar = Coord3(1.0,1.0,64), resize=False)
        mainmap = DumbMapview(pszar = Coord3(1.0,1.0,32), resize=True)

        columns_box = HBox()
        leftbox = VBox()
        rightbox = VBox()
        rightrows = VBox()

        columns_box.cram_left(leftbox)
        columns_box.cram_right(rightbox)
        #rightbox.cram(rightrows)
        leftbox.cram_bottom(Panel(dumb_minimap))
        rightbox.cram_top(Panel(Text("\n".join(["ze", "render", "panel", "fps", "and", "stuff"]))))
        rightbox.cram_top(Panel(Text("\n".join(["ze", "mouse", "panel", "data", "from", "ze map dump"]))))
        rightbox.cram_bottom(Panel(Text("\n".join(["ze", "debug", "panel", "data", "from", "shaderz"]))))
        #rightrows.cram_top(Panel(Text(["ze", "render", "panel", "fps", "and", "shit"], None)))
        #rightrows.cram_top(Panel(Text(["ze", "mouse", "panel", "data", "from", "ze map dump"], None)))
        #rightrows.cram_bottom(Panel(Text(["ze", "debug", "panel", "data", "from", "shaderz"], None)))

        map_box = VBox()
        map_box.cram(mainmap)
        self.layers =  [ Layer(map_box), Layer(columns_box) ]

    def gather(self):
        ervee = []
        for layer in self.layers:
            ervee.extend(layer.gather())
        return ervee

    def resize(self, sz):
        self.winsize = sz
        for layer in self.layers:
            layer.resize(sz)

    def loop(self, window, bg_color, choke):
        self.resize(Size2(window._w, window._h))
        blit = Blitter()
        choke_ms = 0 if choke == 0 else 1000//choke
        while True:
            loopstart = sdltimer.get_ticks()
            while True:
                event = sdlevents.poll_event(True)
                if event is None:
                    break
                elif event.type == sdlevents.SDL_QUIT:
                    return
                elif event.type == sdlevents.SDL_KEYUP:
                    if event.key.keysym.sym == sdlkeys.SDLK_ESCAPE:
                        return
                elif event.type == sdlevents.SDL_WINDOWEVENT:
                    if event.window.event == sdlvideo.SDL_WINDOWEVENT_RESIZED:
                        self.resize(Size2(event.window.data1, event.window.data2))
                elif event.type == sdlevents.SDL_MOUSEBUTTONDOWN:
                    return

            glcalltrace("frame")
            renderlist = self.gather()
            #pprint.pprint(renderlist)
            text_sizes = {}
            map_sizes = {}
            for what, rect in renderlist:
                if isinstance(what, Text):
                    text_sizes[what] = what.size
                elif isinstance(what, Mapview0):
                    glcalltrace("create mapview fbo")
                    map_sizes[what] = TexFBO(what.size)

            glcalltrace("create text surfbunchpbo")
            text_surf_bunch = SurfBunchPBO(text_sizes, FtBitmap)

            # 1. submit text_surf_bunch for text rendering
            for what, ts in text_surf_bunch.items():
                what.render(ts.surface)

            # 2. render maps
            for what, where in map_sizes.items():
                glcalltrace("render mapview")
                with where.as_target():
                    what.render()

            # 3. wait for text rendering to be complete
            pass
            glcalltrace("upload text textures")
            text_surf_bunch.upload()

            # 3. compose
            vpsize = Size2(window._w, window._h)
            glcalltrace("compose")
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glViewport(0, 0, *vpsize)
            glClearColor(*bg_color)
            glClear(GL_COLOR_BUFFER_BIT)

            for what, rect in renderlist:
                if what in text_surf_bunch:
                    glcalltrace("blit text")
                    glActiveTexture(GL_TEXTURE0) # in fact here we can get away
                                                 # with calling this outside the loop
                                                 # but only here. It's noop after
                                                 # the first call (in mesa) anyway.
                    glBindTexture(GL_TEXTURE_2D, text_surf_bunch[what].texname)
                    blit.ralpha(rect, vpsize, color=(1.0,1.0,1.0,1.0))
                elif isinstance(what, Panel):
                    glcalltrace("blit panel")
                    blit.fill(rect, vpsize, what.color)
                elif what in map_sizes:
                    glcalltrace("blit mapview")
                    with map_sizes[what].as_texture(GL_TEXTURE0):
                        blit.texblend(rect, vpsize)

            sdl_flip(window)
            text_surf_bunch.fini()
            for tf in map_sizes.values():
                tf.fini()
            #return
            elapsed = sdltimer.get_ticks() - loopstart
            if choke_ms > elapsed:
                sdltimer.delay(choke_ms - elapsed)

def main():
    fgt.config(description = 'full-graphics ui layout engine test')
    fgt.config.add_render_args(psize=96, par=0.8, ss='dumb', choke=2)
    fgt.config.add_gl_args()
    fgt.config.add_ui_args(uifont = 'ubuntu mono 16')
    fgt.config.parse_args()

    window, context = sdl_init()
    glinfo()

    bg_color = ( 0,0.7,0,1 )

    ui = DumbUI()
    ui.loop(window, bg_color, fgt.config.choke)
    sdl_fini()
    return 0

if __name__ == "__main__":
    sys.exit(main())

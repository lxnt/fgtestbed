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

import os
import sys
import argparse
import logging
import time

import fgt
from fgt.gl import *
from fgt.hud import *
from fgt.sdlenums import *

import pygame2.sdl.events as sdlevents
import pygame2.sdl.video as sdlvideo
import pygame2.sdl.keycode as sdlkeys

from OpenGL.GL import *

class DumbGridShader(Shader0):
    sname = "dumb"
    def __call__(self, grid_size, pszar, **kwargs):
        glUseProgram(self.program)
        glUniform3f(self.uloc[b'pszar'], *pszar)
        glUniform2i(self.uloc[b'grid'], *grid_size)

class Grid(object):
    def __init__(self, size, pszar, sargs={}):
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
    def size(self):
        return self.vao.size
    
    def reshape(self, size):
        glViewport(0, 0, size.w, size.h)
        
    def click(self, at):
        pass

def loop(window, bg_color, fbo_color, grid, hud, panels, choke):
    fbo = FBO(Size2(window._w, window._h))
    while True:
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
                    sz = Size2(event.window.data1, event.window.data2)
                    fbo.resize(sz)
                    grid.reshape(sz)
                    hud.reshape(sz)
            elif event.type == sdlevents.SDL_MOUSEBUTTONDOWN:
                return

        glcalltrace("frame")
        glClearColor(*bg_color)
        glClear(GL_COLOR_BUFFER_BIT)

        glcalltrace("fbo.bind()")
        fbo.bind(fbo_color)
        
        glcalltrace("grid.render()")
        grid.render()
        
        glcalltrace("fbo.blit()")
        fbo.blit(Rect(0,0,window._w, window._h))
        
        glcalltrace("hud.render()")
        hud.render(panels)

        sdl_flip(window)
        if choke > 0:
            time.sleep(1/choke)

def main():
    fgt.config(description = 'full-graphics renderer backend test')
    fgt.config.add_render_args(psize=96, par=0.8, ss='dumb', choke=2)
    fgt.config.add_gl_args()
    fgt.config.add_ui_args(uifont=',96')
    fgt.config.parse_args()
    
    window, context = sdl_init()
    glinfo()
    
    psize = fgt.config.psize
    par = fgt.config.par
    if par > 1:
        pszar_x = 1
        pszar_y = 1/par
    else:
        pszar_x = par
        pszar_y = 1

    grid_w = int(window._w // (pszar_x*psize))
    grid_h = int(window._h // (pszar_y*psize))
        
    bg_color = ( 0,1,0,1 )
    fbo_color = ( 1,0,0,1 )
    
    logging.getLogger("fgt.test").info("grid {}x{} psize {}x{}".format(grid_w, grid_h, 
        int(pszar_x*psize), int(pszar_y*psize)))
    grid = Grid(size = (grid_w, grid_h), pszar = (pszar_x, pszar_y, psize))
    hud = Hud()

    panels = []
    panels.append(HudTextPanel([ "Yokarny Babai" ]))
    panels[0].moveto(Coord2(100, 400))
    panels.append(HudTextPanel([ "Skoromorkovka" ]))
    panels[1].moveto(Coord2(400, 100))
    hud.reshape(Size2(window._w, window._h))
    loop(window, bg_color, fbo_color, grid, hud, panels, fgt.config.choke)
    sdl_fini()
    return 0

if __name__ == "__main__":
    sys.exit(main())

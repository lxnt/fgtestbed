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
import struct

from pygame2 import sdlttf
from pygame2.sdl.pixels import SDL_Color
import pygame2.sdl.surface as sdlsurface

import fgt
from fgt.gl import *

from OpenGL.GL import *

class HudVAO(VAO0):
    """ a quad -> TRIANGLE_STRIP """
    _primitive_type = GL_TRIANGLE_STRIP
    _data_type = struct.Struct("IIII")
    _attrs = (VertexAttr( 0, 4, GL_INT, 0, 0 ),)    

    def set(self, rect):
        self.update(( # hmm. texture coords are inverted? 
            ( rect.x,          rect.y,          0, 1 ), # bottom left
            ( rect.x + rect.w, rect.y,          1, 1 ), # bottom right
            ( rect.x,          rect.y + rect.h, 0, 0 ), # top left
            ( rect.x + rect.w, rect.y + rect.h, 1, 0 )) # top right
        )

class HudShader(Shader0):
    sname = "hud"
    def __call__(self, panel, winsize):
        glUseProgram(self.program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, panel.texture_name)
        glUniform1i(self.uloc[b"hudtex"], 0)
        glUniform2i(self.uloc[b"resolution"], *winsize)
        glUniform4f(self.uloc[b"fg"], *panel.fg)
        glUniform4f(self.uloc[b"bg"], *panel.bg)

class HudTextPanel(object):
    def __init__(self, strs, longest_str = None, active = True, font = None):
        self.fg = GLColor(1, 1, 1, 1)
        self.bg = GLColor(0, 0, 0, 0.68)
        self._texture_name = glGenTextures(1)
        self.font = font if font else a_mono_font(fgt.config.hudfont)
        self.padding = 8
        self.margin = 8 
        self.strings = strs
        if longest_str is None:
            longest_str_px = 0
            for s in strs:
                sz = sdlttf.size(self.font, s)[0]
                if sz > longest_str_px:
                   longest_str_px = sz
        else:
            longest_str_px = sdlttf.size(self.font, longest_str)[0]
        width = 2*self.padding + longest_str_px
        self.ystep = sdlttf.font_line_skip(self.font)
        height = 2*self.padding + self.ystep * len(strs)
        self.surface = rgba_surface(width, height)
        self._surface_dirty = True
        self.active = active
        self.rect = Rect(0, 0, width, height)

    def __str__(self):
        return "{}({})".format(self.__class__.__name__, self.rect)

    def moveto(self, to):
        self.rect = self.rect._replace(x=to.x, y=to.y)

    @property
    def data(self):
        return None

    @property
    def texture_name(self):
        if self._surface_dirty:
            self._render_text()
        return self._texture_name

    def _render_text(self):
        """ renders bw blended text. tinting is done in the shader. """
        self.surface.fill((0,0,0,0))
        i = 0
        dump = False
        for s in self.strings:
            if len(s) > 0:
                if isinstance(self.data, dict):
                    s = s.format(**self.data)
                strsurf = sdlttf.render_blended(self.font, s, SDL_Color())
                # since we render with white, we can set the pixelformat
                # to anything that starts with 'A' and has the same bpp and amask,
                # thus avoiding extra blit cost
                # or we can just render_shaded and use that as the alpha channel.
                
                self.surface.blit(strsurf, (self.padding, self.padding + i * self.ystep))
                sdlsurface.free_surface(strsurf)
            i += 1
        self.surface.upload_tex2d(self._texture_name)
        self._surface_dirty = False

    def fini(self):
        glDeleteTextures(self.texture_name)
        sdlsurface.free_surface(self.surface)

class Hud(object):
    """ draws tinted translucent overlays with some text. """    
    def __init__(self):
        self.shader = HudShader()
        self.panels = []
        self._vao = HudVAO()

    def render(self, panels):
        for p in panels:
            if p.active:
                self._vao.set(p.rect)
                self.shader(p, self.winsize)
                self._vao()
        
    def reshape(self, sz):
        self.winsize = sz


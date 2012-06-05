#!/usr/bin/python3.2
# -*- encoding: utf-8 -*-
#
# lxnt has created fgtestbed, a lump of python code
# all masterwork is of dubious quiality.
# it is studded with bugs
# it is encrusted with bugs
# it is smelling with bugs
# it menaces with spikes of bugs
# a picture of giant bug is engraved on its side
# ...
# lxnt cancels Store item in stockpile: interrupted by bug
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
from __future__ import division

import sys, time, math, struct, io, ctypes, zlib, ctypes, copy
import argparse, traceback, os, types, mmap, logging, logging.config

from raw import MapObject, Designation
from py3sdl2 import * 

from OpenGL.GL import *
from OpenGL.GL.ARB.texture_rg import *
from OpenGL.error import GLError

import pygame2.sdl as sdl
import pygame2.sdl.events as sdlevents
import pygame2.sdl.mouse as sdlmouse
import pygame2.sdl.keyboard as sdlkeyboard
import pygame2.sdl.video as sdlvideo
import pygame2.sdl.surface as sdlsurface
import pygame2.sdl.pixels as sdlpixels
import pygame2.sdl.timer as sdltimer

from pygame2.sdl.keycode import *
from sdlenums import * # all of enums except key/scan codes.

from collections import namedtuple
import pygame2.ttf as ttf
CONTROLS = """\
    F1:                         toggle this text
    Esc:                        quit
    Right mouse button drag:    panning
    Mouse wheel, < >:           up/down Z-level
    Shift+mouse wheel:          up/down 10 Z-levels
    Ctrl+Mouse wheel:           zoom in/out
    Arrows, PgUp/PgDn/Home/End: scroll
    Shift+same:                 faster scroll
    Backspace:                  recenter map
    Keypad +/-:                 adjust animation FPS
    Keypad *:                   toggle reveal_all
    Keypad /:                   toggle debug feedback mode
    Left mouse button, Space:   toggle animation"""

class GridShader(Shader0):
    def __call__(self, map_size,
            grid_size, pszar, tileflags, 
            tex, 
            render_origin,
            mouse_pos, mouse_color,
            show_hidden, debug_active, 
            falpha, darken, frame_no):
        
        glcalltrace("GridShader.__call__")
        
        glUseProgram(self.program)

        glUniform3i(self.uloc[b'mapsize'], *map_size)
        glUniform2i(self.uloc[b'gridsize'], *grid_size)
        glUniform3i(self.uloc[b"origin"], *render_origin)
        glUniform3f(self.uloc[b'pszar'], *pszar)
        
        glUniform1i(self.uloc[b'frame_no'], frame_no)
        glUniform1f(self.uloc[b"darken"], darken)        
        glUniform1i(self.uloc[b"show_hidden"], show_hidden)
        glUniform1i(self.uloc[b'debug_active'], debug_active)
        
        glUniform2i(self.uloc[b"mouse_pos"], *mouse_pos);
        glUniform4f(self.uloc[b"mouse_color"], *mouse_color)
        
        # ati vs nvidia :(
        tc_uloc = self.uloc[b"tileflags"] if self.uloc[b"tileflags"] != -1 else self.uloc[b"tileflags[0]"]
        glUniform1uiv(tc_uloc, tileflags.w, tileflags.ptr)
        
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex.dispatch)
        glUniform1i(self.uloc[b"dispatch"], 0)
        
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D_ARRAY, tex.blitcode)
        glUniform1i(self.uloc[b"blitcode"], 1)
        
        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, tex.font)
        glUniform1i(self.uloc[b"font"], 2)
        
        glActiveTexture(GL_TEXTURE3)
        glBindTexture(GL_TEXTURE_2D, tex.findex)
        glUniform1i(self.uloc[b"findex"], 3)
            
        glActiveTexture(GL_TEXTURE4)
        glBindTexture(GL_TEXTURE_2D_ARRAY, tex.screen)
        glUniform1i(self.uloc[b"screen"], 4)
        
        self.validate()
        
class RendererPanel(HudTextPanel):
    def __init__(self, font):
        strs = (
            "gfps: {gfps:2.0f} afps: {anim_fps:02d} frame# {frame_no:03d}",
            "origin: {origin.x}:{origin.y}:{origin.z} grid: {grid.w}x{grid.h} map: {map.x}x{map.y}x{map.z}",
            "pszar: {pszar.x:.2f} {pszar.y:.2f} {pszar.z};  {psz.x}x{psz.y} px",
            "map_viewport: {viewport.x:02d} {viewport.y:02d} {viewport.w:d} {viewport.h:d}",
            "fbo_size={fbosize.w:d}:{fbosize.h:d} win_size={winsize.w:d}:{winsize.h:d}",
            "{showhidden}", 
        )
        self.active = True
        dummy = Coord3(999,999,999)
        longest_str = strs[1].format(origin=dummy, grid=Size2(999,999), map=dummy)

        super(RendererPanel, self).__init__(font, strs, longest_str)
    
    def update(self, win, map_viewport, show_hidden, **kwargs):
        self._data = kwargs
        self._data['viewport'] = map_viewport
        self._data['showhidden'] = '[show_hidden]' if show_hidden else '             '
        self._surface_dirty = True

        # glue it to the top-right corner, observing margins.
        self.moveto(Coord2(win.w - self.margin - self.rect.w, win.h - self.margin - self.rect.h))

    @property
    def data(self):
        return self._data

class MousePanel(HudTextPanel):
    def __init__(self, font):
        # maxlen of vanilla matname is 22.
        # maxlen of tile-type is 25
        strs = (
            "win_mp={win_mp.x:d}:{win_mp.y:d}",
            "fbo_mp: {fbo_mp.x:d}:{fbo_mp.y:d}",
            "grid_mp: {grid.x:03d}:{grid.y:03d}",
            "dffb_mp: {dffb.x:.2f}:{dffb.y:.2f}",
            "map_mp: {posn.x:03d}:{posn.y:03d}:{posn.z:03d}",
            "   ",
            "color: #{color:08x} {colordec}",
            "{designation}",
            "mat:  {mat[0]: 3d} ({mat[1]})",
            "bmat:  {bmat[0]: 3d} ({bmat[1]})",
            "tile: {tile[0]: 3d} ({tile[1]})",
            "btile: {btile[0]: 3d} ({btile[1]})", # max 38
            "grass: {grass[0]: 3d} ({grass[1]}) amount={grass[2]:02x}", # max 44
        )
        longest_str = "m"*44
        
        self._data = {}
        super(MousePanel, self).__init__(font, strs, longest_str, active = False)

    def update(self, win, renderer_panel, renderer, win_mouse_pos, 
                fbo_mouse_pos, grid_mouse_pos,grid_mouse_pos_f, map_mouse_pos):
        gamedata = renderer.gamedata
        fbo = renderer.fbo
        
        if not gamedata.inside(*map_mouse_pos):
            self.active = False
            return
    
        color = int(fbo.readpixels(Rect(*fbo_mouse_pos, w=1, h=1))[0][0])
    
        self.active = True
        self._surface_dirty = True
        material, tile, bmat, btile, grass, designation, flags = gamedata.gettile(map_mouse_pos)
        self._data.update({
            'color': color,
            'colordec': color>>8,
            'posn': map_mouse_pos,
            'grid': grid_mouse_pos,
            'dffb': grid_mouse_pos_f,
            'fbo_mp': fbo_mouse_pos,
            'win_mp': win_mouse_pos,
            'tile': tile,
            'mat': material,
            'btile': btile,
            'bmat': bmat,
            'grass': grass,
            'designation': Designation(designation),
        })        
        
        # glue it to under the renderer panel, observing margins.
        self.moveto(Coord2(win.w - self.margin - self.rect.w, 
                    renderer_panel.rect.y - self.margin - self.rect.h))

    @property
    def data(self):
        return self._data

class CheatPanel(HudTextPanel):
    def __init__(self, font):
        strs = [x.strip() for x in CONTROLS.split("\n")]
        self.active = True
        super(CheatPanel, self).__init__(font, strs, longest_str = None)

    def update(self, win):
        # center in the window
        self.moveto(Coord2((win.w - self.rect.w)//2, (win.h - self.rect.h)//2))

class DebugPanel(HudTextPanel):
    def __init__(self, font):
        strs = (
            "{trect}",
            "tile, mat, dispatch.xy {d[0][0]: 4d} {d[0][1]: 4d} {d[0][2]: 6d} {d[0][3]: 6d}",
            "fontref, mode, fg, bg  {d[1][0]: 4d} {d[1][1]: 4d} {d[1][2]:06x} {d[1][3]:06x}",
            "cinfo                  {d[2][0]: 4d} {d[2][1]: 4d} {d[2][2]: 6d} {d[2][3]: 6d}",
            "st, psz                {d[3][0]: 4d} {d[3][1]: 4d} {d[3][2]: 6d} {d[3][3]: 6d}",
        )
        super(DebugPanel, self).__init__(font, strs, longest_str = "8"*(4*8+14), active = False)
    
    def update(self, win, pixels, psz, trect):
        d = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]
        xstep = psz.x//4
        ystep = psz.y//4
        for j in range(4):
            y0 = j * ystep
            for i in range(4):
                x0 = i * xstep
                values = {}
                for dy in range(ystep):
                    for dx in range(xstep):
                        value = pixels[y0+dy][x0+dx] >> 8
                        try:
                            values[value] += 1
                        except KeyError:
                            values[value] = 1
                votes = 0
                for k, v in values.items():
                    if v > votes:
                        votes = v
                        d[3-j][i] = k

        self._data = dict(d = d, trect = repr(trect))
        self._surface_dirty = True

        # glue it to the bottom-right corner, observing margins.
        self.moveto(Coord2(win.w - self.margin - self.rect.w, self.margin))

    @property
    def data(self):
        return self._data    

class Rednerer(object):
    _overdraw = 3 # a constant, can't be less than 3 
    # due to the panning algorithm, and no sense in making it more than 3 either
    # With 3 there's always a neighbouring tile drawn to any visible one.
    # Since grid is sized based on viewport size modulo tile size, this
    # guarantees that all visible tiles are drawn.
    
    _zdtab = [  # darkening coefficients for drawing multiple z-levels.
        [1.0],
        [1.0, 0.50 ],
        [1.0, 0.66, 0.33],
        [1.0, 0.60, 0.45, 0.30, 0.15 ],
        [1.0, 0.60, 0.50, 0.40, 0.30, 0.20]  ]

    def __init__(self, window, shaderset, gamedata, 
                 psize, par, zeddown, anim_fps):
        log = logging.getLogger('fgt.renderer.init')

        self.window = window
        self.gamedata = gamedata
        self.hud = Hud()
        self.fbo = FBO()
        self.debug_fbo = FBO()
        self.grid = GridVAO()
        self.grid_shader = GridShader(shaderset)
        self.tex = namedtuple("Texnames", "dispatch blitcode font findex screen")._make(glGenTextures(5))
        
        self._zeddown = zeddown if zeddown < len(self._zdtab) else len(self._zdtab)
        self.anim_fps = anim_fps
        self.min_psz = 3
        self.max_psz = 1024
        
        self.fps = EmaFilter()
        self.last_frame_time = 16 # milliseconds
        
        self.had_input = False
        self.show_hidden = True
        
        font = ttf.open_font(b"/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-R.ttf", 18)
        self.hp_renderer = RendererPanel(font) 
        self.hp_mouse = MousePanel(font)
        self.hp_cheat = CheatPanel(font)
        self.hp_debug = DebugPanel(font)
        self.hp_debug.active = True
        
        self.render_origin = gamedata.window
        self.map_viewport = Rect(0, 0, window._w, window._h)

        glcalltrace("upload dispatch")
        glActiveTexture(GL_TEXTURE0)
        upload_tex2d(self.tex.dispatch, GL_RG16UI,
            gamedata.dispatch.w, gamedata.dispatch.h, 
            GL_RG_INTEGER, GL_UNSIGNED_SHORT, gamedata.dispatch.ptr, GL_NEAREST)
            
        glcalltrace("upload blitcode")
        glActiveTexture(GL_TEXTURE1)
        upload_tex2da(self.tex.blitcode, GL_RGBA32UI,
            gamedata.blitcode.w, gamedata.blitcode.h, gamedata.blitcode.d,
            GL_RGBA_INTEGER, GL_UNSIGNED_INT, gamedata.blitcode.ptr, GL_NEAREST)

        glcalltrace("upload font")
        glActiveTexture(GL_TEXTURE2)
        gamedata.pageman.surface.upload_tex2d(self.tex.font)
        
        glcalltrace("upload findex")
        glActiveTexture(GL_TEXTURE3)
        upload_tex2d(self.tex.findex, GL_RGBA16UI,
            gamedata.pageman.findex.w, gamedata.pageman.findex.h,
            GL_RGBA_INTEGER, GL_UNSIGNED_SHORT, gamedata.pageman.findex.ptr, GL_NEAREST)

        glcalltrace("upload screen")
        glActiveTexture(GL_TEXTURE4)
        upload_tex2da(self.tex.screen, GL_RGBA32UI,
               gamedata.mapdata.w, gamedata.mapdata.h, gamedata.mapdata.d,
               GL_RGBA_INTEGER, GL_UNSIGNED_INT, gamedata.mapdata.ptr, GL_NEAREST)

        if psize is None:
            psize = max(gamedata.pageman.pages['STD'].cdim.w, gamedata.pageman.pages['STD'].cdim.h)
        self.std_psize = psize
        
        if par is None:
            par = gamedata.pageman.pages['STD'].cdim.w / gamedata.pageman.pages['STD'].cdim.h
        if par > 1:
            self.Pszar = Coord3(1, 1/par, psize)
        else:
            self.Pszar = Coord3(par, 1, psize)

        self.winsize = Size2(window._w, window._h)
        self.reshape(winsize = self.winsize)
        log.info(str(self.grid))
        log.info(str(self.winsize))
        gldumplog()
    
    def dump_fbos(self, destdir="idumps"):
        self.fbo.dump(os.path.join(destdir, 'fbo.bmp'))
        self.debug_fbo.dump(os.path.join(destdir, 'debug_fbo.bmp'))
    
    @property
    def psz(self):
        return Coord2(int(self.Pszar.z * self.Pszar.x), int(self.Pszar.z * self.Pszar.y))
    
    def win2glfb(self, win):
        """ converts window coordinates (pixels, SDL coordinate system)
            to gl-style coordinates within the fbo """
        win_h = self.winsize.h
        glwin = Coord2(win.x, win_h - win.y)
        return Coord2(glwin.x + self.map_viewport.x, glwin.y + self.map_viewport.y)
        
    def win2dffb(self, win):
        """ converts window coordinates (pixels, SDL coordinate system) 
            to fractional tile coordinates relative to render_origin 
            (tiles, DF coordinate system) """
        psz = self.psz
        grid_h = self.grid.size.h
       
        glfb = self.win2glfb(win)
        dffb = Coord2(glfb.x / psz.x, grid_h - glfb.y / psz.y)
        return dffb

    def dffb2win(self, dffb):
        """ reverse of the above """
        win_h = self.winsize.h
        grid_h = self.grid.size.h
        psz = self.psz
        
        glfb = Coord2(dffb.x * psz.x, (grid_h - dffb.y) * psz.y)
        glwin = Coord2(glfb.x - self.map_viewport.x, glfb.y - self.map_viewport.y)
        win = Coord2(int(glwin.x), int(win_h - glwin.y))
        return win

    def win2world(self, win):
        """ calculate world corrdinates of the tile under the given pixel """
        dffb = self.win2dffb(win)
        return Coord2(self.render_origin.x + dffb.x, self.render_origin.y + dffb.y)

    def reshape(self, winsize = None, zoom = None):
        log = logging.getLogger("fgt.reshape")
        """ resize or zoom """
        if winsize is not None: # a resize
            pan = Coord2(( self.winsize.w - winsize.w ) // 2,
                          (self.winsize.h - winsize.h ) // 2 )
            self.winsize = winsize
            self.map_viewport = self.map_viewport._replace(w = self.window._w, h = self.window._h)
        elif zoom:
            psz, zoompoint = zoom
            # the zoompoint is the point in window coordinates where
            # the zoom event took place.
            # to keep the zoompoint stationary wrt the window,
            # we calculate fractional tile coordinates of it pre-zoom
            # and post-zoom.
            
            pre_zp = self.win2dffb(zoompoint)
            self.Pszar = self.Pszar._replace(z = psz)
        else:
            raise RuntimeError("reshape(None, None)")

        # code common to both zoom and resize:
        # calculate new grid size
        psz = self.psz
        gridsz = Size2(self.map_viewport.w // psz.x + self._overdraw * 2, 
                       self.map_viewport.h // psz.y + self._overdraw * 2)
        log.info("({}, {}) -> newgrid={} (map_vp={} Pszar={} psz={})".format(
                winsize, zoom, gridsz, self.map_viewport, self.Pszar, self.psz))
        # resize both the grid and the fbo
        self.grid.resize(gridsz)
        self.fbo.resize(Size2(gridsz.w*psz.x, gridsz.h*psz.y))

        if zoom:
            # now convert post_zp back to window coordinates
            # pan amount would be the difference between zoompoint and this.
            zoompoint_after_zoom = self.dffb2win(pre_zp)
            pan = Coord2(zoompoint_after_zoom.x - zoompoint.x, 
                         zoompoint_after_zoom.y - zoompoint.y)

        # try to keep the map from panning
        self.pan(pan)

    def pan(self, rel):
        """ keeps map viewport position somewhere
            in the inner third of the overdraw, which is the tile
            with grid coordinates (1,1) for an overdraw of 3 """
            
        plog = logging.getLogger('fgt.pan').debug

        xpad = self.psz.x*self._overdraw//3
        ypad = self.psz.y*self._overdraw//3
        x, y = self.render_origin.x, self.render_origin.y

        plog("pan mvp={} rel={}".format(self.map_viewport, rel))
        vpx = self.map_viewport.x - rel.x # viewport shift
        vpy = self.map_viewport.y + rel.y # in opengl window CS
        
        if vpx > 2 * xpad:
            delta = (vpx - 2 * xpad) // self.psz.x + 1 # overshoot in tiles
            plog("vpx>2xpad {}>{} delta={}".format(vpx, 2*xpad, delta))
            x += delta # move origin thus many tiles
            vpx -= delta * self.psz.x # compensate
        elif vpx < xpad:
            delta = (xpad - vpx) // self.psz.x + 1
            plog("vpx<xpad {}<{} delta={}".format(vpx, xpad, delta))
            x -= delta
            vpx += delta * self.psz.x

        # here the delta sign is inverted when moving render origin
        # because df grid coordinate system's y axis direction is 
        # opposite to GL window one.
        if vpy > 2 * ypad:
            delta = (vpy - 2 * ypad) // self.psz.y + 1
            plog("vpy>2ypad {}>{} delta={}".format(vpy, 2*ypad, delta))
            y -= delta
            vpy -= delta * self.psz.y
        elif vpy < ypad:
            delta = (ypad - vpy) // self.psz.y + 1
            plog("vpy<ypad {}<{} delta={}".format(vpy, ypad, delta))
            y += delta
            vpy += delta * self.psz.y
            
        self.map_viewport = self.map_viewport._replace(x=vpx, y=vpy)
        self.render_origin = self.render_origin._replace(x=x, y=y)
        plog("pan result mvp={} ro={}".format(self.map_viewport, self.render_origin))

    def zoom(self, zcmd, zpos = None):
        if self.hp_debug.active:
            return self.zoom_x4(zcmd, zpos)
        if zcmd == 'zoom_in' and self.Pszar.z > 1:
            psz = self.Pszar.z + 1
        elif zcmd == 'zoom_out' and self.Pszar.z < self.max_psz:
            psz = self.Pszar.z - 1
        elif zcmd == 'zoom_reset':
            psz = self.std_psize
        if zpos is None:
            zpos = Coord2( self.window._w // 2, self.window._h // 2 )
        if psz >= self.min_psz and psz <= self.max_psz:
            self.reshape(zoom = (psz, zpos))
            
    def zoom_x4(self, zcmd, zpos):
        if zcmd == 'zoom_in' and self.Pszar.z > 1:
            psz = (self.Pszar.z//4 + 1)*4
        elif zcmd == 'zoom_out' and self.Pszar.z < self.max_psz:
            psz = (self.Pszar.z//4 - 1)*4
        elif zcmd == 'zoom_reset': # not quite the same than above..
            psz = (psz//4 + 1)*4
        if zpos is None:
            zpos = Coord2( self.window._w // 2, self.window._h // 2 )
        if psz >= self.min_psz and psz <= self.max_psz:
            self.reshape(zoom = (psz, zpos))

    def _render_one_grid(self, origin, m_pos, m_color, darken, frame_no, hidden = True, debug = False):
        glcalltrace('_render_one_grid')
        self.grid_shader(
            map_size = self.gamedata.dim,
            grid_size = self.grid.size, 
            pszar = self.Pszar, 
            tileflags = self.gamedata.tileflags,
            tex = self.tex,
            render_origin = origin,
            mouse_pos = m_pos, 
            mouse_color = m_color,
            show_hidden = 1 if hidden else 0, 
            debug_active = 1 if debug else 0, 
            falpha = 1.0, 
            darken = darken,
            frame_no = frame_no)
        try:
            self.grid()
        except:
            gldumplog()
            raise()

    def render(self, frame_no):
        bgc = GLColor( 0.0, 0.5, 0.0, 1 )
        tick = sdltimer.get_ticks()
        
        win_mouse_pos = Coord2._make(sdlmouse.get_mouse_state()[1:])
        fbo_mouse_pos = self.win2glfb(win_mouse_pos)
        grid_mouse_pos_f = self.win2dffb(win_mouse_pos)
        grid_mouse_pos = Coord2(int(grid_mouse_pos_f.x), int(grid_mouse_pos_f.y))
        map_mouse_pos = Coord3(self.render_origin.x + grid_mouse_pos.x, 
            self.render_origin.y + grid_mouse_pos.y, self.render_origin.z)
        
        mc = abs ( (tick % 1000)/500.0 - 1)
        mouse_color = ( mc, mc, mc, 1.0)
        
        if self.hp_debug.active:
            # todo: render debug data in single pass instead of what's below
            # outputting a second color output to a separate fbo
            black = (0,0,0,1)
            fbosz = Size2(self.fbo.size.w, self.fbo.size.h)
            self.debug_fbo.resize(fbosz)
            self.debug_fbo.bind(clear = black)
            nomouse = Coord2(-1, -1)
            self._render_one_grid(self.render_origin, nomouse, black, 1.0, frame_no, debug = True)
            # the tile under the mouse
            trect = Rect((fbo_mouse_pos.x//self.psz.x) * self.psz.x,
                         (fbo_mouse_pos.y//self.psz.y) * self.psz.y,
                          self.psz.x, self.psz.y)
            # read it back
            pixels = self.debug_fbo.readpixels(trect)
            self.hp_debug.update(self.winsize, pixels, self.psz, trect)
        
        self.fbo.bind(clear = bgc)

        zed = self.render_origin.z
        zd = self._zdtab[self._zeddown]
        for i in range(1-len(zd), 1): # draw starting from -zeddown zlevels and up
            # draw the map.
            if i + zed < 0:
                continue
            render_origin = self.render_origin._replace(z = i + zed)
            darken = zd[-i]
            self._render_one_grid(render_origin, 
                    grid_mouse_pos, mouse_color, darken, frame_no,
                    hidden = self.show_hidden)

        self.fbo.blit(self.map_viewport)
        panels = [ self.hp_renderer, self.hp_mouse, self.hp_cheat, self.hp_debug ]

        self.hp_renderer.update(self.winsize, self.map_viewport,
            gfps = self.fps.value(self.last_render_time), anim_fps = self.anim_fps, frame_no = frame_no,
            origin = self.render_origin, grid = self.grid.size, map = self.gamedata.dim,
            pszar = self.Pszar, psz = self.psz, 
            winsize = self.winsize, fbosize = self.fbo.size,
            show_hidden = self.show_hidden)
            
        self.hp_mouse.update(self.winsize, self.hp_renderer, self, 
            win_mouse_pos, fbo_mouse_pos, grid_mouse_pos, grid_mouse_pos_f, map_mouse_pos)
        self.hp_cheat.update(self.winsize)
        self.hud.reshape(self.winsize)
        self.hud.render(panels)
        sdl_flip(self.window)
        return sdltimer.get_ticks() - tick
        
    def zpan(self, delta):
        z = self.render_origin.z + delta
        if z  < 0:
            z = 0
        elif z > self.gamedata.dim.z - 1:
            z = self.gamedata.dim.z - 1
        self.render_origin = self.render_origin._replace(z=z)
            
    def loop(self, choke):
        last_frame = self.gamedata.codedepth - 1
        frame_no = 0
        last_render_ts = 0
        render_choke = 1000.0/choke if choke > 0 else 0 # ala G_FPS_CAP but in ticks
        
        last_animflip_ts = 0
        anim_period = 1000.0 / self.anim_fps
                
        paused = False
        finished = False
        panning = False
        
        scrolldict = {  SDLK_LEFT: ( -1, 0),
                        SDLK_RIGHT: ( 1, 0),
                        SDLK_UP: ( 0, -1),
                        SDLK_DOWN: ( 0, 1),
                        SDLK_HOME: ( -1, -1),
                        SDLK_PAGEUP: ( 1, -1),
                        SDLK_END: ( -1, 1),
                        SDLK_PAGEDOWN: ( 1, 1), }
        
        def had_input():
            if not self.had_input:
                self.had_input = True
                self.hp_cheat.active = False
        
        while not finished:
            now = sdltimer.get_ticks()
            self.last_render_time = now - last_render_ts
            last_render_ts = now

            if not paused:
                if now - last_animflip_ts > anim_period:
                    frame_no += 1
                    last_animflip_ts = now
                    if frame_no > last_frame:
                        frame_no = 0
            
            render_time = self.render(frame_no)
            
            while not finished: # hang around in case fps is user-limited
                while True:  # eat events
                    ev = sdlevents.poll_event(True)
                    if ev is None:
                        break
                    elif ev.type == SDL_KEYDOWN:
                        kcode = ev.key.keysym.sym
                        if kcode == SDLK_SPACE:
                            paused = not paused
                        elif kcode == SDLK_F1:
                            self.hp_cheat.active = not self.hp_cheat.active
                        elif kcode == SDLK_F2:
                            self.dump_fbos()
                        elif kcode == SDLK_ESCAPE:
                            if self.had_input:
                                finished = True
                                break
                            else:
                                self.hp_cheat.active = False
                        elif kcode == SDLK_KP_MULTIPLY:
                            self.show_hidden = False if self.show_hidden else True
                        elif kcode in (SDLK_KP_DIVIDE, SDLK_BACKQUOTE):
                            self.hp_debug.active = False if self.hp_debug.active else True
                        elif kcode == SDLK_PERIOD and ev.mod & KMOD_SHIFT:
                            self.zpan(-1)
                        elif kcode == SDLK_COMMA  and ev.mod & KMOD_SHIFT:
                            self.zpan(1)
                        elif kcode in scrolldict:
                            boost = 10 if ev.mod & 3 else 1
                            self.pan(Coord2(scrolldict[kcode][0] * boost * self.psz.x, 
                                scrolldict[kcode][1] * boost * self.psz.y))
                        elif kcode == SDLK_BACKSPACE:
                            self.render_origin = self.gamedata.window
                        elif kcode == SDLK_KP_PLUS:
                            if self.anim_fps > 1:
                                self.anim_fps += 1
                            elif self.anim_fps > 0.5:
                                self.anim_fps = 1
                            else:
                                self.anim_fps *= 2
                            anim_period = 1000.0 / self.anim_fps
                        elif kcode == SDLK_KP_MINUS:
                            if self.anim_fps > 1:
                                self.anim_fps -= 1
                            else:
                                self.anim_fps /= 2
                            anim_period = 1000.0 / self.anim_fps
                        had_input()

                    elif ev.type == SDL_QUIT:
                        finished = True
                        break
                    elif ev.type ==  SDL_WINDOWEVENT:
                        if ev.window.event == sdlvideo.SDL_WINDOWEVENT_RESIZED:
                            self.reshape(Size2(ev.window.data1, ev.window.data2))
                    elif ev.type == SDL_MOUSEBUTTONDOWN:
                        had_input()
                        if ev.button.button == SDL_BUTTON_RIGHT: # RMB
                            panning = True
                        elif ev.button.button == SDL_BUTTON_LEFT:
                            paused = not paused
                    elif ev.type == SDL_MOUSEBUTTONUP:
                        if ev.button.button == SDL_BUTTON_RIGHT:
                            panning = False
                    elif ev.type == SDL_MOUSEMOTION:
                        if panning:
                            self.pan(Coord2(ev.motion.xrel, ev.motion.yrel))
                    elif ev.type == SDL_MOUSEWHEEL:
                        had_input()
                        kmodstate = sdlkeyboard.get_mod_state()
                        amount = -ev.wheel.y
                        mpos = Coord2._make(sdlmouse.get_mouse_state()[1:])
                        if kmodstate & KMOD_CTRL:
                            if amount > 0:
                                self.zoom("zoom_in", mpos)
                            else:
                                self.zoom("zoom_out", mpos)
                        elif kmodstate & KMOD_SHIFT:
                            self.zpan(10 * amount)
                        else:
                            self.zpan(1 * amount)

                elapsed_ticks = sdltimer.get_ticks() - last_render_ts
                if elapsed_ticks > render_choke:
                    break
                sdltimer.delay(8)
    def fini(self):
        # somehow kill entire gl context
        pass

def main():
    ap = argparse.ArgumentParser(description = 'full-graphics renderer testbed')     
    ap.add_argument('-afps', metavar='afps', type=float, default=12, help="animation fps")
    ap.add_argument('-zeddown', metavar='zlevels', type=int, help="number of z-levels to draw below current", default=4)
    ap_render_args(ap)
    ap_data_args(ap)
    pa = ap.parse_args()
    
    logconfig(pa.glinfo, pa.calltrace)
    window, context = sdl_init()
    glinfo()
    
    mo = MapObject(pa.dfdir, pa.rawsdir, pa.apidir)
    mo.use_dump(pa.dfdump)
    rednr = Rednerer(window, pa.ss, mo, pa.psize, pa.par, pa.zeddown, pa.afps)
    rednr.loop(pa.choke)
    rednr.fini()
    
if __name__ == "__main__":
    main()

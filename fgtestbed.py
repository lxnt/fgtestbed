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
import argparse, traceback, os, types, mmap, logging

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
    Mouse wheel, < >:                up/down Z-level
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
            grid_size, pszar, tileclass, 
            tex, txsz,
            render_origin,
            mouse_pos, mouse_color,
            show_hidden, debug_active, 
            falpha, darken, frame_no):
        
        glUseProgram(self.program)

        glUniform3i(self.uloc[b'mapsize'], *map_size)
        glUniform2i(self.uloc[b'gridsize'], *grid_size)
        glUniform3i(self.uloc[b"origin"], *render_origin)
        glUniform3f(self.uloc[b'pszar'], *pszar)
        glUniform4i(self.uloc[b"txsz"], *txsz )  # tex size in tiles, tile size in texels
        
        glUniform1i(self.uloc[b'frame_no'], frame_no)
        glUniform1f(self.uloc[b"darken"], darken)        
        glUniform1i(self.uloc[b"show_hidden"], show_hidden)
        glUniform1i(self.uloc[b'debug'], debug_active)
        
        glUniform2i(self.uloc[b"mouse_pos"], *mouse_pos);
        glUniform4f(self.uloc[b"mouse_color"], *mouse_color)
        
        # ati vs nvidia :(
        tc_uloc = self.uloc[b"tileclass"] if self.uloc[b"tileclass"] != -1 else self.uloc[b"tileclass[0]"]
        glUniform1iv(tc_uloc, len(tileclass), tileclass)
        
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
        glBindTexture(GL_TEXTURE_2D_ARRAY, tex.screen)
        glUniform1i(self.uloc[b"screen"], 3)

class RendererPanel(HudTextPanel):
    def __init__(self, font):
        strs = (
            "gfps: {gfps:2.0f} afps: {anim_fps:02d} frame# {frame_no:03d}",
            "origin: {origin.x}:{origin.y}:{origin.z} grid: {grid.w}x{grid.h} map: {map.x}x{map.y}x{map.z}",
            "pszar: {pszar.x:.2f} {pszar.y:.2f} {pszar.z};  {psz.x}x{psz.y} px",
            "map_viewport: {viewport.x:02d} {viewport.y:02d} {viewport.w:d} {viewport.h:d}",
            "fbo_size={fbosize.w:d}:{fbosize.h:d} win_size={winsize.w:d}:{winsize.h:d}",
            "{debug} {showhidden}", 
        )
        self.active = True
        dummy = Coord3(999,999,999)
        longest_str = strs[1].format(origin=dummy, grid=Size2(999,999), map=dummy)

        super(RendererPanel, self).__init__(font, strs, longest_str)
    
    def update(self, win, map_viewport, debug_active, show_hidden, **kwargs):
        self._data = kwargs
        self._data['viewport'] = map_viewport
        self._data['debug'] = '[debug_active]' if debug_active else '              '
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
            "color: #{color:08x}",
            "win_mp={win_mp.x:d}:{win_mp.y:d}",
            "fbo_mp: {fbo_mp.x:d}:{fbo_mp.y:d}",
            "grid_mp: {grid.x:03d}:{grid.y:03d}",
            "dffb_mp: {dffb.x:.2f}:{dffb.y:.2f}",
            "map_mp: {posn.x:03d}:{posn.y:03d}:{posn.z:03d}",
            "{designation}",
            "mat:  {mat[0]: 3d} ({mat[1]})",
            "bmat:  {bmat[0]: 3d} ({bmat[1]})",
            "tile: {tile[0]: 3d} ({tile[1]})",
            "btile: {btile[0]: 3d} ({btile[1]})", # max 38
            "grass: {grass[0]: 3d} ({grass[1]}) amount={grass[2]:02x}", # max 44
        )
        longest_str = "m"*44
        
        self.active = False
        self._data = {}
        super(MousePanel, self).__init__(font, strs, longest_str)

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
        material, tile, bmat, btile, grass, designation = gamedata.gettile(map_mouse_pos)
        self._data.update({
            'color': color,
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

class Rednerer(object):
    _overdraw = 3 # a constant, can't be less than 3 and better be even
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

    def __init__(self, window, shaderset, gamedata, loud=[], zeddown=2):
        self.window = window
        self.gamedata = gamedata
        self.hud = Hud()
        self.fbo = FBO()
        self.grid = GridVAO()
        self.grid_shader = GridShader(shaderset, 'gl' in loud)
        self.tex = namedtuple("Texnames", "dispatch blitcode font screen")._make(glGenTextures(4))
        
        self.loud_gl      = 'gl' in loud
        self.loud_reshape = 'reshape' in loud
        
        self._zeddown = zeddown
        self.anim_fps = 12
        self.cutoff_frame = gamedata.codedepth - 1
        self.min_psz = 3
        self.max_psz = 1024
        
        self.fps = EmaFilter()
        self.last_frame_time = 16 # milliseconds
        
        self.had_input = False
        self.show_hidden = True
        self.debug_active = False
        
        font = ttf.open_font(b"/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-R.ttf", 18)
        self.hp_renderer = RendererPanel(font) 
        self.hp_mouse = MousePanel(font)
        self.hp_cheat = CheatPanel(font)
        
        self.render_origin = gamedata.window
        self.map_viewport = Rect(0, 0, window._w, window._h)
        
        gamedata.pageman.surface.upload_tex2d(self.tex.font)
        upload_tex2d(self.tex.dispatch, GL_RG16UI,
            gamedata.matcount, gamedata.tiletypecount, 
            GL_RG_INTEGER , GL_UNSIGNED_SHORT, gamedata.disptr)
        
        upload_tex2da(self.tex.blitcode, GL_RGBA32UI,
            gamedata.codew, gamedata.codew, gamedata.codedepth,
            GL_RGBA_INTEGER, GL_UNSIGNED_INT, gamedata.codeptr )
            
        upload_tex2da(self.tex.screen, GL_RGBA32UI,
               gamedata.dim.x, gamedata.dim.y, gamedata.dim.z,
               GL_RGBA_INTEGER, GL_UNSIGNED_INT, gamedata.mapptr)            

        self.txsz = txsz = gamedata.pageman.txsz
        print(txsz)

        if txsz[2] > txsz[3]:
            self.Pszar = Coord3(
                    x = 1.0, 
                    y = txsz[3]/txsz[2],
                    z = txsz[2] )
        else:
            self.Pszar = Coord3(
                    x = txsz[2]/txsz[3],
                    y = 1.0, 
                    z = txsz[3] )

        self.winsize = Size2(window._w, window._h)
        self.reshape(winsize = self.winsize)
        print(self.grid, self.winsize, txsz)
    
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
        print("reshape({}, {}): newgrid={} (map_vp={} Pszar={} psz={})".format(
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
            
        plog = logging.getLogger('fgt.pan').warn

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
        if zcmd == 'zoom_in' and self.Pszar.z > 1:
            psz = self.Pszar.z - 1
        elif zcmd == 'zoom_out' and self.Pszar.z < self.max_psz:
            psz = self.Pszar.z + 1
        elif zcmd == 'zoom_reset':
            psz = max(self.txsz[2], self.txsz[3])
        if zpos is None:
            zpos = Coord2( self.window._w // 2, self.window._h // 2 )
        if psz >= self.min_psz and psz <= self.max_psz:
            self.reshape(zoom = (psz, zpos))

    def _render_one_grid(self, render_origin, mouse_pos, mouse_color, darken, frame_no):
        self.grid_shader(
            map_size = self.gamedata.dim,
            grid_size = self.grid.size, 
            pszar = self.Pszar, 
            tileclass = self.gamedata.tileclass,
            tex = self.tex,
            txsz = self.txsz,
            render_origin = render_origin,
            mouse_pos = mouse_pos, 
            mouse_color = mouse_color,
            show_hidden = 1 if self.show_hidden else 0, 
            debug_active = 1 if self.debug_active else 0, 
            falpha = 1.0, 
            darken = darken,
            frame_no = frame_no)
        try:
            self.grid()
        except:
            gldump()
            raise()

    def render(self, frame_no):
        bgc = GLColor( 0.0, 0.5, 0.0, 1 )
        tick = sdltimer.get_ticks()
        
        win_mouse_pos = Coord2._make(sdlmouse.get_mouse_state()[1:])
        fbo_mouse_pos = self.win2glfb(win_mouse_pos)
        grid_mouse_pos_f = self.win2dffb(win_mouse_pos)
        # TODO: describe the +1 fudge factor.
        # It has to do with glfb - grid conversion which depends somehow
        # on glfb.y/psz.y being floor()-ed or ceil()-ed. 
        grid_mouse_pos = Coord2(int(grid_mouse_pos_f.x),int(grid_mouse_pos_f.y) + 1)
        map_mouse_pos = Coord3(self.render_origin.x + grid_mouse_pos.x, 
            self.render_origin.y + grid_mouse_pos.y, self.render_origin.z)
        
        mc = abs ( (tick % 1000)/500.0 - 1)
        mouse_color = ( mc, mc, mc, 1.0)
        
        self.fbo.bind(clear = bgc)

        zed = self.render_origin.z
        zd = self._zdtab[self._zeddown]
        for i in range(1-len(zd), 1): # draw starting from -zeddown zlevels and up
            # draw the map.
            if i + zed < 0:
                continue
            render_origin = self.render_origin._replace(z = i + zed)
            darken = zd[-i]
            self._render_one_grid(render_origin, grid_mouse_pos, mouse_color, darken, frame_no)

        self.fbo.blit(self.map_viewport)
        panels = [ self.hp_renderer, self.hp_mouse, self.hp_cheat ]

        self.hp_renderer.update(self.winsize, self.map_viewport,
            gfps = self.fps.value(self.last_render_time), anim_fps = self.anim_fps, frame_no = frame_no,
            origin = self.render_origin, grid = self.grid.size, map = self.gamedata.dim,
            pszar = self.Pszar, psz = self.psz, 
            winsize = self.winsize, fbosize = self.fbo.size,
            debug_active = self.debug_active, show_hidden = self.show_hidden)
            
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
            
    def loop(self, anim_fps = 12, choke = 0):
        self.anim_fps = anim_fps
        frame_no = 0
        
        last_render_ts = 0
        render_choke = 1000.0/choke # ala G_FPS_CAP but in ticks
        
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
                    if frame_no > self.cutoff_frame:
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
                        elif kcode == SDLK_ESCAPE:
                            if self.had_input:
                                finished = True
                                break
                            else:
                                self.hp_cheat.active = False
                        elif kcode == SDLK_KP_MULTIPLY:
                            self.show_hidden = False if self.show_hidden else True
                        elif kcode == SDLK_KP_DIVIDE:
                            self.debug_active = False if self.debug_active else True
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
                                self.zoom("zoom_out", mpos)
                            else:
                                self.zoom("zoom_in", mpos)
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
    ap = argparse.ArgumentParser(description = 'full-graphics renderer testbed', 
        epilog =  "Controls:\n" + CONTROLS)
    
    ap.add_argument('-afps', metavar='afps', type=float, default=12, help="animation fps")
    ap.add_argument('-choke', metavar='fps', type=float, default=60, help="renderer fps cap")
    ap.add_argument('-zoom', metavar='px', type=int, default=None, help="set zoom at start")
    ap.add_argument('-zeddown', metavar='zlevels', type=int, help="number of z-levels to draw below current", default=4)
    ap.add_argument('-ss', metavar='sname', help='shader set name', default='three')
    ap.add_argument('dfprefix', metavar="../df_linux", help="df directory to get base tileset and raws from")
    ap.add_argument('dump', metavar="dump-file", help="dump file name")
    ap.add_argument('rawsdir', metavar="raws/dir", nargs='*', help="FG raws dir to parse", default=['fgraws-stdpage'])
    ap.add_argument('-loud', nargs='*', help="spit lots of useless info, values: gl, reshape, parser, ...", default=[])
    ap.add_argument('-inverty', action='store_true', help="invert y-coord in textures", default=False)
    ap.add_argument('-cutoff-frame', metavar="frameno", type=int, default=96, help="frame number to cut animation at")
    pa = ap.parse_args()
    
    window, context = sdl_init()
    if "gl" in pa.loud:
        glinfo()

    mo = MapObject(pa.dfprefix, pa.rawsdir, loud = pa.loud, apidir = '')
    mo.invert_tc = pa.inverty    
    mo.use_dump(pa.dump)
    rednr = Rednerer(window, pa.ss, mo, pa.loud, pa.zeddown)
    if pa.zoom:
        rednr.Psz = pa.zoom
        rednr.reshape(zoompoint = (0,0))
    rednr.loop(pa.afps, pa.choke)
    rednr.fini()
    
if __name__ == "__main__":
    main()

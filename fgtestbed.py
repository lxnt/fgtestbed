#!/usr/bin/python
# -*- encoding: utf-8 -*-
# lxnt has created fgtestbed, a lump of python code
# all masterwork is of dubious quiality.
# it is studded with bugs
# it is encrusted with bugs
# it is smelling with bugs
# it menaces with spikes of bugs
# a picture of giant bug is engraved on its side
# ...
# lxnt cancels Store item in stockpile: interrupted by bug

import sys, time, math, struct, io, ctypes, zlib, ctypes
import collections, argparse, traceback, os, types, mmap
import numpy as np

import pygame

from OpenGL.GL import *
from OpenGL.arrays import vbo
from OpenGL.GL.shaders import *
from OpenGL.GLU import *
from OpenGL.GL.ARB import shader_objects
from OpenGL.GL.ARB.texture_rg import *
from OpenGL.GL.ARB.framebuffer_object import *
from glname import glname as glname

from raw import MapObject

CONTROLS = """ 
    F1: toggle this text
    Right mouse button drag: panning
    Mouse wheel: up/down Z-level
    Shift+mouse wheel: up/down 10 Z-levels
    Ctrl+Mouse wheel: zoom in/out
    Arrow keys, PgUp/PgDn/Home/End: scroll
    Shift+same: faster scroll
    < >: Up/Down z-level
    Backspace: recenter map
    Keypad +/-: adjust animation FPS
    Keypad *: toggle reveal_all
    Left mouse button, Space: toggle animation
    Esc: quit"""

class Shader0(object):
    def __init__(self, loud=False):
        """ dumb constructor, there may be no GL context yet"""
        self.loud = loud
        self.uloc = collections.defaultdict(lambda:-1)
        self.program = None
        self.clean = False
    
    def update_state(self):
        """ user-defined. """
        raise NotImplemented

    def reload(self, vs, fs):
        if self.program:
            self.fini()
        self.init(self, vs, fs)
    
    def compile(self, lines, stype, filename):
        rv = glCreateShader(stype)
        glShaderSource(rv, lines)
        glCompileShader(rv)
        result = glGetShaderiv(rv, GL_COMPILE_STATUS)
        nfo = glGetShaderInfoLog(rv)
        print("compiling {}: result={}; nfo:\n{}".format(filename, result, nfo.strip()))
        return rv
    
    def init(self, vs, fs):
        """ to be called after there is a GL context """
        vsp = self.compile(file(vs).readlines(), GL_VERTEX_SHADER, vs)
        fsp = self.compile(file(fs).readlines(), GL_FRAGMENT_SHADER, fs)
        if not (vsp and fsp):
            raise SystemExit
        
        program = glCreateProgram()

        for shader in (vsp, fsp):
            glAttachShader(program, shader)
            glDeleteShader(shader)
            
        for name, loc in self.aloc.items():
            glBindAttribLocation(program, loc, name)
            if self.loud:
                print "  {0}: name={1} loc={2}".format('-', name, loc)
        glBindFragDataLocation(program, 0, 'color')

        glLinkProgram(program)
    
        link_status = glGetProgramiv( program, GL_LINK_STATUS )
        if link_status == GL_FALSE:
            raise RuntimeError(
                """Link failure (%s): %s"""%(
                link_status,
                glGetProgramInfoLog( program ),
            ))
    
        self.uloc = collections.defaultdict(lambda:-1)
        au = glGetProgramiv(program, GL_ACTIVE_UNIFORMS)
        for i in xrange(au):
            name, wtf, typ = shader_objects.glGetActiveUniformARB(program, i)
            loc = glGetUniformLocation(program, name)
            self.uloc[name] = loc
            if self.loud:
                print "  {0}: name={1} type={2} loc={3}".format(i, name, glname.get(typ, typ), loc)
        
        self.program = program

    def validate(self):
        glValidateProgram(self.program)
        validation = glGetProgramiv( self.program, GL_VALIDATE_STATUS )
        if validation == GL_FALSE:
            raise RuntimeError(
                """Validation failure (%s): %s"""%(
                validation,
                glGetProgramInfoLog(self.program ),
            ))

    def fini(self):
        glDeleteProgram(self.program)
        self.program = None
        self.uloc = {}

    def cleanup(self):
        for loc in self.aloc.values():
            glDisableVertexAttribArray(loc) # is it the right place for this?
        self.clean = False

class Tile_shader(Shader0):
    def __init__(self, renderer, loud=False):
        super(Tile_shader, self).__init__(loud)
        self.rr = renderer        
        self.aloc = { 'position': 0 }

    def update_state(self, falpha=1.0, darken=1.0):
        glUseProgram(self.program)
        
        for loc in self.aloc.values():
            glEnableVertexAttribArray(loc) # is it the right place for this?
        
        glUniform1i(self.uloc['frame_no'], self.rr.frame_no)
        glUniform1f(self.uloc["darken"], darken)

        glUniform2i(self.uloc['grid'], self.rr.grid_w, self.rr.grid_h)
        glUniform3f(self.uloc['pszar'], self.rr.Parx, self.rr.Pary, self.rr.Pszx)
        
        glUniform4i(self.uloc["txsz"], *self.rr.txsz )  # tex size in tiles, tile size in texels
        #glUniform1i(self.uloc["dispatch_row_len"], self.rr.gameobject.hashw);
        glUniform1i(self.uloc["show_hidden"], self.rr.show_hidden);
        
        glUniform2i(self.uloc["mouse_pos"], *self.rr.mouse_in_grid);
        
        mc = abs ( (self.rr.tick % 1000)/500.0 - 1)
        
        glUniform4f(self.uloc["mouse_color"], mc, mc, mc, 1.0)
        
        glUniform3i(self.uloc["origin"], *self.rr.render_origin)
        
        glUniform1iv(self.uloc["tileclass"], 
            len(self.rr.gameobject.tcptr), self.rr.gameobject.tcptr)
        
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.rr.dispatch_txid)
        glUniform1i(self.uloc["dispatch"], 0) # blitter dispatch tiu
        
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D_ARRAY, self.rr.blitcode_txid)
        glUniform1i(self.uloc["blitcode"], 1) # blitter code tiu
        
        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.rr.font_txid)
        glUniform1i(self.uloc["font"], 2) # tilepage tiu
            
        glActiveTexture(GL_TEXTURE3)
        glBindTexture(GL_TEXTURE_2D_ARRAY, self.rr.screen_txid)
        glUniform1i(self.uloc["screen"], 3) # screen tiu
            
        self.rr.grid_vbo.bind()
        glVertexAttribIPointer(self.aloc["position"], 2, GL_SHORT, 0, self.rr.grid_vbo )
        
class Designation(object):
    def __init__(self, u32):
        self.level              =  u32 &   7
        self.pile               = (u32 >>  3) & 1
        self.dig                = (u32 >>  4) & 7
        self.smooth             = (u32 >>  7) & 3
        self.hidden             = (u32 >>  9) & 1
        self.geolayer           = (u32 >> 10) & 15
        self.light              = (u32 >> 14) & 1
        self.subter             = (u32 >> 15) & 1
        self.outside            = (u32 >> 16) & 1
        self.biome              = (u32 >> 17) & 15
        self.ltype              = (u32 >> 21) & 1
        self.aquifer            = (u32 >> 22) & 1
        self.rained             = (u32 >> 23) & 1
        self.traffic            = (u32 >> 24) & 3
        self.flow_forbid        = (u32 >> 26) & 1
        self.liquid_static      = (u32 >> 27) & 1
        self.feat_local         = (u32 >> 28) & 1
        self.feat_global        = (u32 >> 29) & 1
        self.stagnant           = (u32 >> 30) & 1
        self.salt               = (u32 >> 31) & 1
        
    def __str__(self):
        rv = []
        if self.level > 0:
            rv.append([ '', 'stagnant'][self.stagnant])
            rv.append([ '', 'salt'][self.salt])
            rv.append(['water', 'magma'][self.ltype])
            rv.append('level {}'.format(self.level))
        rv.append(['dark', 'light'][self.light])
        rv.append(['inside', 'outside'][self.outside])
        rv.append(['', 'subter'][self.subter])
        rv.append(['', 'rained'][self.light])
        rv.append(['', 'aquifer'][self.aquifer])
        rv.append(['', 'hidden'][self.hidden])
        
        return ' '.join(rv)

class Hud_shader(Shader0):
    def __init__(self, hud_object, loud=False):
        super(Hud_shader, self).__init__(loud)
        self.hud = hud_object
        self.aloc = { 'position': 0 }

    def update_state(self, w, h):        
        glUseProgram(self.program)
    
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.hud.txid)
        glUniform1i(self.uloc["hudtex"], 0)
        
        winw, winh = self.hud.rr.surface.get_size()
        glUniform2i(self.uloc["resolution"], winw, winh) 
        #glUniform2i(self.uloc["size"], w, h) 

        self.hud.vbo.bind()
        glEnableVertexAttribArray(self.aloc["position"])
        glVertexAttribIPointer(self.aloc["position"], 4, GL_INT, 0, self.hud.vbo )

class Hud(object):
    def __init__(self, renderer):
        self.rr = renderer
        self.bg = pygame.Color( 0x000000B0 )
        self.fg = pygame.Color( 0xccccccff)
        self.margin = 8
        self.padding = 8
        self.ema_rendertime = 16.0 # seed value; approx 60 fps
        self.ema_alpha = 0.01
        # tile name maxlength = 25
        # same for material   = 23
        # max chars in hud: 31
        self.strs = (
            "gfps: {gfps:2.0f} afps: {fps:02d} frame# {fno:03d} color: #{color:08x}",
            "zoom: {psz} grid: {gx}x{gy} map: {xdim}x{ydim}x{zdim}",
            "x={tx:03d} y={ty:03d} z={z:03d}  dump10: {dump10[0]}:{dump10[1]}",
            "{designation}",
            "mat:  {mat[0]} ({mat[1]})    bmat:  {bmat[0]} ({bmat[1]})",
            "tile: {tile[0]} ({tile[1]}) ",
            "btile: {btile[0]} ({btile[1]})",
            "grass: {grass[0]} ({grass[1]}) amount={grass[2]:02x}" )
            
    def init(self):
        self.font = pygame.font.SysFont("ubuntumono", 18, False)
        self.ystep = self.font.get_linesize()
        self.txid = glGenTextures(1)
        self.hud_w = 2*self.padding + self.font.size("n"*25 + "m"*25)[0]
        self.hud_h = 2*self.padding + self.font.get_linesize() * len(self.strs)
        self.hudsurf = pygame.Surface( ( self.hud_w, self.hud_h ), pygame.SRCALPHA, 32)
        cheat_lines = map(lambda x: x.strip(), CONTROLS.split("\n"))
        cs_maxline = max(map( lambda x: self.font.size(x)[0], cheat_lines ))
        cw = 2*self.padding + cs_maxline
        ch = 2*self.padding + self.ystep * len(cheat_lines)
        self.cheatsurf = pygame.Surface( ( cw, ch ), pygame.SRCALPHA, 32)
        self.cheatsurf.fill(self.bg)

        i=0
        for l in cheat_lines:
            try:
                surf = self.font.render(l, True, self.fg)
            except ValueError, e:
                print e
                print s, repr(data)
            self.cheatsurf.blit(surf, (self.padding, self.padding + i * self.ystep) )            
            i+=1
        self.vbo = None

    def fini(self):
        glDeleteTextures(self.txid)

    def ema_fps(self):
        val = self.rr.last_render_time
        self.ema_rendertime = self.ema_alpha*val + (1-self.ema_alpha)*self.ema_rendertime
        return 1000.0/self.ema_rendertime

    def restore9(self, v):
        return None

    def restore10(self, v):
        A = ( ( v & 0xFE000000 ) >> 22 ) | ( ( v & 0x00E00000 ) >> 21 )
        B = ( ( v & 0x001E0000 ) >> 11 ) | ( (v & 0x0000FF00) >> 10 )
        return A,B
        
    def restore12(self, v):
        return ( v >> 20, ( v >> 8 ) & ((1<<12)-1) )        

    def update(self):
        self.rr.update_mouse()
        tx, ty, tz =  self.rr.mouse_in_world
        material, tile, bmat, btile, grass, designation = self.rr.gameobject.gettile((tx,ty,tz))
        color = self.rr.getpixel(self.rr.mouse_in_gl)
        data = {
            'fps': self.rr.anim_fps,
            'gfps': self.ema_fps(),
            'fno':  self.rr.frame_no,
            'tx': tx,
            'ty': ty,
            'z': tz,
            'psz': self.rr.Psz,
            'gx': self.rr.grid_w,
            'gy': self.rr.grid_h,
            'xdim': self.rr.gameobject.xdim,
            'ydim': self.rr.gameobject.ydim,
            'zdim': self.rr.gameobject.zdim,
            'tile': tile,
            'mat': material,
            'btile': btile,
            'bmat': bmat,
            'grass': grass,
            'color': color,
            'dump12': self.restore12(color),
            'dump10': self.restore10(color),
            'dump9': self.restore9(color),
            'vp': self.rr.viewpos,
            'pszx': self.rr.Pszx,
            'pszy': self.rr.Pszy,
            'origin': self.rr.render_origin,
            'fbosz': self.rr.fbo.size,
            'fbovsz': self.rr.fbo.viewsize,
            'fbovp': self.rr.fbo.viewpos,
            'designation': Designation(designation),
            'win': self.rr.surface.get_size(), }

        self.hudsurf.fill(self.bg)
        i = 0
        for s in self.strs:
            try:
                surf = self.font.render(s.format(**data), True, self.fg)
            except ValueError, e:
                print e
                print s, repr(data)
            self.hudsurf.blit(surf, (self.padding, self.padding + i * self.ystep) )
            i += 1
    
    def draw(self):
        self.update()
        class rect(object):
            def __str__(self):
                return repr( ( (self.left, self.bottom), (self.right, self.top ),( self.w, self.h) ))
        
        w, h = self.hudsurf.get_size()
        win_w, win_h = self.rr.surface.get_size()
        
        left, bottom = win_w - self.margin - w, win_h - self.margin  - h
        self._draw_quad(self.hudsurf, ( left, bottom ) )
        
        if self.rr.cheat:
            w, h = self.cheatsurf.get_size()
            left = win_w/2 - w/2
            bottom = win_h/2 - h/2
            self._draw_quad(self.cheatsurf, ( left, bottom ) )
        
        self.rr.hudshader.cleanup()

    def _draw_quad(self, surf, dst): # dst assumed to be (left, bottom). surface not pre-flipped.
        x,y = dst
        w,h = surf.get_size()
        data = np.array( (
             ( x,   y,   0, 1), # left-bottom
             ( x,   y+h, 0, 0), # left-top
             ( x+w, y+h, 1, 0), # right-top
             ( x+w, y,   1, 1), # right-bottom
        ), dtype=np.int32 ) 
        if self.vbo is None:
            # todo: make in STATIC_DRAW and reset only on resize
            self.vbo = vbo.VBO(data, usage=GL_DYNAMIC_DRAW) 
        else:
            self.vbo.set_array(data)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D,  self.txid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 
            0, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(surf, "RGBA"))
        self.rr.hudshader.update_state(w, h)
        glDrawArrays(GL_QUADS, 0, 4)
        
class Fbo(object):
    def __init__(self, renderer):
        self.rr = renderer
        self.u_reshape = False
        
    def check(self, tgt = GL_FRAMEBUFFER):
        x = glCheckFramebufferStatus(tgt)
        if x != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("framebuffer incomplete: {}".format(glname.get(x,x)))
        
    def init(self):
        self.map = glGenFramebuffers(1)
        self.mapr = glGenRenderbuffers(1)

    def fini(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDeleteRenderbuffers(1, [self.mapr])
        glDeleteFramebuffers(1, [self.map])

    def reshape(self, size, viewsize):
        glBindFramebuffer(GL_FRAMEBUFFER, self.map)
        glBindRenderbuffer(GL_RENDERBUFFER, self.mapr)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, size[0], size[1])
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, self.mapr)
        self.check()
        self.size = size
        self.viewsize = viewsize
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    
    def update(self, viewpos):
        self.viewpos = viewpos
    
    def bind(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.map)
        glViewport( 0, 0, self.size[0], self.size[1])
    
    def compose(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.map)
        
        x0 = self.viewpos[0]
        y0 = self.viewpos[1]
        x1 = self.viewsize[0] + x0
        y1 = self.viewsize[1] + y0

        glBlitFramebuffer( 
            x0, y0, x1, y1,
            0, 0, self.viewsize[0], self.viewsize[1],
            GL_COLOR_BUFFER_BIT, GL_NEAREST)

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self.viewsize[0], self.viewsize[1])


class Rednerer(object):
    _zdtab = [  # darkening coefficients for drawing multiple z-levels.
        [1.0],
        [1.0, 0.50 ],
        [1.0, 0.66, 0.33],
        [1.0, 0.60, 0.45, 0.30, 0.15 ],
        [1.0, 0.60, 0.50, 0.40, 0.30, 0.20]  ]

    def __init__(self, vs, fs, loud=[], zeddown=2):
        self.vs, self.fs = vs, fs
        self.fbo = Fbo(self)
        self.hud = Hud(self)
        self.mapshader = Tile_shader(self, loud='shaders' in loud)
        self.hudshader = Hud_shader(self.hud, loud='shaders' in loud)
        
        self.do_update_attrs = True
        self.opengl_initialized = False
        
        self.snap_to_grid = False
        self.do_reset_glcontext = False
        self.conf_stretch_tiles = False
        self.conf_snap_window = False
        self.loud_gl      = 'gl' in loud
        self.loud_reshape = 'reshape' in loud
        self.crap = True
        
        self.tilesizes = None # txco texture
        self.grid = None # grid vaa/vbo
        self.screen = None # frame data
        self.surface = None
        self.grid_w = self.grid_h = None
        self.mouse_in_world = (0, 0, 0)
        self.mouse_in_grid = (100500, 100500)
        self.mouse_in_gl = (0, 0)
        self.anim_fps = 12
        self._zeddown = zeddown
        self.cheat = True
        self.had_input = False
        self.show_hidden = 1
        
        pygame.font.init()
        pygame.display.init()
        pygame.display.set_caption("full-graphics testbed", "fgtestbed")

        default_res = ( 1280, 800 )
        self.set_mode(default_res) # does opengl_init() for us

    def set(self, gamoebject):
        self.gameobject = gamoebject
        self.cutoff_frame = gamoebject.codedepth - 1
        self.recenter()
        self.update_textures() # sets up self.txsz
        self.viewpos = (0,0)
        self.reshape() # sets up Psz, viewpos_ and grid.

    def set_mode(self, size):
        if self.surface is None:
            res_change = True
        else:
            res_change = self.surface.get_size() != size
            
        if self.opengl_initialized and not res_change:
            return True # nothing to do
        
        if self.opengl_initialized and self.do_reset_glcontext:
            self.opengl_fini()
        
        flags = pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE
        
        pygame.display.set_mode(size, flags)
        self.surface = pygame.display.get_surface()
        
        if not self.opengl_initialized:
            self.opengl_init()

        return True

    def opengl_init(self):
        if self.loud_gl:
            self.glinfo()

        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_NOTEQUAL, 0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)
        glEnable(GL_POINT_SPRITE)
        glEnable(GL_PROGRAM_POINT_SIZE)
        #glDisable(GL_POINT_SMOOTH)
        glPointParameteri(GL_POINT_SPRITE_COORD_ORIGIN, GL_UPPER_LEFT)
        self.maxPsz = glGetInteger(GL_POINT_SIZE_MAX)
        
        self.fbo.init()
        self.hud.init()
        
        self.grid_vbo = None
        self._txids = glGenTextures(4)
        self.dispatch_txid, self.blitcode_txid, self.font_txid, self.screen_txid = self._txids
        
        self.mapshader.init(self.vs, self.fs)
        self.hudshader.init("hud.vs", "hud.fs")
        
        self.opengl_initialized = True

    def opengl_fini(self):
        self.mapshader.fini()
        self.hudshader.fini()
        self.hud.fini()
        self.fbo.fini()
        glDeleteTextures(self._txids)
        self.grid_vbo = None
        self.maxPsz = None
        self.Parx = self.Pary = self.Psz = self.Pszx = self.Pszy = None
        self.dispatch_txid = self.blitcode_txid = self.font_txid = self._txids = None
        self.opengl_initialized = False

    def _upload_tex2d(self, txid, informat, tw, th, dformat, dtype, dptr):
        glBindTexture(GL_TEXTURE_2D,  txid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, informat, tw, th, 0, dformat, dtype, dptr)

    def _upload_tex2da(self, txid, informat, tw, th, td, dformat, dtype, dptr):
        glBindTexture(GL_TEXTURE_2D_ARRAY,  txid)
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, informat, tw, th, td, 0, dformat, dtype, dptr)       

    def update_textures(self):
        self.txsz = self.gameobject.txsz
        
        print "font: {}x{} {}x{} tiles, {}x{}, {}K".format(
            self.txsz[0], self.txsz[1], self.txsz[2], self.txsz[3],
            self.txsz[0]*self.txsz[2], self.txsz[1]*self.txsz[3],  
            self.txsz[0]*self.txsz[2]*self.txsz[1]*self.txsz[3]*4>>10)        
        
        self._upload_tex2d(self.font_txid, GL_RGBA8, 
            self.txsz[0]*self.txsz[2], self.txsz[1]*self.txsz[3],
            GL_RGBA, GL_UNSIGNED_BYTE, self.gameobject.fontptr)
        
        self._upload_tex2d(self.dispatch_txid, GL_RG16UI,
            self.gameobject.matcount, self.gameobject.tiletypecount, 
            GL_RG_INTEGER , GL_UNSIGNED_SHORT, self.gameobject.disptr)
        
        self._upload_tex2da(self.blitcode_txid, GL_RGBA32UI,
            self.gameobject.codew, self.gameobject.codew, self.gameobject.codedepth,
            GL_RGBA_INTEGER, GL_UNSIGNED_INT, self.gameobject.codeptr )
            
        self._upload_tex2da(self.screen_txid, GL_RGBA32UI,
               self.gameobject.xdim, self.gameobject.ydim, self.gameobject.zdim,
               GL_RGBA_INTEGER, GL_UNSIGNED_INT, self.gameobject.mapptr)            

        self.Psz = max(self.txsz[2:])
        self.Pszx, self.Pszy = self.txsz[2:]
        if self.txsz[2] > self.txsz[3]:
            self.Parx = 1.0
            self.Pary = float(self.txsz[3])/self.txsz[2]
        else:
            self.Parx = float(self.txsz[2])/self.txsz[3]
            self.Pary = 1.0

    def update_grid(self, size):
        w, h = size
        rv = np.zeros((2*w*h,) , np.uint16)
        i = 0
        for xt in xrange(0, w):
            for yt in xrange(0, h):
                rv[2 * i + 0] = xt
                rv[2 * i + 1] = yt
                i += 1

        self.grid_w, self.grid_h = w, h
        self.grid_tile_count = w*h
        self.grid = rv
        if self.grid_vbo is None:
            self.grid_vbo = vbo.VBO(self.grid, usage=GL_STATIC_DRAW)
        else:
            self.grid_vbo.set_array(self.grid)

    def reshape(self, winsize = None, zoompoint = None):
        assert self.Parx is not None
        delta_w = delta_h = 0
        if winsize: # if we have to reset mode, likely on resize
            oldsize = self.surface.get_size()
            self.set_mode(winsize)
            delta_w = oldsize[0] - winsize[0]
            delta_h = oldsize[1] - winsize[1]
            
        window = self.surface.get_size()
        
        orig_pszxy = (self.Pszx, self.Pszy)
        orig_grid_h = self.grid_h
        
        self.Pszx = int(self.Psz * self.Parx)
        self.Pszy = int(self.Psz * self.Pary)
        
        newgrid = ( window[0] / self.Pszx + 4, window[1] / self.Pszy + 4)
        if self.grid_w is not None:
            delta_gw = newgrid[0] - self.grid_w
            delta_gh = newgrid[1] - self.grid_h
        else:
            delta_gw = delta_gh = 0
        
        self.update_grid(newgrid)
        self.fbo.reshape((newgrid[0]*self.Pszx, newgrid[1]*self.Pszy), window)

        if delta_w != 0 or delta_h != 0: # aha, a resize.
            # center of map viewport should be kept stationary wrt whole display
            self.pan((-delta_w/2, -delta_h/2))

        elif zoompoint:
            # the zoompoint should be kept stationary wrt whole display
            # zoom out: delta_psz is negative, render_origin decreases
            
            delta_pszx, delta_pszy =  orig_pszxy[0] - self.Pszx, orig_pszxy[1] - self.Pszy
            mtx, mty = zoompoint[0]/orig_pszxy[0], zoompoint[1]/orig_pszxy[1]
            mty = orig_grid_h - mty
            delta_vp =  mtx * delta_pszx, mty * delta_pszy
            self.pan(delta_vp)
            self.update_mouse()
        else: 
            # if not zoom and not resize?
            pass

    def pan(self, rel):
        vpx, vpy = self.viewpos
        xpad, ypad = self.Pszx, self.Pszy
        x, y, unused = self.render_origin

        vpx -= rel[0]
        vpy += rel[1]        
        
        if vpx > 2 * xpad:
            delta = vpx - 2 * xpad 
            x += delta / xpad + 1
            vpx = delta % xpad + xpad
            
        elif vpx < xpad:
            delta = xpad - vpx
            x -= delta/xpad + 1
            vpx = 2*xpad - abs(delta) % xpad
    
        if vpy > 2 * ypad:
            delta = vpy - 2*ypad
            y -= delta/ypad + 1
            vpy = delta % ypad + ypad

        elif vpy <  ypad:
            delta = ypad - vpy
            y += delta/ypad + 1
            vpy = 2*ypad - abs(delta) % ypad

        self.viewpos = [ vpx, vpy ]
        self.render_origin[:2] = x, y

    def glinfo(self):
        strs = {
            GL_VENDOR: "vendor",
            GL_RENDERER: "renderer",
            GL_VERSION: "version",
            GL_SHADING_LANGUAGE_VERSION: "GLSL version",
        }
        ints = [
            (    7, GL_MAX_VERTEX_ATTRIBS, "GL_MAX_VERTEX_ATTRIBS" ), # number of vec4 attribs available
            (    9, GL_MAX_VERTEX_UNIFORM_COMPONENTS, "GL_MAX_VERTEX_UNIFORM_COMPONENTS" ), # single-component values
            (    8, GL_MAX_FRAGMENT_UNIFORM_COMPONENTS, "GL_MAX_FRAGMENT_UNIFORM_COMPONENTS" ), # same as above
            (    1, GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS, "GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS" ), # samplers in vert shader
            (    2, GL_MAX_TEXTURE_IMAGE_UNITS, "GL_MAX_TEXTURE_IMAGE_UNITS" ),  # samplers in frag shader
            (    3, GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS, "GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS" ), # samplers in vert shader
            (   12, GL_MAX_VARYING_FLOATS, "GL_MAX_VARYING_FLOATS" ), # 4 varying_floats = 1 texture_coord?
            (    3, GL_MAX_TEXTURE_COORDS, "GL_MAX_TEXTURE_COORDS" ), # 1 texture_coord = 4 varying_floats?
            (   -4, GL_POINT_SIZE_MIN, "GL_POINT_SIZE_MIN" ),
            (   32, GL_POINT_SIZE_MAX, "GL_POINT_SIZE_MAX" ), # no idea of our requirements
            ( 2048, GL_MAX_RECTANGLE_TEXTURE_SIZE, "GL_MAX_RECTANGLE_TEXTURE_SIZE" ),
        ]
        exts = glGetString(GL_EXTENSIONS)
        for e,s in strs.items():
            print "{0}: {1}".format(s, glGetString(e))
        for t in ints:
            p = glGetInteger(t[1])
            if (p<t[0]) or ((t[0]<0) and (p+t[0] >0)):
                w = "** "
            else:
                w = ""
            print "{3}{0}: {1} needed:{2}".format(t[2], p, abs(t[0]), w)

    def zoom(self, zcmd, zpos = None):
        if zcmd == 'zoom_in' and self.Psz > 1:
            self.Psz -= 1
        elif zcmd == 'zoom_out' and self.Psz < self.maxPsz:
            self.Psz += 1
        elif zcmd == 'zoom_reset':
            self.Psz = max(self.txsz[2], self.txsz[3])
        self.reshape(zoompoint = zpos)

    def update_mouse(self):
        mx, my = pygame.mouse.get_pos()
        my = self.surface.get_height() -  my
        self.mouse_in_gl = (mx, my)
        fbx, fby = mx + self.viewpos[0], my + self.viewpos[1]
        mtx, mty = fbx/self.Pszx, fby/self.Pszy

        mwx, mwy, mwz =  ( mtx + self.render_origin[0], 
                                self.grid_h - mty + self.render_origin[1] - 1, # no idea where this -1 comes from. srsly.
                                self.render_origin[2] )
        if self.gameobject.inside(mwx, mwy, mwz):
            self.mouse_in_grid = ( mtx, self.grid_h -  mty - 1)
        else:
            self.mouse_in_grid = ( 100500, 100500 )
        self.mouse_in_world = [ mwx, mwy, mwz ]
        
    def getpixel(self, posn):
        return  int(glReadPixels(posn[0], posn[1], 1, 1, GL_RGBA, 
                    GL_UNSIGNED_INT_8_8_8_8)[0][0])
        
    def render(self, frame_no):
        bgc = ( 0.0, 0.0, 0.0, 1 )
        t = pygame.time.get_ticks()
        self.frame_no = frame_no

        self.fbo.update(self.viewpos)
        self.fbo.bind()
        glClearColor(*bgc)
        glClear(GL_COLOR_BUFFER_BIT)

        zed = self.render_origin[2]
        zd = self._zdtab[self._zeddown]
        for i in xrange(1-len(zd), 1): # draw starting from -zeddown zlevels and up
            # draw the map.
            if i + zed < 0:
                continue
            self.render_origin[2] = i + zed
            self.mapshader.update_state(falpha = 1.0, darken = zd[-i])
            glDrawArrays(GL_POINTS, 0, self.grid_tile_count)

        self.mapshader.cleanup()
        self.crap = False
        self.fbo.compose() # blits drawn map into the default FBO.
        
        self.hud.draw()
        pygame.display.flip()
        return  pygame.time.get_ticks() - t
        
    def zpan(self, delta):
        self.render_origin[2]  += delta
        if self.render_origin[2]  < 0:
            self.render_origin[2] = 0
        elif self.render_origin[2] > self.gameobject.zdim - 1:
            self.render_origin[2] = self.gameobject.zdim - 1
        self.mouse_in_world[2] = self.render_origin[2]
            
    def recenter(self):
        self.render_origin = [ self.gameobject.xdim/2, 
                               self.gameobject.ydim/2,
                               self.gameobject.zdim - 23 ]
        if self.render_origin[2] < 0:
            self.render_origin[2] = 0
        self.mouse_in_world = self.render_origin
            
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
        
        scrolldict = {  pygame.K_LEFT: ( -1, 0),
                        pygame.K_RIGHT: ( 1, 0),
                        pygame.K_UP: ( 0, -1),
                        pygame.K_DOWN: ( 0, 1),
                        pygame.K_HOME: ( -1, -1),
                        pygame.K_PAGEUP: ( 1, -1),
                        pygame.K_END: ( -1, 1),
                        pygame.K_PAGEDOWN: ( 1, 1), }
        
        while not finished:
            now = pygame.time.get_ticks()
            self.last_render_time = now - last_render_ts
            last_render_ts = self.tick = now

            if not paused:
                if now - last_animflip_ts > anim_period:
                    frame_no += 1
                    last_animflip_ts = now
                    if frame_no > self.cutoff_frame:
                        frame_no = 0
                        
            
            render_time = self.render(frame_no)
            
            while  True: # eat events
                for ev in pygame.event.get():
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_SPACE:
                            paused = not paused
                        elif ev.key == pygame.K_F1:
                            self.cheat = not self.cheat
                        elif ev.key == pygame.K_ESCAPE:
                            if self.cheat:
                                self.cheat = False
                            else:
                                finished = True
                        elif ev.key == pygame.K_KP_MULTIPLY:
                            if self.show_hidden == 1:
                                self.show_hidden = 0
                            else:
                                self.show_hidden = 1
                        elif ev.key == pygame.K_PERIOD and ev.mod & 3:
                            self.zpan(-1)
                        elif ev.key == pygame.K_COMMA  and ev.mod & 3:
                            self.zpan(1)
                        elif ev.key in scrolldict:
                            if ev.mod & 3:
                                boost = 10
                            else:
                                boost = 1
                            self.render_origin[0] += scrolldict[ev.key][0] * boost
                            self.render_origin[1] += scrolldict[ev.key][1] * boost
                        elif ev.key == pygame.K_BACKSPACE:
                            self.recenter()
                        elif ev.key == pygame.K_KP_PLUS:
                            if self.anim_fps > 1:
                                self.anim_fps += 1
                            elif self.anim_fps > 0.5:
                                self.anim_fps = 1
                            else:
                                self.anim_fps *= 2
                            anim_period = 1000.0 / self.anim_fps
                        elif ev.key == pygame.K_KP_MINUS:
                            if self.anim_fps > 1:
                                self.anim_fps -= 1
                            else:
                                self.anim_fps /= 2
                            anim_period = 1000.0 / self.anim_fps
                        elif ev.key == pygame.K_F2:
                            self.crap = True
                        else:
                            print repr(ev.key), repr(ev)
                        if not self.had_input:
                            self.had_input = True
                            self.cheat = False

                    elif ev.type == pygame.QUIT:
                        finished = True
                    elif ev.type ==  pygame.VIDEORESIZE:
                        self.reshape((ev.w, ev.h))
                    elif ev.type == pygame.MOUSEBUTTONDOWN:
                        if not self.had_input:
                            self.had_input = True
                            self.cheat = False
                        
                        if ev.button == 4: # wheel forward
                            if pygame.key.get_mods() & pygame.KMOD_CTRL:
                                self.zoom("zoom_out", ev.pos)
                            elif pygame.key.get_mods() & pygame.KMOD_SHIFT:
                                self.zpan(-10)
                            else:
                                self.zpan(-1)
                        elif ev.button == 5: # wheel back
                            if pygame.key.get_mods() & pygame.KMOD_CTRL:
                                self.zoom("zoom_in", ev.pos)
                            elif pygame.key.get_mods() & pygame.KMOD_SHIFT:
                                self.zpan(10)
                            else:
                                self.zpan(1)
                        elif ev.button == 3: # RMB
                            panning = True
                        elif ev.button == 1:
                            paused = not paused
                    elif ev.type == pygame.MOUSEBUTTONUP:
                        if ev.button == 3:
                            panning = False
                    elif ev.type == pygame.MOUSEMOTION:
                        if panning:
                            self.pan(ev.rel)
                        
                        self.update_mouse()
                            
                elapsed_ticks = pygame.time.get_ticks() - last_render_ts
                if elapsed_ticks > render_choke:
                    break
                pygame.time.wait(8)

    def fini(self):
        self.opengl_fini()

def main():
    ap = argparse.ArgumentParser(description = 'full-graphics renderer testbed', 
        epilog =  "Controls:\n" + '\n'.join(CONTROLS.split('\n')[2:]) )
    
    ap.add_argument('-afps', metavar='afps', type=float, default=12, help="animation fps")
    ap.add_argument('-choke', metavar='fps', type=float, default=60, help="renderer fps cap")
    ap.add_argument('-irdump', metavar='dfile', help="dump intermediate representation here")
    ap.add_argument('-aldump', metavar='fname', help="dump texture album here, creates fname.png and fname.mapping")
    ap.add_argument('-zeddown', metavar='zlevels', type=int, help="number of z-levels to draw below current", default=4)
    ap.add_argument('-vs', metavar='vertex shader', default='three.vs')
    ap.add_argument('-fs',  metavar='fragment shader', default='three.fs')
    ap.add_argument('dfprefix', metavar="../df_linux", help="df directory to get base tileset and raws from")
    ap.add_argument('dump', metavar="dump-file", help="dump file name")
    ap.add_argument('rawsdir', metavar="raws/dir", nargs='*', help="FG raws dir to parse", default=['fgraws'])
    ap.add_argument('-loud', action='store_true', help="spit lots of useless info")
    ap.add_argument('-cutoff-frame', metavar="frameno", type=int, default=96, help="frame number to cut animation at")        
    pa = ap.parse_args()
    
    loud = ()
    if pa.loud:
        loud = ("gl", "reshape", "shaders", "parser")
    if pa.irdump:
        irdump = file(pa.irdump, 'w')
    else:
        irdump = None

    rednr = Rednerer(vs=pa.vs, fs=pa.fs, loud = loud, zeddown = pa.zeddown)
    mo = MapObject(pa.dfprefix, pa.rawsdir, loud = loud, apidir = '')
    if pa.aldump:
        mo.pagedump(pa.aldump)

    mo.use_dump(pa.dump, pa.irdump)    
    rednr.set(mo)
    rednr.loop(pa.afps, pa.choke)
    rednr.fini()
    
if __name__ == "__main__":
    main()

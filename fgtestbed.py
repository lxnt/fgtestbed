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
import OpenGL.GL.shaders
from OpenGL.GLU import *
from OpenGL.GL.ARB import shader_objects
from OpenGL.GL.ARB.texture_rg import *
from OpenGL.GL.ARB.framebuffer_object import *
from glname import glname as glname

import raw

CONTROLS = """ 
    F1: toggle this text
    Right mouse button drag: panning
    Mouse wheel: up/down Z-level
    Ctrl+Mouse wheel: zoom in/out
    Arrow keys, PgUp/PgDn/Home/End: scroll
    Shift+same: faster scroll
    < >: Up/Down z-level
    Backspace: recenter map
    Keypad +/-: adjust animation FPS
    Left mouse button, Space: toggle animation"""


class mapobject(object):
    def __init__(self, font, matiles, fnprefix, apidir='', cutoff=127):
        self.tileresolve = raw.DfapiEnum(apidir, 'tiletype')
        self.building_t = raw.DfapiEnum(apidir, 'building_type')
        
        self.parse_matsfile(fnprefix + '.materials')
        self.assemble_blitcode(matiles, cutoff)
        self.txsz, self.fontdata = font
        self.maxframes = cutoff + 1
        tilesfile = fnprefix + '.tiles'
        header = file(tilesfile).read(4096)
        if not header.startswith("count_blocks:"):
            raise TypeError("Wrong trousers")
        l, unused = header.split("\n", 1)
        un, x, y, z = l.split(':')
        self.xdim, self.ydim, self.zdim = map(int, [x, y, z])
        self.xdim *= 16
        self.ydim *= 16
        
        if os.name == 'nt':
            self._map_fd = os.open(tilesfile, os.O_RDONLY|os.O_BINARY)
        else:
            self._map_fd = os.open(tilesfile, os.O_RDONLY)

        self._map_mmap = mmap.mmap(self._map_fd, 0, 
            offset = 4096, access = mmap.ACCESS_READ)

    def parse_matsfile(self, matsfile):
        self.inorg_names = {}
        self.inorg_ids = {}
        self.plant_names = {}
        self.plant_ids = {}
        for l in file(matsfile):
            f = l.split()
            if f[1] == 'INORG':
                self.inorg_names[int(f[0])] = ' '.join(f[2:])
                self.inorg_ids[' '.join(f[2:])] = int(f[0])
            elif f[1] == 'PLANT':
                self.plant_names[int(f[0])] = ' '.join(f[2:])
                self.plant_ids[' '.join(f[2:])] = int(f[0])

    def assemble_blitcode(self, mats, cutoff):
        # all used data is available before first map frame is to be
        # rendered in game.
        # eatpage receives individual tile pages and puts them into one big one
        # maptile maps pagename, s, t into tiu, s, t  that correspond to the big one
        # tile_names map tile names in raws to tile_ids in game
        # inorg_ids and plant_ids map mat names in raws to effective mat ids in game
        # (those can change every read of raws)
        
        self.blithash_dt = np.dtype({  # GL_RG16UI
            'names': 's t'.split(),
            'formats': ['u2', 'u2' ],
            'offsets': [ 0, 2 ],
            'titles': ['blitcode s-coord', 'blitcode t-coord'] })
            
        """ GL_RGBA32UI - 128 bits. 16 bytes. Overkill. """
        self.blitcode_dt = np.dtype({
            'names': 'un2 un1 t s mode fg bg'.split(),
            'formats': ['u1', 'u1', 'u1', 'u1', 'u4', 'u4', 'u4'],
            'offsets': [ 0, 1, 2, 3, 4, 8, 12 ] })
        
        tcount = 0
        for mat in mats.values():
            tcount += len(mat.tiles)
        print "{1} mats  {0} defined tiles, assembling...".format(tcount, len(mats.keys()))
        if tcount > 65536:
            raise TooManyTilesDefinedCommaManCommaYouNutsZedonk
        
        self.hashw = 1024 # 20bit hash.
        self.codew = int(math.ceil(math.sqrt(tcount)))
        
        blithash = np.zeros((self.hashw,  self.hashw ), dtype=self.blithash_dt)
        blitcode = np.zeros((cutoff+1, self.codew, self.codew), dtype=self.blitcode_dt)
        
        NOMAT=0x3FF
        def hashit(tile, stone, ore = NOMAT, grass = NOMAT, gramount = NOMAT):
            #mildly esoteric in the presense of NOMAT.
            # it seems grass & layer stone are mutex by tiletype.
            # so we just do:
            if gramount != NOMAT and gramount != 0:
                stone = grass
                ore = NOMAT
            # and define GrassWhatEver tiles within only plant materials
            
            # Also since we don't have a plan how to compose ore/cluster tiles yet:
            if ore != NOMAT:
                stone = ore
                ore = NOMAT

            return ( ( stone & 0x3ff ) << 10 ) | ( tile & 0x3ff )
        
        tc = 1
        for name, mat in mats.items():
            if name in self.inorg_ids:
                mat_id = self.inorg_ids[name]
            elif name in self.plant_ids:
                mat_id = self.plant_ids[name]
            else:
                print  "no per-session id for mat '{0}'".format(name)
                continue
            for tname, frameseq in mat.tiles.items():
                x = int (tc % self.codew)
                y = int (tc / self.codew)
                tc += 1
                
                try:
                    tile_id = self.tileresolve[tname]
                except KeyError:
                    print "unk tname {} in mat {}".format(tname, mat.name)
                    raise
                hashed  = hashit(tile_id, mat_id)
                hx = hashed % self.hashw 
                hy = hashed / self.hashw 
                blithash[hy, hx]['s'] = x
                blithash[hy, hx]['t'] = y               
                frame_no = 0
                if len(frameseq[0]) == 3: # fgbg tile
                    blit, fg, bg = frameseq[0]
                    s, t = blit
                    blitcode[frame_no, y, x]['s'] = s
                    blitcode[frame_no, y, x]['t'] = t
                    blitcode[frame_no, y, x]['un1'] = 0
                    blitcode[frame_no, y, x]['un2'] = 0
                    blitcode[frame_no, y, x]['mode'] = 0
                    blitcode[frame_no, y, x]['fg'] = fg
                    blitcode[frame_no, y, x]['bg'] = bg
                    continue
                    
                for insn in frameseq:
                    blit, blend = insn
                    s, t  = blit
                    blitcode[frame_no, y, x]['s'] = s
                    blitcode[frame_no, y, x]['t'] = t
                    blitcode[frame_no, y, x]['mode'] = 1
                    blitcode[frame_no, y, x]['fg'] = blend
                    blitcode[frame_no, y, x]['bg'] = 0
                    frame_no += 1
                    if frame_no > cutoff:
                        break
        self.blithash, self.blitcode = blithash, blitcode

    def upload_font(self, txid_font):
        
        glBindTexture(GL_TEXTURE_2D,  txid_font)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.txsz[0]*self.txsz[2], self.txsz[1]*self.txsz[3],
            0, GL_RGBA, GL_UNSIGNED_BYTE, self.fontdata)        
        print "font: {}x{} {}x{} tiles, {}x{}, {}K".format(
            self.txsz[0], self.txsz[1], self.txsz[2], self.txsz[3],
            self.txsz[0]*self.txsz[2], self.txsz[1]*self.txsz[3],  self.txsz[0]*self.txsz[2]*self.txsz[1]*self.txsz[3]*4>>10)
            
        if False:
            txcos = "\x10\x10\x10\x10" * self.tp.pdim[0] * self.tp.pdim[1]
            glBindTexture(GL_TEXTURE_2D,  txid_txco)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.tp.pdim[0], self.tp.pdim[1],
                0, GL_RGBA, GL_UNSIGNED_BYTE, txcos)
        
        return self.txsz

    def upload_code(self, txid_hash, txid_blit):
        glBindTexture(GL_TEXTURE_2D,  txid_hash)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

        ptr = ctypes.c_void_p(self.blithash.__array_interface__['data'][0])
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RG16UI, self.hashw, self.hashw, 
                     0, GL_RG_INTEGER , GL_UNSIGNED_SHORT, ptr)
        
        glBindTexture(GL_TEXTURE_2D_ARRAY,  txid_blit)
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                    
        ptr = ctypes.c_void_p(self.blitcode.__array_interface__['data'][0])
        glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, GL_RGBA32UI, self.codew, self.codew, self.maxframes,
                     0, GL_RGBA_INTEGER, GL_UNSIGNED_INT, ptr )
                     
        print "hashtable {}K code {}K".format(4*self.hashw*self.hashw>>10, 16*self.codew*self.codew*self.maxframes >>10)

    def getmap(self, origin, size ):
        x,y,z = origin
        w,h = size
        rv = np.zeros((w, h), np.int32)
        if x + w < 0 or y+h < 0 or x > self.xdim or y > self.ydim:
            # black screen
            return rv
        sx = x
        left = 0
        if sx < 0:
            left = -sx
            sx = 0
        ex = x + w
        right = w
        if ex > self.xdim:
            right = self.xdim - ex
            ex = self.xdim
        sy = y
        top = 0
        if sy < 0:
            top = -sy
            sy = 0
        ey = y + h
        bottom = h
        if ey > self.ydim:
            bottom = self.ydim - ey
            ey = self.ydim
        
        zedoffs = self.xdim*self.ydim*4*z
        yoffs = sy*self.xdim*4
        xskip = sx*4
        rowlen = ex-sx
        
        for rownum in xrange( ey - sy ):
            offs = zedoffs + yoffs + rownum*self.xdim*4 + xskip 
            buf = buffer(self._map_mmap, offs, rowlen*4)
            rv[left:right, top+rownum] = np.ndarray((rowlen,), dtype=np.int32, buffer = buf)        
        return rv
        
    def gettile(self, posn):
        x, y, z = posn
        offs = self.xdim*self.ydim*4*z + y*self.xdim*4 + x*4
        hash = struct.unpack("<I", self._map_mmap[offs:offs+4])[0]
        tile_id = hash & 0x3ff
        mat_id = ( hash >> 10 ) & 0x3ff
        try:
            tilename = self.tileresolve[tile_id]
        except IndexError:
            raise ValueError("unknown tile_type {} (in map dump)".format(tile_id))

        matname = self.inorg_names.get(mat_id, None)
        for prefix in ( 'Grass', 'Tree', 'Shrub', 'Sapling'):
            if tilename.startswith(prefix):
                matname = self.plant_names.get(mat_id, None)
                break
        
        return ( (mat_id, matname), (tile_id, tilename) )



class Shader0(object):
    def __init__(self, loud=False):
        """ dumb constructor, there may be no GL context yet"""
        self.loud = loud
        self.uloc = {}
        self.program = None
        self.clean = False
    
    def update_state(self):
        """ user-defined. """
        raise NotImplemented

    def reload(self, vs, fs):
        if self.program:
            self.fini()
        self.init(self, vs, fs)
        
    def init(self, vs, fs):
        """ to be called after there is a GL context """
        try:
            where = 'vertex'
            vsp = compileShader(file(vs).read(), GL_VERTEX_SHADER)
            where = 'fragment'
            fsp = compileShader(file(fs).read(), GL_FRAGMENT_SHADER)
        except RuntimeError, e:
            print where, e[0]#, e[1][0]
            raise SystemExit
        
        program = glCreateProgram()

        for shader in (vsp, fsp):
            glAttachShader(program, shader)
            glDeleteShader(shader)
            
        for name, loc in self.aloc.items():
            glBindAttribLocation(program, loc, name)
        #glBindFragDataLocation(program, 0, 'color')

        glLinkProgram(program)
    
        link_status = glGetProgramiv( program, GL_LINK_STATUS )
        if link_status == GL_FALSE:
            raise RuntimeError(
                """Link failure (%s): %s"""%(
                link_status,
                glGetProgramInfoLog( program ),
            ))
    
        self.uloc = {}
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
        self.aloc = {
            'position': 0, 
            'screen': 1
        }

    def update_state(self, falpha=1.0, darken=1.0):
        glUseProgram(self.program)
        
        for loc in self.aloc.values():
            glEnableVertexAttribArray(loc) # is it the right place for this?
        
        glUniform1i(self.uloc['frame_no'], self.rr.frame_no)
        glUniform1f(self.uloc["final_alpha"], falpha)
        glUniform1f(self.uloc["darken"], darken)

        glUniform2i(self.uloc['grid'], self.rr.grid_w, self.rr.grid_h)
        glUniform3f(self.uloc['pszar'], self.rr.Parx, self.rr.Pary, self.rr.Pszx)
        
        glUniform4i(self.uloc["txsz"], *self.rr.txsz )  # tex size in tiles, tile size in texels
        glUniform1i(self.uloc["dispatch_row_len"], self.rr.gameobject.hashw);
        
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.rr.dispatch_txid)
        glUniform1i(self.uloc["dispatch"], 0) # blitter dispatch tiu
        
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D_ARRAY, self.rr.blitcode_txid)
        glUniform1i(self.uloc["blitcode"], 1) # blitter blit code tiu
        
        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.rr.font_txid)
        glUniform1i(self.uloc["font"], 2) # tilepage tiu
            
        self.rr.screen_vbo.bind()
        glVertexAttribIPointer(self.aloc["screen"], 1, GL_INT, 0, self.rr.screen_vbo )
        
        self.rr.grid_vbo.bind()
        glVertexAttribIPointer(self.aloc["position"], 2, GL_SHORT, 0, self.rr.grid_vbo )


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
            "gfps: {gfps:2.0f} afps: {fps:02d} frame# {fno:03d}",
            "zoom: {psz} grid: {gx}x{gy} map: {xdim}x{ydim}x{zdim}",
            "x={tx:03d} y={ty:03d} z={z:03d}  ",
            "color: #{color:08x}",
            "mat:  {mat} ({mat_id})",
            "tile: {tile} ({tile_id})" )
            
    def init(self):

        self.font = pygame.font.SysFont("sans", 16, True)
        self.ystep = self.font.get_linesize()
        self.txid = glGenTextures(1)
        self.hud_w = 2*self.padding + self.font.size(self.strs[-1] + "m"*25)[0]
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
        self.vbo = vbo.VBO( None )

    def fini(self):
        glDeleteTextures(self.txid)

    def ema_fps(self):
        val = self.rr.last_render_time
        self.ema_rendertime = self.ema_alpha*val + (1-self.ema_alpha)*self.ema_rendertime
        return 1000.0/self.ema_rendertime

    def update(self):
        tx, ty, tz =  self.rr.mouse_in_world
        material, tile = self.rr.gameobject.gettile((tx,ty,tz))
        color = self.rr.getpixel(self.rr.mouseco)
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
            'mat': material[1],
            'tile': tile[1],
            'mat_id': material[0],
            'tile_id': tile[0],
            'color': color,
            'vp': self.rr.viewpos,
            'pszx': self.rr.Pszx,
            'pszy': self.rr.Pszy,
            'origin': self.rr.render_origin,
            'fbosz': self.rr.fbo.size,
            'fbovsz': self.rr.fbo.viewsize,
            'fbovp': self.rr.fbo.viewpos,
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
        self.vbo.set_array( np.array( (
             ( x,   y,   0, 1), # left-bottom
             ( x,   y+h, 0, 0), # left-top
             ( x+w, y+h, 1, 0), # right-top
             ( x+w, y,   1, 1), # right-bottom
        ), dtype=np.int32 ) )
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

class frame_cache_item(object):
    def __init__(self,s):
        self.screen = s
        self.used = 0

class Rednerer(object):
    _zdtab = [  # darkening coefficients for drawing multiple z-levels.
        [1.0],
        [1.0, 0.50 ],
        [1.0, 0.66, 0.33],
        [1.0, 0.60, 0.45, 0.30, 0.15 ],
        [1.0, 0.60, 0.50, 0.40, 0.30, 0.20]  ]
    def __init__(self, vs, fs, go, loud=[], anicutoff=128, zeddown=2):
        self.vs, self.fs = vs, fs
        self.fbo = Fbo(self)
        self.hud = Hud(self)
        self.mapshader = Tile_shader(self, loud='shaders' in loud)
        self.hudshader = Hud_shader(self.hud, loud='shaders' in loud)
        self.gameobject = go
        
        self.do_update_attrs = True
        self.opengl_initialized = False
        
        self.snap_to_grid = False
        self.do_reset_glcontext = False
        self.conf_stretch_tiles = False
        self.conf_snap_window = False
        self.cutoff_frame = anicutoff      
        self.loud_gl      = 'gl' in loud
        self.loud_reshape = 'reshape' in loud

        self.tilesizes = None # txco texture
        self.grid = None # grid vaa/vbo
        self.screen = None # frame data
        self.surface = None
        self.grid_w = self.grid_h = None
        self.mouse_in_world = (0, 0, 0)
        self.mouseco = (0, 0)
        self.anim_fps = 12
        self._frame_cache = {}
        self._zeddown = zeddown
        self.cheat = True
        self.had_input = False

        self.recenter()

        pygame.font.init()
        pygame.display.init()
        pygame.display.set_caption("full-graphics testbed", "fgtestbed")

        default_res = ( 1280, 800 )
        self.set_mode(default_res) # does opengl_init() for us
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
        
        self.screen_vbo = vbo.VBO(None, usage=GL_STREAM_DRAW)
        self.grid_vbo = vbo.VBO(None, usage=GL_STATIC_DRAW)
        self._txids = glGenTextures(3)
        self.dispatch_txid, self.blitcode_txid, self.font_txid = self._txids
        
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
        self.screen_vbo = None
        self.maxPsz = None
        self.Parx = self.Pary = self.Psz = self.Pszx = self.Pszy = None
        self.dispatch_txid = self.blitcode_txid = self.font_txid = self._txids = None
        self.opengl_initialized = False

    def update_mapdata(self):
        fc_key = tuple(self.render_origin + [self.grid_w, self.grid_h])
        if fc_key not in self._frame_cache:
            keys = self._frame_cache.keys()
            if len(keys) > 16:
                keys.sort(lambda x, y: cmp(self._frame_cache[x].used, self._frame_cache[y].used))
                del self._frame_cache[keys[0]]
                
            self._frame_cache[fc_key] = frame_cache_item(self.gameobject.getmap(self.render_origin, (self.grid_w, self.grid_h)))
            
        self.screen_vbo.set_array(self._frame_cache[fc_key].screen)
        self._frame_cache[fc_key].used += 1

    def update_textures(self):
        self.gameobject.upload_code(self.dispatch_txid, self.blitcode_txid)
        self.txsz = self.gameobject.upload_font(self.font_txid)
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
        self.grid_vbo.set_array(self.grid)

    def reshape(self, winsize = None, zoompoint = None):
        assert self.Parx is not None
        delta_w = delta_h = 0
        if winsize: # if we have to reset mode, likely on resize
            oldsize = self.surface.get_size()
            self.set_mode(winsize)
            
        window = self.surface.get_size()
        
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
            if delta_gw != 0:
                self.render_origin[0] -= delta_gw/2
                self.viewpos[0] = self.Pszx
            if delta_gh != 0:
                self.render_origin[0] -= delta_gh/2
                self.viewpos[1] = self.Pszy
        elif zoompoint:
            # the zoompoint should be kept stationary wrt whole display
            self.viewpos = [ self.Pszx, self.Pszy ]
        else: 
            # center of map viewport should be kept stationary wrt whole display
            self.viewpos = [ self.Pszx, self.Pszy ]

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
        self.mouseco = (mx, my)
        fbx, fby = mx + self.viewpos[0], my + self.viewpos[1]
        mtx, mty = fbx/self.Pszx, fby/self.Pszy

        self.mouse_in_world = [ mtx + self.render_origin[0], 
                                self.grid_h - mty + self.render_origin[1] - 1, # no idea where this -1 comes from. srsly.
                                self.render_origin[2] ]
        
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
            self.render_origin[2] = i + zed
            self.update_mapdata()
            falpha = 1.0

            self.mapshader.update_state(falpha, zd[-i])
            glDrawArrays(GL_POINTS, 0, self.grid_tile_count)

        self.mapshader.cleanup()
        
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
            last_render_ts = now
            
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
                        if not self.had_input:
                            self.had_input = True
                            self.cheat = False
                        if ev.key == pygame.K_SPACE:
                            paused = not paused
                        elif ev.key == pygame.K_F1:
                            self.cheat = not self.cheat
                        elif ev.key == pygame.K_ESCAPE:
                            finished = True 
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
                        else:
                            print repr(ev.key), repr(ev)

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
                            else:
                                self.zpan(-1)
                        elif ev.button == 5: # wheel back
                            if pygame.key.get_mods() & pygame.KMOD_CTRL:
                                self.zoom("zoom_in", ev.pos)
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
                        else:
                            self.update_mouse()
                            
                elapsed_ticks = pygame.time.get_ticks() - last_render_ts
                if elapsed_ticks > render_choke:
                    break
                pygame.time.wait(8)

    def fini(self):
        self.opengl_fini()



if __name__ == "__main__":
    ap = argparse.ArgumentParser(description = 'full-graphics renderer testbed', epilog =  """
        FPS is limited to no more than about 100 somewhere.

        Controls:
        LMB : print rgba hexvalue and tile hash components under mouse
        RMB drag, arrows, pgup/down/home/end, shift:  scroll
        mouse wheel: zoom
        backspace: reset scroll
        esc : quit
        keypad +/- : adjust FPS """)
    
    ap.add_argument('-afps', metavar='afps', type=float, default=12, help="animation fps")
    ap.add_argument('-choke', metavar='fps', type=float, default=60, help="renderer fps cap")
    ap.add_argument('-irdump', metavar='dfile', nargs='?', help="dump intermediate representation here")
    ap.add_argument('-zeddown', nargs='?', type=int, help="number of z-levels to draw below current", default=4)
    ap.add_argument('-vs', metavar='vertex shader', default='three.vs')
    ap.add_argument('-fs',  metavar='fragment shader', default='three.fs')
    ap.add_argument('dfprefix', metavar="../df_linux", help="df directory to get base tileset from")
    ap.add_argument('dumpfx', metavar="dump-prefix", help="dump name prefix (foobar in foobar.mats/foobar.tiles)")
    ap.add_argument('rawsdir', metavar="raws/dir", nargs='*', help="raws dirs to parse")
    ap.add_argument('--loud', action='store_true', help="spit lots of useless info")
    ap.add_argument('--cutoff-frame', metavar="frameno", type=int, default=96, help="frame number to cut animation at")        
    pa = ap.parse_args()

    pageman, matiles, maxframe = raw.work(pa.dfprefix, dumpfile=pa.irdump)
    if pa.cutoff_frame > maxframe:
        cutoff = maxframe
    else:
        cutoff = pa.cutoff_frame
    
    mo = mapobject( font = pageman.get_album(),
                    matiles = matiles,
                    fnprefix = pa.dumpfx, 
                    cutoff = cutoff)
    loud = ()
    if pa.loud:
        loud = ("gl", "reshape", "shaders")
    
    re = Rednerer(vs=pa.vs, fs=pa.fs, go=mo, loud = loud, anicutoff = cutoff, zeddown = pa.zeddown)
    re.loop(pa.afps, pa.choke)
    re.fini()
    

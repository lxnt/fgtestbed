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
from OpenGL.GL.ARB.vertex_array_object import *
from glname import glname as glname

import raw

class mapobject(object):
    def __init__(self, font, matiles, matsfile, tilesfile, apidir='', cutoff=127):
        self.tileresolve = raw.Enumparser(apidir)
        self.parse_matsfile(matsfile)
        self.assemble_blitcode(matiles, cutoff)
        self.txsz, self.fontdata = font

        if os.name == 'nt':
            self._map_fd = os.open(tilesfile, os.O_RDONLY|os.O_BINARY)
        else:
            self._map_fd = os.open(tilesfile, os.O_RDONLY)

        self._map_mmap = mmap.mmap(self._map_fd, 0, access = mmap.ACCESS_READ)

    def parse_matsfile(self, matsfile):
        self.inorg_names = {}
        self.inorg_ids = {}
        self.plant_names = {}
        self.plant_ids = {}
        for l in file(matsfile):
            if l.startswith("count_block:"):
                continue
            elif l.startswith("region:"):
                continue
            elif l.startswith("count:"):
                un, x, y, z = l.split(':')
                self.xdim, self.ydim, self.zdim = map(int, [x, y, z])
                continue
                
            f = l.split()
            if f[1] == 'INORG':
                self.inorg_names[int(f[0])] = ' '.join(f[2:])
                self.inorg_ids[' '.join(f[2:])] = int(f[0])
            elif f[1] == 'PLANT':
                self.plant_names[int(f[0])] = ' '.join(f[2:])
                self.plant_ids[' '.join(f[2:])] = int(f[0])

    def assemble_blitcode(self, mats, cutoff_frame = 127):
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
            
        """self.blitcode_dt = np.dtype({  # GL_RGBA16UI - 64 bits. 8 bytes
            'names': 's t blend r g b a'.split(),
            'formats': ['u2', 'u2', 'u4', 'u1', 'u1', 'u1', 'u1'],
            'offsets': [ 0, 2, 4, 4, 5, 6, 7 ],
            'titles': ['s-coord in tiles', 't-coord in tiles', 'blend-rgba', 'br', 'bg', 'bb', 'ba' ] })"""
        self.blitcode_dt = np.dtype({  # GL_RGBA16UI - 64 bits. 8 bytes
            'names': 's t blend'.split(),
            'formats': ['u2', 'u2', 'u4'],
            'offsets': [ 0, 2, 4 ],
            'titles': ['s-coord in tiles', 't-coord in tiles', 'blend-rgba'] })
        
        tcount = 0
        for mat in mats.values():
            tcount += len(mat.tiles)
        print "{1} mats  {0} defined tiles\nAssembling...".format(tcount, len(mats.keys()))
        if tcount > 65536:
            raise TooManyTilesDefinedCommaManCommaYouNutsZedonk
        
        self.hashw = 1024 # 20bit hash.
        self.codew = math.ceil(math.sqrt(tcount))
        
        blithash = np.zeros((self.hashw,  self.hashw ), dtype=self.blithash_dt)
        blitcode = np.zeros((128, self.codew, self.codew), dtype=self.blitcode_dt)
        
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
                for insn in frameseq:
                    blit, blend = insn
                    s, t  = blit
                    blitcode[frame_no, y, x]['s'] = s
                    blitcode[frame_no, y, x]['t'] = t
                    blitcode[frame_no, y, x]['blend'] = blend
                    frame_no += 1
                    if frame_no > cutoff_frame:
                        break
                tc += 1
        self.blithash, self.blitcode = blithash, blitcode

    def upload_font(self, txid_font):
        
        glBindTexture(GL_TEXTURE_2D,  txid_font)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.txsz[0]*self.txsz[2], self.txsz[1]*self.txsz[3],
            0, GL_RGBA, GL_UNSIGNED_BYTE, self.fontdata)        
            
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
        glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, GL_RGBA16UI, self.codew, self.codew, 128,
                     0, GL_RGBA_INTEGER, GL_UNSIGNED_SHORT, ptr )

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
            if tilename is None:
                return '(unk:0x{:03x})'.format(mat_id), '(unk:0x{:03x})'.format(tile_id) 
        except IndexError:
            return '(unk:0x{:03x})'.format(mat_id), '(unk:0x{:03x})'.format(tile_id)
            
        matname = self.inorg_names.get(mat_id, '(unk:0x{:03x})'.format(mat_id))
        for prefix in ( 'Grass', 'Tree', 'Shrub', 'Sapling'):
            if tilename.startswith(prefix):
                matname = self.plant_names.get(mat_id, '(unk:0x{:03x})'.format(mat_id))
                break
        
        return matname, tilename



class Shader0(object):
    def __init__(self, loud=False):
        """ dumb constructor, there may be no GL context yet"""
        self.loud = loud
        self.uloc = {}
        self.program = None
    
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

class Tile_shader(Shader0):
    def __init__(self, renderer, loud=False):
        super(Tile_shader, self).__init__(loud)
        self.rr = renderer        
        self.aloc = {
            'position': 0, 
            'screen': 1
        }

    def update_state(self, shape = False, textures = False, vbos = False):
        glUseProgram(self.program)
        
        for loc in self.aloc.values():
            glEnableVertexAttribArray(loc) # is it the right place for this?
        
        glUniform1i(self.uloc['frame_no'], self.rr.frame_no)
        glUniform1f(self.uloc["final_alpha"], 1.0)

        glUniform2i(self.uloc['grid'], self.rr.grid_w, self.rr.grid_h)
        glUniform3f(self.uloc['pszar'], self.rr.Parx, self.rr.Pary, self.rr.Pszx)
        
        glUniform4i(self.uloc["txsz"], *self.rr.txsz )  # tex size in tiles, tile size in texels
        glUniform1i(self.uloc["dispatch_row_len"], 1024);
        
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.rr.dispatch_txid)
        glUniform1i(self.uloc["dispatch"], 0) # blitter dispatch tiu
        
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D_ARRAY, self.rr.blitcode_txid)
        glUniform1i(self.uloc["blitcode"], 1) # blitter blit code tiu
        
        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.rr.font_txid)
        glUniform1i(self.uloc["font"], 2) # tilepage tilesizes tiu
            
        self.rr.screen_vbo.bind()
        glVertexAttribIPointer(self.aloc["screen"], 1, GL_INT, 0, self.rr.screen_vbo )
        
        self.rr.grid_vbo.bind()
        glVertexAttribIPointer(self.aloc["position"], 2, GL_SHORT, 0, self.rr.grid_vbo )


class Hud_shader(Shader0):
    def __init__(self, hud_object, loud=False):
        super(Hud_shader, self).__init__(loud)
        self.hud = hud_object
        self.aloc = { 'position': 0 }

    def update_state(self):
        glUseProgram(self.program)
        
        glUniform2f(self.uloc["resolution"], self.hud.res_w, self.hud.res_h) 
        glUniform2f(self.uloc["size"], self.hud.hud_w, self.hud.hud_h) 

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.hud.txid)
        glUniform1i(self.uloc["hudtex"], 0) 
        
        self.hud.quad_vbo.bind()
        glVertexAttribIPointer(self.aloc["position"], 2, GL_INT, 0, self.hud.quad_vbo )
        glEnableVertexAttribArray(self.aloc["position"])

class Hud(object):
    def __init__(self, renderer):
        self.rr = renderer
        self.bg = ( 0.1, 0.1, 0.1, 0.25 )
        self.fg = ( 0.8, 0.8, 0.8, 1.0 )
        self.margin = 8
        self.padding = 8
        self.ema_rendertime = 16.0 # seed value; approx 60 fps
        self.ema_alpha = 0.01
        # tile name maxlength = 25
        # same for material   = 23
        # max chars in hud: 31
        self.strs = (
            "gfps: {gfps:2.0f} afps: {fps:02d} frame# {fno:03d}",
            "zoom: {psz} grid={gx}x{gy} vp={vp[0]},{vp[1]} origin {origin[0]}x{origin[1]}",
            "x={tx:03d} y={ty:03d} z={z:03d} [{xdim}x{ydim}x{zdim}] color: #{color:08x}",
            "pszxy {pszx}x{pszy} fsz {fbosz[0]}x{fbosz[1]} win {win[0]}x{win[1]}",
            "mat:  {mat}",
            "tile: {tile}",
            "fbo: size {fbosz[0]}x{fbosz[1]} viewsize {fbovsz[0]}x{fbovsz[1]} viewpos {fbovp[0]},{fbovp[1]}" )
            
    def init(self):
        self.font = pygame.font.SysFont("sans", 16, True)
        self.txid = glGenTextures(1)
        self.hud_w = 2*self.padding + self.font.size(self.strs[-1] + "m"*25)[0]
        self.hud_h = 2*self.padding + self.font.get_linesize() * len(self.strs)
        self.hudsurf = pygame.Surface( ( self.hud_w, self.hud_h ), 0, 32)
        self.quad_vbo = vbo.VBO(np.array( [
            [0,0], [0,1], [1,0],
            [0,1], [1,1], [1,0] ] , dtype=np.float ))

    def fini(self):
        glDeleteTextures(self.txid)

    def ema_fps(self):
        val = self.rr.last_render_time
        self.ema_rendertime = self.ema_alpha*val + (1-self.ema_alpha)*self.ema_rendertime
        return 1000.0/self.ema_rendertime

    def update(self):
        tx, ty, tz =  self.rr.mouse_in_world
        material, tilename = self.rr.gameobject.gettile((tx,ty,tz))
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
            'mat': material,
            'tile': tilename,
            'color': color,
            'vp': self.rr.viewpos,
            'pszx': self.rr.Pszx,
            'pszy': self.rr.Pszy,
            'origin': self.rr.render_origin,
            'fbosz': self.rr.fbo.size,
            'fbovsz': self.rr.fbo.viewsize,
            'fbovp': self.rr.fbo.viewpos,
            'win': self.rr.surface.get_size(),
            
        }

        self.hudsurf.fill(pygame.Color(0x00000060))
        i = 0
        ystep = self.font.get_linesize()
        for s in self.strs:
            try:
                surf = self.font.render(s.format(**data), True, pygame.Color(0xf0f0f0f0))
            except ValueError, e:
                print e
                print s, repr(data)
            self.hudsurf.blit(surf, (self.padding, self.padding + i * ystep) )
            i += 1
            
        #pygame.image.save(self.hudsurf, "kaka.png")

        glBindTexture(GL_TEXTURE_2D,  self.txid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.hud_w, self.hud_h, 
            0, GL_RGBA, GL_UNSIGNED_BYTE, pygame.image.tostring(self.hudsurf, "RGBA"))          
              
        self.res_w, self.res_h = self.rr.surface.get_size()
        right, top = self.res_w - self.margin, self.res_h - self.margin 
        left = right - self.hud_w
        bottom = top - self.hud_h
        
        quad = np.array( ( (left, top), (right, top), (right, bottom), (left, bottom) ), dtype=np.int32 )
        self.quad_vbo.set_array(quad)
        glBindTexture(GL_TEXTURE_2D, 0)
        
    def draw(self):
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
    def __init__(self, vs, fs, go, loud=[], anicutoff=128):
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
        self._fc_key = None

        self.render_origin = [ self.gameobject.xdim/2, 
                               self.gameobject.ydim/2,
                               self.gameobject.zdim - 23 ]
        if self.render_origin[2] < 0:
            self.render_origin[2] = 0

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
        if self._fc_key != fc_key:
            self._fc_key = fc_key
            self.screen  = self.gameobject.getmap(self.render_origin, (self.grid_w, self.grid_h))
            self.screen_vbo.set_array(self.screen)
            
        
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
            delta_w = winsize[0] - oldsize[0]
            delta_h = winsize[1] - oldsize[1]
            self.set_mode(winsize)
            
        window = self.surface.get_size()
        
        self.Pszx = int(self.Psz * self.Parx)
        self.Pszy = int(self.Psz * self.Pary)
        
        newgrid = ( window[0] / self.Pszx + 4, window[1] / self.Pszy + 4)
        if self.grid_w is not None:
            delta_gw = newgrid[0] - self.grid_w
            delta_gh = newgrid[1] - self.grid_h
        else:
            delta_gw = delta_gh = 9
        
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


    def zoom(self, zcmd):
        if zcmd == 'zoom_in' and self.Psz > 1:
            self.Psz -= 1
        elif zcmd == 'zoom_out' and self.Psz < self.maxPsz:
            self.Psz += 1
        elif zcmd == 'zoom_reset':
            self.Psz = max(self.txsz[2], self.txsz[3])
        self.reshape() 

    def update_mouse(self):
        mx, my = pygame.mouse.get_pos()
        self.mouseco = (mx, my)
        fbx, fby = mx + self.viewpos[0], my + self.viewpos[1]
        mtx, mty = fbx/self.Pszx, fby/self.Pszy
        self.mouse_in_world = ( mtx + self.render_origin[0], 
                                mty + self.render_origin[1], 
                                self.render_origin[2] )
        
    def getpixel(self, posn):
        return  int(glReadPixels(posn[0], posn[1], 1, 1, GL_RGBA, 
                    GL_UNSIGNED_INT_8_8_8_8)[0][0])
        
    def render(self, frame_no):
        bgc = ( 0.5, 0.1, 0.1, 1 )
        t = pygame.time.get_ticks()
        self.frame_no = frame_no
        glClearColor(*bgc)
        glClear(GL_COLOR_BUFFER_BIT)
        
        if True and not False:  # 'if' here only to provide an indent
            # draw the map.
            self.fbo.update(self.viewpos)
            self.fbo.bind()
            
            glClearColor(*bgc)
            glClear(GL_COLOR_BUFFER_BIT)
            
            self.update_mapdata()
            self.mapshader.update_state()

            glDrawArrays(GL_POINTS, 0, self.grid_tile_count)
            
            self.mapshader.cleanup()
            
            self.fbo.compose() # blits drawn map into the default FBO.
        
        if True and not False:  # 'if' here only to provide an indent
            # draw the hud on top of the default FBO
            self.hud.update()
            self.hudshader.update_state()
            self.hud.draw()
            self.hudshader.cleanup()
        pygame.display.flip()
        return  pygame.time.get_ticks() - t
        
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
                        if ev.key == pygame.K_SPACE:
                            paused = not paused
                        elif ev.key == pygame.K_ESCAPE:
                            finished = True 
                        elif ev.key == pygame.K_PERIOD and ev.mod & 3:
                            if self.render_origin[2] > 0:
                                self.render_origin[2] -= 1
                        elif ev.key == pygame.K_COMMA  and ev.mod & 3:
                            if self.render_origin[2] <  self.gameobject.zdim - 1:
                                self.render_origin[2] += 1
                        elif ev.key in scrolldict:
                            if ev.mod & 3:
                                boost = 10
                            else:
                                boost = 1
                            x += scrolldict[ev.key][0] * boost
                            y += scrolldict[ev.key][1] * boost
                            self.render_origin[:2] = x, y
                        elif ev.key == pygame.K_BACKSPACE:
                            x = y = 0
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
                        if ev.button == 4: # wheel forward
                            self.zoom("zoom_out")
                        elif ev.button == 5: # wheel back
                            self.zoom("zoom_in")
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
keypad +/- : adjust FPS

""")

    
    ap.add_argument('-afps', metavar='afps', type=float, default=12, help="animation fps")
    ap.add_argument('-choke', metavar='fps', type=float, default=60, help="renderer fps cap")
    ap.add_argument('-vs', metavar='vertex shader', default='three.vs')
    ap.add_argument('-fs',  metavar='fragment shader', default='three.fs')
    ap.add_argument('dfprefix', metavar="../df_linux", help="df directory to get base tileset from")
    ap.add_argument('dumpfx', metavar="dump-prefix", help="dump name prefix (foobar in foobar.mats/foobar.tiles)")
    ap.add_argument('rawsdir', metavar="raws/dir", nargs='*', help="raws dirs to parse")
    ap.add_argument('--loud', action='store_true', help="spit lots of useless info")
    ap.add_argument('--cutoff-frame', metavar="frameno", type=int, default=96, help="frame number to cut animation at")        
    pa = ap.parse_args()

    pageman, matiles, maxframe = raw.work(pa.dfprefix)
    if pa.cutoff_frame > maxframe:
        cutoff = maxframe
    else:
        cutoff = pa.cutoff_frame
    
    mo = mapobject( font = pageman.get_album(),
                    matiles = matiles,
                    matsfile = pa.dumpfx + '.mats', 
                    tilesfile = pa.dumpfx + '.tiles', cutoff = cutoff)
    loud = ()
    if pa.loud:
        loud = ("gl", "reshape", "shaders")
    
    re = Rednerer(vs=pa.vs, fs=pa.fs, go=mo, loud = loud, anicutoff = cutoff)
    re.loop(pa.afps, pa.choke)
    re.fini()
    

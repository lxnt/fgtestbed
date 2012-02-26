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

class mapobject:
    def __init__(self, fgrawdir, matsfile, tilesfile, pngdir='png', apidir=''):
        self.gr = raw.graphraws(fgrawdir)
        unused, self.tile_names = raw.enumaps(apidir)
        self.parse_matsfile(matsfile)
        self.assemble_blitcode()
        
        self.tp = self.gr.pages[self.gr.pages.keys()[0]]
        self.txco = self.tp.pdim + self.tp.tdim

        if os.name == 'nt':
            self._map_fd = os.open(tilesfile, os.O_RDONLY|os.O_BINARY)
        else:
            self._map_fd = os.open(tilesfile, os.O_RDONLY)

        self._map_mmap = mmap.mmap(self._map_fd, 0, access = mmap.ACCESS_READ)


    def eatpage(self, page):
        pass
    
    def maptile(self, blit):
        return 1, blit[1], blit[2], 0

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

    def assemble_blitcode(self):
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
            
        self.blitcode_dt = np.dtype({  # GL_RGBA16UI - 64 bits. 8 bytes
            'names': 's t r g b a'.split(),
            'formats': ['u2', 'u2', 'u1', 'u1', 'u1', 'u1' ],
            'offsets': [ 0, 2, 4, 5, 6, 7 ],
            'titles': ['s-coord in tiles', 't-coord in tiles',
                       'blend-red', 'blend-blue', 'blend-green', 'blend-alpha'] })

        pages, mats = self.gr.get()
        
        for page in pages:
            self.eatpage(page)
        
        tcount = 0
        for mat in mats:
            tcount += len(mats[mat].tiles.keys())
        print "{1} mats  {0} defined tiles".format(tcount, len(mats.keys()))
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
        
        tc = 1 # 0 === undefined.
        #fd = file("dispatch.text","w")
        #fb = file("blitcode.text","w")
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
                
                tile_id = self.tile_names[tname]
                hashed  = hashit(tile_id, mat_id)
                hx = hashed % self.hashw 
                hy = hashed / self.hashw 
                blithash[hy, hx]['s'] = x
                blithash[hy, hx]['t'] = y
                #fd.write("{:03x} {:03x} {:06x} : {:02x} {:02x} {}\n".format(hx,hy,hashed, x, y, name))
                
                frame_no = 0
                for insn in frameseq:
                    blit, blend = insn
                    un, s, t, un = self.maptile(blit)
                    r,g,b,a = blend
                    blitcode[frame_no, y, x]['s'] = s # fortran, motherfucker. do you speak it?
                    blitcode[frame_no, y, x]['t'] = t
                    blitcode[frame_no, y, x]['r'] = r
                    blitcode[frame_no, y, x]['g'] = g
                    blitcode[frame_no, y, x]['b'] = b
                    blitcode[frame_no, y, x]['a'] = a
                    #fb.write("{},{}: {} {} '{}' {} {} {} {} {}\n".format( x, y, s, t, chr(s+t*16), r, g, b, a, name))
                    #break
                    #if frame_no != -1:
                    #    fb.write("{},{}: {} {} '{}' {} {} {} {}\n".format( x, y, s, t, chr(s+t*16), r, g, b, a))
                    frame_no += 1
                tc += 1

        self.blithash, self.blitcode = blithash, blitcode

    def upload_font(self, txid_font, txid_txco):
        surf = pygame.image.load(self.tp.file)
        stuff = pygame.image.tostring(surf, "RGBA")
        
        glBindTexture(GL_TEXTURE_2D,  txid_font)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, surf.get_width(), surf.get_height(), 
            0, GL_RGBA, GL_UNSIGNED_BYTE, stuff)        
            
        if False:
            txcos = "\x10\x10\x10\x10" * self.tp.pdim[0] * self.tp.pdim[1]
            glBindTexture(GL_TEXTURE_2D,  txid_txco)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.tp.pdim[0], self.tp.pdim[1],
                0, GL_RGBA, GL_UNSIGNED_BYTE, txcos)
        
        return self.tp.pdim + self.tp.tdim

    def upload_code(self, txid_hash, txid_blit):
        if False:
            for i in (GL_UNPACK_SWAP_BYTES, GL_UNPACK_LSB_FIRST, GL_UNPACK_ROW_LENGTH,
                GL_UNPACK_IMAGE_HEIGHT, GL_UNPACK_SKIP_ROWS, GL_UNPACK_SKIP_PIXELS,
                GL_UNPACK_SKIP_IMAGES, GL_UNPACK_ALIGNMENT ):
                print i, glGetInteger(i)
        
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
        
        print "dispatch: {0}x{1} blitcode: {2}x{3}x{4}".format(self.hashw, self.hashw, self.codew, self.codew, 128)
        if False:
            file("dispatch","w").write(self.blithash.tostring())
            file("blitcode","w").write(self.blitcode.tostring())
        
    def frame(self, x,y,z,w,h ):
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
        
        file('frame', 'w').write(rv.tostring())

        return rv

class shader:
    def __init__(self, renderer, loud=False):
        self.rr = renderer
        self.loud = loud
        self.aloc = {
            'position': 0, 
            'screen': 1
        }
        self.program = None
        self.u_vbos = False
        self.u_shape = False
        self.u_textures = False
        
    def reload(self, vs, fs):
        if self.program:
            self.fini()
        self.init(self, vs, fs)
        
    def init(self, vs, fs):
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
        
    def update_state(self, shape = False, textures = False, vbos = False):
        glUseProgram(self.program)
        
        for loc in self.aloc.values():
            glEnableVertexAttribArray(loc) # is it the right place for this?
        
        glUniform1i(self.uloc['frame_no'], self.rr.frame_no)
        glUniform1f(self.uloc["final_alpha"], 1.0)

        if shape or self.u_shape:
            glUniform2i(self.uloc['grid'], self.rr.grid_w + 2, self.rr.grid_h + 2)
            glUniform3f(self.uloc['pszar'], self.rr.Parx, self.rr.Pary, self.rr.Pszx)
            self.u_shape = False
        
        if textures or self.u_textures:
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
            
            self.u_textures = False
            
        if vbos or self.u_vbos:
            self.rr.screen_vbo.bind()
            glVertexAttribIPointer(self.aloc["screen"], 1, GL_INT, 0, self.rr.screen_vbo )
            self.rr.screen_vbo.unbind()
            
            self.rr.grid_vbo.bind()
            glVertexAttribPointer(self.aloc["position"], 2, GL_FLOAT, GL_FALSE, 0, self.rr.grid_vbo )
            self.rr.grid_vbo.unbind()

            self.u_vbos = False

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
        
        
class fbo:
    def __init__(self, renderer):
        self.rr = renderer
        self.u_reshape = False
        
    def check(self, tgt = GL_FRAMEBUFFER):
        x = glCheckFramebufferStatus(tgt)
        if x != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("framebuffer incomplete: {}".format(glname.get(x,x))
        
    def init(self):
        self.map, self.hud = glGenFramebuffers(2)
        self.mapr = glGenRenderbuffers(1)

    def fini(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDeleteRenderbuffers(1, [self.mapr])
        glDeleteFramebuffers(2, [self.map, self.hud])

    def reshape(self):
        mapr_w = (self.rr.grid_w + 2) * self.rr.Pszx
        mapr_h = (self.rr.grid_h + 2) * self.rr.Pszy
        
        glBindFramebuffer(GL_FRAMEBUFFER, self.map)
        glBindRenderbuffer(GL_RENDERBUFFER, self.mapr)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, mapr_w, mapr_h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, self.mapr)
        
        self.check()
        self.mapr_w, self.mapr_h = mapr_w, mapr_h
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    
    def bind_map(self):
        if self.u_reshape:
            self.reshape()
            self.u_reshape = False
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.map)
        glViewport( 0, 0, self.mapr_w, self.mapr_h)
        return True
        
    def bind_hud(self):
        #glBindFramebuffer(GL_FRAMEBUFFER_DRAW, self.hud)
        return True
    
    def compose(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.map)
        
        x0 = self.rr.shift[0] + self.rr.Pszx
        y0 = self.rr.shift[1] + self.rr.Pszy
        x1 = self.rr.surface.get_width() + x0
        y1 = self.rr.surface.get_height() + y0

        glBlitFramebuffer( 
            x0, y0, x1, y1,
            0, 0, self.rr.surface.get_width(), self.rr.surface.get_height(),
            GL_COLOR_BUFFER_BIT, GL_NEAREST)
        

        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)

class rednerer:
    def __init__(self, vs, fs, go, glinfo=False, anicutoff=128):
        self.vs, self.fs = vs, fs
        self.shader = shader(self, loud=True)
        self.fbo = fbo(self)
        self.gameobject = go
        
        self.do_update_attrs = True
        self.opengl_initialized = False
        
        self.snap_to_grid = False
        self.do_reset_glcontext = True
        self.conf_stretch_tiles = False
        self.conf_snap_window = False
        self.cutoff_frame = anicutoff      
        self.skip_glinfo = not glinfo
        self.loud_reshape = True

        self.tilesizes = None # txco texture
        self.grid = None # grid vaa/vbo
        self.screen = None # frame data
        self.surface = None
        
        self.viewport_w = 0
        self.viewport_h = 0
        self.viewport_offset_x = 0
        self.viewport_offset_y = 0
        self.shift = [0, 0] # smooth-panning shift
        self.txsz_w = self.cell_w = self.txsz_h = self.cell_h = 0
        self.tile_w = self.tile_h = None
        self.grid_w = self.grid_h = 0
        self.Pszx = self.Pszy = 0
        self.Psz = -8
        
        self._fc_key = None

        self.MIN_GRID_X = 20
        self.MIN_GRID_Y = 20
        self.MAX_GRID_X = go.xdim
        self.MAX_GRID_Y = go.ydim

        pygame.display.init()
        pygame.display.set_caption("full-graphics testbed", "fgtestbed")
        
        default_res = ( 1280, 800 )
        self.set_mode(*default_res)
        self.gps_allocate(self.MIN_GRID_X, self.MIN_GRID_Y)
        self.Pszx = self.surface.get_width()/self.MIN_GRID_X
        self.Pszy = self.surface.get_height()/self.MIN_GRID_Y
        

    def gps_allocate(self, w, h):
        self.grid_allocate(w, h)
        self.do_update_attrs = True
        
    def set_mode(self, w, h, fullscreen=False):
        if self.surface is None:
            fs_state = False
            res_change = True
        else:
            fs_state = self.surface.get_flags() & pygame.FULLSCREEN
            res_change = ( self.surface.get_width() != w ) or (self.surface.get_height() != h)
            
        if self.opengl_initialized and ( (fs_state and fullscreen) or (not (fs_state or fullscreen))) and not res_change:
            return True # nothing to do
        
        if self.opengl_initialized and self.do_reset_glcontext:
            self.opengl_fini()
        
        flags = pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE
        if fullscreen:
            flags |= pygame.SDL_FULLSCREEN
        
        pygame.display.set_mode((w,h), pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE)
        self.surface = pygame.display.get_surface()
        
        if not self.opengl_initialized:
            self.opengl_init()

        return True
    
    def grid_allocate(self, w, h):
        self.grid_w, self.grid_h = w, h # those are 'guaranteed to be visible' tiles,
                                        # off which reshape calculations are based. 
                                        # rest is using +2 to make panning real smooth
        w += 2
        h += 2
        rv = np.zeros((2*w*h,) , 'f')
        i = 0
        for xt in xrange(0, w):
            for yt in xrange(0, h):
                rv[2 * i + 0] = xt
                rv[2 * i + 1] = yt
                i += 1

        self.grid_tile_count = w*h
        self.grid = rv
    
    def opengl_init(self):
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

        self.fbo.init()
        self.dispatch_txid, self.blitcode_txid, self.font_txid, self.txco_txid = glGenTextures(4)
        self.shader.init(self.vs, self.fs)
        
        self.opengl_initialized = True


    def opengl_fini(self):
        self.shader.fini()
        #glDeleteTextures()
        #glDeleteBuffers()
        self.opengl_initialized = False
        self.do_update_attrs = True

    def update_vbos(self, mapwindow):
        if mapwindow != self._fc_key:
            self._fc_key = mapwindow
            self.screen  = self.gameobject.frame(*mapwindow)
            
        if self.do_update_attrs or not self.screen_vbo:
            self.screen_vbo = vbo.VBO(self.screen, usage=GL_STREAM_DRAW)
            self.grid_vbo = vbo.VBO(self.grid, usage=GL_STATIC_DRAW)
            self.do_update_attrs = False
            self.shader.u_vbos = True # request vaap reset
        else:
            self.screen_vbo.set_array(self.screen)
            self.screen_vbo.bind() # force copyout

    def reshape(self, new_grid_w = 0, new_grid_h = 0, new_window_w = -1, new_window_h = -1, 
                toggle_fullscreen = False, override_snap = False):

        if self.loud_reshape:
            print "reshape(): got grid {}x{} window {}x{} tile {}x{} stretch={} snap={} Psz={}".format(
                new_grid_w, new_grid_h, new_window_w, new_window_h, self.tile_w, self.tile_h,
                self.conf_stretch_tiles, self.conf_snap_window, self.Psz)

        if not self.tile_w:
            return
        
        if (new_window_w < 0):
            new_window_w = self.surface.get_width()
        if (new_window_h < 0):
            new_window_h = self.surface.get_height()
    
        if new_grid_w + new_grid_h == 0:
            new_grid_w = new_window_w/self.tile_w
            new_grid_h = new_window_h/self.tile_h
        
        new_grid_w = min(max(new_grid_w, self.MIN_GRID_X), self.MAX_GRID_X)
        new_grid_h = min(max(new_grid_h, self.MIN_GRID_Y), self.MAX_GRID_Y)
        
        fx = new_window_w / ( float(new_grid_w) * self.tile_w )
        fy = new_window_h / ( float(new_grid_h) * self.tile_h )
        ff = min(fx, fy)
        
        new_psz_x = int(ff * self.tile_w)
        new_psz_y = int(ff * self.tile_h)
            
        new_psz = max(new_psz_x, new_psz_y)
        self.Psz = new_psz
        
        if self.conf_stretch_tiles:
            new_psz_x = new_window_w/new_grid_w
            new_psz_y = new_window_h/new_grid_h    
        
        if (new_grid_w > self.grid_w) or (new_grid_h > self.grid_h):
            new_grid_w = new_window_w / new_psz_x
            new_grid_h = new_window_h / new_psz_y
            new_grid_w = min(max(new_grid_w, self.MIN_GRID_X), self.MAX_GRID_X)
            new_grid_h = min(max(new_grid_h, self.MIN_GRID_Y), self.MAX_GRID_Y)
                    
        self.Pszx = new_psz_x
        self.Pszy = new_psz_y
        
        self.Parx = self.Pary = 1.0
        if self.Pszx > self.Pszy:
            self.Pary = float(new_psz_y)/new_psz_x
        else:
            self.Parx = float(new_psz_x)/new_psz_y
            
        self.viewport_w = new_psz_x * new_grid_w
        self.viewport_h = new_psz_y * new_grid_h
        
        if self.loud_reshape:        
            print "reshape(): final grid {}x{} window {}x{} viewport {}x{} Psz {}x{}".format(
                new_grid_w, new_grid_h, new_window_w, new_window_h,
                self.viewport_w, self.viewport_h, self.Pszx, self.Pszy)
        
        if new_grid_w != self.grid_w or new_grid_h != self.grid_h:
            self.gps_allocate(new_grid_w, new_grid_h)
            
        fullscreen = self.surface.get_flags() & pygame.FULLSCREEN
        if toggle_fullscreen:
            if fullscreen:
                self.set_mode(new_window_w, new_window_h, False)
            else:
                self.set_mode(new_window_w, new_window_h, True)
        else:
            if not fullscreen:
                if self.conf_snap_window and not override_snap:
                    self.set_mode(self.viewport_w, self.viewport_h, False)
                else:
                    self.set_mode(new_window_w, new_window_h, False)
        self.set_viewport()

    def glinfo(self):
        if self.skip_glinfo:
            return
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
        
    def set_viewport(self):
        """ this kills artifacts caused by window being a few pixels
            larger than the tiles occupy. """
        sw, sh =  self.surface.get_width(), self.surface.get_height()
        self.viewport_x = (sw - self.viewport_w)/2;
        self.viewport_y = (sh - self.viewport_h)/2;
        
        if self.loud_reshape:
            print "set_viewport(): got {}x{} out of {}x{} offs {}x{}\n".format(
                self.viewport_w, self.viewport_h, sw, sh, self.viewport_offset_x, 
                self.viewport_offset_y)
        
        self.fbo.u_reshape = True
        self.shader.u_shape = True # request shape uniforms reset

    def texture_reset(self):
        self.gameobject.upload_code(self.dispatch_txid, self.blitcode_txid)
        self.txsz = self.gameobject.upload_font(self.font_txid, self.txco_txid)
        self.tile_w = self.txsz[2]
        self.tile_h = self.txsz[3]

        self.reshape()
        self.shader.u_textures = True # request TIU rebind

    def _zoom(self, zoom, force = 0):
        new_psz  = self.Psz + zoom
        
        if new_psz < 2:
            return
        
        t_ar = float(self.tile_w)/self.tile_h
        
        if self.tile_w > self.tile_h:
            new_psz_x = new_psz
            new_psz_y = int(new_psz / t_ar)
        else:
            new_psz_x =  int( new_psz * t_ar)
            new_psz_y = new_psz

        new_grid_w = self.surface.get_width() / new_psz_x
        new_grid_h = self.surface.get_height() / new_psz_y

        print "_zoom({}): psz {} -> {} pszxy {}x{} -> {}x{} grid {}x{} -> {}x{}".format(
            zoom, self.Psz, new_psz, 
            self.Pszx, self.Pszy, new_psz_x, new_psz_y,
            self.grid_w, self.grid_h, new_grid_w, new_grid_h)
            
        og = (self.grid_w, self.grid_h)
        self.reshape(new_grid_w, new_grid_h, -1, -1, False, True)
        if og == (self.grid_w, self.grid_h): # if we got stuck,
            force += 1
            self._zoom(zoom*force, force) # apply boot to ass
    
    def resize(self, new_window_w, new_window_h, toggle_fullscreen = False):
        if  (     (new_window_w == self.surface.get_width())
              and (new_window_h == self.surface.get_height())
              and (not toggle_fullscreen)):
                print "resize: no resize."
                return
        print "resize: psz is {0}".format(self.Psz)
        if self.Psz < max(self.tile_w, self.tile_h):
            Psz = max(self.tile_w, self.tile_h)
            new_grid_w = new_window_w / self.tile_w
            new_grid_h = new_window_h / self.tile_h
        else:
            new_grid_w = new_window_w / ( self.surface.get_width() / self.grid_w) 
            new_grid_h = new_window_h / ( self.surface.get_height() / self.grid_h)
        print "resize to {0}x{1} reshape to grid {2}x{3}".format(new_window_w, new_window_h, new_grid_w, new_grid_h)
        self.reshape(new_grid_w, new_grid_h, new_window_w, new_window_h, toggle_fullscreen)

    def zoom(self, zcmd):
        if zcmd == 'zoom_in':
            self._zoom(-1)
        elif zcmd == 'zoom_out':
            self._zoom(1)
        elif zcmd == 'zoom_reset':
            self.reshape(self.surface.get_width() / self.tile_w, self.surface.get_height() / self.tile_h) 
        elif zcmd == 'zoom_resetgrid':
            self.reshape(self.surface.get_width() / self.tile_w, self.surface.get_height() / self.tile_h) 
        elif zcmd == 'zoom_fullscreen':
            if self.surface.get_flags() & pygame.SDL_FULLSCREEN:
                pass
            else:
                pass
            # no idea whatta do here
        

    def get_mouse_coords(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        x = (mouse_x - self.viewport_offset_x) / self.Pszx
        y = (mouse_y - self.viewport_offset_y) / self.Pszy
        return x,y

    def render(self, mapwindow, frame_no):
        bgc = ( 0.1, 0.1, 0.1, 1 )
        t = pygame.time.get_ticks()
        self.frame_no = frame_no
        glClearColor(*bgc)
        glClear(GL_COLOR_BUFFER_BIT)    
        if self.fbo.bind_map(): # 'if' here only to provide an indent
            glClearColor(*bgc)
            glClear(GL_COLOR_BUFFER_BIT)
            
            self.update_vbos(mapwindow)
            self.shader.update_state()

            glDrawArrays(GL_POINTS, 0, self.grid_tile_count)
            
        if self.fbo.bind_hud(): # same as above
            pass
            
        self.fbo.compose()
        pygame.display.flip()
        return  pygame.time.get_ticks() - t
        
    def loop(self, GFPS = 12):
        frame_no = 0
        vpx = vpy = 0
        
        x = (self.gameobject.xdim - self.grid_w)/2
        y = (self.gameobject.ydim - self.grid_h)/2
        z = self.gameobject.zdim - 10
        if z < 0:
            z = 0
        z = 162
        slt = 1000.0/GFPS # milliseconds
        last_frame_ts = 0
        paused = False
        finished = False
        panning = False
        self.reset_vbo = True
        last_frame_ts = -1e23
        scrolldict = {
                        pygame.K_LEFT: ( -1, 0),
                        pygame.K_RIGHT: ( 1, 0),
                        pygame.K_UP: ( 0, -1),
                        pygame.K_DOWN: ( 0, 1),
                        pygame.K_HOME: ( -1, -1),
                        pygame.K_PAGEUP: ( 1, -1),
                        pygame.K_END: ( -1, 1),
                        pygame.K_PAGEDOWN: ( 1, 1),
        }
        
        while not finished:
            last_render_ts = pygame.time.get_ticks()
            if not paused:
                frame_no += 1
                if frame_no > self.cutoff_frame:
                    frame_no = 0
            render_time = self.render((x-1, y-1, z, self.grid_w+2, self.grid_h+2), frame_no)
            
            #print "frame rendered in {0} msec".format(render_time)
            render_time += 1
            next_render_time = pygame.time.get_ticks() + slt - render_time
            while  True:
                for ev in pygame.event.get():
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_SPACE:
                            paused = not paused
                        elif ev.key == pygame.K_ESCAPE:
                            finished = True 
                        elif ev.key == pygame.K_PERIOD and ev.mod & 3:
                            if z > 0:
                                z -= 1
                            print "Z={}".format(z)
                        elif ev.key == pygame.K_COMMA  and ev.mod & 3:
                            if z < self.gameobject.zdim - 1:
                                z += 1
                            print "Z={}".format(z)
                        elif ev.key in scrolldict:
                            if ev.mod & 3:
                                boost = 10
                            else:
                                boost = 1
                            x += scrolldict[ev.key][0] * boost
                            y += scrolldict[ev.key][1] * boost
                        elif ev.key == pygame.K_BACKSPACE:
                            x = y = 0
                        elif ev.key == pygame.K_KP_PLUS:
                            GFPS += 1
                        elif ev.key == pygame.K_KP_MINUS:
                            GFPS -= 1
                        else:
                            print repr(ev.key), repr(ev)

                    elif ev.type == pygame.QUIT:
                        finished = True
                    elif ev.type ==  pygame.VIDEORESIZE:
                        self.resize(ev.w, ev.h)
                    elif ev.type == pygame.MOUSEBUTTONDOWN:
                        if ev.button == 4: # wheel forward
                            self.zoom("zoom_out")
                        elif ev.button == 5: # wheel back
                            self.zoom("zoom_in")
                        elif ev.button == 3: # RMB
                            panning = True
                        elif ev.button == 1:
                            pv = glReadPixels(ev.pos[0], self.surface.get_height() - ev.pos[1], 1, 1, GL_RGBA , GL_UNSIGNED_INT_8_8_8_8)[0][0]
                            cx, cy = ev.pos[0]/self.Pszx, ev.pos[1]/self.Pszy
                            try:
                                thash = self.screen[cx,cy]
                            except IndexError:
                                thash = -1
                            
                            r, g, b, a = pv >> 24, (pv >>16 ) & 0xff, (pv>>8) &0xff, pv&0xff
                            print "{:02x} {:02x} {:02x} {:02x} at {}px thash={:03x} {:03x}".format(r,g,b,a, ev.pos, thash%1024, thash/1024)
                            #print "{:.3f} {:.3f} {:.3f} {:03x} {:03x}".format(r/16.0, g/16.0, b/2, thash%1024, thash/1024)
                            #print "{:.3f} {:.3f} {:.3f} {:.3f}".format(6*r/256.0,6*g/256.0,128*b/256.0,a/256.0)
                            #print "{:03x} {:03x}".format( (r<<8 ) | b,(g<<8 ) | a)
                            
                        else:
                            paused = not paused
                    elif ev.type == pygame.MOUSEBUTTONUP:
                        if ev.button == 3:
                            panning = False
             
                    elif ev.type == pygame.MOUSEMOTION:
                        if panning:
                            vpx -= ev.rel[0]
                            vpy += ev.rel[1]
                            if (vpx > self.Pszx): 
                                vpx = self.Pszx - vpx
                                x += 1
                            elif vpx < -self.Pszx:
                                x -= 1
                                vpx = self.Pszx + vpx
                            if (vpy > self.Pszy): 
                                vpy = self.Pszy - vpy
                                y -= 1
                            elif vpy < -self.Pszy:
                                y += 1
                                vpy = self.Pszy + vpy
                            self.shift = [ vpx, vpy ]

                if next_render_time - pygame.time.get_ticks() < -50:
                    #print "drawing's too slow, {0:.2f} FPS vs {1:.2f} reqd".format(1000.0/render_time, GFPS)
                    break
                elif next_render_time - pygame.time.get_ticks() < 0:
                    break
                elif next_render_time - pygame.time.get_ticks() < 50:
                    pygame.time.wait(int(next_render_time - pygame.time.get_ticks()))
                    break
                else:
                    pygame.time.wait(50)

    def fini(self):
        self.grid_vbo = None
        self.screen_vbo = None
        self.shader.fini()
        self.fbo.fini()
        glDeleteTextures((self.dispatch_txid, self.font_txid, self.blitcode_txid))
        pygame.quit()


"""
    debug_get_flags_option: help for ST_DEBUG:
    |      mesa [0x0000000000000001]
    |      tgsi [0x0000000000000002]
    | constants [0x0000000000000004]
    |      pipe [0x0000000000000008]
    |       tex [0x0000000000000010]
    |  fallback [0x0000000000000020]
    |    screen [0x0000000000000080]
    |     query [0x0000000000000040]

    debug_get_flags_option: help for LP_DEBUG: -- softpipe only
    |          pipe [0x0000000000000001]
    |          tgsi [0x0000000000000002]
    |           tex [0x0000000000000004]
    |         setup [0x0000000000000010]
    |          rast [0x0000000000000020]
    |         query [0x0000000000000040]
    |        screen [0x0000000000000080]
    |    show_tiles [0x0000000000000200]
    | show_subtiles [0x0000000000000400]
    |      counters [0x0000000000000800]
    |         scene [0x0000000000001000]
    |         fence [0x0000000000002000]
    |           mem [0x0000000000004000]
    |            fs [0x0000000000008000]

    debug_get_flags_option: help for GALLIVM_DEBUG:
    |         tgsi [0x0000000000000001]
    |           ir [0x0000000000000002]
    |          asm [0x0000000000000004]
    |         nopt [0x0000000000000008]
    |         perf [0x0000000000000010]
    | no_brilinear [0x0000000000000020]
    |           gc [0x0000000000000040]


    #~ #export LP_DEBUG=tgsi
    #~ #export ST_DEBUG=tgsi,mesa
    #~ #export GALLIVM_DEBUG=tgsi
    #~ #export MESA_DEBUG=y
    #~ #export LIBGL_DEBUG=verbose
    #~ #export GALLIUM_PRINT_OPTIONS=help
    #~ #export TGSI_PRINT_SANITY=y """

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

    
    ap.add_argument('-fps', metavar='fps', type=float, default=12)
    ap.add_argument('-vs', metavar='vertex shader', default='three.vs')
    ap.add_argument('-fs',  metavar='fragment shader', default='three.fs')
    ap.add_argument('dumpfx', metavar="dumpfx", nargs='?', help="dump name prefix (foobar in foobar.mats/foobar.tiles)", default='fugrdump')
    ap.add_argument('-raws', metavar="fgraws", default="fgraws", help="fg raws directory")
    ap.add_argument('--glinfo', action='store_true', help="spit info about GL driver capabilities")
    ap.add_argument('--cutoff-frame', metavar="frameno", type=int, default=96, help="frame number to cut animation at")
        
    pa = ap.parse_args()
    
    mo = mapobject(matsfile=pa.dumpfx+'.mats', tilesfile = pa.dumpfx + '.tiles', fgrawdir=pa.raws)
        
    re = rednerer(vs=pa.vs, fs=pa.fs, go=mo, glinfo=pa.glinfo, anicutoff = pa.cutoff_frame)
    re.texture_reset()
    re.loop(pa.fps)

    re.fini()

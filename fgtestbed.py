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

import sys, time, math, struct, io, ctypes, zlib, collections, argparse, traceback, os, types
from random import random as rnd
import pygame
import raw

from OpenGL.GL import *
from OpenGL.arrays import vbo
from OpenGL.GL.shaders import *
import OpenGL.GL.shaders
from OpenGL.GLU import *
from OpenGL.GL.ARB import shader_objects

import numpy as np
import raw

def compileProgramTheRightWay(*shaders):
    
    program = glCreateProgram()
    for shader in shaders:
        glAttachShader(program, shader)
    glLinkProgram(program)
    
    link_status = glGetProgramiv( program, GL_LINK_STATUS )
    if link_status == GL_FALSE:
        raise RuntimeError(
            """Link failure (%s): %s"""%(
            link_status,
            glGetProgramInfoLog( program ),
        ))
    glUseProgram(program)
    au = glGetProgramiv(program, GL_ACTIVE_UNIFORMS)
    rv = {}
    for i in xrange(au):
        name, wtf, typ = shader_objects.glGetActiveUniformARB(program, i)
        loc = glGetUniformLocation(program, name)
        val = None
        #xval = glGetUniformiv(program, loc, 32)
        print "{0}: name={1} type={2} loc={3} val={4}".format(i, name, typ, loc, val)
        if typ == GL_SAMPLER_2D:
            glUniform1i(loc, 0)
        elif typ == GL_SAMPLER_3D:
            glUniform1i(loc, 1)
    if False:
        for uname, uval in unifomap.items():
            uloc = glGetUniformLocation(program, uname)
            print "{0}: {1}".format(uname, uloc)
            try:
                glUniform1i(uloc, uval)
            except GLError:
                print 'failed'
    
    glValidateProgram(program)
    validation = glGetProgramiv( program, GL_VALIDATE_STATUS )
    if validation == GL_FALSE:
        raise RuntimeError(
            """Validation failure (%s): %s"""%(
            validation,
            glGetProgramInfoLog( program ),
        ))
    for shader in shaders:
        glDeleteShader(shader)
    return OpenGL.GL.shaders.ShaderProgram( program ) # context mgr        

class mapobject:
    def __init__(self):
        t = time.time()
        self.p = raw.preparer()
        self.p.first_stage()
        print "first_stage: {0:.4f} sec.".format(time.time()-t)
        self.tp = self.p.gr.pages[self.p.gr.pages.keys()[0]]
        self.txco = self.tp.pdim + self.tp.tdim
        self.maxz = self.p.madpump._zdim - 1

    def upload_font(self, txid_font):
        
        surf = pygame.image.load(self.tp.file)
        stuff = textureData = pygame.image.tostring(textureSurface, "RGBA", 1)
        
        glMatrixMode(GL_TEXTURE)
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glBindTexture(GL_TEXTURE_2D,  txid_font)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, surf.get_width(), surf.get_height(), 
            0, GL_RGBA, GL_UNSIGNED_BYTE, stuff)
        
        return self.tp.tdim + self.tpm.pdim

    def upload_textures(self, txid_hash, txid_blit, txid_blend):
        glMatrixMode(GL_TEXTURE)
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glBindTexture(GL_TEXTURE_2D,  txid_hash)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED32UI, 1024, 1024, 0, GL_RGBA, GL_UNSIGNED_INT, self.p.blithash )
        glBindTexture(GL_TEXTURE_3D,  txid_blit)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage3D(GL_TEXTURE_3D, 0, GL_RED32UI, self.p.tx, self.p.ty, self.p.tz, 0, GL_RGBA, GL_UNSIGNED_INT, self.p.blitcode )
        glBindTexture(GL_TEXTURE_3D,  txid_blend)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage3D(GL_TEXTURE_3D, 0, GL_RGBA8, self.p.tx, self.p.ty, self.p.tz, 0, GL_RGBA, GL_UNSIGNED_BYTE, self.p.blendcode )
        
    def frame(self, x,y,z,w,h):
        maxx= 95
        maxy = 95
        rv = np.zeros((w, h), np.int32)
        if x + w < 0 or y+h < 0 or x > maxx or y > maxy:
            # black screen
            return rv
        sx = x
        left = 0
        if sx < 0:
            left = -sx
            sx = 0
        ex = x + w
        right = 0
        if ex > maxx:
            right = maxx - ex
            ex = maxx
        sy = y
        if sy < 0:
            top = -sy
            sy = 0
        ey = y + h
        if ey > maxy:
            bottom = maxy - ey
            ey = maxy
        
        # now cut'n'paste requested piece of crap onto correct spot 
        # in the rv.
        
        pompous_variable_name = self.p.madpump[sx:ex,sy:ey,z]
        rv[left:right, top:bottom] = pompous_variable_name
        return rv

class rednerer(object):
    def __init__(self, vs, fs, go):
        self.snap_to_grid = False
        self.gameobject = go
        
        self.grid_w = 80
        self.grid_h = 25
        
        
        self.vs = vs
        self.fs = fs
        self.reset_vbos = True
        
        self.texgen = None
        self.filter = GL_NEAREST
        
        self.opengl_initialized = False
        self.do_reset_glcontext = False
        self.do_update_attrs = True
        self.surface = None
        
        
        self.set_mode(1280, 1024)
        
    def set_mode(self, w, h, fullscreen=False):
        if self.surface is None:
            fs_state = False
            res_change = True
        else:
            fs_state = self.surface.get_flags() & pygame.FULLSCREEN
            res_change = ( surface.get_width() != w ) or (surface.get_height() != h)
            
        if self.opengl_initialized and ( (fullscreen_state and fullscree) or (not (fullscreen_state or fullscreen))) and not res_change:
            return True # nothing to do
        
        if self.opengl_initialized and self.do_reset_glcontext:
            self.opengl_fini()
        
        flags = pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE
        if fullscreen:
            flags |= pygame.SDL_FULLSCREEN
        
        pygame.display.set_mode((w,h), pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE)
        
        if not self.opengl_initialized:
            self.opengl_init()
        return True
        
    def opengl_init(self):
        
        glMatrixMode(GL_MODELVIEW) # always so as we don't do any model->world->eye transform
        glLoadIdentity()

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        gluOrtho2D(0, self.w_px, 0, self.h_px)
        #print repr(glGetFloatv(GL_PROJECTION_MATRIX))
        #glViewport(0, self.w_px, 0, self.h_px)
        glViewport(0, 0, self.w_px, self.h_px)

        glClearColor(0.3, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
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
        self.font_txid, self.txco_txid = glGenTextures(2)
        self.shader_setup()
        
        self.opengl_initialized = True
        
    def opengl_fini(self):
        self.shader = None
        glDeleteTextures()
        glDeleteBuffers()
        self.opengl_initialized = False
        self.do_update_attrs = True
        
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
        if  "GL_ARB_texture_rectangle" in exts:
            print "GL_ARB_texture_rectangle: supported"
        else:
            print "GL_ARB_texture_rectangle: NOT SUPPORTED"
        
    def shader_setup(self, nominal=True):
        print "Compiling shaders: \n {0}\n {1}".format(self.vs, self.fs)
        vs = file(self.vs).readlines()
        fs = file(self.fs).readlines()
        if nominal:
            vs.insert(5,"#define NOMINAL")
            fs.insert(5,"#define NOMINAL")
        try:
            where = 'vertex'
            vsp = compileShader("\n".join(vs), GL_VERTEX_SHADER)
            where = 'fragment'
            fsp = compileShader("\n".join(fs), GL_FRAGMENT_SHADER)
        except RuntimeError, e:
            print where, e[0]#, e[1][0]
            raise SystemExit
        
        where = 'link'

        self.shader = compileProgramTheRightWay( vsp, fsp ) 
        
        uniforms = "dispatch blitcode blendcode font txco txsz final_alpha viewpoint pszar frame_no".split()
        attributes = [ "screen" ] #.split()

        self.uloc = {}
        for u in uniforms:
            self.uloc[u] = glGetUniformLocation(self.shader, u)
            print "{0}: {1:08x}".format(u, self.uloc[u])
        self.aloc = {}
        for a in attributes:
            self.aloc[a] = glGetAttribLocation(self.shader, a)
            try:
                glEnableVertexAttribArray(self.aloc[a])
            except Exception, e:
                print "failed enabling VAA for {0}".format(a)
                print e
                raise
                
        glUniform1i(self.uloc["dispatch"], 0) # blitter dispatch tiu
        glUniform1i(self.uloc["blendcode"], 1) # blitter blend code tiu
        glUniform1i(self.uloc["blitcode"], 2) # blitter blit code tiu
        glUniform1i(self.uloc["font"], 3) # tilepage tilesizes tiu
        glUniform1i(self.uloc["txco"], 4) # tilepage tiu
        glUniform1f(self.uloc["final_alpha"], 1.0)
        glUniform2f(self.uloc["viewpoint"], 0, 0);
        glUniform1f(self.uloc["frame_no"], 0.0);

    def reload_shaders(self, frame, texture, nominal):
        self.shader = None
        print "reload_shaders(): shaders dropped, reloading with nominal={0}".format(nominal)
        self.shader_setup(nominal)
        self.reset_vbos = True

    def upload_textures(self): 
        w_t, h_t, t_w, t_h = self.gameobject.txco

        glUniform4f(self.uloc["txsz"],*self.txsz )  # tex size in tiles, tile size in texels
        print "txsz set to ( {0:0.2f}, {1:0.2f}, {2:0.2f}, {3:0.2f} )".format( w_t, h_t, t_w, t_h )
        

    def rebind_textures(self):
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.txid['dispatch'])
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_3D, self.txid['blendcode'])
        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_3D, self.txid['blitcode'])
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.txid['font'])
        glActiveTexture(GL_TEXTURE4)
        glBindTexture(GL_TEXTURE_2D, self.txid['txco'])

    def update_all_uniforms(self):
        #glUniform4f(self.uloc["txsz"], w_t, h_t, t_w, t_h )  # tex size in tiles, tile size in texels
        glUniform1f(self.uloc["final_alpha"], 1.0)
        glUniform2f(self.uloc["viewpoint"], 0, 0)
        glUniform4f(self.uloc["txsz"], *self.txsz ) 
        
    def update_vbos(self, frame_i):

        Parx = 1.0;
        Pary = 1.0;
        if frame.Pszx > frame.Pszy:
            Pary = float(frame.Pszy)/float(frame.Pszx)
        else:
            Parx = float(frame.Pszx)/float(frame.Pszy)
        glUniform3f(self.uloc["pszar"], Parx, Pary, frame.Psz)

        if self.reset_vbos:
            self.makegrid(frame.grid_w, frame.grid_h)
            self.reset_vbos = False
            
            Parx = 1.0;
            Pary = 1.0;
            if frame.Pszx > frame.Pszy:
                Pary = float(frame.Pszy)/float(frame.Pszx)
            else:
                Parx = float(frame.Pszx)/float(frame.Pszy)
            glUniform3f(self.uloc["pszar"], Parx, Pary, frame.Psz)
                
            buf = self.gameobject.frame()
            self.screen_vbo = vbo.VBO(buf, usage=GL_STREAM_DRAW)
            self.screen_vbo.bind()
            
            glVertexAttribPointer(self.aloc["screen"], 4, GL_UNSIGNED_BYTE, GL_FALSE, 0, self.screen_vbo)

        else:
            self.screen_vbo.set_array(frame.buf())
            self.screen_vbo.bind()


    """ 31.25 renderer_glsl  """
    MIN_GRID_X = 80
    MIN_GRID_Y = 25
    MAX_GRID_X = 256
    MAX_GRID_Y = 256
    
    def zoom(self, delta):
        psize  = self.psize + delta
        
        # get new grid size
        nw_t = math.floor(float(self.gw)/psize)
        nh_t = math.floor(float(self.gh)/psize)
        
        # clamp the crap, yarrrr
        nw_t = min(max(nw_t, 80), 256)
        nh_t = min(max(nh_t, 25), 256)
        
        # recalc resulting psize
        psize = math.floor(min(self.w_px/nw_t, self.h_px/nh_t))
        
        """ now what do we have:
            if the window is 
                so wide, that nw_t*(h_px/nh_t) > MAX_GRID_X
            or
                so tall, that n_ht*(w_px/nw_t) > MAX_GRID_Y
                
            the game just makes tiles change aspect ratio.
            if this is not an option, then prohibit zoom past that level
        """
        
        
        if self.snap_to_grid:
            self.w_px = self.psize*self.w_t
            self.h_px = self.psize*self.h_t
        
        #self.makegrid()
        
        
        self.reset_videomode()
        glUniform1f(self.uloc["pointsize"], psize)
    
    def reshape(self, wpx, hpx, gw, gh): 

        Pw = (1.0 * wpx)/gw
        Ph = (1.0 * hpx)/gh
        if Pw > Ph:
            Psize = Pw
            Parx = 1.0
            Pary = Ph/Pw
        else:            
            Psize = Ph
            Parx = Pw/Ph
            Pary = 1.0

        glUniform3f(self.uloc["pszar"], Parx, Pary, frame.Psz)
                
        self.makegrid(gw, gh)
        self.gw = gw
        self.gh = gh
        
    def makegrid(self, w, h):
        rv = []
        for xt in xrange(0, w):
            for yt in xrange(0, h):
                x = (xt + 0.5)#/w
                y = (h - yt - 0.5)#/h
                rv.append( [ x, y ] )
    
        self.vertexcount = len(rv)
        self.grid_vbo = vbo.VBO(np.array( rv, 'f' ), usage=GL_STATIC_DRAW)
        self.grid_vbo.bind()
        glVertexAttribPointer(self.aloc["position"], 2, GL_FLOAT, False, 0, self.grid_vbo)
        print "grid reset to {0} vertices".format(self.vertexcount)

    def render_frame(self, texture, frame_i, bgc, alpha):
        t = pygame.time.get_ticks()
        glUseProgram(self.shader) # is this rly needed?
        glUniform1f(self.uloc["final_alpha"], alpha)
        glUniform1i(self.uloc["frameno"], frame_i)
        self.update_vbos(texture)
        glClearColor(*bgc)
        glClear(GL_COLOR_BUFFER_BIT)
        self.grid_vbo.bind() # are these
        self.rebind_textures() # rly needed?
        self.update_all_uniforms()
        glUseProgram(self.shader)
        glDrawArrays(GL_POINTS, 0, self.vertexcount)
        pygame.display.flip()
        return  pygame.time.get_ticks() - t
        
    def loop(self):
        bgc = ( 0.0, 0.3, 0.0 ,1 )
        
        GFPS = 24
        frame_i = 0
        frame_max = 127
        vpx = vpy = x = y = z = 0
        
        slt = 1000.0/GFPS # milliseconds
        last_frame_ts = 0
        paused = False
        finished = False
        panning = False
        self.reset_vbo = True
        last_frame_ts = -1e23
        scrolldict = {
                                pygame.K_LEFT: ( -5, 0),
                                pygame.K_RIGHT: ( 5, 0),
                                pygame.K_UP: ( 0, -5),
                                pygame.K_DOWN: ( 0, 5),
                            }
        while not finished:
            last_render_ts = pygame.time.get_ticks()
            if not paused:
                frame_i += 1
                frame_i &= 0x7f
            render_time = self.render_frame(self.gameobject.frame(x,y,z,self.w_t,self.self.h_t), frame_i, bgc, 1.0)
            
            print "frame rendered in {0} msec".format(render_time)
            render_time += 1
            next_render_time = pygame.time.get_ticks() + slt - render_time
            while  True:
                for ev in pygame.event.get():
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_SPACE:
                            paused = not paused
                        elif ev.key == pygame.K_ESCAPE:
                            finished = True 
                        elif ev.key == pygame.K_F1:
                            self.reload_shaders(nominal=True)
                        elif ev.key == pygame.K_F2:
                            self.reload_shaders(nominal=False)
                        elif ev.key == pygame.K_LESS and z > 0:
                            z -= 1
                        elif ev.key == pygame.K_GREATER and z < self.gameobject.maxz:
                            z += 1
                        elif ev.key in scrolldict:
                            x += scrolldict[ev.key][0]
                            y += scrolldict[ev.key][1]
                        elif ev.key == pygame.K_BACKSPACE:
                            x = y = 0

                    elif ev.type == pygame.QUIT:
                        finished = True
                    elif ev.type ==  pygame.VIDEORESIZE:
                        self.reshape(ev.w, ev.h)
                    elif ev.type == pygame.MOUSEBUTTONDOWN:
                        if ev.button == 4: # wheel forward
                            self.zoom(-1)
                        elif ev.button == 5: # wheel back
                            self.zoom(+1)
                        elif ev.button == 3: # RMB
                            panning = True
                        else:
                            paused = not paused
                    elif ev.type == pygame.MOUSEBUTTONUP:
                        if ev.button == 3:
                            #print "panned to {0}x{1}".format(self.x, self.y)
                            panning = False
                            glUniform2f(self.uloc["viewpoint"], 0, 0)
                    elif ev.type ==  pygame.MOUSEMOTION:
                        if panning:
                            vpx -= ev.rel[0]
                            vpy += ev.rel[1]
                            if (vpx > self.psize): 
                                vpx = self.psize - vpx
                                x -= 1
                            elif vpx < 1:
                                x += 1
                                vpx = 0
                            if (vpy > self.psize): 
                                vpy = self.psize - vpy
                                y -= 1
                            elif vpy < 1:
                                y += 1
                                vpy = 0 
                            glUniform2f(self.uloc["viewpoint"], vpx, vpy)
                            
                if next_render_time - pygame.time.get_ticks() < -50:
                    print "drawing's too slow, {0:.2f} FPS vs {1:.2f} reqd".format(1000.0/render_time, gfps)
                    break
                elif next_render_time - pygame.time.get_ticks() < 0:
                    break
                elif next_render_time - pygame.time.get_ticks() < 50:
                    pygame.time.wait(int(next_render_time - pygame.time.get_ticks()))
                    break
                else:
                    pygame.time.wait(50)

    def fini(self):
        self.shader = None
        self.vbo = None
        glDeleteTextures((self.ansi_txid, self.font_txid))
        pygame.quit()




#~ debug_get_flags_option: help for ST_DEBUG:
#~ |      mesa [0x0000000000000001]
#~ |      tgsi [0x0000000000000002]
#~ | constants [0x0000000000000004]
#~ |      pipe [0x0000000000000008]
#~ |       tex [0x0000000000000010]
#~ |  fallback [0x0000000000000020]
#~ |    screen [0x0000000000000080]
#~ |     query [0x0000000000000040]

#~ debug_get_flags_option: help for LP_DEBUG: -- softpipe only
#~ |          pipe [0x0000000000000001]
#~ |          tgsi [0x0000000000000002]
#~ |           tex [0x0000000000000004]
#~ |         setup [0x0000000000000010]
#~ |          rast [0x0000000000000020]
#~ |         query [0x0000000000000040]
#~ |        screen [0x0000000000000080]
#~ |    show_tiles [0x0000000000000200]
#~ | show_subtiles [0x0000000000000400]
#~ |      counters [0x0000000000000800]
#~ |         scene [0x0000000000001000]
#~ |         fence [0x0000000000002000]
#~ |           mem [0x0000000000004000]
#~ |            fs [0x0000000000008000]

#~ debug_get_flags_option: help for GALLIVM_DEBUG:
#~ |         tgsi [0x0000000000000001]
#~ |           ir [0x0000000000000002]
#~ |          asm [0x0000000000000004]
#~ |         nopt [0x0000000000000008]
#~ |         perf [0x0000000000000010]
#~ | no_brilinear [0x0000000000000020]
#~ |           gc [0x0000000000000040]


#export LP_DEBUG=tgsi
#export ST_DEBUG=tgsi,mesa
#export GALLIVM_DEBUG=tgsi
#export MESA_DEBUG=y
#export LIBGL_DEBUG=verbose
#export GALLIUM_PRINT_OPTIONS=help
#export TGSI_PRINT_SANITY=y

if __name__ == "__main__":
    mo = mapobject()
    t = time.time()
    re = rednerer('fg_is_win.vs', 'fg_is_win.fs', mo)
    print "second_stage: {0:.4f} sec.".format(time.time()-t)
    re.loop()
    

if __name__ == "old__main__":
    ap = argparse.ArgumentParser(description = '[PRINT_MODE:SHADER] testbed')
    ap.add_argument('-fps', '--fps', metavar='fps', type=float, default=0.4)
    ap.add_argument('-rect', '--rect', metavar='texture mode', dest='tmode', action='store_const', const=GL_TEXTURE_RECTANGLE)
    ap.add_argument('-npot', '--npot', metavar='texture mode', dest='tmode', action='store_const', const=GL_TEXTURE_2D)
    ap.add_argument('-gfps', '--gfps', metavar='gfps', type=float, default=1.0)
    ap.add_argument('-s', '--start-frame', metavar='start frame', type=int, default=0)
    ap.add_argument('-vs', '--vertex-shader',  metavar='vertex shader', default='data/cbr_is_bold.vs')
    ap.add_argument('-fs', '--fragment-shader',  metavar='fragment shader', default='data/cbr_is_bold.fs')
    ap.add_argument('dumpname', metavar="dump_prefix", help="dump name prefix (foobar in foobar.sdump/foobar0000.png)")
    ap.add_argument('mesa', metavar="mesa_driver", nargs='?', default="hw", help="mesa driver, values: hw, hw-alt, sw, sw-alt")
        
    pa = ap.parse_args()
    if pa.tmode is None:
        pa.tmode = GL_TEXTURE_2D
        
    envi = {
        "hw": (),
        "hw-alt": (("LIBGL_DRIVERS_PATH","/usr/lib/x86_64-linux-gnu/dri-alternates"),),
        "sw" : (("LIBGL_ALWAYS_SOFTWARE","y"),),
        "sw-alt": (("LIBGL_ALWAYS_SOFTWARE","y"), ("LIBGL_DRIVERS_PATH","/usr/lib/x86_64-linux-gnu/dri-alternates"),)
    }
    
    for v in envi.values():
        for et in v:
            if et:
                try:
                    del os.environ[et[0]]
                except KeyError:
                    pass
    if pa.mesa:
        for et in envi[pa.mesa]:
            if et:
                os.environ[et[0]] = et[1]
    
    try:
        stuff = StuffDump(pa.dumpname)
        
        r = rednener(stuff, pa.vertex_shader, pa.fragment_shader, pa.tmode)
    except OSError, e:
        traceback.print_exc(e)
        ap.print_help()
        sys.exit(1)
    
    r.loop(fps=pa.fps, gfps=pa.gfps, start_frame=pa.start_frame)
    r.fini()

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

import os, os.path, collections, struct, mmap
import ctypes, ctypes.util
import logging, subprocess
from ctypes import c_void_p as gl_off_t

import pygame2.sdl as sdl
import pygame2.sdl.events as sdlevents
import pygame2.sdl.mouse as sdlmouse
import pygame2.sdl.video as sdlvideo
import pygame2.sdl.surface as sdlsurface
import pygame2.sdl.pixels as sdlpixels
import pygame2.sdl.rwops as sdlrwops
import pygame2.sdl.hints as sdlhints

from pygame2.sdl.rect import SDL_Rect
from pygame2.sdl.video import SDL_Surface
from pygame2 import sdlttf, sdlimage

import OpenGL

OpenGL.ERROR_CHECKING_GLSL = False
OpenGL.FORWARD_COMPATIBLE_ONLY = True
OpenGL.FULL_LOGGING = 'GLTRACE' in os.environ
OpenGL.ERROR_ON_COPY = True

from OpenGL.GL import *
from OpenGL.GL.ARB.debug_output import *
from OpenGL.GL.ARB.copy_buffer import *
from OpenGL.error import GLError
from OpenGL.GL.ARB.texture_rg import *

from gi.repository import freetype2

import fgt
from fgt.glname import glname as glname
from fgt.sdlenums import *

__all__ = """sdl_init sdl_flip sdl_offscreen_init sdl_fini
bar2voidp mmap2voidp CArray rgba_surface a_mono_font
glinfo gldumplog glcalltrace
upload_tex2d upload_tex2da dump_tex2da texparams
Shader0 VAO0 VertexAttr GridVAO
Rect Coord2 Coord3 Size2 Size3 GLColor
FBO TexFBO SurfBunchPBO Blitter FtBitmap""".split()

Coord2 = collections.namedtuple('Coord2', 'x y')
Coord3 = collections.namedtuple('Coord3', 'x y z')
Rect = collections.namedtuple('Rect', 'x y w h')
Size2 = collections.namedtuple('Size2', 'w h')
Size3 = collections.namedtuple('Size3', 'w h d')
GLColor = collections.namedtuple('GLColor', 'r g b a')
VertexAttr = collections.namedtuple('VertexAttr', 'index size type stride offset')

ctypes.pythonapi.PyByteArray_AsString.restype = ctypes.c_void_p
ctypes.pythonapi.PyByteArray_FromStringAndSize.restype = ctypes.py_object
libc = ctypes.CDLL(ctypes.util.find_library("c"))

def glnamelist(*args):
    """ For glDeleting stuff without CopyErrors.
        Note that glDeleteTextures is "exceptional" in that it
        doesn't want the first parameter. What a joke. """
    n = len(args)
    return n, struct.pack("I"*n, *args)

def bar2voidp(bar):
    return ctypes.c_void_p(ctypes.pythonapi.PyByteArray_AsString(id(bar)))

def mmap2voidp(_mmap):
    PyObject_HEAD = [ ('ob_refcnt', ctypes.c_size_t), ('ob_type', ctypes.c_void_p) ]
    PyObject_HEAD_debug = PyObject_HEAD + [
        ('_ob_next', ctypes.c_void_p), ('_ob_prev', ctypes.c_void_p), ]
    class mmap_mmap(ctypes.Structure):
        _fields_ = PyObject_HEAD + [ ('data', ctypes.c_void_p), ('size', ctypes.c_size_t) ]
    guts = mmap_mmap.from_address(id(_mmap))
    return ctypes.c_void_p(guts.data) # WTF??

def pot_align(value, pot):
    return (((value - 1)>>pot) + 1) << pot
    return (value + (1<<pot) - 1) & ~((1<<pot) -1)

class CArray(object):
    def __init__(self, data, fmt, w, h=1, d=1):
        assert ( h != 1) or ( d == 1) # I don't need this crap
        self.dt = struct.Struct(fmt)
        self.w = w
        self.h = h 
        self.d = d
        if data is None:
            self.data = bytearray(w*h*d*self.dt.size)
        else:
            if len(data) < self.dt.size*w*h*d:
                raise ValueError("insufficient data: {} < {}".format(len(data), self.dt.size*w*h*d))
            elif len(data) > self.dt.size*w*h*d:
                logging.getLogger("fgt.CArrray").warn("{} extra bytes".format(len(data) - self.dt.size*w*h*d))
            self.data = data

    def __str__(self):
        return "{}x{}x{}; {}K".format(self.w, self.h, self.d,
            self.w*self.h*self.d*self.dt.size >>10)

    def bzero(self):
        self.memset(0)

    def memset(self, c):
        ctypes.memset(self.ptr, c, self.w*self.h*self.d*self.dt.size)

    def fill(self, value):
        for i in range(self.w*self.h*self.d):
            self.dt.pack_into(self.data, self.dt.size*i, *value)

    def get(self, x, y=0, z=0):
        offs = self.dt.size*(x + y*self.w + z*self.w*self.h)
        return self.dt.unpack_from(self.data, offs)
            
    def set(self, value, x, y=0, z=0):
        offs = self.dt.size*(x + y*self.w + z*self.w*self.h)
        self.dt.pack_into(self.data, offs, *value)

    @property
    def ptr(self):
        if isinstance(self.data, bytearray):
            return bar2voidp(self.data)
        elif isinstance(self.data, mmap.mmap):
            return mmap2voidp(self.data)
        else:
            raise TypeError("no ptr for {}".format(type(self.data)))
    
    def dump(self, flike):
        flike.write(self.data)

def upload_tex2d(txid, informat, tw, th, dformat, dtype, dptr, filter):
    glBindTexture(GL_TEXTURE_2D, txid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filter)
    glTexImage2D(GL_TEXTURE_2D, 0, informat, tw, th, 0, dformat, dtype, dptr)
    #if informat != GL_RGBA8:
        #texparams(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, 0)

def upload_tex2da(txid, informat, tw, th, td, dformat, dtype, dptr, filter):
    glBindTexture(GL_TEXTURE_2D_ARRAY,  txid)
    try:
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    except:
        gldump()
        raise
    glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, filter)
    glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, filter)
    #glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAX_LEVEL, 0)
    #unpackstate()
    glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, informat, tw, th, td, 0, dformat, dtype, dptr)
    #texparams(GL_TEXTURE_2D_ARRAY)

def unpackstate(callable = print):
    d = [
            (glGetBoolean, GL_UNPACK_SWAP_BYTES, "GL_UNPACK_SWAP_BYTES"),
            (glGetBoolean, GL_UNPACK_LSB_FIRST, "GL_UNPACK_LSB_FIRST"),
            (glGetInteger, GL_UNPACK_IMAGE_HEIGHT, "GL_UNPACK_IMAGE_HEIGHT"),
            (glGetInteger, GL_UNPACK_SKIP_IMAGES, "GL_UNPACK_SKIP_IMAGES"),
            (glGetInteger, GL_UNPACK_ROW_LENGTH, "GL_UNPACK_ROW_LENGTH"),
            (glGetInteger, GL_UNPACK_SKIP_ROWS, "GL_UNPACK_SKIP_ROWS"),
            (glGetInteger, GL_UNPACK_SKIP_PIXELS, "GL_UNPACK_SKIP_PIXELS"),
            (glGetInteger, GL_UNPACK_ALIGNMENT, "GL_UNPACK_ALIGNMENT"),
        ]
    for foo, param, name in d:
        callable("{} = {}".format(name, foo(param)))

def texparams(target, callable = print):
    w = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_WIDTH)
    h = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_HEIGHT)
    d = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_DEPTH)
    ifmt = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_INTERNAL_FORMAT)
    rt = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_RED_TYPE)
    bt = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_GREEN_TYPE)
    gt = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_BLUE_TYPE)
    at = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_ALPHA_TYPE)
    rsz = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_RED_SIZE)
    gsz = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_GREEN_SIZE)
    bsz = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_BLUE_SIZE)
    asz = glGetTexLevelParameteriv(target, 0, GL_TEXTURE_ALPHA_SIZE)
    min_f = glGetTexParameteriv(target, GL_TEXTURE_MIN_FILTER)
    max_f = glGetTexParameteriv(target, GL_TEXTURE_MAG_FILTER)
    wrap_s = glGetTexParameteriv(target, GL_TEXTURE_WRAP_S)
    wrap_t = glGetTexParameteriv(target, GL_TEXTURE_WRAP_T)
    callable(w,h,d,glname.get(ifmt))
    callable(glname.get(rt),glname.get(bt),glname.get(gt),glname.get(at),rsz,gsz,bsz,asz)
    callable(glname.get(min_f), glname.get(max_f), glname.get(wrap_s), glname.get(wrap_t))
    

def dump_tex2da(fname):
    d = glGetTexImage(GL_TEXTURE_2D_ARRAY, 0, GL_RGBA_INTEGER, GL_UNSIGNED_INT)
    gldumplog()
    open(fname, "wb").write(d)
    raise SystemExit
    
    
class Shader0(object):
    """ shader base class.
        
        Descendants are expected to implement __call__ method
        that should take UseProgram() and update set any uniforms
        necessary.
        
        Currently it is considered best practice to set all uniform values
        in the __call__() method even if some of them are constant or 
        did not change since last invocation. This is to keep all the state
        in a single place.
    
        Fragment shader code is expected to put the frag color into
            vec4 out frag;
        
        Vertex attribute number 0 is always named 'position'.
                
    """
    aloc = { b'position': 0 }
    prepend = ()
    def __init__(self, sname=None):
        log_locs = logging.getLogger('fgt.shader.locs').info
        
        self.uloc = collections.defaultdict(lambda:-1)
        if sname is None:
            sname = self.sname
        vsfn = os.path.join(fgt.config.shaderpath, sname) + '.vs'
        fsfn = os.path.join(fgt.config.shaderpath, sname) + '.fs'
        prepend = list(map(lambda x: x+"\n", self.prepend))
        vsp = self._compile(prepend + open(vsfn, encoding='utf-8').readlines(), GL_VERTEX_SHADER, vsfn)
        fsp = self._compile(prepend + open(fsfn, encoding='utf-8').readlines(), GL_FRAGMENT_SHADER, fsfn)
        if not (vsp and fsp):
            raise SystemExit
        
        program = glCreateProgram()

        for shader in (vsp, fsp):
            glAttachShader(program, shader)
            glDeleteShader(shader)
            
        for name, loc in self.aloc.items():
            glBindAttribLocation(program, loc, name)
            log_locs("  vao{0}: name={1}".format(loc, name))
        glBindFragDataLocation(program, 0, b'frag')

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
        for i in range(au):
            name, wtf, typ = glGetActiveUniform(program, i)
            loc = glGetUniformLocation(program, name)
            self.uloc[name] = loc
            log_locs("  uni{0}: name={1} type={2} loc={3}".format(i, name, glname.get(typ, typ), loc))
        
        self.program = program

    def __call__(self):
        raise NotImplemented
    
    def _compile(self, lines, stype, filename):
        log = logging.getLogger('fgt.shader')
        rv = glCreateShader(stype)
        glShaderSource(rv, lines)
        try:
            glCompileShader(rv)
        except GLError:
            result = GL_FALSE
        result = glGetShaderiv(rv, GL_COMPILE_STATUS)
        nfo = glGetShaderInfoLog(rv)
        if result == GL_TRUE:
            log.info("compiled '{}'.".format(filename))
            if len(nfo) > 0:
                for l in nfo.decode('utf-8').strip().split("\n"):
                    log.info(l)
        else:
            log.error("compiling '{}': ".format(filename))
            if len(nfo) > 0:
                for l in nfo.decode('utf-8').strip().split("\n"):
                    log.error(l)
        return rv
    
    def validate(self):
        glValidateProgram(self.program)
        validation = glGetProgramiv( self.program, GL_VALIDATE_STATUS )
        if validation == GL_FALSE:
            gldump()
            raise RuntimeError(
                """Validation failure (%s): %s"""%(
                validation,
                glGetProgramInfoLog(self.program ),
            ))

class VAO0(object):
    """ http://www.opengl.org/wiki/Vertex_Array_Object 
        a VAO with a single VBO and w/o elements.
    """
    _primitive_type = None # GL_POINTS or whatever
    _data_type = None # struct.Struct(something)
    _attrs = None
    
    def __init__(self):
        glcalltrace("{}.{}()".format(self.__class__.__name__, '__init__'))
        self._vao_name = glGenVertexArrays(1)
        self._vbo_name = glGenBuffers(1)
        self._count = 0
        self._data = bytearray(32)
    
    def _create(self):
        glcalltrace("{}.{}()".format(self.__class__.__name__, '_create'))
        glBindVertexArray(self._vao_name)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_name)
        for a in self._attrs:
            glEnableVertexAttribArray(a.index)
            glVertexAttribIPointer(a.index, a.size, a.type, 
                a.stride, ctypes.c_void_p(a.offset))
    
    def __len__(self):
        return self._count
    
    def __call__(self):
        glcalltrace("{}.{}()".format(self.__class__.__name__, '__call__'))
        glBindVertexArray(self._vao_name)
        glDrawArrays(self._primitive_type, 0, self._count)

    def update(self, attrs, count = None):
        glcalltrace("{}.{}()".format(self.__class__.__name__, 'update'))
        count = len(attrs) if count is None else count
        grew = count > self._count
        self._count = count
        data_size = count * self._data_type.size
        if data_size > len(self._data):
            self._data.extend(0 for i in range(data_size - len(self._data)))
        i = 0
        for d in attrs:
            offs = i * self._data_type.size
            self._data_type.pack_into(self._data, offs, *d)
            i += 1

        data_ptr = bar2voidp(self._data)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_name)
        if grew:
            glBufferData(GL_ARRAY_BUFFER, data_size, data_ptr, GL_DYNAMIC_DRAW)
            self._create()
        else:
            glBufferSubData(GL_ARRAY_BUFFER, 0, data_size, data_ptr)

    def fini(self):
        glDeleteVertexArrays(*glnamelist(self._vao_name))
        glDeleteBuffers(*glnamelist(self._vbo_name))
        del self._vbo_name
        del self._vao_name

class GridVAO(VAO0):
    _primitive_type = GL_POINTS
    _data_type = struct.Struct('II')
    _attrs = (VertexAttr( 0, 2, GL_INT, 0, 0 ),)

    def resize(self, size):
        w, h = self.size = size
        self.update(iter( (i%w, i//w) for i in range(w*h) ), w*h)

    def __str__(self):
        return "GridVAO(size={} num={})".format(self.size, self._count)

class FBO(object):
    """ aids smooth panning.

        the map view is rendered onto this FBO, which is sized so that 
        it is 2 (or maybe 16, in future) tiles larger than the actual window
        and aligned to contain integral number of tiles. Then the potion
        actually visible is blitted onto the window.
        
        size is the actual size of the underlying framebuffer: tuple(w, h)
    """
    def __init__(self, size = None):
        self.fb_name = glGenFramebuffers(1)
        self.rb_name = glGenRenderbuffers(1)
        self.size = None
        if size is not None:
            self.resize(size)
        
    def resize(self, size):
        if self.size == size:
            return
        self.size = size
        glBindFramebuffer(GL_FRAMEBUFFER, self.fb_name)
        glBindRenderbuffer(GL_RENDERBUFFER, self.rb_name)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, size.w, size.h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, self.rb_name)
        x = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if x != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("framebuffer incomplete: {}".format(glname.get(x,x)))
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def bind(self, clear = None):
        """ call this before rendering the map view """
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.fb_name)
        glViewport(0, 0, self.size.w, self.size.h)
        if clear is not None:
            glClearColor(*clear)
            glClear(GL_COLOR_BUFFER_BIT)
    
    def readpixels(self, rect):
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fb_name)
        return glReadPixels(*rect, format=GL_RGBA, type=GL_UNSIGNED_INT_8_8_8_8)
    
    def dump(self, filename, srcrect = None):
        if srcrect is None:
            srcrect = Rect(0,0,self.size.w, self.size.h)
        pixels = self.readpixels(srcrect)
        surf = rgba_surface(srcrect.w, srcrect.h, pixels)
        surf.write_bmp(filename)
        log = logging.getLogger("fgt.fbo.dump").info("wrote '{}'".format(filename))
    
    def blit(self, srcrect):
        """ blits visible part onto the window. 
            srcrect: tuple (x, y, w, h) 
            w,h should be equal to the window size"""
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fb_name)
        
        x0 = srcrect.x
        y0 = srcrect.y
        x1 = srcrect.x + srcrect.w
        y1 = srcrect.y + srcrect.h

        glBlitFramebuffer( 
                x0, y0, x1, y1,
                 0,  0, srcrect.w, srcrect.h,
                GL_COLOR_BUFFER_BIT, GL_LINEAR)

        glViewport(0, 0, srcrect.w, srcrect.h)

    def fini(self):
        glDeleteRenderbuffers(*glnamelist(self.fb_name))
        glDeleteFramebuffers(*glnamelist(self.rb_name))
        del self.fb_name
        del self.rb_name

class TexFBO(object):
    """ render target for most of rendering.
        supports context mgmt protocol for both rendering to and from
        i.e. :
            with some_fbo.target(Size2(tex_w,tex_h)):
                ...
                render shit
                ...
        later:
            with same_fbo.source(GL_TEXTURE23)
                with other_fbo.target(Size2(window_w,window_h))
                    ...
                    render other shit
                    ...
        and/or:
            with some_fbo.pixels([offset=..., size=...]) as pixels
                ...
                read those pixels which are a c_void_p but don't write'em
                ...

        doing something like:
            ctm = some_fbo.a_ctx_manager_factory(...)
              ... here take a dump into the GL state
            with ctm:
                ....
        is discouraged.

        Nesting of same-type contexts will mess up GL state since they
        don't rebind back buffers that were bound to their targets prior.

        GL state sanity is your problem. """

    def __init__(self, size):
        self.fb_name = glGenFramebuffers(1)
        self.tex_name = glGenTextures(1)
        self.bo_name = glGenBuffers(1)

        glBindTexture(GL_TEXTURE_2D, self.tex_name)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)

        self.size = None
        #if size is not None:
        #    self.resize(size)
        self.resize(size)

    def as_target(self, clear=None):
        owner = self
        class _fbo_target_ctx(object):
            def __enter__(ctxm):
                glBindFramebuffer(GL_DRAW_FRAMEBUFFER, owner.fb_name)
                glViewport(0, 0, owner.size.w, owner.size.h)
                if clear is not None:
                    glClearColor(*clear)
                    glClear(GL_COLOR_BUFFER_BIT)
            def __exit__(ctxm, et, ev, tb):
                pass
        return _fbo_target_ctx()

    def as_texture(self, textarget):
        if self.size is None:
            raise EOFError("no pixels here")
        tex_name = self.tex_name
        class _fbo_source_ctx(object):
            def __enter__(ctxm):
                glActiveTexture(textarget)
                glBindTexture(GL_TEXTURE_2D, tex_name)
            def __exit__(ctxm, et, ev, tb):
                pass
        return _fbo_source_ctx()

    def as_pixels(self, offset=0, size=None):
        if self.size is None:
            raise EOFError("no pixels here")
        elif size is None:
            size = self.bytesize
        if offset < 0 or size <= 0 or offset+size > self.bytesize:
            raise ValueError("bogus offset and/or size ")

        buftarget = GL_COPY_READ_BUFFER_ARB # in GL_ARB_copy_buffer
        buftarget = GL_COPY_READ_BUFFER # in 3.1
        class _fbo_pixel_ctx(object):
            def __enter__(ctxm):
                glBindBuffer(buftarget, self.bo_name)
                return glMapBufferRange(buftarget, offset, size, GL_MAP_READ_BIT)
            def __exit__(ctxm, et, ev, tb):
                glBindBuffer(buftarget, self.bo_name)
                glUnmapBuffer(buftarget)
        return _fbo_pixel_ctx()

    def resize(self, size):
        if self.size == size:
            return
        self.size = size
        self.bytesize = size.w*size.h*4

        # [re]-init texture storage
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.bo_name)
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.bytesize, ctypes.c_void_p(0), GL_STREAM_DRAW)
        glBindTexture(GL_TEXTURE_2D, self.tex_name)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, size.w, size.h, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, ctypes.c_void_p(0))

        # attach the texture
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.fb_name)
        glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
            GL_TEXTURE_2D, self.tex_name, 0)

        # check completeness
        x = glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER)
        if x != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("framebuffer incomplete: {}".format(glname.get(x,x)))
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)

    def fini(self):
        glDeleteFramebuffers(*glnamelist(self.fb_name))
        glDeleteTextures(glnamelist(self.tex_name)[1])
        glDeleteBuffers(*glnamelist(self.bo_name))
        del self.fb_name
        del self.tex_name
        del self.bo_name

SurfTex = collections.namedtuple('SurfTex', 'surface texname')
class SurfBunchPBO(object):
    """ a bunch of surfaces backed by a pixel buffer object for upload.
        Only GL_TEXTURE2D for now. Fmt/data_fmt/data_type are controlled
        by surface type classvars. Surface type must have those params;
        its constructor must accept 'w','h' positional and 'data_ptr' keyword
        arguments, where 'data_ptr' is c_void_p or similar.

        TexEnv is up to texbunch supplier.
        Be sure not to do reads on the surfaces.

        TODO:
            - Avoid rgba_surface recreation on swaps.
            - Avoid complete teardown on resize

        """

    def __init__(self, sizes, surface_type, filter=GL_LINEAR, wrap=GL_CLAMP_TO_EDGE):
        """ where sizes is a dict some_key -> Size2
            textures and surfaces are later accessed by this key """
        assert len(sizes)
        self.surftype = surface_type
        self.frontbuf, self.backbuf = glGenBuffers(2)
        self.store = {}
        self.surfaces = {}
        offset = 0
        self.texnames = tuple(glGenTextures(len(sizes)))
        texnames = list(self.texnames)
        for some_key, size in sizes.items():
            texname = texnames.pop(0)
            glBindTexture(GL_TEXTURE_2D, texname)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filter)
            self.store[some_key] = ( texname, size, offset )
            offset += size.w*size.h*4
        self.bufsize = offset
        glBindTexture(GL_TEXTURE_2D, 0)

        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.backbuf)
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.bufsize, gl_off_t(0), GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.frontbuf)
        glBufferData(GL_PIXEL_UNPACK_BUFFER, self.bufsize, gl_off_t(0), GL_STREAM_DRAW)
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

        self.swap() # initializes self.surfaces.

    def __getitem__(self, k):
        """ return a SurfTex, rest is implementation detail. """
        return SurfTex(self.surfaces[k], self.store[k][0])

    def __contains__(self, k):
        return k in self.store

    def keys(self):
        return keys(self.store)

    def __len__(self):
        return len(self.store)

    def __iter__(self):
        for k in self.store.keys():
            yield k
        raise StopIteration

    def items(self):
        for k in self.store.keys():
            yield ( k, self.__getitem__(k) )
        raise StopIteration

    def swap(self):
        self.frontbuf, self.backbuf = self.backbuf, self.frontbuf
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.frontbuf)
        ptr = glMapBuffer(GL_PIXEL_UNPACK_BUFFER, GL_WRITE_ONLY)
        for some_key, stuff in self.store.items():
            unused, size, offset = stuff
            try:
                self.surfaces[some_key].free()
            except KeyError:
                pass
            glop = ctypes.c_void_p(ptr + offset)
            self.surfaces[some_key] = self.surftype(size.w, size.h, data_ptr = glop)

    def upload(self):
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.frontbuf)
        glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER)
        for texname, size, offset in self.store.values():
            glBindTexture(GL_TEXTURE_2D, texname)
            glTexImage2D(GL_TEXTURE_2D, 0, self.surftype.gl_internal_fmt,
                size.w, size.h, 0, self.surftype.gl_data_fmt,
                self.surftype.gl_data_type, gl_off_t(offset))
        self.swap()

    def fini(self):
        if len(self.texnames):
            glDeleteTextures(glnamelist(*self.texnames)[1])
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, self.frontbuf)
        glUnmapBuffer(GL_PIXEL_UNPACK_BUFFER, self.frontbuf)
        glDeleteBuffers(*glnamelist(self.frontbuf, self.backbuf))

        del self.texnames
        del self.frontbuf
        del self.backbuf

class BlitVAO(VAO0):
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

class BlitShader(Shader0):
    sname = "blit"
    M_FILL   = 1 # fill with color
    M_BLEND  = 2 # texture it
    M_OPAQUE = 3 # force texture alpha to 1.0
    M_RALPHA = 4 # fill with color; take alpha from tex

    def __call__(self, dstsize, mode, color, srcrect, srcsize):
        glUseProgram(self.program)
        glUniform1i(self.uloc[b"tex"], 0)
        glUniform2i(self.uloc[b"dstsize"], *dstsize)
        glUniform1i(self.uloc[b"mode"], mode)
        glUniform4f(self.uloc[b"color"], *color)
        glUniform4i(self.uloc[b"srcrect"], *srcrect)
        glUniform2i(self.uloc[b"srcsize"], *srcsize)

class Blitter(object):
    def __init__(self):
        self.shader = BlitShader()
        self.vao = BlitVAO()
        self.log = logging.getLogger("fgt.ui.blitter")

    def fill(self, *args, **kwargs):
        return self._blit(self.shader.M_FILL, *args, **kwargs)

    def texblend(self, *args, **kwargs):
        return self._blit(self.shader.M_BLEND, *args, **kwargs)

    def tex(self, *args, **kwargs):
        return self._blit(self.shader.M_OPAQUE, *args, **kwargs)

    def ralpha(self, *args, **kwargs):
        return self._blit(self.shader.M_RALPHA, *args, **kwargs)

    def _blit(self, mode, dstrect, dstsize, color=(0,0,0,0.68),
                srcrect = Rect(0,0,0,0), srcsize = Size2(0,0)):
        """ dstsize - size of destination viewport for calculating NDC
            srcrect, srcsize - for partial blitting """
        self.log.debug("mode={} dstrect={} vpsize={}".format(mode, dstrect, dstsize))
        self.vao.set(dstrect)
        self.shader(dstsize, mode, color, srcrect, srcsize)
        self.vao()

class FtBitmap(object):
    gl_unpack_alignment = 4
    gl_internal_fmt = GL_R8
    gl_data_fmt = GL_RED
    gl_data_type = GL_UNSIGNED_BYTE

    def __init__(self, w, h, data_ptr = None):
        self.gob = freetype2.Bitmap()
        self.gob.rows = h
        self.gob.width = w
        self.gob.pitch = pot_align(w, 2)
        self.gob.num_grays = 256
        self.pixel_mode = freetype2.PixelMode.GRAY
        if data_ptr is None:
            self.gob.buffer = libc.malloc(len(self))
            libc.memset(self.gob.buffer, 0, len(self))
            self.do_free = True
        else:
            self.gob.buffer = data_ptr.value
            self.do_free = False

    def __str__(self):
        return "size:{}x{} pitch:{} bytes:{}".format(self.gob.width,
            self.gob.rows, self.gob.pitch, len(self))

    @property
    def ptr(self):
        return self.gob.buffer

    def __len__(self):
        print( self.gob.pitch * self.gob.rows )
        return self.gob.pitch * self.gob.rows

    def bytearray(self):
        return ctypes.pythonapi.PyByteArray_FromStringAndSize(self.gob.buffer, len(self))

    def free(self):
        if self.do_free:
            libc.free(self.gob.buffer)
        del self.gob

def glinfo():
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
#        (   -3.0, GL_MIN_PROGRAM_TEXEL_OFFSET, "GL_MIN_PROGRAM_TEXEL_OFFSET" ), 
#        (    3.0, GL_MAX_PROGRAM_TEXEL_OFFSET, "GL_MAX_PROGRAM_TEXEL_OFFSET" ), 
#        (    3, GL_MAX_VERTEX_OUTPUT_COMPONENTS, "GL_MAX_VERTEX_OUTPUT_COMPONENTS" ), # 1 texture_coord = 4 varying_floats?
#        (   -4, GL_POINT_SIZE_MIN, "GL_POINT_SIZE_MIN" ),
#        (   32, GL_POINT_SIZE_MAX, "GL_POINT_SIZE_MAX" ),
        (    2, GL_MAX_VERTEX_ATTRIBS, "GL_MAX_VERTEX_ATTRIBS" ), 
#        (    2, GL_MAX_VERTEX_UNIFORM_BLOCKS, "GL_MAX_VERTEX_UNIFORM_BLOCKS" ),
    ]

    log = logging.getLogger('fgt.glinfo')
    log_exts = logging.getLogger('fgt.glinfo.extensions')

    if log_exts.isEnabledFor(logging.INFO):
        for i in range(glGetInteger(GL_NUM_EXTENSIONS)):
            log_exts.info(glGetStringi(GL_EXTENSIONS, i).decode('utf-8'))
    
    if log.isEnabledFor(logging.INFO):
        for e,s in strs.items():
            log.info("{0}: {1}".format(s, glGetString(e).decode('utf-8')))
            
        for t in ints:
            try:
                if isinstance(t[0], int):
                    p = glGetInteger(t[1])
                elif isinstance(t[0], float):
                    p = glGetFloat(t[1])
                else:
                    raise WTFError
                if (p<t[0]) or ((t[0]<0) and (p+t[0] >0)):
                    w = "** "
                else:
                    w = ""
                log.info("{0}: {1}".format(t[2], p, abs(t[0]), w))
            except GLError as e:
                if e.err != 1280:
                    raise
                log.warn("{0}: {1}".format(t[2], "invalid enumerant"))
        gldumplog()

def glcalltrace(s):
    s = "{0} {1} {0}".format("*" * 16, s)
    logging.getLogger('OpenGL.calltrace' ).info(s)

def gldumplog(header = '', logger = None):
    if not bool(glGetDebugMessageLogARB):
        return
    if logger is None:
        logger = logging.getLogger('OpenGL.debug_output')

    count = 256
    logSize = 1048576
    sources = arrays.GLuintArray.zeros((count, ))
    types = arrays.GLuintArray.zeros((count, ))
    ids = arrays.GLuintArray.zeros((count, ))
    severities = arrays.GLuintArray.zeros((count, ))
    lengths = arrays.GLsizeiArray.zeros((count, ))
    messageLog = arrays.GLcharArray.zeros((logSize, ))

    num = glGetDebugMessageLogARB(count, logSize, sources, types, ids, severities, lengths, messageLog)
    offs = 0
    ldict = {
        GL_DEBUG_SEVERITY_HIGH_ARB : logger.error,
        GL_DEBUG_SEVERITY_MEDIUM_ARB : logger.warn,
        GL_DEBUG_SEVERITY_LOW_ARB : logger.info,
    }

    first = True
    for n in range(num):
        msg = bytes(messageLog[offs:offs+lengths[n]]).decode('utf-8')
        if first:
            glcalltrace("gldump({})".format(header))
            logger.info("gldump({})".format(header))
            first = False
        ldict.get(severities[n],logger.error)(
            "{} {} {} {} {}".format(
                glname.get(sources[n], sources[n]),
                glname.get(types[n], types[n]),
                glname.get(ids[n], ids[n]),
                glname.get(severities[n], severities[n]),
                msg))
        offs += lengths[n]

def sdl_init(size=(1280, 800), title = "DFFG testbed", icon = None, gldebug=False, fwdcore=False):
    log = logging.getLogger('fgt.sdl_init')
    sdlhints.set_hint(SDL_HINT_RENDER_DRIVER, 'software') # do not need no renderer
    sdlhints.set_hint(SDL_HINT_FRAMEBUFFER_ACCELERATION, '0') # do not need no window surface
    sdl.init(sdl.SDL_INIT_VIDEO | sdl.SDL_INIT_NOPARACHUTE)
    cflags = 0
    cmask = 0
    fwdcore = False # mesa doesn't support it :(
    if fwdcore:
        cflags |= SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG
        cmask |= SDL_GL_CONTEXT_PROFILE_CORE
    else:
        cmask |= SDL_GL_CONTEXT_PROFILE_COMPATIBILITY
    if gldebug:
        cflags |= SDL_GL_CONTEXT_DEBUG_FLAG
    
    gl_attrs = (
        (SDL_GL_RED_SIZE, "SDL_GL_RED_SIZE", 8),
        (SDL_GL_GREEN_SIZE, "SDL_GL_GREEN_SIZE", 8),
        (SDL_GL_BLUE_SIZE, "SDL_GL_BLUE_SIZE", 8),
        (SDL_GL_ALPHA_SIZE, "SDL_GL_ALPHA_SIZE", 8),
        (SDL_GL_DEPTH_SIZE, "SDL_GL_DEPTH_SIZE", 0),
        (SDL_GL_STENCIL_SIZE, "SDL_GL_STENCIL_SIZE", 0),
        (SDL_GL_DOUBLEBUFFER, "SDL_GL_DOUBLEBUFFER", 1),
        (SDL_GL_CONTEXT_MAJOR_VERSION, "SDL_GL_CONTEXT_MAJOR_VERSION", 3),
        (SDL_GL_CONTEXT_MINOR_VERSION, "SDL_GL_CONTEXT_MINOR_VERSION", 0),
        (SDL_GL_CONTEXT_PROFILE_MASK, "SDL_GL_CONTEXT_PROFILE_MASK", cmask),
        (SDL_GL_CONTEXT_FLAGS, "SDL_GL_CONTEXT_FLAGS", cflags),
    )

    for attr, name, val in gl_attrs:
        log.debug("requesting {} [{}] = {}".format(name, attr, val))
        sdlvideo.gl_set_attribute(attr, val)

    window = sdlvideo.create_window(title, SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, 
        size[0], size[1], SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE)
    if icon:
        sdlvideo.set_window_icon(window, icon)
    context = sdlvideo.gl_create_context(window)
    gldumplog("just after context", logger=log) # this catches PyOpenGL's try: glGetString() except: glGetStringiv() unsanity
    for attr, name, val in gl_attrs:
        got = sdlvideo.gl_get_attribute(attr)
        log.debug("{} requested {} got {}".format(name, val, got))
    
    try:
        log.info("glGet: vers = {}.{} flags={}  " .format(
            glGetInteger(GL_MAJOR_VERSION),
            glGetInteger(GL_MINOR_VERSION),
            glGetInteger(GL_CONTEXT_FLAGS)))
    except KeyError:
        pass

    if not fwdcore:
        glEnable(GL_POINT_SPRITE)

    glEnable(GL_VERTEX_PROGRAM_POINT_SIZE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_DEPTH_TEST)
    
    sdlttf.init()
    sdlimage.init()
    return window, context

def sdl_offscreen_init():
    """ init sdl core and the SDL_image lib (raw.py standalone run)"""
    sdl.init(0)
    sdlimage.init()

class rgba_surface(object):
    """ a plain RGBA32 surface w/o any blending on blits, hopefully.
        pixel ordering depends on endianness. lil': ABGR, big: RGBA
        
        when subclassing to change pixel format, note that data_ptr's
        expected format changes too.
    """
    sdl_pixel_fmt = sdlpixels.SDL_PIXELFORMAT_ABGR8888
    gl_unpack_alignment = 4
    gl_internal_fmt = GL_RGBA8
    gl_data_fmt = GL_RGBA
    gl_data_type = GL_UNSIGNED_BYTE
    
    def __init__(self, w = None, h = None, data_ptr = None, surface = None,
                    filename = None, filedata = None):
        self.do_free = True
        if filedata is not None:
            if type(filedata) is bytes:
                imagedata = bytearray(filedata)
            if type(filedata) is bytearray:
                rwops = sdlrwops.rw_from_mem(bar2voidp(filedata).value, len(filedata))
            elif hasattr(filedata, "seek"):
                rwops = sdlrwops.rw_from_object(filedata)
            else:
                raise TypeError("unusable data type {}", str(type(filedata)))
            self._surf = sdlimage.load_rw(rwops, 1)
        elif isinstance(filename, str):
            self._surf = sdlimage.load(filename)
        elif isinstance(w, int) and isinstance(h, int):
            masks = list(sdlpixels.pixelformat_enum_to_masks(self.sdl_pixel_fmt))
            bpp = masks.pop(0)
            if data_ptr is None:
                self._surf = sdlsurface.create_rgb_surface(w, h, bpp, *masks)
            else: # data_ptr == ABGR8888
                self._surf = sdlsurface.create_rgb_surface_from(data_ptr, w, h, bpp, w*4, *masks)
        elif isinstance(surface, SDL_Surface):
            self.do_free = False
            self._surf = surface
        else:
            raise TypeError("Crazy shit in parameters: ({} {} {} {} {})".format(type(w),
                    type(h), type(data_ptr), type(surface), type(filename)))
            
        sdlsurface.set_surface_blend_mode(self._surf, sdlvideo.SDL_BLENDMODE_NONE)

    def __str__(self):
        return "rgba_surface(size={}x{}, {}, do_free={})".format(self._surf._w, 
                self._surf._h, sdlpixels.get_pixelformat_name(self._surf.format.format), self.do_free)

    def hflip(self):
        pitch = self._surf._pitch
        pixels = ctypes.cast(self._surf._pixels, ctypes.c_void_p).value
        h = self._surf._h
        tmp_ba = bytearray(pitch*h)
        tmp = bar2voidp(tmp_ba).value
        sdlsurface.lock_surface(self._surf)
        ctypes.memmove(tmp, pixels, pitch*h)
        for y in range(self._surf._h):
            src = tmp + pitch * ( h - y - 1)
            dst = pixels + pitch * y
            ctypes.memmove(dst, src, pitch)
        sdlsurface.unlock_surface(self._surf)

    def write_bmp(self, filename):
        sdlsurface.save_bmp(self._surf, filename)

    def blit(self, src, dstrect, srcrect = None):
        """ ala pygame """
        if isinstance(src, SDL_Surface):
            src = rgba_surface(surface=src)           
        if len(dstrect) == 2:
            dstrect = SDL_Rect(dstrect[0], dstrect[1], src.w, src.h)
        else:
            dstrect = SDL_Rect(*dstrect)
        if srcrect is not None:
            srcrect = SDL_Rect(*srcrect)
        sdlsurface.blit_surface(src._surf, srcrect, self._surf, dstrect)

    def upload_tex2d(self, texture_name):
        assert self.pitch == 4 * self.w # muahahaha
        upload_tex2d(texture_name, self.gl_internal_fmt, self.w, self.h,
                self.gl_data_fmt, self.gl_data_type, self.pixels, GL_LINEAR)

    def fill(self, color):
        """ expects RGBA8888 4-tuple """
        color = sdlpixels.map_rgba(self._surf.format, *color)
        sdlsurface.fill_rect(self._surf, None, color)
    
    def get_size(self):
        return self._surf.size
    
    @property
    def pitch(self):
        return self._surf.pitch

    @property
    def size(self):
        return self._surf.size

    @property
    def pixels(self):
        return self._surf.pixels
    
    @property
    def w(self):
        return self._surf._w
    
    @property
    def h(self):
        return self._surf._h
    
    def free(self):
        if self.do_free:
            sdlsurface.free_surface(self._surf)
            self.do_free = False

    def __del__(self):
        if self.do_free:
            sdlsurface.free_surface(self._surf)
            
    def dump(self, fname):
        open(fname, "wb").write(ctypes.string_at(self.pixels, self.pitch*self.h))

def sdl_flip(window):
    sdlvideo.gl_swap_window(window)

def sdl_fini():
    sdlimage.quit()
    sdlttf.quit()
    sdl.quit()

def findafont(subnames = []):
    stuff = subprocess.check_output('fc-list : -f %{fullname}:%{style}:%{file}\n'.split(' '))
    leest = []
    for l in stuff.decode('utf-8').split("\n"):
        try:
            fam, style, path = l.split(':')
            leest.append((path, fam, style))
        except ValueError:
            pass
    for subname in subnames:
        for path, fam, style in leest:
            if 'italic' in style.lower() or 'oblique' in style.lower():
                continue
            if subname.lower() in fam.lower():
                return ( path, subname )
    raise Exception("no font found for '{}'".format(repr(subnames)))

def a_mono_font(pref = None, size = 23):
    monoes = ['ntu mono', 'vu sans mono', 'ion mono', 'reemono', 'bus mono', 'mono', ]
    if pref is None:
        pref = monoes
    elif ',' in pref:
        pref, size =  pref.split(',')
        size = int(size)
        pref = [ pref ] if pref else monoes
    else:
        pref = [ pref ]
    ttfname, unused = findafont(pref)
    return sdlttf.open_font(ttfname, size)




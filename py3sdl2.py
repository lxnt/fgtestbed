#!/usr/bin/python3.2
# -*- encoding: utf-8 -*-

# Python 3.2 / SDL2 /OpenGL 3.0 FC r&d

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

import os, os.path, sys, collections, struct, time, ctypes, logging
from collections import namedtuple
sys.path.append('/home/lxnt/00DFGL/sdlhg/prefix/lib/python3.2/site-packages/')

import pygame2
pygame2.set_dll_path('/home/lxnt/00DFGL/sdlhg/prefix/lib/')

import pygame2.sdl as sdl
import pygame2.sdl.events as sdlevents
import pygame2.sdl.mouse as sdlmouse
import pygame2.sdl.video as sdlvideo
import pygame2.sdl.surface as sdlsurface
import pygame2.sdl.pixels as sdlpixels

from pygame2.sdl.keycode import *
from pygame2.sdl.pixels import SDL_Color
from pygame2.sdl.rect import SDL_Rect
from pygame2.sdl.video import SDL_Surface

import pygame2.ttf as ttf
import pygame2.image as image

import OpenGL
OpenGL.FORWARD_COMPATIBLE_ONLY = True
#OpenGL.FULL_LOGGING = True
from OpenGL.GL import *
from OpenGL.GL.shaders import *
from OpenGL.GLU import *
from OpenGL.GL.ARB import shader_objects
from OpenGL.GL.ARB.texture_rg import *
from OpenGL.GL.ARB.framebuffer_object import *
from OpenGL.GL.ARB.debug_output import *

from OpenGL.error import GLError

from glname import glname as glname
from sdlenums import *

ctypes.pythonapi.PyByteArray_AsString.restype = ctypes.c_void_p

def bar2voidp(bar):
    return ctypes.c_void_p(ctypes.pythonapi.PyByteArray_AsString(id(bar)))

__all__ = """sdl_init sdl_flip sdl_offscreen_init
rgba_surface 
glinfo upload_tex2d upload_tex2da gldump
Shader0 VAO0
HudTextPanel Hud
GridVAO DumbGridShader
Rect Coord2 Coord3 Size2 Size3 GLColor
FBO EmaFilter""".split()

Coord2 = namedtuple('Coord2', 'x y')
Coord3 = namedtuple('Coord3', 'x y z')
Rect = namedtuple('Rect', 'x y w h')
Size2 = namedtuple('Size2', 'w h')
Size3 = namedtuple('Size3', 'w h d')
GLColor = namedtuple('GLColor', 'r g b a')
VertexAttr = namedtuple('VertexAttr', 'index size type stride offset')
def upload_tex2d(txid, informat, tw, th, dformat, dtype, dptr):
    glBindTexture(GL_TEXTURE_2D, txid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, informat, tw, th, 0, dformat, dtype, dptr)
    glBindTexture(GL_TEXTURE_2D, 0)

def upload_tex2da(txid, informat, tw, th, td, dformat, dtype, dptr):
    glBindTexture(GL_TEXTURE_2D_ARRAY,  txid)
    glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, informat, tw, th, td, 0, dformat, dtype, dptr)   
    
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
    def __init__(self, sname=None, loud=False, sdir = 'shaders'):
        self.loud = loud
        self.aloc = { b'position': 0 }
        self.uloc = collections.defaultdict(lambda:-1)
        if sname is None:
            sname = self.sname
        vsfn = os.path.join(sdir, sname) + '.vs'
        fsfn = os.path.join(sdir, sname) + '.fs'
        vsp = self._compile(open(vsfn, encoding='utf-8').readlines(), GL_VERTEX_SHADER, vsfn)
        fsp = self._compile(open(fsfn, encoding='utf-8').readlines(), GL_FRAGMENT_SHADER, fsfn)
        if not (vsp and fsp):
            raise SystemExit
        
        program = glCreateProgram()

        for shader in (vsp, fsp):
            glAttachShader(program, shader)
            glDeleteShader(shader)
            
        for name, loc in self.aloc.items():
            glBindAttribLocation(program, loc, name)
            if self.loud:
                print("  vao{0}: name={1}".format(loc, name))
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
            name, wtf, typ = shader_objects.glGetActiveUniformARB(program, i)
            loc = glGetUniformLocation(program, name)
            self.uloc[name] = loc
            if self.loud:
                print("  uni{0}: name={1} type={2} loc={3}".format(i, name, glname.get(typ, typ), loc))
        
        self.program = program

    def __call__(self):
        raise NotImplemented
    
    def _compile(self, lines, stype, filename):
        rv = glCreateShader(stype)
        glShaderSource(rv, lines)
        glCompileShader(rv)
        result = glGetShaderiv(rv, GL_COMPILE_STATUS)
        nfo = glGetShaderInfoLog(rv)
        print("compiling {}: result={}; nfo:\n{}".format(filename, result, nfo.strip()))
        return rv
    
    def validate(self):
        glValidateProgram(self.program)
        validation = glGetProgramiv( self.program, GL_VALIDATE_STATUS )
        if validation == GL_FALSE:
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
            self._data[offs:offs + self._data_type.size] = self._data_type.pack(*d)
            i += 1

        data_ptr = bar2voidp(self._data)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_name)
        if grew:
            glBufferData(GL_ARRAY_BUFFER, data_size, data_ptr, GL_DYNAMIC_DRAW)
            self._create()
        else:
            glBufferSubData(GL_ARRAY_BUFFER, 0, data_size, data_ptr)

    def fini(self):
        glDeleteVertexArrays(1, self._vao_name)
        self._vbo = None

class DumbGridShader(Shader0):
    sname = "dumb"
    def __call__(self, grid_size, pszar, **kwargs):
        glUseProgram(self.program)
        glUniform3f(self.uloc[b'pszar'], *pszar)
        glUniform2i(self.uloc[b'grid'], *grid_size)

class GridVAO(VAO0):
    _primitive_type = GL_POINTS
    _data_type = struct.Struct('II')
    _attrs = (VertexAttr( 0, 2, GL_INT, 0, 0 ),)

    def resize(self, size):
        w, h = self.size = size
        self.update(iter( (i%w, i//w) for i in range(w*h) ), w*h)

    def __str__(self):
        return "GridVAO(size={} num={})".format(self.size, self._count)

class Grid(object):
    """ dumb state container atm """
    def __init__(self, size, pszar, loud):
        self.shader = DumbGridShader(loud=loud)
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
    def __init__(self, font, strs, longest_str = None):
        self.fg = GLColor(1, 1, 1, 1)
        self.bg = GLColor(0, 0, 0, 0.68)
        self._texture_name = glGenTextures(1)
        self.font = font
        self.padding = 8
        self.margin = 8 
        self.strings = strs
        if longest_str is None:
            longest_str_px = 0
            for s in strs:
                sz = ttf.size(self.font, s)[0]
                if sz > longest_str_px:
                   longest_str_px = sz
        else:
            longest_str_px = ttf.size(self.font, longest_str)[0]
        width = 2*self.padding + longest_str_px
        self.ystep = ttf.font_line_skip(self.font)
        height = 2*self.padding + self.ystep * len(strs)
        self.surface = rgba_surface(width, height)
        self._surface_dirty = True
        self.active = True
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
        self.surface.fill((0,0,0,0xff))
        i = 0
        dump = False
        for s in self.strings:
            if len(s) > 0:
                if isinstance(self.data, dict):
                    s = s.format(**self.data)
                strsurf = ttf.render_blended(self.font, s, SDL_Color())
#                print(s, strsurf._w, strsurf._h)
                if dump:
                    rgba_surface(strsurf).dump("a/strsurf")
                    self.surface.dump("a/before-blit")
                
                self.surface.blit(strsurf, (self.padding, self.padding + i * self.ystep))
                sdlsurface.free_surface(strsurf)
                
                if dump:
                    self.surface.dump("a/after-blit")
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
        if size is not None:
            self.resize(size)
        
    def resize(self, size):
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
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glDeleteRenderbuffers(1, [self.fb_name])
        glDeleteFramebuffers(1, [self.rb_name])

class EmaFilter(object):
    """ http://en.wikipedia.org/wiki/Exponential_moving_average 

        used here for the FPS counters. seed of 16 corresponds
        to approximately 60 fps if we're talking microseconds.
        
        alpha of 0.01 is completely arbitrary, see the wikipedia article.
        
        usage: supply whatever time it took to render previous frame
        to the value() method and it'll return a filtered value.
        
        filtered fps = 1.0 / filtered value
        
        todo: convert this into a generator.
    """
    def __init__(self, alpha = 0.01, seed = 16):
        self.alpha = alpha
        self._value = seed
    
    def value(self, val):
        self._value = self.alpha*val + (1-self.alpha)*self._value
        return self._value
    

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
#        (    3, GL_MAX_TEXTURE_COORDS, "GL_MAX_TEXTURE_COORDS" ), # 1 texture_coord = 4 varying_floats?
#        (   -4, GL_POINT_SIZE_MIN, "GL_POINT_SIZE_MIN" ),
#        (   32, GL_POINT_SIZE_MAX, "GL_POINT_SIZE_MAX" ),
        (    2, GL_MAX_VERTEX_ATTRIBS, "GL_MAX_VERTEX_ATTRIBS" ), 
#        (    2, GL_MAX_VERTEX_UNIFORM_BLOCKS, "GL_MAX_VERTEX_UNIFORM_BLOCKS" ),
    ]

    if False:
        exts = []
        for i in range(glGetInteger(GL_NUM_EXTENSIONS)):
            exts.append(glGetStringi(GL_EXTENSIONS, i))
        print("\n".join(map(str,exts)))
        
    for e,s in strs.items():
        print("{0}: {1}".format(s, glGetString(e)))
        
    for t in ints:
        try:
            p = glGetInteger(t[1])
            if (p<t[0]) or ((t[0]<0) and (p+t[0] >0)):
                w = "** "
            else:
                w = ""
            print("{0}: {1}".format(t[2], p, abs(t[0]), w))
        except GLError as e:
            if e.err != 1280:
                raise
            print("{0}: {1}".format(t[2], "invalid enumerant"))

def glcalltrace(s):
    s = "{0} {1} {0}".format("*" * 16, s)
    logging.getLogger('OpenGL.calltrace' ).info(s)
def sdl_init(size=(1280, 800), title = "DFFG testbed", icon = None):
    sdl.init(sdl.SDL_INIT_VIDEO)
    posn = (sdlvideo.SDL_WINDOWPOS_UNDEFINED_DISPLAY, sdlvideo.SDL_WINDOWPOS_UNDEFINED_DISPLAY)
    posn = (0, 0)
    
    sdlvideo.gl_set_attribute(SDL_GL_RED_SIZE, 8)
    sdlvideo.gl_set_attribute(SDL_GL_GREEN_SIZE, 8)
    sdlvideo.gl_set_attribute(SDL_GL_BLUE_SIZE, 8)
    sdlvideo.gl_set_attribute(SDL_GL_ALPHA_SIZE, 8)
    #sdlvideo.gl_set_attribute(SDL_GL_BUFFER_SIZE, 32)
    #sdlvideo.gl_set_attribute(SDL_GL_DEPTH_SIZE, 0)
    #sdlvideo.gl_set_attribute(SDL_GL_STENCIL_SIZE, 0)
    
    sdlvideo.gl_set_attribute(SDL_GL_DOUBLEBUFFER, 1)
    sdlvideo.gl_set_attribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    sdlvideo.gl_set_attribute(SDL_GL_CONTEXT_MINOR_VERSION, 0)

    sdlvideo.gl_set_attribute(SDL_GL_CONTEXT_FLAGS, 
        SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG | SDL_GL_CONTEXT_DEBUG_FLAG)
    sdlvideo.gl_set_attribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE)

    window = sdlvideo.create_window(title, posn[0], posn[1], size[0], size[1], 
        SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE)
    if icon:
        sdlvideo.set_window_icon(window, icon)
    context = sdlvideo.gl_create_context(window)
    
    gldump(ignore=True) # SDL's SDL_GL_ExtesionSupported vs forward-compatible context
    glEnable(GL_VERTEX_PROGRAM_POINT_SIZE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_DEPTH_TEST)
    
    ttf.init()
    image.init()
    return window, context

def gldump(s=None, ignore=False):
    if s:
        print("gldump({})".format(s))
    count = 256
    logSize = 1048576
    sources = arrays.GLuintArray.zeros((count, ))
    types = arrays.GLuintArray.zeros((count, ))
    ids = arrays.GLuintArray.zeros((count, ))
    severities = arrays.GLuintArray.zeros((count, ))
    lengths = arrays.GLsizeiArray.zeros((count, ))
    messageLog = arrays.GLcharArray.zeros((logSize, ))
    
    num = glGetDebugMessageLogARB(count, logSize, sources, types, ids, severities, lengths, messageLog)
    if ignore:
        return
    offs = 0
    for n in range(num):
        msg = bytes(messageLog[offs:offs+lengths[n]]).decode('utf-8')
        print(glname.get(sources[n], sources[n]),
            glname.get(types[n], types[n]),
            glname.get(ids[n], ids[n]),
            glname.get(severities[n], severities[n]),
            msg)
        offs += lengths[n]

    
    
def sdl_offscreen_init():
    """ just init sdl core and the SDL_image lib (raw.py standalone run)"""
    sdl.init(0)
    image.init()

class rgba_surface(object):
    """ a plain RGBA32 surface w/o any blending on blits """
    def __init__(self, w = None, h = None):
        if isinstance(w, SDL_Surface):
            assert h is None
            self._surf = w
            self.do_free = False
        else:
            assert isinstance(w, int) and isinstance(h, int)
            self._surf = sdlsurface.create_rgb_surface(w, h,
                *sdlpixels.pixelformat_enum_to_masks(sdlpixels.SDL_PIXELFORMAT_RGBA8888))
            self.do_free = True
        # SDLBUG. Somehow, ARGB->RGBA blit gets treated as RGBA->RGBA
        # if blend_mode is none.
        #sdlsurface.set_surface_blend_mode(self._surf, sdlvideo.SDL_BLENDMODE_NONE)
    
    def blit(self, src, dstrect, srcrect = None):
        """ ala pygame """
        if isinstance(src, SDL_Surface):
            src = rgba_surface(src)
            
        if len(dstrect) == 2:
            dstrect = SDL_Rect(dstrect[0], dstrect[1], src.w, src.h)
        else:
            dstrect = SDL_Rect(*dstrect)
            
        if srcrect is not None:
            srcrect = SDL_Rect(*srcrect)
        #print("blit from {} to {}".format(sdlpixels.get_pixelformat_name(src._surf.format.format), 
        #    sdlpixels.get_pixelformat_name(self._surf.format.format)))
        sdlsurface.blit_surface(src._surf, srcrect, self._surf, dstrect)

    def upload_tex2d(self, texture_name):
        assert self.pitch == 4 * self.w # muahahaha
        upload_tex2d(texture_name, GL_RGBA8, self.w, self.h,
                GL_RGBA, GL_UNSIGNED_BYTE, self.pixels)

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
    
    def __del__(self):
        if self.do_free:
            sdlsurface.free_surface(self._surf)
            
    def dump(self, fname):
        open(fname, "wb").write(ctypes.string_at(self.pixels, self.pitch*self.h))

def sdl_flip(window):
    sdlvideo.gl_swap_window(window)

def sdl_fini():
    image.quit()
    ttf.quit()
    sdl.quit()

def loop(window, bg_color, fbo_color, grid, hud, panels):
    fbo = FBO(Size2(window._w, window._h))
    while True:
        while True:
            event = sdlevents.poll_event(True)
            if event is None:
                break
            elif event.type == sdlevents.SDL_QUIT:
                return
            elif event.type == sdlevents.SDL_KEYUP:
                if event.key.keysym.sym == SDLK_ESCAPE:
                    return
            elif event.type == sdlevents.SDL_WINDOWEVENT:
                if event.window.event == sdlvideo.SDL_WINDOWEVENT_RESIZED:
                    sz = Size2(event.window.data1, event.window.data2)
                    fbo.resize(sz)
                    grid.reshape(sz)
                    hud.reshape(sz)
            elif event.type == sdlevents.SDL_MOUSEBUTTONDOWN:
                if event.button.button == sdlmouse.SDL_BUTTON_LEFT and event.button.state == sdlevents.SDL_PRESSED:
                    for s in stuff:
                        s.click((event.button.x, event.button.y))
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
        #gldump()
        time.sleep(0.5)

def main():
    psize = int(sys.argv[1]) if len(sys.argv) > 1 else 128
    pszar_x = 0.8
    pszar_y = 1.0
    bg_color = ( 0,1,0,1 )
    fbo_color = ( 1,0,0,1 )
    
    window, context = sdl_init()
    glinfo()
        
    grid_w = int(window._w // (pszar_x*psize))
    grid_h = int(window._h // (pszar_y*psize))
    print("grid {}x{} psize {}x{}".format(grid_w, grid_h, pszar_x*psize, pszar_y*psize))
    grid = Grid(size = (grid_w, grid_h), pszar = (pszar_x, pszar_y, psize), loud = ['gl'])
    hud = Hud()

    font = ttf.open_font(b"/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-R.ttf", 38)
    panels = []
    panels.append(HudTextPanel(font, [ "Yokarny Babai" ]))
    panels[0].moveto(Coord2(100, 400))
    panels.append(HudTextPanel(font, [ "Skoromorkovka" ]))
    panels[1].moveto(Coord2(400, 100))
    hud.reshape(Size2(window._w, window._h))
    loop(window, bg_color, fbo_color, grid, hud, panels)
    sdl_fini()
    return 0

if __name__ == "__main__":
    sys.exit(main())

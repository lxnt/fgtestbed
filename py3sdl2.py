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

import os, sys, collections, struct, time
sys.path.append('/home/lxnt/00DFGL/sdlhg/prefix/lib/python3.2/site-packages/')

import pygame2
pygame2.set_dll_path('/home/lxnt/00DFGL/sdlhg/prefix/lib/')

import pygame2.sdl as sdl
import pygame2.sdl.events as sdlevents
import pygame2.sdl.mouse as sdlmouse
import pygame2.sdl.video as sdlvideo
import pygame2.sdl.surface as sdlsurface
from pygame2.sdl.keycode import *
from pygame2.sdl.pixels import SDL_Color
from pygame2.sdl.rect import SDL_Rect

import pygame2.ttf as ttf

from OpenGL.GL import *
from OpenGL.arrays import vbo
from OpenGL.GL.shaders import *
from OpenGL.GLU import *
from OpenGL.GL.ARB import shader_objects
from OpenGL.GL.ARB.texture_rg import *
from OpenGL.GL.ARB.framebuffer_object import *
from OpenGL.error import GLError

from glname import glname as glname
"""
umm crap. is it 'shader.draw(vao) or vao.draw(shader) ?

"""
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
    def __init__(self, vs_fname, fs_fname, loud=False):
        self.loud = loud
        self.aloc = { b'position': 0 }
        self.uloc = collections.defaultdict(lambda:-1)

        vsp = self._compile(open(vs_fname, encoding='utf-8').readlines(), GL_VERTEX_SHADER, vs_fname)
        fsp = self._compile(open(fs_fname, encoding='utf-8').readlines(), GL_FRAGMENT_SHADER, fs_fname)
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

    def __init__(self):
        self._vao_name = glGenVertexArrays(1)
        self._vbo = None
        self._num = None
        
    def __len__(self):
        return self._num
    
    def __call__(self):
        glBindVertexArray(self._vao_name) # use it
        glDrawArrays(self._primitive_type, 0, len(self))        

    def update_vbo(self, dtype, data, num = None):
        N = self._num = len(data) if num is None else num

        dt = struct.Struct(dtype)
        barr = bytearray(N*dt.size)
        i = 0
        for d in data:
            offs = i * dt.size
            barr[offs:offs + dt.size] = dt.pack(*d)
            i += 1
        
        if self._vbo is None:
            glBindVertexArray(self._vao_name) # modify it
            self._vbo = vbo.VBO(bytes(barr), usage=GL_STATIC_DRAW)
            self._vbo.bind()
            self.set_va_ptrs()
            glBindVertexArray(0) # guard against stray modifications
        else:
            self._vbo.set_array(bytes(barr))
    
    def set_va_ptrs():
        raise NotImplemented

    def fini(self):
        glDeleteVertexArrays(1, self._vao_name)
        self._vbo = None

class GridShader(Shader0):
    def __call__(self, grid_size, pszar):
        glUseProgram(self.program)
        glUniform3f(self.uloc[b'pszar'], *pszar)
        glUniform2i(self.uloc[b'grid'], *grid_size)

class GridVAO(VAO0):
    _primitive_type = GL_POINTS

    def __init__(self, sz):
        super(GridVAO, self).__init__()
        self.update(sz)
        
    def update(self, sz):
        w, h = self.size = sz
        self.update_vbo("II", iter( (i%w, i//w) for i in range(w*h) ), w*h)

    def set_va_ptrs(self):
        glEnableVertexAttribArray(0) # make sure this attr is enabled
        glVertexAttribIPointer(0, 2, GL_INT, 0, self._vbo) # bind data to the position
        

class Grid(object):
    """ dumb state container atm """
    def __init__(self, shader, sz, pszar):
        self.shader = shader
        self.vao = GridVAO(sz) 
        self.pszar = pszar
        
    def render(self):
        self.shader(self.vao.size, self.pszar)
        self.vao()
        
    def reshape(self, sz):
        glViewport(0, 0, sz[0], sz[1])
        
    def click(self, at):
        pass

class HudVAO(VAO0):
    """ a quad -> TRIANGLE_STRIP """
    _primitive_type = GL_TRIANGLE_STRIP
    
    def update(self, a_rect):
        """ a_rect: tuple(x, y, w, h) """
        cps = ( 
            ( a_rect[0],             a_rect[1],             0, 1 ),
            ( a_rect[0],             a_rect[1] + a_rect[3], 0, 0 ),
            ( a_rect[0] + a_rect[2], a_rect[1],             1, 1 ),
            ( a_rect[0] + a_rect[2], a_rect[1] + a_rect[3], 1, 0 ))
        
        self.update_vbo("IIII", cps)

    def set_va_ptrs(self):
        glEnableVertexAttribArray(0) # make sure this attr is enabled
        glVertexAttribIPointer(0, 4, GL_INT, 0, self._vbo) # bind data to it

class HudShader(Shader0):
    """ draws a tinted translucent overlay at given coords. 
    
        Future development might be in direction of drawing 
        all the hud shit in one pass using, maybe, a 2darray 
        texture or something. Currently it's one-by-one.
    """
    def __call__(self, screen_rect, texture_name):
        """ *_rect : tuple(x, y, w, h)
            texture_name - off glGenTextures() """
        glUseProgram(self.program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, texture_name)
        glUniform1i(self.uloc[b"hudtex"], 0)
        glUniform2i(self.uloc[b"resolution"], *screen_rect[2:])
        glUniform4f(self.uloc[b"fg"], 1.0, 1.0, 1.0, 1.0)
        glUniform4f(self.uloc[b"bg"], 0.0, 0.0, 0.0, 0.68)

class HudPanel(object):
    def __init__(self, font, strs, longest_str = None):
        self.fg = SDL_Color( 0xffffffff )
        self.bg = 0xff
        
        self.texture_name = glGenTextures(1)
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
        self.width = 2*self.padding + longest_str_px
        self.ystep = ttf.font_line_skip(self.font)
        self.height = 2*self.padding + self.ystep * len(strs)
        self.surface = sdlsurface.create_rgb_surface(
            self.width, self.height, 32, 0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF)

    def update(self, data = None):
        sdlsurface.fill_rect(self.surface, None, self.bg)
        i = 0
        for s in self.strings:
            if isinstance(data, dict):
                s = s.format(**data)
            srcrect = None
            dstrect = SDL_Rect(self.padding, self.padding + i * self.ystep)
            strsurf = ttf.render_blended(self.font, s, self.fg)
            sdlsurface.blit_surface(strsurf, srcrect, self.surface, dstrect)
            sdlsurface.free_surface(strsurf)
            i += 1

        glBindTexture(GL_TEXTURE_2D, self.texture_name)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        
        assert self.surface.pitch == 4 * self.width # muahahaha

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.width, self.height, 
            0, GL_RGBA, GL_UNSIGNED_BYTE, self.surface.pixels)

        glBindTexture(GL_TEXTURE_2D, 0)

    def fini(self):
        glDeleteTextures(self.texture_name)
        sdlsurface.free_surface(self.surface)

class Hud(object):
    def __init__(self, shader, w, h):
        self.shader = shader
        self.reshape((w, h))
        self.panels = []
        self._vao = HudVAO()

    def addpanel(self, panel, alignment):
        self.panels.append((panel, alignment))

    def render(self):
        for p, a  in self.panels:
            p.update()
            self._vao.update((a[0], a[1], p.width, p.height))
            self.shader(self.screen_rect, p.texture_name)
            self._vao()
        
    def reshape(self, sz):
        w, h = sz
        self.screen_rect = (0, 0, w, h)
        
    def click(self, at):
        x, y = at

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
        (   -4, GL_POINT_SIZE_MIN, "GL_POINT_SIZE_MIN" ),
        (   32, GL_POINT_SIZE_MAX, "GL_POINT_SIZE_MAX" ),
        (    2, GL_MAX_VERTEX_ATTRIBS, "GL_MAX_VERTEX_ATTRIBS" ), 
        #( 2048, GL_MAX_RECTANGLE_TEXTURE_SIZE, "GL_MAX_RECTANGLE_TEXTURE_SIZE" ),
    ]
    try:
        exts = glGetString(GL_EXTENSIONS).split()
    except GLError as e:
        if e.err != 1280:
            raise
        exts = []
        for i in range(glGetInteger(GL_NUM_EXTENSIONS)):
            exts.append(glGetStringi(GL_EXTENSIONS, i))
        
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

def sdl_init():
    sdl.init(sdl.SDL_INIT_VIDEO)
    posn = (sdlvideo.SDL_WINDOWPOS_UNDEFINED_DISPLAY, sdlvideo.SDL_WINDOWPOS_UNDEFINED_DISPLAY)
    posn = (0, 0)
    size = (1280, 800)
    
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_RED_SIZE, 8)
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_GREEN_SIZE, 8)
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_BLUE_SIZE, 8)
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_ALPHA_SIZE, 8)
    #sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_BUFFER_SIZE, 32)
    #sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_DEPTH_SIZE, 0)
    #sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_STENCIL_SIZE, 0)
    
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_DOUBLEBUFFER, 1)
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_CONTEXT_MINOR_VERSION, 0)

    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_CONTEXT_FLAGS, sdlvideo.SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG) #SDL_GL_CONTEXT_DEBUG_FLAG)
    sdlvideo.gl_set_attribute(sdlvideo.SDL_GL_CONTEXT_PROFILE_MASK, sdlvideo.SDL_GL_CONTEXT_PROFILE_CORE)

    window = sdlvideo.create_window("glcontexest", posn[0], posn[1], size[0], size[1], 
        sdlvideo.SDL_WINDOW_OPENGL | sdlvideo.SDL_WINDOW_RESIZABLE)
    context = sdlvideo.gl_create_context(window)
    glEnable(GL_VERTEX_PROGRAM_POINT_SIZE)       
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_DEPTH_TEST)
    
    ttf.init()
    return window, context

def sdl_fini():
    ttf.quit()
    sdl.quit()

def render(bg_color, stuff):
    glClearColor(*bg_color)
    glClear(GL_COLOR_BUFFER_BIT)
    for s in stuff:
        s.render()

def loop(window, bg_color, stuff):
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
                    for s in stuff:
                        s.reshape((event.window.data1, event.window.data2))
            elif event.type == sdlevents.SDL_MOUSEBUTTONDOWN:
                if event.button.button == sdlmouse.SDL_BUTTON_LEFT and event.button.state == sdlevents.SDL_PRESSED:
                    for s in stuff:
                        s.click((event.button.x, event.button.y))
        render(bg_color, stuff)
        sdlvideo.gl_swap_window(window)
        time.sleep(0.1)

def main():
    psize = int(sys.argv[1]) if len(sys.argv) > 1 else 128
    bg_color = ( 0.23, 0.42, 0.08, 1 )
    
    window, context = sdl_init()
    glinfo()
    
    grid_shader = GridShader("py3sdl2.vs", "py3sdl2.fs", loud = True)
    grid = Grid(grid_shader, sz = (2, 2), pszar = (1.0, 1.0, psize))
    
    hud_shader = HudShader("hud.vs", "hud.fs", loud = True)
    hud = Hud(hud_shader, window._w, window._h)

    font = ttf.open_font(b"/usr/share/fonts/truetype/ubuntu-font-family/UbuntuMono-R.ttf", 38)
    p = HudPanel(font, [ "Yokarny Babai" ])
    hud.addpanel(p, (100, 100))
    
    loop(window, bg_color, [grid, hud])
    sdl_fini()
    return 0

if __name__ == "__main__":
    sys.exit(main())

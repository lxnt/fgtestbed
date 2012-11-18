# -*- encoding: utf-8 -*-
from pygame2.sdl.power import SDL_POWERSTATE_UNKNOWN    
from pygame2.sdl.power import SDL_POWERSTATE_ON_BATTERY 
from pygame2.sdl.power import SDL_POWERSTATE_NO_BATTERY 
from pygame2.sdl.power import SDL_POWERSTATE_CHARGING   
from pygame2.sdl.power import SDL_POWERSTATE_CHARGED    
from pygame2.sdl.audio import SDL_AUDIO_MASK_BITSIZE 
from pygame2.sdl.audio import SDL_AUDIO_MASK_DATATYPE 
from pygame2.sdl.audio import SDL_AUDIO_MASK_ENDIAN 
from pygame2.sdl.audio import SDL_AUDIO_MASK_SIGNED 
from pygame2.sdl.audio import SDL_AUDIO_ALLOW_FREQUENCY_CHANGE 
from pygame2.sdl.audio import SDL_AUDIO_ALLOW_FORMAT_CHANGE    
from pygame2.sdl.audio import SDL_AUDIO_ALLOW_CHANNELS_CHANGE  
from pygame2.sdl.audio import SDL_AUDIO_ALLOW_ANY_CHANGE       
from pygame2.sdl.audio import SDL_AUDIO_STOPPED 
from pygame2.sdl.audio import SDL_AUDIO_PLAYING 
from pygame2.sdl.audio import SDL_AUDIO_PAUSED  
from pygame2.sdl.audio import SDL_MIX_MAXVOLUME 
from pygame2.sdl.surface import SDL_SWSURFACE 
from pygame2.sdl.surface import SDL_PREALLOC  
from pygame2.sdl.surface import SDL_RLEACCEL  
from pygame2.sdl.surface import SDL_DONTFREE  
from pygame2.sdl.log import SDL_LOG_CATEGORY_APPLICATION 
from pygame2.sdl.log import SDL_LOG_CATEGORY_ERROR       
from pygame2.sdl.log import SDL_LOG_CATEGORY_SYSTEM      
from pygame2.sdl.log import SDL_LOG_CATEGORY_AUDIO       
from pygame2.sdl.log import SDL_LOG_CATEGORY_VIDEO       
from pygame2.sdl.log import SDL_LOG_CATEGORY_RENDER      
from pygame2.sdl.log import SDL_LOG_CATEGORY_INPUT       
from pygame2.sdl.log import SDL_LOG_CATEGORY_CUSTOM      
from pygame2.sdl.log import SDL_LOG_PRIORITY_VERBOSE  
from pygame2.sdl.log import SDL_LOG_PRIORITY_DEBUG    
from pygame2.sdl.log import SDL_LOG_PRIORITY_INFO     
from pygame2.sdl.log import SDL_LOG_PRIORITY_WARN     
from pygame2.sdl.log import SDL_LOG_PRIORITY_ERROR    
from pygame2.sdl.log import SDL_LOG_PRIORITY_CRITICAL 
from pygame2.sdl.shape import SDL_NONSHAPEABLE_WINDOW    
from pygame2.sdl.shape import SDL_INVALID_SHAPE_ARGUMENT 
from pygame2.sdl.shape import SDL_WINDOW_LACKS_SHAPE     
from pygame2.sdl.hints import SDL_HINT_DEFAULT  
from pygame2.sdl.hints import SDL_HINT_NORMAL   
from pygame2.sdl.hints import SDL_HINT_OVERRIDE 
from pygame2.sdl.hints import SDL_HINT_FRAMEBUFFER_ACCELERATION 
from pygame2.sdl.hints import SDL_HINT_IDLE_TIMER_DISABLED      
from pygame2.sdl.hints import SDL_HINT_ORIENTATIONS             
from pygame2.sdl.hints import SDL_HINT_RENDER_DRIVER            
from pygame2.sdl.hints import SDL_HINT_RENDER_OPENGL_SHADERS    
from pygame2.sdl.hints import SDL_HINT_RENDER_SCALE_QUALITY     
from pygame2.sdl.hints import SDL_HINT_RENDER_VSYNC             
from pygame2.sdl.events import SDL_RELEASED 
from pygame2.sdl.events import SDL_PRESSED  
from pygame2.sdl.events import SDL_FIRSTEVENT          
from pygame2.sdl.events import SDL_QUIT                
from pygame2.sdl.events import SDL_WINDOWEVENT         
from pygame2.sdl.events import SDL_SYSWMEVENT          
from pygame2.sdl.events import SDL_KEYDOWN             
from pygame2.sdl.events import SDL_KEYUP               
from pygame2.sdl.events import SDL_TEXTEDITING         
from pygame2.sdl.events import SDL_TEXTINPUT           
from pygame2.sdl.events import SDL_MOUSEMOTION         
from pygame2.sdl.events import SDL_MOUSEBUTTONDOWN     
from pygame2.sdl.events import SDL_MOUSEBUTTONUP       
from pygame2.sdl.events import SDL_MOUSEWHEEL          
from pygame2.sdl.events import SDL_INPUTMOTION         
from pygame2.sdl.events import SDL_INPUTBUTTONDOWN     
from pygame2.sdl.events import SDL_INPUTBUTTONUP       
from pygame2.sdl.events import SDL_INPUTWHEEL          
from pygame2.sdl.events import SDL_INPUTPROXIMITYIN    
from pygame2.sdl.events import SDL_INPUTPROXIMITYOUT   
from pygame2.sdl.events import SDL_JOYAXISMOTION       
from pygame2.sdl.events import SDL_JOYBALLMOTION       
from pygame2.sdl.events import SDL_JOYHATMOTION        
from pygame2.sdl.events import SDL_JOYBUTTONDOWN       
from pygame2.sdl.events import SDL_JOYBUTTONUP         
from pygame2.sdl.events import SDL_FINGERDOWN          
from pygame2.sdl.events import SDL_FINGERUP            
from pygame2.sdl.events import SDL_FINGERMOTION        
from pygame2.sdl.events import SDL_TOUCHBUTTONDOWN     
from pygame2.sdl.events import SDL_TOUCHBUTTONUP       
from pygame2.sdl.events import SDL_DOLLARGESTURE       
from pygame2.sdl.events import SDL_DOLLARRECORD        
from pygame2.sdl.events import SDL_MULTIGESTURE        
from pygame2.sdl.events import SDL_CLIPBOARDUPDATE     
from pygame2.sdl.events import SDL_DROPFILE            
from pygame2.sdl.events import SDL_USEREVENT           
from pygame2.sdl.events import SDL_LASTEVENT           
from pygame2.sdl.events import SDL_TEXTEDITINGEVENT_TEXT_SIZE 
from pygame2.sdl.events import SDL_TEXTINPUTEVENT_TEXT_SIZE   
from pygame2.sdl.events import SDL_ADDEVENT  
from pygame2.sdl.events import SDL_PEEKEVENT 
from pygame2.sdl.events import SDL_GETEVENT  
from pygame2.sdl.events import SDL_QUERY   
from pygame2.sdl.events import SDL_IGNORE  
from pygame2.sdl.events import SDL_DISABLE 
from pygame2.sdl.events import SDL_ENABLE  
from pygame2.sdl import SDL_INIT_TIMER 
from pygame2.sdl import SDL_INIT_AUDIO 
from pygame2.sdl import SDL_INIT_VIDEO 
from pygame2.sdl import SDL_INIT_JOYSTICK 
from pygame2.sdl import SDL_INIT_HAPTIC 
from pygame2.sdl import SDL_INIT_NOPARACHUTE 
from pygame2.sdl import SDL_INIT_EVERYTHING 
from pygame2.sdl import SDL_FALSE 
from pygame2.sdl import SDL_TRUE 
from pygame2.sdl.mouse import SDL_BUTTON_LEFT   
from pygame2.sdl.mouse import SDL_BUTTON_MIDDLE 
from pygame2.sdl.mouse import SDL_BUTTON_RIGHT  
from pygame2.sdl.mouse import SDL_BUTTON_X1     
from pygame2.sdl.mouse import SDL_BUTTON_X2     
from pygame2.sdl.mouse import SDL_BUTTON_LMASK  
from pygame2.sdl.mouse import SDL_BUTTON_MMASK  
from pygame2.sdl.mouse import SDL_BUTTON_RMASK  
from pygame2.sdl.mouse import SDL_BUTTON_X1MASK 
from pygame2.sdl.mouse import SDL_BUTTON_X2MASK 
from pygame2.sdl.joystick import SDL_HAT_CENTERED  
from pygame2.sdl.joystick import SDL_HAT_UP        
from pygame2.sdl.joystick import SDL_HAT_RIGHT     
from pygame2.sdl.joystick import SDL_HAT_DOWN      
from pygame2.sdl.joystick import SDL_HAT_LEFT      
from pygame2.sdl.joystick import SDL_HAT_RIGHTUP   
from pygame2.sdl.joystick import SDL_HAT_RIGHTDOWN 
from pygame2.sdl.joystick import SDL_HAT_LEFTUP    
from pygame2.sdl.joystick import SDL_HAT_LEFTDOWN  
from pygame2.sdl.video import SDL_BLENDMODE_NONE  
from pygame2.sdl.video import SDL_BLENDMODE_BLEND 
from pygame2.sdl.video import SDL_BLENDMODE_ADD   
from pygame2.sdl.video import SDL_BLENDMODE_MOD   
from pygame2.sdl.video import SDL_GL_RED_SIZE                 
from pygame2.sdl.video import SDL_GL_GREEN_SIZE               
from pygame2.sdl.video import SDL_GL_BLUE_SIZE                
from pygame2.sdl.video import SDL_GL_ALPHA_SIZE               
from pygame2.sdl.video import SDL_GL_BUFFER_SIZE              
from pygame2.sdl.video import SDL_GL_DOUBLEBUFFER             
from pygame2.sdl.video import SDL_GL_DEPTH_SIZE               
from pygame2.sdl.video import SDL_GL_STENCIL_SIZE             
from pygame2.sdl.video import SDL_GL_ACCUM_RED_SIZE           
from pygame2.sdl.video import SDL_GL_ACCUM_GREEN_SIZE         
from pygame2.sdl.video import SDL_GL_ACCUM_BLUE_SIZE          
from pygame2.sdl.video import SDL_GL_ACCUM_ALPHA_SIZE         
from pygame2.sdl.video import SDL_GL_STEREO                   
from pygame2.sdl.video import SDL_GL_MULTISAMPLEBUFFERS       
from pygame2.sdl.video import SDL_GL_MULTISAMPLESAMPLES       
from pygame2.sdl.video import SDL_GL_ACCELERATED_VISUAL       
from pygame2.sdl.video import SDL_GL_RETAINED_BACKING         
from pygame2.sdl.video import SDL_GL_CONTEXT_MAJOR_VERSION    
from pygame2.sdl.video import SDL_GL_CONTEXT_MINOR_VERSION    
from pygame2.sdl.video import SDL_GL_CONTEXT_FLAGS            
from pygame2.sdl.video import SDL_GL_CONTEXT_PROFILE_MASK     
from pygame2.sdl.video import SDL_GL_CONTEXT_PROFILE_CORE           
from pygame2.sdl.video import SDL_GL_CONTEXT_PROFILE_COMPATIBILITY  
#from pygame2.sdl.video import SDL_GL_CONTEXT_PROFILE_ES2            
from pygame2.sdl.video import SDL_GL_CONTEXT_DEBUG_FLAG              
from pygame2.sdl.video import SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG 
from pygame2.sdl.video import SDL_GL_CONTEXT_ROBUST_ACCESS_FLAG      
from pygame2.sdl.video import SDL_WINDOW_FULLSCREEN       
from pygame2.sdl.video import SDL_WINDOW_OPENGL           
from pygame2.sdl.video import SDL_WINDOW_SHOWN            
from pygame2.sdl.video import SDL_WINDOW_HIDDEN           
from pygame2.sdl.video import SDL_WINDOW_BORDERLESS       
from pygame2.sdl.video import SDL_WINDOW_RESIZABLE        
from pygame2.sdl.video import SDL_WINDOW_MINIMIZED        
from pygame2.sdl.video import SDL_WINDOW_MAXIMIZED        
from pygame2.sdl.video import SDL_WINDOW_INPUT_GRABBED    
from pygame2.sdl.video import SDL_WINDOW_INPUT_FOCUS      
from pygame2.sdl.video import SDL_WINDOW_MOUSE_FOCUS      
from pygame2.sdl.video import SDL_WINDOW_FOREIGN          
from pygame2.sdl.video import SDL_WINDOWEVENT_NONE            
from pygame2.sdl.video import SDL_WINDOWEVENT_SHOWN           
from pygame2.sdl.video import SDL_WINDOWEVENT_HIDDEN          
from pygame2.sdl.video import SDL_WINDOWEVENT_EXPOSED         
from pygame2.sdl.video import SDL_WINDOWEVENT_MOVED           
from pygame2.sdl.video import SDL_WINDOWEVENT_RESIZED         
from pygame2.sdl.video import SDL_WINDOWEVENT_SIZE_CHANGED    
from pygame2.sdl.video import SDL_WINDOWEVENT_MINIMIZED       
from pygame2.sdl.video import SDL_WINDOWEVENT_MAXIMIZED       
from pygame2.sdl.video import SDL_WINDOWEVENT_RESTORED        
from pygame2.sdl.video import SDL_WINDOWEVENT_ENTER           
from pygame2.sdl.video import SDL_WINDOWEVENT_LEAVE           
from pygame2.sdl.video import SDL_WINDOWEVENT_FOCUS_GAINED    
from pygame2.sdl.video import SDL_WINDOWEVENT_FOCUS_LOST      
from pygame2.sdl.video import SDL_WINDOWEVENT_CLOSE           
from pygame2.sdl.video import SDL_WINDOWPOS_UNDEFINED_MASK 
from pygame2.sdl.video import SDL_WINDOWPOS_UNDEFINED 
from pygame2.sdl.video import SDL_WINDOWPOS_CENTERED_MASK 
from pygame2.sdl.video import SDL_WINDOWPOS_CENTERED 
from pygame2.sdl.pixels import SDL_ALPHA_OPAQUE       
from pygame2.sdl.pixels import SDL_ALPHA_TRANSPARENT  
from pygame2.sdl.pixels import SDL_PIXELTYPE_UNKNOWN  
from pygame2.sdl.pixels import SDL_PIXELTYPE_INDEX1   
from pygame2.sdl.pixels import SDL_PIXELTYPE_INDEX4   
from pygame2.sdl.pixels import SDL_PIXELTYPE_INDEX8   
from pygame2.sdl.pixels import SDL_PIXELTYPE_PACKED8  
from pygame2.sdl.pixels import SDL_PIXELTYPE_PACKED16 
from pygame2.sdl.pixels import SDL_PIXELTYPE_PACKED32 
from pygame2.sdl.pixels import SDL_PIXELTYPE_ARRAYU8  
from pygame2.sdl.pixels import SDL_PIXELTYPE_ARRAYU16 
from pygame2.sdl.pixels import SDL_PIXELTYPE_ARRAYU32 
from pygame2.sdl.pixels import SDL_PIXELTYPE_ARRAYF16 
from pygame2.sdl.pixels import SDL_PIXELTYPE_ARRAYF32 
from pygame2.sdl.pixels import SDL_BITMAPORDER_NONE 
from pygame2.sdl.pixels import SDL_BITMAPORDER_4321 
from pygame2.sdl.pixels import SDL_BITMAPORDER_1234 
from pygame2.sdl.pixels import SDL_PACKEDORDER_NONE 
from pygame2.sdl.pixels import SDL_PACKEDORDER_XRGB 
from pygame2.sdl.pixels import SDL_PACKEDORDER_RGBX 
from pygame2.sdl.pixels import SDL_PACKEDORDER_ARGB 
from pygame2.sdl.pixels import SDL_PACKEDORDER_RGBA 
from pygame2.sdl.pixels import SDL_PACKEDORDER_XBGR 
from pygame2.sdl.pixels import SDL_PACKEDORDER_BGRX 
from pygame2.sdl.pixels import SDL_PACKEDORDER_ABGR 
from pygame2.sdl.pixels import SDL_PACKEDORDER_BGRA 
from pygame2.sdl.pixels import SDL_ARRAYORDER_NONE 
from pygame2.sdl.pixels import SDL_ARRAYORDER_RGB  
from pygame2.sdl.pixels import SDL_ARRAYORDER_RGBA 
from pygame2.sdl.pixels import SDL_ARRAYORDER_ARGB 
from pygame2.sdl.pixels import SDL_ARRAYORDER_BGR  
from pygame2.sdl.pixels import SDL_ARRAYORDER_BGRA 
from pygame2.sdl.pixels import SDL_ARRAYORDER_ABGR 
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_NONE    
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_332     
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_4444    
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_1555    
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_5551    
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_565     
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_8888    
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_2101010 
from pygame2.sdl.pixels import SDL_PACKEDLAYOUT_1010102 
from pygame2.sdl.pixels import SDL_DEFINE_PIXELFOURCC 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_UNKNOWN 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_INDEX1LSB 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_INDEX1MSB 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_INDEX4LSB 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_INDEX4MSB 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_INDEX8 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGB332 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGB444 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGB555 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGR555 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ARGB4444 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGBA4444 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ABGR4444 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGRA4444 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ARGB1555 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGBA5551 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ABGR1555 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGRA5551 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGB565 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGR565 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGB24 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGR24 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGB888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGBX8888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGR888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGRX8888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ARGB8888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_RGBA8888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ABGR8888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_BGRA8888 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_ARGB2101010 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_YV12 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_IYUV 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_YUY2 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_UYVY 
from pygame2.sdl.pixels import SDL_PIXELFORMAT_YVYU 
from pygame2.sdl.render import SDL_RENDERER_SOFTWARE      
from pygame2.sdl.render import SDL_RENDERER_ACCELERATED   
from pygame2.sdl.render import SDL_RENDERER_PRESENTVSYNC  
from pygame2.sdl.render import SDL_RENDERER_TARGETTEXTURE 
from pygame2.sdl.render import SDL_TEXTUREACCESS_STATIC    
from pygame2.sdl.render import SDL_TEXTUREACCESS_STREAMING 
from pygame2.sdl.render import SDL_TEXTUREACCESS_TARGET    
from pygame2.sdl.render import SDL_TEXTUREMODULATE_NONE  
from pygame2.sdl.render import SDL_TEXTUREMODULATE_COLOR 
from pygame2.sdl.render import SDL_TEXTUREMODULATE_ALPHA 
from pygame2.sdl.endian import SDL_LIL_ENDIAN 
from pygame2.sdl.endian import SDL_BIG_ENDIAN 
from pygame2.sdl.endian import SDL_BYTEORDER 

__all__ = [ 
    "SDL_POWERSTATE_UNKNOWN", 
    "SDL_POWERSTATE_ON_BATTERY", 
    "SDL_POWERSTATE_NO_BATTERY", 
    "SDL_POWERSTATE_CHARGING", 
    "SDL_POWERSTATE_CHARGED", 
    "SDL_AUDIO_MASK_BITSIZE", 
    "SDL_AUDIO_MASK_DATATYPE", 
    "SDL_AUDIO_MASK_ENDIAN", 
    "SDL_AUDIO_MASK_SIGNED", 
    "SDL_AUDIO_ALLOW_FREQUENCY_CHANGE", 
    "SDL_AUDIO_ALLOW_FORMAT_CHANGE", 
    "SDL_AUDIO_ALLOW_CHANNELS_CHANGE", 
    "SDL_AUDIO_ALLOW_ANY_CHANGE", 
    "SDL_AUDIO_STOPPED", 
    "SDL_AUDIO_PLAYING", 
    "SDL_AUDIO_PAUSED", 
    "SDL_MIX_MAXVOLUME", 
    "SDL_SWSURFACE", 
    "SDL_PREALLOC", 
    "SDL_RLEACCEL", 
    "SDL_DONTFREE", 
    "SDL_LOG_CATEGORY_APPLICATION", 
    "SDL_LOG_CATEGORY_ERROR", 
    "SDL_LOG_CATEGORY_SYSTEM", 
    "SDL_LOG_CATEGORY_AUDIO", 
    "SDL_LOG_CATEGORY_VIDEO", 
    "SDL_LOG_CATEGORY_RENDER", 
    "SDL_LOG_CATEGORY_INPUT", 
    "SDL_LOG_CATEGORY_CUSTOM", 
    "SDL_LOG_PRIORITY_VERBOSE", 
    "SDL_LOG_PRIORITY_DEBUG", 
    "SDL_LOG_PRIORITY_INFO", 
    "SDL_LOG_PRIORITY_WARN", 
    "SDL_LOG_PRIORITY_ERROR", 
    "SDL_LOG_PRIORITY_CRITICAL", 
    "SDL_NONSHAPEABLE_WINDOW", 
    "SDL_INVALID_SHAPE_ARGUMENT", 
    "SDL_WINDOW_LACKS_SHAPE", 
    "SDL_HINT_DEFAULT", 
    "SDL_HINT_NORMAL", 
    "SDL_HINT_OVERRIDE", 
    "SDL_HINT_FRAMEBUFFER_ACCELERATION", 
    "SDL_HINT_IDLE_TIMER_DISABLED", 
    "SDL_HINT_ORIENTATIONS", 
    "SDL_HINT_RENDER_DRIVER", 
    "SDL_HINT_RENDER_OPENGL_SHADERS", 
    "SDL_HINT_RENDER_SCALE_QUALITY", 
    "SDL_HINT_RENDER_VSYNC", 
    "SDL_RELEASED", 
    "SDL_PRESSED", 
    "SDL_FIRSTEVENT", 
    "SDL_QUIT", 
    "SDL_WINDOWEVENT", 
    "SDL_SYSWMEVENT", 
    "SDL_KEYDOWN", 
    "SDL_KEYUP", 
    "SDL_TEXTEDITING", 
    "SDL_TEXTINPUT", 
    "SDL_MOUSEMOTION", 
    "SDL_MOUSEBUTTONDOWN", 
    "SDL_MOUSEBUTTONUP", 
    "SDL_MOUSEWHEEL", 
    "SDL_INPUTMOTION", 
    "SDL_INPUTBUTTONDOWN", 
    "SDL_INPUTBUTTONUP", 
    "SDL_INPUTWHEEL", 
    "SDL_INPUTPROXIMITYIN", 
    "SDL_INPUTPROXIMITYOUT", 
    "SDL_JOYAXISMOTION", 
    "SDL_JOYBALLMOTION", 
    "SDL_JOYHATMOTION", 
    "SDL_JOYBUTTONDOWN", 
    "SDL_JOYBUTTONUP", 
    "SDL_FINGERDOWN", 
    "SDL_FINGERUP", 
    "SDL_FINGERMOTION", 
    "SDL_TOUCHBUTTONDOWN", 
    "SDL_TOUCHBUTTONUP", 
    "SDL_DOLLARGESTURE", 
    "SDL_DOLLARRECORD", 
    "SDL_MULTIGESTURE", 
    "SDL_CLIPBOARDUPDATE", 
    "SDL_DROPFILE", 
    "SDL_USEREVENT", 
    "SDL_LASTEVENT", 
    "SDL_TEXTEDITINGEVENT_TEXT_SIZE", 
    "SDL_TEXTINPUTEVENT_TEXT_SIZE", 
    "SDL_ADDEVENT", 
    "SDL_PEEKEVENT", 
    "SDL_GETEVENT", 
    "SDL_QUERY", 
    "SDL_IGNORE", 
    "SDL_DISABLE", 
    "SDL_ENABLE", 
    "SDL_INIT_TIMER", 
    "SDL_INIT_AUDIO", 
    "SDL_INIT_VIDEO", 
    "SDL_INIT_JOYSTICK", 
    "SDL_INIT_HAPTIC", 
    "SDL_INIT_NOPARACHUTE", 
    "SDL_INIT_EVERYTHING", 
    "SDL_FALSE", 
    "SDL_TRUE", 
    "SDL_BUTTON_LEFT", 
    "SDL_BUTTON_MIDDLE", 
    "SDL_BUTTON_RIGHT", 
    "SDL_BUTTON_X1", 
    "SDL_BUTTON_X2", 
    "SDL_BUTTON_LMASK", 
    "SDL_BUTTON_MMASK", 
    "SDL_BUTTON_RMASK", 
    "SDL_BUTTON_X1MASK", 
    "SDL_BUTTON_X2MASK", 
    "SDL_HAT_CENTERED", 
    "SDL_HAT_UP", 
    "SDL_HAT_RIGHT", 
    "SDL_HAT_DOWN", 
    "SDL_HAT_LEFT", 
    "SDL_HAT_RIGHTUP", 
    "SDL_HAT_RIGHTDOWN", 
    "SDL_HAT_LEFTUP", 
    "SDL_HAT_LEFTDOWN", 
    "SDL_BLENDMODE_NONE", 
    "SDL_BLENDMODE_BLEND", 
    "SDL_BLENDMODE_ADD", 
    "SDL_BLENDMODE_MOD", 
    "SDL_GL_RED_SIZE", 
    "SDL_GL_GREEN_SIZE", 
    "SDL_GL_BLUE_SIZE", 
    "SDL_GL_ALPHA_SIZE", 
    "SDL_GL_BUFFER_SIZE", 
    "SDL_GL_DOUBLEBUFFER", 
    "SDL_GL_DEPTH_SIZE", 
    "SDL_GL_STENCIL_SIZE", 
    "SDL_GL_ACCUM_RED_SIZE", 
    "SDL_GL_ACCUM_GREEN_SIZE", 
    "SDL_GL_ACCUM_BLUE_SIZE", 
    "SDL_GL_ACCUM_ALPHA_SIZE", 
    "SDL_GL_STEREO", 
    "SDL_GL_MULTISAMPLEBUFFERS", 
    "SDL_GL_MULTISAMPLESAMPLES", 
    "SDL_GL_ACCELERATED_VISUAL", 
    "SDL_GL_RETAINED_BACKING", 
    "SDL_GL_CONTEXT_MAJOR_VERSION", 
    "SDL_GL_CONTEXT_MINOR_VERSION", 
    "SDL_GL_CONTEXT_FLAGS", 
    "SDL_GL_CONTEXT_PROFILE_MASK", 
    "SDL_GL_CONTEXT_PROFILE_CORE", 
    "SDL_GL_CONTEXT_PROFILE_COMPATIBILITY", 
#    "SDL_GL_CONTEXT_PROFILE_ES2", 
    "SDL_GL_CONTEXT_DEBUG_FLAG", 
    "SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG", 
    "SDL_GL_CONTEXT_ROBUST_ACCESS_FLAG", 
    "SDL_WINDOW_FULLSCREEN", 
    "SDL_WINDOW_OPENGL", 
    "SDL_WINDOW_SHOWN", 
    "SDL_WINDOW_HIDDEN", 
    "SDL_WINDOW_BORDERLESS", 
    "SDL_WINDOW_RESIZABLE", 
    "SDL_WINDOW_MINIMIZED", 
    "SDL_WINDOW_MAXIMIZED", 
    "SDL_WINDOW_INPUT_GRABBED", 
    "SDL_WINDOW_INPUT_FOCUS", 
    "SDL_WINDOW_MOUSE_FOCUS", 
    "SDL_WINDOW_FOREIGN", 
    "SDL_WINDOWEVENT_NONE", 
    "SDL_WINDOWEVENT_SHOWN", 
    "SDL_WINDOWEVENT_HIDDEN", 
    "SDL_WINDOWEVENT_EXPOSED", 
    "SDL_WINDOWEVENT_MOVED", 
    "SDL_WINDOWEVENT_RESIZED", 
    "SDL_WINDOWEVENT_SIZE_CHANGED", 
    "SDL_WINDOWEVENT_MINIMIZED", 
    "SDL_WINDOWEVENT_MAXIMIZED", 
    "SDL_WINDOWEVENT_RESTORED", 
    "SDL_WINDOWEVENT_ENTER", 
    "SDL_WINDOWEVENT_LEAVE", 
    "SDL_WINDOWEVENT_FOCUS_GAINED", 
    "SDL_WINDOWEVENT_FOCUS_LOST", 
    "SDL_WINDOWEVENT_CLOSE", 
    "SDL_WINDOWPOS_UNDEFINED_MASK", 
    "SDL_WINDOWPOS_UNDEFINED", 
    "SDL_WINDOWPOS_CENTERED_MASK", 
    "SDL_WINDOWPOS_CENTERED", 
    "SDL_ALPHA_OPAQUE", 
    "SDL_ALPHA_TRANSPARENT", 
    "SDL_PIXELTYPE_UNKNOWN", 
    "SDL_PIXELTYPE_INDEX1", 
    "SDL_PIXELTYPE_INDEX4", 
    "SDL_PIXELTYPE_INDEX8", 
    "SDL_PIXELTYPE_PACKED8", 
    "SDL_PIXELTYPE_PACKED16", 
    "SDL_PIXELTYPE_PACKED32", 
    "SDL_PIXELTYPE_ARRAYU8", 
    "SDL_PIXELTYPE_ARRAYU16", 
    "SDL_PIXELTYPE_ARRAYU32", 
    "SDL_PIXELTYPE_ARRAYF16", 
    "SDL_PIXELTYPE_ARRAYF32", 
    "SDL_BITMAPORDER_NONE", 
    "SDL_BITMAPORDER_4321", 
    "SDL_BITMAPORDER_1234", 
    "SDL_PACKEDORDER_NONE", 
    "SDL_PACKEDORDER_XRGB", 
    "SDL_PACKEDORDER_RGBX", 
    "SDL_PACKEDORDER_ARGB", 
    "SDL_PACKEDORDER_RGBA", 
    "SDL_PACKEDORDER_XBGR", 
    "SDL_PACKEDORDER_BGRX", 
    "SDL_PACKEDORDER_ABGR", 
    "SDL_PACKEDORDER_BGRA", 
    "SDL_ARRAYORDER_NONE", 
    "SDL_ARRAYORDER_RGB", 
    "SDL_ARRAYORDER_RGBA", 
    "SDL_ARRAYORDER_ARGB", 
    "SDL_ARRAYORDER_BGR", 
    "SDL_ARRAYORDER_BGRA", 
    "SDL_ARRAYORDER_ABGR", 
    "SDL_PACKEDLAYOUT_NONE", 
    "SDL_PACKEDLAYOUT_332", 
    "SDL_PACKEDLAYOUT_4444", 
    "SDL_PACKEDLAYOUT_1555", 
    "SDL_PACKEDLAYOUT_5551", 
    "SDL_PACKEDLAYOUT_565", 
    "SDL_PACKEDLAYOUT_8888", 
    "SDL_PACKEDLAYOUT_2101010", 
    "SDL_PACKEDLAYOUT_1010102", 
    "SDL_DEFINE_PIXELFOURCC", 
    "SDL_PIXELFORMAT_UNKNOWN", 
    "SDL_PIXELFORMAT_INDEX1LSB", 
    "SDL_PIXELFORMAT_INDEX1MSB", 
    "SDL_PIXELFORMAT_INDEX4LSB", 
    "SDL_PIXELFORMAT_INDEX4MSB", 
    "SDL_PIXELFORMAT_INDEX8", 
    "SDL_PIXELFORMAT_RGB332", 
    "SDL_PIXELFORMAT_RGB444", 
    "SDL_PIXELFORMAT_RGB555", 
    "SDL_PIXELFORMAT_BGR555", 
    "SDL_PIXELFORMAT_ARGB4444", 
    "SDL_PIXELFORMAT_RGBA4444", 
    "SDL_PIXELFORMAT_ABGR4444", 
    "SDL_PIXELFORMAT_BGRA4444", 
    "SDL_PIXELFORMAT_ARGB1555", 
    "SDL_PIXELFORMAT_RGBA5551", 
    "SDL_PIXELFORMAT_ABGR1555", 
    "SDL_PIXELFORMAT_BGRA5551", 
    "SDL_PIXELFORMAT_RGB565", 
    "SDL_PIXELFORMAT_BGR565", 
    "SDL_PIXELFORMAT_RGB24", 
    "SDL_PIXELFORMAT_BGR24", 
    "SDL_PIXELFORMAT_RGB888", 
    "SDL_PIXELFORMAT_RGBX8888", 
    "SDL_PIXELFORMAT_BGR888", 
    "SDL_PIXELFORMAT_BGRX8888", 
    "SDL_PIXELFORMAT_ARGB8888", 
    "SDL_PIXELFORMAT_RGBA8888", 
    "SDL_PIXELFORMAT_ABGR8888", 
    "SDL_PIXELFORMAT_BGRA8888", 
    "SDL_PIXELFORMAT_ARGB2101010", 
    "SDL_PIXELFORMAT_YV12", 
    "SDL_PIXELFORMAT_IYUV", 
    "SDL_PIXELFORMAT_YUY2", 
    "SDL_PIXELFORMAT_UYVY", 
    "SDL_PIXELFORMAT_YVYU", 
    "SDL_RENDERER_SOFTWARE", 
    "SDL_RENDERER_ACCELERATED", 
    "SDL_RENDERER_PRESENTVSYNC", 
    "SDL_RENDERER_TARGETTEXTURE", 
    "SDL_TEXTUREACCESS_STATIC", 
    "SDL_TEXTUREACCESS_STREAMING", 
    "SDL_TEXTUREACCESS_TARGET", 
    "SDL_TEXTUREMODULATE_NONE", 
    "SDL_TEXTUREMODULATE_COLOR", 
    "SDL_TEXTUREMODULATE_ALPHA", 
    "SDL_LIL_ENDIAN", 
    "SDL_BIG_ENDIAN", 
    "SDL_BYTEORDER" 
]


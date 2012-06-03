#version 130
#line 2 0

/* blend modes */
#define BM_NONE         0   // discard.
#define BM_ASIS         1   // no blend.
#define BM_CLASSIC      2
#define BM_FGONLY       3
#define BM_OVERSCAN     254
#define BM_CODEDBAD     255   // filler insn

uniform usampler2D      findex;         // RGBA16UI: cs, cy, cw, ch
uniform sampler2D       font;

uniform vec3 pszar;
uniform vec4 mouse_color;
uniform float darken;                   // drawing lower levels.
uniform int debug_active;

flat in uvec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat in  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall
flat in  vec4 fl_fg, fl_bg; 	        // floor or the only blit

flat in uvec4 debug0;
flat in uvec4 debug1;

out vec4 frag;

void borderglow(inout vec4 color, in vec4 border_color) {
    vec2 wh = pszar.xy * pszar.z;
    vec2 pc = gl_PointCoord * wh;
    float w = 1;
    if (pc.x > 29.0)  { w = 2 ; }
    if (   ( pc.x < w) || (pc.x > wh.x - w) 
        || ( pc.y < w) || (pc.y > wh.y - w)) 
        color = border_color;
    return;
}

vec4 debug_encode(in uint value) {
/* encodes the value into rgb, take one */
    return vec4( 
        ((value >> 16) & 0xff)/255.0, 
        ((value >> 8) & 0xff)/255.0,  
        (value & 0xff)/255.0, 
    1.0);
}
vec4 debug_output_row(in uvec4 dval) { 
    float x = gl_PointCoord.x;
    vec4 a = vec4(0.25, 0.5, 0.75, 1.0);
    
    if (x < a.x)
        return debug_encode(dval.x);
    if (x < a.y)
        return debug_encode(dval.y);
    if (x < a.z)
        return debug_encode(dval.z);
    if (x < a.w)
        return debug_encode(dval.w);
}
vec4 debug_output(in uvec4 d0, in uvec4 d1, in uvec4 d2, in uvec4 d3) {
    float y = gl_PointCoord.y;
    vec4 a = vec4(0.25, 0.5, 0.75, 1.0);
    if (y < a.x)  // top row
        return debug_output_row(d0);
    if (y < a.y)  
        return debug_output_row(d1);
    if (y < a.z)  
        return debug_output_row(d2);
    if (y < a.w)  // bottom row
        return debug_output_row(d3);
}

vec4 blit_execute(in vec2 pc, in uint mode, in uint cindex, in vec4 fg, in vec4 bg) {
    ivec2 finsz = textureSize(findex,0);
    ivec2 fintc = ivec2(cindex % finsz.x, cindex / finsz.x);
    //ivec2 fintc = ivec2(cindex % finsz.x, finsz.x - cindex / finsz.x - 1);
    uvec4 cinfo = texelFetch(findex, fintc, 0);
    ivec2 fonsz = textureSize(font,0);
    
    //cinfo.y = fonsz.y - cinfo.y - 1;
    //cinfo.t = - cinfo.t;
    
    vec2 texcoords;
    texcoords.x = (cinfo.x + cinfo.s * pc.x) / fonsz.x;
    texcoords.y = (cinfo.y + cinfo.t * pc.y) / fonsz.y;
    
    vec4 tile_color = textureLod(font, texcoords, 0);
    vec4 rv;

    switch (mode) {
        case BM_FGONLY: 
            rv = fg * tile_color;
            rv.a = 1.0;
            break;
        case BM_CLASSIC:
            rv = mix(tile_color * fg, bg, 1.0 - tile_color.a);
            rv.a = 1.0;
            break;
        case BM_ASIS:
            rv = tile_color;
            rv.a = 1.0;
            break;
        case BM_NONE:	    
        default:
            rv = vec4(float(mode)/16.0,0,0,0);
            break;
    }
    return rv;
}

void main() {
    uint fl_mode = stuff.x & 0xFF;
    uint fl_cindex = stuff.x >> 8;
    uint up_cindex = stuff.y >> 8;
    uint up_mode = stuff.y & 0xFF;
    uint mouse = stuff.z;
    uint hidden = stuff.w;
    
    uvec4 debug3 = uvec4(fl_mode, fl_cindex, 23, 42);
    
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0))
        discard;

    if (debug_active > 0) {
        frag = debug_output(debug0, debug1, stuff, debug3);
        return;
    }
    
    if (fl_mode == BM_OVERSCAN) {
        frag = vec4(0.42, 0.23, 0.08, 1.0);
        return;
    }

    if (hidden > 0) {
        frag = vec4(0.5, 0.5, 0.5, 1.0);
        return;
    }

    vec4 color = blit_execute(pc, fl_mode, fl_cindex, fl_fg, fl_bg);
    
    if (liquicolor.a > 0.1)
        color = mix(liquicolor, color, 0.5);
    
    color.rgb *= darken;
    
    if (mouse > 0)
        borderglow(color, mouse_color);
    
    frag = color;
}

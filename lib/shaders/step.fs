#version 130
#pragma debug(on)

/* blend modes */
#define BM_NONE         0u   // discard.
#define BM_ASIS         1u   // no blend.
#define BM_CLASSIC      2u
#define BM_FGONLY       3u
#define BM_OVERSCAN     254u
#define BM_CODEDBAD     255u   // filler insn

uniform usampler2D      findex;         // RGBA16UI: cs, cy, cw, ch
uniform sampler2D       font;

uniform vec3 pszar;
uniform vec4 mouse_color;
uniform float darken;                   // drawing lower levels.
uniform int debug_active;

flat in uvec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat in  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall
flat in  vec4 fl_fg, fl_bg; 	        // floor or the only blit
flat in  vec4 up_fg, up_bg; 	        // object or none blit

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
    return vec4( ((value >> 16u) & 0xffu),
                 ((value >> 8u) & 0xffu),
                  (value & 0xffu),
                   255u) / 255.0;
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

vec4 blit_execute(in vec2 pc, in uint mode, in uint cindex, in vec4 fg, in vec4 bg, out uvec4 d2, out uvec4 d3) {
    ivec2 finsz = textureSize(findex,0);
    ivec2 fintc = ivec2(int(cindex) % finsz.x, int(cindex) / finsz.x);
    uvec4 cinfo = texelFetch(findex, fintc, 0);
    ivec2 fonsz = textureSize(font,0);
    d2 = cinfo;
    d3 = uvec4(finsz.xy, fonsz.xy);
    
    // tile size in font texture normalized coordinates
    vec2 tilesizeN = vec2(float(cinfo.z)/float(fonsz.x), float(cinfo.w)/float(fonsz.y));
    // offset to the tile in font texture normalized coordinates
    vec2 offsetN = vec2(float(cinfo.x)/float(fonsz.x), float(cinfo.y)/float(fonsz.y));
    // finally, the texture coordinates for the fragment
    vec2 texcoords = offsetN + tilesizeN * pc;
    
    vec4 tile_color = textureLod(font, texcoords, 0);
    vec4 rv;

    switch (int(mode)) {
        case int(BM_FGONLY):
            rv = fg * tile_color;
            rv.a = tile_color.a;
            break;
        case int(BM_CLASSIC):
            rv = mix(tile_color * fg, bg, 1.0 - tile_color.a);
            rv.a = 1.0;
            break;
        case int(BM_ASIS):
            rv = tile_color;
            rv.a = 1.0;
            break;
        case int(BM_NONE):
            rv = vec4(0,0,0,0);
            break;
        default:
            rv = vec4(float(mode)/16.0,0,0,1);
            break;
    }
    return rv;
}

uint rgba2rbgui(in vec4 c) {
    return (uint(c.r*255)<<16u) + 
            (uint(c.g*255)<<8u) + 
            (uint(c.b*255));
}

void main() {
    uint fl_mode = stuff.x & 0xFFu;
    uint fl_cindex = stuff.x >> 8u;
    uint up_cindex = stuff.y >> 8u;
    uint up_mode = stuff.y & 0xFFu;
    uint mouse = stuff.z;
    uint hidden = stuff.w;
    
    uvec4 debug2 = uvec4(8u, 8u, 8u, 8u);
    uvec4 debug3 = uvec4(42u, 23u, 23u, 42u);
    
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0))
        discard;

    if (fl_mode == BM_OVERSCAN) {
        frag = vec4(0.42, 0.23, 0.08, 1.0);
        return;
    }

    if (hidden > 0u) {
        frag = vec4(0.23, 0.23, 0.23, 1.0);
        return;
    }

    vec4 color = blit_execute(pc, fl_mode, fl_cindex, fl_fg, fl_bg, debug2, debug3);
    if (up_mode != BM_CODEDBAD) {
        vec4 up_color = blit_execute(pc, up_mode, up_cindex, up_fg, up_bg, debug2, debug3);
        debug2.x = fl_cindex;
        debug2.y = fl_mode;
        debug2.z = rgba2rbgui(fl_fg);
        debug2.w = rgba2rbgui(fl_bg);
        debug3.x = up_cindex;
        debug3.y = up_mode;
        debug3.z = rgba2rbgui(up_fg);
        debug3.w = rgba2rbgui(up_bg);
       
        color = mix(up_color, color, 1.0 - up_color.a);
    }

    if (debug_active > 0) {
        frag = debug_output(debug0, debug1, debug2, debug3);
        return;
    }
    
    if (liquicolor.a > 0.1) {
        if (fl_mode == BM_NONE) {
            color = vec4(liquicolor.rgb, 0.75);
        } else {
            color = mix(liquicolor, color, 0.5);
        }
    }
    
    color.rgb *= darken;
    
    if (mouse > 0u)
        borderglow(color, mouse_color);

    frag = color;
}

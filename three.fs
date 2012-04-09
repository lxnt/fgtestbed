#version 130
#line 2 0

#define BM_NONE         0
#define BM_ASIS         1
#define BM_CLASSIC      2
#define BM_FGONLY       3
#define BM_BAD_DISPATCH 4   // addr = (0,0)
#define BM_CODEDBAD     5   // filler insn

uniform sampler2D       font;

uniform vec3 pszar;               // { Parx, Pary, Psz }
uniform float darken;             // drawing lower levels.
uniform vec4 mouse_color;
uniform int frame_no;
uniform int debug;

/* should have at least 8 on most GL3 cards
   blit is ( s, t, txsz_s, txsz_t ) */
flat in  vec4 up_blit, up_fg, up_bg; 	// possible 'upper' blit on top of [fake]floor
flat in  vec4 fl_blit, fl_fg, fl_bg; 	// floor or the only blit 
flat in ivec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat in  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall

flat in ivec4 debug0; // 4x4 = 16 values pushed through the tile
flat in ivec4 debug1; // under mouse at 'debug' frame as signalled 
flat in ivec4 debug2; // by debug_frame uniform. 
flat in ivec4 debug3; // pszar better be 1:1

out vec4 frag; // telefrag ?

vec4 debug_encode(in int value) {
/* encodes the value into rgb, take one */
    return vec4( 
	((value >> 16) & 0xff)/255.0, 
	((value >> 8) & 0xff)/255.0,  
	(value & 0xff)/255.0, 
    1.0);
}
vec4 debug_output_row(in ivec4 dval) { 
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
vec4 debug_output() {
    float y = gl_PointCoord.y;
    vec4 a = vec4(0.25, 0.5, 0.75, 1.0);
    if (y < a.x)  // top row
	return debug_output_row(debug0);
    if (y < a.y)  
	return debug_output_row(debug1);
    if (y < a.z)  
	return debug_output_row(debug2);
    if (y < a.w)  // bottom row
	return debug_output_row(debug3);
}

vec4 blit_execute(in vec2 pc, in int mode, in vec4 blit, in vec4 fg, in vec4 bg) {
    vec2 texcoords = vec2 (blit.x + pc.x * blit.z, blit.y + pc.y * blit.w );
    vec4 tile_color = texture(font, texcoords);
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

void borderglow(inout vec4 color, in vec4 base_color) {
    vec2 pc = gl_PointCoord * pszar.xy * pszar.z;
    float w = 1.0;
    if (pszar.z > 29.0) { w = 2.0; }
    if (   (pc.x < w) || (pc.x > pszar.z*pszar.x - w)
	|| (pc.y < w) || (pc.y > pszar.z*pszar.y - w) ) {
	color = base_color;
    }
}

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0)) {
	discard;
    }
    int up_mode = stuff.x;
    int fl_mode = stuff.y;
    int mouse   = stuff.z;
    int hidden  = stuff.w;

    vec4 hi_color = vec4(0.8, 0.8, 0.4, 1.0); // fancy hidden-map effect 
    vec4 color = blit_execute(pc, fl_mode, fl_blit, fl_fg, fl_bg);
    vec4 up_color = blit_execute(pc, up_mode, up_blit, up_fg, up_bg);
#if 0 // uptiles disabled atm
    if (up_mode > 0) {
        color = mix(color, up_color, up_color.a);
    }
#endif
    if (hidden > 0) {
	frag = hi_color; // * darken ?
	return;
    }

    if (fl_mode > 0)
	color = mix(liquicolor, color, 0.5);
    else  // openspace, etc
	color = liquicolor;
    color = color * darken;

#if 1
    if (fl_mode == BM_BAD_DISPATCH)
	borderglow(color, vec4(mouse_color.r, 0,0,1));
    if (fl_mode == BM_CODEDBAD)
	borderglow(color, vec4(mouse_color.r, mouse_color.g,0,1));
#endif

    if (mouse > 0)
	borderglow(color, mouse_color);

    if ((debug > 0) && (mouse > 0))
	frag = debug_output();
    else
	frag = color; // what a mess
}

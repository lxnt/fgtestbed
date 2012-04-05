#version 130
#line 2 0

uniform sampler2D font;
uniform usampler2D      dispatch; // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA32UI ARRAY

uniform vec3 pszar;             // { Parx, Pary, Psz }
uniform float darken;  // drawing lower levels.
uniform vec4 mouse_color;
uniform int show_hidden;
uniform int frame_no;
uniform ivec4 txsz;               // { w_tiles, h_tiles, max_tile_w, max_tile_h } <- font texture params.

flat in  int mouse_here;
flat in uint floor_mat;
flat in uint floor_tile;
flat in uint upper_mat;
flat in uint upper_tile;
flat in uint designation;

out vec4 fragcolor;

#define BM_NONE         0
#define BM_ASIS         1
#define BM_CLASSIC      2
#define BM_FGONLY       3

/* dumps 2 9-bit values as rgb8 (2 colors' lsb ignored (=0)) 
    r: a8a7a6a5 a4a3ZZ
    g: a2a1a0b8 b7b6ZZ
    b: b5b4b3b2 b1b0ZZ
*/
vec4 dump9(uint a9, uint b9) {
    uint r = a9 & 0xFCu;
    uint g = ( (a9 << 6u) & (b9 >> 4u) ) & 0xFCu;
    uint b = (b9 << 2u) & 0xFCu;
    return vec4(float(r)/256.0, float(g)/256.0, float(b)/256.0, 1.0);
}

/* dumps 2 12-bit values as rgb8
    r = a11a10a9a8 a7a6a5a4
    g = a3a2a1a0 b11b10b9b8
    b = b7b6b5b4 b3b2b1b0
*/
vec4 dump12(uint A, uint B) { 
    uint r = (A >> 4u) & 0xFFu;
    uint g = ((A & 0x0Fu) << 4u ) | ( (B>>8u) & 0x0Fu );
    uint b = B & 0xFFu;
    return vec4(float(r)/256.0, float(g)/256.0, float(b)/256.0, 1.0);
}
/* same with 10 bit values
    r: a9a8a7a6 a5a4a3_0
    g: a2a1a0b9 b8b7b6_0
    b: b5b4b3b2 b1b0_0_0
*/
vec4 dump10(uint A, uint B) {
    uint r = ( A >> 2u ) & 0xFFu;
    uint g = (( ( A & 7u ) << 5u ) | ( B >> 5u ) ) & 0xFFu;
    
    uint b = ( B << 2u ) & 0xFFu;
    return vec4(float(r)/256.0, float(g)/256.0, float(b)/256.0, 1.0);
}

vec4 dump(uint A, uint B) {
    return vec4(1.0,1.0,1.0,1.0);
}

vec4 blit_execute(vec2 pc, uint mat, uint tile, inout int mode) {
    vec4 rv, blit, fg, bg;
    ivec2 ref = ivec2 ( int(mat), int(tile) );

    uvec4 addr = texelFetch(dispatch, ref.xy, 0 );
    addr.z = uint(frame_no);

    if ((addr.x + addr.y) == 0u) { // not defined
        mode = BM_ASIS;
        return dump10(mat, tile);
    }
    
    uvec4 insn = texelFetch(blitcode, ivec3(addr.xyz), 0);
    
    blit.xy = vec2(insn.x>>24u, (insn.x>>16u ) &0xffu)/ vec2(txsz.xy) ;
    blit.zw = 1.0 / vec2(txsz.xy) ; // for as long as we don't support tiles-smaller-than-txsz.zw
    // when we do: blit.zw = vec2( (insn.x>>8u)&0xffu,insn.x&0xffu )/vec2(txsz.xy);
    
    mode = int(insn.y);
    fg = vec4(insn.z>>24u, (insn.z>>16u ) &0xffu, (insn.z>>8u ) &0xffu, insn.z & 0xffu) / 256.0;
    bg = vec4(insn.w>>24u, (insn.w>>16u ) &0xffu, (insn.w>>8u ) &0xffu, insn.w & 0xffu) / 256.0;

    vec2 texcoords = vec2 (blit.x + pc.x * blit.z, blit.y + pc.y * blit.w );
    vec4 tile_color = texture(font, texcoords);
    
    switch (mode) {
	case BM_FGONLY: 
	    rv = fg * tile_color * darken;
	    rv.a = 1.0;
	    break;
	case BM_CLASSIC:
	    rv = mix(tile_color * fg, bg, 1.0 - tile_color.a) * darken;
	    rv.a = 1.0;
	    break;
	case BM_ASIS:
	    rv = tile_color * darken;
	    rv.a = 1.0;
	    break;
	case BM_NONE:	    
	default:
	    rv = vec4(0,0,0,0);
            break;
    }
    return rv;
}

void liquify(inout vec4 color, int mode) {
    if ((designation & 7u) > 0u) {
        float amount = float(designation & 7u)/7.0; // normalized liquid amount
	vec4 liquicolor;
	if (((designation >>21u) & 1u ) == 1u) {
	    liquicolor = vec4(amount, amount, 0.0, 1.0);
	} else {
	    liquicolor = vec4(0.0, 0.1*amount, amount, 1.0);
	}
	if (mode != 0) {
	    color = mix(liquicolor, color, 0.5);
	} else {
	    color = liquicolor;
	    color.a = 0.5*amount;
	}
    }
}

void mousefy(inout vec4 color) {
    if (mouse_here > 0) {
	vec2 pc = gl_PointCoord * pszar.xy * pszar.z;
	float w = 1.0;
	if (pszar.z > 29.0) { w = 2.0; }
	if (   (pc.x < w) || (pc.x > pszar.z*pszar.x - w)
	    || (pc.y < w) || (pc.y > pszar.z*pszar.y - w) ) {
	    color = mouse_color;
	}
    }
}

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0)) {
	discard;
    }
    uint hidden = (designation >>9u) & 1u;
    if ((show_hidden == 0) && (hidden == 1u)) {
        fragcolor = vec4(0.0, 1.0, 1.0, 1.0);
	return;
    }

    int mode = BM_NONE, igmode = BM_NONE;

    vec4 color = blit_execute(pc, floor_mat, floor_tile, mode);
#if 0
    if (upper_tile > 0u) {
        vec4 bc = blit_execute(pc, upper_mat, upper_tile, igmode);
        color = bc;
    }
#endif

    liquify(color, mode);
    mousefy(color);
    fragcolor = color; // what a mess
}

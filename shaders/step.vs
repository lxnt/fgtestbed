#version 130
#line 2 0

/* blend modes */
#define BM_NONE         0   // discard.
#define BM_ASIS         1   // no blend.
#define BM_CLASSIC      2
#define BM_FGONLY       3
#define BM_BAD_DISPATCH 4   // addr = (0,0), not actually used in blitcode
#define BM_CODEDBAD     5   // filler insn

uniform usampler2DArray screen;   // mapdata under traditional name
uniform usampler2D      dispatch; // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA32UI ARRAY

uniform ivec3 mapsize;
uniform ivec3 origin;                   // render_origin
uniform ivec2 gridsize;
uniform  vec3 pszar;
uniform ivec2 mouse_pos;
uniform  int  show_hidden;

in ivec2 position;                      // tiles relative to the render_origin; df cs.

flat out ivec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat out  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall

void decode_tile(in ivec3 posn, 
                 out int mat,  out int tile,
                 out int bmat, out int btile, 
                 out int gmat, out int gamt, 
                 out uint des) {
    
    posn.y = mapsize.y - posn.y;
    uvec4 vc = texelFetch(screen, posn, 0);
    
    mat   = int(vc.r >> 16u);
    tile  = int(vc.r & 65535u);
    bmat  = int(vc.g >> 16u);
    btile = int(vc.g & 65535u);
    gamt  = int(vc.b >> 16u);
    gmat  = int(vc.b & 65535u);
    des   = vc.a;
}

vec4 liquimount(in uint designation) {
    if ((designation & 7u) > 0u) {
        float amount = float(designation & 7u)/7.0; // normalized liquid amount
	if (((designation >>21u) & 1u ) == 1u) {
	    return vec4(amount, amount, 0.0, 1.0); // magma
	} else {
	    return vec4(0.0, 0.1*amount, amount, 1.0); // water
	}
    } else {
	return vec4(0,0,0,0);
    }
}

int hidden(in uint designation) {
    uint hbit = (designation >> 9u) & 1u;
    if ((show_hidden == 0) && (hbit == 1u))
	return 23;
    return 0;
}

int mouse_here() { 
    if (mouse_pos == position)
	return 23;
    return 0;
}

void main() { 
    vec2 posn = 2.0 * (vec2(position.x, gridsize.y - position.y) + 0.5)/gridsize - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;
    
    stuff = ivec4(0,0,0,0);
    
    ivec3 map_posn = ivec3(position, 0) + origin;
    if (any(lessThan(map_posn, ivec3(0,0,0)))
	|| any(greaterThanEqual(map_posn, mapsize))) {
	stuff = ivec4(-1,-1,-1,-1);
	return;
    }
    
    int fl_mat = 0, fl_tile = 0, fl_mode = BM_CODEDBAD;
    int up_mat = 0, up_tile = 0, up_mode = BM_CODEDBAD;
    int gr_mat = 0, gr_amt = 0;
    uint designation = 0u;
    
    decode_tile(map_posn, fl_mat, fl_tile, up_mat, up_tile, gr_mat, gr_amt, designation);

    liquicolor = liquimount(designation);
    stuff = ivec4(0, 0, mouse_here(), hidden(designation));
}

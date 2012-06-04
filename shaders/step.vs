#version 130
#pragma debug(on)

/* blend modes */
#define BM_NONE         0u   // discard.
#define BM_ASIS         1u   // no blend.
#define BM_CLASSIC      2u
#define BM_FGONLY       3u
#define BM_OVERSCAN     254u
#define BM_CODEDBAD     255u   // filler insn

uniform usampler2DArray screen;   // mapdata under traditional name
uniform usampler2D      dispatch; // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA32UI ARRAY

uniform ivec3 mapsize;
uniform ivec3 origin;                   // render_origin
uniform ivec2 gridsize;
uniform  vec3 pszar;
uniform ivec2 mouse_pos;
uniform  int  show_hidden;
uniform  int frame_no;
uniform ivec4 txsz;               // { w_tiles, h_tiles, max_tile_w, max_tile_h } <- font texture params.

in ivec2 position;                      // tiles relative to the render_origin; df cs.

flat out uvec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat out  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall
flat out  vec4 fl_fg, fl_bg; 	        // floor or the only blit

flat out uvec4 debug0;
flat out uvec4 debug1;

void decode_tile(in ivec3 posn, 
                 out uint fmat, out uint ftile,
                 out uint umat, out uint utile, 
                 out uint gmat, out uint gamt, 
                 out uint des) {
    
    uvec4 vc = texelFetch(screen, posn, 0);
    
    fmat  = vc.r >> 16u;
    ftile = vc.r & 65535u;
    umat  = vc.g >> 16u;
    utile = vc.g & 65535u;
    gamt  = vc.b >> 16u;
    gmat  = vc.b & 65535u;
    des   = vc.a;
}

void decode_insn(in uint mat, in uint tile, out uint mode, out vec4 fg, out vec4 bg) {
    mode = BM_CODEDBAD;
    fg = vec4(1,0,0,1);
    bg = vec4(0,0,0,0);
    
    uvec4 addr = texelFetch(dispatch, ivec2(int(mat), int(tile)), 0);
    
    debug0 = uvec4(mat, tile, addr.x, addr.y);
    
    addr.z = uint(frame_no);
    uvec4 insn = texelFetch(blitcode, ivec3(addr.xyz), 0);
    
    debug1 = uvec4(insn.x >>8u, insn.x & 0xffu, insn.z>>8u, insn.w>>8u);
    
    mode = insn.x;
    fg = vec4(insn.z>>24u, (insn.z>>16u ) &0xffu, (insn.z>>8u ) &0xffu, insn.z & 0xffu) / 256.0;
    bg = vec4(insn.w>>24u, (insn.w>>16u ) &0xffu, (insn.w>>8u ) &0xffu, insn.w & 0xffu) / 256.0;
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
    vec2 posn = 2.0 * (vec2(position.x, gridsize.y - position.y - 1) + 0.5)/gridsize - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;
    
    stuff = uvec4(0,0,0,0);
    debug0 = uvec4(0,0,0,0);
    debug1 = uvec4(0,0,0,0);
    
    ivec3 map_posn = ivec3(position, 0) + origin;
    if (   any(        lessThan(map_posn, ivec3(0,0,0)))
        || any(greaterThanEqual(map_posn, mapsize))) {
        stuff = uvec4(BM_OVERSCAN, 0, 0, 0);
        return;
    }
    
    uint fl_mat = 0u, fl_tile = 0u; uint fl_mode = BM_CODEDBAD;
    uint up_mat = 0u, up_tile = 0u; uint up_mode = BM_CODEDBAD;
    uint gr_mat = 0u, gr_amt = 0u;
    uint designation = 0u;
       
    decode_tile(map_posn, fl_mat, fl_tile, up_mat, up_tile, gr_mat, gr_amt, designation);
    decode_insn(fl_mat, fl_tile, fl_mode, fl_fg, fl_bg);
    
    liquicolor = liquimount(designation);
    stuff = uvec4(fl_mode, 0, mouse_here(), hidden(designation));
}

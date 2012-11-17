#version 130
#pragma debug(on)

/* blend modes */
#define BM_NONE         0u   // discard.
#define BM_ASIS         1u   // no blend.
#define BM_CLASSIC      2u
#define BM_FGONLY       3u
#define BM_OVERSCAN     254u
#define BM_CODEDBAD     255u   // filler insn

/* tile flags */
#define TF_GRASS        1u
#define TF_FAKEFLOOR    2u
#define TF_TRUEFLOOR    4u
#define TF_VOID         8u
#define TF_UNKNOWN     16u
#define TF_PLANT       32u
#define TF_NONMAT      64u

/* builtin materials */
#define BMAT_NONE               0u

#define TILETYPECOUNT   699     // tile types

uniform uint tileflags[TILETYPECOUNT];

uniform usampler2DArray screen;   // mapdata under traditional name
uniform usampler2D      dispatch; // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA32UI ARRAY

uniform ivec3 mapsize;
uniform ivec3 origin;                   // render_origin
uniform ivec2 gridsize;
uniform  vec3 pszar;
uniform ivec2 mouse_pos;
uniform  int  show_hidden;
uniform uint  frame_no;

in ivec2 position;                      // tiles relative to the render_origin; df cs.

flat out uvec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat out  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall
flat out  vec4 fl_fg, fl_bg; 	        // floor or the only blit
flat out  vec4 up_fg, up_bg; 	        // object or none blit

flat out uvec4 debug0;
flat out uvec4 debug1;

void decode_tile(const in uvec4 vc,
                 out uint fmat, out uint ftile,
                 out uint umat, out uint utile, 
                 out uint gmat, out uint gamt, 
                 out uint des) {
    
    fmat  = vc.r >> 16u;
    ftile = vc.r & 65535u;
    umat  = vc.g >> 16u;
    utile = vc.g & 65535u;
    gamt  = vc.b >> 16u;
    gmat  = vc.b & 65535u;
    des   = vc.a;
}

void decode_insn(in uint mat, in uint tile, in uint fudge, out uint mode, out vec4 fg, out vec4 bg) {
    mode = BM_CODEDBAD;
    fg = vec4(1,0,0,1);
    bg = vec4(0,0,0,0);
    
    uvec4 addr = texelFetch(dispatch, ivec2(int(mat), int(tile)), 0);
    
    debug0 = uvec4(mat, tile, addr.x, addr.y);
    
    uint framecount = addr.x >> 8u;
    addr.x = addr.x & 0xffu;

    addr.z = (frame_no + fudge) % framecount;
    
    uvec4 insn = texelFetch(blitcode, ivec3(addr.xyz), 0);
    
    debug1 = uvec4(insn.x >>8u, insn.x & 0xffu, insn.z>>8u, insn.w>>8u);
    
    mode = insn.x;
    fg = vec4(insn.z>>24u, (insn.z>>16u ) &0xffu, (insn.z>>8u ) &0xffu, insn.z & 0xffu) / 256.0;
    bg = vec4(insn.w>>24u, (insn.w>>16u ) &0xffu, (insn.w>>8u ) &0xffu, insn.w & 0xffu) / 256.0;
}

int check_a_floor(const in uvec4 vc, inout uint mat, inout uint tile) {
    uint ftile, fmat, btile, bmat, gamt, gmat, des;
    
    decode_tile(vc, fmat, ftile, bmat, btile, gmat, gamt, des);
    
    if ((tileflags[ftile] & TF_TRUEFLOOR) > 0u ) {
        tile = ftile;
        if ((tileflags[ftile] & TF_GRASS) > 0u) {
            mat = gmat;
            return 1; // prefer grass
        } else {
            mat = fmat;
        }
    }
    return 0;
}

const ivec2 fafl_0p = ivec2(0,1);
const ivec2 fafl_0m = ivec2(0,-1);
const ivec2 fafl_p0 = ivec2(1,0);
const ivec2 fafl_m0 = ivec2(-1,0);
const ivec2 fafl_pp = ivec2(1,1);
const ivec2 fafl_mp = ivec2(-1,1);
const ivec2 fafl_mm = ivec2(-1,-1);
const ivec2 fafl_pm = ivec2(1,-1);


void fake_a_floor(in ivec3 posn, inout uint mat, inout uint tile) {
    tile = 0u; mat = 0u;
    
    uvec4 vc = texelFetchOffset(screen, posn, 0, fafl_0p);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_0m);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_p0);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_m0);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_pp);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_mp);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_pm);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    vc = texelFetchOffset(screen, posn, 0, fafl_mm);
    if (check_a_floor(vc,  mat, tile) > 0) return;

    
    /* here if we haven't found any grass floor nearby */
    if (tile != 0u) {
        /* but we found *some* floor, return it. */
        return;
    }
    /* here if there ain't no floor around; invent one.
       take the fl_mat? hmm? aww. 
        TREE SHRUB SAPLING PEBBLES BOULDER STAIR_UP
       those are the fakefloor tiles.
       guess this needs some lookup table.
    
        in the meanwhile, just return zeroes.
    */
    return;
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
    uint fake_mat = 0u, fake_tile = 0u;
    
    /* animation fudge factor to break the lockstep */
    uint fudge = uint(map_posn.x * map_posn.y * map_posn.z);
       
    decode_tile(texelFetch(screen, map_posn, 0), fl_mat, fl_tile, up_mat, up_tile, gr_mat, gr_amt, designation);
    
    uint fl_flags = tileflags[fl_tile];
    uint up_flags = tileflags[up_tile];
    
    if ((fl_flags & TF_GRASS) > 0u)
        fl_mat = gr_mat;
    if ((fl_flags & TF_PLANT) > 0u)
        fl_mat = up_mat;
    if ((fl_flags & TF_NONMAT) > 0u)
        fl_mat = BMAT_NONE;

#if 1
    if ((fl_flags & TF_FAKEFLOOR) > 0u) {
        fake_a_floor(map_posn, fake_mat, fake_tile);
    }

    if (fake_tile != 0u) {
        // real tile gets decoded into up_* variables
        decode_insn(fl_mat, fl_tile, fudge, up_mode, up_fg, up_bg);
        // fake tile gets decoded into fl_* variables
        decode_insn(fake_mat, fake_tile, fudge, fl_mode, fl_fg, fl_bg);
    } else { // business as usual
        decode_insn(fl_mat, fl_tile, fudge, fl_mode, fl_fg, fl_bg);
    }
#else
    decode_insn(fl_mat, fl_tile, fudge, fl_mode, fl_fg, fl_bg);
    
#endif
    // here do something if up_tile !=0: i.e. a building or something.
    
    liquicolor = liquimount(designation);
    stuff = uvec4(fl_mode, up_mode, mouse_here(), hidden(designation));
}

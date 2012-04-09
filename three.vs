#version 130
#line 2 0

/* length of tileclass/flag array */
#define TILECOUNT 519

/* blend modes */
#define BM_NONE         0   // discard.
#define BM_ASIS         1   // no blend.
#define BM_CLASSIC      2
#define BM_FGONLY       3
#define BM_BAD_DISPATCH 4   // addr = (0,0), not actually used in blitcode
#define BM_CODEDBAD     5   // filler insn

/* flag/class values can be redefined in raws. see tileclasses.txt*/
#define TC_MASK         255     // 0x00FF   // 256 classes
#define TCF_MASK        65280   // 0xFF00   // 8 flags

#define TCF_FAKEFLOOR   256     // 0x0100   // this tile needs a fakefloor
#define TCF_VEG         512     // 0x0200   // vegetation: always have TCF_FAKEFLOOR
#define TCF_WATER       1024    // 0x0400   // river, brook
#define TCF_TRUEFLOOR   2048    // 0x0800   // this tile is a floor

#define TC_GENERIC      0
#define TC_STONE        1
#define TC_SOIL         2
#define TC_GRASS        3
#define TC_MINERAL      4
#define TC_CONSTRUCTED  5
#define TC_FEATURE      6
#define TC_LAVA         7
#define TC_FROZEN       8
#define TC_RIVER        9
#define TC_BROOK        10
#define TC_VEGETATION   11


uniform usampler2DArray screen;   // mapdata under traditional name
uniform usampler2D      dispatch; // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA32UI ARRAY

uniform  int  frame_no;
uniform int show_hidden;
uniform ivec3 origin;
uniform ivec2 grid;
uniform  vec3 pszar;               // { parx, pary, psz }
uniform ivec2 mouse_pos;
uniform int tileclass[TILECOUNT];
uniform ivec4 txsz;               // { w_tiles, h_tiles, max_tile_w, max_tile_h } <- font texture params.

in ivec2 position;

/* should have at least 8 on most GL3 cards.
   blit is ( s, t, txsz_s, txsz_t ) */
flat out  vec4 up_blit, up_fg, up_bg; 	// possible 'upper' blit on top of [fake]floor
flat out  vec4 fl_blit, fl_fg, fl_bg; 	// floor or the only blit 
flat out ivec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat out  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall


flat out ivec4 debug0;			// do_dump, value, unused, unused
flat out ivec4 debug1;
flat out ivec4 debug2;
flat out ivec4 debug3;

void decode_tile(in ivec2 offs, 
                 out int mat,  out int tile,
                 out int bmat, out int btile, 
                 out int gmat, out int gamt, 
                 out uint des) {
    uvec4 vc = texelFetch(screen, origin + ivec3(position.x + offs.x, position.y + offs.y, 0), 0);
    mat   = int(vc.r >> 16u);
    tile  = int(vc.r & 65535u);
    bmat  = int(vc.g >> 16u);
    btile = int(vc.g & 65535u);
    gamt  = int(vc.b >> 16u);
    gmat  = int(vc.b & 65535u);
    des   = vc.a;
}

void decode_insn(in int mat, in int tile, out int mode, out vec4 blit, out vec4 fg, out vec4 bg, out ivec2 iblit) {
    mode = BM_BAD_DISPATCH;
    blit = vec4(0,0,0,0);
    fg = vec4(1,0,0,1);
    bg = vec4(0,0,0,0);
    
    uvec4 addr = texelFetch(dispatch, ivec2(int(mat), int(tile)), 0);
    debug2 = ivec4(1,addr.x,0,0);
    debug3 = ivec4(1,addr.y,0,0);	
    if ((addr.x == 0u) && (addr.y == 0u)) return; // dispatched to 00: hmm
    
    addr.z = uint(frame_no);
    uvec4 insn = texelFetch(blitcode, ivec3(addr.xyz), 0);
    iblit = ivec2(int(insn.x >> 16u), int(insn.x & 65535u));
    blit.x = float( iblit.x ) / txsz.x;
    blit.y = float( iblit.y ) / txsz.y;
    blit.zw = 1.0 / vec2(txsz.xy); // for as long as we don't support tiles-smaller-than-txsz.zw
    
    mode = int(insn.y);
    fg = vec4(insn.z>>24u, (insn.z>>16u ) &0xffu, (insn.z>>8u ) &0xffu, insn.z & 0xffu) / 256.0;
    bg = vec4(insn.w>>24u, (insn.w>>16u ) &0xffu, (insn.w>>8u ) &0xffu, insn.w & 0xffu) / 256.0;
}

int check_a_floor(in ivec2 offs, inout int tile, inout int mat) {
    int ftile, fmat, btile, bmat, gamt, gmat;
    uint des;
    
    decode_tile(offs, ftile, fmat, btile, bmat, gamt, gmat, des);
    
    if ((tileclass[ftile] & TCF_TRUEFLOOR) > 0 ) {
        tile = ftile;
        if ((tileclass[ftile] & TCF_MASK) == TC_GRASS) {
            mat = gmat;
            return 1; // prefer grass
        } else {
            mat = fmat;
        }
    }
    return 0;
}

void find_a_floor(out int tile, out int mat) {
    tile = 0; mat = 0;
    
    if (check_a_floor(ivec2( 0,  1), tile, mat) > 0) return; 
    if (check_a_floor(ivec2( 0, -1), tile, mat) > 0) return;
    if (check_a_floor(ivec2( 1,  0), tile, mat) > 0) return;
    if (check_a_floor(ivec2(-1,  0), tile, mat) > 0) return;
    
    if (check_a_floor(ivec2( 1,  1), tile, mat) > 0) return;
    if (check_a_floor(ivec2(-1,  1), tile, mat) > 0) return;
    if (check_a_floor(ivec2(-1, -1), tile, mat) > 0) return;
    if (check_a_floor(ivec2( 1, -1), tile, mat) > 0) return;
    
    
    if ((tileclass[tile] & TCF_TRUEFLOOR) == 0 ) {
        return;
    }
    /* todo: make a guess 
    if (tile == 0u) {
    // detectorzor
        tile = 201u;  mat  = 179u; // dacite stonewall
    }
    */
}

void liquimount(in uint designation) {
    if ((designation & 7u) > 0u) {
        float amount = float(designation & 7u)/7.0; // normalized liquid amount
	if (((designation >>21u) & 1u ) == 1u) {
	    liquicolor = vec4(amount, amount, 0.0, 1.0);
	} else {
	    liquicolor = vec4(0.0, 0.1*amount, amount, 1.0);
	}
    } else {
	liquicolor = vec4(0,0,0,0);
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
    /*  normalize grid indices to viewport coords {(-1,1),(-1,1)},
	taking into account cel aspect ratio */
    //vec2 posn = 2.0 * pszar.xy*(position + 0.5)/grid - 1.0;
    vec2 posn = 2.0 * (position + 0.5)/grid - 1.0;  // temporarily not taking.
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;

    int fl_mat = 0, fl_tile = 0, fl_mode = BM_CODEDBAD;
    int up_mat = 0, up_tile = 0, up_mode = BM_CODEDBAD;
    int gr_mat = 0, gr_amt = 0;
    uint designation = 0u;
    
    decode_tile(ivec2(0,0), fl_mat, fl_tile, up_mat, up_tile, gr_mat, gr_amt, designation);

    liquimount(designation);

    int tflag  = tileclass[fl_tile] & TCF_MASK;
    int tclass = tileclass[fl_tile] & TC_MASK;

    debug0 = ivec4(fl_mat, fl_tile, up_mat, up_tile);
    debug1 = ivec4(gr_mat, gr_amt, tflag, tclass);
    
    int mode = BM_CODEDBAD;
    vec4 blit, fg, bg;
    
    // can't rely on grass_amount (wtf?).
    ivec2 fl_iblit, up_iblit;
    if ( tclass == TC_GRASS ) {
	decode_insn(gr_mat, fl_tile, mode, blit, fg, bg, fl_iblit);
	fl_mode = mode;
	fl_blit = blit;
	fl_fg = fg;
	fl_bg = bg;
	up_mode = BM_NONE; // no upper blit
    } else {
	decode_insn(fl_mat, fl_tile, mode, blit, fg, bg, fl_iblit);
	fl_mode = mode;
	fl_blit = blit;
	fl_fg = fg;
	fl_bg = bg;
	up_mode = BM_NONE; // no upper blit
#if 0
        if ((tflag & TCF_FAKEFLOOR) > 0) { // gotta fake a floor for this one
	    up_mode = fl_mode;
	    up_blit = fl_blit;
	    up_fg = fl_fg;
            up_bg = fl_bg;
	    up_iblit = fl_iblit;
            if ( (tflag & TCF_VEG) == 0 )
                up_mat = fl_mat;
            find_a_floor(fl_mat, fl_tile);
	    decode_insn(gr_mat, fl_tile, mode, blit, fg, bg, fl_iblit);
	    fl_mode = mode;
	    fl_blit = blit;
	    fl_fg = fg;
	    fl_bg = bg;
        }
#endif
    }
    debug2 = ivec4(fl_mode, fl_iblit.x, fl_iblit.y, 0);
    debug3 = ivec4(up_mode, up_iblit.x, up_iblit.y, 0);
    stuff = ivec4(up_mode, fl_mode, mouse_here(), hidden(designation)); 
}



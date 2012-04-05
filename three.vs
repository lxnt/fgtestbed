#version 130
#line 2 0
#define TILECOUNT 519

uniform usampler2DArray screen;   // mapdata under traditional name

uniform  int  frame_no;
uniform ivec3 origin;
uniform ivec2 grid;
uniform  vec3 pszar;               // { parx, pary, psz }
uniform ivec2 mouse_pos;
uniform int tileclass[TILECOUNT];

/* fgtestbed$ egrep '(tilec|tcfl)' fgraws/tileclasses.txt 
[tcflag:fakefloor:0]
[tcflag:floor:1]
[tcflag:ramp:2]
[tcflag:flow:3]
[tileclass:stone:1]
[tileclass:soil:2]
[tileclass:grass:3]
[tileclass:mineral:4]
[tileclass:constructed:5]
[tileclass:feature:6]
[tileclass:lava:7]
[tileclass:frozen:8]
[tileclass:river:9]
[tileclass:brook:10]
[tileclass:vegetation:11] */

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


in ivec2 position; 

flat out  int mouse_here;
flat out uint floor_mat;
flat out uint floor_tile;
flat out uint upper_mat;
flat out uint upper_tile;
flat out uint designation;

void decode_tile(int dx, int dy, 
                 inout uint mat, inout uint tile, 
                 inout uint bmat, inout uint btile, 
                 inout uint gmat, inout uint gamt, 
                 inout uint des) {
    uvec4 vc = texelFetch(screen, origin + ivec3(position.x + dx, position.y + dy, 0), 0);
    mat   = vc.r >> 16u;
    tile  = vc.r & 0xffffu;
    bmat  = vc.g >> 16u;
    btile = vc.g & 0xffffu;
    gamt  = vc.b >> 16u;
    gmat  = vc.b & 0xffffu;
    des   = vc.a;
}

int check_a_floor(int dx, int dy, inout uint tile, inout uint mat) {
    uint ftile, fmat, btile, bmat, gamt, gmat, des;
    
    decode_tile(dx, dy, ftile, fmat, btile, bmat, gamt, gmat, des);
    
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

void find_a_floor(out uint tile, out uint mat) {
    tile = 0u; mat = 0u;
    
    if (check_a_floor( 0,  1, tile, mat) > 0) return; 
    if (check_a_floor( 0, -1, tile, mat) > 0) return;
    if (check_a_floor( 1,  0, tile, mat) > 0) return;
    if (check_a_floor(-1,  0, tile, mat) > 0) return;
    
    if (check_a_floor( 1,  1, tile, mat) > 0) return;
    if (check_a_floor(-1,  1, tile, mat) > 0) return;
    if (check_a_floor(-1, -1, tile, mat) > 0) return;
    if (check_a_floor( 1, -1, tile, mat) > 0) return;
    
    
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

void main() {
    vec2 normposn = (position + 0.5)/grid;
    normposn.y = 1.0 - normposn.y;
    vec2 posn = 2.0 * pszar.xy*normposn - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;

    if  (mouse_pos == position)
	mouse_here = 23;
    else
	mouse_here = 0;

    uint fl_mat = 0u, fl_tile = 0u;
    uint up_mat = 0u, up_tile = 0u;
    uint gr_mat = 0u, gr_amt = 0u;
    
    decode_tile(0, 0, fl_mat, fl_tile, up_mat, up_tile, gr_mat, gr_amt, designation);
    
    int tflag  = tileclass[fl_tile] & TCF_MASK;
    int tclass = tileclass[fl_tile] & TC_MASK;
    
    // can't rely on grass_amount (wtf?).
    if ( tclass == TC_GRASS ) {
        fl_mat = gr_mat;
    } else {
        if ((tflag & TCF_FAKEFLOOR) > 0) { // gotta fake a floor for this one
            up_tile = fl_tile;
            if ( (tflag & TCF_VEG) == 0 )
                up_mat = fl_mat;
            find_a_floor(fl_mat, fl_tile);
        }
    }
    
    floor_mat = fl_mat;
    floor_tile = fl_tile;
    upper_mat = up_mat;
    upper_tile = up_tile;
}


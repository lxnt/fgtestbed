#version 120
#line 2 0

uniform sampler2D dispatch; // blit_insn to blitcode_idx lookup table
uniform sampler2D blitcode; // w*2*128* x h contains both blit and blend insns. w is fixed at 8. 
			    // h is not really fixed, set at 512 for now, giving 4K tiles in 4MB of space

uniform sampler2D font;
uniform sampler2D txco;

uniform float final_alpha;
uniform vec3 pszar;             // { Parx, Pary, Psz }
uniform vec4 txsz;              // { w_tiles, h_tiles, max_tile_w, max_tile_h }
uniform float frame_no;

varying vec2 crap;        // computed rendering and positioning | blithash texcoords : ( tile_id, mat_id ) in fact

vec2 idx2texco(float idx, float w, float h) {
    vec2 rv;
    rv.x = fract( idx / w );  	    // normalized coords 
    rv.y = floor( idx / w ) / h;    // into font texture - "offset"
    return rv;
}

vec4 idx2texco_txco(float idx) {
    vec4 rv;
    
    rv.xy = idx2texco(idx, txsz.x, txsz.y);

    vec4 tile_size = texture2D(txco, rv.xy);
    rv.zw = tile_size.xy*(256.0/txsz.zw); // pixel size of the tile normalized to maxtilesize
    
    return rv;
}

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0)) {
        discard;
    }
    
    vec4 blcoderef = texture2D(dispatch, crap); // index into blitcode for given blit_insn
    
    vec2 frame_coords = idx2texco(blcoderef.r, 8, 512); // this points to 0th frame.
    frame_coords.x += frame_no / 1024; // 1024 since each frame takes up 2 texels
    
    vec4 tile_idx = texture2D(blitcode, frame_coords);
    
    frame_coords.x += 1 / 2048; // shift to blend
    vec4 blend_color = texture2D(blitcode, frame_coords);
    
    
    vec4 tile = idx2texco_txco(tile_idx.r);
    
    vec2 texcoords = vec2 (tile.x + (pc.x/txsz.x)*tile.z,
                           tile.y + (pc.y/txsz.y)*tile.w );

    vec4 tile_color = texture2D(font, texcoords);
    gl_FragColor = mix(tile_color, blend_color, 1.0 - tile_color.a);
    gl_FragColor.rg = crap;
    gl_FragColor.b = 1.0;
    gl_FragColor.a = final_alpha;
}

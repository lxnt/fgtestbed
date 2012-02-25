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

varying float crap;        // computed rendering and positioning | blit_insn : ( tile_id, mat_id ) in fact

vec2 idx2texco(float idx, float w, float h) {
    vec2 rv;
    rv.x = fract( idx / w );  	    // normalized coords
    rv.y = floor( idx / w ) / h;    // into a wXh texture
    return rv;
}

vec4 blit_decode(vec4 blit_insn) {
// for the time being, blit_insn.xy are tile coords in 0-255 range, normalized.
// should multiply them by 256/actual_tex_sz_in tiles to get actual tex coords.

    vec4 rv;
    rv.xy = blit_insn.xy * (256.0 / txsz.xy );

    vec4 tile_size = texture2D(txco, rv.xy); // we get this tile image's actual dimensions
    rv.zw = tile_size.xy*(256.0/txsz.zw); // pixel size of the tile normalized to maxtilesize
    
    return rv;
}

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0)) {
        discard;
    }
    
    vec4 bcr = texture2D(dispatch, idx2texco(crap, 1024.0, 1024.0)); // index into blitcode for given blit_insn
    float coderef = bcr.a*256.0; // denormalize this shit
    vec2 frame_coords = idx2texco(coderef, 8.0, 32.0); // this points to 0th frame.
    frame_coords.x += frame_no / 1024.0; // 1024 since each frame takes up 2 texels
    
    vec4 blit_insn = texture2D(blitcode, frame_coords);
    
    frame_coords.x += 1.0 / 2048.0; // shift to blend
    vec4 blend_color = texture2D(blitcode, frame_coords);
    
    vec4 tile = blit_decode(blit_insn);
    
    vec2 texcoords = vec2 (tile.x + (pc.x/txsz.x)*tile.z,
                           tile.y + (pc.y/txsz.y)*tile.w );

    vec4 tile_color = texture2D(font, texcoords);
    gl_FragColor = mix(tile_color, blend_color, 1.0 - tile_color.a);
    gl_FragColor.rg = idx2texco(crap, 1024.0, 1024.0);
    gl_FragColor.a = final_alpha;
    //gl_FragColor = bcr;
    //gl_FragColor.rgb = vec3 ( 32.0/256.0, 64.0/256.0, 128.0/256.0);
    
}

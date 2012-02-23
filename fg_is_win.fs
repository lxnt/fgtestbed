#version 120
#line 2 0

uniform sampler3D blitcode;
uniform sampler3D blendcode;

uniform sampler2D dispatch;
uniform sampler2D font;
uniform sampler2D txco;

uniform float final_alpha;
uniform vec3 pszar;             // { Parx, Pary, Psz }
uniform vec4 txsz;              // { w_tiles, h_tiles, max_tile_w, max_tile_h }
uniform float frame_no;

varying vec2 crap;        // computed rendering and positioning | blithash texcoords : ( tile_id, mat_id ) in fact


vec4 idx2texco(float idx) {
    vec4 tile_size;
    vec4 rv;
    
    /*
    if (idx < 0) // crap out
    	idx = 0.0;
    */
    rv.x = fract( idx / txsz.x );  	    // normalized coords 
    rv.y = floor( idx / txsz.x ) / txsz.y;  // into font texture - "offset"

    tile_size = texture2D(txco, rv.xy);
    rv.zw = tile_size.xy*(256.0/txsz.zw); // pixel size of the tile normalized to maxtilesize
    
    return rv;
}

vec3 idx3texco(float idx, float w, float h) { // assuming 1-pix wide tiles
    vec3 rv;
    rv.x = fract( idx / w );  	    // normalized coords 
    rv.y = floor( idx / w ) / h;    // into font texture - "offset"
    rv.z = frame_no;
    return rv;
}

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0)) {
        discard;
    }
    
    vec4 blinsnref = texture2D(dispatch, crap); // index into blitcode for given blit_insn
    
    vec3 bcf = idx3texco(blinsnref.r, 1024.0, 1024.0); // index into font for particular frame of given blit_insn
    
    vec4 tile_idx = texture3D(blitcode, bcf);
    vec4 blend_color = texture3D(blendcode, bcf); 
    
    vec4 tile = idx2texco(tile_idx.r);
    
    vec2 texcoords = vec2 (tile.x + (pc.x/txsz.x)*tile.z,
                           tile.y + (pc.y/txsz.y)*tile.w );

    vec4 tile_color = texture2D(font, texcoords);
    gl_FragColor = mix(tile_color, blend_color, 1.0 - tile_color.a);
    gl_FragColor.a = final_alpha;
}

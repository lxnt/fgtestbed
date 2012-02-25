#version 130
#line 2 0
precision highp int;
precision highp float;

uniform usampler2D dispatch; 	  // blit_insn to blitcode_idx lookup table. Texture is GL_RG16UI.
uniform usampler2DArray blitcode; // blit and blend insns. Texture is GL_RGBA16UI ARRAY
uniform int frame_no;
uniform ivec4 txsz;              // { w_tiles, h_tiles, max_tile_w, max_tile_h } <- font texture params.
uniform int dispatch_row_len;
uniform vec2 viewpoint;			
uniform vec3 pszar; 			// { parx, pary, psz }

in vec2 position;
in int screen;

flat out vec4 blit;
flat out vec4 blend;
flat out vec4 debug;

void main() {
    vec2 posn = pszar.xy*position*pszar.z - viewpoint;     
    gl_Position = gl_ModelViewProjectionMatrix*vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;

    uvec4 addr;
    addr = texelFetch(dispatch, ivec2( screen % dispatch_row_len, screen / dispatch_row_len ), 0 );
    addr.z = uint(frame_no);

    if ((addr.x + addr.y) == 0u) {
	blit = vec4(0,0,0,0);
	blend = vec4(0,0,0,0);
	return;
    }

    uvec4 insn = texelFetch(blitcode, ivec3(addr.xyz), 0);
    
    blit.xy = vec2(insn.xy)/ vec2(txsz.xy) ;

    blit.zw = 1.0 / vec2(txsz.xy) ; // for as long as we don't support tiles-smaller-than-txsz.zw
    
    blend = vec4(insn.z >> 8, insn.z & 0xffu, insn.w >> 8, insn.z & 0xffu) / 256.0;
  

    //float fs = float( addr.x * 8.0 );
    //debug = vec4( fract(fs/ (65536.0*256.0) ), fract(fs/ 65536.0), fract(fs/256.0), 1.0);
    //debug = vec4( float(addr.x)/1024, float(addr.y)/1024, 0, 1);
    //debug=blit;
    debug = vec4( float(addr.x)/6.0, float(addr.y)/6.0, float(addr.z)/128.0, 1.0);
    
    //debug = vec4( blit.x, blit.y, float(addr.z)/128.0, 1.0); 
    
}

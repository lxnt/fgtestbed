#version 130
#line 2 0
precision highp int;
precision highp float;

uniform sampler2D font;

uniform float final_alpha;
uniform vec3 pszar;             // { Parx, Pary, Psz }
uniform float darken;  // drawing lower levels.
uniform vec4 mouse_color;

flat in vec4 blit;   // fka 'tile', but zw are pre-divided with txsz.xy
flat in vec4 fg;
flat in vec4 bg;
flat in float mode;
flat in float mouse_here;

out vec4 color;

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0) || (blit.z == 0)) {
        discard;
    }
    
    vec2 texcoords = vec2 (blit.x + pc.x * blit.z, blit.y + pc.y * blit.w );
    vec4 tile_color = texture2D(font, texcoords);
    if (mode > 0) {
	color = fg * tile_color * darken;
    } else {
	color = mix(tile_color * fg, bg, 1.0 - tile_color.a) * darken;
    }
    
    if (mouse_here > 0) {
	pc = gl_PointCoord * pszar.xy * pszar.z;
	float w = 1.0;
	if (pszar.z > 29.0) { w = 2.0; }
	if (   (pc.x < w) || (pc.x > pszar.z*pszar.x - w) 
	    || (pc.y < w) || (pc.y > pszar.z*pszar.y - w) ) {
	    color = mouse_color;
	}
    }
    color.a = final_alpha;    
}

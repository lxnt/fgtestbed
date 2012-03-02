#version 130
#line 2 0
precision highp int;
precision highp float;

uniform sampler2D font;

uniform vec3 pszar;             // { Parx, Pary, Psz }
uniform float darken;  // drawing lower levels.
uniform vec4 mouse_color;
uniform int show_hidden;

flat in vec4 blit;   // fka 'tile', but zw are pre-divided with txsz.xy
flat in vec4 fg;
flat in vec4 bg;
flat in int mode;  /* -1 - no tile ; 0 - open space ; 1 - classic ; 2 - just blit */
flat in int mouse_here;
flat in uint des;

out vec4 color;

void main() {

    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0)) {
        discard;
    }
    
    if ( ( show_hidden == 0) && (((des >>9u) & 1u) == 1u)) {
	discard;
    }
    
    vec2 texcoords = vec2 (blit.x + pc.x * blit.z, blit.y + pc.y * blit.w );
    vec4 tile_color = texture2D(font, texcoords);
    
    switch (mode) {
	case 2:
	    color = fg * tile_color * darken;
	    break;
	case 1:
	    color = mix(tile_color * fg, bg, 1.0 - tile_color.a) * darken;
	    break;
	case 0:
	    color = vec4(1.0,1.0,1.0,0.0);
	    break;
	case -1:
	default:
	    discard;
    }
    
    if ((des & 7u) > 0u) {
	vec4 liquicolor;
	if (((des >>21u) & 1u ) == 1u) {
	    liquicolor = vec4(float(des & 7u)/7.0, 0.1*float(des & 7u)/7.0, 0.0, 1.0);
	} else {
	    liquicolor = vec4(0.0, 0.1*float(des & 7u)/7.0, float(des & 7u)/7.0, 1.0);
	}
	if (mode != 0) {
	    color = mix(liquicolor, color, 0.5);
	} else {
	    color = liquicolor;
	    color.a = 0.5*float(des & 7u)/7.0;
	}
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

}

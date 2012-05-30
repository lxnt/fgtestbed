#version 130
#line 2 0


uniform ivec3 mapsize;
uniform ivec3 origin;                   // render_origin
uniform ivec2 gridsize;
uniform  vec3 pszar;
uniform ivec2 mouse_pos;

in ivec2 position;                      // tiles relative to the render_origin; df cs.

flat out ivec4 stuff;      		// up_mode, fl_mode, mouse, hidden

void main() { 
    vec2 posn = 2.0 * (vec2(position.x, gridsize.y - position.y) + 0.5)/gridsize - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;
    
    stuff = ivec4(0,0,0,0);
    
    ivec3 map_posn = ivec3(position, 0) + origin;
    if (any(lessThan(map_posn, ivec3(0,0,0)))
	|| any(greaterThanEqual(map_posn, mapsize))) {
	stuff = ivec4(-1,-1,-1,-1);
	return;
    }
    
    if (mouse_pos == position)
	stuff.z = 23;

}

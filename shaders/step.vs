#version 130
#line 2 0

uniform ivec2 grid;                     // grid size
uniform  vec3 pszar;
uniform ivec2 mouse_pos;

in ivec2 position;                      // tiles relative to the render_origin; df cs.

flat out ivec4 stuff;      		// up_mode, fl_mode, mouse, hidden

void main() { 
    vec2 posn = 2.0 * (vec2(position.x, grid.y - position.y) + 0.5)/grid - 1.0;
    gl_Position = vec4(posn.x, posn.y, 0.0, 1.0);
    gl_PointSize = pszar.z;
    
    stuff = ivec4(0,0,0,0);
    
    if (mouse_pos == position)
	stuff.z = 23;
}

#version 130
#line 2 0

out vec4 frag;
uniform vec3 pszar;
uniform vec4 mouse_color;

flat in ivec4 stuff;      		// up_mode, fl_mode, mouse, hidden
flat in  vec4 liquicolor; 		// alpha < 0.1 -> no liquidatall

void borderglow(inout vec4 color, in vec4 border_color) {
    vec2 wh = pszar.xy * pszar.z;
    vec2 pc = gl_PointCoord * wh;
    float w = 1;
    if (pc.x > 29.0)  { w = 2 ; }
    if (   ( pc.x < w) || (pc.x > wh.x - w) 
	|| ( pc.y < w) || (pc.y > wh.y - w)) 
	color = border_color;
    return;
}

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0) || (stuff.x == -1))
        discard;
    
    vec4 color = vec4(gl_PointCoord, 0, 1);
    int mouse = stuff.z;
    int hidden = stuff.w;
        
    if (hidden > 0) {
	frag = vec4(0.5, 0.5, 0.5, 1.0);
	return;
    }
    if (liquicolor.a > 0.1)
	color = mix(liquicolor, color, 0.5);
    
    if (mouse > 0)
	borderglow(color, mouse_color);
    
    frag = color;

}

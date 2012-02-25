#version 120
#line 2 0
#pragma optimize(off)
#pragma debug(on)

uniform vec2 viewpoint;			
uniform vec3 pszar; 			// { parx, pary, psz }

attribute float screen;          // key into blithash 
attribute vec2 position;        // almost forgot teh grid

varying float crap;        // computed rendering and positioning

void main() {

    crap = screen;
    
    vec2 posn = pszar.xy*position*pszar.z - viewpoint;
     
    gl_Position = gl_ModelViewProjectionMatrix*vec4(posn.x, posn.y, 0.0, 1.0);
    //gl_PointSize = pszar.z;    
}

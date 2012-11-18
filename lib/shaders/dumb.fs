#version 130
#line 2 0

out vec4 frag;
uniform vec3 pszar;

void main() {
    vec2 pc = gl_PointCoord/pszar.xy;
    if ((pc.x > 1.0) || (pc.y > 1.0))
        discard;
    
    if ((pc.x*pszar.z < 2) || (pc.y*pszar.z < 2))
        frag = vec4(1,1,1,1);
    else
        frag = vec4(gl_PointCoord.xy, 0, 1);
}

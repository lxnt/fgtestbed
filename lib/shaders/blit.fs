#version 130
#line 2 0

#define M_FILL   1  // fill with color
#define M_BLEND  2  // texture it
#define M_OPAQUE 3  // force texture alpha to 1.0

uniform int mode;
uniform sampler2D tex;
uniform vec4 color;

in vec2 coord;
out vec4 frag;

void main() {
    switch(mode) {
        case M_FILL:
            frag = color;
            break;
        case M_BLEND:
            frag = texture(tex,  coord);
            break;
        case M_OPAQUE:
            frag = texture(tex,  coord);
            frag.a = 1.0;
            break;
        default:
            frag.rg = coord;
            frag.ba = vec2(0,1);
            break;
    }
}

import types
import colorsys 
import re

def hsv_to_rgb(*args):
    if len(args) == 1:
       h,s,v = args[0]
    else:
       h,s,v = args
    return colorsys.hsv_to_rgb(h,s,v)

def rgb_to_hsv(*args):
    if len(args) == 1:
       r,g,b = args[0]
    else:
       r,g,b = args
    return colorsys.rgb_to_hsv(r,g,b)

def string_to_rgb(s):
    try:
        s = s.lower()
        c = None
        if s in X11COLORS_BY_NAME:
            c = X11COLORS_BY_NAME[s][3]
        elif (len(s)==4 or len(s)==7) and s[0]=="#":
            hexpart = s[1:]
            if len(hexpart)==3:
                hexpart = hexpart[0]+hexpart[0]+hexpart[1]+hexpart[1]+hexpart[2]+hexpart[2]
            r = int(hexpart[0:2], 16)/255.0
            g = int(hexpart[2:4], 16)/255.0
            b = int(hexpart[4:6], 16)/255.0
            c = [r,g,b]
        else:
            s = s.replace(',',' ')
            if "." in s:
                c = map(float,s.split())
            else:
                c = map(lambda x: int(x)/255.0, s.split())
        return c
    except:
        return None

def rgb_to_string(rgb):
    return "#%02x%02x%02x"%(round(rgb[0]*255), round(rgb[1]*255), round(rgb[2]*255))

def bwcontrast(rgb):
    '''
    Returns either 0 (signifying black) or 1 (signifying white) depending
    on which contrasts better with the given rgb color.
    Args:
        rgb     (3-vector) The color to contrast with.
    Returns:
        0 (black) or 1 (white)
    '''
    lightness = 0.213*rgb[0] + 0.715*rgb[1] + 0.072*rgb[2]
    if lightness < 0.5:
        return 1
    else:
        return 0

def interpolate( cstart, cend, ncolors ):
    '''
    Returns a list of colors linearly interpolated between two
    specified colors. (In fact, this will linearly interpolate
    between any two vectors - they don't have to be colors or
    even of length 3.)
    Args:
        cstart  (color vector) The color to start at.
        cend    (color vector) The color to end at.
        ncolors (int) The number of colors in the final list.
                The result always includes cstart and cend, so ncolors
                should be >= 2,
    Returns:
        List of HSV color vectors. cstart is the first element,
        cend is the last.
    '''
    if ncolors < 2:
        return [cstart, cend]
    nsteps = ncolors - 1
    cdelta = []
    for i in range(len(cstart)):
        cdelta.append( float(cend[i]-cstart[i])/nsteps )
    colors = [cstart[:]]
    for i in range(nsteps):
        c = []
        for j in range(len(cstart)):
            v = cstart[j] + (i+1)*cdelta[j]
            if v > 1:
                v = math.fmod(v)
            c.append( v )
        colors.append(c)
    return colors

__X11COLORS__ = \
'''aliceblue\t#f0f8ff\t240,248,255
antiquewhite\t#faebd7\t250,235,215
aqua\t#00ffff\t0,255,255
aquamarine\t#7fffd4\t127,255,212
azure\t#f0ffff\t240,255,255
beige\t#f5f5dc\t245,245,220
bisque\t#ffe4c4\t255,228,196
black\t#000000\t0,0,0
blanchedalmond\t#ffebcd\t255,235,205
blue\t#0000ff\t0,0,255
blueviolet\t#8a2be2\t138,43,226
brown\t#a52a2a\t165,42,42
burlywood\t#deb887\t222,184,135
cadetblue\t#5f9ea0\t95,158,160
chartreuse\t#7fff00\t127,255,0
chocolate\t#d2691e\t210,105,30
coral\t#ff7f50\t255,127,80
cornflowerblue\t#6495ed\t100,149,237
cornsilk\t#fff8dc\t255,248,220
crimson\t#dc143c\t220,20,60
cyan\t#00ffff\t0,255,255
darkblue\t#00008b\t0,0,139
darkcyan\t#008b8b\t0,139,139
darkgoldenrod\t#b8860b\t184,134,11
darkgray\t#a9a9a9\t169,169,169
darkgreen\t#006400\t0,100,0
darkgrey\t#a9a9a9\t169,169,169
darkkhaki\t#bdb76b\t189,183,107
darkmagenta\t#8b008b\t139,0,139
darkolivegreen\t#556b2f\t85,107,47
darkorange\t#ff8c00\t255,140,0
darkorchid\t#9932cc\t153,50,204
darkred\t#8b0000\t139,0,0
darksalmon\t#e9967a\t233,150,122
darkseagreen\t#8fbc8f\t143,188,143
darkslateblue\t#483d8b\t72,61,139
darkslategray\t#2f4f4f\t47,79,79
darkslategrey\t#2f4f4f\t47,79,79
darkturquoise\t#00ced1\t0,206,209
darkviolet\t#9400d3\t148,0,211
deeppink\t#ff1493\t255,20,147
deepskyblue\t#00bfff\t0,191,255
dimgray\t#696969\t105,105,105
dimgrey\t#696969\t105,105,105
dodgerblue\t#1e90ff\t30,144,255
firebrick\t#b22222\t178,34,34
floralwhite\t#fffaf0\t255,250,240
forestgreen\t#228b22\t34,139,34
fuchsia\t#ff00ff\t255,0,255
gainsboro\t#dcdcdc\t220,220,220
ghostwhite\t#f8f8ff\t248,248,255
gold\t#ffd700\t255,215,0
goldenrod\t#daa520\t218,165,32
gray\t#808080\t128,128,128
green\t#008000\t0,128,0
greenyellow\t#adff2f\t173,255,47
grey\t#808080\t128,128,128
honeydew\t#f0fff0\t240,255,240
hotpink\t#ff69b4\t255,105,180
indianred\t#cd5c5c\t205,92,92
indigo\t#4b0082\t75,0,130
ivory\t#fffff0\t255,255,240
khaki\t#f0e68c\t240,230,140
lavender\t#e6e6fa\t230,230,250
lavenderblush\t#fff0f5\t255,240,245
lawngreen\t#7cfc00\t124,252,0
lemonchiffon\t#fffacd\t255,250,205
lightblue\t#add8e6\t173,216,230
lightcoral\t#f08080\t240,128,128
lightcyan\t#e0ffff\t224,255,255
lightgoldenrodyellow\t#fafad2\t250,250,210
lightgray\t#d3d3d3\t211,211,211
lightgreen\t#90ee90\t144,238,144
lightgrey\t#d3d3d3\t211,211,211
lightpink\t#ffb6c1\t255,182,193
lightsalmon\t#ffa07a\t255,160,122
lightseagreen\t#20b2aa\t32,178,170
lightskyblue\t#87cefa\t135,206,250
lightslategray\t#778899\t119,136,153
lightslategrey\t#778899\t119,136,153
lightsteelblue\t#b0c4de\t176,196,222
lightyellow\t#ffffe0\t255,255,224
lime\t#00ff00\t0,255,0
limegreen\t#32cd32\t50,205,50
linen\t#faf0e6\t250,240,230
magenta\t#ff00ff\t255,0,255
maroon\t#800000\t128,0,0
mediumaquamarine\t#66cdaa\t102,205,170
mediumblue\t#0000cd\t0,0,205
mediumorchid\t#ba55d3\t186,85,211
mediumpurple\t#9370db\t147,112,219
mediumseagreen\t#3cb371\t60,179,113
mediumslateblue\t#7b68ee\t123,104,238
mediumspringgreen\t#00fa9a\t0,250,154
mediumturquoise\t#48d1cc\t72,209,204
mediumvioletred\t#c71585\t199,21,133
midnightblue\t#191970\t25,25,112
mintcream\t#f5fffa\t245,255,250
mistyrose\t#ffe4e1\t255,228,225
moccasin\t#ffe4b5\t255,228,181
navajowhite\t#ffdead\t255,222,173
navy\t#000080\t0,0,128
oldlace\t#fdf5e6\t253,245,230
olive\t#808000\t128,128,0
olivedrab\t#6b8e23\t107,142,35
orange\t#ffa500\t255,165,0
orangered\t#ff4500\t255,69,0
orchid\t#da70d6\t218,112,214
palegoldenrod\t#eee8aa\t238,232,170
palegreen\t#98fb98\t152,251,152
paleturquoise\t#afeeee\t175,238,238
palevioletred\t#db7093\t219,112,147
papayawhip\t#ffefd5\t255,239,213
peachpuff\t#ffdab9\t255,218,185
peru\t#cd853f\t205,133,63
pink\t#ffc0cb\t255,192,203
plum\t#dda0dd\t221,160,221
powderblue\t#b0e0e6\t176,224,230
purple\t#800080\t128,0,128
red\t#ff0000\t255,0,0
rosybrown\t#bc8f8f\t188,143,143
royalblue\t#4169e1\t65,105,225
saddlebrown\t#8b4513\t139,69,19
salmon\t#fa8072\t250,128,114
sandybrown\t#f4a460\t244,164,96
seagreen\t#2e8b57\t46,139,87
seashell\t#fff5ee\t255,245,238
sienna\t#a0522d\t160,82,45
silver\t#c0c0c0\t192,192,192
skyblue\t#87ceeb\t135,206,235
slateblue\t#6a5acd\t106,90,205
slategray\t#708090\t112,128,144
slategrey\t#708090\t112,128,144
snow\t#fffafa\t255,250,250
springgreen\t#00ff7f\t0,255,127
steelblue\t#4682b4\t70,130,180
tan\t#d2b48c\t210,180,140
teal\t#008080\t0,128,128
thistle\t#d8bfd8\t216,191,216
tomato\t#ff6347\t255,99,71
turquoise\t#40e0d0\t64,224,208
violet\t#ee82ee\t238,130,238
wheat\t#f5deb3\t245,222,179
white\t#ffffff\t255,255,255
whitesmoke\t#f5f5f5\t245,245,245
yellow\t#ffff00\t255,255,0
yellowgreen\t#9acd32\t154,205,50
'''

X11COLORS = map(lambda x:x.split('\t'), __X11COLORS__.strip().split('\n'))
X11COLORS_BY_NAME = {}
for clr in X11COLORS:
    clr[2] = list(map(int, clr[2].split(',')))
    clr.append([ clr[2][0]/255.0, clr[2][1]/255.0, clr[2][2]/255.0 ])
    X11COLORS_BY_NAME[ clr[0] ] = clr

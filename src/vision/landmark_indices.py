"""MediaPipe Face Mesh (478-point) landmark indices used by the vision engine.

"Right"/"left" refer to the subject's right/left (image left/right in a non-mirrored photo).
"""

from __future__ import annotations

NUM_LANDMARKS = 478
MIN_LANDMARKS = 468  # mesh without iris points

FOREHEAD_TOP = 10
CHIN = 152
NOSE_TIP = 1
FOREHEAD_CENTER = 151
RIGHT_FACE_EDGE = 234
LEFT_FACE_EDGE = 454
RIGHT_FOREHEAD = 54
LEFT_FOREHEAD = 284
RIGHT_JAW = 172
LEFT_JAW = 397
RIGHT_CHEEK_CENTER = 50
LEFT_CHEEK_CENTER = 280

# Eye corners, lids and brow (per eye): outer, inner, upper(3), lower(3), brow-lower-centre
RIGHT_EYE = {"outer": 33, "inner": 133, "upper": (160, 159, 158), "lower": (144, 145, 153),
             "brow": 52}
LEFT_EYE = {"outer": 263, "inner": 362, "upper": (387, 386, 385), "lower": (373, 374, 380),
            "brow": 282}

FACE_OVAL = (10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400,
             377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67,
             109)
RIGHT_EYE_CONTOUR = (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246)
LEFT_EYE_CONTOUR = (263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388,
                    466)
RIGHT_BROW = (70, 63, 105, 66, 107, 55, 65, 52, 53, 46)
LEFT_BROW = (300, 293, 334, 296, 336, 285, 295, 282, 283, 276)
LIPS_OUTER = (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39,
              40, 185)

EXCLUSION_CONTOURS = (RIGHT_EYE_CONTOUR, LEFT_EYE_CONTOUR, RIGHT_BROW, LEFT_BROW, LIPS_OUTER)

REQUIRED_INDICES: tuple[int, ...] = tuple(sorted({
    FOREHEAD_TOP, CHIN, NOSE_TIP, FOREHEAD_CENTER, RIGHT_FACE_EDGE, LEFT_FACE_EDGE,
    RIGHT_FOREHEAD, LEFT_FOREHEAD, RIGHT_JAW, LEFT_JAW, RIGHT_CHEEK_CENTER, LEFT_CHEEK_CENTER,
    *FACE_OVAL, *RIGHT_EYE_CONTOUR, *LEFT_EYE_CONTOUR, *RIGHT_BROW, *LEFT_BROW, *LIPS_OUTER,
    RIGHT_EYE["outer"], RIGHT_EYE["inner"], *RIGHT_EYE["upper"], *RIGHT_EYE["lower"],
    RIGHT_EYE["brow"], LEFT_EYE["outer"], LEFT_EYE["inner"], *LEFT_EYE["upper"],
    *LEFT_EYE["lower"], LEFT_EYE["brow"],
}))

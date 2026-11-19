"""Shared portal material inputs and deterministic orbit card geometry."""

import math


SURFACE = "M_Stage1PortalBlue"
CORE = "M_PortalDepthCore"
HALO = "M_PortalAetherHalo"
SPARK = "M_PortalOrbitSparks"
COUNT = 96
COLUMNS, ROWS = 12, 8

PARAMETERS = {
    "PortalBlue": (0.015, 0.18, 0.95, 1.0),
    "PortalCyan": (0.025, 0.76, 1.0, 1.0),
    "PortalViolet": (0.37, 0.040, 0.96, 1.0),
    "PortalEnergy": 2.4,
    "PortalRimIntensity": 5.2,
    "PortalFlowSpeed": 0.46,
    "PortalBodyOpacity": 0.68,
    "SparkCyan": (0.044, 0.70, 1.0, 1.0),
    "SparkViolet": (0.46, 0.075, 1.0, 1.0),
    "SparkIntensity": 4.4,
    "OrbitSpeed": 1.0,
    "SparkSize": 1.0,
}

FLOW = """float2 P = (UV - 0.5) * 2.0;
float R = length(P);
float A = atan2(P.y, P.x + 0.00001);
float Motion = T * PortalFlowSpeed;
float Turbulence = 0.46 * sin(5.0 * A + 10.0 * R - 0.7 * Motion)
                 + 0.23 * sin(8.0 * A - 18.0 * R + 0.53 * Motion);
float Phase = 2.0 * A + 4.4 * log(max(R, 0.065)) - Motion + Turbulence;
float Ribbon = pow(saturate(0.5 + 0.5 * cos(Phase)), 2.2);
float Fiber = pow(saturate(0.5 + 0.5 * sin(5.0 * Phase + 10.0 * R)), 10.0);
float Interior = 1.0 - smoothstep(0.78, 0.95, R);
float Spiral = smoothstep(0.06, 0.23, R) * Interior;
float Edge = R - (0.901 + 0.008 * sin(8.0 * A - Motion)
                        + 0.005 * sin(15.0 * A + Motion));
"""

COLOR_CODE = {
    SURFACE: FLOW + """float Rim = exp(-pow(Edge / 0.021, 2.0));
float Haze = exp(-26.0 * abs(Edge));
float Mix = saturate(0.40 + 0.28 * cos(A - 3.0 * R - Motion * 0.33) + 0.20 * Ribbon);
float3 FlowColor = lerp(PortalViolet.rgb, PortalCyan.rgb, Mix);
float3 Body = PortalBlue.rgb * (0.54 + 0.39 * smoothstep(0.08, 0.76, R)) * Interior;
float3 Stream = FlowColor * (0.37 + 1.23 * Ribbon + 0.24 * Fiber) * Spiral;
float3 RimColor = lerp(PortalCyan.rgb, PortalViolet.rgb, 0.12 + 0.11 * sin(3.0 * A + Motion));
float RimPattern = 0.84 + 0.16 * sin(12.0 * A + R * 32.0 - Motion * 2.0);
return PortalEnergy * (Body + Stream)
     + PortalRimIntensity * RimColor * (Rim * RimPattern + 0.11 * Haze);
""",
    CORE: FLOW + """float3 InteriorColor = lerp(PortalBlue.rgb, PortalViolet.rgb, 0.27 + 0.15 * Ribbon);
return PortalEnergy * InteriorColor * (0.29 + 0.28 * Ribbon * Spiral + 0.07 * Fiber * Spiral);
""",
    HALO: FLOW + """float Band = exp(-pow((R - 0.87) / 0.043, 2.0));
float Breath = 0.66 + 0.34 * sin(12.0 * A + R * 39.0 - Motion * 2.4);
float3 Tint = lerp(PortalCyan.rgb, PortalViolet.rgb, 0.29 + 0.23 * sin(3.0 * A + Motion));
return Tint * PortalEnergy * Band * (0.54 + 0.84 * Breath);
""",
}

COLOR_PARAMETERS = {
    SURFACE: ("PortalBlue", "PortalCyan", "PortalViolet", "PortalEnergy", "PortalRimIntensity", "PortalFlowSpeed"),
    CORE: ("PortalBlue", "PortalViolet", "PortalEnergy", "PortalFlowSpeed"),
    HALO: ("PortalCyan", "PortalViolet", "PortalEnergy", "PortalFlowSpeed"),
}

SURFACE_OPACITY = FLOW + """float AA = clamp(fwidth(R), 0.002, 0.017);
float Rim = exp(-pow(Edge / 0.025, 2.0));
float Alpha = PortalBodyOpacity - 0.09 + (0.09 + 0.12 * Ribbon) * Spiral + 0.35 * Rim;
return saturate(Alpha) * (1.0 - smoothstep(0.027, 0.071 + AA, Edge));
"""

HALO_OPACITY = """float R = length((UV - 0.5) * 2.0);
return 0.38 * (1.0 - smoothstep(0.92, 1.0, R));
"""

DEPTH_MASK = "float2 p=(UV-.5)*2.; return .915-length(p);"

SPARK_INDEX = """float2 Packed = UV * float2(12.0, 8.0);
float2 Cell = floor(Packed);
float I = Cell.x + 12.0 * Cell.y;
"""

SPARK_PATH = SPARK_INDEX + """float Variation = fmod(I * 53.0 + 17.0, 97.0) / 97.0;
float Radius = (I < 76.0) ? (0.96 + 0.20 * Variation) : (0.57 + 0.31 * Variation);
float Start = I * (6.28318530718 / 96.0);
float Angle = Start + T * OrbitSpeed * (0.28 + 0.34 * fmod(I * 67.0 + 13.0, 97.0) / 97.0);
"""

SPARK_OFFSET = SPARK_PATH + """float DriftY = 3.8 * sin(T * 1.11 + I * 2.37);
return float3(51.0 * Radius * (cos(Angle) - cos(Start)),
              DriftY, 87.0 * Radius * (sin(Angle) - sin(Start)));
"""

SPARK_OPACITY = SPARK_PATH + """float2 P = abs((frac(Packed) - 0.5) / (0.35 * clamp(SparkSize, 0.35, 1.4)));
float Dot = 1.0 - smoothstep(0.08, 0.95, length(P));
float Axial = min(max(P.x, 6.5 * P.y), max(6.5 * P.x, P.y));
float Cross = 0.62 * (1.0 - smoothstep(0.24, 0.90, Axial));
float Shape = (I < 76.0 && fmod(I, 8.0) == 0.0) ? max(Dot, Cross) : Dot;
float Lifetime = 1.5 + 1.5 * fmod(I * 29.0 + 5.0, 97.0) / 97.0;
float Age = frac(T / Lifetime + fmod(I * 79.0 + 31.0, 97.0) / 97.0);
float Gate = smoothstep(0.04, 0.18, Age) * (1.0 - smoothstep(0.60, 0.83, Age));
float Twinkle = 0.63 + 0.37 * sin(T * (3.8 + 2.2 * Variation) + I * 1.77);
float Height = 90.0 + 87.0 * Radius * sin(Angle);
float AboveFloor = smoothstep(2.0, 12.0, Height);
return Shape * Gate * Twinkle * AboveFloor * smoothstep(0.03, 0.95, ScaleX);
"""

SPARK_COLOR = SPARK_INDEX + """float Tint = fmod(I * 29.0 + 11.0, 96.0);
float3 Color = Tint < 67.0 ? SparkCyan.rgb : (Tint < 88.0 ? SparkViolet.rgb : float3(0.40, 0.84, 1.0));
return SparkIntensity * Color * (Tint >= 88.0 ? 1.38 : 1.0);
"""


def spark_cards():
    """Each card yields four local XYZ positions and their packed atlas UVs."""
    for index in range(COUNT):
        variation = ((index * 53 + 17) % 97) / 97
        radius = 0.96 + 0.20 * variation if index < 76 else 0.57 + 0.31 * variation
        angle = math.tau * index / COUNT
        center = (51 * radius * math.cos(angle), -6 - (index % 5) * 6, 87 * radius * math.sin(angle))
        half = 1.05 + 1.25 * ((index * 31 + 7) % 97) / 97
        if index < 76 and index % 8 == 0:
            half = 2.6
        tilt = math.radians(-24 + 12 * (index % 5))
        column, row = index % COLUMNS, index // COLUMNS
        corners = []
        for x, z in ((0, 0), (1, 0), (1, 1), (0, 1)):
            right = (2 * x - 1) * half
            xyz = (center[0] + right * math.cos(tilt), center[1] + right * math.sin(tilt),
                   center[2] + (2 * z - 1) * half)
            uv = ((column + 0.15 + 0.7 * x) / COLUMNS, (row + 0.15 + 0.7 * z) / ROWS)
            corners.append((xyz, uv))
        yield corners

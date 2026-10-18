"""Mission terrain and cell map from a mission .pak (packets 0 and 4-7).

Packet 0: N x N PostcompVertex (MCLib/Vertex.h:32), 32 bytes each, row-major
from the map's top-left (north-west) corner:
    float normal[3], float elevation, u32 textureData (overlay << 16 | base),
    u32 localRGBLight, u32 terrainType, u8 selected, water, shadow, highlighted
Packets 4-7: MissionMap (MCLib/Move.cpp:840): i32 height, i32 width,
    i32 planet, then height x width u32 MapCell words, row-major from the
    north-west corner. There are 3 cells per vertex (MAPCELL_DIM).

World units: 128 per vertex, 0.2 m per unit (Terrain.cpp:63-77). Elevations
are in world units too.
"""

import struct

from packet import PacketFile

VERTEX_SIZE = 32
WORLD_UNITS_PER_VERTEX = 128.0
METERS_PER_WORLD_UNIT = 0.2
CELLS_PER_VERTEX = 3

# MapCell bits (MCLib/Move.h:225-275)
CELL_BITS = {
    "terrain": (0, 0xF), "overlay": (4, 0x3), "gate": (8, 0x1), "offmap": (9, 0x1),
    "passable": (10, 0x1), "mine": (13, 0xF), "height": (18, 0xF), "wall": (24, 0x1),
    "road": (25, 0x1), "shallow": (26, 0x1), "deep": (27, 0x1), "forest": (28, 0x1),
}


def cell_field(word, name):
    shift, mask = CELL_BITS[name]
    return (word >> shift) & mask


def read_vertices(pak):
    data = pak.read(0)
    count = len(data) // VERTEX_SIZE
    side = int(round(count ** 0.5))
    if side * side != count:
        raise ValueError(f"terrain packet holds {count} vertices, not a square")
    elevation, terrain_type, base_tex, overlay_tex, water = [], [], [], [], []
    for i in range(count):
        _, _, _, elev, tex, _light, ttype, _sel, wat, _sh, _hl = struct.unpack_from(
            "<4fIIIBBBB", data, i * VERTEX_SIZE)
        elevation.append(round(elev, 3))
        terrain_type.append(ttype)
        base_tex.append(tex & 0xFFFF)
        overlay_tex.append(tex >> 16)
        water.append(wat)
    return side, {"elevation": elevation, "terrain_type": terrain_type,
                  "base_texture": base_tex, "overlay_texture": overlay_tex, "water": water}


def read_cells(pak, first_packet=4):
    height = struct.unpack("<i", pak.read(first_packet))[0]
    width = struct.unpack("<i", pak.read(first_packet + 1))[0]
    planet = struct.unpack("<i", pak.read(first_packet + 2))[0]
    raw = pak.read(first_packet + 3)
    if len(raw) != height * width * 4:
        raise ValueError(f"cell packet is {len(raw)} bytes, expected {height * width * 4}")
    return height, width, planet, raw


def tacmap(pak, packet=3):
    """Packet 3 holds the tactical-map image as a TGA file."""
    return pak.read(packet)


def convert(pak_path, mission_fit):
    pak = PacketFile.open(pak_path)
    side, verts = read_vertices(pak)
    rows, cols, planet, cells = read_cells(pak)
    if rows != side * CELLS_PER_VERTEX or cols != side * CELLS_PER_VERTEX:
        raise ValueError(f"cell map {rows}x{cols} does not match {side} vertices")
    water = mission_fit.get("Water", {})
    terrain = mission_fit.get("Terrain", {})
    meta = {
        "vertices_per_side": side,
        "cells_per_side": rows,
        "world_units_per_vertex": WORLD_UNITS_PER_VERTEX,
        "meters_per_world_unit": METERS_PER_WORLD_UNIT,
        "planet": planet,
        "water_elevation": water.get("Elevation", -1000.0),
        "water_shallow_depth": water.get("ShallowDepth", 0.0),
        "water_alpha_depth": water.get("AlphaDepth", 0.0),
        "water_frequency": water.get("Frequency", 8.0),
        "water_amplitude": water.get("Ampliture", 3.0),  # sic: the FIT key is misspelled
        "detail_tiling": terrain.get("DetailTextureTilingFactor", 30.0),
        "water_tiling": terrain.get("WaterTextureTilingFactor", 48.0),
        "cell_bits": {k: list(v) for k, v in CELL_BITS.items()},
        **verts,
    }
    return meta, cells, tacmap(pak)

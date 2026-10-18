"""MC2 PacketFile reader (MCLib/Packet.cpp, packet.h).

Layout: u32 magic 0xFEEDFACE (or a checksum), then a seek table of u32
offsets starting at byte 8; the first offset / 4 - 2 gives the packet count.
The top 3 bits of an offset are the storage type (0 raw, 1 file-in-file,
2 LZ, 4 zlib, 7 null). Compressed packets start with a u32 unpacked size.
"""

import struct
import zlib

MAGIC = 0xFEEDFACE
TYPE_SHIFT = 29
OFFSET_MASK = (1 << TYPE_SHIFT) - 1
RAW, FWF, LZD, HF, ZLIB, NUL = 0, 1, 2, 3, 4, 7


class PacketFile:
    def __init__(self, data):
        self.data = data
        first_offset = struct.unpack_from("<I", data, 4)[0]
        self.num_packets = first_offset // 4 - 2
        self.table = list(struct.unpack_from(f"<{self.num_packets}I", data, 8))

    @classmethod
    def open(cls, path):
        with open(path, "rb") as fh:
            return cls(fh.read())

    def info(self, i):
        raw = self.table[i]
        kind, offset = raw >> TYPE_SHIFT, raw & OFFSET_MASK
        end = len(self.data) if i + 1 == self.num_packets else self.table[i + 1] & OFFSET_MASK
        return kind, offset, end - offset

    def read(self, i):
        kind, offset, size = self.info(i)
        if kind in (RAW, FWF):
            return self.data[offset:offset + size]
        if kind == NUL:
            return b""
        unpacked = struct.unpack_from("<I", self.data, offset)[0]
        body = self.data[offset + 4:offset + size]
        if kind == ZLIB:
            out = zlib.decompress(body)
        elif kind == LZD:
            from lz import lz_decompress
            out = lz_decompress(body)
        else:
            raise ValueError(f"packet {i}: unsupported storage type {kind}")
        if len(out) != unpacked:
            raise ValueError(f"packet {i}: unpacked {len(out)} bytes, expected {unpacked}")
        return out

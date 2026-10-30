"""Create the synthetic visual fixtures using only the Python standard library.

Run from this directory: python3 generate_figures.py
This writes newly generated test PNGs, not scientific results.
"""
import csv
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
W, H = 900, 540
WHITE, BLACK, GRID, BLUE, ORANGE = (255, 255, 255), (28, 35, 42), (218, 226, 232), (30, 97, 168), (216, 116, 31)
FONT = {
    'A': '01110/10001/10001/11111/10001/10001/10001', 'B': '11110/10001/10001/11110/10001/10001/11110',
    'C': '01111/10000/10000/10000/10000/10000/01111', 'D': '11110/10001/10001/10001/10001/10001/11110',
    'E': '11111/10000/10000/11110/10000/10000/11111', 'F': '11111/10000/10000/11110/10000/10000/10000',
    'G': '01111/10000/10000/10111/10001/10001/01111', 'H': '10001/10001/10001/11111/10001/10001/10001',
    'I': '11111/00100/00100/00100/00100/00100/11111', 'J': '00111/00010/00010/00010/10010/10010/01100',
    'K': '10001/10010/10100/11000/10100/10010/10001', 'L': '10000/10000/10000/10000/10000/10000/11111',
    'M': '10001/11011/10101/10101/10001/10001/10001', 'N': '10001/11001/10101/10011/10001/10001/10001',
    'O': '01110/10001/10001/10001/10001/10001/01110', 'P': '11110/10001/10001/11110/10000/10000/10000',
    'Q': '01110/10001/10001/10001/10101/10010/01101', 'R': '11110/10001/10001/11110/10100/10010/10001',
    'S': '01111/10000/10000/01110/00001/00001/11110', 'T': '11111/00100/00100/00100/00100/00100/00100',
    'U': '10001/10001/10001/10001/10001/10001/01110', 'V': '10001/10001/10001/10001/10001/01010/00100',
    'W': '10001/10001/10001/10101/10101/10101/01010', 'X': '10001/10001/01010/00100/01010/10001/10001',
    'Y': '10001/10001/01010/00100/00100/00100/00100', 'Z': '11111/00001/00010/00100/01000/10000/11111',
    '0': '01110/10001/10011/10101/11001/10001/01110', '1': '00100/01100/00100/00100/00100/00100/01110',
    '2': '01110/10001/00001/00010/00100/01000/11111', '3': '11110/00001/00001/01110/00001/00001/11110',
    '4': '00010/00110/01010/10010/11111/00010/00010', '5': '11111/10000/10000/11110/00001/00001/11110',
    '6': '01110/10000/10000/11110/10001/10001/01110', '7': '11111/00001/00010/00100/01000/01000/01000',
    '8': '01110/10001/10001/01110/10001/10001/01110', '9': '01110/10001/10001/01111/00001/00001/01110',
    '%': '11001/11010/00100/01000/10110/00110/00000', ' ': '00000/00000/00000/00000/00000/00000/00000',
}

def canvas():
    return bytearray(WHITE * (W * H))

def rect(p, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            p[(y * W + x) * 3:(y * W + x) * 3 + 3] = bytes(color)

def line(p, x0, y0, x1, y1, color, width=3):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = round(x0 + (x1 - x0) * i / steps)
        y = round(y0 + (y1 - y0) * i / steps)
        rect(p, x - width // 2, y - width // 2, x + (width + 1) // 2, y + (width + 1) // 2, color)

def label(p, x, y, text, scale=3, color=BLACK):
    for c in text.upper():
        for yy, row in enumerate(FONT[c].split('/')):
            for xx, bit in enumerate(row):
                if bit == '1':
                    rect(p, x + xx * scale, y + yy * scale, x + (xx + 1) * scale, y + (yy + 1) * scale, color)
        x += 6 * scale

def save(path, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    rows = b''.join(b'\0' + pixels[y * W * 3:(y + 1) * W * 3] for y in range(H))
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')
    path.write_bytes(data)

def rows(name):
    with (ROOT / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def axes(p, title, axis, maximum, step):
    label(p, 130, 35, title, 4)
    label(p, 130, 87, axis, 3)
    for v in range(0, maximum + 1, step):
        y = 430 - round(v / maximum * 300)
        line(p, 140, y, 820, y, GRID, 1)
        label(p, 70, y - 10, str(v), 3)
    line(p, 140, 130, 140, 430, BLACK)
    line(p, 140, 430, 820, 430, BLACK)

data = rows('latency.csv')
p = canvas()
axes(p, 'FAC LATENCY BY INTERVAL', 'LATENCY MS', 10, 2)
points = [(200 + i * 180, 430 - round(float(row['latency_ms']) / 10 * 300)) for i, row in enumerate(data)]
for a, b in zip(points, points[1:]):
    line(p, *a, *b, BLUE, 6)
for (x, y), row in zip(points, data):
    rect(p, x - 7, y - 7, x + 8, y + 8, ORANGE)
    label(p, x - 5, 447, row['interval'], 3)
label(p, 360, 493, 'INTERVAL', 3)
save(ROOT / 'figure1-latency.png', p)

data = rows('completion.csv')
p = canvas()
axes(p, 'TASK COMPLETION', 'COMPLETION RATE %', 100, 20)
for i, row in enumerate(data):
    x = 310 + i * 270
    height = round(float(row['completion_percent']) / 100 * 300)
    rect(p, x - 70, 430 - height, x + 70, 430, BLUE if i == 0 else ORANGE)
    label(p, x - 70, 447, row['method'], 3)
save(ROOT / 'figure2-completion.png', p)

"""
generate_icons.py — Tengeneza icon zote za PWA kwa Zoyina Pesa
Endesha: python generate_icons.py
Inahitaji: pip install Pillow
"""
from PIL import Image, ImageDraw
import os

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
OUT_DIR = os.path.join("static", "icons")
os.makedirs(OUT_DIR, exist_ok=True)

def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Mandhari ya kijani (background ya duara iliyopigwa)
    radius = size // 2
    draw.ellipse([0, 0, size - 1, size - 1], fill="#00C853")

    # Mstari wa herufi "Z" kwa nafasi
    m = size * 0.18
    lw = max(2, size // 22)
    pts = [
        (m, m * 1.1),
        (size - m, m * 1.1),
        (m, size - m * 1.1),
        (size - m, size - m * 1.1),
    ]
    draw.line([pts[0], pts[1]], fill="white", width=lw)
    draw.line([pts[1], pts[2]], fill="white", width=lw)
    draw.line([pts[2], pts[3]], fill="white", width=lw)

    path = os.path.join(OUT_DIR, f"icon-{size}x{size}.png")
    img.save(path, "PNG")
    print(f"  ✓ {path}")

print("Inatengeneza icon za PWA...")
for s in SIZES:
    make_icon(s)

print(f"\n✅ Icon {len(SIZES)} zimetengenezwa kwenye '{OUT_DIR}/'")
print("Sasa unaweza kuanza server: python app.py")

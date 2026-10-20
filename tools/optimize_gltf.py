"""glTF (+ .bin + dokular) → tek, web için küçültülmüş .glb.

Arka plan modeli için 4096 px dokular gereksiz büyük; bu araç dokuları
küçültür (renk + alfa: PNG, diğerleri: JPEG), saydamlığı BLEND yerine MASK
yapar (derinlik sıralaması sorunlarını önler) ve hepsini tek bir GLB içine
paketler. Geometri olduğu gibi kopyalanır.

Kullanım:
    python tools/optimize_gltf.py <model.gltf> <çıktı.glb> [--size 1024] [--jpeg-quality 88]

Pillow gerektirir (backend sanal ortamında matplotlib ile birlikte gelir):
    backend/.venv/bin/python tools/optimize_gltf.py ...
"""
import argparse
import io
import json
import struct
from pathlib import Path

from PIL import Image

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942


def _pad(data: bytes, fill: bytes) -> bytes:
    return data + fill * ((4 - len(data) % 4) % 4)


def _texture_roles(gltf: dict) -> dict[int, str]:
    """Görüntü indeksi → rol ('base' alfa taşıyabilir, diğerleri opak)."""
    roles = {}
    for mat in gltf.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        for key, role in (("baseColorTexture", "base"), ("metallicRoughnessTexture", "orm")):
            if key in pbr:
                roles[gltf["textures"][pbr[key]["index"]]["source"]] = role
        for key, role in (("normalTexture", "normal"), ("occlusionTexture", "orm"), ("emissiveTexture", "emissive")):
            if key in mat:
                roles[gltf["textures"][mat[key]["index"]]["source"]] = role
    return roles


def _encode(path: Path, role: str, size: int, quality: int) -> tuple[bytes, str]:
    im = Image.open(path)
    im = im.resize((min(size, im.width), min(size, im.height)), Image.LANCZOS)
    buf = io.BytesIO()
    if role == "base" and "A" in im.getbands():
        im.convert("RGBA").save(buf, "PNG", optimize=True)
        return buf.getvalue(), "image/png"
    im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue(), "image/jpeg"


def optimize(src: Path, dst: Path, size: int, quality: int) -> None:
    gltf = json.loads(src.read_text(encoding="utf-8"))
    if len(gltf.get("buffers", [])) != 1:
        raise SystemExit("Yalnızca tek buffer'lı glTF destekleniyor")
    binary = bytearray(_pad((src.parent / gltf["buffers"][0]["uri"]).read_bytes(), b"\x00"))

    roles = _texture_roles(gltf)
    for i, image in enumerate(gltf.get("images", [])):
        data, mime = _encode(src.parent / image["uri"], roles.get(i, "other"), size, quality)
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)})
        gltf["images"][i] = {"bufferView": len(gltf["bufferViews"]) - 1, "mimeType": mime}
        binary += _pad(data, b"\x00")
        print(f"  doku {i} ({roles.get(i, 'other')}): {image['uri']} → {mime}, {len(data) / 1024:.0f} KB")

    for mat in gltf.get("materials", []):
        mat.pop("extras", None)
        if mat.get("alphaMode") == "BLEND":
            mat["alphaMode"] = "MASK"
            mat["alphaCutoff"] = 0.5
    gltf["buffers"] = [{"byteLength": len(binary)}]
    gltf["asset"]["generator"] = f"{gltf['asset'].get('generator', '')} + optimize_gltf.py".strip(" +")

    json_chunk = _pad(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    total = 12 + 8 + len(json_chunk) + 8 + len(binary)
    with dst.open("wb") as fh:
        fh.write(struct.pack("<III", GLB_MAGIC, 2, total))
        fh.write(struct.pack("<II", len(json_chunk), CHUNK_JSON) + json_chunk)
        fh.write(struct.pack("<II", len(binary), CHUNK_BIN) + bytes(binary))
    print(f"→ {dst} ({total / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--size", type=int, default=1024, help="en büyük doku kenarı (px)")
    parser.add_argument("--jpeg-quality", type=int, default=88)
    args = parser.parse_args()
    optimize(args.src, args.dst, args.size, args.jpeg_quality)

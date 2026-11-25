# Prepare the deck-04 tutor cutout from the uploaded portrait.
# Input : --src (default: the Gemini portrait on the Desktop)
# Output: assets\photos\tutor-cutout.png  (transparent bg, deck grade, 4K-ready)
# Run   : py .\exports\prepare-tutor-photo.py
#
# Quality chain for 4K exports:
#   Real-ESRGAN x2 (ONNX / onnxruntime)  ->  rembg isnet matte
#   ->  Lanczos to deck-04 pixel size    ->  gentle grade + unsharp
# The ONNX model (~64 MB) is cached in %TEMP%\opencode and downloaded once.
# If onnxruntime or the model is unavailable, it falls back to Lanczos.

import argparse
import shutil
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "photos" / "tutor-cutout.png"
DEFAULT_SRC = Path(r"C:\Users\rohit\OneDrive\Desktop\Gemini_Generated_Image_g5zejtg5zejtg5ze.png")

# 509x754 source -> 1654x2451, i.e. 1:1 with the portrait at 4x export scale
UPSCALE = 3.25
MODEL_URL = "https://huggingface.co/JoPmt/Real_Esrgan_x2_Onnx_Tflite_Tfjs/resolve/main/model.onnx"
MODEL = Path(__import__("tempfile").gettempdir()) / "opencode" / "realesrgan-x2.onnx"
SESSION = new_session("isnet-general-use")


def super_resolve(im: Image.Image) -> Image.Image:
    """2x neural upscale; onnxruntime is already installed with the kit."""
    try:
        import onnxruntime as ort
    except ImportError:
        return _lanczos(im, 2)

    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        tmp = MODEL.with_suffix(".download")
        print(f"     downloading Real-ESRGAN x2 ONNX -> {MODEL.name}")
        urllib.request.urlretrieve(MODEL_URL, tmp)
        shutil.move(str(tmp), str(MODEL))

    src = np.array(im.convert("RGB"))
    h, w = src.shape[:2]
    ph, pw = (4 - h % 4) % 4, (4 - w % 4) % 4
    padded = np.pad(src, ((0, ph), (0, pw), (0, 0)), mode="reflect")
    x = padded.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    sess = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
    y = sess.run(None, {"input": x})[0][0]
    rgb = np.clip(np.transpose(y, (1, 2, 0)) * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(rgb[: h * 2, : w * 2], "RGB")


def _lanczos(im: Image.Image, factor: int) -> Image.Image:
    return im.resize((im.width * factor, im.height * factor), Image.LANCZOS)


def matte(im: Image.Image) -> Image.Image:
    out = remove(im, session=SESSION, post_process_mask=False)
    arr = np.array(out)
    a = cv2.erode(arr[:, :, 3].astype(np.float32), np.ones((3, 3), np.uint8), iterations=1)
    a = np.clip(cv2.GaussianBlur(a, (0, 0), 0.9), 0, 255)
    arr[:, :, 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def grade(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Cool shadows, warm highlights, soft vignette, steel-blue rim light."""
    x = rgb.astype(np.float32) / 255.0
    lum = (0.2126 * x[:, :, 0] + 0.7152 * x[:, :, 1] + 0.0722 * x[:, :, 2])[:, :, None]
    shadow = np.clip(1.0 - lum / 0.45, 0.0, 1.0)
    high = np.clip((lum - 0.55) / 0.45, 0.0, 1.0)
    x += shadow * np.array([-0.004, 0.0, 0.020], np.float32)
    x += high * np.array([0.011, 0.003, -0.009], np.float32)

    h, w = lum.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vd = np.sqrt(((xx - w * 0.5) / (w * 0.80)) ** 2 + ((yy - h * 0.40) / (h * 0.88)) ** 2)
    vig = np.clip(1.0 - np.clip(vd - 0.58, 0.0, 1.0) * 0.42, 0.0, 1.0)[..., None]
    x *= vig

    blur = cv2.GaussianBlur(alpha, (0, 0), 12).astype(np.float32) / 255.0
    edge = np.clip((alpha.astype(np.float32) / 255.0) - blur, 0.0, 1.0)[..., None]
    rim = edge * np.clip(1.15 - (xx / w) * 1.55, 0.0, 1.0)[..., None]
    x = x + np.array([0.55, 0.74, 1.0], np.float32)[None, None, :] * rim * 0.15

    return np.clip(x * 255.0, 0, 255).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    args = ap.parse_args()

    src = Path(args.src)
    base = Image.open(src).convert("RGB")
    sr = super_resolve(base)
    print(f"     neural upscale {base.width}x{base.height} -> {sr.width}x{sr.height}")

    cut = matte(sr)
    target = (round(base.width * UPSCALE), round(base.height * UPSCALE))
    cut = cut.resize(target, Image.LANCZOS)
    arr = np.array(cut)

    # SR restores the detail; a light unsharp pass after grading locks it in
    graded = grade(arr[:, :, :3], arr[:, :, 3]).astype(np.float32)
    rgb = graded
    for _ in range(2):  # two light passes avoid the halos of one heavy pass
        blur = cv2.GaussianBlur(rgb, (0, 0), 1.2)
        rgb = cv2.addWeighted(rgb, 1.8, blur, -0.8, 0)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack([rgb, arr[:, :, 3]]), "RGBA").save(OUT, optimize=True)

    A = np.array(Image.open(OUT))[:, :, 3]
    ys, xs = np.where(A > 24)
    # compare at equal scale (output downsampled back to source size)
    out_small = np.array(Image.open(OUT).convert("RGB").resize(base.size, Image.LANCZOS))
    src_lap = cv2.Laplacian(np.array(base), cv2.CV_32F)[:, :, 0].var()
    out_lap = cv2.Laplacian(out_small, cv2.CV_32F)[:, :, 0].var()
    print(f"[ok] {OUT.name}  {target[0]}x{target[1]}  {OUT.stat().st_size / 1024:,.0f} KB")
    print(f"     subject bbox {int(xs.min())},{int(ys.min())} - {int(xs.max())},{int(ys.max())}")
    print(f"     equal-scale laplacian {src_lap:,.0f} -> {out_lap:,.0f}")


if __name__ == "__main__":
    main()

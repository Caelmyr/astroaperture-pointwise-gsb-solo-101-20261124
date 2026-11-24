"""Calibrated ADU are read from the working raster before any display stretch."""

from io import BytesIO
import warnings

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from image_lab.validation import Invalid, number

MAX_UPLOAD = 20 * 1024 * 1024
MAX_PIXELS = 4_200_000
SATURATION = 65520


def validate_size(width, height):
    if min(width, height) < 32 or max(width, height) > 4096 or width * height > MAX_PIXELS:
        raise Invalid('图像边长须为 32–4096 像素，总量至多 420 万像素。')


def decode(raw):
    if len(raw) > MAX_UPLOAD:
        raise Invalid('单张原片至多 20 MiB。')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                validate_size(*image.size)
                if image.format not in {'PNG', 'TIFF'} or image.mode not in {'I;16', 'I;16L', 'I;16B'}:
                    raise Invalid('请选择线性 16 位灰度 PNG 或 TIFF。')
                if getattr(image, 'n_frames', 1) != 1:
                    raise Invalid('只支持单幅灰度原片。')
                field = np.asarray(ImageOps.exif_transpose(image), dtype=np.uint16).copy()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise Invalid('无法解码这张星野原片。') from error
    return field


def read(path):
    with Image.open(path) as source:
        return np.asarray(source, dtype=np.uint16).copy()


def png(field):
    stream = BytesIO()
    Image.fromarray(field).save(stream, format='PNG')
    return stream.getvalue()


def levels(field, low=None, high=None):
    if low is None and high is None:
        low, high = np.percentile(field, (1, 99.8))
        return float(low), float(max(high, low + 1))
    low = number(low, '黑点 ADU', 0, 65535)
    high = number(high, '白点 ADU', 0, 65536)
    if low >= high:
        raise Invalid('白点须高于黑点。')
    return low, high


def preview(field, low=None, high=None, flag=False):
    black, white = levels(field, low, high)
    pixels = np.rint(np.sqrt(np.clip((field.astype(np.float32) - black) / (white - black), 0, 1)) * 255).astype(np.uint8)
    if flag:
        pixels = np.repeat(pixels[..., None], 3, axis=-1)
        pixels[field >= SATURATION] = (255, 127, 68)
    return png(pixels)


def describe(field):
    hist = np.histogram(field, bins=32, range=(0, 65536))[0]
    low, high = levels(field)
    return {'min': int(field.min()), 'max': int(field.max()), 'median': float(np.median(field)),
            'saturated': int(np.count_nonzero(field >= SATURATION)), 'histogram': hist.tolist(),
            'levels': [low, high]}

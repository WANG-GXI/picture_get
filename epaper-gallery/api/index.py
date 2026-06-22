import os
from flask import Flask, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO

app = Flask(__name__)

# 【关键】获取当前 index.py 所在的绝对路径，确保能百分百找到你的 Minion Pro 字体
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_dithered_art(image_url):
    try:
        response = requests.get(image_url, timeout=20)
        response.raise_for_status() 
        img = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        img = Image.new('RGB', (480, 648), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((30, 300), f"Fetch Error:\n{str(e)[:40]}", fill=(255, 0, 0))
        return img.quantize(colors=3)

    # 智能裁剪并缩放到你的墨水屏竖屏尺寸 (480x648)
    img = ImageOps.fit(img, (480, 648), Image.Resampling.LANCZOS)

    # 如果你想在图片右下角加上优雅的 Minion Pro 水印或作品名，可以在这里画上去
    # draw = ImageDraw.Draw(img)
    # try:
    #     font_path = os.path.join(BASE_DIR, 'MinionPro-Regular.otf')
    #     f_title = ImageFont.truetype(font_path, 24)
    #     draw.text((300, 600), "Gallery EPD", fill=(255, 0, 0), font=f_title)
    # except:
    #     pass

    # 墨水屏专属调色板
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette([
        255, 255, 255,  # 0: 白
        0,   0,   0,    # 1: 黑
        255, 0,   0,    # 2: 红
    ] + [0, 0, 0] * 253)

    # 魔法：Floyd-Steinberg 抖动算法
    dithered_img = img.quantize(palette=pal_img, dither=Image.FLOYDSTEINBERG)
    return dithered_img


# 路由 1：电脑浏览器高清预览 (莫奈《日出》原图测试)
@app.route('/preview_gallery')
def preview_gallery():
    art_url = "https://collectionapi.metmuseum.org/api/collection/v1/iiif/336046/1364579/main-image"
    dithered_img = generate_dithered_art(art_url)
    
    preview_img = dithered_img.convert("RGB")
    img_io = BytesIO()
    preview_img.save(img_io, 'PNG')
    img_io.seek(0)
    return Response(img_io.getvalue(), mimetype='image/png')


# 路由 2：给 ESP32 的底层二进制流
@app.route('/get_gallery_epd')
def get_gallery_epd():
    art_url = "https://collectionapi.metmuseum.org/api/collection/v1/iiif/336046/1364579/main-image"
    dithered_img = generate_dithered_art(art_url)

    black_buf = bytearray(38880)
    red_buf = bytearray(38880)
    
    for i in range(38880):
        black_buf[i] = 0xFF
        red_buf[i] = 0xFF

    for py_y in range(648):
        for py_x in range(480):
            color_index = dithered_img.getpixel((py_x, py_y))
            phys_x = py_y
            phys_y = 479 - py_x

            byte_idx = phys_y * 81 + (phys_x // 8)
            bit_idx = 7 - (phys_x % 8)

            if color_index == 2:    # 红层
                red_buf[byte_idx] &= ~(1 << bit_idx)   
            elif color_index == 1:  # 黑层
                black_buf[byte_idx] &= ~(1 << bit_idx) 

    binary_payload = black_buf + red_buf
    return Response(binary_payload, mimetype='application/octet-stream')

# Vercel 需要导出 app 对象
if __name__ == '__main__':
    app.run()

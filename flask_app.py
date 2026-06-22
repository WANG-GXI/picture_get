from flask import Flask, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO

app = Flask(__name__)

# --- 核心图像处理函数 ---
def generate_dithered_art(image_url):
    # 1. 下载彩色源图像
    try:
        response = requests.get(image_url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        # 如果下载失败，创建一张带错误提示的白底图
        img = Image.new('RGB', (480, 648), color='white')
        ImageDraw.Draw(img).text((50, 300), "Image fetch failed.", fill=(0,0,0))
        return img

    # 2. 智能裁剪并缩放到你的墨水屏竖屏尺寸
    # ImageOps.fit 会自动保留图像中心，并完美填满 480x648，不拉伸变形
    img = ImageOps.fit(img, (480, 648), Image.Resampling.LANCZOS)

    # 3. 【核心黑科技】定义微雪三色墨水屏的专属调色板 (Palette)
    pal_img = Image.new("P", (1, 1))
    # 调色板前三个颜色固定为：白、黑、红
    pal_img.putpalette([
        255, 255, 255,  # 索引 0: 白色
        0,   0,   0,    # 索引 1: 黑色
        255, 0,   0,    # 索引 2: 红色
    ] + [0, 0, 0] * 253) # 剩余索引填黑

    # 4. 施展魔法：应用 Floyd-Steinberg 抖动算法
    # 将彩色图像强制降维到只有这三种颜色，并通过抖动补偿色彩误差
    dithered_img = img.quantize(palette=pal_img, dither=Image.FLOYDSTEINBERG)
    
    return dithered_img


# --- 路由 1：给电脑浏览器看的高清预览图 ---
@app.route('/preview_gallery')
def preview_gallery():
    # 这里以葛饰北斋的《凯风快晴》（赤富士）的维基百科公共图库链接为例
    art_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Tomiake_kei_no_Fuji.jpg/800px-Tomiake_kei_no_Fuji.jpg"
    
    # 获取抖动后的图像
    dithered_img = generate_dithered_art(art_url)
    
    # 转回 RGB 格式以便浏览器显示
    preview_img = dithered_img.convert("RGB")
    img_io = BytesIO()
    preview_img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return Response(img_io.getvalue(), mimetype='image/png')


# --- 路由 2：给 ESP32 喂的底层二进制数据 ---
@app.route('/get_gallery_epd')
def get_gallery_epd():
    art_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Tomiake_kei_no_Fuji.jpg/800px-Tomiake_kei_no_Fuji.jpg"
    dithered_img = generate_dithered_art(art_url)

    # 初始化 EPD 物理屏幕的黑层和红层数组 (648x480 = 38880 bytes)
    black_buf = bytearray(38880)
    red_buf = bytearray(38880)
    
    for i in range(38880):
        black_buf[i] = 0xFF
        red_buf[i] = 0xFF

    # 提取像素并执行 90 度旋转映射
    for py_y in range(648):
        for py_x in range(480):
            # 获取调色板索引：0是白，1是黑，2是红
            color_index = dithered_img.getpixel((py_x, py_y))
            
            phys_x = py_y
            phys_y = 479 - py_x

            byte_idx = phys_y * 81 + (phys_x // 8)
            bit_idx = 7 - (phys_x % 8)

            if color_index == 2:    # 红色
                red_buf[byte_idx] &= ~(1 << bit_idx)   # 红层写0显示红
            elif color_index == 1:  # 黑色
                black_buf[byte_idx] &= ~(1 << bit_idx) # 黑层写0显示黑

    binary_payload = black_buf + red_buf
    return Response(binary_payload, mimetype='application/octet-stream')

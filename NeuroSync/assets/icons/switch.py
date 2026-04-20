from PIL import Image

# 1. 打开你抠好背景的透明 PNG 图片
img = Image.open('icon.png')

# 2. 准备图标需要的各种尺寸
icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# 3. 直接保存为包含多尺寸的 .ico 文件
img.save('logo.ico', format='ICO', sizes=icon_sizes)

print("完美的 .ico 图标已生成！")